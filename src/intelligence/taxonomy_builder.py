"""
Hierarchical topic taxonomy builder for knowledgeVault-YT.

Queries all topics from Neo4j, uses LLM to organize them into a
parent-child hierarchy, and creates SUBTOPIC_OF relationships.
"""

import json
import logging
from typing import Optional

import ollama

from src.config import get_settings
from src.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

TAXONOMY_PROMPT = """You are a knowledge taxonomy architect. Given a list of topics extracted
from video transcripts, organize them into a hierarchical taxonomy.

Rules:
1. Group related topics under broader parent categories.
2. A topic can only have ONE parent.
3. Top-level categories should be broad domains (e.g., "technology", "science", "business").
4. Only create parent-child relationships where one topic is clearly a subtopic of another.
5. If a topic doesn't fit cleanly under any parent, leave it as a top-level topic.
6. Use the EXACT topic names provided — do not rename them.

Return a JSON array of relationships:
[{"child": "exact topic name", "parent": "exact parent topic name"}]

If no hierarchical relationships exist, return: []
"""


class TaxonomyBuilder:
    """Builds a hierarchical topic taxonomy from the knowledge graph."""

    def __init__(self, graph: GraphStore):
        self.graph = graph
        self.settings = get_settings()
        self.model = self.settings["ollama"].get(
            "deep_model", self.settings["ollama"]["triage_model"]
        )

    def build_taxonomy(self) -> int:
        """Query all topics and create SUBTOPIC_OF relationships.

        Returns:
            Number of SUBTOPIC_OF relationships created.
        """
        # Fetch all topics from Neo4j
        with self.graph.driver.session() as session:
            result = session.run(
                "MATCH (t:Topic) RETURN t.name AS name ORDER BY name"
            )
            topics = [r["name"] for r in result]

        if len(topics) < 5:
            logger.info(f"Only {len(topics)} topics — skipping taxonomy build.")
            return 0

        logger.info(f"Building taxonomy for {len(topics)} topics...")

        # Process in batches of 50 to stay within context window
        all_relationships = []
        batch_size = 50
        for i in range(0, len(topics), batch_size):
            batch = topics[i:i + batch_size]
            relationships = self._classify_batch(batch)
            all_relationships.extend(relationships)

        # Create SUBTOPIC_OF edges in Neo4j
        created = 0
        for rel in all_relationships:
            child = rel.get("child", "").lower().strip()
            parent = rel.get("parent", "").lower().strip()
            if child and parent and child != parent:
                try:
                    with self.graph.driver.session() as session:
                        session.run(
                            """MATCH (c:Topic {name: $child})
                               MATCH (p:Topic {name: $parent})
                               MERGE (c)-[:SUBTOPIC_OF]->(p)""",
                            child=child, parent=parent,
                        )
                    created += 1
                except Exception as e:
                    logger.debug(f"Failed to create taxonomy edge {child} → {parent}: {e}")

        logger.info(f"Taxonomy built: {created} SUBTOPIC_OF relationships created")
        return created

    def _classify_batch(self, topics: list[str]) -> list[dict]:
        """Send a batch of topics to LLM for hierarchical classification."""
        topic_list = "\n".join(f"- {t}" for t in topics)
        user_prompt = f"Topics to organize:\n{topic_list}"

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": TAXONOMY_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                options={"num_predict": 1000, "temperature": 0.1},
            )
            raw = response["message"]["content"].strip()

            # Parse JSON
            clean = raw
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean
                clean = clean.rsplit("```", 1)[0].strip()
            result = json.loads(clean)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)
                        and "child" in r and "parent" in r]
        except Exception as e:
            logger.warning(f"Taxonomy batch classification failed: {e}")

        return []
