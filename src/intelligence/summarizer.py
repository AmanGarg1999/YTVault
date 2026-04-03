"""
Summarizer engine for knowledgeVault-YT.

Generates hierarchical summaries, topics, and key takeaways from 
video transcripts using LLM synthesis with optional Map-Reduce 
for long transcripts.
"""

import json
import logging
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

            from src.utils.llm_pool import LLMPool, LLMTask
            pool = LLMPool()

            map_tasks = [
                LLMTask(
                    task_id=f"group_{i}",
                    fn=self._map_summarize_group,
                    args=(group,),
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

            self.db.upsert_video_summary(summary)
            logger.info(f"Map-reduce summary complete for {video_id} ({len(groups)} groups)")
            return summary

        except Exception as e:
            logger.error(f"Summarization failed for {video_id}: {e}")
            return None

    def _map_summarize_group(self, group: list) -> str:
        """Map phase: summarize a group of chunks into bullet points."""
        group_text = " ".join(c.cleaned_text or c.raw_text for c in group)
        # Truncate to fit context window
        group_text = group_text[:8000]

        response = ollama.chat(
            model=self.deep_model,
            messages=[
                {"role": "system", "content": self.map_prompt},
                {"role": "user", "content": group_text},
            ],
            options={"num_predict": 500, "temperature": 0.1},
        )
        return response["message"]["content"].strip()

    def _reduce_synthesize(self, combined_bullets: str) -> Optional[dict]:
        """Reduce phase: synthesize all bullet summaries into structured JSON."""
        # Truncate if too long for context window
        if len(combined_bullets) > 15000:
            combined_bullets = combined_bullets[:15000] + "\n[... truncated ...]"

        response = ollama.chat(
            model=self.deep_model,
            messages=[
                {"role": "system", "content": self.reduce_prompt},
                {"role": "user", "content": combined_bullets},
            ],
            options={"num_predict": 1500, "temperature": 0.1},
        )
        return self._parse_json_response(response["message"]["content"].strip())

    def _parse_json_response(self, content: str) -> Optional[dict]:
        """Extract and parse JSON from LLM response."""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            logger.debug(f"JSON parsing failed: {e}. Raw content: {content[:100]}...")
            return None
