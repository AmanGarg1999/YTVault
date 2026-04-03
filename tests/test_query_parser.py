"""
Unit tests for the structured query parser.

Run with: python -m pytest tests/test_query_parser.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.intelligence.query_parser import parse_query, QueryPlan


# ---------------------------------------------------------------------------
# Single Filter Tests
# ---------------------------------------------------------------------------

class TestSingleFilters:
    """Test individual filter token extraction."""

    def test_channel_unquoted(self):
        plan = parse_query("channel:lexfridman What is consciousness?")
        assert plan.channel_filter == "lexfridman"
        assert plan.free_text == "What is consciousness?"

    def test_channel_quoted(self):
        plan = parse_query('channel:"Lex Fridman" What is consciousness?')
        assert plan.channel_filter == "Lex Fridman"
        assert plan.free_text == "What is consciousness?"

    def test_topic_unquoted(self):
        plan = parse_query("topic:AI future of intelligence")
        assert plan.topic_filter == "AI"
        assert plan.free_text == "future of intelligence"

    def test_topic_quoted(self):
        plan = parse_query('topic:"machine learning" gradient descent explained')
        assert plan.topic_filter == "machine learning"
        assert plan.free_text == "gradient descent explained"

    def test_guest_unquoted(self):
        plan = parse_query("guest:Naval How to get rich?")
        assert plan.guest_filter == "Naval"
        assert plan.free_text == "How to get rich?"

    def test_guest_quoted(self):
        plan = parse_query('guest:"Sam Altman" future of AGI')
        assert plan.guest_filter == "Sam Altman"
        assert plan.free_text == "future of AGI"

    def test_after_date_month(self):
        plan = parse_query("after:2024-01 latest AI research")
        assert plan.after_date == "2024-01"
        assert plan.free_text == "latest AI research"

    def test_after_date_full(self):
        plan = parse_query("after:2024-01-15 recent talks")
        assert plan.after_date == "2024-01-15"

    def test_before_date(self):
        plan = parse_query("before:2023-06 historical perspectives")
        assert plan.before_date == "2023-06"
        assert plan.free_text == "historical perspectives"

    def test_language_lang(self):
        plan = parse_query("lang:en English content")
        assert plan.language_filter == "en"
        assert plan.free_text == "English content"

    def test_language_full_keyword(self):
        plan = parse_query("language:es Spanish content")
        assert plan.language_filter == "es"
        assert plan.free_text == "Spanish content"


# ---------------------------------------------------------------------------
# Combined Filter Tests
# ---------------------------------------------------------------------------

class TestCombinedFilters:
    """Test multiple filters in a single query."""

    def test_channel_and_topic(self):
        plan = parse_query("channel:lexfridman topic:AI What is AGI?")
        assert plan.channel_filter == "lexfridman"
        assert plan.topic_filter == "AI"
        assert plan.free_text == "What is AGI?"

    def test_all_filters(self):
        plan = parse_query(
            'channel:huberman topic:"sleep" guest:"Matt Walker" '
            'after:2024-01 before:2025-01 lang:en best sleep practices'
        )
        assert plan.channel_filter == "huberman"
        assert plan.topic_filter == "sleep"
        assert plan.guest_filter == "Matt Walker"
        assert plan.after_date == "2024-01"
        assert plan.before_date == "2025-01"
        assert plan.language_filter == "en"
        assert plan.free_text == "best sleep practices"

    def test_date_range(self):
        plan = parse_query("after:2023-01 before:2024-06 neural networks")
        assert plan.after_date == "2023-01"
        assert plan.before_date == "2024-06"
        assert plan.free_text == "neural networks"


# ---------------------------------------------------------------------------
# No-Filter / Edge Case Tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test plain text and unusual inputs."""

    def test_plain_text_no_filters(self):
        plan = parse_query("What did Naval Ravikant say about wealth creation?")
        assert plan.channel_filter is None
        assert plan.topic_filter is None
        assert plan.guest_filter is None
        assert plan.after_date is None
        assert plan.before_date is None
        assert plan.language_filter is None
        assert plan.free_text == "What did Naval Ravikant say about wealth creation?"

    def test_empty_query(self):
        plan = parse_query("")
        assert plan.free_text == ""
        assert plan.channel_filter is None

    def test_only_filter_no_text(self):
        plan = parse_query("channel:lexfridman")
        assert plan.channel_filter == "lexfridman"
        assert plan.free_text == ""

    def test_preserves_raw_query(self):
        raw = "channel:lex topic:AI What is AGI?"
        plan = parse_query(raw)
        assert plan.raw_query == raw

    def test_extra_whitespace_cleaned(self):
        plan = parse_query("channel:test    lots   of   spaces   here")
        assert "  " not in plan.free_text
        assert plan.free_text == "lots of spaces here"

    def test_filter_at_end(self):
        plan = parse_query("What is dark matter? topic:physics")
        assert plan.topic_filter == "physics"
        assert "topic:" not in plan.free_text

    def test_colon_in_free_text_not_captured(self):
        """A colon that doesn't match any known filter should remain in free text."""
        plan = parse_query("Ratio of 1:10 in experiment")
        assert plan.channel_filter is None
        assert "1:10" in plan.free_text


# ---------------------------------------------------------------------------
# ChromaDB Where Clause Conversion
# ---------------------------------------------------------------------------

class TestChromaDBWhere:
    """Test conversion of QueryPlan to ChromaDB filter dict."""

    def test_no_filters_returns_none(self):
        plan = parse_query("plain text query")
        assert plan.to_chromadb_where() is None

    def test_single_channel_filter(self):
        plan = parse_query("channel:UCxxx some query")
        where = plan.to_chromadb_where()
        assert where == {"channel_id": {"$eq": "UCxxx"}}

    def test_date_range_filter(self):
        plan = parse_query("after:2024-01 before:2025-01 test")
        where = plan.to_chromadb_where()
        assert "$and" in where
        conditions = where["$and"]
        assert len(conditions) == 2

    def test_combined_filters_and_clause(self):
        plan = parse_query("channel:test after:2024-01 lang:en query")
        where = plan.to_chromadb_where()
        assert "$and" in where
        assert len(where["$and"]) == 3
