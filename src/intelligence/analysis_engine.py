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

    def get_topic_engagement(self, video_id: str, topic_name: str) -> float:
        """Calculate the average heatmap interest score for a specific topic in a video."""
        video = self.db.get_video(video_id)
        if not video or not video.heatmap_json:
            return 0.0
            
        try:
            heatmap_data = json.loads(video.heatmap_json)
            chunks = self.db.get_chunks_for_video(video_id)
            
            topic_chunks = []
            for chunk in chunks:
                topics = json.loads(chunk.topics_json or "[]")
                if any(topic_name.lower() in t.get("name", "").lower() for t in topics):
                    topic_chunks.append(chunk)
            
            if not topic_chunks:
                return 0.0
                
            total_score = 0.0
            count = 0
            
            for chunk in topic_chunks:
                # Find heatmap entries that overlap with this chunk
                for entry in heatmap_data:
                    score = entry.get("score") if "score" in entry else entry.get("value", 0)
                    start = entry.get("start_time") if "start_time" in entry else entry.get("start", 0)
                    end = entry.get("end_time") if "end_time" in entry else entry.get("end", 0)
                    
                    if (start <= chunk.end_timestamp and end >= chunk.start_timestamp):
                        total_score += score
                        count += 1
            
            return total_score / count if count > 0 else 0.0
        except Exception:
            return 0.0

    def get_video_topics_summary(self, video_id: str) -> list[str]:
        """Get top topics aggregated for a video."""
        try:
            topics = self.db.get_video_aggregated_topics(video_id)
            # Sort by relevance and return names
            sorted_topics = sorted(topics, key=lambda x: x.get('relevance', 0), reverse=True)
            return [t['name'] for t in sorted_topics[:10]]
        except Exception:
            return []

    def get_topic_velocity(self, topic_name: str) -> dict:
        """Calculate the 'velocity' of a topic (mentions over time)."""
        mentions = self.db.get_topic_mentions_over_time(topic_name)
        if not mentions:
            return {"velocity": 0.0, "timeline": []}
            
        # Basic velocity: mentions in the last 30 days vs total average
        # (This is a simplified implementation)
        return {
            "total_mentions": sum(m["mentions"] for m in mentions),
            "timeline": mentions,
            "unique_dates": len(mentions)
        }

    def get_topic_sentiment_summary(self, topic_name: str) -> dict:
        """Aggregate sentiment scores for a topic across all videos."""
        # For now, we'll fetch claims related to the topic and their associated video sentiment
        # This is an approximation.
        try:
            # We'd ideally have a way to get sentiment directly for a topic.
            # For now, let's look at claims about this topic.
            # Note: We need a search_claims_by_topic in SQLiteStore or similar.
            # Let's assume we can filter locally for now if not too many.
            all_claims = self.db.search_claims(topic_name, limit=100)
            
            sentiments = []
            for claim in all_claims:
                if topic_name.lower() in claim.topic.lower():
                    # Fetch video sentiment for the video where this claim appears
                    v_sentiment = self.db.execute(
                        "SELECT score FROM video_sentiment WHERE video_id = ? LIMIT 1",
                        (claim.video_id,)
                    ).fetchone()
                    if v_sentiment:
                        sentiments.append(v_sentiment["score"])
            
            if not sentiments:
                return {"average_sentiment": 0.0, "count": 0}
                
            avg = sum(sentiments) / len(sentiments)
            return {
                "average_sentiment": avg,
                "label": "Positive" if avg > 0.2 else ("Negative" if avg < -0.2 else "Neutral"),
                "count": len(sentiments)
            }
        except Exception as e:
            logger.error(f"Failed to get topic sentiment for {topic_name}: {e}")
            return {"average_sentiment": 0.0, "count": 0}

    def analyze_claim_stances(self, topic: str, claims: list) -> dict:
        """Use LLM to determine the overall 'stance' or 'narrative' on a topic based on claims."""
        if not claims:
            return {"stance": "Unknown", "consensus_score": 0.0}
            
        from src.config import get_settings, load_prompt
        import ollama
        
        settings = get_settings()
        ollama_cfg = settings["ollama"]
        model = ollama_cfg.get("deep_model", ollama_cfg.get("rag_model", "llama3.2:3b"))
        
        claims_text = "\n".join([f"- {c.claim_text} (Source: {c.video_id})" for c in claims])
        
        prompt = f"""
        Analyze the following claims regarding the topic: "{topic}".
        Determine the overall stance/narrative (e.g., "Critical", "Supportive", "Warning", "Informational").
        Calculate a consensus score from 0 to 1 (how much do they agree?).
        Provide a 1-sentence summary of the prevailing narrative.
        
        Return JSON format:
        {{
            "stance": "string",
            "consensus_score": float,
            "prevailing_narrative": "string"
        }}
        
        CLAIMS:
        {claims_text}
        """
        
        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}
            )
            content = response["message"]["content"]
            # Basic JSON extraction
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"stance": "Inconclusive", "consensus_score": 0.5}
        except Exception as e:
            logger.error(f"Stance analysis failed: {e}")
            return {"stance": "Error", "consensus_score": 0.0}
