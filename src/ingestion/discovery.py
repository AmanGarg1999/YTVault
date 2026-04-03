"""
Discovery module for knowledgeVault-YT.

Handles URL parsing, yt-dlp metadata extraction, and video queue management.
Enforces the "No Media Download" policy — only metadata and transcripts.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from src.storage.sqlite_store import Channel, Video
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)


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
def _run_ytdlp(args: list[str], timeout: int = 60) -> str:
    """Run yt-dlp with given arguments and return stdout.

    Isolates subprocess environment to prevent locale-dependent failures.
    """
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
    url = f"https://www.youtube.com/watch?v={video_id}"
    raw = _run_ytdlp(["--dump-json", url])
    data = json.loads(raw)

    channel_id = data.get("channel_id", "")
    channel = Channel(
        channel_id=channel_id,
        name=data.get("channel", data.get("uploader", "Unknown")),
        url=data.get("channel_url", ""),
        description="",
    )
    video = Video(
        video_id=data.get("id", video_id),
        channel_id=channel_id,
        title=data.get("title", ""),
        url=data.get("webpage_url", url),
        description=(data.get("description", "") or "")[:500],
        duration_seconds=int(data.get("duration", 0) or 0),
        upload_date=_format_date(data.get("upload_date", "")),
        view_count=int(data.get("view_count", 0) or 0),
        tags=data.get("tags", []) or [],
        language_iso=data.get("language", "en") or "en",
    )
    return video, channel


def extract_channel_info(url: str) -> Channel:
    """Extract channel metadata from a channel URL."""
    raw = _run_ytdlp(["--dump-json", "--playlist-items", "0", url], timeout=30)
    # yt-dlp may return channel info in the first entry
    lines = raw.strip().split("\n")
    if lines:
        data = json.loads(lines[0])
        return Channel(
            channel_id=data.get("channel_id", ""),
            name=data.get("channel", data.get("uploader", "Unknown")),
            url=data.get("channel_url", url),
            description=(data.get("description", "") or "")[:500],
        )
    raise RuntimeError(f"Could not extract channel info from: {url}")


def discover_video_ids(url: str, parsed: ParsedURL):
    """Discover video IDs from a channel or playlist URL. yields IDs."""
    if parsed.url_type == "video":
        yield parsed.video_id
        return

    target_url = url
    if parsed.url_type == "channel":
        # Strategy A: Specifically target /videos tab
        if not target_url.endswith("/videos"):
            discovery_url = target_url.rstrip("/") + "/videos"
        else:
            discovery_url = target_url
        
        count = 0
        try:
            for vid in _fetch_ids_stream(discovery_url):
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
        for vid in _fetch_ids_stream(url):
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
                for vid in _fetch_ids_stream(base_url):
                    yield vid
            except Exception as e:
                logger.error(f"Base channel fallback failed: {e}")


def _fetch_ids_stream(url: str):
    """Helper to run yt-dlp discovery and yield IDs."""
    return _run_ytdlp_stream([
        "--flat-playlist",
        "--ignore-errors",
        "--print", "id",
        url,
    ])


def _format_date(date_str: str) -> str:
    """Convert yt-dlp date format (YYYYMMDD) to ISO format."""
    if date_str and len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str or ""
