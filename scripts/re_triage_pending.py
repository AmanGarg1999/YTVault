
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.storage.sqlite_store import SQLiteStore, Video
from src.ingestion.triage import TriageEngine, TriageDecision
from src.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s │ %(levelname)-8s │ %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    settings = get_settings()
    db_path = settings["sqlite"]["path"]
    db = SQLiteStore(db_path)
    triage = TriageEngine()
    
    logger.info("Fetching videos from Triage Queue (PENDING_REVIEW)...")
    pending_videos = db.get_videos_by_status("PENDING_REVIEW", limit=1000)
    
    if not pending_videos:
        logger.info("No videos found in PENDING_REVIEW status.")
        return

    logger.info(f"Found {len(pending_videos)} videos in the queue.")
    
    # Process in batches to optimize LLM calls
    batch_size = 5
    
    for i in range(0, len(pending_videos), batch_size):
        batch = pending_videos[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(pending_videos)-1)//batch_size + 1} ({len(batch)} videos)...")
        
        try:
            # Use batch_classify for performance
            results = triage.batch_classify(batch)
            
            for vid, res in results.items():
                logger.info(f"  {vid}: {res.decision.value} - {res.reason[:60]}...")
                db.update_triage_status(
                    vid,
                    status=res.decision.value,
                    reason=res.reason,
                    confidence=res.confidence
                )
                
                # If accepted, we might need to update the checkpoint stage so it continues the pipeline
                # However, the user just asked to triage them. 
                # If they were PENDING_REVIEW, their checkpoint_stage is likely METADATA_HARVESTED.
                # If they move to ACCEPTED, they should move to TRIAGE_COMPLETE to be picked up by the pipeline.
                if res.decision == TriageDecision.ACCEPT:
                    db.update_checkpoint_stage(vid, "TRIAGE_COMPLETE")
                elif res.decision == TriageDecision.REJECT:
                    db.update_checkpoint_stage(vid, "DONE")
                    
        except Exception as e:
            logger.error(f"Failed to process batch starting at index {i}: {e}")

    logger.info("Re-triage complete.")

if __name__ == "__main__":
    main()
