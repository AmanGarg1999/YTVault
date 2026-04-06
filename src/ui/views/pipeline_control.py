"""
Pipeline Control Center - Manage active scans and video processing.

Features:
- View active scans and their progress
- Pause/Resume individual scans
- Stop scans gracefully
- Remove videos from processing queue
- Track processing status in real-time
"""

import logging
import streamlit as st
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


def render(db, run_pipeline_background):
    """Render the Pipeline Control Center page."""
    st.markdown("""
    <div class="main-header">
        <h1>Pipeline Control Center</h1>
        <p>Manage active scans, pause/resume processing, and control video ingestion</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("DEBUG: Page header rendered")

    try:
        # =====================================================================
        # SECTION 1: Active Scans Control
        # =====================================================================
        st.markdown("### Active Scans")
        st.write("DEBUG: Section 1 started")
        
        active_scans = db.get_active_scans()
        
        if active_scans:
            for idx, scan in enumerate(active_scans):
                scan_id = scan.scan_id
                control = db.get_control_state(scan_id)
                
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
                    
                    # Scan info
                    with col1:
                        st.markdown(f"**Scan:** `{scan_id}`")
                        st.caption(f"URL: {scan.source_url[:60]}...")
                        st.caption(f"Type: {scan.scan_type}")
                    
                    # Progress
                    with col2:
                        progress = 0
                        if scan.total_discovered > 0:
                            progress = (scan.total_processed / scan.total_discovered) * 100
                        
                        st.metric("Progress", f"{scan.total_processed}/{scan.total_discovered}")
                        # Clamp progress between 0 and 1.0 to avoid Streamlit ValueError
                        safe_progress = max(0.0, min(1.0, progress / 100))
                        st.progress(safe_progress, text=f"{progress:.0f}%")
                    
                    # Status info
                    with col3:
                        status_text = "RUNNING" if control and control.status == "RUNNING" else "PAUSED" if control and control.status == "PAUSED" else "STOPPED"
                        control_status = control.status if control else "RUNNING"
                        st.write(f"**{control_status}**")
                        
                        if control and control.pause_reason:
                            st.caption(f"Reason: {control.pause_reason}")
                    
                    # Controls
                    with col4:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if control and control.status == "PAUSED":
                                if st.button("Resume", key=f"resume_{idx}", use_container_width=True):
                                    db.resume_scan(scan_id)
                                    st.success("Scan resumed")
                                    st.rerun()
                            else:
                                if st.button("Pause", key=f"pause_{idx}", use_container_width=True):
                                    reason = st.text_input(
                                        f"Pause reason (optional):",
                                        key=f"pause_reason_{idx}"
                                    )
                                    db.pause_scan(scan_id, reason)
                                    st.warning(f"Scan paused: {reason}")
                                    st.rerun()
                        
                        with col_b:
                            if st.button("Stop", key=f"stop_{idx}", use_container_width=True, type="secondary"):
                                db.stop_scan(scan_id)
                                st.error("Scan stopped")
                                st.rerun()
                    
                    # Videos in this scan
                    with st.expander("Videos in Scan", expanded=False):
                        videos = db.conn.execute(
                            """SELECT video_id, title, triage_status, checkpoint_stage 
                               FROM videos WHERE video_id IN (
                                   SELECT last_video_id FROM scan_checkpoints WHERE scan_id = ?
                               ) LIMIT 10""",
                            (scan_id,)
                        ).fetchall()
                        
                        if videos:
                            for v in videos:
                                st.write(f"- {v['title'][:50]}... ({v['triage_status']}) [{v['checkpoint_stage']}]")
                        else:
                            st.caption("Fetching videos...")
        else:
            st.info("No active scans currently running.")
        
        st.markdown("---")

        # =====================================================================
        # SECTION 2: Video-Level Queue Management
        # =====================================================================
        st.markdown("### Video Discovery Queue Management")
        st.write("DEBUG: Section 2 started")
        
        # Get discovered but not yet processed videos
        discovered_videos = db.get_videos_by_status("DISCOVERED", limit=100)
        
        if discovered_videos:
            st.markdown(f"#### Videos Awaiting Processing ({len(discovered_videos)})")
            
            # Display as interactive list
            video_data = []
            for v in discovered_videos:
                video_data.append({
                    "Title": v.title[:50] + "..." if len(v.title) > 50 else v.title,
                    "Channel": v.channel_id[:12],
                    "Status": v.triage_status,
                    "Added": v.created_at[:10] if v.created_at else "—",
                    "Video ID": v.video_id,
                })
            
            df = pd.DataFrame(video_data)
            
            # Show with selection
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Remove from queue option
            with st.expander("Remove from Queue", expanded=False):
                st.markdown("**Remove videos before they are processed:**")
                
                video_to_remove = st.selectbox(
                    "Select video to remove from queue",
                    discovered_videos,
                    format_func=lambda v: f"{v.title[:40]}... ({v.video_id[:8]})"
                )
                
                if video_to_remove and st.button("Remove Selected Video", type="secondary"):
                    success = db.remove_video_from_queue(video_to_remove.video_id)
                    if success:
                        st.success(f"Removed from queue: {video_to_remove.title[:40]}...")
                        st.rerun()
                    else:
                        st.error("Could not remove video (may already be processing)")
        else:
            st.info("No videos in discovery queue.")
        
        st.markdown("---")

        # =====================================================================
        # SECTION 3: Processing Status by Stage
        # =====================================================================
        st.markdown("### Processing Status by Pipeline Stage")
        st.write("DEBUG: Section 3 started")
        
        stages = [
            ("METADATA_HARVESTED", "Metadata Harvested"),
            ("TRIAGE_COMPLETE", "Triage Complete"),
            ("TRANSCRIPT_FETCHED", "Transcript Fetched"),
            ("SPONSOR_FILTERED", "Sponsor Filtered"),
            ("TEXT_NORMALIZED", "Text Normalized"),
            ("CHUNKED", "Chunked"),
            ("CHUNK_ANALYZED", "Analyzed"),
            ("EMBEDDED", "Embedded"),
            ("GRAPH_SYNCED", "Graph Synced"),
            ("DONE", "Complete"),
        ]
        
        stage_data = []
        for stage_key, stage_label in stages:
            try:
                count = db.conn.execute(
                    "SELECT COUNT(*) as cnt FROM videos WHERE checkpoint_stage = ?",
                    (stage_key,)
                ).fetchone()["cnt"]
                
                stage_data.append({
                    "Stage": stage_label,
                    "Count": count,
                })
            except Exception as e:
                logger.debug(f"Could not get count for {stage_key}: {e}")
        
        if stage_data:
            df = pd.DataFrame(stage_data)
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.bar_chart(df.set_index("Stage"))
            with col2:
                st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")

        # =====================================================================
        # SECTION 4: Triage Status Summary
        # =====================================================================
        st.markdown("### Triage Decision Summary")
        st.write("DEBUG: Section 4 started")
        
        triage_statuses = ["ACCEPTED", "REJECTED", "PENDING_REVIEW", "DISCOVERED"]
        
        triage_data = []
        for status in triage_statuses:
            count = db.conn.execute(
                "SELECT COUNT(*) as cnt FROM videos WHERE triage_status = ?",
                (status,)
            ).fetchone()["cnt"]
            
            icon_map = {
                "ACCEPTED": "DONE",
                "REJECTED": "FAIL",
                "PENDING_REVIEW": "WAIT",
                "DISCOVERED": "NEW",
            }
            
            triage_data.append({
                "Status": status,
                "Count": count,
            })
        
        df = pd.DataFrame(triage_data)
        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(df.set_index("Status"))
        with col2:
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")

        # =====================================================================
        # SECTION 5: Quick Actions
        # =====================================================================
        st.markdown("### Quick Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Refresh Status", use_container_width=True):
                st.rerun()
        
        with col2:
            st.info("To view detailed logs, navigate to: Logs & Activity (sidebar)")
        
        with col3:
            st.info("To manage data, navigate to: Data Management (sidebar)")

    except Exception as e:
        st.error(f"Failed to load Pipeline Control: {e}")
        logger.error(f"Pipeline Control error: {e}", exc_info=True)
