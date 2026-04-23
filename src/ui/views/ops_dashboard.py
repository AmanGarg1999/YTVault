"""Operations Dashboard - Unified Intelligence Orchestration."""

import streamlit as st
import logging
import pandas as pd
import time
from datetime import datetime
from src.ui.components import (
    page_header,
    section_header,
    glass_card,
    info_card,
    metric_grid,
    radial_health_chart,
    status_badge,
    action_confirmation_dialog,
    spacer
)
from src.intelligence.live_monitor import LiveMonitor
from src.storage.sqlite_store import SQLiteStore
from src.ingestion.discovery import validate_target_availability

logger = logging.getLogger(__name__)

def render(db: SQLiteStore, run_pipeline_background, run_bulk_pipeline_background, run_repair=None, get_diagnostics=None):
    """Render the unified Operations Dashboard."""
    
    page_header(
        "Operations Dashboard",
        "Orchestrate research harvests, monitor fleet performance, and maintain system health."
    )

    try:
        # 1. TABS: Orchestration, Fleet, Health, Logs
        tab_control, tab_fleet, tab_health, tab_logs = st.tabs([
            "Orchestration Control",
            "Active Fleet",
            "Vault Health",
            "Live Logs"
        ])

        with tab_control:
            render_command_center(db, run_pipeline_background, run_bulk_pipeline_background)

        with tab_fleet:
            render_fleet_monitor(db, run_pipeline_background)

        with tab_health:
            render_diagnostics(db, run_repair, get_diagnostics)

        with tab_logs:
            render_telemetry(db)
            
    except Exception as e:
        error_card("Operations Hub Failure", f"A critical error occurred while rendering the dashboard: {e}")
        logger.error(f"Ops Dashboard Render Error: {e}", exc_info=True)


def render_command_center(db, run_pipeline_background, run_bulk_pipeline_background):
    """Unified Control and Intake."""
    
    # Global Controls
    with glass_card():
        col_text, col_run, col_stop = st.columns([2, 1, 1])
        with col_text:
            st.markdown("### Global Process Control")
            st.caption("Synchronize all background intelligence gathering operations.")
        
        with col_run:
            if st.button("Resume All Scans", type="primary", use_container_width=True, key="global_resume"):
                count = db.set_global_control_state("RUNNING")
                action_confirmation_dialog(
                    "Global Command Sent",
                    f"Resumption signal broadcast to {count} background orchestrators.",
                    icon="▶"
                )
        
        with col_stop:
            if st.button("Halt Operations", type="primary", use_container_width=True, key="global_halt"):
                count = db.set_global_control_state("STOPPED", "Global stop requested")
                action_confirmation_dialog(
                    "Operations Halted",
                    f"Emergency stop signal broadcast to {count} active processes.",
                    icon="⏹"
                )

    spacer("2rem")
    
    col1, col2 = st.columns(2)
    
    with col1:
        section_header("Quick Intake", icon="✦")
        with glass_card():
            url = st.text_input(
                "Target URL",
                placeholder="Paste YouTube channel, playlist, or video URL...",
                key="ops_harvest_url"
            )
            if st.button("Start Harvest", type="primary", use_container_width=True, key="ops_harvest_btn"):
                if not url:
                    st.toast("Target Required", icon="⚠️")
                else:
                    with st.spinner("Initializing..."):
                        try:
                            if "youtube.com" not in url and "youtu.be" not in url:
                                raise ValueError("Invalid YouTube URL.")
                            validate_target_availability(url)
                            run_pipeline_background(url, db)
                            st.success(f"Harvest started for {url[:40]}...")
                        except Exception as e:
                            st.error(str(e))

    with col2:
        section_header("Bulk synchronization", icon="◈")
        with glass_card():
            channels = db.get_all_channels()
            selected = st.multiselect("Select Targets", channels, format_func=lambda c: c.name, key="ops_bulk_select")
            if st.button("Ignite Bulk Harvest", type="primary", disabled=not selected, key="ops_bulk_btn"):
                urls = [c.url for c in selected]
                run_bulk_pipeline_background(urls, db, force_metadata_refresh=True)
                st.success(f"Processing {len(urls)} targets.")


