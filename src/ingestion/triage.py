"""
Triage Engine for knowledgeVault-YT.

Two-phase classification:
  Phase 1: Rule-based pre-filter (< 1ms per video)
  Phase 2: LLM metadata classifier via Ollama (< 2s per video)
"""

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import ollama

from src.config import get_settings, load_prompt, load_verified_channels
from src.storage.sqlite_store import Video
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)


class TriageDecision(str, Enum):
    ACCEPT = "ACCEPTED"
    REJECT = "REJECTED"
    PENDING = "PENDING_REVIEW"
    NEEDS_LLM = "NEEDS_LLM"


@dataclass
class TriageResult:
    decision: TriageDecision
    reason: str
    confidence: float = 1.0
    is_tutorial: bool = False
    phase: str = "rule"       # "rule" or "llm"
    latency_ms: float = 0.0


class TriageEngine:
    """Two-phase triage engine: rule-based pre-filter + LLM classifier."""

    def __init__(self):
        self.settings = get_settings()
        self.triage_cfg = self.settings["triage"]
        self.ollama_cfg = self.settings["ollama"]

        # Load verified channels
        channels_cfg = load_verified_channels()
        self.verified_channel_ids = {
            ch["id"] for ch in channels_cfg.get("verified_channels", [])
        }
        self.shorts_whitelist = set(channels_cfg.get("shorts_whitelist", []))

        # Load LLM prompt
        self.triage_prompt = load_prompt("triage_classifier")

        # Keyword sets (compiled as word-boundary regex for accurate matching)
        import re
        raw_keywords = self.triage_cfg.get("knowledge_keywords", [])
        self.knowledge_keywords = raw_keywords
        self._keyword_patterns = {
            kw: re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
            for kw in raw_keywords
        }
        self.min_duration = self.triage_cfg.get("min_duration_seconds", 60)
        self.confidence_threshold = self.triage_cfg.get("llm_confidence_threshold", 0.7)

        # Batch triage prompt
        self.batch_triage_prompt = load_prompt("batch_triage_classifier")

    def classify(self, video: Video) -> TriageResult:
        """Run full triage pipeline on a video.

        Phase 1 is always attempted first. If the result is NEEDS_LLM,
        Phase 2 (LLM) is invoked.
        """
        # Phase 1: Rule-based
        result = self._rule_filter(video)
        if result.decision != TriageDecision.NEEDS_LLM:
            return result

        # Phase 2: LLM-based
        return self._llm_classify(video)

    def _rule_filter(self, video: Video) -> TriageResult:
        """Phase 1: Fast rule-based pre-filtering."""
        start = time.perf_counter()

        # Hard Reject: Ultra-short content (unless whitelisted)
        if video.duration_seconds < self.min_duration:
            if video.channel_id not in self.shorts_whitelist:
                latency = (time.perf_counter() - start) * 1000
                return TriageResult(
                    decision=TriageDecision.REJECT,
                    reason=f"duration_under_{self.min_duration}s",
                    confidence=1.0,
                    phase="rule",
                    latency_ms=latency,
                )

        # Hard Accept: Verified Knowledge channels
        if video.channel_id in self.verified_channel_ids:
            latency = (time.perf_counter() - start) * 1000
            return TriageResult(
                decision=TriageDecision.ACCEPT,
                reason="verified_channel",
                confidence=1.0,
                phase="rule",
                latency_ms=latency,
            )

        # Hard Accept: Educational keyword match in title (word-boundary)
        title_lower = video.title.lower()
        matched_keywords = [
            kw for kw, pattern in self._keyword_patterns.items()
            if pattern.search(title_lower)
        ]
        if matched_keywords:
            latency = (time.perf_counter() - start) * 1000
            return TriageResult(
                decision=TriageDecision.ACCEPT,
                reason=f"keyword_match: {', '.join(matched_keywords[:3])}",
                confidence=0.85,
                phase="rule",
                latency_ms=latency,
            )

        # Needs LLM classification
        latency = (time.perf_counter() - start) * 1000
        return TriageResult(
            decision=TriageDecision.NEEDS_LLM,
            reason="ambiguous_metadata",
            phase="rule",
            latency_ms=latency,
        )

    def _llm_classify(self, video: Video) -> TriageResult:
        """Phase 2: LLM-based metadata classification via Ollama."""
        start = time.perf_counter()

        user_prompt = self._build_triage_user_prompt(video)

        try:
            response = self._call_ollama_triage(user_prompt)

            raw_response = response["message"]["content"].strip()
            parsed = self._parse_llm_response(raw_response)
            latency = (time.perf_counter() - start) * 1000

            return self._finalize_triage_result(video, parsed, latency)

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            logger.error(f"LLM triage failed for {video.video_id}: {e}")
            return TriageResult(
                decision=TriageDecision.PENDING,
                reason=f"llm_error: {str(e)[:100]}",
                confidence=0.0,
                phase="llm",
                latency_ms=latency,
            )

    def batch_classify(self, videos: list[Video]) -> dict[str, TriageResult]:
        """Classify a batch of videos in a single LLM call for performance."""
        if not videos:
            return {}
        
        start = time.perf_counter()
        
        # Build a single prompt for all videos
        batch_content = []
        for v in videos:
            batch_content.append(
                f"ID: {v.video_id}\n"
                f"TITLE: {v.title}\n"
                f"DESCRIPTION: {v.description[:300]}\n"
                f"DURATION: {v.duration_seconds}s\n"
                f"TAGS: {', '.join(v.tags[:5]) if v.tags else 'none'}\n"
                f"---"
            )
        
        user_prompt = "\n".join(batch_content)
        
        try:
            # Note: We use the same _call_ollama_triage but with the batch prompt
            response = self._call_ollama_batch_triage(user_prompt)
            raw_response = response["message"]["content"].strip()
            parsed_batch = self._parse_llm_response(raw_response)
            
            latency_total = (time.perf_counter() - start) * 1000
            latency_per = latency_total / len(videos)
            
            results = {}
            for v in videos:
                vid = v.video_id
                if vid in parsed_batch:
                    results[vid] = self._finalize_triage_result(v, parsed_batch[vid], latency_per)
                else:
                    # Fallback if LLM missed this ID in the JSON
                    results[vid] = TriageResult(
                        decision=TriageDecision.PENDING,
                        reason="llm_batch_missing_id",
                        confidence=0.0,
                        phase="llm",
                        latency_ms=latency_per
                    )
            return results

        except Exception as e:
            logger.error(f"Batch LLM triage failed for {len(videos)} videos: {e}")
            latency = (time.perf_counter() - start) * 1000
            return {
                v.video_id: TriageResult(
                    decision=TriageDecision.PENDING,
                    reason=f"llm_batch_error: {str(e)[:50]}",
                    confidence=0.0,
                    phase="llm",
                    latency_ms=latency / len(videos)
                )
                for v in videos
            }

    def _finalize_triage_result(self, video: Video, parsed: dict, latency_ms: float) -> TriageResult:
        """Helper to convert parsed LLM JSON to TriageResult."""
        category = str(parsed.get("category", "AMBIGUOUS")).upper()
        confidence = float(parsed.get("confidence", 0.0))
        is_tutorial = bool(parsed.get("is_tutorial", False))

        if category == "KNOWLEDGE" and confidence >= self.confidence_threshold:
            decision = TriageDecision.ACCEPT
        elif category == "NOISE" and confidence >= self.confidence_threshold:
            decision = TriageDecision.REJECT
        else:
            decision = TriageDecision.PENDING

        logger.debug(f"Triage Result for {video.video_id}: {decision.value} ({confidence:.2f}), is_tutorial: {is_tutorial}")
        return TriageResult(
            decision=decision,
            reason=parsed.get("reason", "llm_classification"),
            confidence=confidence,
            is_tutorial=is_tutorial,
            phase="llm",
            latency_ms=latency_ms,
        )

    def _call_ollama_batch_triage(self, user_prompt: str) -> dict:
        """Call Ollama for batch triage classification."""
        from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
        pool = LLMPool()
        task = LLMTask(
            task_id=f"batch_triage_{int(time.time())}",
            fn=ollama.chat,
            kwargs={
                "model": self.ollama_cfg["triage_model"],
                "messages": [
                    {"role": "system", "content": self.batch_triage_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {
                    "num_predict": 1000, # Increased for batch results
                    "temperature": 0.05,
                },
            },
            priority=LLMPriority.LOW
        )
        future = pool.submit(task)
        return future.result(timeout=120)

    def _call_ollama_triage(self, user_prompt: str) -> dict:
        """Call Ollama for triage classification via PriorityPool."""
        from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
        pool = LLMPool()
        task = LLMTask(
            task_id=f"triage_{int(time.time())}",
            fn=ollama.chat,
            kwargs={
                "model": self.ollama_cfg["triage_model"],
                "messages": [
                    {"role": "system", "content": self.triage_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {
                    "num_predict": self.ollama_cfg.get("triage_max_tokens", 100),
                    "temperature": self.ollama_cfg.get("temperature", 0.1),
                },
            },
            priority=LLMPriority.LOW
        )
        
        try:
            future = pool.submit(task)
            return future.result(timeout=60)
        except Exception as e:
            if "timeout" in str(e).lower():
                logger.error(f"Ollama triage timeout: {e}")
                raise TimeoutError(f"Ollama inference timeout: {e}")
            raise

    def _build_triage_user_prompt(self, video: Video) -> str:
        """Build the user-message portion of the triage prompt."""
        tags_str = ", ".join(video.tags[:10]) if video.tags else "none"
        duration_str = f"{video.duration_seconds // 60}m {video.duration_seconds % 60}s"

        return (
            f"TITLE: {video.title}\n"
            f"DESCRIPTION: {video.description[:500]}\n"
            f"DURATION: {duration_str}\n"
            f"TAGS: {tags_str}"
        )

    def _parse_llm_response(self, response: str) -> dict:
        """Parse LLM JSON response with fallback handling."""
        # Try direct JSON parse
        try:
            # Strip markdown code fences if present
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean
                clean = clean.rsplit("```", 1)[0] if "```" in clean else clean
                clean = clean.strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from response text
        import re
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: mark as ambiguous
        logger.warning(f"Could not parse LLM triage response: {response[:200]}")
        return {
            "category": "AMBIGUOUS",
            "confidence": 0.0,
            "reason": "unparseable_response",
        }
