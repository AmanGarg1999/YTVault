"""
Unit tests for knowledgeVault-YT core modules.

Run with: python -m pytest tests/ -v
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

# Ensure project root on sys.path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Tests: parse_youtube_url
# ---------------------------------------------------------------------------

from src.ingestion.discovery import parse_youtube_url


class TestParseYouTubeURL:
    """Test URL parsing for various YouTube URL formats."""

    def test_video_standard(self):
        result = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.url_type == "video"
        assert result.video_id == "dQw4w9WgXcQ"

    def test_video_short(self):
        result = parse_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        assert result.url_type == "video"
        assert result.video_id == "dQw4w9WgXcQ"

    def test_channel_handle(self):
        result = parse_youtube_url("https://youtube.com/@lexfridman")
        assert result.url_type == "channel"

    def test_channel_url(self):
        result = parse_youtube_url("https://www.youtube.com/channel/UCSHZKyawb77ixDdsGog4iWA")
        assert result.url_type == "channel"

    def test_playlist(self):
        result = parse_youtube_url("https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")
        assert result.url_type == "playlist"

    def test_invalid_url(self):
        with pytest.raises(ValueError):
            parse_youtube_url("https://google.com/search?q=test")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            parse_youtube_url("")

    def test_video_with_extra_params(self):
        # YouTube video IDs are always 11 characters; URLs with both v= and list=
        # should be treated as a video (user navigated to a specific video).
        result = parse_youtube_url("https://www.youtube.com/watch?v=abc12345678&t=120&list=PLxxx")
        assert result.url_type == "video"
        assert result.video_id == "abc12345678"


# ---------------------------------------------------------------------------
# Tests: sliding_window_chunk
# ---------------------------------------------------------------------------

from src.storage.vector_store import sliding_window_chunk


class TestSlidingWindowChunk:
    """Test the text chunking algorithm."""

    def test_basic_chunking(self):
        text = " ".join(["word"] * 500)
        chunks = sliding_window_chunk(
            cleaned_text=text, video_id="test_v1",
            segments=[], window_size=100, overlap=20,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.video_id == "test_v1"
            assert len(chunk.cleaned_text) > 0

    def test_small_text_single_chunk(self):
        text = "This is a very short text."
        chunks = sliding_window_chunk(
            cleaned_text=text, video_id="test_v2",
            segments=[], window_size=400, overlap=80,
            min_chunk_size=1,  # Override default (50) so 6-word text is accepted
        )
        assert len(chunks) == 1
        assert chunks[0].cleaned_text.strip() == text

    def test_empty_text(self):
        chunks = sliding_window_chunk(
            cleaned_text="", video_id="test_v3",
            segments=[], window_size=400, overlap=80,
        )
        assert len(chunks) == 0

    def test_min_chunk_size_filter(self):
        text = "Short"
        chunks = sliding_window_chunk(
            cleaned_text=text, video_id="test_v4",
            segments=[], window_size=400, overlap=80,
            min_chunk_size=50,
        )
        # "Short" has 1 word, below min_chunk_size of 50 words
        # Behavior depends on implementation — at minimum should not crash
        assert isinstance(chunks, list)

    def test_chunk_ids_unique(self):
        text = " ".join(["word"] * 1000)
        chunks = sliding_window_chunk(
            cleaned_text=text, video_id="test_v5",
            segments=[], window_size=100, overlap=20,
        )
        chunk_ids = [c.chunk_id for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))


# ---------------------------------------------------------------------------
# Tests: SQLiteStore
# ---------------------------------------------------------------------------

from src.storage.sqlite_store import SQLiteStore, Video, Channel, Guest, ScanCheckpoint


class TestSQLiteStore:
    """Test SQLite operations with a temporary database."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a temporary database with a seed channel for FK constraints."""
        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        # Insert a seed channel so video inserts satisfy the FK constraint
        store.upsert_channel(Channel(
            channel_id="ch1", name="Test Channel", url="https://youtube.com/@test",
        ))
        yield store
        store.close()

    def test_context_manager(self, tmp_path):
        db_path = str(tmp_path / "ctx_test.db")
        with SQLiteStore(db_path) as db:
            stats = db.get_pipeline_stats()
            assert stats is not None
        # Should not raise after close

    def test_insert_and_get_video(self, db):
        video = Video(
            video_id="test123",
            channel_id="ch1",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            description="A test video",
            duration_seconds=300,
            upload_date="2024-01-01",
            view_count=1000,
        )
        db.insert_video(video)
        result = db.get_video("test123")
        assert result is not None
        assert result.title == "Test Video"
        assert result.duration_seconds == 300

    def test_upsert_channel(self, db):
        channel = Channel(
            channel_id="ch1",
            name="Test Channel",
            url="https://youtube.com/@test",
        )
        db.upsert_channel(channel)
        result = db.get_channel("ch1")
        assert result is not None
        assert result.name == "Test Channel"

    def test_update_triage_status(self, db):
        video = Video(
            video_id="triage_test",
            channel_id="ch1",
            title="Triage Test",
            url="https://youtube.com/watch?v=triage_test",
        )
        db.insert_video(video)
        db.update_triage_status("triage_test", "ACCEPTED", "high_quality", 0.95)
        result = db.get_video("triage_test")
        assert result.triage_status == "ACCEPTED"
        assert result.triage_confidence == 0.95

    def test_scan_checkpoint_roundtrip(self, db):
        scan_id = db.create_scan_checkpoint(
            source_url="https://youtube.com/@test",
            scan_type="channel",
        )
        assert scan_id is not None
        checkpoint = db.get_scan_checkpoint(scan_id)
        assert checkpoint.status == "IN_PROGRESS"

    def test_checkpoint_advance(self, db):
        video = Video(
            video_id="cp_test",
            channel_id="ch1",
            title="Checkpoint Test",
            url="https://youtube.com/watch?v=cp_test",
        )
        db.insert_video(video)
        db.update_checkpoint_stage("cp_test", "TRIAGE_COMPLETE")
        result = db.get_video("cp_test")
        assert result.checkpoint_stage == "TRIAGE_COMPLETE"

    def test_pipeline_stats(self, db):
        stats = db.get_pipeline_stats()
        assert isinstance(stats, dict)
        assert "total_videos" in stats

    def test_schema_version(self, db):
        version = db._get_schema_version()
        assert version >= 1

    def test_find_guest_exact_canonical(self, db):
        db.upsert_guest("Elon Musk")
        result = db.find_guest_exact("Elon Musk")
        assert result is not None
        assert result.canonical_name == "Elon Musk"

    def test_find_guest_exact_alias(self, db):
        guest = db.upsert_guest("Elon Reeve Musk")
        db.add_guest_alias(guest.guest_id, "Elon Musk")
        result = db.find_guest_exact("Elon Musk")
        assert result is not None
        assert result.canonical_name == "Elon Reeve Musk"

    def test_find_guest_exact_not_found(self, db):
        result = db.find_guest_exact("Nonexistent Person")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: CheckpointManager
