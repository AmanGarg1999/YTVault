"""
Epiphany Engine for knowledgeVault-YT.

Automates the discovery of cross-channel insights by running scheduled
or triggered analyses over the knowledge graph and generating RAG briefings
with relationship classification (Consensus, Contradiction, Complementary, Evolution).
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import ollama

from src.config import get_settings, load_prompt
from src.intelligence.rag_engine import RAGEngine
from src.storage.graph_store import GraphStore
from src.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


@dataclass
class InsightBriefing:
    """A generated daily/weekly briefing of new connections."""
    topic: str
    channels_involved: list[str]
    summary_markdown: str
    confidence_score: float
    relationship_type: str = ""  # CONSENSUS, CONTRADICTION, COMPLEMENTARY, EVOLUTION
    key_differences: list[str] = field(default_factory=list)
    key_agreements: list[str] = field(default_factory=list)
    insight: str = ""


class EpiphanyEngine:
    """Generates automated insights with relationship classification."""

    def __init__(self, db: SQLiteStore, graph: GraphStore, rag: RAGEngine):
        self.db = db
        self.graph = graph
        self.rag = rag
        self.settings = get_settings()
        self.deep_model = self.settings["ollama"].get(
            "deep_model", self.settings["ollama"]["triage_model"]
        )
        try:
            self.briefing_prompt = load_prompt("epiphany_briefing")
        except FileNotFoundError:
            self.briefing_prompt = ""

    def generate_daily_briefing(self) -> list[InsightBriefing]:
        """Find top cross-channel topics, classify relationships, generate summaries."""
        logger.info("Starting Epiphany Engine briefing generation...")

        top_topics = self.graph.get_cross_channel_topics(limit=5)
        if not top_topics:
            logger.info("No cross-channel topics found yet.")
            return []

        briefings = []
        for t in top_topics:
            topic_name = t["topic"]
            c1 = t["channel_1"]
            c2 = t["channel_2"]

            logger.info(f"Generating insight for topic '{topic_name}'...")
            try:
                # Step 1: Retrieve context from both channels
                response = self.rag.query(
                    f"Compare and contrast what channel:{c1} and channel:{c2} "
                    f"have said regarding topic:\"{topic_name}\". What are the key takeaways?"
                )

                # Step 2: Classify the relationship type
                classification = self._classify_relationship(
                    topic_name, c1, c2, response.answer
                )

                rel_type = classification.get("relationship_type", "COMPLEMENTARY")

                # Step 3: Store classification on graph edge
                self.graph.link_related_topics(
                    topic_name, topic_name,
                    co_occurrence=0,
                    relationship_type=rel_type,
                )

                briefings.append(InsightBriefing(
                    topic=topic_name,
                    channels_involved=[c1, c2],
                    summary_markdown=classification.get("summary", response.answer),
                    confidence_score=response.confidence.overall if response.confidence else 0.0,
                    relationship_type=rel_type,
                    key_differences=classification.get("key_differences", []),
                    key_agreements=classification.get("key_agreements", []),
                    insight=classification.get("insight", ""),
                ))
            except Exception as e:
                logger.error(f"Failed to generate insight for '{topic_name}': {e}")

        return briefings

    def _classify_relationship(
        self, topic: str, channel_1: str, channel_2: str, rag_answer: str
    ) -> dict:
        """Classify the cross-channel relationship using the deep model."""
        if not self.briefing_prompt:
            return {"relationship_type": "COMPLEMENTARY", "summary": rag_answer}

        user_prompt = (
            f"Topic: {topic}\n"
            f"Channel 1: {channel_1}\n"
            f"Channel 2: {channel_2}\n\n"
            f"Analysis from RAG:\n{rag_answer[:3000]}"
        )

        from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
        pool = LLMPool()
        task = LLMTask(
            task_id=f"epiphany_{topic[:20]}",
            fn=ollama.chat,
            kwargs={
                "model": self.deep_model,
                "messages": [
                    {"role": "system", "content": self.briefing_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"num_predict": 800, "temperature": 0.1},
            },
            priority=LLMPriority.MEDIUM
        )
        
        try:
            future = pool.submit(task)
            response = future.result(timeout=180)
            raw = response["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                raw = raw.rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Relationship classification failed: {e}")
            return {"relationship_type": "COMPLEMENTARY", "summary": rag_answer}
