"""
Obsidian export utility for knowledgeVault-YT.

Converts research-grade entities (Claims, Bridges, Clashes) into linked
Markdown notes optimized for Obsidian.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.storage.sqlite_store import (
    SQLiteStore, Claim, ThematicBridge, ExpertClash, Video, Channel
)

logger = logging.getLogger(__name__)


class ObsidianExporter:
    """Exports KnowledgeVault-YT research data to an Obsidian vault structure."""

    def __init__(self, db: SQLiteStore, output_dir: str):
        self.db = db
        self.output_dir = Path(output_dir)
        
        # Ensure root output dir is world-writable
        os.makedirs(self.output_dir, mode=0o777, exist_ok=True)
        try:
            os.chmod(self.output_dir, 0o777)
            # Also try to ensure parent 'data' directory is world-writable if possible
            if self.output_dir.parent.exists():
                os.chmod(self.output_dir.parent, 0o777)
        except Exception as e:
            logger.warning(f"Could not set vault/parent permissions: {e}")
        
        # Subdirectories for organized vault
        for sub in ["Videos", "Channels", "Claims", "Intelligence"]:
            sub_path = self.output_dir / sub
            os.makedirs(sub_path, mode=0o777, exist_ok=True)
            os.chmod(sub_path, 0o777)

    def _write_file(self, path: Path, content: str):
        """Write text to file and ensure it is world-writable for Docker host compatibility."""
        path.write_text(content)
        try:
            os.chmod(path, 0o666)
        except Exception as e:
            logger.warning(f"Failed to set permissions on {path}: {e}")

    def _sanitize(self, text: str) -> str:
        """Sanitize text for use in filenames."""
        return "".join([c if c.isalnum() or c in " _-" else "_" for c in text]).strip()

    def export_all(self):
        """Export everything to the vault."""
        logger.info(f"Starting full Obsidian export to {self.output_dir}")
        self.export_channels()
        self.export_videos()
        self.export_claims()
        self.export_bridges()
        self.export_clashes()
        logger.info("Obsidian export complete.")

    def export_channels(self):
        """Export all channels as individual notes."""
        channels = self.db.get_all_channels()
        for channel in channels:
            filename = self._sanitize(channel.name) + ".md"
            path = self.output_dir / "Channels" / filename
            
            content = [
                "---",
                f"type: channel",
                f"channel_id: {channel.channel_id}",
                f"handle: {channel.handle or 'N/A'}",
                f"category: {channel.category}",
                f"is_verified: {channel.is_verified}",
                f"url: {channel.url}",
                "---",
                f"# {channel.name}\n",
                f"![Thumbnail]({channel.thumbnail_url})\n" if channel.thumbnail_url else "",
                f"{channel.description}\n",
                f"## Channel Statistics",
                f"- **Subscribers:** {channel.follower_count:,}",
                f"- **Total Videos Discovered:** {channel.total_videos}",
                f"- **Knowledge Processed:** {channel.processed_videos}\n",
                f"## Knowledge Assets",
                f"### Videos in Vault",
                f"```dataview",
                f"list from \"Videos\" where channel_id = \"{channel.channel_id}\"",
                f"```\n",
                f"### Extracted Claims",
                f"```dataview",
                f"list from \"Claims\" where channel_id = \"{channel.channel_id}\"",
                f"```"
            ]
            self._write_file(path, "\n".join(content))

    def export_videos(self):
        """Export all accepted videos as individual notes."""
        # Export all videos that are at least discovered, but flag production status
        rows = self.db.conn.execute(
            "SELECT * FROM videos"
        ).fetchall()
        
        for row in rows:
            video = Video.from_row(row)
            channel = self.db.get_channel(video.channel_id)
            channel_link = f"[[{self._sanitize(channel.name)}]]" if channel else "Unknown"
            
            filename = self._sanitize(video.title[:100]) + f" ({video.video_id}).md"
            path = self.output_dir / "Videos" / filename
            
            summary = self.db.get_video_summary(video.video_id)
            
            # Format duration
            mins, secs = divmod(video.duration_seconds, 60)
            duration_str = f"{mins}m {secs}s"
            
            content = [
                "---",
                f"type: video",
                f"status: {video.triage_status}",
                f"video_id: {video.video_id}",
                f"channel_id: {video.channel_id}",
                f"upload_date: {video.upload_date}",
                f"duration: {duration_str}",
                f"views: {video.view_count:,}",
                f"url: {video.url}",
                "---",
                f"# {video.title}\n",
                f"> [!INFO] Pipeline Status: **{video.triage_status}** / **{video.checkpoint_stage}**",
                f"> This note is in **Pre-Production** and will be enriched as the pipeline processes it.\n" if video.triage_status == "DISCOVERED" else "",
                f"**Channel:** {channel_link}",
                f"**Published:** {video.upload_date}",
                f"**Duration:** {duration_str} | **Views:** {video.view_count:,}",
                f"**Source:** [YouTube]({video.url})\n"
            ]
            
            if summary:
                content.append(f"## 📝 Research Summary\n{summary.summary_text}\n")
                
                takeaways = json.loads(summary.takeaways_json or "[]")
                if takeaways:
                    content.append("### 💡 Key Takeaways")
                    for t in takeaways:
                        content.append(f"- {t}")
                    content.append("")
                
                timeline = json.loads(summary.timeline_json or "[]")
                if timeline:
                    content.append("### ⏳ Timeline")
                    for entry in timeline:
                        content.append(f"- **{entry.get('timestamp', '')}**: {entry.get('event', '')}")
                    content.append("")

                topics = json.loads(summary.topics_json or "[]")
                if topics:
                    content.append("### 🏷️ Topics")
                    content.append(" ".join([f"#{self._sanitize(t['name'])}" for t in topics]))
                    content.append("")

            # Direct listing of claims as a callout for immediate value
            claims = self.db.get_claims_for_video(video.video_id)
            if claims:
                content.append("## 📌 Highlighted Claims")
                for i, c in enumerate(claims[:5]):
                    content.append(f"> [!QUOTE] {c.speaker or 'Speaker'}")
                    content.append(f"> {c.claim_text}")
                    content.append(f"> [Link to Claim](Claim-{c.claim_id}.md)")
                    content.append("")

            # Links to all claims via dataview
            content.append(f"## 🔍 Deep Dive: All Claims")
            content.append(f"```dataview")
            content.append(f"table claim_text as \"Claim\", speaker as \"Speaker\" from \"Claims\" where video_id = \"{video.video_id}\"")
            content.append(f"```\n")
            
            self._write_file(path, "\n".join(content))

    def export_claims(self):
        """Export all claims as individual notes or a single directory."""
        # For Obsidian, we might want one note per claim or one note per video-claims
        rows = self.db.conn.execute("SELECT * FROM claims").fetchall()
        for row in rows:
            claim = Claim(**dict(row))
            video = self.db.get_video(claim.video_id)
            
            filename = f"Claim-{claim.claim_id}.md"
            path = self.output_dir / "Claims" / filename
            
            video_link = f"[[{self._sanitize(video.title[:100])} ({video.video_id})]]" if video else "Unknown"
            timestamp_link = f"{video.url}&t={int(claim.timestamp)}" if video else ""
            
            content = [
                "---",
                f"type: claim",
                f"claim_id: {claim.claim_id}",
                f"video_id: {claim.video_id}",
                f"speaker: {claim.speaker}",
                f"topic: {claim.topic}",
                f"confidence: {claim.confidence}",
                "---",
                f"# Claim {claim.claim_id}\n",
                f"> {claim.claim_text} ^ref-{claim.claim_id}\n",
                f"**Speaker:** {claim.speaker}",
                f"**Topic:** #{self._sanitize(claim.topic)}",
                f"**Source:** {video_link} [at {int(claim.timestamp)}s]({timestamp_link})",
                f"**Confidence:** {claim.confidence:.0%}\n",
                f"---",
                f"## Related Research",
                f"```dataview",
                f"list from \"Intelligence\" where contains(related_claims, \"{claim.claim_id}\")",
                f"```"
            ]
            self._write_file(path, "\n".join(content))

    def export_bridges(self):
        """Export all thematic bridges."""
        bridges = self.db.get_thematic_bridges()
        
        filename = "Thematic_Bridges.md"
        path = self.output_dir / "Intelligence" / filename
        
        lines = ["# Thematic Bridges\n"]
        lines.append("Cross-topic synthesized insights.\n")
        
        for b in bridges:
            lines.append(f"### {b.topic_a} ↔ {b.topic_b}")
            lines.append(f"- **Insight:** {b.insight}")
            lines.append(f"- **Model:** `{b.llm_model}`")
            lines.append(f"- **Detected:** {b.created_at}")
            lines.append("\n---\n")
            
        path.write_text("\n".join(lines))

    def export_clashes(self):
        """Export all expert clashes."""
        # expert_clashes table
        rows = self.db.conn.execute("SELECT * FROM expert_clashes").fetchall()
        
        filename = "Expert_Clashes.md"
        path = self.output_dir / "Intelligence" / filename
        
        lines = ["# Expert Clashes\n"]
        lines.append("Contradictions and debates identified across the vault.\n")
        
        for row in rows:
            c = ExpertClash(**dict(row))
            lines.append(f"### Topic: {c.topic}")
            lines.append(f"- **Expert A ({c.expert_a}):** {c.claim_a}")
            lines.append(f"- **Expert B ({c.expert_b}):** {c.claim_b}")
            
            src_a = self.db.get_video(c.source_a) if c.source_a else None
            src_b = self.db.get_video(c.source_b) if c.source_b else None
            
            link_a = f"[[{self._sanitize(src_a.title[:100])} ({src_a.video_id})]]" if src_a else "N/A"
            link_b = f"[[{self._sanitize(src_b.title[:100])} ({src_b.video_id})]]" if src_b else "N/A"
            
            lines.append(f"- **Source A:** {link_a}")
            lines.append(f"- **Source B:** {link_b}")
            lines.append("\n---\n")
            
        path.write_text("\n".join(lines))
