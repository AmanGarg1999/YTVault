"""
Discovery module for knowledgeVault-YT.

Handles URL parsing, yt-dlp metadata extraction, and video queue management.
Enforces the "No Media Download" policy — only metadata and transcripts.
"""

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

from src.storage.sqlite_store import Channel, Video
from src.utils.retry import with_retry
from src.utils.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)

# yt-dlp Circuit Breaker
YTDLP_BREAKER = get_circuit_breaker("yt-dlp", failure_threshold=3, recovery_timeout=120)

# Rate limiting configuration
YTDLP_RATE_LIMIT_DELAY = 1.0  # seconds between requests
YTDLP_LAST_REQUEST_TIME = 0  # Module-level tracking


def _apply_rate_limit():
    """Apply rate limiting between yt-dlp requests."""
    global YTDLP_LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - YTDLP_LAST_REQUEST_TIME
    if elapsed < YTDLP_RATE_LIMIT_DELAY:
        delay = YTDLP_RATE_LIMIT_DELAY - elapsed
        logger.debug(f"Rate limiting: sleeping {delay:.2f}s")
        time.sleep(delay)
    YTDLP_LAST_REQUEST_TIME = time.time()


# ---------------------------------------------------------------------------
# URL Parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsedURL:
    """Result of parsing a YouTube URL."""
    url_type: str   # "video" | "playlist" | "channel"
    video_id: Optional[str] = None
    playlist_id: Optional[str] = None
    channel_handle: Optional[str] = None
    channel_id: Optional[str] = None
    raw_url: str = ""


def parse_youtube_url(url: str) -> ParsedURL:
    """Parse a YouTube URL into its type and identifiers.

    Supports:
        - youtube.com/watch?v=XXXX
        - youtu.be/XXXX
        - youtube.com/playlist?list=XXXX
        - youtube.com/@handle
        - youtube.com/channel/XXXX
        - youtube.com/c/XXXX
    """
    url = url.strip()

    # Single video: /watch?v= or youtu.be/
    # A watch URL with both v= and list= is treated as a video (the user
    # navigated to a specific video, even if it's part of a playlist).
    video_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    if video_match and ('watch' in url or 'youtu.be' in url):
        return ParsedURL(
            url_type="video",
            video_id=video_match.group(1),
            raw_url=url,
        )

    # Playlist (only matches when there is no v= present)
    playlist_match = re.search(r'list=([a-zA-Z0-9_-]+)', url)
    if playlist_match:
        return ParsedURL(
            url_type="playlist",
            playlist_id=playlist_match.group(1),
            raw_url=url,
        )

    # Channel handle: /@handle or just @handle
    handle_match = re.search(r'(?:youtube\.com/)?@([a-zA-Z0-9_.-]+)', url)
    if handle_match:
        return ParsedURL(
            url_type="channel",
            channel_handle=handle_match.group(1),
            raw_url=f"https://www.youtube.com/@{handle_match.group(1)}",
        )

    # Channel ID: /channel/UCXXXX
    channel_match = re.search(r'youtube\.com/channel/([a-zA-Z0-9_-]+)', url)
    if channel_match:
        return ParsedURL(
            url_type="channel",
            channel_id=channel_match.group(1),
            raw_url=url,
        )

    # Custom URL: /c/name
    custom_match = re.search(r'youtube\.com/c/([a-zA-Z0-9_.-]+)', url)
    if custom_match:
        return ParsedURL(
            url_type="channel",
            channel_handle=custom_match.group(1),
            raw_url=url,
        )

    raise ValueError(f"Unable to parse YouTube URL: {url}")


# ---------------------------------------------------------------------------
# yt-dlp Metadata Extraction
# ---------------------------------------------------------------------------

@with_retry("yt_dlp_metadata")
def _run_ytdlp(args: list[str], timeout: int = 180) -> str:
    """Run yt-dlp with given arguments and return stdout.

    Wrapped with a Circuit Breaker to prevent hanging on YouTube blocks.
    """
    return YTDLP_BREAKER.call(_run_ytdlp_raw, args, timeout)


