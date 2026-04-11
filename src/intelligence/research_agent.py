import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.storage.sqlite_store import SQLiteStore, ResearchReport
from src.storage.vector_store import VectorStore
from src.intelligence.rag_engine import RAGEngine, Citation
from src.config import get_settings, DATA_DIR
import ollama

logger = logging.getLogger(__name__)

class ResearchAgent:
    """Autonomous agent that synthesizes vault knowledge into formal reports."""

    def __init__(self, db: SQLiteStore):
        self.db = db
        self.settings = get_settings()
        self.vs = VectorStore()
        self.rag = RAGEngine(self.db, self.vs)
        self.output_dir = DATA_DIR / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, query: str) -> Optional[ResearchReport]:
        """
        Conduct a deep-search and synthesize a white paper with Peer Review.
        """
        logger.info(f"Research Agent starting query: {query}")
        
        # 1. Retrieval Phase: Semantic Search & RAG
        summary_results = []
        if self.vs.is_ready():
            summary_results = self.vs.search_summaries(query, top_k=5)
        else:
            logger.warning("VectorStore not ready, skipping semantic search for summaries.")
            
        rag_response = self.rag.query(query)
        
        if not summary_results and not rag_response.citations:
            logger.warning(f"No relevant content found for query: {query}")
            return None

        # 2. Context Assembly with Expanded Metadata
        context_blocks = []
        sources = []
        
        # Add summary context
        if summary_results:
            context_blocks.append("### THEMATIC CONTEXT (Summaries)")
            for res in summary_results:
                video = self.db.get_video(res["video_id"])
                if video:
                    context_blocks.append(f"SOURCE: {video.title}\nSUMMARY: {res['text']}")
                    sources.append({"video_id": res["video_id"], "title": video.title})

        # Add RAG evidence context
        if rag_response.citations:
            context_blocks.append("### GRANULAR EVIDENCE (Transcript Chunks)")
            for cit in rag_response.citations:
                # Fetch full video stats for metadata expansion
                video = self.db.get_video(cit.video_id)
                stats_info = ""
                
                # Fetch sentiment for this chunk if available
                sentiment = self.db.execute(
                    "SELECT label, score FROM video_sentiment WHERE video_id = ? AND (chunk_id = ? OR chunk_id IS NULL) LIMIT 1",
                    (cit.video_id, cit.chunk_id)
                ).fetchone()
                sentiment_info = f", Sentiment: {sentiment['label']} ({sentiment['score']:.2f})" if sentiment else ""
                
                context_blocks.append(
                    f"SOURCE: {cit.video_title} (Channel: {cit.channel_name}, "
                    f"Timestamp: {cit.timestamp_str}{stats_info}{sentiment_info})\n"
                    f"EXCERPT: {cit.text_excerpt}"
                )
                if not any(s["video_id"] == cit.video_id for s in sources):
                    sources.append({"video_id": cit.video_id, "title": cit.video_title})

        context_str = "\n\n---\n\n".join(context_blocks)

        # 3. Synthesis Phase: LLM Writing
        paper_content = self._synthesize_paper(query, context_str)
        
        if not paper_content:
            return None

        # 4. Peer Review Phase (Hallucination Guardrail)
        review_note = self._peer_review(query, paper_content, context_str)
        if review_note:
            paper_content += f"\n\n---\n**PEER REVIEWER NOTE:**\n{review_note}\n"

        # 5. Append Bibliography (Verifiable Citations)
        paper_content += "\n\n## BIBLIOGRAPHY & VERIFICATION\n"
        bib_items = []
        for i, cit in enumerate(rag_response.citations if rag_response.citations else []):
            source_num = i + 1
            bib_items.append(
                f"[^{source_num}]: {cit.video_title} - {cit.channel_name} "
                f"([View @ {cit.timestamp_str}]({cit.youtube_link}))"
            )
        
        if bib_items:
            paper_content += "\n".join(bib_items)
        else:
            for i, res in enumerate(summary_results):
                video = self.db.get_video(res["video_id"])
                if video:
                    paper_content += f"- {video.title} ([Video Link]({video.url}))\n"

        # 6. Persistence
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
        
        Context from Vault Content (includes sentiment analysis):
        {context}
        
        Requirements for the White Paper:
        1. Use a formal, professional tone.
        2. STRUCTURE: 
           - EXECUTIVE SUMMARY
           - KEY THEMES & INSIGHTS
           - CONTRASTING PERSPECTIVES (If any)
           - ACTIONABLE RECOMMENDATIONS
           - CONCLUSION
        3. CITE YOUR SOURCES: Whenever mentioning an insight, use Markdown footnotes [^1], [^2], etc.
           These must correspond to the sources provided in the context blocks.
        4. Focus on SYNTHESIS: Connect the dots between qualitative insights and the broader research topic.
        
        OUTPUT FORMAT: Markdown.
        """
        
        from src.utils.llm_pool import get_llm_semaphore
        try:
            with get_llm_semaphore():
                response = ollama.chat(
                    model=self.settings["ollama"]["deep_model"],
                    messages=[{"role": "user", "content": prompt}]
                )
            return response.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Synthesis failed for query '{query}': {e}")
            return None

    def _peer_review(self, query: str, report: str, context: str) -> Optional[str]:
        """Validate report against context to detect hallucinations."""
        logger.info("Starting Peer Review phase...")
        prompt = f"""
        Act as a Critical Reviewer. Your task is to verify if the following Research Report accurately reflects the provided Context.
        
        RESEARCH TOPIC: {query}
        
        REPORT:
        {report}
        
        ---
        CONTEXT:
        {context}
        
        ---
        Instructions:
        1. Identify any claims in the report that are NOT supported by the context.
        2. Check if citations [^1], [^2], etc. point to the correct sources for the claims made.
        3. If issues are found, list them concisely as bullet points. 
        4. If the report is accurate, respond with "VERIFIED".
        
        Only respond with bullet points of issues OR the word "VERIFIED".
        """
        
        from src.utils.llm_pool import get_llm_semaphore
        try:
            with get_llm_semaphore():
                response = ollama.chat(
                    model=self.settings["ollama"]["deep_model"],
                    messages=[{"role": "user", "content": prompt}]
                )
            result = response.get("message", {}).get("content", "").strip()
            if result.upper() == "VERIFIED":
                return None
            return result
        except Exception as e:
            logger.error(f"Peer Review failed: {e}")
            return "Reviewer failed to process - please verify citations manually."
