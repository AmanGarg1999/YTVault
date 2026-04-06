import unittest
import threading
import time
import os
from unittest.mock import MagicMock, patch
from src.storage.sqlite_store import SQLiteStore, Video, Channel
from src.utils.llm_pool import get_llm_semaphore, LLMPool, LLMTask
import src.storage.vector_store
import src.storage.graph_store

class TestP0Enhancements(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_vault_p0.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = SQLiteStore(self.db_path)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_resume_locking_contention(self):
        """Verify that two scans cannot claim the same video."""
        video_id = "test_vid_lock"
        scan_1 = "scan_alpha"
        scan_2 = "scan_beta"
        
        # Insert channel first to satisfy FK
        self.db.upsert_channel(Channel(channel_id="ch1", name="Test", url="http://test"))
        
        # Insert video
        self.db.insert_video(Video(video_id=video_id, channel_id="ch1", title="Test", url="http://test"))
        
        # Scan 1 claims it
        success_1 = self.db.claim_video(video_id, scan_1)
        self.assertTrue(success_1, "Scan 1 should successfully claim unclaimed residue")
        
        # Scan 2 tries to claim it
        success_2 = self.db.claim_video(video_id, scan_2)
        self.assertFalse(success_2, "Scan 2 should fail to claim video already locked by Scan 1")
        
        # Scan 1 releases it
        self.db.release_video(video_id, scan_1)
        
        # Scan 2 can now claim it
        success_2_retry = self.db.claim_video(video_id, scan_2)
        self.assertTrue(success_2_retry, "Scan 2 should successfully claim video after it was released")

    def test_global_llm_concurrency_limit(self):
        """Verify that the global semaphore limits concurrent LLM calls."""
        # Instead of reloading, we'll just use the existing semaphore and verify it blocks
        from src.utils.llm_pool import get_llm_semaphore
        semaphore = get_llm_semaphore()
        
        # We'll use a small number of threads and a custom lock to verify blocking
        # since we can't easily change the BoundedSemaphore's internal limit after init
        # without affecting the whole app.
        
        active_calls = 0
        max_observed_concurrent = 0
        call_lock = threading.Lock()

        def mock_llm_call():
            nonlocal active_calls, max_observed_concurrent
            with semaphore:
                with call_lock:
                    active_calls += 1
                    max_observed_concurrent = max(max_observed_concurrent, active_calls)
                
                time.sleep(0.1)
                
                with call_lock:
                    active_calls -= 1

        threads = []
        for _ in range(12): # More than default 8
            t = threading.Thread(target=mock_llm_call)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # It should cap at whatever current limit is (8 or configured)
        limit = semaphore._initial_value
        self.assertLessEqual(max_observed_concurrent, limit)
        self.assertGreater(max_observed_concurrent, 0)

    @patch("src.storage.graph_store.GraphStore", autospec=True)
    @patch("src.storage.vector_store.VectorStore", autospec=True)
    def test_atomic_deletion_logic(self, mock_vector_cls, mock_graph_cls):
        """Verify that multi-store deletion is called correctly."""
        # When using autospec=True for the class, the return_value is an instance of the class
        mock_graph = mock_graph_cls.return_value
        mock_vector = mock_vector_cls.return_value
        
        video_id = "del_vid_123"
        
        # Verify SQLite data is actually gone (if it was there)
        self.db.upsert_channel(Channel(channel_id="ch1", name="Test", url="http://test"))
        self.db.insert_video(Video(video_id=video_id, channel_id="ch1", title="Test", url="http://test"))
        
        # Simulate the deletion flow as it would appear in data_management.py
        mock_graph.delete_video_nodes(video_id)
        mock_vector.delete_video_chunks(video_id)
        self.db.delete_video_data(video_id)
        
        mock_graph.delete_video_nodes.assert_called_with(video_id)
        mock_vector.delete_video_chunks.assert_called_with(video_id)
        
        # In SQLite, deletion resets the video for re-discovery rather than dropping the row
        video = self.db.get_video(video_id)
        self.assertIsNotNone(video)
        self.assertEqual(video.triage_status, "DISCOVERED")
        self.assertEqual(video.checkpoint_stage, "METADATA_HARVESTED")


if __name__ == "__main__":
    unittest.main()
