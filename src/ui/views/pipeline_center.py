"""Pipeline Center - Unified monitoring, control, and logging dashboard."""

import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def render(db, run_pipeline_background, run_repair=None, get_diagnostics=None):
    """Render the Pipeline Control Center."""
    st.markdown("""
    <div class="main-header">
        <h1>Pipeline Control Center</h1>
        <p>Monitor active harvests, manage the queue, and handle failures</p>
    </div>
    """, unsafe_allow_html=True)

    # =====================================================================
    # GLOBAL CONTROLS
    # =====================================================================
    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown("### Global Queue Controls")
            st.caption("Control all active discovery and ingestion tasks simultaneously.")
        
        with col2:
            if st.button("RUN ALL PENDING", type="primary", use_container_width=True):
                count = db.set_global_control_state("RUNNING")
                st.success(f"Signaled {count} scans to RESUME")
                st.rerun()
        
        with col3:
            if st.button("STOP ALL SCANS", type="secondary", use_container_width=True):
                count = db.set_global_control_state("STOPPED", "Global stop requested")
                st.warning(f"Signaled {count} scans to STOP")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    try:
        # =====================================================================
        # TABS: Monitor, Control, Logs
        # =====================================================================
        tab_monitor, tab_control, tab_maintenance, tab_logs = st.tabs([
            "Active Scans",
            "Control",
            "Health & Maintenance",
            "Logs"
        ])

        # =====================================================================
        # TAB 1: MONITOR - Real-time scan status
        # =====================================================================
        with tab_monitor:
            render_monitor_tab(db, run_pipeline_background)

        # =====================================================================
        # TAB 2: CONTROL - Pause/Resume/Stop operations
        # =====================================================================
        with tab_control:
            render_control_tab(db, run_pipeline_background)

        # =====================================================================
        # TAB 3: MAINTENANCE - Vault health and repair
        # =====================================================================
        with tab_maintenance:
            render_maintenance_tab(db, run_repair, get_diagnostics)

        # =====================================================================
        # TAB 4: LOGS - Live activity feed
        # =====================================================================
        with tab_logs:
            render_logs_tab(db)

    except Exception as e:
        st.error(f"Pipeline Center error: {e}")
        logger.error(f"Pipeline Center error: {e}", exc_info=True)