def _run_ytdlp_raw(args: list[str], timeout: int = 180) -> str:
    """Inner yt-dlp execution logic."""
    import os as _os
    cmd = [
        "yt-dlp", "--no-download", "--no-check-certificate", "--force-ipv4",
        "--extractor-args", "youtube:player_client=android,web",
        "--quiet", "--no-warnings"
    ] + args
    logger.debug(f"Running: {' '.join(cmd)}")

    # Isolate env: inherit PATH but force UTF-8 locale
    # Add common pip and snap locations to PATH
    curr_path = _os.environ.get("PATH", "")
    extra_paths = [
        "/usr/bin", "/usr/local/bin", 
        _os.path.expanduser("~/.local/bin"),
        "/snap/bin"
    ]
    env = {
        "PATH": f"{curr_path}:{':'.join(p for p in extra_paths if p not in curr_path)}".strip(":"),
        "HOME": _os.environ.get("HOME", "/tmp"),
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
    }

    import shutil as _shutil
    if not _shutil.which(cmd[0]):
        # Try to find in extra paths manually
        for p in extra_paths:
            full_p = _os.path.join(p, cmd[0])
            if _os.path.exists(full_p):
                cmd[0] = full_p
                break

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
    except FileNotFoundError:
        logger.error(f"yt-dlp executable not found. PATH: {env['PATH']}")
        raise RuntimeError(f"yt-dlp not found. Please install it and ensure it is in your PATH.")

    if result.returncode != 0:
        logger.error(f"yt-dlp exited with code {result.returncode}: {result.stderr[:500]}")
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:200]}")
    
    if not result.stdout.strip():
        logger.error(f"yt-dlp returned empty output. stderr: {result.stderr[:500]}")
        raise RuntimeError(f"yt-dlp returned empty output")
    
    return result.stdout


def _run_ytdlp_stream(args: list[str]):
    """Run yt-dlp and yield stdout line by line."""
    import os as _os
    cmd = [
        "yt-dlp", "--no-download", "--no-check-certificate", "--force-ipv4",
        "--extractor-args", "youtube:player_client=android,web",
        "--quiet", "--no-warnings"
    ] + args
    
    curr_path = _os.environ.get("PATH", "")
    extra_paths = [
        "/usr/bin", "/usr/local/bin", 
        _os.path.expanduser("~/.local/bin"),
        "/snap/bin"
    ]
    env = {
        "PATH": f"{curr_path}:{':'.join(p for p in extra_paths if p not in curr_path)}".strip(":"),
        "HOME": _os.environ.get("HOME", "/tmp"),
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
    }

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            text=True, env=env, bufsize=1, universal_newlines=True
        )
        for line in process.stdout:
            yield line.strip()
        
        process.wait()
        if process.returncode != 0:
            stderr = process.stderr.read()
            logger.warning(f"yt-dlp stream (code {process.returncode}) failed: {stderr[:200]}")
    except Exception as e:
        logger.error(f"yt-dlp stream error: {e}")


def extract_video_metadata(video_id: str) -> tuple[Video, Channel]:
    """Extract full metadata for a single video using yt-dlp.

    No media files are downloaded (--no-download flag enforced).
    Returns both the Video and a shallow Channel model for FK constraints.
    """
    _apply_rate_limit()  # Rate limiting
    url = f"https://www.youtube.com/watch?v={video_id}"
    raw = _run_ytdlp(["--dump-json", "--no-playlist", url])
    data = json.loads(raw)

    channel_id = data.get("channel_id", "")
    channel = Channel(
        channel_id=channel_id,
        name=data.get("channel", data.get("uploader", "Unknown")),
        url=data.get("channel_url", ""),
        description=(data.get("channel_description", "") or "")[:500],
        follower_count=0,
        handle=data.get("uploader_id", ""),
        thumbnail_url=data.get("thumbnails", [{}])[-1].get("url", "") if data.get("thumbnails") else "",
        is_verified=bool(data.get("channel_is_verified", False)),
    )
    video = Video(
        video_id=data.get("id", video_id),
        channel_id=channel_id,
        title=data.get("title", ""),
        url=data.get("webpage_url", url),
        description=(data.get("description", "") or "")[:500],
        duration_seconds=int(data.get("duration", 0) or 0),
        upload_date=_format_date(data.get("upload_date", "")),
        view_count=0,
        tags=data.get("tags", []) or [],
        language_iso=data.get("language", "en") or "en",
        like_count=0,
        comment_count=0,
        category=data.get("categories", [""])[0] if data.get("categories") else "",
        thumbnail_url=data.get("thumbnail", ""),
        heatmap_json=json.dumps(data.get("heatmap", [])),
    )
    return video, channel