def render_fleet_monitor(db, run_pipeline_background):
    """Fleet status and Active Scans."""
    active_scans = db.get_active_scans()
    
    if not active_scans:
        info_card("Fleet Idle", "All intelligence discovery threads are currently dormant.")
    else:
        for scan in active_scans:
            with glass_card():
                processed = getattr(scan, 'total_processed', 0)
                discovered = getattr(scan, 'total_discovered', 0)
                scan_id = getattr(scan, "scan_id", "")
                
                col_info, col_prog, col_ctrl = st.columns([4, 4, 2])
                
                with col_info:
                    name = scan.channel_name or f"Scan {scan_id[-8:]}"
                    st.markdown(f"**{name}**")
                    st.caption(scan.scan_type)
                
                with col_prog:
                    if discovered > 0:
                        progress = min(processed / discovered, 1.0)
                        st.progress(progress, text=f"{processed}/{discovered}")
                    else:
                        st.progress(0, text="Initializing...")
                
                with col_ctrl:
                    control = db.get_control_state(scan_id)
                    status = control.status if control else "RUNNING"
                    st.markdown(status_badge("primary" if status == "RUNNING" else "warning", status), unsafe_allow_html=True)
                    
                    # Individual Control
                    c1, c2 = st.columns(2)
                    if status == "RUNNING":
                        if c1.button("⏸", key=f"p_{scan_id}", help="Pause"):
                            db.set_control_state(scan_id, "PAUSED"); st.rerun()
                    else:
                        if c1.button("▶", key=f"r_{scan_id}", help="Resume"):
                            db.set_control_state(scan_id, "RUNNING"); st.rerun()
                    if c2.button("⏹", key=f"s_{scan_id}", help="Stop"):
                        db.set_control_state(scan_id, "STOPPED"); st.rerun()


def render_diagnostics(db, run_repair, get_diagnostics):
    """System Health and Maintenance."""
    stats = db.get_pipeline_stats()
    
    # Metrics Grid
    m_grid = [
        {"value": stats.get("total_videos", 0), "label": "Vaulted Videos"},
        {"value": stats.get("in_progress", 0), "label": "Active Tasks"},
        {"value": stats.get("done", 0), "label": "Synthesized Assets"},
        {"value": stats.get("rejected", 0), "label": "Noise Filtered"}
    ]
    metric_grid(m_grid)
    
    spacer("2rem")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        total_handled = stats.get("done", 0) + stats.get("rejected", 0)
        total_all = stats.get("total_videos", 1)
        health_pct = int((total_handled / total_all) * 100)
        radial_health_chart(health_pct, "Scan Integrity", "Percentage of content fully processed.")

    with col2:
        if get_diagnostics:
            diag = get_diagnostics(db)
            with glass_card("Vault Integrity"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Transcripts", f"{diag['pct_transcripts']}%")
                c2.metric("Summaries", f"{diag['pct_summaries']}%")
                c3.metric("Heatmaps", f"{diag['pct_heatmaps']}%")
                
                if st.button("EXECUTE SYSTEM REPAIR", type="primary", use_container_width=True):
                    if run_repair:
                        run_repair()
                        st.toast("Repair Initiated", icon="🔧")

    spacer("2rem")
    section_header("Queue Stage Breakdown", icon="⏳")
    stages = stats.get("stages", {})
    if stages:
        order = ["DISCOVERED", "METADATA_HARVESTED", "TRIAGE_COMPLETE", "TRANSCRIPT_FETCHED", "CHUNKED", "SUMMARIZED", "GRAPH_SYNCED", "DONE"]
        stage_data = [{"Stage": s, "Videos": stages.get(s, 0)} for s in order if stages.get(s,0) > 0 or s in ["DISCOVERED", "DONE"]]
        st.bar_chart(pd.DataFrame(stage_data).set_index("Stage")["Videos"])


def render_telemetry(db):
    """Logs and Subscriptions."""
    monitor = LiveMonitor(db)
    
    log_tab, sub_tab = st.tabs(["Pipeline Logs", "Research Subscriptions"])
    
    with log_tab:
        col_ctrl1, col_ctrl2 = st.columns([2, 1])
        with col_ctrl2:
            limit = st.slider("Log Depth", 50, 500, 100)
        
        logs = db.get_logs(limit=limit)
        for l in reversed(logs):
            color = "#ef4444" if l.level == "ERROR" else ("#f59e0b" if l.level == "WARNING" else "#cbd5e1")
            st.markdown(f"""
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; border-bottom: 1px solid rgba(255,255,255,0.05); padding: 0.4rem 0;">
                <span style="color: #64748b;">[{l.timestamp[-8:]}]</span>
                <span style="color: {color}; font-weight: 700;"> {l.level}</span>
                <span style="color: #94a3b8;"> | {l.stage or 'CORE'} | </span>
                <span style="color: #f1f5f9;">{l.message}</span>
            </div>
            """, unsafe_allow_html=True)

    with sub_tab:
        with glass_card("Follow New Research Channel"):
            col1, col2 = st.columns([3, 1])
            new_url = col1.text_input("Channel URL", placeholder="https://youtube.com/@...", label_visibility="collapsed")
            if col2.button("Sync Now", type="primary", use_container_width=True):
                if new_url and monitor.follow_channel(new_url):
                    st.success("Followed")
                    st.rerun()

        monitored = db.get_monitored_channels()
        for m in monitored:
            channel = db.get_channel(m.channel_id)
            with glass_card():
                c1, c2, c3 = st.columns([1, 4, 1])
                if channel and channel.thumbnail_url: c1.image(channel.thumbnail_url, width=50)
                c2.markdown(f"**{channel.name if channel else m.channel_id}**")
                c2.caption(f"Last Brief: {m.last_brief_at or 'Never'}")
                if c3.button("Delete", key=f"unsub_{m.channel_id}"):
                    monitor.unfollow_channel(m.channel_id)
                    st.rerun()
