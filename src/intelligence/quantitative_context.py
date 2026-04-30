"""
Quantitative context assembler for knowledgeVault-YT.

Assembles data-backed metrics from SQLite and Neo4j to ground LLM 
synthesis in quantitative evidence (Phase 1).
"""

import logging
import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.storage.sqlite_store import SQLiteStore
from src.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

@dataclass
class QuantitativeMetrics:
    """Raw metrics attached to RAGResponse for UI rendering."""
    topic_coverage: dict = field(default_factory=dict)         # video_count, channel_count, date_range
    claim_stats: dict = field(default_factory=dict)            # clusters, total_claims, avg_corroboration
    sentiment_distribution: dict = field(default_factory=dict) # positive/neutral/negative counts + avg
    authorities: list[dict] = field(default_factory=list)      # top channels/guests for this topic
    contradictions: list[dict] = field(default_factory=list)   # from get_contradiction_matrix
    taxonomy_context: dict = field(default_factory=dict)       # parent topic, subtopics
    echo_chamber_warning: str = ""                             # empty if no warning
    heatmap_boost_applied: bool = False                        # whether high-interest chunks were boosted

class QuantitativeContextAssembler:
    """Assembles quantitative intelligence for a topic to ground LLM synthesis."""

    def __init__(self, db: SQLiteStore, graph: GraphStore):
        self.db = db
        self.graph = graph

    def assemble(self, query: str, topic: str, timeout: float = 3.0) -> tuple[str, QuantitativeMetrics]:
        """Runs parallel data gathering and returns (context_string, metrics_object)."""
        metrics = QuantitativeMetrics()
        
        if not topic:
            return "", metrics

        topic_clean = topic.lower().strip()
        
        # Define tasks for parallel execution
        tasks = {
            "claim_stats": lambda: self.db.get_claim_corroboration_stats(topic_clean),
            "topic_coverage": lambda: self.db.get_topic_coverage_stats(topic_clean),
            "sentiment": lambda: self.db.get_topic_sentiment_aggregated(topic_clean),
            "authorities": lambda: self.graph.get_topic_authorities(topic_clean),
            "contradictions": lambda: self.graph.get_contradiction_matrix(topic_clean),
            "taxonomy": lambda: self.graph.get_topic_taxonomy_context(topic_clean),
        }

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_to_key = {executor.submit(fn): key for key, fn in tasks.items()}
            try:
                # Use a completion loop with a timeout for the entire set
                for future in concurrent.futures.as_completed(future_to_key, timeout=timeout):
                    key = future_to_key[future]
                    try:
                        results[key] = future.result()
                    except Exception as e:
                        logger.warning(f"Quantitative context task '{key}' failed: {e}")
                        results[key] = None
            except concurrent.futures.TimeoutError:
                logger.warning("Quantitative context assembly partially timed out.")

        # Populate metrics object
        metrics.claim_stats = results.get("claim_stats") or {}
        metrics.topic_coverage = results.get("topic_coverage") or {}
        metrics.sentiment_distribution = results.get("sentiment") or {}
        metrics.authorities = results.get("authorities") or []
        metrics.contradictions = results.get("contradictions") or []
        metrics.taxonomy_context = results.get("taxonomy") or {}

        # Echo chamber check
        if metrics.topic_coverage.get("channel_count", 0) == 1:
            metrics.echo_chamber_warning = (
                "Warning: All evidence for this topic comes from a single channel. "
                "The perspectives presented may be biased or lack cross-verification."
            )

        # Build context string for LLM
        context_blocks = []
        context_blocks.append("### QUANTITATIVE INTELLIGENCE")
        context_blocks.append("Use the following data to ground your answer and cite numbers where possible:")
        
        if metrics.topic_coverage:
            cov = metrics.topic_coverage
            context_blocks.append(
                f"- Vault Coverage: {cov.get('video_count', 0)} videos across {cov.get('channel_count', 0)} channels. "
                f"Data range: {cov.get('earliest', 'N/A')} to {cov.get('latest', 'N/A')}."
            )

        if metrics.claim_stats:
            stats = metrics.claim_stats
            context_blocks.append(
                f"- Consensus Profile: {stats.get('claim_clusters', 0)} verified claim clusters. "
                f"Average corroboration factor: {stats.get('avg_corroboration', 1.0):.2f}."
            )

        if metrics.sentiment_distribution:
            sent = metrics.sentiment_distribution
            context_blocks.append(
                f"- Sentiment Profile: {sent.get('label', 'Neutral')} (Avg Score: {sent.get('average_sentiment', 0.0):.2f})."
            )

        if metrics.authorities:
            auth_str = ", ".join([f"{a['name']} ({a['type']})" for a in metrics.authorities[:3]])
            context_blocks.append(f"- Top Topic Authorities: {auth_str}")

        if metrics.contradictions:
            context_blocks.append(f"- Note: {len(metrics.contradictions)} known contradictions detected in the vault for this topic.")

        if metrics.taxonomy_context.get("parent_topic"):
            context_blocks.append(f"- Hierarchical Context: Part of the broader '{metrics.taxonomy_context['parent_topic']}' domain.")

        if metrics.echo_chamber_warning:
            context_blocks.append(f"- RISK ADVISORY: {metrics.echo_chamber_warning}")

        return "\n".join(context_blocks), metrics