def extract_channel_info(url: str) -> Channel:
    """Extract channel metadata from a channel URL.
    
    Strategy: Try to get first video from playlist, fallback to generic channel object.
    """
    _apply_rate_limit()  # Rate limiting
    
    # Try to get first video info from the channel
    try:
        # Use --flat-playlist with limit 1 to get first video's metadata
        raw = _run_ytdlp([
            "--flat-playlist",
            "--playlist-end", "1",
            "--dump-json",
            "--print", "id",
            url
        ], timeout=180)
        
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
        if lines:
            # First line should be a video ID
            first_video_id = lines[0]
            if len(first_video_id) == 11:  # Valid YouTube video ID length
                # Extract metadata from first video
                try:
                    video, channel = extract_video_metadata(first_video_id)
                    return channel
                except Exception as e:
                    logger.warning(f"Failed to extract from first video: {e}")
    except Exception as e:
        logger.debug(f"Failed to get first video info: {e}")
    
    # Fallback: Create a basic channel object with just the URL
    # The channel will be populated when individual videos are processed
    logger.warning(f"Using minimal channel info for {url}")
    
    # Try to extract channel ID from URL if possible
    channel_id = "unknown"
    if "/channel/" in url:
        channel_id = url.split("/channel/")[-1].split("/")[0]
    elif "/@ " in url: # Space to avoid matching the regex in replace
         channel_id = url.split("/@")[-1].split("/")[0]
            
    return Channel(
        channel_id=channel_id,
        name=channel_id if channel_id != "unknown" else "Unknown Channel",
        url=url,
        description="",
    )


def discover_video_ids(url: str, parsed: ParsedURL, after_date: str = None):
    """Discover video IDs from a channel or playlist URL. yields IDs.

    Args:
        url: YouTube URL (channel, playlist, or single video).
        parsed: Pre-parsed ParsedURL object.
        after_date: Optional ISO date (YYYY-MM-DD) for P0-E incremental harvest.
            Only videos published on or after this date will be discovered.
            Pass None (default) for a full harvest.
    """
    if parsed.url_type == "video":
        yield parsed.video_id
        return

    target_url = url
    if parsed.url_type == "channel":
        # Strategy A: Specifically target /videos tab
        if "/videos" not in target_url:
            discovery_url = target_url.rstrip("/") + "/videos"
        else:
            discovery_url = target_url
        
        count = 0
        try:
            for vid in _fetch_ids_stream(discovery_url, after_date=after_date):
                yield vid
                count += 1
            if count > 0:
                logger.info(f"Discovered {count} videos from {discovery_url}")
                return
        except Exception as e:
            logger.warning(f"Discovery at {discovery_url} failed: {e}. Trying fallback...")

    # Strategy B: Fallback to original URL
    try:
        count = 0
        for vid in _fetch_ids_stream(url, after_date=after_date):
            yield vid
            count += 1
        if count > 0:
            logger.info(f"Discovered {count} videos from {url}")
            return
    except Exception as e:
        logger.warning(f"Discovery at original URL {url} failed: {e}")

    # Strategy C: Force base channel URL
    if parsed.url_type == "channel":
        base_url = re.sub(r'/(videos|shorts|streams|playlists)/?$', '', url)
        if base_url != url:
            logger.info(f"Trying base channel URL fallback: {base_url}")
            try:
                for vid in _fetch_ids_stream(base_url, after_date=after_date):
                    yield vid
            except Exception as e:
                logger.error(f"Base channel fallback failed: {e}")


def _fetch_ids_stream(url: str, after_date: str = None):
    """Helper to run yt-dlp discovery and yield IDs.

    Args:
        url: YouTube channel/playlist URL.
        after_date: Optional ISO date string (YYYY-MM-DD). When provided, only
            videos published on or after this date are returned.  This maps to
            yt-dlp's ``--dateafter`` flag and is the core of P0-E diff-harvest.
    """
    args = [
        "--flat-playlist",
        "--ignore-errors",
        "--print", "id",
    ]
    if after_date:
        # yt-dlp expects YYYYMMDD; strip dashes if ISO format is passed
        date_compact = after_date.replace("-", "")
        args += ["--dateafter", date_compact]
        logger.info(f"P0-E Diff-harvest: only fetching videos after {after_date}")
    args.append(url)
    return _run_ytdlp_stream(args)


def _format_date(date_str: str) -> str:
    """Convert yt-dlp date format (YYYYMMDD) to ISO format."""
    if date_str and len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str or ""
