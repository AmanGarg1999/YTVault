"""
Unit tests for the entity resolver module.

Tests fuzzy matching, exact matching, LLM response parsing,
and the resolution pipeline — all with mocked Ollama calls.

Run with: python -m pytest tests/test_entity_resolver.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.sqlite_store import SQLiteStore, Guest
from src.intelligence.entity_resolver import EntityResolver, ExtractedEntity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """Create a temporary database with guest seed data."""
    store = SQLiteStore(str(tmp_path / "resolver_test.db"))

    # Seed some guests
    store.upsert_guest("Elon Musk")
    store.upsert_guest("Sam Altman")
    guest = store.upsert_guest("Naval Ravikant")
    store.add_guest_alias(guest.guest_id, "Naval")

    yield store
    store.close()


@pytest.fixture
def resolver(db):
    """Create an EntityResolver with mocked settings."""
    with patch("src.intelligence.entity_resolver.get_settings") as mock_settings, \
         patch("src.intelligence.entity_resolver.load_prompt") as mock_prompt:
        mock_settings.return_value = {
            "ollama": {
                "triage_model": "llama3.2:3b",
                "host": "http://localhost:11434",
            },
            "sqlite": {"path": ""},
            "chromadb": {"path": ""},
            "neo4j": {"uri": "", "user": "", "password": ""},
        }
        mock_prompt.return_value = "You are an NER system."
        er = EntityResolver(db)
    return er


# ---------------------------------------------------------------------------
# LLM Response Parsing Tests
# ---------------------------------------------------------------------------

class TestParseEntityResponse:
    """Test parsing of LLM NER JSON responses."""

    def test_parse_valid_json_array(self, resolver):
        raw = json.dumps([
            {"name": "Elon Musk", "role": "CEO", "context": "Tesla and SpaceX"},
            {"name": "Sam Altman", "role": "CEO", "context": "OpenAI"},
        ])
        entities = resolver._parse_entity_response(raw)
        assert len(entities) == 2
        assert entities[0].name == "Elon Musk"
        assert entities[1].role == "CEO"

    def test_parse_code_fenced_json(self, resolver):
        raw = '```json\n[{"name": "Naval", "role": "investor", "context": "AngelList"}]\n```'
        entities = resolver._parse_entity_response(raw)
        assert len(entities) == 1
        assert entities[0].name == "Naval"

    def test_parse_empty_array(self, resolver):
        entities = resolver._parse_entity_response("[]")
        assert entities == []

    def test_parse_garbage_returns_empty(self, resolver):
        entities = resolver._parse_entity_response("I found some people but not sure who.")
        assert entities == []

    def test_parse_filters_empty_names(self, resolver):
        raw = json.dumps([
            {"name": "", "role": "unknown", "context": ""},
            {"name": "Valid Name", "role": "guest", "context": "appeared"},
        ])
        entities = resolver._parse_entity_response(raw)
        assert len(entities) == 1
        assert entities[0].name == "Valid Name"

    def test_parse_missing_optional_fields(self, resolver):
        raw = json.dumps([{"name": "Test Person"}])
        entities = resolver._parse_entity_response(raw)
        assert len(entities) == 1
        assert entities[0].role == "unknown"
        assert entities[0].context == ""


# ---------------------------------------------------------------------------
# Exact Match Resolution Tests
# ---------------------------------------------------------------------------

class TestExactMatch:
    """Test exact name/alias matching resolution."""

    def test_exact_canonical_match(self, resolver, db):
        guest = resolver.resolve("Elon Musk")
        assert guest.canonical_name == "Elon Musk"

    def test_exact_alias_match(self, resolver, db):
        guest = resolver.resolve("Naval")
        assert guest.canonical_name == "Naval Ravikant"

    def test_no_match_creates_new(self, resolver, db):
        guest = resolver.resolve("Completely Unknown Person")
        assert guest.canonical_name == "Completely Unknown Person"
        assert guest.guest_id > 0

        # Verify it's now in the DB
        found = db.find_guest_exact("Completely Unknown Person")
        assert found is not None


# ---------------------------------------------------------------------------
# Fuzzy Match Tests
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    """Test fuzzy string matching for guest resolution."""

    def test_close_match_found(self, resolver, db):
        # Pre-load cache so fuzzy matching works
        resolver._guests_cache = db.get_all_guests()

        candidates = resolver._fuzzy_match("Elon Musks")  # typo
        assert len(candidates) >= 1
        assert any(c.canonical_name == "Elon Musk" for c in candidates)

    def test_distant_name_no_match(self, resolver, db):
        resolver._guests_cache = db.get_all_guests()

        candidates = resolver._fuzzy_match("Albert Einstein")
        assert len(candidates) == 0

    def test_alias_fuzzy_match(self, resolver, db):
        resolver._guests_cache = db.get_all_guests()

        candidates = resolver._fuzzy_match("Navall")  # close to alias "Naval"
        assert len(candidates) >= 1

    def test_case_insensitive(self, resolver, db):
        resolver._guests_cache = db.get_all_guests()

        candidates = resolver._fuzzy_match("elon musk")
        assert len(candidates) >= 1


# ---------------------------------------------------------------------------
# Entity Extraction Tests (Mocked LLM)
# ---------------------------------------------------------------------------

class TestExtractEntities:
    """Test entity extraction with mocked Ollama."""

    @patch("src.intelligence.entity_resolver.ollama")
    def test_extract_returns_entities(self, mock_ollama, resolver):
        mock_ollama.chat.return_value = {
            "message": {
                "content": json.dumps([
                    {"name": "Joe Rogan", "role": "host", "context": "podcast host"},
                    {"name": "Elon Musk", "role": "guest", "context": "discussing Mars"},
                ])
            }
        }

        entities = resolver.extract_entities("Joe Rogan interviews Elon Musk about Mars.")
        assert len(entities) == 2
        assert entities[0].name == "Joe Rogan"
        assert entities[1].name == "Elon Musk"

    @patch("src.intelligence.entity_resolver.ollama")
    def test_extract_handles_llm_error(self, mock_ollama, resolver):
        mock_ollama.chat.side_effect = Exception("Ollama not running")

        entities = resolver.extract_entities("Some transcript text here.")
        assert entities == []

    @patch("src.intelligence.entity_resolver.ollama")
    def test_extract_truncates_long_text(self, mock_ollama, resolver):
        mock_ollama.chat.return_value = {
            "message": {"content": "[]"}
        }

        long_text = "word " * 5000  # 25,000 chars
        resolver.extract_entities(long_text)

        # Verify the LLM received truncated text (first 2000 chars)
        call_args = mock_ollama.chat.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert len(user_msg) <= 2000


# ---------------------------------------------------------------------------
# Full Pipeline Tests (Mocked LLM)
# ---------------------------------------------------------------------------

class TestProcessVideoEntities:
    """Test the full extract-and-resolve pipeline."""

    @patch("src.intelligence.entity_resolver.ollama")
    def test_full_pipeline_resolves_and_records(self, mock_ollama, resolver, db):
        mock_ollama.chat.return_value = {
            "message": {
                "content": json.dumps([
                    {"name": "Elon Musk", "role": "guest", "context": "discussing AI"},
                    {"name": "New Person", "role": "expert", "context": "quantum computing"},
                ])
            }
        }

        guests = resolver.process_video_entities("test_vid_001", "Elon Musk talks about AI.")
        assert len(guests) == 2

        # Elon Musk should be resolved to existing record (exact match
        # does not increment mention_count — only upsert_guest does)
        elon = next(g for g in guests if g.canonical_name == "Elon Musk")
        assert elon.mention_count >= 1

        # New Person should be created
        new = next(g for g in guests if g.canonical_name == "New Person")
        assert new.guest_id > 0

    @patch("src.intelligence.entity_resolver.ollama")
    def test_deduplicates_within_video(self, mock_ollama, resolver, db):
        """Same name appearing twice in NER results should only resolve once."""
        mock_ollama.chat.return_value = {
            "message": {
                "content": json.dumps([
                    {"name": "Sam Altman", "role": "CEO", "context": "OpenAI"},
                    {"name": "Sam Altman", "role": "speaker", "context": "AGI talk"},
                ])
            }
        }

        guests = resolver.process_video_entities("test_vid_002", "Sam Altman discusses AGI twice.")
        assert len(guests) == 1
        assert guests[0].canonical_name == "Sam Altman"

    @patch("src.intelligence.entity_resolver.ollama")
    def test_cache_cleared_after_batch(self, mock_ollama, resolver, db):
        mock_ollama.chat.return_value = {
            "message": {"content": "[]"}
        }

        resolver.process_video_entities("test_vid_003", "No entities here.")
        assert resolver._guests_cache is None  # Cache should be cleared
