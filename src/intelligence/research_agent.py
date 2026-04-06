import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.storage.sqlite_store import SQLiteStore, ResearchReport
from src.config import get_settings
import ollama

logger = logging.getLogger(__name__)

class ResearchAgent:
    """Autonomous agent that synthesizes vault knowledge into formal reports."""

    def __init__(self, db: SQLiteStore):
        self.db = db
        self.settings = get_settings()
        self.output_dir = Path("/app/data/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, query: str) -> Optional[ResearchReport]:
        """
        Conduct a deep-search and synthesize a white paper.
        """
        logger.info(f"Research Agent starting query: {query}")
        
        # 1. Retrieval Phase: Find relevant content
        # We search summaries for the query
        search_results = self.db.conn.execute(
            """SELECT v.video_id, v.title, vs.summary_text, vs.topics_json, vs.takeaways_json
               FROM video_summaries vs
               JOIN videos v ON vs.video_id = v.video_id
               WHERE vs.summary_text LIKE ? OR vs.topics_json LIKE ?
               LIMIT 10""",
            (f"%{query}%", f"%{query}%")
        ).fetchall()
        
        if not search_results:
            logger.warning(f"No relevant content found for query: {query}")
            return None

        # 2. Context Assembly
        context_blocks = []
        sources = []
        for row in search_results:
            context_blocks.append(f"SOURCE: {row['title']}\nSUMMARY: {row['summary_text']}\nTAKEAWAYS: {row['takeaways_json']}")
            sources.append({"video_id": row["video_id"], "title": row["title"]})

        context_str = "\n\n---\n\n".join(context_blocks)

        # 3. Synthesis Phase: LLM Writing
        paper_content = self._synthesize_paper(query, context_str)
        
        if not paper_content:
            return None

        # 4. Persistence
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join([c if c.isalnum() else "_" for c in query[:30]])
        filename = f"report_{safe_query}_{timestamp}.md"
        file_path = self.output_dir / filename
        
        with open(file_path, "w") as f:
            f.write(paper_content)

        report = ResearchReport(
            query=query,
            title=f"Research: {query}",
            file_path=str(file_path),
            summary=paper_content[:500] + "...",
            sources_json=json.dumps(sources)
        )
        
        self.db.insert_research_report(report)
        return report

    def _synthesize_paper(self, query: str, context: str) -> Optional[str]:
        """Synthesize the collected context into a structured white paper."""
        prompt = f"""
        Act as a Senior Research Analyst. You are writing a "Deep Intelligence Brief" based on a private knowledge vault.
        
        RESEARCH TOPIC: {query}
        
        Context from Vault Content:
        {context}
        
        Requirements for the White Paper:
        1. Use a formal, professional tone.
        2. STRUCTURE: 
           - EXECUTIVE SUMMARY
           - KEY THEMES & INSIGHTS
           - CONTRASTING PERSPECTIVES (If any)
           - ACTIONABLE RECOMMENDATIONS
           - CONCLUSION
        3. CITE YOUR SOURCES: Whenever mentioning an insight, use [Source Name] style.
        4. Focus on SYNTHESIS: Don't just repeat the sources; connect the dots between them.
        
        OUTPUT FORMAT: Markdown.
        """
        
        from src.utils.llm_pool import get_llm_semaphore
        try:
            with get_llm_semaphore():
                response = ollama.chat(
                    model=self.settings["ollama"]["deep_model"],
                    messages=[{"role": "user", "content": prompt}]
                )
            content = response.get("message", {}).get("content", "")
            return content
        except Exception as e:
            logger.error(f"Synthesis failed for query '{query}': {e}")
            return None
