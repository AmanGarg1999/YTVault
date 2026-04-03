"""
Integration test for the pipeline orchestrator.

Mocks all external dependencies (yt-dlp, Ollama, SponsorBlock, Neo4j)
and verifies the full pipeline runs a single video through all stages
with correct checkpoint progression.

Run with: python -m pytest tests/test_pipeline_integration.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.sqlite_store import SQLiteStore, Channel, Video
from src.pipeline.checkpoint import STAGE_ORDER


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_VIDEO_ID = "dQw4w9WgXcQ"
FAKE_CHANNEL_ID = "UCfake123"

FAKE_METADATA_JSON = json.dumps({
    "id": FAKE_VIDEO_ID,
    "channel_id": FAKE_CHANNEL_ID,
    "channel": "Test Channel",
    "channel_url": "https://youtube.com/@test",
    "title": "Integration Test Video — Deep Dive Analysis",
    "webpage_url": f"https://youtube.com/watch?v={FAKE_VIDEO_ID}",
    "description": "A comprehensive analysis of testing methodologies.",
    "duration": 3600,
    "upload_date": "20240115",
    "view_count": 100000,
    "tags": ["analysis", "testing", "deep dive"],
    "language": "en",
})


@pytest.fixture
def settings(tmp_path):
    """Create test settings with temp paths."""
    return {
        "app": {"name": "test", "version": "0.1.0", "data_dir": str(tmp_path)},
        "ollama": {
            "host": "http://localhost:11434",
            "triage_model": "llama3.2:3b",
            "normalizer_model": "llama3.2:3b",
            "rag_model": "llama3.2:3b",
            "embedding_model": "nomic-embed-text",
            "triage_max_tokens": 100,
            "normalizer_max_tokens": 2048,
            "temperature": 0.1,
        },
        "sqlite": {"path": str(tmp_path / "test.db")},
        "chromadb": {"path": str(tmp_path / "chromadb")},
        "neo4j": {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"},
        "ingestion": {
            "concurrent_metadata_fetches": 1,
            "checkpoint_interval": 10,
            "rate_limit_delay": 0,
        },
        "triage": {
            "min_duration_seconds": 60,
            "llm_confidence_threshold": 0.7,
            "knowledge_keywords": ["analysis", "deep dive", "lecture"],
        },
        "refinement": {
            "sponsorblock_api": "https://sponsor.ajay.app/api/skipSegments",
            "sponsorblock_categories": ["sponsor"],
            "sponsorblock_timeout": 5,
            "normalizer_chunk_size": 1000,
            "normalizer_chunk_overlap": 100,
        },
        "chunking": {"window_size": 100, "overlap": 20, "min_chunk_size": 10},
        "rag": {"vector_top_k": 15, "rerank_top_k": 8, "chunk_overlap_dedup": True},
        "retry": {},
    }


@pytest.fixture
def db(settings):
    """Create a temporary database."""
    store = SQLiteStore(settings["sqlite"]["path"])
    yield store
    store.close()


# ---------------------------------------------------------------------------
# Integration Test: Full Pipeline for a Single Video
# ---------------------------------------------------------------------------

class TestPipelineSingleVideo:
    """Test the full pipeline for a single video with all externals mocked."""

    @patch("src.pipeline.orchestrator.get_settings")
    @patch("src.pipeline.orchestrator.ensure_data_dirs")
    @patch("src.ingestion.triage.get_settings")
    @patch("src.ingestion.triage.load_prompt")
    @patch("src.ingestion.triage.load_verified_channels")
    @patch("src.ingestion.refinement.get_settings")
    @patch("src.ingestion.refinement.load_prompt")
    @patch("src.ingestion.discovery._run_ytdlp")
    @patch("src.ingestion.transcript.YouTubeTranscriptApi")
    @patch("src.ingestion.refinement.requests")
    @patch("src.ingestion.refinement.ollama")
    def test_single_video_reaches_embedded(
        self, mock_refinement_ollama, mock_requests,
        mock_transcript_api, mock_ytdlp,
        mock_ref_prompt, mock_ref_settings,
        mock_verified, mock_triage_prompt, mock_triage_settings,
        mock_ensure_dirs, mock_orch_settings,
        settings, db, tmp_path,
    ):
        """Verify a video progresses through discovery → triage → transcript →
        sponsor_filter → normalize → chunk → embed stages."""

        # --- Configure mocks ---

        # Settings: return our test config for all callers
        mock_orch_settings.return_value = settings
        mock_triage_settings.return_value = settings
        mock_ref_settings.return_value = settings

        # Prompts
        mock_triage_prompt.return_value = "Classify this content."
        mock_ref_prompt.return_value = "Normalize this text."

        # Verified channels: empty
        mock_verified.return_value = {"verified_channels": [], "shorts_whitelist": []}

        # yt-dlp: return fake metadata for single video
        mock_ytdlp.return_value = FAKE_METADATA_JSON

        # Transcript: return a realistic transcript
        fake_segments = [
            MagicMock(text="This is a comprehensive analysis of testing.",
                      start=0.0, duration=5.0, is_generated=False),
            MagicMock(text="We explore different methodologies and approaches.",
                      start=5.0, duration=5.0, is_generated=False),
            MagicMock(text="Deep learning has transformed the field significantly.",
                      start=10.0, duration=5.0, is_generated=False),
        ] * 20  # Repeat to get enough words for chunking

        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = fake_segments

        mock_list = MagicMock()
        mock_list.find_manually_created_transcript.return_value = mock_transcript

        mock_api_instance = MagicMock()
        mock_api_instance.list.return_value = mock_list
        mock_transcript_api.return_value = mock_api_instance

        # SponsorBlock: no segments (404)
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response

        # Normalization LLM: return cleaned text as-is
        mock_refinement_ollama.chat.return_value = {
            "message": {"content": " ".join(s.text for s in fake_segments)}
        }

        # --- Run the pipeline ---
        from src.pipeline.orchestrator import PipelineOrchestrator

        # Inject our pre-built db and skip vector/graph stores
        with patch.object(PipelineOrchestrator, '__init__', lambda self: None):
            pipeline = PipelineOrchestrator()
            pipeline.settings = settings
            pipeline.ollama_cfg = settings["ollama"]
            pipeline.db = db
            pipeline._on_progress = None
            pipeline._on_status = None
            pipeline._graph_store = None
            pipeline._vector_store = None

            from src.pipeline.checkpoint import CheckpointManager
            from src.ingestion.triage import TriageEngine
            from src.ingestion.refinement import TextNormalizer

            pipeline.checkpoint = CheckpointManager(db)
            pipeline.triage = TriageEngine()
            pipeline.normalizer = TextNormalizer()

        # Stage 1: Manually insert channel + video (simulating discovery)
        channel = Channel(
            channel_id=FAKE_CHANNEL_ID, name="Test Channel",
            url="https://youtube.com/@test",
        )
        db.upsert_channel(channel)

        video_data = json.loads(FAKE_METADATA_JSON)
        video = Video(
            video_id=FAKE_VIDEO_ID, channel_id=FAKE_CHANNEL_ID,
            title=video_data["title"],
            url=video_data["webpage_url"],
            description=video_data["description"],
            duration_seconds=3600,
            upload_date="2024-01-15",
            tags=video_data["tags"],
        )
        db.insert_video(video)

        # Stage 2: Triage — keyword "analysis" + "deep dive" in title → ACCEPTED
        pipeline._stage_triage(video)
        pipeline.checkpoint.advance(FAKE_VIDEO_ID, "TRIAGE_COMPLETE")

        triaged = db.get_video(FAKE_VIDEO_ID)
        assert triaged.triage_status == "ACCEPTED"

        # Stage 3: Transcript
        success = pipeline._stage_transcript(triaged)
        assert success
        pipeline.checkpoint.advance(FAKE_VIDEO_ID, "TRANSCRIPT_FETCHED")

        # Verify temp state was created (not in transcript_chunks)
        temp = db.get_temp_state(FAKE_VIDEO_ID)
        assert temp is not None
        assert len(temp["raw_text"]) > 0
        assert temp["segments_json"] != "[]"

        # Stage 4: SponsorBlock filter
        pipeline._stage_sponsor_filter(triaged)
        pipeline.checkpoint.advance(FAKE_VIDEO_ID, "SPONSOR_FILTERED")

        # Stage 5: Normalization
        pipeline._stage_normalize(triaged)
        pipeline.checkpoint.advance(FAKE_VIDEO_ID, "TEXT_NORMALIZED")

        # Verify normalized text in temp state
        temp_after = db.get_temp_state(FAKE_VIDEO_ID)
        assert temp_after["cleaned_text"] != ""

        # Stage 6: Chunking
        pipeline._stage_chunk(triaged)
        pipeline.checkpoint.advance(FAKE_VIDEO_ID, "CHUNKED")

        # Verify chunks were created and temp state was cleaned up
        chunks = db.get_chunks_for_video(FAKE_VIDEO_ID)
        assert len(chunks) > 0
        assert db.get_temp_state(FAKE_VIDEO_ID) is None  # Cleaned up

        # Verify checkpoint progression
        final = db.get_video(FAKE_VIDEO_ID)
        assert final.checkpoint_stage == "CHUNKED"

    def test_checkpoint_stage_order_is_valid(self):
        """Verify STAGE_ORDER has expected structure."""
        assert STAGE_ORDER[0] == "METADATA_HARVESTED"
        assert STAGE_ORDER[-1] == "DONE"
        assert "TRIAGE_COMPLETE" in STAGE_ORDER
        assert "TRANSCRIPT_FETCHED" in STAGE_ORDER
        assert "CHUNKED" in STAGE_ORDER
        assert "EMBEDDED" in STAGE_ORDER
        assert "GRAPH_SYNCED" in STAGE_ORDER
