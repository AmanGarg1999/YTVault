"""
Refinement layer for knowledgeVault-YT.

Handles:
  1. SponsorBlock integration — strip sponsored/intro/outro segments
  2. Text normalization — remove fillers, fix punctuation via Ollama LLM
"""

import json as _json
import logging
import time
from dataclasses import dataclass

import ollama
import requests

from src.config import get_settings, load_prompt
from src.ingestion.transcript import TimestampedSegment
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SponsorBlock Integration
# ---------------------------------------------------------------------------

@dataclass
class SponsorSegment:
    """A SponsorBlock skip segment."""
    start: float
    end: float
    category: str


def fetch_sponsor_segments(video_id: str) -> list[SponsorSegment]:
    """Fetch crowd-sourced sponsor/intro/outro segments from SponsorBlock API.

    Returns empty list on failure (graceful degradation).
    """
    settings = get_settings()
    cfg = settings["refinement"]

    try:
        response = requests.get(
            cfg["sponsorblock_api"],
            params={
                "videoID": video_id,
                "categories": _json.dumps(cfg["sponsorblock_categories"]),
            },
            timeout=cfg.get("sponsorblock_timeout", 5),
        )

        if response.status_code == 200:
            segments = [
                SponsorSegment(
                    start=s["segment"][0],
                    end=s["segment"][1],
                    category=s["category"],
                )
                for s in response.json()
            ]
            logger.info(
                f"SponsorBlock: {len(segments)} segments for {video_id} "
                f"({', '.join(s.category for s in segments)})"
            )
            return segments
        elif response.status_code == 404:
            logger.debug(f"SponsorBlock: no data for {video_id}")
            return []
        else:
            logger.warning(
                f"SponsorBlock API returned {response.status_code} for {video_id}"
            )
            return []

    except requests.RequestException as e:
        logger.warning(f"SponsorBlock API error for {video_id}: {e}")
        return []


def strip_sponsored_segments(
    segments: list[TimestampedSegment],
    sponsor_segments: list[SponsorSegment],
) -> list[TimestampedSegment]:
    """Remove transcript segments that fall within sponsor time ranges.

    A transcript segment is removed if its midpoint falls within a sponsor segment.
    """
    if not sponsor_segments:
        return segments

    def is_sponsored(seg: TimestampedSegment) -> bool:
        midpoint = seg.start + (seg.duration / 2)
        return any(sp.start <= midpoint <= sp.end for sp in sponsor_segments)

    filtered = [seg for seg in segments if not is_sponsored(seg)]
    removed = len(segments) - len(filtered)
    if removed > 0:
        logger.info(f"Stripped {removed}/{len(segments)} sponsored segments")
    return filtered


# ---------------------------------------------------------------------------
# Text Normalization via LLM
# ---------------------------------------------------------------------------

class TextNormalizer:
    """Normalizes transcript text using a local LLM via Ollama.

    Removes verbal fillers, fixes punctuation, and merges broken sentences
    while preserving all factual content.
    """

    def __init__(self):
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self.refinement_cfg = self.settings["refinement"]
        self.system_prompt = load_prompt("text_normalizer")

    def normalize(self, text: str) -> str:
        """Normalize a transcript text through the LLM.

        Long texts are processed in chunks to stay within the model's
        context window.
        """
        if not text.strip():
            return ""

        chunk_size = self.refinement_cfg.get("normalizer_chunk_size", 1000)
        overlap = self.refinement_cfg.get("normalizer_chunk_overlap", 100)

        words = text.split()
        if len(words) <= chunk_size:
            return self._normalize_chunk(text)

        # Process in overlapping chunks using LLMPool
        from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
        pool = LLMPool()
        
        tasks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            
            tasks.append(LLMTask(
                task_id=f"normalize_{start}",
                fn=self._normalize_chunk,
                args=(chunk_text,),
                priority=LLMPriority.MEDIUM
            ))
            start += chunk_size - overlap

        results = pool.submit_batch(tasks)
        
        # Sort results by task_id to maintain order
        sorted_results = sorted(results, key=lambda r: int(r.task_id.split("_")[1]))
        chunks = [r.result for r in sorted_results if r.success and r.result]
        
        if not chunks:
            logger.warning("All normalization chunks failed, returning original text.")
            return text

        # Merge chunks (overlap handling: use the first chunk's version)
        return self._merge_overlapping_chunks(chunks, overlap)

    def _normalize_chunk(self, text: str) -> str:
        """Normalize a single chunk of text via Ollama."""
        start_time = time.perf_counter()

        try:
            # Note: This is called by the LLMPool worker thread
            response = self._call_ollama_normalize(text)

            result = response["message"]["content"].strip()
            latency = (time.perf_counter() - start_time) * 1000
            word_count = len(text.split())
            logger.debug(
                f"Normalized {word_count} words in {latency:.0f}ms"
            )
            return result

        except Exception as e:
            logger.error(f"Text normalization chunk failed: {e}")
            # Fallback: return original text (better than losing content)
            return text

    @with_retry("ollama_inference")
    def _call_ollama_normalize(self, text: str) -> dict:
        """Call Ollama for text normalization with retry."""
        from src.utils.llm_pool import get_llm_semaphore
        with get_llm_semaphore():
            return ollama.chat(
                model=self.ollama_cfg["normalizer_model"],
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text},
                ],
                options={
                    "num_predict": self.ollama_cfg.get("normalizer_max_tokens", 2048),
                    "temperature": 0.05,
                },
            )

    def _merge_overlapping_chunks(self, chunks: list[str], overlap_words: int) -> str:
        """Merge overlapping normalized chunks.

        Simple strategy: take the full first chunk, then for subsequent chunks,
        skip the first `overlap_words` words (they overlap with the previous chunk).
        """
        if not chunks:
            return ""
        if len(chunks) == 1:
            return chunks[0]

        merged = [chunks[0]]
        for chunk in chunks[1:]:
            words = chunk.split()
            # Skip overlap region
            skip = min(overlap_words, len(words) // 2)
            merged.append(" ".join(words[skip:]))

        return " ".join(merged)


def quick_normalize(text: str) -> str:
    """Quick regex-based normalization as a lightweight alternative.

    Removes common fillers without requiring LLM inference.
    Useful for fast pre-processing or when Ollama is unavailable.
    """
    import re

    # Common verbal fillers
    fillers = [
        r'\b(?:um|uh|uhm|umm)\b',
        r'\byou know\b',
        r'\bbasically\b',
        r'\bsort of\b',
        r'\bkind of\b',
        r'\bI mean\b',
        r'\bright\?\s*',
        r'\blike,?\s+(?=\w)',  # "like" as filler (rough heuristic)
    ]

    result = text
    for pattern in fillers:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)

    # Clean up extra whitespace
    result = re.sub(r'\s{2,}', ' ', result).strip()

    return result
