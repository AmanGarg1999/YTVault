"""
Chunk-level deep analysis for knowledgeVault-YT.

Runs topic extraction, entity extraction, claim extraction, and quote
extraction on every transcript chunk — not just the first N characters.
Uses LLMPool for concurrent processing.
"""

import json
import logging
from typing import Optional

import ollama

from src.config import get_settings, load_prompt
from src.storage.sqlite_store import SQLiteStore, TranscriptChunk, Claim, Quote
from src.utils.llm_pool import LLMPool, LLMTask

logger = logging.getLogger(__name__)


class ChunkAnalyzer:
    """Analyzes individual transcript chunks for topics, entities, claims, and quotes.

    Designed to be called from the pipeline's CHUNK_ANALYZED stage.
    Processes all chunks for a video in parallel via LLMPool.
    """

    def __init__(self, db: SQLiteStore):
        self.db = db
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self.fast_model = self.ollama_cfg["triage_model"]
        self.deep_model = self.ollama_cfg.get("deep_model", self.fast_model)

        # Load prompts
        self.topic_prompt = load_prompt("topic_extractor")
        self.entity_prompt = load_prompt("entity_extractor")
        self.claim_prompt = load_prompt("claim_extractor")
        self.quote_prompt = load_prompt("quote_extractor")

    def analyze_video_chunks(self, video_id: str) -> dict:
        """Run full analysis on all chunks for a video.

        Returns:
            Dict with counts: {"topics": N, "entities": N, "claims": N, "quotes": N}
        """
        chunks = self.db.get_chunks_for_video(video_id)
        if not chunks:
            logger.warning(f"No chunks found for video {video_id}")
            return {"topics": 0, "entities": 0, "claims": 0, "quotes": 0}

        logger.info(f"Analyzing {len(chunks)} chunks for video {video_id}")

        pool = LLMPool()
        tasks = [
            LLMTask(
                task_id=chunk.chunk_id,
                fn=self._analyze_single_chunk,
                args=(chunk,),
            )
            for chunk in chunks
        ]

        results = pool.submit_batch(tasks)

        totals = {"topics": 0, "entities": 0, "claims": 0, "quotes": 0}
        for lr in results:
            if lr.success and lr.result:
                for key in totals:
                    totals[key] += lr.result.get(key, 0)

        logger.info(
            f"Chunk analysis complete for {video_id}: "
            f"{totals['topics']} topics, {totals['entities']} entities, "
            f"{totals['claims']} claims, {totals['quotes']} quotes"
        )
        return totals

    def _analyze_single_chunk(self, chunk: TranscriptChunk) -> dict:
        """Analyze a single chunk: extract topics, entities, claims, quotes."""
        text = chunk.cleaned_text or chunk.raw_text
        if not text or len(text.split()) < 20:
            return {"topics": 0, "entities": 0, "claims": 0, "quotes": 0}

        # Run all four extractions
        topics = self._extract_topics(text)
        entities = self._extract_entities(text)
        claims = self._extract_claims(text, chunk)
        quotes = self._extract_quotes(text, chunk)

        # Save analysis to chunk record
        self.db.update_chunk_analysis(
            chunk_id=chunk.chunk_id,
            topics_json=json.dumps(topics),
            entities_json=json.dumps(entities),
            claims_json=json.dumps(claims),
            quotes_json=json.dumps(quotes),
        )

        # Persist claims and quotes to their dedicated tables
        for c in claims:
            self.db.insert_claim(Claim(
                video_id=chunk.video_id,
                chunk_id=chunk.chunk_id,
                speaker=c.get("speaker", ""),
                claim_text=c.get("claim", ""),
                topic=c.get("topic", ""),
                timestamp=chunk.start_timestamp,
                confidence=c.get("confidence", 0.5),
            ))

        for q in quotes:
            self.db.insert_quote(Quote(
                video_id=chunk.video_id,
                chunk_id=chunk.chunk_id,
                speaker=q.get("speaker", ""),
                quote_text=q.get("quote", ""),
                topic=q.get("topic", ""),
                timestamp=chunk.start_timestamp,
            ))

        return {
            "topics": len(topics),
            "entities": len(entities),
            "claims": len(claims),
            "quotes": len(quotes),
        }

    def _extract_topics(self, text: str) -> list[dict]:
        """Extract topics from chunk text."""
        return self._call_llm_json_list(
            self.fast_model, self.topic_prompt, text[:3000], "topic"
        )

    def _extract_entities(self, text: str) -> list[dict]:
        """Extract person entities from chunk text."""
        return self._call_llm_json_list(
            self.fast_model, self.entity_prompt, text[:2000], "entity"
        )

    def _extract_claims(self, text: str, chunk: TranscriptChunk) -> list[dict]:
        """Extract claims/assertions from chunk text using the deep model."""
        return self._call_llm_json_list(
            self.deep_model, self.claim_prompt, text[:3000], "claim"
        )

    def _extract_quotes(self, text: str, chunk: TranscriptChunk) -> list[dict]:
        """Extract notable quotes from chunk text using the deep model."""
        return self._call_llm_json_list(
            self.deep_model, self.quote_prompt, text[:3000], "quote"
        )

    def _call_llm_json_list(
        self, model: str, system_prompt: str, text: str, label: str
    ) -> list[dict]:
        """Call Ollama and parse a JSON array response. Returns [] on failure."""
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                options={"num_predict": 500, "temperature": 0.1},
            )
            raw = response["message"]["content"].strip()
            return self._parse_json_array(raw)
        except Exception as e:
            logger.debug(f"{label} extraction failed: {e}")
            return []

    def _parse_json_array(self, raw: str) -> list[dict]:
        """Parse a JSON array from LLM response with fence stripping."""
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean
            clean = clean.rsplit("```", 1)[0].strip()
        try:
            result = json.loads(clean)
            if isinstance(result, list):
                return [item for item in result if isinstance(item, dict)]
        except json.JSONDecodeError:
            pass
        return []
