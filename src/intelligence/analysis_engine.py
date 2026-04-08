"""Analysis Engine for knowledgeVault-YT.

Handles advanced content analysis like heatmap processing, 
audience interest correlation, and trend detection.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class HeatmapPeak:
    """Represents a period of high audience interest in a video."""
    start_time: float
    end_time: float
    score: float
    transcript_text: str = ""

class AnalysisEngine:
    """Advanced analytics engine for content intelligence."""
    
    def __init__(self, db):
        self.db = db

    def get_heatmap_highlights(self, video_id: str, threshold: float = 0.7) -> list[HeatmapPeak]:
        """Extract 'Key Moments' by correlating heatmap peaks with transcript chunks.
        
        Args:
            video_id: The YouTube video ID.
            threshold: Normalized interest score (0-1) to consider a 'peak'.
            
        Returns:
            List of HeatmapPeak objects with associated transcript text.
        """
        video = self.db.get_video(video_id)
        if not video or not video.heatmap_json:
            return []
            
        try:
            heatmap_data = json.loads(video.heatmap_json)
            if not isinstance(heatmap_data, list):
                return []
                
            # 1. Identify peaks in heatmap
            peaks = []
            current_peak = None
            
            # heatmap_data is typically a list of {start_time, end_time, score}
            # or yt-dlp format: {start, end, value}
            for entry in heatmap_data:
                score = entry.get("score") if "score" in entry else entry.get("value", 0)
                start = entry.get("start_time") if "start_time" in entry else entry.get("start", 0)
                end = entry.get("end_time") if "end_time" in entry else entry.get("end", 0)
                
                if score >= threshold:
                    if current_peak is None:
                        current_peak = HeatmapPeak(
                            start_time=start,
                            end_time=end,
                            score=score
                        )
                    else:
                        # Extend current peak
                        current_peak.end_time = entry["end_time"]
                        current_peak.score = max(current_peak.score, score)
                else:
                    if current_peak:
                        peaks.append(current_peak)
                        current_peak = None
            
            if current_peak:
                peaks.append(current_peak)
                
            if not peaks:
                return []
                
            # 2. Correlate with transcript chunks
            # We'll fetch chunks that overlap with the peak timestamps
            all_chunks = self.db.get_chunks_for_video(video_id)
            
            for peak in peaks:
                relevant_text = []
                for chunk in all_chunks:
                    # Check for overlap
                    if (chunk.start_timestamp <= peak.end_time and 
                        chunk.end_timestamp >= peak.start_time):
                        relevant_text.append(chunk.cleaned_text)
                
                peak.transcript_text = " ".join(relevant_text).strip()
                
            # Sort by score (highest interest first)
            return sorted(peaks, key=lambda x: x.score, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to analyze heatmap for {video_id}: {e}")
            return []

    def get_video_topics_summary(self, video_id: str) -> list[str]:
        """Get top topics aggregated for a video."""
        try:
            topics = self.db.get_video_aggregated_topics(video_id)
            # Sort by relevance and return names
            sorted_topics = sorted(topics, key=lambda x: x.get('relevance', 0), reverse=True)
            return [t['name'] for t in sorted_topics[:10]]
        except Exception:
            return []
