"""
Export module for knowledgeVault-YT.

Exports research insights and data in Markdown, JSON, and CSV formats.
"""

import csv
import io
import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from src.intelligence.rag_engine import RAGResponse
from src.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class ExportEngine:
    """Export research data in multiple formats."""

    def __init__(self, db: SQLiteStore):
        self.db = db

    def export_rag_response(self, response: RAGResponse, fmt: str = "markdown") -> str:
        """Export a RAG response in the requested format.

        Args:
            response: The RAG query response.
            fmt: Output format — "markdown", "json", or "csv".

        Returns:
            Formatted string content.
        """
        if fmt == "json":
            return self._rag_to_json(response)
        elif fmt == "csv":
            return self._rag_to_csv(response)
        else:
            return self._rag_to_markdown(response)

    def export_guests(self, fmt: str = "markdown") -> str:
        """Export all guest records."""
        guests = self.db.get_all_guests()

        if fmt == "json":
            return json.dumps(
                [{"name": g.canonical_name, "aliases": g.aliases,
                  "mentions": g.mention_count, "type": g.entity_type}
                 for g in guests],
                indent=2,
            )
        elif fmt == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Name", "Aliases", "Mentions", "Type"])
            for g in guests:
                writer.writerow([
                    g.canonical_name, "; ".join(g.aliases),
                    g.mention_count, g.entity_type,
                ])
            return output.getvalue()
        else:
            lines = ["# Guest Registry\n"]
            for g in guests:
                aliases = f" (aka {', '.join(g.aliases)})" if g.aliases else ""
                lines.append(
                    f"- **{g.canonical_name}**{aliases} — "
                    f"{g.mention_count} mentions ({g.entity_type})"
                )
            return "\n".join(lines)

    def export_pipeline_stats(self) -> str:
        """Export pipeline statistics as Markdown summary."""
        stats = self.db.get_pipeline_stats()
        return (
            f"# Pipeline Statistics\n\n"
            f"**Generated:** {datetime.now().isoformat()}\n\n"
            f"| Metric | Count |\n|---|---|\n"
            f"| Total Channels | {stats.get('total_channels', 0)} |\n"
            f"| Total Videos | {stats.get('total_videos', 0)} |\n"
            f"| Triage: Accepted | {stats.get('accepted', 0)} |\n"
            f"| Triage: Rejected | {stats.get('rejected', 0)} |\n"
            f"| Triage: Pending | {stats.get('pending_review', 0)} |\n"
            f"| Transcripts Fetched | {stats.get('transcript_fetched', 0)} |\n"
            f"| Chunks Indexed | {stats.get('total_chunks', 0)} |\n"
            f"| Guests Identified | {stats.get('total_guests', 0)} |\n"
        )

    # -------------------------------------------------------------------
    # Format Converters
    # -------------------------------------------------------------------

    def _rag_to_markdown(self, r: RAGResponse) -> str:
        lines = [
            f"# Research Query\n",
            f"**Question:** {r.query}\n",
            f"---\n",
            f"## Answer\n\n{r.answer}\n",
            f"---\n",
            f"## Sources ({r.total_chunks_used} citations)\n",
        ]
        for c in r.citations:
            lines.append(
                f"- **[{c.source_id}]** [{c.video_title}]({c.youtube_link}) "
                f"({c.channel_name}, {c.timestamp_str})"
            )
        lines.append(
            f"\n---\n*Query latency: {r.latency_ms:.0f}ms | "
            f"Chunks retrieved: {r.total_chunks_retrieved}*"
        )
        return "\n".join(lines)

    def _rag_to_json(self, r: RAGResponse) -> str:
        return json.dumps({
            "query": r.query,
            "answer": r.answer,
            "citations": [
                {
                    "source_id": c.source_id,
                    "video_id": c.video_id,
                    "video_title": c.video_title,
                    "channel": c.channel_name,
                    "timestamp": c.timestamp_str,
                    "youtube_link": c.youtube_link,
                    "excerpt": c.text_excerpt,
                }
                for c in r.citations
            ],
            "metrics": {
                "latency_ms": r.latency_ms,
                "chunks_retrieved": r.total_chunks_retrieved,
                "chunks_used": r.total_chunks_used,
            },
        }, indent=2)

    def _rag_to_csv(self, r: RAGResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Source", "Video Title", "Channel", "Timestamp",
            "YouTube Link", "Excerpt",
        ])
        for c in r.citations:
            writer.writerow([
                c.source_id, c.video_title, c.channel_name,
                c.timestamp_str, c.youtube_link, c.text_excerpt,
            ])
        return output.getvalue()
