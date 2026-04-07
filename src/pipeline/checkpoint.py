"""
Checkpoint manager for knowledgeVault-YT.

Implements crash-safe resume capability for interrupted scans.
Every pipeline stage transition is atomically committed to SQLite.
"""

import logging
from typing import Optional

from src.storage.sqlite_store import SQLiteStore, ScanCheckpoint, Video

logger = logging.getLogger(__name__)


# Pipeline stage ordering (must match Technical Spec)
STAGE_ORDER = [
    "METADATA_HARVESTED",
    "TRIAGE_COMPLETE",
    "TRANSCRIPT_FETCHED",
    "TRANSLATED",            # NEW: Translate non-English transcripts
    "SPONSOR_FILTERED",
    "TEXT_NORMALIZED",
    "CHUNKED",
    "CHUNK_ANALYZED",
    "SUMMARIZED",
    "EMBEDDED",
    "GRAPH_SYNCED",
    "CORROBORATED",
    "DONE",
]


class CheckpointManager:
    """Manages scan checkpoints for crash-safe pipeline resumption.

    Each video independently tracks its pipeline stage via the
    `checkpoint_stage` column. On resume, videos are processed
    starting from their last completed stage.
    """

    def __init__(self, db: SQLiteStore):
        self.db = db

    def create_scan(self, source_url: str, scan_type: str) -> str:
        """Create a new scan checkpoint and return its ID."""
        return self.db.create_scan_checkpoint(source_url, scan_type)

    def get_scan(self, scan_id: str) -> Optional[ScanCheckpoint]:
        """Get an existing scan checkpoint."""
        return self.db.get_scan_checkpoint(scan_id)

    def get_active_scans(self) -> list[ScanCheckpoint]:
        """Get all in-progress scans."""
        return self.db.get_active_scans()

    def advance(self, video_id: str, new_stage: str) -> None:
        """Atomically advance a video to the next pipeline stage.

        This commits immediately to SQLite, ensuring crash-safety.
        """
        if new_stage not in STAGE_ORDER:
            raise ValueError(f"Invalid stage: {new_stage}. Must be one of {STAGE_ORDER}")

        self.db.update_checkpoint_stage(video_id, new_stage)
        logger.debug(f"Checkpoint: {video_id} → {new_stage}")

    def get_next_stage(self, current_stage: str) -> Optional[str]:
        """Get the next stage after the current one."""
        try:
            idx = STAGE_ORDER.index(current_stage)
            if idx + 1 < len(STAGE_ORDER):
                return STAGE_ORDER[idx + 1]
            return None  # Already at DONE
        except ValueError:
            return STAGE_ORDER[0]

    def get_remaining_stages(self, current_stage: str) -> list[str]:
        """Get all stages remaining after the current one."""
        try:
            idx = STAGE_ORDER.index(current_stage)
            return STAGE_ORDER[idx + 1:]
        except ValueError:
            return STAGE_ORDER

    def get_resumable_videos(self) -> list[Video]:
        """Get all accepted videos that haven't completed processing."""
        return self.db.get_resumable_videos()

    def update_scan_progress(self, scan_id: str, **kwargs) -> None:
        """Update scan-level progress counters."""
        self.db.update_scan_checkpoint(scan_id, **kwargs)

    def complete_scan(self, scan_id: str) -> None:
        """Mark a scan as completed."""
        self.db.update_scan_checkpoint(scan_id, status="COMPLETED")
        logger.info(f"Scan {scan_id} completed")

    def fail_scan(self, scan_id: str) -> None:
        """Mark a scan as failed."""
        self.db.update_scan_checkpoint(scan_id, status="FAILED")
        logger.warning(f"Scan {scan_id} marked as FAILED")
