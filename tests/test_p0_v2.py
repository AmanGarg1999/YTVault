"""
P0 Enhancement Test Suite — KnowledgeVault-YT
Tests for all 5 P0 items implemented in April 2026:
  P0-A: Saga outbox for atomic triple-store sync
  P0-B: Hash-based embedding skip
  P0-C: Pipeline temp-state cleanup
  P0-D: Store divergence stats (query-level test)
  P0-E: Diff-harvest --dateafter flag
"""

import hashlib
import os
import unittest
from unittest.mock import MagicMock, patch

from src.storage.sqlite_store import Channel, SQLiteStore, Video


class TestP0_A_SagaOutbox(unittest.TestCase):
    """P0-A: Saga outbox for triple-store atomicity."""

    def setUp(self):
        self.db_path = "test_p0_v2_a.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = SQLiteStore(self.db_path)
        self.db.upsert_channel(Channel(channel_id="ch1", name="Test", url="http://test"))
        self.db.insert_video(Video(video_id="vid1", channel_id="ch1", title="T", url="http://t"))

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_outbox_entry(self):
        self.db.create_sync_outbox_entry("vid1")
        rows = self.db.get_pending_outbox()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["video_id"], "vid1")
        self.assertFalse(rows[0]["chroma_done"])
        self.assertFalse(rows[0]["neo4j_done"])

    def test_mark_chroma_done(self):
        self.db.create_sync_outbox_entry("vid1")
        self.db.mark_outbox_chroma_done("vid1")
        rows = self.db.get_pending_outbox()
        # Still pending because neo4j_done=False
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["chroma_done"])
        self.assertFalse(rows[0]["neo4j_done"])

    def test_mark_both_done_disappears_from_pending(self):
        self.db.create_sync_outbox_entry("vid1")
        self.db.mark_outbox_chroma_done("vid1")
        self.db.mark_outbox_neo4j_done("vid1")
        rows = self.db.get_pending_outbox()
        self.assertEqual(len(rows), 0, "Both done \u2014 should not appear in pending")

    def test_cleanup_done_outbox(self):
        self.db.create_sync_outbox_entry("vid1")
        self.db.mark_outbox_chroma_done("vid1")
        self.db.mark_outbox_neo4j_done("vid1")
        removed = self.db.cleanup_done_outbox()
        self.assertEqual(removed, 1)

    def test_outbox_stats(self):
        self.db.create_sync_outbox_entry("vid1")
        stats = self.db.get_outbox_stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["pending_chroma"], 1)
        self.assertEqual(stats["pending_neo4j"], 1)

    def test_mark_translation_stored_no_direct_conn(self):
        """mark_translation_stored() must not use self.conn directly in caller."""
        # This is a regression test for the raw self.db.conn.execute() fix.
        self.db.mark_translation_stored("vid1")
        row = self.db.conn.execute(
            "SELECT translated_text_stored FROM videos WHERE video_id = ?", ("vid1",)
        ).fetchone()
        self.assertEqual(row["translated_text_stored"], 1)

    def test_saga_worker_drain_no_stores(self):
        """SagaWorker.drain() should not crash when stores are None."""
        from src.pipeline.saga_worker import SagaWorker
        self.db.create_sync_outbox_entry("vid1")
        worker = SagaWorker(db=self.db, vector_store=None, graph_store=None)
        resolved = worker.drain()
        # No stores \u2014 can't fully resolve, but must not raise
        self.assertIsInstance(resolved, int)

    def test_saga_worker_drain_with_mock_stores(self):
        """SagaWorker successfully resolves a pending entry with mocked stores."""
        from src.pipeline.saga_worker import SagaWorker

        self.db.create_sync_outbox_entry("vid1")

        mock_vs = MagicMock()
        mock_gs = MagicMock()
        mock_gs.upsert_video = MagicMock()
        mock_gs.link_video_to_topic = MagicMock()
        mock_gs.upsert_guest = MagicMock()
        mock_gs.link_guest_to_video = MagicMock()
        mock_gs.link_guest_to_topic = MagicMock()
        mock_gs.link_related_topics = MagicMock()

        # Ensure db has the helpers saga worker needs
        self.db.get_video_aggregated_topics = MagicMock(return_value=[])
        self.db.get_video_aggregated_entities = MagicMock(return_value=[])
        self.db.get_chunks_for_video = MagicMock(return_value=[])

        worker = SagaWorker(db=self.db, vector_store=mock_vs, graph_store=mock_gs)
        resolved = worker.drain()
        self.assertGreaterEqual(resolved, 1)


