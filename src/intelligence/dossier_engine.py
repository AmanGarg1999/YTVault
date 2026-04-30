"""
Dossier Engine for knowledgeVault-YT.

Compiles multi-dimensional topic reports combining quantitative 
timeline data, graph-based authority scoring, consensus analysis, 
and contradiction matrices.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from src.intelligence.analysis_engine import AnalysisEngine
from src.storage.sqlite_store import SQLiteStore
from src.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

class DossierEngine:
    """Orchestrates the generation of comprehensive topic dossiers."""

    def __init__(self, db: SQLiteStore, graph: GraphStore, analysis: AnalysisEngine):
        self.db = db
        self.graph = graph
        self.analysis = analysis

    def generate_topic_dossier(self, topic: str) -> dict:
        """Compile a full intelligence dossier for a specific topic."""
        logger.info(f"Generating comprehensive dossier for topic: {topic}")
        
        # 1. Quantitative Timeline (Phase 1)
        velocity_data = self.analysis.get_topic_velocity(topic)
        sentiment_summary = self.analysis.get_topic_sentiment_summary(topic)
        
        # 2. Graph Insights (Phase 2)
        # Find top authorities for this topic (channels discussing it most)
        try:
            authorities = self.graph.run_query(
                """MATCH (c:Channel)-[:PUBLISHED]->(v:Video)-[r:DISCUSSES]->(t:Topic {name: $topic})
                   RETURN c.name AS name, count(v) AS mentions, avg(r.relevance) AS avg_relevance
                   ORDER BY mentions DESC, avg_relevance DESC
                   LIMIT 5""",
                topic=topic.lower().strip()
            )
        except Exception as e:
            logger.warning(f"Failed to fetch authorities for dossier: {e}")
            authorities = []
        
        # Find contradictions specifically for this topic
        contradictions = self.graph.get_contradiction_matrix(topic)
        
        # 3. Consensus & Narrative Analysis
        # Fetch a sample of claims to determine stance
        claims = self.db.search_claims(topic, limit=20)
        stance_analysis = self.analysis.analyze_claim_stances(topic, claims)
        
        # 4. Compile the report structure
        dossier = {
            "metadata": {
                "topic": topic,
                "generated_at": datetime.now().isoformat(),
                "version": "1.0"
            },
            "executive_summary": stance_analysis.get("prevailing_narrative", "No summary available."),
            "quantitative_intelligence": {
                "total_mentions": velocity_data.get("total_mentions", 0),
                "timeline": velocity_data.get("timeline", []),
                "average_sentiment": sentiment_summary.get("average_sentiment", 0.0),
                "sentiment_label": sentiment_summary.get("label", "Neutral")
            },
            "authority_matrix": authorities,
            "contradictions": contradictions,
            "stance_analysis": stance_analysis,
            "sources": [
                {
                    "video_id": c.video_id,
                    "claim": c.claim_text,
                    "speaker": c.speaker
                } for c in claims[:10]
            ]
        }
        
        return dossier

    def format_dossier_markdown(self, dossier: dict) -> str:
        """Format the dossier dict into a beautiful Markdown report."""
        topic = dossier["metadata"]["topic"]
        q = dossier["quantitative_intelligence"]
        s = dossier["stance_analysis"]
        
        lines = [
            f"# 📂 Intelligence Dossier: {topic.upper()}",
            f"**Generated on:** {dossier['metadata']['generated_at']}\n",
            "---",
            "## 📝 Executive Summary",
            dossier["executive_summary"],
            "\n---",
            "## 📈 Quantitative Insights",
            f"- **Total Mentions in Vault:** {q['total_mentions']}",
            f"- **Aggregate Sentiment:** {q['sentiment_label']} ({q['average_sentiment']:.2f})",
            f"- **Narrative Stance:** {s['stance']}",
            f"- **Consensus Score:** {s['consensus_score'] * 100:.0f}%\n",
            "### 📅 Mentions Timeline",
            "| Date | Mentions |",
            "|---|---|",
        ]
        
        for entry in q["timeline"][-10:]: # Show last 10 dates
            lines.append(f"| {entry['date']} | {entry['mentions']} |")
            
        lines.append("\n---")
        lines.append("## 🏆 Authority Matrix (Top Channels)")
        lines.append("| Channel | Mentions | Avg. Relevance |")
        lines.append("|---|---|---|")
        for auth in dossier["authority_matrix"]:
            lines.append(f"| {auth['name']} | {auth['mentions']} | {auth['avg_relevance']:.2f} |")
            
        lines.append("\n---")
        lines.append("## ⚖️ Contradiction & Conflict Analysis")
        if dossier["contradictions"]:
            for con in dossier["contradictions"]:
                lines.append(f"- **Conflict with {con['topic_b']}**: Intensity {con['intensity']}")
        else:
            lines.append("_No direct topical contradictions detected in the graph._")
            
        lines.append("\n---")
        lines.append("## 📑 Supporting Evidence (Sample Claims)")
        for src in dossier["sources"]:
            lines.append(f"- **{src['speaker']}**: \"{src['claim']}\" ([View Source](https://www.youtube.com/watch?v={src['video_id']}))")
            
        lines.append(f"\n---\n*Generated by KnowledgeVault-YT Dossier Engine*")
        return "\n".join(lines)
