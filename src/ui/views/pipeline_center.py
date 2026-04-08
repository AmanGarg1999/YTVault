"""Pipeline Center - Intelligence Core Redesign."""

import logging
import time
from datetime import datetime
import pandas as pd
import streamlit as st
from src.ui.components import (
    page_header,
    section_header,
    metric_grid,
    glass_card,
    status_badge,
    spacer,
)

logger = logging.getLogger(__name__)

def render(db, run_pipeline_background, run_repair=None, get_diagnostics=None):
    """Render the redesigned Pipeline Control Center."""
    
    page_header(
        "System Intelligence Pulse",
        "Monitor active harvests, manage the research queue, and handle ingestion health."
    )

    # =====================================================================
    # GLOBAL CONTROLS
    # =====================================================================
    with glass_card():
        col_text, col_run, col_stop = st.columns([2, 1, 1])
        with col_text:
            st.markdown("### Global Process Control")
            st.caption("Synchronize all background intelligence gathering operations.")
        
        with col_run:
            if st.button("Resume All Scans", type="primary", use_container_width=True):
                count = db.set_global_control_state("RUNNING")
                st.toast(f"Signaled {count} scans to RESUME")
                st.rerun()
        
        with col_stop:
            if st.button("Halt Operations", type="secondary", use_container_width=True):
                count = db.set_global_control_state("STOPPED", "Global stop requested")
                st.toast(f"Signaled {count} scans to STOP")
                st.rerun()

    spacer("2rem")

    try:
        # TABS: Monitor, Control, Logs
        tab_monitor, tab_control, tab_maintenance, tab_logs = st.tabs([
            "Active Scans",
            "Control",
            "Vault Health",
            "System Logs"
        ])

        with tab_monitor:
            render_monitor_tab(db, run_pipeline_background)

        with tab_control:
            render_control_tab(db, run_pipeline_background)

        with tab_maintenance:
            render_maintenance_tab(db, run_repair, get_diagnostics)

        with tab_logs:
            render_logs_tab(db)

    except Exception as e:
        st.error(f"Pipeline Center error: {e}")
        logger.error(f"Pipeline Center error: {e}", exc_info=True)


def render_monitor_tab(db, run_pipeline_background):
    active_scans = db.get_active_scans()

    if not active_scans:
        st.info("No active scans running at the moment.")
    else:
        for scan in active_scans:
            with glass_card():
                processed = getattr(scan, 'total_processed', 0)
                discovered = getattr(scan, 'total_discovered', 0)
                
                col_info, col_metrics, col_status = st.columns([3, 2, 1])
                
                with col_info:
                    display_name = getattr(scan, 'channel_name', None) or f"Scan {getattr(scan, 'scan_id', 'unknown')[-8:]}"
                    st.markdown(f"**{display_name}**")
                    st.caption(getattr(scan, 'source_url', 'N/A')[:60])
                    
                    if discovered > 0:
                        progress = min(processed / discovered, 1.0)
                        st.progress(progress)
                        st.caption(f"{processed} of {discovered} processed")
                    else:
                        st.progress(0, text="Initializing...")
                
                with col_metrics:
                    mcols = st.columns(2)
                    with mcols[0]:
                        st.metric("Type", getattr(scan, 'scan_type', 'N/A'))
                    with mcols[1]:
                        pct = (processed / discovered * 100) if discovered > 0 else 0
                        st.metric("Progress", f"{pct:.0f}%")
                
                with col_status:
                    scan_id = getattr(scan, "scan_id", "")
                    control = db.get_control_state(scan_id)
                    db_status = control.status if control else "RUNNING"
                    
                    st.markdown(status_badge("primary" if db_status == "RUNNING" else "warning", db_status), unsafe_allow_html=True)
                    
                    if db_status == "RUNNING":
                        # Check if actually in memory
                        global_orch = getattr(st, "_global_orchestrators", {})
                        if scan_id not in global_orch and getattr(scan, "source_url", "") not in global_orch:
                            if st.button("Re-attach", key=f"reattach_{scan_id}", use_container_width=True):
                                run_pipeline_background(scan.source_url, db, scan_id=scan_id)
                                st.rerun()

    # Channel Health Leaderboard
    st.divider()
    section_header("Channel Integrity Leaderboard", icon="◈")
    
    channels = db.get_all_channels()
    if channels:
        for ch in channels:
            videos = db.get_videos_by_channel(ch.channel_id)
            if not videos: continue
            
            total = len(videos)
            done = sum(1 for v in videos if getattr(v, "checkpoint_stage", "") == "DONE")
            accepted = sum(1 for v in videos if getattr(v, "triage_status", "") == "ACCEPTED")
            rejected = sum(1 for v in videos if getattr(v, "triage_status", "") == "REJECTED")
            
            quality_score = (done / total * 0.4) + (accepted / max(1, accepted + rejected) * 0.6 if accepted + rejected > 0 else 0) * 100
            
            with st.expander(f"{ch.name[:30]} | Health: {quality_score:.0f}%", expanded=False):
                with glass_card():
                    metrics = [
                        {"value": total, "label": "Videos"},
                        {"value": done, "label": "Completed"},
                        {"value": accepted, "label": "Accepted"},
                        {"value": f"{quality_score:.1f}%", "label": "Quality", "glow": True}
                    ]
                    metric_grid(metrics, cols=4)
                    
                    if st.button("Deep Sync Channel", key=f"sync_{ch.channel_id}", use_container_width=True):
                        run_pipeline_background(ch.url, db)
                        st.rerun()
    else:
        st.caption("No channels discovered yet.")


