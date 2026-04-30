"""
Export module for knowledgeVault-YT.

Exports research insights and data in Markdown, JSON, and CSV formats.
"""

import csv
import io
import json
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from src.intelligence.rag_engine import RAGResponse
from src.storage.sqlite_store import SQLiteStore
from src.storage.graph_store import GraphStore
from src.intelligence.analysis_engine import AnalysisEngine
from src.intelligence.dossier_engine import DossierEngine

logger = logging.getLogger(__name__)


class ExportEngine:
    """Export research data in multiple formats."""

    def __init__(self, db: SQLiteStore):
        self.db = db
        # Lazy initialization for expensive analytical components
        self._graph = None
        self._analysis = None
        self._dossier = None

    @property
    def graph(self):
        if self._graph is None:
            self._graph = GraphStore()
        return self._graph

    @property
    def analysis(self):
        if self._analysis is None:
            self._analysis = AnalysisEngine(self.db)
        return self._analysis

    @property
    def dossier(self):
        if self._dossier is None:
            self._dossier = DossierEngine(self.db, self.graph, self.analysis)
        return self._dossier

    def export_topic_dossier(self, topic: str, fmt: str = "markdown") -> str:
        """Generate and export a full intelligence dossier for a topic."""
        data = self.dossier.generate_topic_dossier(topic)
        if fmt == "json":
            return json.dumps(data, indent=2)
        else:
            return self.dossier.format_dossier_markdown(data)

    def create_vault_snapshot(self) -> str:
        """
        Create a full intelligence snapshot (.kvvault ZIP).
        Contains the SQLite database and a summary report.
        Returns path to the generated ZIP.
        """
        temp_dir = Path(tempfile.mkdtemp())
        snapshot_path = temp_dir / f"knowledge_vault_snapshot_{datetime.now().strftime('%Y%m%d_%H%M')}.kvvault"
        
        try:
            with zipfile.ZipFile(snapshot_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Database Backup
                db_backup_path = temp_dir / "vault.sqlite"
                # Use SQLite's backup capability if possible, or just copy (since we have WAL)
                shutil.copy2(self.db.db_path, db_backup_path)
                zipf.write(db_backup_path, "vault.sqlite")
                
                # 2. Summary Report
                summary = self.export_pipeline_stats()
                summary_path = temp_dir / "manifest.md"
                summary_path.write_text(summary)
                zipf.write(summary_path, "manifest.md")
                
                # 3. Export all Chat Missions
                missions = self.export_mission_package([s.session_id for s in self.db.get_chat_sessions()])
                mission_path = temp_dir / "missions.json"
                mission_path.write_text(missions)
                zipf.write(mission_path, "missions.json")
                
            return str(snapshot_path)
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return ""

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
        elif fmt == "obsidian":
            return self._rag_to_obsidian_markdown(response)
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

    def export_video_package(self, video_id: str, fmt: str = "markdown") -> str:
        """Export a complete research package for a specific video."""
        video = self.db.get_video(video_id)
        if not video:
            return "Video not found"
        
        summary = self.db.get_video_summary(video_id)
        claims = self.db.get_claims_for_video(video_id)
        channel = self.db.get_channel(video.channel_id)

        if fmt == "json":
            return json.dumps({
                "video": {
                    "id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "channel": channel.name if channel else "Unknown",
                    "published": video.upload_date
                },
                "summary": {
                    "text": summary.summary_text if summary else "",
                    "takeaways": json.loads(summary.takeaways_json) if summary and summary.takeaways_json else [],
                    "topics": json.loads(summary.topics_json) if summary and summary.topics_json else []
                },
                "claims": [
                    {
                        "text": c.claim_text,
                        "speaker": c.speaker,
                        "timestamp": c.timestamp,
                        "topic": c.topic,
                        "confidence": c.confidence
                    } for c in claims
                ]
            }, indent=2)
        else:
            # Markdown
            lines = [
                f"# Research Package: {video.title}",
                f"**Source:** [{video.url}]({video.url})",
                f"**Channel:** {channel.name if channel else 'Unknown'}",
                f"**Published:** {video.upload_date}\n",
                "---",
                "## 📝 Research Summary",
                summary.summary_text if summary else "_No summary available._",
                "\n### 💡 Key Takeaways"
            ]
            
            if summary and summary.takeaways_json:
                takeaways = json.loads(summary.takeaways_json)
                for t in takeaways:
                    lines.append(f"- {t}")
            else:
                lines.append("_No takeaways structured yet._")

            lines.append("\n## 📌 Evidence-Based Claims")
            if claims:
                for c in claims:
                    lines.append(f"- **{c.speaker or 'Speaker'}**: {c.claim_text} (at {int(c.timestamp)}s)")
            else:
                lines.append("_No claims extracted yet._")

            lines.append(f"\n---\n*Generated by KnowledgeVault-YT Export Engine on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
            return "\n".join(lines)


    def export_chat_session(self, session_id: str, fmt: str = "markdown") -> str:
        """Export a full chat session history."""
        sessions = self.db.get_chat_sessions()
        session = next((s for s in sessions if s.session_id == session_id), None)
        if not session:
            return "Session not found"
        
        history = self.db.get_chat_history(session_id)
        
        if fmt == "json":
            return json.dumps({
                "session_name": session.name,
                "session_id": session.session_id,
                "created_at": session.created_at,
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "citations": json.loads(m.citations_json) if m.citations_json else []
                    } for m in history
                ]
            }, indent=2)
        else:
            # Markdown
            lines = [
                f"# Mission Briefing: {session.name}",
                f"**Session ID:** `{session.session_id}`",
                f"**Date:** {session.created_at}\n",
                "---"
            ]
            
            for m in history:
                role_label = "### 🧑‍💻 User" if m.role == "user" else "### 🤖 Intelligence Assistant"
                lines.append(f"\n{role_label}")
                lines.append(m.content)
                
                if m.role == "assistant" and m.citations_json:
                    try:
                        citations = json.loads(m.citations_json)
                        if citations:
                            lines.append("\n**Sources Cited:**")
                            for c in citations:
                                lines.append(f"- [{c.get('source_id', '?')}] {c.get('video_title', 'Video')} ({c.get('timestamp', '00:00')})")
                    except: pass
            
            lines.append(f"\n---\n*Exported by KnowledgeVault-YT on {datetime.now().strftime('%Y-%m-%d')}*")
            return "\n".join(lines)

    def export_mission_package(self, session_ids: list[str]) -> str:
        """Export a complete collaboration mission package (Sessions + related video metadata)."""
        sessions = self.db.get_chat_sessions()
        target_sessions = [s for s in sessions if s.session_id in session_ids]
        
        package = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "missions": []
        }
        
        related_video_ids = set()
        
        for sess in target_sessions:
            history = self.db.get_chat_history(sess.session_id)
            sess_data = {
                "name": sess.name,
                "id": sess.session_id,
                "messages": []
            }
            
            for m in history:
                citations = json.loads(m.citations_json) if m.citations_json else []
                for c in citations:
                    if "video_id" in c:
                        related_video_ids.add(c["video_id"])
                
                sess_data["messages"].append({
                    "role": m.role,
                    "content": m.content,
                    "citations": citations
                })
            
            package["missions"].append(sess_data)
        
        # Add minimal video metadata for context sync
        package["context_sources"] = []
        for v_id in related_video_ids:
            v = self.db.get_video(v_id)
            if v:
                package["context_sources"].append({
                    "id": v.video_id,
                    "title": v.title,
                    "url": v.url,
                    "channel_id": v.channel_id
                })
        
        return json.dumps(package, indent=2)

    def import_mission_package(self, package_json: str) -> dict:
        """Import a collaboration mission package. (Stub for sync)"""
        try:
            data = json.loads(package_json)
            # In a real sync, we'd insert these into the DB
            # For this hardening phase, we focus on the export capability first
            return {"success": True, "missions_count": len(data.get("missions", []))}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------
    # Format Converters
    # -------------------------------------------------------------------

    def _rag_to_markdown(self, r: RAGResponse) -> str:
        lines = [
            f"# 📜 Research Intelligence Report\n",
            f"**Query:** {r.query}\n",
            f"---\n",
            f"## 🤖 Synthesized Intelligence\n\n{r.answer}\n",
        ]
        
        # Phase 1/2 Enhancement: Quantitative Intelligence in Export
        if hasattr(r, "quantitative_metrics") and r.quantitative_metrics:
            qm = r.quantitative_metrics
            lines.extend([
                f"---\n",
                f"## 📊 Quantitative Context\n",
                f"- **Consensus Score:** `{qm.claim_stats.get('avg_corroboration', 1.0):.2f}`",
                f"- **Vault Coverage:** {qm.topic_coverage.get('video_count', 0)} videos across {qm.topic_coverage.get('channel_count', 0)} channels",
                f"- **Sentiment:** {qm.sentiment_distribution.get('label', 'Neutral')} ({qm.sentiment_distribution.get('average_sentiment', 0.0):.2f})",
                f"- **Top Authorities:** {', '.join([a['name'] for a in qm.authorities[:3]])}",
                "\n"
            ])

        lines.extend([
            f"---\n",
            f"## 📑 Source Citations ({r.total_chunks_used})\n",
        ])
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
        data = {
            "query": r.query,
            "answer": r.answer,
            "citations": [
                {
                    "source_id": c.source_id,
                    "video_id": c.video_id,
                    "video_title": c.video_title,
                    "channel": c.channel_name,
                    "timestamp": c.timestamp_str,
                    "link": c.youtube_link
                } for c in r.citations
            ],
            "metadata": {
                "latency_ms": r.latency_ms,
                "chunks_retrieved": r.total_chunks_retrieved,
                "confidence": r.confidence.overall if r.confidence else 0.0
            }
        }
        if hasattr(r, "quantitative_metrics") and r.quantitative_metrics:
            from dataclasses import asdict
            data["quantitative_metrics"] = asdict(r.quantitative_metrics)
            
        return json.dumps(data, indent=2)

    def _rag_to_csv(self, r: RAGResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Source", "Video Title", "Channel", "Timestamp",
            "YouTube Link", "Excerpt",
        ])
        for c in r.citations:
            writer.writerow([
                c.source_id, c.video_id, c.video_title, c.channel_name,
                c.timestamp_str, c.youtube_link, c.text_excerpt,
            ])
        return output.getvalue()

    def _rag_to_obsidian_markdown(self, r: RAGResponse) -> str:
        """Format research report with Obsidian frontmatter and backlinks."""
        frontmatter = [
            "---",
            f"type: research_report",
            f"query: \"{r.query}\"",
            f"date: {datetime.now().strftime('%Y-%m-%d')}",
            f"latency: {r.latency_ms:.0f}ms",
            f"sources: {r.total_chunks_used}",
            "tags: [knowledgevault, research]",
            "---\n"
        ]
        
        body = self._rag_to_markdown(r)
        
        # Add Obsidian-style backlinks to channels if mentioned
        # (This is a simple version, can be expanded)
        return "\n".join(frontmatter) + "\n" + body
