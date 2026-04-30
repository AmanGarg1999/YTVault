"""
Transcript acquisition module for knowledgeVault-YT.

Fetches transcripts using youtube-transcript-api with a priority-ordered
strategy: manual English → auto English → manual any → auto any.
"""

import logging
import time
import json
import urllib.request
import http.cookiejar
import requests
import yt_dlp
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 3, 5]  # seconds between retries

COOKIE_PATH = Path("data/youtube_cookies.txt")

def _get_youtube_session() -> requests.Session:
    session = requests.Session()
    if COOKIE_PATH.exists():
        try:
            cookie_jar = http.cookiejar.MozillaCookieJar(COOKIE_PATH)
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies.update(cookie_jar)
            logger.info("Loaded YouTube cookies from data/youtube_cookies.txt")
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
    return session

def _fetch_fallback_ytdlp(video_id: str) -> Optional["TranscriptResult"]:
    """Fallback to yt-dlp to extract json3 subtitles if youtube-transcript-api fails."""
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'skip_download': True,
        'quiet': True,
    }
    if COOKIE_PATH.exists():
        ydl_opts['cookiefile'] = str(COOKIE_PATH)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
            
            auto_subs = info.get('automatic_captions', {}).get('en', [])
            manual_subs = info.get('subtitles', {}).get('en', [])
            
            # Prefer manual subs over auto
            subs = manual_subs if manual_subs else auto_subs
            strategy = "manual_en" if manual_subs else "auto_en"
            
            json3_sub = next((s for s in subs if s['ext'] == 'json3'), None)
            if not json3_sub:
                logger.warning(f"No json3 subtitles found via yt-dlp for {video_id}")
                return None
                
            url = json3_sub['url']
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                
            segments = []
            for event in data.get('events', []):
                if 'segs' in event:
                    text = "".join(seg.get('utf8', '') for seg in event['segs']).replace('\n', ' ').strip()
                    if text:
                        start = event.get('tStartMs', 0) / 1000.0
                        duration = event.get('dDurationMs', 0) / 1000.0
                        segments.append(TimestampedSegment(text=text, start=start, duration=duration))
            
            if not segments:
                return None

            def format_ts(seconds):
                mins, secs = divmod(int(seconds), 60)
                return f"[{mins:02d}:{secs:02d}]"

            full_text = " ".join(f"{format_ts(seg.start)} {seg.text}" for seg in segments)
            
            logger.info(f"yt-dlp fallback successful for {video_id}: {len(segments)} segments")
            return TranscriptResult(
                segments=segments, full_text=full_text,
                strategy=strategy, language_iso="en",
                needs_translation=False
            )
            
    except Exception as e:
        logger.error(f"yt-dlp fallback failed for {video_id}: {e}")
        return None


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


def fetch_transcript(video_id: str, retry_count: int = 0) -> TranscriptResult:
    """Fetch transcript with priority-ordered fallback strategy and retry logic.

    Priority:
        1. Manual English transcript
        2. Auto-generated English transcript
        3. Manual transcript in any language (flagged for translation)
        4. Auto-generated transcript in any language (flagged for translation)

    Returns:
        TranscriptResult with segments, full text, and strategy info.
    """
    try:
        # List transcripts with retry
        transcript_list = None
        session = _get_youtube_session()
        for attempt in range(MAX_RETRIES):
            try:
                transcript_list = YouTubeTranscriptApi(http_client=session).list(video_id)
                break
            except (TranscriptsDisabled, VideoUnavailable):
                raise  # Don't retry on these errors
            except Exception as e:
                if "blocking requests" in str(e) or "429" in str(e):
                    wait_time = RETRY_DELAYS[attempt] * 10
                    logger.warning(f"IP Block detected for {video_id}. Retrying in {wait_time}s... ({e})")
                else:
                    wait_time = RETRY_DELAYS[attempt]
                    logger.warning(f"Transcript list attempt {attempt+1}/{MAX_RETRIES} failed for {video_id}, retrying in {wait_time}s: {e}")
                    
                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {MAX_RETRIES} transcript list attempts failed for {video_id}: {e}")
                    raise

        if transcript_list is None:
            logger.error(f"Could not list transcripts for {video_id}")
            return TranscriptResult(
                segments=[], full_text="", strategy="none",
                language_iso="", needs_translation=False,
                error="could_not_list_transcripts",
            )

    except (TranscriptsDisabled, VideoUnavailable) as e:
        logger.warning(f"Transcripts unavailable for {video_id}: {e}")
        return TranscriptResult(
            segments=[], full_text="", strategy="none",
            language_iso="", needs_translation=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Error listing transcripts for {video_id}: {e}")
        
        # Try yt-dlp fallback
        fallback_result = _fetch_fallback_ytdlp(video_id)
        if fallback_result:
            return fallback_result
            
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
        
        if not segments:
            return None

        def format_ts(seconds):
            mins, secs = divmod(int(seconds), 60)
            return f"[{mins:02d}:{secs:02d}]"

        full_text = " ".join(f"{format_ts(seg.start)} {seg.text}" for seg in segments)
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
        def format_ts(seconds):
            mins, secs = divmod(int(seconds), 60)
            return f"[{mins:02d}:{secs:02d}]"

        full_text = " ".join(f"{format_ts(seg.start)} {seg.text}" for seg in segments)
        strategy_type = "manual" if manual else "auto"
        logger.info(
            f"Fetched {strategy_type}_{language_iso} transcript for {video_id}: "
            f"{len(segments)} segments"
        )
        return segments, full_text, language_iso

    except Exception as e:
        logger.debug(f"Any-language transcript fetch failed (manual={manual}): {e}")
        return None
