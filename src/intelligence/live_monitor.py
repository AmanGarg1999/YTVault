import logging
import json
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path

from src.storage.sqlite_store import SQLiteStore, WeeklyBrief, MonitoredChannel
from src.ingestion.discovery import discover_video_ids, parse_youtube_url
from src.intelligence.research_agent import ResearchAgent
from src.config import get_settings

logger = logging.getLogger(__name__)

class LiveMonitor:
    """Monitors subscribed channels and generates periodic intelligence briefs."""

    def __init__(self, db: SQLiteStore):
        self.db = db
        self.settings = get_settings()
        self.research_agent = ResearchAgent(self.db)

    def follow_channel(self, url: str) -> bool:
        """Subscribe to a channel for automated briefs."""
        try:
            parsed = parse_youtube_url(url)
            if parsed.url_type != "channel":
                logger.error(f"URL is not a channel: {url}")
                return False
            
            # Ensure channel exists in DB (discovery will handle metadata later)
            # For now we use the channel_id if parsed, or we'll need to fetch it
            channel_id = parsed.channel_id
            if not channel_id:
                from src.ingestion.discovery import extract_channel_info
                channel = extract_channel_info(url)
                channel_id = channel.channel_id
                self.db.upsert_channel(channel)
            
            self.db.insert_monitored_channel(channel_id)
            logger.info(f"Successfully followed channel: {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to follow channel {url}: {e}")
            return False

    def unfollow_channel(self, channel_id: str):
        """Unsubscribe from a channel."""
        self.db.remove_monitored_channel(channel_id)
        logger.info(f"Unfollowed channel: {channel_id}")

    def run_subscriptions_check(self) -> Optional[WeeklyBrief]:
        """
        Check all monitored channels for new content and generate a brief
        if enough new data is found.
        """
        monitored = self.db.get_monitored_channels()
        if not monitored:
            logger.info("No channels are currently monitored.")
            return None

        # Determine the lookback period (e.g., since last brief or last 7 days)
        new_video_ids = []
        channels_with_new_content = []

        for m in monitored:
            last_check = m.last_brief_at or (datetime.now() - timedelta(days=7)).isoformat()
            
            channel = self.db.get_channel(m.channel_id)
            if not channel:
                continue
                
            # Discover new videos since last brief
            from src.ingestion.discovery import parse_youtube_url
            parsed = parse_youtube_url(channel.url)
            
            # Use discover_video_ids with after_date for incremental discovery
            discovered = list(discover_video_ids(channel.url, parsed, after_date=last_check[:10]))
            
            if discovered:
                new_video_ids.extend(discovered)
                channels_with_new_content.append(m.channel_id)
                logger.info(f"Found {len(discovered)} new videos for channel {channel.name}")

        if not new_video_ids:
            logger.info("No new content found across monitored channels.")
            return None

        # Update last_brief_at for these channels
        self.db.update_last_brief_time(channels_with_new_content)

        # Generate a "Weekly Brief" using the Research Agent
        # We construct a specialized query for the new videos
        v_ids_str = ", ".join(new_video_ids[:10]) # Limit to top 10 for brevety
        query = f"Provide a Strategic Intelligence Brief on the latest content from these channels, focusing on videos: {v_ids_str}"
        
        report = self.research_agent.generate_report(query)
        if report:
            brief = WeeklyBrief(
                channel_ids_json=json.dumps(channels_with_new_content),
                content=report.summary # or the whole thing if we want
            )
            # Use the full file content for the brief
            try:
                with open(report.file_path, "r") as f:
                    brief.content = f.read()
            except:
                pass
                
            self.db.insert_weekly_brief(brief)
            logger.info(f"Generated Weekly Brief for {len(channels_with_new_content)} channels.")
            return brief
            
        return None
