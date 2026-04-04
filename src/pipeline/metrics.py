"""
Performance metrics tracking for knowledgeVault-YT pipeline.

Captures stage timing, throughput, error rates, and other performance indicators.
All metrics are persisted in SQLite for historical analysis and monitoring.
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class StageMetric:
    """Individual stage execution metric."""
    stage_name: str
    video_id: str
    scan_id: str
    start_time: float
    end_time: float
    duration_seconds: float
    status: str  # "success", "failed", "skipped"
    item_count: int = 1  # videos/chunks processed in this stage
    error_message: str = ""


class PerformanceMetricsCollector:
    """Collects and persists pipeline performance metrics."""

    def __init__(self, db_path: str):
        """Initialize metrics collector with SQLite backend."""
        self.db_path = db_path
        self._ensure_metrics_table()
        
    def _ensure_metrics_table(self):
        """Create metrics table if not exists."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    status TEXT NOT NULL,
                    item_count INTEGER DEFAULT 1,
                    error_message TEXT DEFAULT "",
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (scan_id) REFERENCES scan_checkpoints(scan_id)
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to create metrics table: {e}")

    def record_stage(self, metric: StageMetric):
        """Record a single stage execution metric."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO pipeline_metrics 
                (scan_id, video_id, stage_name, start_time, end_time, 
                 duration_seconds, status, item_count, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.scan_id,
                metric.video_id,
                metric.stage_name,
                metric.start_time,
                metric.end_time,
                metric.duration_seconds,
                metric.status,
                metric.item_count,
                metric.error_message,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to record stage metric: {e}")

    def get_stage_metrics(self, scan_id: str) -> List[StageMetric]:
        """Get all metrics for a scan session."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT stage_name, video_id, scan_id, start_time, end_time, 
                       duration_seconds, status, item_count, error_message
                FROM pipeline_metrics
                WHERE scan_id = ?
                ORDER BY start_time ASC
            """, (scan_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            metrics = []
            for row in rows:
                metrics.append(StageMetric(
                    stage_name=row[0],
                    video_id=row[1],
                    scan_id=row[2],
                    start_time=row[3],
                    end_time=row[4],
                    duration_seconds=row[5],
                    status=row[6],
                    item_count=row[7],
                    error_message=row[8]
                ))
            
            return metrics
        except Exception as e:
            logger.error(f"Failed to retrieve stage metrics: {e}")
            return []

    def get_aggregate_metrics(self, hours: int = 24) -> Dict:
        """Get aggregated performance metrics for the last N hours."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Overall stats
            cursor.execute("""
                SELECT COUNT(*) as total_stages,
                       SUM(duration_seconds) as total_time,
                       COUNT(DISTINCT video_id) as unique_videos,
                       COUNT(DISTINCT scan_id) as unique_scans,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as error_count
                FROM pipeline_metrics
                WHERE created_at >= ?
            """, (cutoff_time.isoformat(),))
            
            overall = cursor.fetchone()
            
            # Per-stage stats
            cursor.execute("""
                SELECT stage_name,
                       COUNT(*) as count,
                       AVG(duration_seconds) as avg_duration,
                       MIN(duration_seconds) as min_duration,
                       MAX(duration_seconds) as max_duration,
                       COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
                       COUNT(CASE WHEN status = 'failed' THEN 1 END) as error_count
                FROM pipeline_metrics
                WHERE created_at >= ?
                GROUP BY stage_name
                ORDER BY stage_name
            """, (cutoff_time.isoformat(),))
            
            stage_stats = cursor.fetchall()
            conn.close()
            
            # Process results
            total_stages = overall[0] or 0
            total_time = overall[1] or 0.0
            unique_videos = overall[2] or 0
            success_count = overall[4] or 0
            error_count = overall[5] or 0
            
            success_rate = (success_count / total_stages * 100) if total_stages > 0 else 0
            throughput = unique_videos / (total_time / 3600) if total_time > 0 else 0
            
            return {
                "period_hours": hours,
                "total_stages_executed": total_stages,
                "total_time_seconds": total_time,
                "unique_videos_processed": unique_videos,
                "unique_scans": overall[3] or 0,
                "success_count": success_count,
                "error_count": error_count,
                "success_rate_percent": round(success_rate, 2),
                "throughput_videos_per_hour": round(throughput, 2),
                "avg_stage_duration_seconds": round(total_time / total_stages, 2) if total_stages > 0 else 0,
                "stage_breakdown": [
                    {
                        "stage": stage[0],
                        "execution_count": stage[1],
                        "avg_duration": round(stage[2], 2),
                        "min_duration": round(stage[3], 2),
                        "max_duration": round(stage[4], 2),
                        "success_count": stage[5],
                        "error_count": stage[6],
                    }
                    for stage in stage_stats
                ]
            }
        except Exception as e:
            logger.error(f"Failed to retrieve aggregate metrics: {e}")
            return {}

    def get_latest_scan_metrics(self) -> Dict:
        """Get metrics from the most recent active scan."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get latest scan
            cursor.execute("""
                SELECT DISTINCT scan_id
                FROM pipeline_metrics
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return {}
            
            scan_id = result[0]
            metrics = self.get_stage_metrics(scan_id)
            
            if not metrics:
                return {}
            
            # Calculate stats
            total_duration = sum(m.duration_seconds for m in metrics)
            success_count = len([m for m in metrics if m.status == "success"])
            error_count = len([m for m in metrics if m.status == "failed"])
            
            # Group by stage
            stages = {}
            for metric in metrics:
                if metric.stage_name not in stages:
                    stages[metric.stage_name] = {
                        "count": 0,
                        "total_duration": 0,
                        "errors": 0
                    }
                stages[metric.stage_name]["count"] += 1
                stages[metric.stage_name]["total_duration"] += metric.duration_seconds
                if metric.status == "failed":
                    stages[metric.stage_name]["errors"] += 1
            
            return {
                "scan_id": scan_id,
                "total_metrics_recorded": len(metrics),
                "total_duration_seconds": round(total_duration, 2),
                "success_count": success_count,
                "error_count": error_count,
                "success_rate_percent": round(success_count / len(metrics) * 100, 2) if metrics else 0,
                "stage_performance": stages
            }
        except Exception as e:
            logger.error(f"Failed to retrieve latest scan metrics: {e}")
            return {}


class StageTimer:
    """Context manager for timing pipeline stages."""
    
    def __init__(self, collector: PerformanceMetricsCollector, stage_name: str, 
                 video_id: str, scan_id: str):
        self.collector = collector
        self.stage_name = stage_name
        self.video_id = video_id
        self.scan_id = scan_id
        self.start_time = None
        self.status = "success"
        self.error_message = ""
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        duration = end_time - self.start_time
        
        if exc_type is not None:
            self.status = "failed"
            self.error_message = str(exc_val) if exc_val else ""
        
        metric = StageMetric(
            stage_name=self.stage_name,
            video_id=self.video_id,
            scan_id=self.scan_id,
            start_time=self.start_time,
            end_time=end_time,
            duration_seconds=duration,
            status=self.status,
            error_message=self.error_message
        )
        
        self.collector.record_stage(metric)
        
        return False  # Don't suppress exceptions
