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
        """Compile a full 8-section intelligence dossier for a specific topic."""
        logger.info(f"Generating comprehensive dossier for topic: {topic}")
        
        # 1. Quantitative Timeline & Velocity
        velocity_data = self.analysis.get_topic_velocity(topic)
        
        # 2. Expert Network & Authority Matrix
        authorities = self.graph.get_topic_authorities(topic)
        
        # 3. Knowledge Taxonomy
        taxonomy = self.graph.get_topic_taxonomy_context(topic)
        
        # 4. Sentiment & Tone Distribution
        sentiment = self.analysis.get_topic_sentiment_summary(topic)
        
        # 5. Contradiction Matrix
        contradictions = self.graph.get_contradiction_matrix(topic)
        
        # 6. Consensus & Narrative Pillars
        claims = self.db.search_claims(topic, limit=30)
        stance = self.analysis.analyze_claim_stances(topic, claims)
        
        # 7. Coverage Gap Analysis
        from src.intelligence.analysis_engine import CoverageAnalyzer
        coverage_analyzer = CoverageAnalyzer(self.db)
        coverage = coverage_analyzer.analyze_topic_coverage(topic)
        suggestions = coverage_analyzer.suggest_ingestions(topic)
        
        # 8. Compile the report structure
        dossier = {
            "metadata": {
                "topic": topic,
                "generated_at": datetime.now().isoformat(),
                "version": "2.0"
            },
            "sections": {
                "executive_summary": stance.get("prevailing_narrative", "No summary available."),
                "quantitative_timeline": velocity_data,
                "authority_matrix": authorities,
                "taxonomy": taxonomy,
                "sentiment": sentiment,
                "contradictions": contradictions,
                "narrative_pillars": stance,
                "coverage_gaps": {
                    "analysis": coverage,
                    "suggestions": suggestions
                }
            },
            "raw_sources": [
                {
                    "video_id": c.video_id,
                    "claim": c.claim_text,
                    "speaker": c.speaker
                } for c in claims[:15]
            ]
        }
        
        return dossier

    def format_dossier_markdown(self, dossier: dict) -> str:
        """Format the dossier dict into a professional 8-section Markdown report."""
        m = dossier["metadata"]
        s = dossier["sections"]
        topic = m["topic"]
        
        lines = [
            f"# 📜 Intelligence Dossier: {topic.upper()}",
            f"**Generated:** {datetime.fromisoformat(m['generated_at']).strftime('%Y-%m-%d %H:%M')}",
            f"**Intelligence Version:** {m['version']}\n",
            "---",
            "## 1. 📝 Executive Summary",
            s["executive_summary"],
            "\n---",
            "## 2. 📈 Quantitative Timeline",
            f"**Mention Velocity:** `{s['quantitative_timeline']['velocity']:.2f}x` ({s['quantitative_timeline']['trend'].upper()})",
            f"**Total Vault Mentions:** {s['quantitative_timeline']['total_mentions']}",
            "\n*Timeline markers found in vault metadata across multiple videos.*",
            "\n---",
            "## 3. 🎓 Expert Network (Authority Matrix)",
        ]
        
        if s["authority_matrix"]:
            lines.append("| Entity | Type | Relevance |")
            lines.append("|--------|------|-----------|")
            for auth in s["authority_matrix"][:5]:
                lines.append(f"| {auth['name']} | {auth['type']} | {auth.get('relevance', auth.get('avg_relevance', 0.0)):.2f} |")
        else:
            lines.append("_No specialized authorities identified for this specific topic._")
            
        lines.extend([
            "\n---",
            "## 4. 🕸 Knowledge Taxonomy",
            f"**Parent Topic:** `{s['taxonomy'].get('parent_topic', 'Root')}`",
            f"**Subtopics:** {', '.join(s['taxonomy'].get('subtopics', [])) or 'None detected'}",
            "\n---",
            "## 5. 🎭 Sentiment & Tone Distribution",
            f"**Overall Sentiment:** {s['sentiment'].get('label', 'Neutral')} ({s['sentiment'].get('average_sentiment', 0.0):.2f})",
            "\n*Based on aggregated analysis of transcript segments and claim-level tone.*",
            "\n---",
            "## 6. ⚖️ Contradiction Matrix",
        ])
        
        if s["contradictions"]:
            lines.append("| Subject A | Subject B | Intensity | Status |")
            lines.append("|-----------|-----------|-----------|--------|")
            for c in s["contradictions"][:5]:
                lines.append(f"| {c['topic_a']} | {c['topic_b']} | {c['intensity']:.2f} | CONFLICT |")
        else:
            lines.append("_No direct contradictions detected in current vault data._")
            
        lines.extend([
            "\n---",
            "## 7. 🏛 Consensus & Narrative Pillars",
            f"**Narrative Stance:** {s['narrative_pillars'].get('stance', 'Balanced')}",
            f"**Consensus Score:** `{s['narrative_pillars'].get('consensus_score', 0.0) * 100:.1f}%`",
            f"\n**Core Pillars:**\n{s['narrative_pillars'].get('prevailing_narrative', 'N/A')}",
            "\n---",
            "## 8. 🔍 Coverage Gaps & Suggested Ingestions",
            f"**Vault Depth Score:** `{s['coverage_gaps']['analysis']['score'] * 100:.1f}%` ({s['coverage_gaps']['analysis']['status']})",
        ])
        
        if s["coverage_gaps"]["analysis"]["gaps"]:
            lines.append("\n**Identified Gaps:**")
            for gap in s["coverage_gaps"]["analysis"]["gaps"]:
                lines.append(f"- ⚠️ {gap}")
                
        if s["coverage_gaps"]["suggestions"]:
            lines.append("\n**Recommended Next Actions:**")
            for sug in s["coverage_gaps"]["suggestions"]:
                lines.append(f"- [ ] {sug}")
        
        lines.extend([
            "\n---",
            "## 📑 Referenced Sources (Vault Sample)",
        ])
        
        for i, src in enumerate(dossier["raw_sources"][:10], 1):
            lines.append(f"{i}. **{src['speaker'] or 'Unknown'}**: \"{src['claim']}\" (Video: {src['video_id']})")
            
        return "\n".join(lines)
