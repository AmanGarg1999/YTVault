"""
Unit tests for the export engine.

Run with: python -m pytest tests/test_export.py -v
"""

import csv
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.intelligence.rag_engine import Citation, ConfidenceScore, RAGResponse
from src.intelligence.export import ExportEngine
from src.storage.sqlite_store import SQLiteStore, Video, Channel, Guest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """Create a temporary database with seed data for export tests."""
    store = SQLiteStore(str(tmp_path / "export_test.db"))

    # Insert a channel and video
    channel = Channel(channel_id="ch1", name="Test Channel", url="https://youtube.com/@test")
    store.upsert_channel(channel)

    video = Video(
        video_id="vid1", channel_id="ch1", title="Test Video",
        url="https://youtube.com/watch?v=vid1",
        duration_seconds=600, upload_date="2024-01-01",
    )
    store.insert_video(video)

    # Insert guests
    store.upsert_guest("Alice Smith")
    store.upsert_guest("Bob Jones", entity_type="ORGANIZATION")

    yield store
    store.close()


@pytest.fixture
def exporter(db):
    return ExportEngine(db)


@pytest.fixture
def sample_rag_response():
    """Create a sample RAGResponse for export testing."""
    citations = [
        Citation(
            source_id="source_1",
            chunk_id="vid1__chunk_0001",
            video_id="vid1",
            video_title="Test Video",
            channel_name="Test Channel",
            start_timestamp=120.0,
            end_timestamp=180.0,
            text_excerpt="This is a sample excerpt from the transcript.",
        ),
        Citation(
            source_id="source_2",
            chunk_id="vid1__chunk_0002",
            video_id="vid1",
            video_title="Test Video",
            channel_name="Test Channel",
            start_timestamp=300.0,
            end_timestamp=360.0,
            text_excerpt="Another excerpt with different content.",
        ),
    ]

    confidence = ConfidenceScore(
        source_diversity=0.5,
        chunk_relevance=0.85,
        coverage=0.7,
        overall=0.72,
    )

    return RAGResponse(
        query="What is the meaning of life?",
        answer="According to the sources, the meaning of life is 42.",
        citations=citations,
        confidence=confidence,
        total_chunks_retrieved=15,
        total_chunks_used=2,
        latency_ms=450.0,
    )


# ---------------------------------------------------------------------------
# RAG Response Export Tests
# ---------------------------------------------------------------------------

class TestRAGExportMarkdown:
    """Test RAG response export in Markdown format."""

    def test_contains_question(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="markdown")
        assert "What is the meaning of life?" in output

    def test_contains_answer(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="markdown")
        assert "the meaning of life is 42" in output

    def test_contains_citations(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="markdown")
        assert "[source_1]" in output
        assert "[source_2]" in output
        assert "Test Video" in output

    def test_contains_youtube_links(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="markdown")
        assert "youtube.com/watch?v=vid1" in output

    def test_contains_latency(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="markdown")
        assert "450ms" in output


class TestRAGExportJSON:
    """Test RAG response export in JSON format."""

    def test_valid_json(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="json")
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_json_structure(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="json")
        data = json.loads(output)
        assert "query" in data
        assert "answer" in data
        assert "citations" in data
        assert "metrics" in data

    def test_json_citations_count(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="json")
        data = json.loads(output)
        assert len(data["citations"]) == 2

    def test_json_citation_fields(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="json")
        data = json.loads(output)
        citation = data["citations"][0]
        assert "source_id" in citation
        assert "video_id" in citation
        assert "video_title" in citation
        assert "channel" in citation
        assert "youtube_link" in citation

    def test_json_metrics(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="json")
        data = json.loads(output)
        assert data["metrics"]["chunks_retrieved"] == 15
        assert data["metrics"]["chunks_used"] == 2


class TestRAGExportCSV:
    """Test RAG response export in CSV format."""

    def test_valid_csv(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="csv")
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 citations

    def test_csv_header(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        assert "Source" in header
        assert "Video Title" in header
        assert "Channel" in header

    def test_csv_data_rows(self, exporter, sample_rag_response):
        output = exporter.export_rag_response(sample_rag_response, fmt="csv")
        reader = csv.reader(io.StringIO(output))
        next(reader)  # skip header
        row = next(reader)
        assert "source_1" in row
        assert "Test Video" in row


# ---------------------------------------------------------------------------
# Guest Export Tests
# ---------------------------------------------------------------------------

class TestGuestExport:
    """Test guest registry export in various formats."""

    def test_guest_markdown(self, exporter):
        output = exporter.export_guests(fmt="markdown")
        assert "Alice Smith" in output
        assert "Bob Jones" in output
        assert "Guest Registry" in output

    def test_guest_json(self, exporter):
        output = exporter.export_guests(fmt="json")
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 2
        names = {g["name"] for g in data}
        assert "Alice Smith" in names
        assert "Bob Jones" in names

    def test_guest_csv(self, exporter):
        output = exporter.export_guests(fmt="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        assert "Name" in header
        rows = list(reader)
        assert len(rows) == 2

    def test_guest_json_includes_entity_type(self, exporter):
        output = exporter.export_guests(fmt="json")
        data = json.loads(output)
        org = next(g for g in data if g["name"] == "Bob Jones")
        assert org["type"] == "ORGANIZATION"


# ---------------------------------------------------------------------------
# Pipeline Stats Export Tests
# ---------------------------------------------------------------------------

class TestPipelineStatsExport:
    """Test pipeline statistics export."""

    def test_stats_markdown(self, exporter):
        output = exporter.export_pipeline_stats()
        assert "Pipeline Statistics" in output
        assert "Total Videos" in output
        assert "Total Channels" in output

    def test_stats_contains_counts(self, exporter):
        output = exporter.export_pipeline_stats()
        # Should contain numeric values (at least 0s)
        assert "| 0 |" in output or "| 1 |" in output


# ---------------------------------------------------------------------------
# Citation Helper Tests
# ---------------------------------------------------------------------------

class TestCitationHelpers:
    """Test Citation dataclass properties."""

    def test_timestamp_str(self):
        c = Citation(
            source_id="s1", chunk_id="c1", video_id="v1",
            video_title="Test", channel_name="Ch",
            start_timestamp=125.0, end_timestamp=185.0,
            text_excerpt="text",
        )
        assert c.timestamp_str == "02:05"

    def test_youtube_link(self):
        c = Citation(
            source_id="s1", chunk_id="c1", video_id="abc123",
            video_title="Test", channel_name="Ch",
            start_timestamp=60.0, end_timestamp=120.0,
            text_excerpt="text",
        )
        assert c.youtube_link == "https://www.youtube.com/watch?v=abc123&t=60s"

    def test_zero_timestamp(self):
        c = Citation(
            source_id="s1", chunk_id="c1", video_id="v1",
            video_title="Test", channel_name="Ch",
            start_timestamp=0.0, end_timestamp=30.0,
            text_excerpt="text",
        )
        assert c.timestamp_str == "00:00"
        assert "&t=0s" in c.youtube_link
