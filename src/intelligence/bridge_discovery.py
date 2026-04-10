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
        Identify pairs of topics from different categories to find cross-niche synergies.
        """
        # 1. Get topics grouped by channel category
        query = """
        SELECT 
            c.category,
            json_extract(t.value, '$.name') as topic_name
        FROM video_summaries vs
        JOIN videos v ON vs.video_id = v.video_id
        JOIN channels c ON v.channel_id = c.channel_id,
        json_each(vs.topics_json) as t
        WHERE c.category IS NOT NULL AND c.category != 'UNCLASSIFIED'
        """
        rows = self.db.conn.execute(query).fetchall()
        
        if len(rows) < 2:
            logger.warning("Not enough categorized topics to find bridges.")
            return []

        # Organize by category
        cat_map = {}
        for row in rows:
            cat = row["category"]
            topic = row["topic_name"]
            if cat not in cat_map:
                cat_map[cat] = set()
            cat_map[cat].add(topic)

        categories = list(cat_map.keys())
        if len(categories) < 2:
            logger.warning("Topics found but all are in the same category.")
            # Fallback to random if only one category exists
            return self.find_bridges_for_topics(list(rows[0].keys()), sample_size)

        discovered = []
        pairs_attempted = set()

        # 2. Pick pairs from DIFFERENT categories
        for _ in range(sample_size * 2):  # Try more than we need in case LLM fails
            if len(discovered) >= sample_size:
                break
                
            cat_a, cat_b = random.sample(categories, 2)
            topic_a = random.choice(list(cat_map[cat_a]))
            topic_b = random.choice(list(cat_map[cat_b]))
            
            pair_key = tuple(sorted([topic_a, topic_b]))
            if pair_key in pairs_attempted:
                continue
            pairs_attempted.add(pair_key)

            logger.info(f"Attempting bridge: [{cat_a}] {topic_a} <-> [{cat_b}] {topic_b}")
            bridge = self._find_connection(topic_a, topic_b)
            if bridge:
                self.db.insert_thematic_bridge(bridge)
                discovered.append(bridge)

        return discovered[:sample_size]

    def find_bridges_for_topics(self, topic_list: List[str], sample_size: int = 3) -> List[ThematicBridge]:
        """Targeted bridge discovery for a specific set of topics."""
        if len(topic_list) < 2:
            return []
            
        discovered = []
        pairs = []
        for _ in range(sample_size):
            a, b = random.sample(topic_list, 2)
            if (a, b) not in pairs and (b, a) not in pairs:
                pairs.append((a, b))

        for topic_a, topic_b in pairs:
            bridge = self._find_connection(topic_a, topic_b)
            if bridge:
                self.db.insert_thematic_bridge(bridge)
                discovered.append(bridge)
        
        return discovered

    def _find_connection(self, topic_a: str, topic_b: str) -> Optional[ThematicBridge]:
        """Ask the LLM to find a thematic bridge between two topics."""
        import ollama
        from src.utils.llm_pool import get_llm_semaphore
        
        prompt = f"""
        Act as a "Systems Thinker" and Research Architect. Your goal is to find a "Hidden Connection" 
        or a "Thematic Bridge" between two disparate topics found in a knowledge vault.
        
        Topic A: {topic_a}
        Topic B: {topic_b}
        
        Task: 
        1. Identify a surprising synergy, non-obvious parallel, or creative intersection between these two fields.
        2. Explain how an insight from Topic A could be applied to Topic B, or vice versa.
        3. Provide a specific, "Aha!" moment insight.
        
        Format:
        SYNERGY: [One sentence describing the core connection]
        INSIGHT: [Detailed explanation of the value and application]
        """
        
        try:
            with get_llm_semaphore():
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
