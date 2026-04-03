"""
Query parser for knowledgeVault-YT.

Parses structured query syntax into filter components:
    channel:lexfridman topic:AI after:2024-01 guest:"Elon Musk" free text here

Produces a QueryPlan with:
    - free_text: the natural language portion for vector search
    - filters: ChromaDB metadata filters
    - topic_filter: for Neo4j graph-aware retrieval
    - guest_filter: for guest entity matching
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Parsed query with structured filters separated from free text."""
    free_text: str
    channel_filter: Optional[str] = None
    topic_filter: Optional[str] = None
    guest_filter: Optional[str] = None
    after_date: Optional[str] = None
    before_date: Optional[str] = None
    language_filter: Optional[str] = None
    raw_query: str = ""

    def to_chromadb_where(self) -> Optional[dict]:
        """Convert filters to ChromaDB where clause.

        Returns None if no filters are active.
        """
        conditions = []

        if self.channel_filter:
            conditions.append({"channel_id": {"$eq": self.channel_filter}})

        if self.after_date:
            conditions.append({"upload_date": {"$gte": self.after_date}})

        if self.before_date:
            conditions.append({"upload_date": {"$lte": self.before_date}})

        if self.language_filter:
            conditions.append({"language_iso": {"$eq": self.language_filter}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}


# Regex patterns for structured filter tokens
_FILTER_PATTERNS = [
    # channel:name or channel:"multi word"
    (r'channel:(?:"([^"]+)"|(\S+))', "channel"),
    # topic:name or topic:"multi word"
    (r'topic:(?:"([^"]+)"|(\S+))', "topic"),
    # guest:name or guest:"multi word"
    (r'guest:(?:"([^"]+)"|(\S+))', "guest"),
    # after:YYYY-MM or after:YYYY-MM-DD
    (r'after:(\d{4}-\d{2}(?:-\d{2})?)', "after"),
    # before:YYYY-MM or before:YYYY-MM-DD
    (r'before:(\d{4}-\d{2}(?:-\d{2})?)', "before"),
    # lang:en or language:en
    (r'(?:lang|language):(\w{2,5})', "language"),
]


def parse_query(raw_query: str) -> QueryPlan:
    """Parse a query string into a structured QueryPlan.

    Extracts filter tokens (channel:, topic:, after:, etc.) and
    returns the remaining free text for vector search.

    Examples:
        "channel:lexfridman What is consciousness?"
        → free_text="What is consciousness?", channel_filter="lexfridman"

        'topic:AI guest:"Sam Altman" after:2024-01 future of AGI'
        → free_text="future of AGI", topic="AI", guest="Sam Altman", after="2024-01"

        "plain text query with no filters"
        → free_text="plain text query with no filters"
    """
    plan = QueryPlan(free_text="", raw_query=raw_query)
    remaining = raw_query

    for pattern, filter_type in _FILTER_PATTERNS:
        match = re.search(pattern, remaining)
        if match:
            # Extract value (group 1 for quoted, group 2 for unquoted, or just group 1)
            groups = match.groups()
            value = next((g for g in groups if g is not None), "")

            if filter_type == "channel":
                plan.channel_filter = value
            elif filter_type == "topic":
                plan.topic_filter = value
            elif filter_type == "guest":
                plan.guest_filter = value
            elif filter_type == "after":
                plan.after_date = value
            elif filter_type == "before":
                plan.before_date = value
            elif filter_type == "language":
                plan.language_filter = value

            # Remove the matched token from the remaining text
            remaining = remaining[:match.start()] + remaining[match.end():]

    # Clean up the remaining free text
    plan.free_text = re.sub(r'\s{2,}', ' ', remaining).strip()

    if plan.channel_filter or plan.topic_filter or plan.guest_filter:
        logger.info(
            f"Parsed query filters: channel={plan.channel_filter}, "
            f"topic={plan.topic_filter}, guest={plan.guest_filter}, "
            f"after={plan.after_date}, before={plan.before_date}"
        )

    return plan
