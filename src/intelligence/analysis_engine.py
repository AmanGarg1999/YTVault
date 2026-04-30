"""Analysis Engine for knowledgeVault-YT.

Handles advanced content analysis like heatmap processing, 
audience interest correlation, and trend detection.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

class CoverageAnalyzer:
    """Analyzes vault coverage and identifies knowledge gaps."""

    def __init__(self, db: "SQLiteStore"):
        self.db = db

    def analyze_topic_coverage(self, topic: str) -> dict:
        """Detailed analysis of how well a topic is covered in the vault."""
        stats = self.db.get_topic_coverage_stats(topic)
        if stats.get("video_count", 0) == 0:
            return {"score": 0.0, "status": "No coverage", "gaps": ["No data in vault"]}

        # Compute depth score (0-1)
        # Factors: video count, channel count, temporal spread
        video_weight = min(stats.get("video_count", 0) / 10, 1.0) * 0.4
        channel_weight = min(stats.get("channel_count", 0) / 3, 1.0) * 0.4
        
        # Temporal spread
        temporal_weight = 0.0
        if stats.get("earliest") and stats.get("latest"):
            try:
                from datetime import datetime
                d1 = datetime.strptime(stats["earliest"], "%Y-%m-%d")
                d2 = datetime.strptime(stats["latest"], "%Y-%m-%d")
                days = (d2 - d1).days
                temporal_weight = min(days / 365, 1.0) * 0.2
            except Exception:
                pass
        
        score = video_weight + channel_weight + temporal_weight
        
        gaps = []
        if stats.get("channel_count", 0) < 2:
            gaps.append("Single-source risk: Perspectives may be biased")
        if stats.get("video_count", 0) < 5:
            gaps.append("Thin evidence: Low citation density")
        
        # Check for staleness
        if stats.get("latest"):
            try:
                from datetime import datetime
                latest = datetime.strptime(stats["latest"], "%Y-%m-%d")
                days_old = (datetime.now() - latest).days
                if days_old > 180:
                    gaps.append(f"Stale data: Last update was {days_old} days ago")
            except Exception:
                pass

        return {
            "score": score,
            "status": "High" if score > 0.8 else ("Moderate" if score > 0.4 else "Thin"),
            "gaps": gaps,
            "video_count": stats.get("video_count", 0),
            "channel_count": stats.get("channel_count", 0)
        }

    def get_vault_gaps(self) -> list[dict]:
        """Identifies topics with weak coverage across the entire vault."""
        # Get all topics and their stats
        # For simplicity, we'll use consolidated topics if the method exists
        if hasattr(self.db, "get_consolidated_topics"):
            topics = self.db.get_consolidated_topics()
            gaps = []
            for t in topics:
                name = t.get("topic")
                if not name: continue
                analysis = self.analyze_topic_coverage(name)
                if analysis["score"] < 0.6:
                    gaps.append({
                        "topic": name,
                        "score": analysis["score"],
                        "primary_gap": analysis["gaps"][0] if analysis["gaps"] else "General thinness",
                        "status": analysis["status"]
                    })
            return sorted(gaps, key=lambda x: x["score"])
        return []

    def suggest_ingestions(self, topic: str) -> list[str]:
        """Suggests channel categories or keywords to ingest based on gaps."""
        analysis = self.analyze_topic_coverage(topic)
        suggestions = []
        if any("Single-source risk" in g for g in analysis["gaps"]):
            suggestions.append(f"Search for 2-3 additional channels discussing {topic}")
        if any("Stale data" in g for g in analysis["gaps"]):
            suggestions.append(f"Search for recent videos on {topic} from the last 30 days")
        if analysis["score"] < 0.3:
            suggestions.append(f"Broaden research by ingesting subtopics of {topic}")
        return suggestions


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
        """Calculate mention velocity and trend for a topic."""
        mentions = self.db.get_topic_mentions_over_time(topic_name)
        if not mentions:
            return {"velocity": 0.0, "trend": "stable", "timeline": []}
            
        # Compute trend (last 3 entries vs prior)
        total_mentions = sum(m["mentions"] for m in mentions)
        if len(mentions) >= 4:
            recent = sum(m["mentions"] for m in mentions[-2:])
            prior = sum(m["mentions"] for m in mentions[:-2]) / (len(mentions) - 2)
            
            recent_avg = recent / 2
            velocity = recent_avg / prior if prior > 0 else 1.0
            
            if velocity > 1.5:
                trend = "rising"
            elif velocity < 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            velocity = 1.0
            trend = "stable"

        return {
            "velocity": velocity,
            "trend": trend,
            "total_mentions": total_mentions,
            "timeline": mentions
        }

    def get_topic_sentiment_summary(self, topic_name: str) -> dict:
        """Aggregate sentiment scores for a topic using new storage layer methods."""
        try:
            return self.db.get_topic_sentiment_aggregated(topic_name)
        except Exception as e:
            logger.error(f"Failed to get topic sentiment for {topic_name}: {e}")
            return {"average_sentiment": 0.0, "label": "Neutral", "distribution": {}, "total_count": 0}

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
            
            # Robust JSON extraction
            import json
            def parse_json(text):
                try:
                    # Clean markdown
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0]
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0]
                    
                    # Find boundaries
                    start = text.find("{")
                    end = text.rfind("}")
                    if start != -1 and end != -1:
                        return json.loads(text[start:end+1])
                    return None
                except Exception:
                    return None

            data = parse_json(content)
            if data:
                return data
            return {"stance": "Inconclusive", "consensus_score": 0.5}
        except Exception as e:
            logger.error(f"Stance analysis failed: {e}")
            return {"stance": "Error", "consensus_score": 0.0}
