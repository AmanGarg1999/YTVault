"""
Performance Metrics Dashboard — Real-time pipeline performance monitoring.

Displays execution times, throughput, success rates, and detailed 
stage-by-stage breakdowns for the ingestion pipeline.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.config import get_settings
from src.pipeline.metrics import PerformanceMetricsCollector


def render():
    """Render the performance metrics dashboard."""
    st.header("Performance Metrics", anchor="performance-metrics")
    
    # Get settings and metrics collector
    settings = get_settings()
    collector = PerformanceMetricsCollector(settings["sqlite"]["path"])
    
    # Time period selector
    col1, col2, col3 = st.columns(3)
    with col1:
        hours = st.radio("Time Period", [1, 6, 24], format_func=lambda x: f"Last {x}h", horizontal=False)
    
    # Get metrics
    metrics = collector.get_aggregate_metrics(hours=hours)
    latest_scan = collector.get_latest_scan_metrics()
    
    if not metrics or metrics.get("total_stages_executed", 0) == 0:
        st.info("No performance data available yet. Run an ingestion scan to collect metrics.")
        return
    
    # =====================================================================
    # Summary Cards
    # =====================================================================
    
    st.subheader("Summary", anchor="summary")
    
    metric_cols = st.columns(5)
    
    with metric_cols[0]:
        st.metric(
            "Videos Processed",
            metrics.get("unique_videos_processed", 0),
            delta=f"{metrics.get('unique_scans', 0)} scans"
        )
    
    with metric_cols[1]:
        st.metric(
            "Success Rate",
            f"{metrics.get('success_rate_percent', 0):.1f}%",
            delta=f"{metrics.get('success_count', 0)} succeeded"
        )
    
    with metric_cols[2]:
        throughput = metrics.get('throughput_videos_per_hour', 0)
        st.metric(
            "Throughput",
            f"{throughput:.2f}",
            delta="videos/hour"
        )
    
    with metric_cols[3]:
        total_time = metrics.get('total_time_seconds', 0)
        hours_display = f"{total_time / 3600:.1f}h" if total_time >= 3600 else f"{total_time / 60:.1f}m"
        st.metric(
            "Total Time",
            hours_display,
            delta=f"{metrics.get('total_stages_executed', 0)} stages"
        )
    
    with metric_cols[4]:
        avg_duration = metrics.get('avg_stage_duration_seconds', 0)
        st.metric(
            "Avg Stage Time",
            f"{avg_duration:.2f}s",
            delta="per stage"
        )
    
    # =====================================================================
    # Latest Scan Details
    # =====================================================================
    
    if latest_scan:
        st.subheader("Latest Scan", anchor="latest-scan")
        
        latest_cols = st.columns(4)
        
        with latest_cols[0]:
            st.metric(
                "Scan ID",
                latest_scan.get("scan_id", "N/A")[:8] + "...",
                delta="most recent"
            )
        
        with latest_cols[1]:
            st.metric(
                "Metrics Recorded",
                latest_scan.get("total_metrics_recorded", 0),
                delta="stages"
            )
        
        with latest_cols[2]:
            st.metric(
                "Scan Duration",
                f"{latest_scan.get('total_duration_seconds', 0):.1f}s",
                delta=f"{latest_scan.get('success_count', 0)}/{latest_scan.get('total_metrics_recorded', 0)}"
            )
        
        with latest_cols[3]:
            st.metric(
                "Error Count",
                latest_scan.get("error_count", 0),
                delta=f"{latest_scan.get('success_rate_percent', 0):.0f}% success"
            )
        
        # Latest scan stage performance
        if latest_scan.get("stage_performance"):
            st.write("**Stage Performance in Latest Scan:**")
            
            stage_data = []
            for stage_name, perf in latest_scan["stage_performance"].items():
                stage_data.append({
                    "Stage": stage_name,
                    "Count": perf["count"],
                    "Total Time (s)": f"{perf['total_duration']:.2f}",
                    "Errors": perf["errors"],
                })
            
            df_latest = pd.DataFrame(stage_data)
            st.dataframe(df_latest, use_container_width=True, hide_index=True)
    
    # =====================================================================
    # Stage Breakdown
    # =====================================================================
    
    st.subheader("Stage Performance Breakdown", anchor="stage-breakdown")
    
    stage_breakdown = metrics.get("stage_breakdown", [])
    
    if stage_breakdown:
        # Create detailed DataFrame
        stage_data = []
        for stage in stage_breakdown:
            stage_data.append({
                "Stage": stage["stage"],
                "Executions": stage["execution_count"],
                "Success": stage["success_count"],
                "Errors": stage["error_count"],
                "Avg Time (s)": stage["avg_duration"],
                "Min Time (s)": stage["min_duration"],
                "Max Time (s)": stage["max_duration"],
                "Success Rate": f"{100 * stage['success_count'] / stage['execution_count']:.1f}%" if stage['execution_count'] > 0 else "0%",
            })
        
        df_stages = pd.DataFrame(stage_data)
        
        # Display as table
        st.dataframe(df_stages, use_container_width=True, hide_index=True)
        
        # Create visualization
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Execution Time by Stage (Average)**")
            chart_data = df_stages[["Stage", "Avg Time (s)"]].copy()
            chart_data["Stage"] = chart_data["Stage"].str.replace("_", " ")
            st.bar_chart(
                data=chart_data.set_index("Stage"),
                use_container_width=True,
                height=300
            )
        
        with col2:
            st.write("**Success vs Error Count by Stage**")
            chart_data2 = df_stages[["Stage", "Success", "Errors"]].copy()
            chart_data2["Stage"] = chart_data2["Stage"].str.replace("_", " ")
            st.bar_chart(
                data=chart_data2.set_index("Stage"),
                use_container_width=True,
                height=300
            )
    
    # =====================================================================
    # Performance Tips
    # =====================================================================
    
    with st.expander("Performance Analysis & Tips"):
        st.write("""
        **Understanding Pipeline Metrics:**
        
        - **Throughput**: Videos processed per hour. Higher is better for batch ingestion.
        - **Success Rate**: Percentage of pipeline stages that complete successfully.
        - **Stage Duration**: Time spent in each pipeline stage. Helps identify bottlenecks.
        
        **Optimization Tips:**
        
        1. **High EMBEDDED times?** Your vector model might be overloaded. Consider smaller chunks.
        2. **High TRANSLATED times?** Ollama translation is running slowly. Check service health.
        3. **High CHUNK_ANALYZED times?** LLM extraction is slow. This is normal for detailed analysis.
        4. **Errors in any stage?** Check logs and service health on the Dashboard tab.
        5. **Need faster ingestion?** Disable CHUNK_ANALYZED or GRAPH_SYNCED for faster baseline builds.
        
        **Single-User Optimization:**
        
        - Since you're a single user, focus on **accuracy over speed**.
        - Longer stage times mean richer analysis and better knowledge extraction.
        - If a stage fails, the checkpoint system resumes from the last successful stage.
        """)
    
    # =====================================================================
    # Data Export
    # =====================================================================
    
    with st.expander("Export Metrics"):
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Download as CSV"):
                # Prepare CSV data
                csv_data = []
                csv_data.append("Performance Metrics Export")
                csv_data.append(f"Generated: {datetime.now().isoformat()}")
                csv_data.append(f"Time Period: Last {hours} Hours\n")
                
                csv_data.append("SUMMARY STATISTICS")
                for key, value in metrics.items():
                    if key not in ["stage_breakdown", "period_hours"]:
                        csv_data.append(f"{key},{value}")
                
                csv_text = "\n".join(csv_data)
                
                st.download_button(
                    label="Download Metrics CSV",
                    data=csv_text,
                    file_name=f"performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )
        
        with col2:
            if st.button("View Raw JSON"):
                st.json(metrics)


if __name__ == "__main__":
    render()
