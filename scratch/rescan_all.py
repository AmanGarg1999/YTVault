import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings
from src.storage.sqlite_store import SQLiteStore
from src.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def main():
    settings = get_settings()
    db = SQLiteStore(settings["sqlite"]["path"])
    channels = db.get_all_channels()
    urls = [c.url for c in channels if c.url]
    number_of_channels = len(urls)
    db.close()
    
    print(f"Starting FULL RESCAN of {number_of_channels} channels. This will take a long time.")
    
    orchestrator = PipelineOrchestrator()
    for i, url in enumerate(urls):
        print(f"\n--- Rescanning Channel {i+1}/{number_of_channels}: {url} ---")
        try:
            orchestrator.run(url, force_metadata_refresh=True)
            orchestrator.db.sync_channel_video_counts()
        except Exception as e:
            print(f"Error processing {url}: {e}")
            
    orchestrator.close()
    print("\nFull bulk rescan completed successfully.")

if __name__ == "__main__":
    main()