def render_monitor_tab(db, run_pipeline_background):
    """Tab 1: Active scans monitoring with channel health."""
    
    st.markdown("### Active Ingestion Scans")
    active_scans = db.get_active_scans()

    if not active_scans:
        st.info("No active scans running at the moment.")
    else:
        col_refresh = st.columns([1])
        with col_refresh[0]:
            if st.button("Refresh", type="secondary", key="refresh_scans"):
                st.rerun()

        st.markdown("---")

        for scan in active_scans:
            with st.container(border=True):
                processed = getattr(scan, 'total_processed', 0)
                discovered = getattr(scan, 'total_discovered', 0)
                
                col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 1])
                
                with col1:
                    display_name = getattr(scan, 'channel_name', None) or f"Scan {getattr(scan, 'scan_id', 'unknown')[-8:]}"
                    st.markdown(f"**Channel:** `{display_name}`")
                    st.caption(f"Source: {getattr(scan, 'source_url', 'N/A')[:60]}...")
                    
                    # Calculate progress bar
                    if discovered > 0:
                        progress = min(processed / discovered, 1.0)
                    else:
                        progress = 0
                    
                    st.progress(progress, text=f"{processed}/{discovered} processed")
                
                with col2:
                    st.metric("Type", getattr(scan, 'scan_type', 'N/A'))
                
                with col3:
                    if discovered > 0:
                        pct = (processed / discovered) * 100
                        st.metric("Progress", f"{pct:.0f}%")
                    else:
                        st.metric("Progress", "0%")
                
                with col4:
                    global_orch = getattr(st, "_global_orchestrators", {})
                    scan_id = getattr(scan, "scan_id", "")
                    source_url = getattr(scan, "source_url", "")
                    
                    is_in_memory = (scan_id in global_orch or source_url in global_orch)
                    
                    # Get DB control state
                    control = db.get_control_state(scan_id)
                    db_status = control.status if control else "RUNNING"
                    
                    if is_in_memory:
                        if db_status == "PAUSED":
                            status_label = "PAUSED"
                        else:
                            status_label = "RUNNING"
                    else:
                        if db_status == "RUNNING":
                            status_label = "DISCONNECTED"
                        elif db_status == "PAUSED":
                            status_label = "PAUSED"
                        else:
                            status_label = "STOPPED"
                            
                    st.markdown(f"**{status_label}**")
                    
                    # Add Re-attach button if disconnected but supposed to be running
                    if not is_in_memory and db_status == "RUNNING":
                        if st.button("Re-attach", key=f"reattach_{scan_id}", use_container_width=True):
                            run_pipeline_background(source_url, db, scan_id=scan_id)
                            st.success(f"Re-attached to {scan_id}")
                            time.sleep(0.5)
                            st.rerun()

    # =====================================================================
    # Channel Health Section
    # =====================================================================
    st.markdown("---")
    st.markdown("### Channel Health Dashboard")
    
    try:
        channels = db.get_all_channels()
        if channels:
            # Display channels with expandable details (Advanced View)
            for idx, ch in enumerate(channels):
                try:
                    videos = db.get_videos_by_channel(ch.channel_id)
                    if not videos:
                        continue
                        
                    total = len(videos)
                    done = sum(1 for v in videos if getattr(v, "checkpoint_stage", "") == "DONE")
                    accepted = sum(1 for v in videos if getattr(v, "triage_status", "") == "ACCEPTED")
                    rejected = sum(1 for v in videos if getattr(v, "triage_status", "") == "REJECTED")
                    
                    # Calculate quality metrics
                    quality_score = (done / total * 0.4) + (accepted / max(1, accepted + rejected) * 0.6 if accepted + rejected > 0 else 0) * 100
                    
                    with st.expander(f"{getattr(ch, 'name', 'Unknown')[:30]} | {done}/{total} videos | Quality: {quality_score:.0f}%", expanded=False):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Total Videos", total)
                            st.metric("Completed", done)
                        
                        with col2:
                            st.metric("Accepted", accepted)
                            st.metric("Rejected", rejected)
                        
                        with col3:
                            st.metric("Quality Score", f"{quality_score:.1f}%")
                            st.metric("Language", getattr(videos[0], 'language_iso', 'en').upper())
                        
                        st.markdown(f"**Channel ID:** `{ch.channel_id}`")
                        
                        # Video details sub-section
                        st.markdown("#### Recent Videos in Channel")
                        recent_vids = videos[:5]
                        video_records = []
                        for v in recent_vids:
                            topics = _get_video_topics(db, v.video_id)
                            video_records.append({
                                "title": v.title[:45] + "..." if len(v.title) > 45 else v.title,
                                "status": getattr(v, "triage_status", "UNKNOWN"),
                                "stage": getattr(v, "checkpoint_stage", "UNKNOWN"),
                                "topics": ", ".join(topics[:2]) if topics else "—",
                            })
                        
                        if video_records:
                            df = pd.DataFrame(video_records)
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        
                        # Quick actions
                        st.markdown("#### Channel Actions")
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("Re-harvest", key=f"reharvest_btn_{ch.channel_id}", use_container_width=True):
                                if getattr(ch, 'url', None):
                                    with st.spinner("Initiating harvest..."):
                                        logger.info(f"Triggering re-harvest for channel: {ch.name} ({ch.url})")
                                        run_pipeline_background(ch.url, db)
                                        st.success(f"Re-harvest queued for {ch.name}")
                                        st.toast(f"Harvest started for {ch.name}")
                                        time.sleep(1.2) # Allow time for background thread to init
                                        st.rerun()
                                else:
                                    st.error("No URL available for this channel.")
                        
                        with col_btn2:
                            if st.button("Refresh", key=f"refresh_ch_view_{ch.channel_id}", use_container_width=True):
                                st.rerun()
                except Exception as e:
                    logger.warning(f"Error processing channel {ch.channel_id}: {e}")
                    continue
        else:
            st.info("No channels discovered yet.")
    except Exception as e:
        st.warning(f"Could not load channel health: {e}")


