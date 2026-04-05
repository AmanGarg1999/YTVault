import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from src.pipeline.orchestrator import PipelineOrchestrator
from src.storage.sqlite_store import SQLiteStore, Video, Channel

def test_parallel_processing_logic():
    """
    Test that PipelineOrchestrator.run() correctly parallelizes video processing
    and handles thread-local database connections.
    """
    # 1. Setup mock DB and settings
    db_path = ":memory:" # Or a temporary file
    db = SQLiteStore(db_path)
    
    settings = {
        "pipeline": {"max_parallel_videos": 4},
        "sqlite": {"path": db_path},
        "ollama": {"triage_model": "test"}
    }
    
    orchestrator = PipelineOrchestrator()
    orchestrator.settings = settings
    orchestrator.db = db # Use the same memory DB for setup
    
    # 2. Mock stages to simulate work and record thread IDs
    processing_threads = set()
    lock = threading.Lock()
    
    def mock_process_video(video_id, scan_id):
        with lock:
            processing_threads.add(threading.get_ident())
        time.sleep(0.5) # Simulate work
        return True

    # 3. Mock discovery to return multiple videos
    num_videos = 10
    vids = [f"vid_{i}" for i in range(num_videos)]
    
    # Manually insert videos into DB (discovery simulation)
    channel = Channel(channel_id="chan_1", name="Test Channel", url="http://test")
    db.upsert_channel(channel)
    for vid in vids:
        video = Video(video_id=vid, channel_id="chan_1", title=f"Video {vid}", url="http://test")
        db.insert_video(video)

    # Patch the actual processing method
    with patch.object(PipelineOrchestrator, "_process_single_video", side_effect=mock_process_video):
        # Patch discovery to put videos in the queue
        def mock_discovery(url, parsed, scan_id, q, force):
            for vid in vids:
                q.put((vid, True))
            # No sentinel here, run() logic handles it via sentinel from discovery_worker wrapper
        
        with patch.object(PipelineOrchestrator, "_stage_discover_stream", side_effect=mock_discovery):
            # Run the pipeline
            scan_id = orchestrator.run("https://youtube.com/c/test")
            
            # 4. Verify results
            # Check that multiple threads were used
            print(f"DEBUG: Processing used {len(processing_threads)} distinct threads")
            assert len(processing_threads) > 1, "Should have used multiple threads"
            assert len(processing_threads) <= 4, "Should not exceed max_workers (plus main/discovery)"
            
            # Check scan completion
            scan = orchestrator.checkpoint.get_scan(scan_id)
            assert scan.status == "COMPLETED"
            assert scan.total_processed == num_videos

if __name__ == "__main__":
    test_parallel_processing_logic()
