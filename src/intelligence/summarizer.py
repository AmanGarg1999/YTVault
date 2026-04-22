"""
Summarizer engine for knowledgeVault-YT.

Generates hierarchical summaries, topics, and key takeaways from 
video transcripts using LLM synthesis with optional Map-Reduce 
for long transcripts.
"""

import json
import logging
import time
from typing import Optional

import ollama

from src.config import get_settings, load_prompt
from src.storage.sqlite_store import SQLiteStore, VideoSummary

logger = logging.getLogger(__name__)


class SummarizerEngine:
    """Orchestrates video summarization using map-reduce over all chunks.

    Map phase:  Summarize groups of chunks into bullet points (parallel via LLMPool).
    Reduce phase: Synthesize all bullet summaries into a final structured JSON.
    """

    def __init__(self, db: SQLiteStore):
        self.db = db
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self.deep_model = self.ollama_cfg.get("deep_model", self.ollama_cfg["triage_model"])
        self.map_prompt = load_prompt("map_reduce_summarizer")
        self.reduce_prompt = load_prompt("summarizer")
        self.blueprint_prompt = load_prompt("blueprint_extractor")
        self.reference_prompt = load_prompt("reference_extractor")

    def get_or_generate_summary(self, video_id: str, force: bool = False) -> Optional[VideoSummary]:
        """Get cached summary or generate a new one if missing or forced."""
        if not force:
            cached = self.db.get_video_summary(video_id)
            if cached:
                return cached
        return self.generate_summary(video_id)

    def generate_summary(self, video_id: str) -> Optional[VideoSummary]:
        """Generate a hierarchical summary using map-reduce over ALL chunks."""
        logger.info(f"Generating map-reduce summary for video: {video_id}")

        chunks = self.db.get_chunks_for_video(video_id)
        if not chunks:
            logger.warning(f"No chunks found for video {video_id}, cannot summarize.")
            return None

        try:
            # --- Map phase: summarize chunk groups into bullets ---
            group_size = 4  # chunks per group
            groups = [
                chunks[i:i + group_size]
                for i in range(0, len(chunks), group_size)
            ]

            from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
            pool = LLMPool()

            map_tasks = [
                LLMTask(
                    task_id=f"group_{i}",
                    fn=self._map_summarize_group,
                    args=(group,),
                    priority=LLMPriority.LOW
                )
                for i, group in enumerate(groups)
            ]

            map_results = pool.submit_batch(map_tasks)
            bullet_summaries = []
            for lr in sorted(map_results, key=lambda r: r.task_id):
                if lr.success and lr.result:
                    bullet_summaries.append(lr.result)

            if not bullet_summaries:
                logger.warning(f"Map phase produced no summaries for {video_id}")
                return None

            # --- Reduce phase: synthesize into final structured output ---
            combined_bullets = "\n\n".join(bullet_summaries)
            data = self._reduce_synthesize(combined_bullets)
            if not data:
                return None

            summary = VideoSummary(
                video_id=video_id,
                summary_text=data.get("summary", ""),
                topics_json=json.dumps(data.get("topics", [])),
                takeaways_json=json.dumps(data.get("takeaways", [])),
                entities_json=json.dumps(data.get("primary_entities", [])),
                references_json=json.dumps(data.get("references", [])),
                timeline_json=json.dumps(data.get("narrative_timeline", [])),
            )

            # Persist summary
            self.db.upsert_video_summary(summary)

            # --- Advanced Intelligence Persistence ---
            
            # 1. Actionable Blueprints
            blueprint_steps = data.get("actionable_blueprint", [])
            if blueprint_steps:
                self.db.upsert_blueprint(video_id, blueprint_steps)

            # 2. Expert Clashes (Disagreements)
            disagreements = data.get("expert_disagreements", [])
            video_obj = self.db.get_video(video_id)
            channel_name = "Unknown"
            if video_obj:
                channel = self.db.get_channel(video_obj.channel_id)
                if channel:
                    channel_name = channel.name

            for d in disagreements:
                from src.storage.sqlite_store import ExpertClash
                self.db.insert_clash(ExpertClash(
                    topic=d.get("topic", "General"),
                    expert_a=d.get("expert_a", channel_name),
                    expert_b=d.get("expert_b", "Unknown"),
                    claim_a=d.get("claim_a", ""),
                    claim_b=d.get("claim_b", ""),
                    source_a=video_id
                ))

            # 3. Sentiment Heatmap
            timeline = data.get("narrative_timeline", [])
            for entry in timeline:
                from src.storage.sqlite_store import VideoSentiment
                # We approximate chunk_id link by matching topic if possible, 
                # but for now we store video-level timeline sentiment.
                self.db.insert_sentiment(VideoSentiment(
                    video_id=video_id,
                    score=entry.get("sentiment_score", 0.0),
                    label=entry.get("sentiment_label", "Neutral")
                ))

            # 4. External Citations
            refs = data.get("references", [])
            for r in refs:
                if isinstance(r, dict):
                    self.db.insert_citation(
                        video_id=video_id,
                        name=r.get("name", ""),
                        url=r.get("url", ""),
                        c_type=r.get("type", "OTHER")
                    )

            logger.info(f"Map-reduce summary complete for {video_id} ({len(groups)} groups)")
            return summary

        except Exception as e:
            logger.error(f"Summarization failed for {video_id}: {e}")
            return None

    def _map_summarize_group(self, group: list) -> str:
        """Map phase: summarize a group of chunks into bullet points."""
        group_text = " ".join(c.cleaned_text or c.raw_text for c in group)
        # Truncate to fit context window
        group_text = group_text[:12000]

        response = ollama.chat(
            model=self.deep_model,
            messages=[
                {"role": "system", "content": self.map_prompt},
                {"role": "user", "content": group_text},
            ],
            options={
                "num_predict": self.ollama_cfg.get("map_max_tokens", 800),
                "temperature": 0.1,
            },
        )
        return response["message"]["content"].strip()

    def _reduce_synthesize(self, combined_bullets: str) -> Optional[dict]:
        """Reduce phase: synthesize all bullet summaries into structured JSON."""
        # Truncate if too long for context window
        if len(combined_bullets) > 25000:
            combined_bullets = combined_bullets[:25000] + "\n[... truncated ...]"

        from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
        pool = LLMPool()
        t_id = int(time.time())
        
        task_sum = LLMTask(
            task_id=f"reduce_{t_id}",
            fn=ollama.chat,
            kwargs={
                "model": self.deep_model,
                "messages": [
                    {"role": "system", "content": self.reduce_prompt},
                    {"role": "user", "content": combined_bullets},
                ],
                "options": {"num_predict": self.ollama_cfg.get("reduce_max_tokens", 2000), "temperature": 0.1},
            },
            priority=LLMPriority.LOW
        )
        task_blue = LLMTask(
            task_id=f"blueprint_{t_id}",
            fn=ollama.chat,
            kwargs={
                "model": self.deep_model,
                "messages": [
                    {"role": "system", "content": self.blueprint_prompt},
                    {"role": "user", "content": combined_bullets},
                ],
                "options": {"num_predict": self.ollama_cfg.get("blueprint_max_tokens", 1200), "temperature": 0.1},
            },
            priority=LLMPriority.LOW
        )
        task_ref = LLMTask(
            task_id=f"reference_{t_id}",
            fn=ollama.chat,
            kwargs={
                "model": self.deep_model,
                "messages": [
                    {"role": "system", "content": self.reference_prompt},
                    {"role": "user", "content": combined_bullets},
                ],
                "options": {"num_predict": self.ollama_cfg.get("extraction_max_tokens", 800), "temperature": 0.1},
            },
            priority=LLMPriority.LOW
        )

        try:
            results = pool.submit_batch([task_sum, task_blue, task_ref])
            
            # Map back to specific tasks
            res_dict = {r.task_id: r.result for r in filter(lambda x: x.success, results)}
            
            raw_sum = res_dict.get(f"reduce_{t_id}", {}).get("message", {}).get("content", "")
            raw_blue = res_dict.get(f"blueprint_{t_id}", {}).get("message", {}).get("content", "")
            raw_ref = res_dict.get(f"reference_{t_id}", {}).get("message", {}).get("content", "")
            
            data = self._parse_json_response(raw_sum)
            if not isinstance(data, dict):
                data = {}
                
            blue_data = self._parse_json_response(raw_blue)
            data["actionable_blueprint"] = blue_data if isinstance(blue_data, list) else []
            
            ref_data = self._parse_json_response(raw_ref)
            data["references"] = ref_data if isinstance(ref_data, list) else []
            
            return data
        except Exception as e:
            logger.error(f"Reduce phase (fan-out) failed via pool: {e}")
            return None

    def _parse_json_response(self, content: str):
        """Extract and parse JSON from LLM response using strict bounding."""
        if not content:
            return None
        try:
            # Clean generic markdown fences first
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            content = content.strip()
            
            # Find the boundaries of the JSON object or array
            start_idx = -1
            end_idx = -1
            
            dict_start = content.find("{")
            array_start = content.find("[")
            
            if dict_start != -1 and (array_start == -1 or dict_start < array_start):
                start_idx = dict_start
                end_idx = content.rfind("}")
            elif array_start != -1:
                start_idx = array_start
                end_idx = content.rfind("]")
                
            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                content = content[start_idx:end_idx+1]
                
            return json.loads(content)
        except (json.JSONDecodeError, IndexError, ValueError) as e:
            logger.debug(f"JSON parsing failed: {e}. Raw content: {content[:100]}...")
            return None
