"""
Transcript acquisition module for knowledgeVault-YT.

Fetches transcripts using youtube-transcript-api with a priority-ordered
strategy: manual English → auto English → manual any → auto any.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)


@dataclass
class TimestampedSegment:
    """A single transcript segment with timing info."""
    text: str
    start: float       # seconds
    duration: float     # seconds

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class TranscriptResult:
    """Result of a transcript acquisition attempt."""
    segments: list[TimestampedSegment]
    full_text: str
    strategy: str           # "manual_en", "auto_en", "manual_any", "auto_any", "none"
    language_iso: str
    needs_translation: bool
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.segments) > 0


def fetch_transcript(video_id: str) -> TranscriptResult:
    """Fetch transcript with priority-ordered fallback strategy.

    Priority:
        1. Manual English transcript
        2. Auto-generated English transcript
        3. Manual transcript in any language (flagged for translation)
        4. Auto-generated transcript in any language (flagged for translation)

    Returns:
        TranscriptResult with segments, full text, and strategy info.
    """
    try:
        # Use a more robust check for list_transcripts (recent versions of the library)
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        else:
            # Fallback for very old versions or unexpected library state
            logger.warning(f"list_transcripts missing on YouTubeTranscriptApi — checking for alternative methods")
            # We skip list-based priority but try to fetch default 'en' directly
            # This is a last-resort fallback for broken environments
            default_transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
            if default_transcript:
                return TranscriptResult(
                    segments=[TimestampedSegment(text=s["text"], start=s["start"], duration=s["duration"]) 
                             for s in default_transcript],
                    full_text=" ".join(s["text"] for s in default_transcript),
                    strategy="auto_en", language_iso="en", needs_translation=False
                )
            raise AttributeError("YouTubeTranscriptApi has no 'list_transcripts' method")

    except (TranscriptsDisabled, VideoUnavailable) as e:
        logger.warning(f"Transcripts unavailable for {video_id}: {e}")
        return TranscriptResult(
            segments=[], full_text="", strategy="none",
            language_iso="", needs_translation=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Error listing transcripts for {video_id}: {e}")
        return TranscriptResult(
            segments=[], full_text="", strategy="none",
            language_iso="", needs_translation=False,
            error=str(e),
        )

    # Strategy 1: Manual English
    result = _try_fetch(transcript_list, video_id, language="en", manual=True)
    if result:
        return TranscriptResult(
            segments=result[0], full_text=result[1],
            strategy="manual_en", language_iso="en",
            needs_translation=False,
        )

    # Strategy 2: Auto-generated English
    result = _try_fetch(transcript_list, video_id, language="en", manual=False)
    if result:
        return TranscriptResult(
            segments=result[0], full_text=result[1],
            strategy="auto_en", language_iso="en",
            needs_translation=False,
        )

    # Strategy 3: Manual in any language
    result = _try_fetch_any(transcript_list, video_id, manual=True)
    if result:
        return TranscriptResult(
            segments=result[0], full_text=result[1],
            strategy="manual_any", language_iso=result[2],
            needs_translation=True,
        )

    # Strategy 4: Auto-generated in any language
    result = _try_fetch_any(transcript_list, video_id, manual=False)
    if result:
        return TranscriptResult(
            segments=result[0], full_text=result[1],
            strategy="auto_any", language_iso=result[2],
            needs_translation=True,
        )

    logger.warning(f"No transcript found for {video_id}")
    return TranscriptResult(
        segments=[], full_text="", strategy="none",
        language_iso="", needs_translation=False,
        error="no_transcript_available",
    )


def _try_fetch(
    transcript_list, video_id: str, language: str, manual: bool
) -> Optional[tuple[list[TimestampedSegment], str]]:
    """Try to fetch a specific transcript type."""
    try:
        if manual:
            transcript = transcript_list.find_manually_created_transcript([language])
        else:
            transcript = transcript_list.find_generated_transcript([language])

        raw_segments = transcript.fetch()
        segments = [
            TimestampedSegment(
                text=seg.text if hasattr(seg, "text") else seg["text"],
                start=seg.start if hasattr(seg, "start") else seg["start"],
                duration=seg.duration if hasattr(seg, "duration") else seg["duration"],
            )
            for seg in raw_segments
        ]
        full_text = " ".join(seg.text for seg in segments)
        strategy_type = "manual" if manual else "auto"
        logger.info(
            f"Fetched {strategy_type}_{language} transcript for {video_id}: "
            f"{len(segments)} segments, {len(full_text)} chars"
        )
        return segments, full_text

    except NoTranscriptFound:
        return None
    except Exception as e:
        logger.debug(f"Transcript fetch failed ({language}, manual={manual}): {e}")
        return None


def _try_fetch_any(
    transcript_list, video_id: str, manual: bool
) -> Optional[tuple[list[TimestampedSegment], str, str]]:
    """Try to fetch a transcript in any available language.

    Uses the public iterator API to avoid reliance on private attributes.
    """
    try:
        # Filter transcripts by type using the public API
        candidates = [
            t for t in transcript_list
            if (not manual and t.is_generated) or (manual and not t.is_generated)
        ]

        if not candidates:
            return None

        # Use the first available transcript
        transcript = candidates[0]
        language_iso = transcript.language_code

        raw_segments = transcript.fetch()
        segments = [
            TimestampedSegment(
                text=seg.text if hasattr(seg, "text") else seg["text"],
                start=seg.start if hasattr(seg, "start") else seg["start"],
                duration=seg.duration if hasattr(seg, "duration") else seg["duration"],
            )
            for seg in raw_segments
        ]
        full_text = " ".join(seg.text for seg in segments)
        strategy_type = "manual" if manual else "auto"
        logger.info(
            f"Fetched {strategy_type}_{language_iso} transcript for {video_id}: "
            f"{len(segments)} segments"
        )
        return segments, full_text, language_iso

    except Exception as e:
        logger.debug(f"Any-language transcript fetch failed (manual={manual}): {e}")
        return None
