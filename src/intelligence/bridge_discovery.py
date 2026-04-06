import logging
from typing import List, Tuple, Optional
import random
from src.storage.sqlite_store import SQLiteStore, ThematicBridge
from src.config import get_settings

logger = logging.getLogger(__name__)

class BridgeDiscoveryEngine:
    """Discovers 'hidden connections' between disparate topics in the vault."""

    def __init__(self, db: SQLiteStore):
        self.db = db
        self.settings = get_settings()

    def discover_bridges(self, sample_size: int = 5) -> List[ThematicBridge]:
        """
        Identify pairs of topics and ask LLM to find non-obvious synergies.
        """
        # 1. Get top topics
        # We'll just pull a diversity of topics from the DB
        all_topics = self.db.conn.execute(
            "SELECT DISTINCT json_each.value FROM video_summaries, json_each(topics_json)"
        ).fetchall()
        
        if len(all_topics) < 2:
            logger.warning("Not enough topics to find bridges.")
            return []

        topics = [t[0] for t in all_topics]
        discovered = []

        # 2. Pick random pairs to explore
        pairs = []
        for _ in range(sample_size):
            a, b = random.sample(topics, 2)
            if (a, b) not in pairs and (b, a) not in pairs:
                pairs.append((a, b))

        # 3. Use LLM to find connections
        for topic_a, topic_b in pairs:
            bridge = self._find_connection(topic_a, topic_b)
            if bridge:
                self.db.insert_thematic_bridge(bridge)
                discovered.append(bridge)

        return discovered

    def _find_connection(self, topic_a: str, topic_b: str) -> Optional[ThematicBridge]:
        """Ask the LLM to find a thematic bridge between two topics."""
        import ollama
        
        prompt = f"""
        Act as a high-level research architect. Your goal is to find a "Hidden Connection" or a "Thematic Bridge" 
        between two disparate topics found in a knowledge vault.
        
        Topic A: {topic_a}
        Topic B: {topic_b}
        
        Task: 
        1. Identify a surprising synergy, non-obvious parallel, or creative intersection between these two fields.
        2. Explain how an insight from Topic A could be applied to Topic B, or vice versa.
        3. Keep the insight concise but high-impact (2-3 sentences).
        
        Format:
        SYNERGY: [One sentence describing the core connection]
        INSIGHT: [Detailed explanation of the value]
        """
        
        try:
            response = ollama.chat(
                model=self.settings["ollama"]["triage_model"],
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.get("message", {}).get("content", "")
            
            if "SYNERGY:" in content:
                return ThematicBridge(
                    topic_a=topic_a,
                    topic_b=topic_b,
                    insight=content.strip(),
                    llm_model=self.settings["ollama"]["triage_model"]
                )
        except Exception as e:
            logger.error(f"Failed to discover bridge between {topic_a} and {topic_b}: {e}")
            
        return None