def render_control_tab(db, run_pipeline_background):
    active_scans = db.get_active_scans()
    if not active_scans:
        st.info("No active scans to control.")
        return

    for idx, scan in enumerate(active_scans):
        scan_id = scan.scan_id
        control = db.get_control_state(scan_id)
        current_status = control.status if control else "RUNNING"
        
        with glass_card():
            col_info, col_prog, col_btn = st.columns([2, 1.5, 1.5])
            with col_info:
                st.markdown(f"**Target:** `{scan.channel_name or scan_id[-8:]}`")
                st.markdown(status_badge("info", current_status), unsafe_allow_html=True)
            
            with col_prog:
                prog = (scan.total_processed / max(scan.total_discovered, 1)) * 100
                st.metric("Progress", f"{prog:.1f}%")
            
            with col_btn:
                cb1, cb2 = st.columns(2)
                with cb1:
                    if current_status == "RUNNING":
                        if st.button("Pause", key=f"p_{scan_id}"):
                            db.set_control_state(scan_id, "PAUSED"); st.rerun()
                    else:
                        if st.button("Resume", key=f"r_{scan_id}"):
                            db.set_control_state(scan_id, "RUNNING"); st.rerun()
                with cb2:
                    if st.button("Stop", key=f"s_{scan_id}"):
                        db.set_control_state(scan_id, "STOPPED"); st.rerun()


def render_maintenance_tab(db, run_repair, get_diagnostics):
    if not get_diagnostics: return
    
    diag = get_diagnostics(db)
    section_header("Vault Integrity Diagnostics", icon="✦")
    
    metrics = [
        {"value": diag["total"], "label": "Videos"},
        {"value": f"{diag['pct_transcripts']}%", "label": "Transcripts"},
        {"value": f"{diag['pct_summaries']}%", "label": "Summaries"},
        {"value": f"{diag['pct_heatmaps']}%", "label": "Heatmaps", "glow": True}
    ]
    metric_grid(metrics, cols=4)
    
    spacer("1.5rem")
    if st.button("EXECUTE SYSTEM REPAIR", type="primary", use_container_width=True):
        if run_repair:
            run_repair()
            st.toast("Unified Vault Repair started!")
            st.rerun()


def render_logs_tab(db):
    section_header("Live Activity Feed", icon="◯")
    
    col1, col2 = st.columns([2, 1])
    with col2:
        log_limit = st.slider("Samples", 50, 500, 100)
    
    logs = db.get_logs(limit=log_limit)
    if logs:
        for log in reversed(logs):
            with st.container(border=False):
                st.markdown(f"""
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; padding: 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <span style="color: var(--accent-glow);">[{log.stage}]</span> 
                    <span style="color: white;">{log.message}</span>
                    <span style="color: var(--text-muted); float: right;">{log.timestamp[-8:]}</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No logs found.")