def _get_video_topics(db, video_id: str) -> list[str]:
    """Extract topics for a video from its chunks."""
    try:
        chunks = db.conn.execute(
            "SELECT topics_json FROM transcript_chunks WHERE video_id = ? LIMIT 5",
            (video_id,)
        ).fetchall()
        
        topics = set()
        import json
        for chunk in chunks:
            try:
                topics_data = json.loads(chunk[0] or "[]")
                for t in topics_data:
                    if isinstance(t, dict):
                        topics.add(t.get("name", ""))
                    elif isinstance(t, str):
                        topics.add(t)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return list(topics)[:5]
    except Exception as e:
        logger.debug(f"Could not get topics for {video_id}: {e}")
        return []


def render_control_tab(db, run_pipeline_background):
    """Tab 2: Pipeline control operations (pause/resume/stop)."""
    
    st.markdown("### Scan Control Operations")
    
    active_scans = db.get_active_scans()
    
    if not active_scans:
        st.info("No active scans to control.")
        return

    for idx, scan in enumerate(active_scans):
        scan_id = scan.scan_id
        control = db.get_control_state(scan_id)
        
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
            
            # Scan info
            with col1:
                display_name = getattr(scan, 'channel_name', None) or f"Scan {scan_id[-8:]}"
                st.markdown(f"**Target:** `{display_name}`")
                st.caption(f"URL: {scan.source_url[:60]}...")
                st.caption(f"Type: {scan.scan_type}")
            
            # Progress
            with col2:
                progress = 0
                if scan.total_discovered > 0:
                    progress = (scan.total_processed / scan.total_discovered) * 100
                
                st.metric("Progress", f"{scan.total_processed}/{scan.total_discovered}")
                safe_progress = max(0.0, min(1.0, progress / 100))
                st.progress(safe_progress, text=f"{progress:.0f}%")
            
            # Status
            with col3:
                current_status = control.status if control else "RUNNING"
                status_emoji = {
                    "RUNNING": "",
                    "PAUSED": "",
                    "STOPPED": "",
                }.get(current_status, "")
                
                st.markdown(f"{current_status}")
            
            # Control buttons
            with col4:
                col_pause, col_stop = st.columns(2)
                
                with col_pause:
                    if current_status == "RUNNING":
                        if st.button("Pause", key=f"pause_{idx}_{scan_id}", help="Pause scan"):
                            db.set_control_state(scan_id, "PAUSED")
                            st.success(f"Paused {scan_id}")
                            st.rerun()
                    else:
                        if st.button("Resume", key=f"resume_{idx}_{scan_id}", help="Resume scan"):
                            db.set_control_state(scan_id, "RUNNING")
                            st.success(f"Resumed {scan_id}")
                            st.rerun()
                
                with col_stop:
                    if st.button("Stop", key=f"stop_{idx}_{scan_id}", help="Stop scan"):
                        db.set_control_state(scan_id, "STOPPED")
                        st.warning(f"Stopped {scan_id}")
                        st.rerun()


def render_logs_tab(db):
    """Tab 3: Real-time activity feed with filtering."""
    
    st.markdown("### Live Pipeline Activity Feed")
    
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
    logs = [log for log in logs if log.level in level_filter]
    
    if logs:
        st.markdown("---")
        
        # Display logs in reverse order (newest first)
        for log in reversed(logs):
            # Color by level
            level_color = {
                "SUCCESS": "",
                "INFO": "",
                "WARNING": "",
                "ERROR": "",
                "DEBUG": "",
            }.get(log.level, "")
            
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Format timestamp
                    try:
                        ts = datetime.fromisoformat(log.timestamp)
                        rel_time = _relative_time(ts)
                    except:
                        rel_time = log.timestamp
                    
                    st.markdown(f"**[{log.stage}]** {log.message}")
                    st.caption(f"{rel_time} • {log.video_id[:8] if log.video_id else 'N/A'}")
                
                with col2:
                    if log.error_detail:
                        with st.expander("Error Details"):
                            st.code(log.error_detail, language="text")
    else:
        st.info("No logs found.")


