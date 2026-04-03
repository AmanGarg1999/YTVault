"""
ETA calculation utilities for knowledgeVault-YT pipeline.

Tracks processing time per stage and provides time-to-completion estimates.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """Metrics for a pipeline stage."""
    stage_name: str
    total_videos_processed: int = 0
    total_time_seconds: float = 0.0
    error_count: int = 0
    
    @property
    def average_time_per_video(self) -> float:
        """Average seconds per video for this stage."""
        if self.total_videos_processed == 0:
            return 0.0
        return self.total_time_seconds / self.total_videos_processed
    
    def record(self, elapsed_seconds: float, success: bool = True):
        """Record processing of one video."""
        self.total_videos_processed += 1
        self.total_time_seconds += elapsed_seconds
        if not success:
            self.error_count += 1


class ETACalculator:
    """Calculate time-to-completion estimates for scans."""
    
    def __init__(self):
        self.stage_metrics: dict[str, StageMetrics] = {}
        self.scan_start_time: float = 0.0
        self.videos_discovered: int = 0
        self.videos_completed: int = 0
    
    def start_scan(self):
        """Mark the start of a scan."""
        self.scan_start_time = time.time()
        self.videos_discovered = 0
        self.videos_completed = 0
    
    def update_discovery(self, total_discovered: int):
        """Update discovered video count."""
        self.videos_discovered = total_discovered
    
    def record_video_completion(self, stage_name: str, elapsed_seconds: float, success: bool = True):
        """Record completion of one video at a stage."""
        if stage_name not in self.stage_metrics:
            self.stage_metrics[stage_name] = StageMetrics(stage_name)
        
        self.stage_metrics[stage_name].record(elapsed_seconds, success)
        
        # Track videos that completed at the final stage
        if stage_name == "DONE":
            self.videos_completed += 1
    
    def get_eta_seconds(self, current_video_index: int, current_stage_index: int, 
                       total_stages: int) -> Optional[float]:
        """Estimate seconds until completion.
        
        Args:
            current_video_index: Which video we're on (0-based)
            current_stage_index: Which stage we're on (0-based)
            total_stages: Total number of stages
        
        Returns:
            Estimated seconds to completion, or None if not calculable.
        """
        if self.videos_discovered == 0 or not self.stage_metrics:
            return None
        
        remaining_videos = self.videos_discovered - current_video_index - 1
        if remaining_videos <= 0:
            # Almost done, estimate time for current video's remaining stages
            remaining_time = 0.0
            for stage_idx in range(current_stage_index, total_stages):
                stage_name = self._get_stage_name(stage_idx)
                if stage_name in self.stage_metrics:
                    remaining_time += self.stage_metrics[stage_name].average_time_per_video
            return remaining_time
        
        # Calculate time for remaining videos through all stages
        total_remaining_time = 0.0
        
        # Time for current video's remaining stages
        for stage_idx in range(current_stage_index, total_stages):
            stage_name = self._get_stage_name(stage_idx)
            if stage_name in self.stage_metrics:
                total_remaining_time += self.stage_metrics[stage_name].average_time_per_video
        
        # Time for all remaining videos through all stages
        avg_time_per_video_all_stages = sum(
            m.average_time_per_video for m in self.stage_metrics.values()
        )
        total_remaining_time += remaining_videos * avg_time_per_video_all_stages
        
        return total_remaining_time
    
    def get_completion_percentage(self, current_video_index: int, current_stage_index: int,
                                 total_stages: int) -> float:
        """Calculate completion percentage.
        
        Returns:
            Percentage 0-100.
        """
        if self.videos_discovered == 0:
            return 0.0
        
        # Simple: (videos completed + partial progress on current) / total
        videos_completed_pct = (current_video_index / self.videos_discovered) * 100
        stage_progress = (current_stage_index / max(1, total_stages)) * (100 / self.videos_discovered)
        
        return min(99.9, videos_completed_pct + stage_progress)
    
    def get_throughput_videos_per_hour(self) -> Optional[float]:
        """Calculate current throughput in videos/hour."""
        if self.videos_completed == 0:
            return None
        
        elapsed = time.time() - self.scan_start_time
        if elapsed < 1:
            return None
        
        hours_elapsed = elapsed / 3600
        return self.videos_completed / hours_elapsed if hours_elapsed > 0 else None
    
    def _get_stage_name(self, stage_index: int) -> str:
        """Get stage name by index."""
        stages = [
            "DISCOVERY", "TRIAGE_COMPLETE", "TRANSCRIPT_FETCHED",
            "SPONSOR_FILTERED", "TEXT_NORMALIZED", "CHUNKED",
            "CHUNK_ANALYZED", "EMBEDDED", "GRAPH_SYNCED", "DONE"
        ]
        return stages[stage_index] if stage_index < len(stages) else f"STAGE_{stage_index}"
    
    def get_summary(self) -> str:
        """Get a human-readable ETA summary."""
        if not self.stage_metrics:
            return "ETA: Calculating..."
        
        throughput = self.get_throughput_videos_per_hour()
        total_avg_time = sum(m.average_time_per_video for m in self.stage_metrics.values())
        
        summary_parts = []
        summary_parts.append(f"Discovered: {self.videos_discovered}")
        summary_parts.append(f"Completed: {self.videos_completed}")
        
        if throughput:
            summary_parts.append(f"Throughput: {throughput:.1f} videos/hour")
        
        if total_avg_time > 0:
            remaining_videos = self.videos_discovered - self.videos_completed
            remaining_time = remaining_videos * total_avg_time
            minutes = int(remaining_time / 60)
            summary_parts.append(f"ETA: ~{minutes}min")
        
        return " | ".join(summary_parts)