class TestP0_B_ContentHashEmbeddingSkip(unittest.TestCase):
    """P0-B: Content hash-based embedding skip."""

    def setUp(self):
        self.db_path = "test_p0_v2_b.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = SQLiteStore(self.db_path)
        self.db.upsert_channel(Channel(channel_id="ch1", name="Test", url="http://test"))
        self.db.insert_video(Video(video_id="vid1", channel_id="ch1", title="T", url="http://t"))

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_get_chunks_with_hashes_empty(self):
        result = self.db.get_chunks_with_hashes("vid1")
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_content_hash_stored_and_retrieved(self):
        from src.storage.sqlite_store import TranscriptChunk
        chunk = TranscriptChunk(
            chunk_id="vid1__chunk_0000",
            video_id="vid1",
            chunk_index=0,
            raw_text="hello world",
            cleaned_text="hello world",
            word_count=2,
        )
        self.db.insert_chunks([chunk])

        expected_hash = hashlib.sha256("hello world".encode()).hexdigest()
        self.db.conn.execute(
            "UPDATE transcript_chunks SET content_hash = ? WHERE chunk_id = ?",
            (expected_hash, "vid1__chunk_0000"),
        )
        self.db.conn.commit()

        hashes = self.db.get_chunks_with_hashes("vid1")
        self.assertIn("vid1__chunk_0000", hashes)
        self.assertEqual(hashes["vid1__chunk_0000"], expected_hash)

    def test_upsert_chunks_skip_ids(self):
        """VectorStore.upsert_chunks skips chunks in skip_ids."""
        from src.storage.sqlite_store import TranscriptChunk
        from src.storage.vector_store import VectorStore

        chunk = TranscriptChunk(
            chunk_id="vid1__chunk_skip",
            video_id="vid1",
            chunk_index=0,
            raw_text="skip me",
            cleaned_text="skip me",
            word_count=2,
        )

        mock_collection = MagicMock()
        with patch("src.storage.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            with patch("src.storage.vector_store.OllamaEmbeddingFunction"):
                vs = VectorStore.__new__(VectorStore)
                vs.collection = mock_collection
                vs.embedding_fn = MagicMock()

                result = vs.upsert_chunks([chunk], skip_ids={"vid1__chunk_skip"})
                # All chunks skipped \u2014 upsert should not be called
                mock_collection.upsert.assert_not_called()
                self.assertEqual(result, 0)


class TestP0_C_TempStateCleanup(unittest.TestCase):
    """P0-C: Pipeline temp state cleanup."""

    def setUp(self):
        self.db_path = "test_p0_v2_c.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = SQLiteStore(self.db_path)
        self.db.upsert_channel(Channel(channel_id="ch1", name="Test", url="http://test"))

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _insert_video_with_stage(self, video_id, stage):
        self.db.insert_video(Video(video_id=video_id, channel_id="ch1", title="T", url="http://t"))
        self.db.update_checkpoint_stage(video_id, stage)

    def test_cleanup_done_keeps_wip(self):
        self._insert_video_with_stage("done_vid", "GRAPH_SYNCED")
        self._insert_video_with_stage("wip_vid", "EMBEDDED")

        self.db.save_temp_state("done_vid", raw_text="done text")
        self.db.save_temp_state("wip_vid", raw_text="wip text")

        removed = self.db.cleanup_done_temp_states()
        self.assertEqual(removed, 1)

        # WIP entry still exists
        self.assertIsNotNone(self.db.get_temp_state("wip_vid"))
        # Done entry is gone
        self.assertIsNone(self.db.get_temp_state("done_vid"))

    def test_get_temp_state_stats(self):
        self._insert_video_with_stage("vid1", "EMBEDDED")
        self.db.save_temp_state("vid1", raw_text="a" * 1000, cleaned_text="b" * 500)
        stats = self.db.get_temp_state_stats()
        self.assertIn("row_count", stats)
        self.assertIn("total_size_kb", stats)
        self.assertGreater(stats["row_count"], 0)
        self.assertGreater(stats["total_size_kb"], 0)


class TestP0_D_StoreDivergenceStats(unittest.TestCase):
    """P0-D: Store divergence stats (SQLite-level only)."""

    def setUp(self):
        self.db_path = "test_p0_v2_d.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = SQLiteStore(self.db_path)
        self.db.upsert_channel(Channel(channel_id="ch1", name="Test", url="http://test"))

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_get_store_sync_stats_structure(self):
        self.db.insert_video(Video(video_id="v1", channel_id="ch1", title="T", url="http://t"))
        self.db.update_triage_status("v1", "ACCEPTED")
        stats = self.db.get_store_sync_stats()
        self.assertIn("sqlite_accepted", stats)
        self.assertIn("sqlite_done", stats)
        self.assertIn("pending_outbox_chroma", stats)
        self.assertIn("pending_outbox_neo4j", stats)
        self.assertGreaterEqual(stats["sqlite_accepted"], 1)


class TestP0_E_DiffHarvest(unittest.TestCase):
    """P0-E: Diff-harvest --dateafter flag in yt-dlp calls."""

    def test_fetch_ids_stream_no_dateafter(self):
        from src.ingestion.discovery import _fetch_ids_stream
        with patch("src.ingestion.discovery._run_ytdlp_stream") as mock_run:
            mock_run.return_value = iter([])
            list(_fetch_ids_stream("http://example.com"))
            args = mock_run.call_args[0][0]
            self.assertNotIn("--dateafter", args)

    def test_fetch_ids_stream_with_dateafter(self):
        from src.ingestion.discovery import _fetch_ids_stream
        with patch("src.ingestion.discovery._run_ytdlp_stream") as mock_run:
            mock_run.return_value = iter([])
            list(_fetch_ids_stream("http://example.com", after_date="2026-01-15"))
            args = mock_run.call_args[0][0]
            self.assertIn("--dateafter", args)
            dateafter_idx = args.index("--dateafter")
            self.assertEqual(args[dateafter_idx + 1], "20260115")

    def test_fetch_ids_stream_date_compact_no_dashes(self):
        """Ensure YYYY-MM-DD is converted to YYYYMMDD for yt-dlp."""
        from src.ingestion.discovery import _fetch_ids_stream
        with patch("src.ingestion.discovery._run_ytdlp_stream") as mock_run:
            mock_run.return_value = iter([])
            list(_fetch_ids_stream("http://example.com", after_date="2025-03-07"))
            args = mock_run.call_args[0][0]
            self.assertIn("20250307", args)

    def test_discover_video_ids_passes_after_date(self):
        """discover_video_ids() propagates after_date to _fetch_ids_stream()."""
        from src.ingestion.discovery import ParsedURL, discover_video_ids
        parsed = ParsedURL(url_type="channel", channel_handle="test", raw_url="http://test")
        with patch("src.ingestion.discovery._fetch_ids_stream") as mock_fetch:
            mock_fetch.return_value = iter([])
            list(discover_video_ids("http://test", parsed, after_date="2026-04-01"))
            # _fetch_ids_stream should have been called with after_date
            calls = mock_fetch.call_args_list
            self.assertTrue(
                any(c.kwargs.get("after_date") == "2026-04-01" for c in calls),
                f"after_date not passed to _fetch_ids_stream. Calls: {calls}"
            )


if __name__ == "__main__":
    unittest.main()
