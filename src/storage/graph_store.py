"""
Neo4j graph store for knowledgeVault-YT.

Manages the knowledge graph: Videos, Channels, Guests, and Topics
as nodes with typed relationships for cross-channel intelligence.
"""

import logging
from typing import Optional

from neo4j import GraphDatabase

from src.config import get_settings
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)


class GraphStore:
    """Neo4j-backed knowledge graph for entity relationships.

    Graph Schema:
        Nodes:  (:Video), (:Channel), (:Guest), (:Topic)
        Edges:  (Channel)-[:PUBLISHED]->(Video)
                (Guest)-[:APPEARED_IN {timestamp, context}]->(Video)
                (Video)-[:DISCUSSES {relevance}]->(Topic)
                (Guest)-[:EXPERT_ON {mentions}]->(Topic)
                (Topic)-[:RELATED_TO {co_occurrence}]->(Topic)
    """

    def __init__(self):
        settings = get_settings()
        cfg = settings["neo4j"]
        self.driver = GraphDatabase.driver(
            cfg["uri"],
            auth=(cfg["user"], cfg["password"]),
        )
        self._init_schema()
        logger.info(f"GraphStore connected: {cfg['uri']}")

    def _init_schema(self):
        """Create constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT unique_video IF NOT EXISTS FOR (v:Video) REQUIRE v.video_id IS UNIQUE",
            "CREATE CONSTRAINT unique_channel IF NOT EXISTS FOR (c:Channel) REQUIRE c.channel_id IS UNIQUE",
            "CREATE CONSTRAINT unique_guest IF NOT EXISTS FOR (g:Guest) REQUIRE g.canonical_name IS UNIQUE",
            "CREATE CONSTRAINT unique_topic IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX video_title IF NOT EXISTS FOR (v:Video) ON (v.title)",
            "CREATE INDEX guest_name IF NOT EXISTS FOR (g:Guest) ON (g.canonical_name)",
            "CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)",
        ]
        with self.driver.session() as session:
            for stmt in constraints + indexes:
                try:
                    session.run(stmt)
                except Exception as e:
                    logger.debug(f"Schema statement skipped: {e}")

    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()

    # -------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------

    @with_retry("neo4j_query")
    def upsert_channel(self, channel_id: str, name: str, url: str = "",
                       category: str = "") -> None:
        """Create or update a Channel node."""
        with self.driver.session() as session:
            session.run(
                """MERGE (c:Channel {channel_id: $channel_id})
                   SET c.name = $name, c.url = $url, c.category = $category""",
                channel_id=channel_id, name=name, url=url, category=category,
            )

    @with_retry("neo4j_query")
    def upsert_video(self, video_id: str, title: str, channel_id: str,
                     upload_date: str = "", duration: int = 0) -> None:
        """Create or update a Video node and link to its Channel."""
        with self.driver.session() as session:
            session.run(
                """MERGE (v:Video {video_id: $video_id})
                   SET v.title = $title, v.upload_date = $upload_date,
                       v.duration = $duration
                   WITH v
                   MATCH (c:Channel {channel_id: $channel_id})
                   MERGE (c)-[:PUBLISHED]->(v)""",
                video_id=video_id, title=title, channel_id=channel_id,
                upload_date=upload_date, duration=duration,
            )

    @with_retry("neo4j_query")
    def upsert_guest(self, canonical_name: str, entity_type: str = "PERSON") -> None:
        """Create or update a Guest node."""
        with self.driver.session() as session:
            session.run(
                """MERGE (g:Guest {canonical_name: $name})
                   SET g.first_seen = COALESCE(g.first_seen, datetime()),
                       g.mention_count = COALESCE(g.mention_count, 0) + 1,
                       g.entity_type = $entity_type,
                       g.last_seen = datetime()""",
                name=canonical_name, entity_type=entity_type,
            )

    @with_retry("neo4j_query")
    def upsert_topic(self, topic_name: str) -> None:
        """Create or update a Topic node."""
        with self.driver.session() as session:
            session.run(
                "MERGE (t:Topic {name: $name})",
                name=topic_name.lower().strip(),
            )

    # -------------------------------------------------------------------
    # Relationship Operations
    # -------------------------------------------------------------------

    @with_retry("neo4j_query")
    def link_guest_to_video(self, guest_name: str, video_id: str,
                            timestamp: float = 0.0, context: str = "") -> None:
        """Create APPEARED_IN relationship between Guest and Video."""
        with self.driver.session() as session:
            session.run(
                """MATCH (g:Guest {canonical_name: $guest_name})
                   MATCH (v:Video {video_id: $video_id})
                   MERGE (g)-[r:APPEARED_IN]->(v)
                   SET r.timestamp = $timestamp, r.context = $context""",
                guest_name=guest_name, video_id=video_id,
                timestamp=timestamp, context=context[:200],
            )

    @with_retry("neo4j_query")
    def link_video_to_topic(self, video_id: str, topic_name: str,
                            relevance: float = 1.0) -> None:
        """Create DISCUSSES relationship between Video and Topic."""
        with self.driver.session() as session:
            session.run(
                """MATCH (v:Video {video_id: $video_id})
                   MERGE (t:Topic {name: $topic_name})
                   MERGE (v)-[r:DISCUSSES]->(t)
                   SET r.relevance = $relevance""",
                video_id=video_id, topic_name=topic_name.lower().strip(),
                relevance=relevance,
            )

    @with_retry("neo4j_query")
    def link_guest_to_topic(self, guest_name: str, topic_name: str,
                            mention_count: int = 1) -> None:
        """Create EXPERT_ON relationship between Guest and Topic."""
        with self.driver.session() as session:
            session.run(
                """MATCH (g:Guest {canonical_name: $guest_name})
                   MERGE (t:Topic {name: $topic_name})
                   MERGE (g)-[r:EXPERT_ON]->(t)
                   SET r.mention_count = COALESCE(r.mention_count, 0) + $count""",
                guest_name=guest_name, topic_name=topic_name.lower().strip(),
                count=mention_count,
            )

    @with_retry("neo4j_query")
    def link_related_topics(self, topic_a: str, topic_b: str,
                            co_occurrence: int = 1,
                            relationship_type: str = "") -> None:
        """Create RELATED_TO relationship between two Topics.

        Args:
            relationship_type: Optional classification from Epiphany Engine:
                CONSENSUS, CONTRADICTION, COMPLEMENTARY, EVOLUTION.
        """
        with self.driver.session() as session:
            session.run(
                """MERGE (a:Topic {name: $a})
                   MERGE (b:Topic {name: $b})
                   MERGE (a)-[r:RELATED_TO]-(b)
                   SET r.co_occurrence = COALESCE(r.co_occurrence, 0) + $count,
                       r.relationship_type = CASE
                           WHEN $rel_type <> '' THEN $rel_type
                           ELSE COALESCE(r.relationship_type, '')
                       END""",
                a=topic_a.lower().strip(), b=topic_b.lower().strip(),
                count=co_occurrence, rel_type=relationship_type,
            )

    @with_retry("neo4j_query")
    def upsert_claim(self, claim_text: str, speaker: str, video_id: str,
                     topic: str = "") -> None:
        """Create a Claim node with ASSERTED, SOURCED_FROM, and ABOUT relationships."""
        with self.driver.session() as session:
            session.run(
                """MERGE (cl:Claim {text: $text})
                   SET cl.speaker = $speaker
                   WITH cl
                   MATCH (v:Video {video_id: $video_id})
                   MERGE (cl)-[:SOURCED_FROM]->(v)
                   WITH cl
                   OPTIONAL MATCH (g:Guest {canonical_name: $speaker})
                   FOREACH (_ IN CASE WHEN g IS NOT NULL THEN [1] ELSE [] END |
                       MERGE (g)-[:ASSERTED]->(cl)
                   )""",
                text=claim_text[:500], speaker=speaker, video_id=video_id,
            )
            # Link to topic if provided
            if topic:
                session.run(
                    """MATCH (cl:Claim {text: $text})
                       MERGE (t:Topic {name: $topic})
                       MERGE (cl)-[:ABOUT]->(t)""",
                    text=claim_text[:500], topic=topic.lower().strip(),
                )

    # -------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------

    @with_retry("neo4j_query")
    def get_guest_appearances(self, guest_name: str) -> list[dict]:
        """Get all videos where a guest appeared, across channels."""
        with self.driver.session() as session:
            result = session.run(
                """MATCH (g:Guest {canonical_name: $name})-[a:APPEARED_IN]->(v:Video)
                          <-[:PUBLISHED]-(c:Channel)
                   RETURN c.name AS channel, v.title AS title,
                          v.video_id AS video_id, v.upload_date AS upload_date,
                          a.timestamp AS timestamp, a.context AS context
                   ORDER BY v.upload_date DESC""",
                name=guest_name,
            )
            return [dict(record) for record in result]

    @with_retry("neo4j_query")
    def get_cross_channel_topics(self, limit: int = 20) -> list[dict]:
        """Find topics discussed across multiple channels."""
        with self.driver.session() as session:
            result = session.run(
                """MATCH (c1:Channel)-[:PUBLISHED]->(v1:Video)-[:DISCUSSES]->(t:Topic)
                          <-[:DISCUSSES]-(v2:Video)<-[:PUBLISHED]-(c2:Channel)
                   WHERE c1 <> c2
                   RETURN t.name AS topic, c1.name AS channel_1, c2.name AS channel_2,
                          COUNT(*) AS connection_strength
                   ORDER BY connection_strength DESC
                   LIMIT $limit""",
                limit=limit,
            )
            return [dict(record) for record in result]

    @with_retry("neo4j_query")
    def get_guest_topic_evolution(self, guest_name: str) -> list[dict]:
        """Track how a guest's discussed topics evolved over time."""
        with self.driver.session() as session:
            result = session.run(
                """MATCH (g:Guest {canonical_name: $name})-[:APPEARED_IN]->(v:Video)
                          -[:DISCUSSES]->(t:Topic)
                   RETURN t.name AS topic, v.upload_date AS date,
                          v.title AS video_title, v.video_id AS video_id
                   ORDER BY v.upload_date""",
                name=guest_name,
            )
            return [dict(record) for record in result]

    @with_retry("neo4j_query")
    def get_graph_stats(self) -> dict:
        """Get aggregate graph statistics.
        
        Secured against Cypher injection by validating node labels against
        a strict allowlist before formatting the dynamic query.
        """
        stats = {}
        allowed_labels = {"Video", "Channel", "Guest", "Topic"}
        
        with self.driver.session() as session:
            for label in allowed_labels:
                # Defensively validate label even if hardcoded
                if label not in allowed_labels:
                    continue
                result = session.run(f"MATCH (n:{label}) RETURN COUNT(n) AS count")
                stats[label.lower() + "_nodes"] = result.single()["count"]

            result = session.run("MATCH ()-[r]->() RETURN COUNT(r) AS count")
            stats["total_relationships"] = result.single()["count"]

        return stats
