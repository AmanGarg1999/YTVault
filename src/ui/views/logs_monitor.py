"""
Pipeline Logs & Activity Monitor - Real-time visibility into pipeline events.

Shows:
- Live pipeline logs with severity levels (INFO, SUCCESS, WARNING, ERROR)
- Activity timeline for each video
- Error tracking and failure analysis
- Log export and filtering
"""

import logging
import json
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd

logger = logging.getLogger(__name__)


def render(db):
    """Render the Logs & Activity Monitor page."""
    st.markdown("""
    <div class="main-header">
        <h1>Pipeline Logs & Activity Monitor</h1>
        <p>Real-time visibility into all pipeline events, errors, and processing stages</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        # =====================================================================
        # SECTION 1: Real-Time Activity Feed
        # =====================================================================
        st.markdown("### Live Activity Feed")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            scan_filter = st.selectbox(
                "Filter by Scan",
                ["All"] + _get_active_scans(db),
                key="scan_filter",
            )
        with col2:
            level_filter = st.multiselect(
                "Log Levels",
                ["SUCCESS", "INFO", "WARNING", "ERROR", "DEBUG"],
                default=["SUCCESS", "INFO", "WARNING", "ERROR"],
                key="level_filter",
            )
        with col3:
            log_limit = st.slider(
                "Show Recent Logs",
                min_value=10, max_value=500,
                value=100, step=50,
                key="log_limit",
            )
        
        # Fetch logs
        scan_id = None
        if scan_filter != "All":
            import re
            match = re.search(r"\(([^)]+)\)$", scan_filter)
            scan_id = match.group(1) if match else scan_filter
        
        logs = db.get_logs(scan_id=scan_id, limit=log_limit)
        logs = [log for log in logs
                if level_filter is None or log.level in level_filter]
        
        if logs:
            # Display as a rich table
            log_data = []
            for log in logs:
                icon_map = {
                    "SUCCESS": "DONE",
                    "INFO": "INFO",
                    "WARNING": "WARN",
                    "ERROR": "ERROR",
                    "DEBUG": "DEBUG",
                }
                icon = icon_map.get(log.level, "•")
                
                # Get video/channel titles for display
                video_title = "—"
                if log.video_id:
                    v = db.get_video(log.video_id)
                    video_title = v.title[:40] + "..." if v else log.video_id[:12]
                
                channel_name = "—"
                if log.channel_id:
                    c = db.get_channel(log.channel_id)
                    channel_name = c.name if c else log.channel_id[:12]
                elif log.scan_id:
                    # Try to infer channel from scan_id if possible
                    # (This is a bit slow, but only for the first page of logs)
                    pass

                log_data.append({
                    "Time": log.timestamp,
                    "Level": f"{icon} {log.level}",
                    "Stage": log.stage or "—",
                    "Channel": channel_name,
                    "Video": video_title,
                    "Message": log.message[:80] + "..." if len(log.message) > 80 else log.message,
                })
            
            df = pd.DataFrame(log_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Show detailed view on click
            with st.expander("View Full Log Details", expanded=False):
                selected_idx = st.selectbox(
                    "Select log entry",
                    range(len(logs)),
                    format_func=lambda i: f"{logs[i].timestamp} | {logs[i].level} | {logs[i].message[:50]}",
                )
                if 0 <= selected_idx < len(logs):
                    log = logs[selected_idx]
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Metadata**")
                        st.write(f"Log ID: `{log.log_id}`")
                        st.write(f"Timestamp: `{log.timestamp}`")
                        st.write(f"Level: `{log.level}`")
                        st.write(f"Stage: `{log.stage}`")
                    with col2:
                        st.markdown("**References**")
                        st.write(f"Scan: `{log.scan_id or '—'}`")
                        st.write(f"Video: `{log.video_id or '—'}`")
                        st.write(f"Channel: `{log.channel_id or '—'}`")
                    
                    st.markdown("**Message**")
                    st.write(log.message)
                    
                    if log.error_detail:
                        st.markdown("**Error Details**")
                        st.code(log.error_detail, language="text")
        else:
            st.info("No logs found matching the selected filters.")

        st.markdown("---")

        # =====================================================================
        # SECTION 2: Scan-Specific Activity Timeline
        # =====================================================================
        st.markdown("### Per-Video Activity Timeline")
        
        active_scans = _get_active_scans(db)
        if active_scans:
            selected_scan = st.selectbox("Select Scan for Timeline", active_scans, key="timeline_scan")
            
            if selected_scan:
                # Get all videos in scan and their logs
                logs = db.get_logs(scan_id=selected_scan, limit=1000)
                
                # Group by video_id
                video_logs = {}
                for log in logs:
                    if log.video_id:
                        if log.video_id not in video_logs:
                            video_logs[log.video_id] = []
                        video_logs[log.video_id].append(log)
                
                if video_logs:
                    # Show timeline
                    for video_id in sorted(video_logs.keys()):
                        v_logs = video_logs[video_id]
                        
                        # Get video title
                        video = db.get_video(video_id)
                        video_title = video.title[:50] + "..." if video else video_id[:12]
                        
                        # Track stages
                        stages_seen = set()
                        errors = [l for l in v_logs if l.level == "ERROR"]
                        
                        with st.expander(f"{video_title} ({len(v_logs)} events)", expanded=False):
                            # Timeline visualization
                            for log in sorted(v_logs, key=lambda x: x.timestamp):
                                if log.stage:
                                    stages_seen.add(log.stage)
                                
                                icon_map = {
                                    "SUCCESS": "DONE",
                                    "INFO": "INFO",
                                    "WARNING": "WARN",
                                    "ERROR": "ERROR",
                                    "DEBUG": "DEBUG",
                                }
                                icon = icon_map.get(log.level, "•")
                                
                                st.write(f"{icon} **{log.timestamp}** — {log.stage or 'GENERAL'}")
                                st.caption(log.message)
                                
                                if log.error_detail:
                                    st.warning(f"Error: {log.error_detail}")
                else:
                    st.info("No video logs for this scan yet.")
        else:
            st.info("No active scans to show timeline for.")

        st.markdown("---")

        # =====================================================================
        # SECTION 3: Error Analysis & Troubleshooting
        # =====================================================================
        st.markdown("### Error Analysis & Troubleshooting")
        
        # Get recent errors
        error_logs = []
        all_logs = db.get_logs(limit=5000)
        for log in all_logs:
            if log.level == "ERROR":
                error_logs.append(log)
        
        if error_logs:
            error_summary = {}
            for log in error_logs:
                key = f"{log.stage}:{log.message[:50]}"
                if key not in error_summary:
                    error_summary[key] = {"count": 0, "videos": set(), "latest": log}
                error_summary[key]["count"] += 1
                if log.video_id:
                    error_summary[key]["videos"].add(log.video_id)
            
            error_data = []
            for key, data in error_summary.items():
                stage, msg = key.split(":", 1)
                error_data.append({
                    "Stage": stage,
                    "Error Type": msg,
                    "Count": data["count"],
                    "Affected Videos": len(data["videos"]),
                    "Latest": data["latest"].timestamp,
                })
            
            df = pd.DataFrame(error_data)
            df = df.sort_values("Count", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Detailed error inspection
            if st.checkbox("Inspect Error Details", key="inspect_errors"):
                selected_error = st.selectbox(
                    "Select error to inspect",
                    error_data,
                    format_func=lambda x: f"{x['Stage']} | {x['Error Type']} ({x['Count']}x)"
                )
                
                if selected_error:
                    stage = selected_error["Stage"]
                    msg_prefix = selected_error["Error Type"]
                    
                    relevant_logs = [l for l in error_logs
                                    if l.stage == stage and l.message.startswith(msg_prefix)]
                    
                    st.markdown(f"**{len(relevant_logs)} Errors Matching This Pattern**")
                    for log in relevant_logs[:5]:  # Show first 5
                        with st.container(border=True):
                            st.write(f"**Video:** `{log.video_id}`")
                            st.write(f"**Time:** {log.timestamp}")
                            st.write(f"**Message:** {log.message}")
                            if log.error_detail:
                                st.code(log.error_detail, language="text")
        else:
            st.success("No errors logged!")

        st.markdown("---")

        # =====================================================================
        # SECTION 4: Log Summary & Export
        # =====================================================================
        st.markdown("### Log Summary & Export")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Overall Log Stats**")
            try:
                all_logs = db.get_logs(limit=10000)
                summary = {}
                for log in all_logs:
                    summary[log.level] = summary.get(log.level, 0) + 1
                
                for level in ["SUCCESS", "INFO", "WARNING", "ERROR", "DEBUG"]:
                    count = summary.get(level, 0)
                    st.metric(level, count)
            except Exception as e:
                st.error(f"Could not load stats: {e}")
        
        with col2:
            st.markdown("**Export Options**")
            
            export_format = st.radio(
                "Export as",
                ["CSV", "JSON"],
                horizontal=True,
                key="export_format",
            )
            
            if st.button("Export Logs", key="export_logs"):
                try:
                    scan_id = scan_filter if scan_filter != "All" else None
                    logs = db.get_logs(scan_id=scan_id, limit=10000)
                    
                    if export_format == "CSV":
                        df = pd.DataFrame([{
                            "log_id": l.log_id,
                            "timestamp": l.timestamp,
                            "level": l.level,
                            "stage": l.stage,
                            "scan_id": l.scan_id,
                            "video_id": l.video_id,
                            "channel_id": l.channel_id,
                            "message": l.message,
                        } for l in logs])
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "Download CSV",
                            csv,
                            "pipeline_logs.csv",
                            "text/csv"
                        )
                    else:  # JSON
                        data = [{
                            "log_id": l.log_id,
                            "timestamp": l.timestamp,
                            "level": l.level,
                            "stage": l.stage,
                            "scan_id": l.scan_id,
                            "video_id": l.video_id,
                            "channel_id": l.channel_id,
                            "message": l.message,
                            "error_detail": l.error_detail,
                        } for l in logs]
                        json_str = json.dumps(data, indent=2)
                        st.download_button(
                            "Download JSON",
                            json_str,
                            "pipeline_logs.json",
                            "application/json"
                        )
                except Exception as e:
                    st.error(f"Export failed: {e}")
        
        # Cleanup option
        st.markdown("---")
        st.markdown("**Log Maintenance**")
        cleanup_days = st.slider(
            "Delete logs older than (days)",
            min_value=7,
            max_value=365,
            value=30,
        )
        if st.button("Cleanup Old Logs", key="cleanup_logs"):
            count = db.clear_logs(cleanup_days)
            st.success(f"Deleted {count} old logs")

    except Exception as e:
        st.error(f"Failed to load Logs Monitor: {e}")
        logger.error(f"Logs Monitor error: {e}", exc_info=True)


def _get_active_scans(db) -> list[str]:
    """Get list of active scan labels (Channel Name + ID)."""
    try:
        active = db.get_active_scans()
        # Return as "Channel Name (scan_id)"
        return [f"{scan.channel_name} ({scan.scan_id})" for scan in active]
    except Exception as e:
        logger.debug(f"Could not get active scans: {e}")
        return []
