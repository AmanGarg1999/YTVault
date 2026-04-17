import time
import logging
from src.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SyncAll")

CHANNELS = [
    # Phase 1: Stale
    "https://www.youtube.com/channel/UCcefcZRL2oaA_uBNeo5UOWg", # Y Combinator
    "https://www.youtube.com/channel/UC_ccm5rjG4JdSsGPuxZLIaQ", # Harry Sahota
    "https://www.youtube.com/channel/UCSMOQeBJ2RAnuFungnQOxLg", # Blender
    
    # Phase 2: High-Velocity
    "https://www.youtube.com/channel/UC2bBsPXFWZWiBmkRiNlz8vg", # Abhijit Chavda
    "https://www.youtube.com/channel/UCSHZKyawb77ixDdsGog4iWA", # Lex Fridman
    "https://www.youtube.com/channel/UCzQUP1qoWDoEbmsQxvdjxgQ", # PowerfulJRE
]

def main():
    orchestrator = PipelineOrchestrator()
    
    for url in CHANNELS:
        logger.info(f"--- Starting Sync for {url} ---")
        try:
            # force_metadata_refresh=False allows incremental harvest via after_date
            scan_id = orchestrator.run(url, force_metadata_refresh=False)
            logger.info(f"Finished Sync for {url}. Scan ID: {scan_id}")
        except Exception as e:
            logger.error(f"Failed to sync {url}: {e}")
        
        # Sleep briefly between channels to avoid hammering
        time.sleep(5)

if __name__ == "__main__":
    main()
