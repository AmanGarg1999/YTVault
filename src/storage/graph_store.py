"""
Neo4j graph store for knowledgeVault-YT.

Manages the knowledge graph: Videos, Channels, Guests, and Topics
as nodes with typed relationships for cross-channel intelligence.
"""

import logging
import threading
from typing import Optional

from neo4j import GraphDatabase

from src.config import get_settings
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)


class GraphStore:
    """Neo4j-backed knowledge graph for entity relationships.
    
    Implements a thread-safe Singleton pattern to avoid redundant 
    driver initialization and heavy schema checks.

    Graph Schema:
        Nodes:  (:Video), (:Channel), (:Guest), (:Topic)
        Edges:  (Channel)-[:PUBLISHED]->(Video)
                (Guest)-[:APPEARED_IN {timestamp, context}]->(Video)
                (Video)-[:DISCUSSES {relevance}]->(Topic)
                (Guest)-[:EXPERT_ON {mentions}]->(Topic)
                (Topic)-[:RELATED_TO {co_occurrence}]->(Topic)
    """
    _instance = None
    _initialized = False
    _schema_initialized = False
    _lock = threading.RLock()

    def __new__(cls):
        """Singleton pattern: return existing instance if available (thread-safe)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GraphStore, cls).__new__(cls)
            return cls._instance

    def __init__(self):
        """Initialize Neo4j driver and schema if not already done."""
        with self._lock:
            if GraphStore._initialized:
                return

            settings = get_settings()
            cfg = settings["neo4j"]
            self.driver = GraphDatabase.driver(
                cfg["uri"],
                auth=(cfg["user"], cfg["password"]),
            )
            GraphStore._initialized = True
            if self._init_schema():
                GraphStore._schema_initialized = True
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
        success = True
        with self.get_session() as session:
            for stmt in constraints + indexes:
                try:
                    session.run(stmt)
                except Exception as e:
                    logger.warning(f"Schema statement failed: {e}")
                    success = False
        return success

    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()

    def _ensure_driver(self):
        """Ensure the Neo4j driver is initialized and connected."""
        with self._lock:
            try:
                if self.driver:
                    self.driver.verify_connectivity()
                    return
            except Exception:
                logger.info("GraphStore: Driver closed or unreachable. Re-initializing...")
            
            settings = get_settings()
            cfg = settings["neo4j"]
            self.driver = GraphDatabase.driver(
                cfg["uri"],
                auth=(cfg["user"], cfg["password"]),
            )
            GraphStore._initialized = True
            
            # Re-attempt schema if it was never successful
            if not GraphStore._schema_initialized:
                if self._init_schema():
                    GraphStore._schema_initialized = True

    def get_session(self):
        """Get a new Neo4j session, re-initializing driver if necessary."""
        self._ensure_driver()
        return self.driver.session()

    def run_query(self, query: str, **params) -> list[dict]:
        """Execute a raw Cypher query and return results as a list of dicts."""
        with self.get_session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    # -------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------

    @with_retry("neo4j_query")
    def upsert_channel(self, channel_id: str, name: str, url: str = "",
                       category: str = "") -> None:
        """Create or update a Channel node."""
        with self.get_session() as session:
            session.run(
                """MERGE (c:Channel {channel_id: $channel_id})
                   SET c.name = $name, c.url = $url, c.category = $category""",
                channel_id=channel_id, name=name, url=url, category=category,
            )

    @with_retry("neo4j_query")
    def upsert_video(self, video_id: str, title: str, channel_id: str,
                     upload_date: str = "", duration: int = 0) -> None:
        """Create or update a Video node and link to its Channel."""
        with self.get_session() as session:
            session.run(
                """MERGE (v:Video {video_id: $video_id})
                   SET v.title = $title, v.upload_date = $upload_date,
                       v.duration = $duration
                    WITH v
                   MERGE (c:Channel {channel_id: $channel_id})
                   MERGE (c)-[:PUBLISHED]->(v)""",
                video_id=video_id, title=title, channel_id=channel_id,
                upload_date=upload_date, duration=duration,
            )

    @with_retry("neo4j_query")
    def upsert_guest(self, canonical_name: str, entity_type: str = "PERSON") -> None:
        """Create or update a Guest node."""
        with self.get_session() as session:
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
        with self.get_session() as session:
            session.run(
                "MERGE (t:Topic {name: $name})",
                name=topic_name.lower().strip(),
            )

    @with_retry("neo4j_query")
    def batch_upsert_videos(self, videos: list[dict]) -> None:
        """Batch upsert multiple Video nodes and link to their Channels."""
        with self.get_session() as session:
            session.run(
                """UNWIND $videos AS v_data
                   MERGE (v:Video {video_id: v_data.video_id})
                   SET v.title = v_data.title, v.upload_date = v_data.upload_date,
                       v.duration = v_data.duration
                    WITH v, v_data
                   MERGE (c:Channel {channel_id: v_data.channel_id})
                   MERGE (c)-[:PUBLISHED]->(v)""",
                videos=videos,
            )

    @with_retry("neo4j_query")
    def batch_link_topics(self, links: list[dict]) -> None:
        """Batch create DISCUSSES relationships between Videos and Topics."""
        with self.get_session() as session:
            session.run(
                """UNWIND $links AS link
                   MATCH (v:Video {video_id: link.video_id})
                   MERGE (t:Topic {name: link.topic_name})
                   MERGE (v)-[r:DISCUSSES]->(t)
                   SET r.relevance = link.relevance""",
                links=links,
            )

    # -------------------------------------------------------------------
    # Relationship Operations
    # -------------------------------------------------------------------

    @with_retry("neo4j_query")
    def link_guest_to_video(self, guest_name: str, video_id: str,
                            timestamp: float = 0.0, context: str = "") -> None:
        """Create APPEARED_IN relationship between Guest and Video."""
        with self.get_session() as session:
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
        with self.get_session() as session:
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
        with self.get_session() as session:
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
        with self.get_session() as session:
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
    def upsert_claim(self, text: str, speaker: str, video_id: str,
                     topic: str = "", claim_id: str = "") -> None:
        """Create a Claim node with ASSERTED, SOURCED_FROM, and ABOUT relationships."""
        with self.get_session() as session:
            session.run(
                """MERGE (cl:Claim {text: $text})
                   SET cl.speaker = $speaker, cl.claim_id = $claim_id
                   WITH cl
                   MATCH (v:Video {video_id: $video_id})
                   MERGE (cl)-[:SOURCED_FROM]->(v)
                   WITH cl
                   OPTIONAL MATCH (g:Guest {canonical_name: $speaker})
                   FOREACH (_ IN CASE WHEN g IS NOT NULL THEN [1] ELSE [] END |
                       MERGE (g)-[:ASSERTED]->(cl)
                   )""",
                text=text[:1000], speaker=speaker, video_id=video_id, claim_id=claim_id,
            )
            # Link to topic if provided
            if topic:
                session.run(
                    """MATCH (cl:Claim {text: $text})
                       MERGE (t:Topic {name: $topic})
                       MERGE (cl)-[:ABOUT]->(t)""",
                    text=text[:1000], topic=topic.lower().strip(),
                )

    @with_retry("neo4j_query")
    def delete_video_nodes(self, video_id: str) -> dict:
        """Delete a Video node and its private relationships (Claims).
        
        Preserves shared Guest and Topic nodes unless they become 
        completely orphaned (handled by separate cleanup if needed).
        """
        with self.get_session() as session:
            # Delete claims sourced from this video AND the video itself
            result = session.run(
                """MATCH (v:Video {video_id: $video_id})
                   OPTIONAL MATCH (cl:Claim)-[:SOURCED_FROM]->(v)
                   DETACH DELETE cl, v
                   RETURN count(v) as video_deleted, count(cl) as claims_deleted""",
                video_id=video_id
            )
            summary = result.single()
            return {
                "video_deleted": summary["video_deleted"] > 0,
                "claims_deleted": summary["claims_deleted"]
            }

    @with_retry("neo4j_query")
    def delete_guest(self, canonical_name: str) -> bool:
        """Fully remove a guest and their private relationships from the graph.
        
        Used for purging noise entities detected during sanitization.
        """
        with self.get_session() as session:
            result = session.run(
                "MATCH (g:Guest {canonical_name: $name}) DETACH DELETE g RETURN count(g) as count",
                name=canonical_name
            )
            return result.single()["count"] > 0

    @with_retry("neo4j_query")
    def merge_guests(self, survivor_name: str, mergee_names: list[str]) -> bool:
        """Consolidate multiple Guest nodes into one using APOC.
        
        Redirects all relationships (APPEARED_IN, EXPERT_ON, ASSERTED) 
        and merges properties like mention_count.
        """
        if not mergee_names:
            return False
        with self.get_session() as session:
            # 1. Ensure survival node exists
            session.run("MERGE (g:Guest {canonical_name: $name})", name=survivor_name)
            
            # 2. Use APOC to merge nodes and relationships (if available)
            # properties: 'overwrite' means take from the last node in the list (the survivor)
            # mention_count: 'combine' sums them up
            
            # Check for APOC availability
            apoc_check = session.run("RETURN apoc.version() as version").single()
            if not apoc_check:
                logger.warning("APOC plugin not detected. Falling back to basic property merge.")
                # Fallback: simple property copy for mention_count sum
                session.run(
                    """
                    MATCH (s:Guest {canonical_name: $survivor})
                    MATCH (m:Guest) WHERE m.canonical_name IN $mergees AND m <> s
                    SET s.mention_count = s.mention_count + m.mention_count
                    WITH s, m
                    DETACH DELETE m
                    """,
                    survivor=survivor_name, mergees=mergee_names
                )
                return True

            session.run(
                """
                MATCH (s:Guest {canonical_name: $survivor})
                MATCH (m:Guest) WHERE m.canonical_name IN $mergees AND m <> s
                WITH s, collect(m) as nodes
                WHERE size(nodes) > 0
                CALL apoc.refactor.mergeNodes(nodes + s, {
                    properties: {
                        canonical_name: 'overwrite',
                        mention_count: 'combine',
                        last_seen: 'max',
                        first_seen: 'min',
                        entity_type: 'discard'
                    },
                    mergeRels: true
                }) YIELD node
                RETURN count(node) as count
                """,
                survivor=survivor_name,
                mergees=mergee_names
            )
            return True

    # -------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------

    @with_retry("neo4j_query")
    def get_guest_appearances(self, guest_name: str) -> list[dict]:
        """Get all videos where a guest appeared, across channels."""
        with self.get_session() as session:
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
        with self.get_session() as session:
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
        with self.get_session() as session:
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
        
        with self.get_session() as session:
            for label in allowed_labels:
                # Defensively validate label even if hardcoded
                if label not in allowed_labels:
                    continue
                result = session.run(f"MATCH (n:{label}) RETURN COUNT(n) AS count")
                stats[label.lower() + "_nodes"] = result.single()["count"]

            result = session.run("MATCH ()-[r]->() RETURN COUNT(r) AS count")
            stats["total_relationships"] = result.single()["count"]

        return stats

    @with_retry("neo4j_query")
    def get_central_authorities(self, label: str = "Channel", limit: int = 10) -> list[dict]:
        """Find central nodes (Channels/Guests) using degree centrality as a proxy for authority."""
        with self.get_session() as session:
            # For Channels, we measure incoming 'PUBLISHED' and outgoing 'DISCUSSES' via Videos
            if label == "Channel":
                result = session.run(
                    """MATCH (c:Channel)
                       OPTIONAL MATCH (c)-[:PUBLISHED]->(v:Video)-[:DISCUSSES]->(t:Topic)
                       RETURN c.name AS name, count(DISTINCT t) AS authority_score
                       ORDER BY authority_score DESC
                       LIMIT $limit""",
                    limit=limit
                )
            else:
                result = session.run(
                    f"""MATCH (n:{label})
                       OPTIONAL MATCH (n)-[r]-()
                       RETURN COALESCE(n.name, n.canonical_name) AS name, count(r) AS authority_score
                       ORDER BY authority_score DESC
                       LIMIT $limit""",
                    limit=limit
                )
            return [dict(record) for record in result]

    @with_retry("neo4j_query")
    def get_echo_chambers(self, limit: int = 5) -> list[dict]:
        """Identify clusters of channels that share a high volume of topics."""
        with self.get_session() as session:
            result = session.run(
                """MATCH (c1:Channel)-[:PUBLISHED]->(v1:Video)-[:DISCUSSES]->(t:Topic)
                          <-[:DISCUSSES]-(v2:Video)<-[:PUBLISHED]-(c2:Channel)
                   WHERE id(c1) < id(c2)
                   WITH c1, c2, count(DISTINCT t) AS shared_topics
                   WHERE shared_topics > 2
                   RETURN c1.name AS channel_a, c2.name AS channel_b, shared_topics
                   ORDER BY shared_topics DESC
                   LIMIT $limit""",
                limit=limit
            )
            return [dict(record) for record in result]

    @with_retry("neo4j_query")
    def get_contradiction_matrix(self, topic: str = "") -> list[dict]:
        """Find topics with CONTRADICTION relationship types between sources."""
        query = """
            MATCH (t1:Topic)-[r:RELATED_TO {relationship_type: 'CONTRADICTION'}]-(t2:Topic)
            RETURN t1.name AS topic_a, t2.name AS topic_b, r.co_occurrence AS intensity
            ORDER BY intensity DESC
        """
        if topic:
            query = """
                MATCH (t1:Topic {name: $topic})-[r:RELATED_TO {relationship_type: 'CONTRADICTION'}]-(t2:Topic)
                RETURN t1.name AS topic_a, t2.name AS topic_b, r.co_occurrence AS intensity
                ORDER BY intensity DESC
            """
        with self.get_session() as session:
            result = session.run(query, topic=topic.lower().strip())
            return [dict(record) for record in result]

    @with_retry("neo4j_query")
    def get_topic_authorities(self, topic: str, limit: int = 5) -> list[dict]:
        """Channels + guests ranked by topic authority."""
        query = """
        MATCH (c:Channel)-[:PUBLISHED]->(v:Video)-[r:DISCUSSES]->(t:Topic)
        WHERE t.name CONTAINS $topic
        RETURN c.name AS name, 'Channel' AS type, 
               count(v) AS mentions, avg(r.relevance) AS avg_relevance
        ORDER BY mentions DESC LIMIT $limit
        UNION
        MATCH (g:Guest)-[:EXPERT_ON]->(t:Topic)
        WHERE t.name CONTAINS $topic
        RETURN g.canonical_name AS name, 'Guest' AS type,
               g.mention_count AS mentions, 0.0 AS avg_relevance
        ORDER BY mentions DESC LIMIT $limit
        """
        with self.get_session() as session:
            result = session.run(query, topic=topic.lower().strip(), limit=limit)
            return [dict(record) for record in result]

    @with_retry("neo4j_query")
    def get_topic_taxonomy_context(self, topic: str) -> dict:
        """Leverages the SUBTOPIC_OF edges to find parents and children."""
        query = """
        MATCH (t:Topic) WHERE t.name = $topic
        OPTIONAL MATCH (t)-[:SUBTOPIC_OF]->(parent:Topic)
        OPTIONAL MATCH (child:Topic)-[:SUBTOPIC_OF]->(t)
        RETURN parent.name AS parent_topic, collect(child.name) AS subtopics
        """
        with self.get_session() as session:
            result = session.run(query, topic=topic.lower().strip())
            record = result.single()
            if record:
                return {
                    "parent_topic": record["parent_topic"],
                    "subtopics": record["subtopics"]
                }
            return {"parent_topic": None, "subtopics": []}
