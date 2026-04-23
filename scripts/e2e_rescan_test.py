import logging
import sys
import os
import ssl

# Add project root to path
sys.path.append(os.getcwd())

# Bypassing SSL certificate verification for transcripts in restricted environments
ssl._create_default_https_context = ssl._create_unverified_context

from src.pipeline.orchestrator import PipelineOrchestrator
from src.config import get_settings

def run_e2e_rescan():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("E2E_Rescan")
    
    settings = get_settings()
    logger.info(f"Using deep_model: {settings['ollama']['deep_model']}")
    
    orchestrator = PipelineOrchestrator()
    
    # Target: Joe Rogan Experience #2479 - Bob Lazar & Luigi Vendittelli
    # This video is perfect for testing diarization as it has Joe + Bob + Luigi.
    video_id = "Lb_1d68vx-g"
    
    # Reset checkpoint to METADATA_HARVESTED to force full refinement and analysis
    orchestrator.db.update_checkpoint_stage(video_id, "METADATA_HARVESTED")
    
    logger.info(f"Starting end-to-end verification for video: {video_id}")
    
    try:
        # Manually claim and process the video to simulate a pipeline run for just this target
        scan_id = "e2e_test_turn"
        orchestrator.db.claim_video(video_id, scan_id)
        
        orchestrator._process_single_video(video_id, scan_id)
        
        logger.info("E2E verification completed successfully.")
        
    except Exception as e:
        logger.error(f"E2E verification failed: {e}", exc_info=True)
    finally:
        orchestrator.db.release_video(video_id, scan_id)

if __name__ == "__main__":
    run_e2e_rescan()