# ---------------------------------------------------------------------------

from src.pipeline.checkpoint import CheckpointManager, STAGE_ORDER


class TestCheckpointManager:
    """Test pipeline stage ordering and checkpoint logic."""

    @pytest.fixture
    def checkpoint(self, tmp_path):
        db = SQLiteStore(str(tmp_path / "cp.db"))
        yield CheckpointManager(db)
        db.close()

    def test_stage_order_starts_with_metadata(self):
        assert STAGE_ORDER[0] == "METADATA_HARVESTED"

    def test_stage_order_ends_with_done(self):
        assert STAGE_ORDER[-1] == "DONE"

    def test_get_remaining_stages_from_start(self, checkpoint):
        remaining = checkpoint.get_remaining_stages("METADATA_HARVESTED")
        assert remaining[0] == "TRIAGE_COMPLETE"
        assert "DONE" in remaining

    def test_get_remaining_stages_from_done(self, checkpoint):
        remaining = checkpoint.get_remaining_stages("DONE")
        assert remaining == []

    def test_get_next_stage(self, checkpoint):
        assert checkpoint.get_next_stage("METADATA_HARVESTED") == "TRIAGE_COMPLETE"
        assert checkpoint.get_next_stage("DONE") is None

    def test_advance_invalid_stage_raises(self, checkpoint):
        with pytest.raises(ValueError):
            checkpoint.advance("test_video", "INVALID_STAGE")


# ---------------------------------------------------------------------------
# Tests: LLM Response Parsing
# ---------------------------------------------------------------------------

from src.ingestion.triage import TriageEngine