# Language map
LANGUAGE_MAP = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
}


def _get_active_scans(db):
    """Get list of active scan labels (Channel Name + ID)."""
    try:
        scans = db.get_active_scans()
        return [f"{s.channel_name} ({s.scan_id})" for s in scans]
    except:
        return []


def render_maintenance_tab(db, run_repair, get_diagnostics):
    """Tab 3: Vault health checkpoints and systematic repair."""
    st.markdown("### Vault Health & Systematic Repair")
    
    # Check for active background repair
    active_repair = None
    if hasattr(st, "_global_orchestrators"):
        for rid, info in st._global_orchestrators.items():
            if info.get("type") == "repair":
                active_repair = info
                break
    
    if active_repair:
        current = active_repair.get("progress_current", 0)
        total = active_repair.get("progress_total", 0)
        
        if total > 0:
            progress = current / total
            st.info(f"**Vault Repair in Progress...** (Processed {current}/{total} videos)")
            st.progress(progress)
        else:
            st.info("**Vault Repair Initializing...**")
            st.progress(0.0)
        
        if st.button("REFRESH STATUS", key="refresh_repair_pc"):
            st.rerun()
        st.markdown("---")

    if get_diagnostics:
        diag = get_diagnostics(db)
        
        # Health Overview Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Videos", diag["total"])
        with col2:
            st.metric("Transcripts", f"{diag['pct_transcripts']}%", delta=f"-{diag['missing_transcripts']} missing" if diag['missing_transcripts'] else None, delta_color="inverse")
        with col3:
            st.metric("Summaries", f"{diag['pct_summaries']}%", delta=f"-{diag['missing_summaries']} missing" if diag['missing_summaries'] else None, delta_color="inverse")
        with col4:
            st.metric("Heatmaps", f"{diag['pct_heatmaps']}%", delta=f"-{diag['missing_heatmaps']} missing" if diag['missing_heatmaps'] else None, delta_color="inverse")
        
        # Progress Bars
        st.write("#### Data Coverage")
        st.progress(diag['pct_transcripts'] / 100, text=f"Transcripts: {diag['pct_transcripts']}%")
        st.progress(diag['pct_summaries'] / 100, text=f"Summaries: {diag['pct_summaries']}%")
        st.progress(diag['pct_heatmaps'] / 100, text=f"Heatmaps: {diag['pct_heatmaps']}%")
        
        st.info("""
        **Vault Repair** systematically fixes identified gaps:
        - **Missing Transcripts**: Resets videos to re-fetch transcripts.
        - **Missing Summaries**: Triggers the new Map-Reduce summarization stage.
        - **Missing Heatmaps**: Refreshes metadata to include audience interest heatmaps.
        """)
        
        if st.button("RUN FULL VAULT REPAIR", type="primary", use_container_width=True, key="run_repair_pc"):
            if run_repair:
                run_repair()
                st.success("Unified Vault Repair started in background!")
                st.toast("Vault health repair in progress...")
                db.log_pipeline_event(
                    level="INFO",
                    message="Manual full vault health repair started",
                    stage="REPAIR"
                )
                st.rerun()
            else:
                st.error("Repair runner not available")
    else:
        st.warning("Diagnostics engine not available")


def _relative_time(dt: datetime) -> str:
    """Format datetime as relative time."""
    now = datetime.now()
    if dt.tzinfo is not None:
        now = now.replace(tzinfo=dt.tzinfo)
    
    diff = now - dt
    
    if diff.total_seconds() < 60:
        return "just now"
    elif diff.total_seconds() < 3600:
        mins = int(diff.total_seconds() // 60)
        return f"{mins}m ago"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() // 3600)
        return f"{hours}h ago"
    else:
        days = int(diff.total_seconds() // 86400)
        return f"{days}d ago"
