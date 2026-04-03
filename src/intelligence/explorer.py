"""
Explorer logic for knowledgeVault-YT.

Provides high-level graph insights, multi-hop connection discovery, 
and topic-centric relationship mapping by unifying SQLite and Neo4j data.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.storage.graph_store import GraphStore
from src.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


@dataclass
class EntityNode:
    id: str
    label: str
    type: str  # 'Video', 'Guest', 'Topic', 'Channel'
    metadata: dict


@dataclass
class RelationshipEdge:
    source: str
    target: str
    type: str
    metadata: dict


class KnowledgeExplorer:
    """Orchestrates deep-dive data exploration across relational and graph stores."""

    def __init__(self, db: SQLiteStore, graph: GraphStore):
        self.db = db
        self.graph = graph

    def get_entity_connections(self, entity_id: str, entity_type: str, limit: int = 50):
        """Get a subgraph of immediate and secondary connections for a given entity."""
        nodes = []
        edges = []
        
        # 1. Fetch from Neo4j
        # We find the central node and its neighbors
        with self.graph.driver.session() as session:
            # Query central node and neighbors
            query = ""
            if entity_type == "Guest":
                query = "MATCH (n:Guest {canonical_name: $id})-[r]-(m) RETURN n, r, m LIMIT $limit"
            elif entity_type == "Topic":
                query = "MATCH (n:Topic {name: $id})-[r]-(m) RETURN n, r, m LIMIT $limit"
            elif entity_type == "Video":
                query = "MATCH (n:Video {video_id: $id})-[r]-(m) RETURN n, r, m LIMIT $limit"
            else:
                return {"nodes": [], "edges": []}

            result = session.run(query, id=entity_id, limit=limit)
            
            seen_nodes = set()
            for record in result:
                n = record["n"]
                m = record["m"]
                r = record["r"]
                
                # Add central node
                if n.id not in seen_nodes:
                    nodes.append(self._neo_node_to_node(n))
                    seen_nodes.add(n.id)
                
                # Add neighbor node
                if m.id not in seen_nodes:
                    nodes.append(self._neo_node_to_node(m))
                    seen_nodes.add(m.id)
                
                # Add relationship
                edges.append({
                    "source": n.id,
                    "target": m.id,
                    "type": r.type,
                    "metadata": dict(r)
                })

        return {"nodes": nodes, "edges": edges}

    def find_path_between_entities(self, start_id: str, start_type: str, 
                                   end_id: str, end_type: str, max_depth: int = 3):
        """Find a path (or paths) between two entities in the knowledge graph."""
        with self.graph.driver.session() as session:
            # Cypher for shortest path
            query = f"""
            MATCH (s:{start_type} {{ {self._get_id_key(start_type)}: $start_id }})
            MATCH (e:{end_type} {{ {self._get_id_key(end_type)}: $end_id }})
            MATCH p = shortestPath((s)-[*]-(e))
            WHERE length(p) <= $max_depth
            RETURN p
            """
            result = session.run(query, start_id=start_id, end_id=end_id, max_depth=max_depth)
            
            path = result.single()
            if not path:
                return None
            
            p = path["p"]
            return {
                "length": len(p),
                "nodes": [self._neo_node_to_node(n) for n in p.nodes],
                "relationships": [r.type for r in p.relationships]
            }

    def get_topic_landscape(self, topic_name: str):
        """Get all videos, guests, and related topics for a specific topic spotlight."""
        with self.graph.driver.session() as session:
            # Query for videos discusses topic
            videos_res = session.run(
                "MATCH (v:Video)-[:DISCUSSES]->(t:Topic {name: $name}) "
                "RETURN v.title AS title, v.video_id AS video_id",
                name=topic_name.lower()
            )
            # Query for guests expertise on topic
            guests_res = session.run(
                "MATCH (g:Guest)-[:EXPERT_ON]->(t:Topic {name: $name}) "
                "RETURN g.canonical_name AS canonical_name",
                name=topic_name.lower()
            )
            # Related topics
            related_res = session.run(
                "MATCH (t:Topic {name: $name})-[:RELATED_TO]-(r:Topic) "
                "RETURN r.name AS name, r.co_occurrence AS co_occurrence",
                name=topic_name.lower()
            )

            return {
                "videos": [dict(v) for v in videos_res],
                "guests": [dict(g) for g in guests_res],
                "related": [dict(r) for r in related_res]
            }

    def get_global_graph(self, limit: int = 150):
        """Fetch a broad sample of high-density connections for global exploration."""
        nodes = []
        edges = []
        with self.graph.driver.session() as session:
            # Match high-degree nodes first to get interesting connections
            query = """
            MATCH (n)-[r]-(m)
            WITH n, r, m, count(r) as degree
            ORDER BY degree DESC
            RETURN n, r, m
            LIMIT $limit
            """
            result = session.run(query, limit=limit)
            seen_nodes = set()
            for record in result:
                n, m, r = record["n"], record["m"], record["r"]
                for node in [n, m]:
                    if node.id not in seen_nodes:
                        nodes.append(self._neo_node_to_node(node))
                        seen_nodes.add(node.id)
                edges.append({
                    "source": n.id,
                    "target": m.id,
                    "type": r.type,
                    "metadata": dict(r)
                })
        return {"nodes": nodes, "edges": edges}

    def get_vault_stats(self):
        """Aggregate top topics and most active experts for the discovery sidebar."""
        stats = {"top_topics": [], "top_guests": []}
        with self.graph.driver.session() as session:
            # Top Topics by discussion count
            topics = session.run("""
                MATCH (t:Topic)<-[r:DISCUSSES]-(v:Video)
                RETURN t.name AS name, count(r) AS weight
                ORDER BY weight DESC LIMIT 10
            """)
            stats["top_topics"] = [dict(t) for t in topics]
            
            # Top Guests by appearance/expertise
            guests = session.run("""
                MATCH (g:Guest)-[r:APPEARS_IN|EXPERT_ON]->()
                RETURN g.canonical_name AS name, count(r) AS weight
                ORDER BY weight DESC LIMIT 10
            """)
            stats["top_guests"] = [dict(g) for g in guests]
            
        return stats


    def _neo_node_to_node(self, node):
        """Convert Neo4j node to simple dict for UI."""
        labels = list(node.labels)
        primary_label = labels[0] if labels else "Unknown"
        
        # ID selection for streamlit-agraph (must be string)
        # Use element_id (Neo4j 5+) or str(id) (Legacy)
        try:
            node_id = str(node.element_id)
        except (AttributeError, ValueError):
            node_id = str(node.id)
            
        # Unique business ID selection based on type
        internal_id = ""
        if "Video" in labels: internal_id = node.get("video_id", "")
        elif "Guest" in labels: internal_id = node.get("canonical_name", "")
        elif "Topic" in labels: internal_id = node.get("name", "")
        elif "Channel" in labels: internal_id = node.get("channel_id", "")
        
        return {
            "id": node_id,
            "internal_id": internal_id,
            "label": internal_id or primary_label,
            "type": primary_label,
            "metadata": dict(node)
        }

    def _get_id_key(self, label: str) -> str:
        """Map node label to its unique ID property name."""
        mapping = {
            "Video": "video_id",
            "Guest": "canonical_name",
            "Topic": "name",
            "Channel": "channel_id"
        }
        return mapping.get(label, "id")
