import sys
import threading
import time
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.sqlite_store import SQLiteStore, Video

# Configure logging to see retries
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_sqlite_concurrency():
    print("--- Testing SQLite Concurrency & Retry ---")
    test_db_path = "data/test_concurrency.db"
    if Path(test_db_path).exists():
        Path(test_db_path).unlink()
    
    db = SQLiteStore(test_db_path)
    
    def write_task(thread_id):
        # Create a new connection for each thread as required by SQLite
        thread_db = SQLiteStore(test_db_path)
        try:
            video = Video(
                video_id=f"test_concurrency_{thread_id}_{int(time.time())}",
                channel_id="test_channel",
                title=f"Concurrency Test Thread {thread_id}",
                url=f"https://youtube.com/watch?v=test_{thread_id}",
                upload_date="2024-04-30"
            )
            print(f"Thread {thread_id} attempting insert_video...")
            thread_db.insert_video(video)
            print(f"Thread {thread_id} successful.")
        except Exception as e:
            print(f"Thread {thread_id} FAILED: {e}")
        finally:
            thread_db.close()

    threads = []
    for i in range(10): # 10 threads hitting at once
        t = threading.Thread(target=write_task, args=(i,))
        threads.append(t)
        
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    print("Concurrency test completed.")
    db.close()

if __name__ == "__main__":
    test_sqlite_concurrency()