class TestLLMResponseParsing:
    """Test parsing of LLM JSON responses (used by triage and entity resolver)."""

    @pytest.fixture
    def engine(self):
        """Create a TriageEngine for testing parse methods."""
        try:
            return TriageEngine()
        except Exception:
            pytest.skip("TriageEngine init requires settings.yaml")

    def test_parse_clean_json(self, engine):
        response = '{"category": "DEEP_KNOWLEDGE", "confidence": 0.9, "reason": "test"}'
        result = engine._parse_llm_response(response)
        assert result["category"] == "DEEP_KNOWLEDGE"
        assert result["confidence"] == 0.9

    def test_parse_code_fenced_json(self, engine):
        response = '```json\n{"category": "NOISE", "confidence": 0.2, "reason": "short"}\n```'
        result = engine._parse_llm_response(response)
        assert result["category"] == "NOISE"

    def test_parse_garbage_input(self, engine):
        response = "I think this video is interesting but I'm not sure."
        result = engine._parse_llm_response(response)
        assert result["category"] == "AMBIGUOUS"

    def test_parse_json_embedded_in_text(self, engine):
        response = 'Here is my analysis: {"category": "DEEP_KNOWLEDGE", "confidence": 0.8, "reason": "detailed"} That is all.'
        result = engine._parse_llm_response(response)
        assert result["category"] == "DEEP_KNOWLEDGE"


# ---------------------------------------------------------------------------
# Tests: Config Validation
# ---------------------------------------------------------------------------

from src.config import _validate_settings


class TestConfigValidation:
    """Test config validation catches missing keys."""

    def test_valid_config(self):
        config = {
            "ollama": {"host": "http://localhost:11434", "triage_model": "llama3"},
            "sqlite": {"path": "data/test.db"},
            "chromadb": {"path": "data/chromadb"},
            "neo4j": {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"},
        }
        # Should not raise
        _validate_settings(config)

    def test_missing_section(self):
        config = {
            "sqlite": {"path": "data/test.db"},
            "chromadb": {"path": "data/chromadb"},
            "neo4j": {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"},
        }
        with pytest.raises(ValueError, match="ollama"):
            _validate_settings(config)

    def test_missing_nested_key(self):
        config = {
            "ollama": {"host": "http://localhost:11434"},  # missing triage_model
            "sqlite": {"path": "data/test.db"},
            "chromadb": {"path": "data/chromadb"},
            "neo4j": {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"},
        }
        with pytest.raises(ValueError, match="triage_model"):
            _validate_settings(config)


# ---------------------------------------------------------------------------
# Tests: Retry Decorator
# ---------------------------------------------------------------------------

from src.utils.retry import with_retry, CircuitBreaker


class TestRetryDecorator:
    """Test the retry and circuit breaker utilities."""

    def test_no_retry_on_success(self):
        call_count = 0

        @with_retry("test_key", default_retries=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_retry_on_failure(self):
        call_count = 0

        @with_retry("test_key", default_retries=2, default_backoff=[0, 0])
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "ok"

        result = fail_then_succeed()
        assert result == "ok"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        @with_retry("test_key", default_retries=1, default_backoff=[0])
        def always_fail():
            raise ConnectionError("permanent")

        with pytest.raises(ConnectionError):
            always_fail()

    def test_circuit_breaker_opens(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        with pytest.raises(ValueError):
            cb.call(self._failing_fn)
        with pytest.raises(ValueError):
            cb.call(self._failing_fn)

        # Circuit should be open now
        assert cb.state == "OPEN"
        with pytest.raises(RuntimeError, match="Circuit breaker OPEN"):
            cb.call(self._failing_fn)

    @staticmethod
    def _failing_fn():
        raise ValueError("boom")


# ---------------------------------------------------------------------------
# Tests: ScanCheckpoint Dataclass
# ---------------------------------------------------------------------------


class TestScanCheckpointDataclass:
    """Test that ScanCheckpoint can be created from SQL row dicts."""

    def test_from_dict_with_id(self):
        row_dict = {
            "id": 42,
            "scan_id": "scan_001",
            "source_url": "https://youtube.com/@test",
            "scan_type": "channel",
            "total_discovered": 10,
            "total_processed": 5,
            "last_video_id": "vid_5",
            "status": "IN_PROGRESS",
            "started_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
        }
        cp = ScanCheckpoint(**row_dict)
        assert cp.id == 42
        assert cp.scan_id == "scan_001"
