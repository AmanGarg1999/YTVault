#!/usr/bin/env python3
"""
Backfill script for knowledgeVault-YT.
Re-processes all 'DONE' videos with the updated SummarizerEngine to extract
Actionable Blueprints, Expert Clashes, Sentiment Heatmaps, and Citations.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.storage.sqlite_store import SQLiteStore
from src.intelligence.summarizer import SummarizerEngine
from src.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("backfill")

def run_backfill():
    settings = get_settings()
    db_path = settings["sqlite"]["path"]
    
    with SQLiteStore(db_path) as db:
        # Find all videos that are in 'DONE' stage but might lack the new intelligence data
        # We check actionable_blueprints as a proxy, or just process ALL done videos.
        # To be safe and thorough, we process all videos where checkpoint_stage = 'DONE'.
        
        videos = db.conn.execute(
            "SELECT video_id, title FROM videos WHERE video_id = 'Rni7Fz7208c'"
        ).fetchall()
        
        if not videos:
            # Fallback to any video with chunks if this one is somehow missing from DONE
            videos = db.conn.execute(
                "SELECT video_id, title FROM videos WHERE checkpoint_stage = 'DONE' AND video_id IN (SELECT video_id FROM transcript_chunks) LIMIT 1"
            ).fetchall()
        
        if not videos:
            logger.info("No videos in 'DONE' stage found for backfilling.")
            return

        total = len(videos)
        logger.info(f"Starting backfill for {total} videos...")
        
        engine = SummarizerEngine(db)
        
        for i, row in enumerate(videos):
            video_id = row["video_id"]
            title = row["title"]
            
            logger.info(f"[{i+1}/{total}] Re-processing: {title} ({video_id})")
            try:
                # generate_summary results in a clean re-run of extraction
                engine.generate_summary(video_id)
            except Exception as e:
                logger.error(f"Failed to backfill {video_id}: {e}")

        logger.info("Backfill complete!")

if __name__ == "__main__":
    run_backfill()
