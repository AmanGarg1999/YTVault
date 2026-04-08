"""Ingestion Hub - Intelligence Core Redesign."""

import streamlit as st
import logging
import pandas as pd
import time

logger = logging.getLogger(__name__)

from src.ui.components import (
    page_header,
    section_header,
    video_card,
    spacer,
    info_card,
    success_card,
    glass_card,
    status_badge,
    metric_grid,
)

def render(db, run_pipeline_background, run_bulk_pipeline_background):
    """Render the redesigned unified Ingestion Hub."""
    
    page_header(
        "Ingestion Hub",
        "Control content intake, manage metadata overrides, and orchestrate research harvests."
    )

    try:
        # TABS: Start Harvest, Bulk Re-harvest, Reprocessing, Pending Review
        tab_harvest, tab_bulk, tab_reprocess, tab_pending, tab_rejected = st.tabs([
            "Quick Harvest",
            "Bulk Operations",
            "Force-Reprocess",
            "Triage Queue",
            "Rejected Intel"
        ])

        with tab_harvest:
            render_harvest_tab(db, run_pipeline_background)

        with tab_bulk:
            render_bulk_tab(db, run_bulk_pipeline_background)

        with tab_reprocess:
            render_reprocess_tab(db, run_pipeline_background)

        with tab_pending:
            render_pending_tab(db)

        with tab_rejected:
            render_rejected_tab(db, run_pipeline_background)

    except Exception as e:
        st.error(f"Ingestion Hub error: {e}")
        logger.error(f"Ingestion Hub error: {e}", exc_info=True)


def render_harvest_tab(db, run_pipeline_background):
    section_header("Quick Intake", icon="✦")
    
    with glass_card():
        url = st.text_input(
            "Target URL",
            placeholder="Paste YouTube channel, playlist, or video URL...",
            key="harvest_url_input_hub"
        )
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Start Harvest", type="primary", use_container_width=True):
                if url:
                    run_pipeline_background(url, db)
                    st.toast("Harvest initiated!")
                    time.sleep(1)
                    st.rerun()

    spacer("2rem")
    section_header("Recent Intake History", icon="◯")
    
    scans = db.get_active_scans()
    if scans:
        with glass_card():
            scan_data = []
            for scan in scans[:10]:
                scan_data.append({
                    "Target": scan.channel_name or scan.source_url[:40],
                    "Type": scan.scan_type,
                    "Discovered": scan.total_discovered,
                    "Processed": scan.total_processed,
                    "State": scan.status,
                })
            st.dataframe(pd.DataFrame(scan_data), use_container_width=True, hide_index=True)
    else:
        info_card("System Synchronized", "No active harvest tasks in the last 24 hours.")


def render_pending_tab(db):
    section_header("Ambiguity Triage Queue", icon="◯")
    
    pending = db.get_videos_by_status("PENDING_REVIEW", limit=50)

    if not pending:
        success_card("Pipeline Optimized", "The automated triage engine has classified all available content.")
    else:
        avg_conf = sum(v.triage_confidence for v in pending) / len(pending)
        metrics = [
            {"value": len(pending), "label": "Pending"},
            {"value": f"{avg_conf:.0%}", "label": "Avg Confidence", "glow": avg_conf < 0.6},
            {"value": "MANUAL", "label": "Level"}
        ]
        metric_grid(metrics, cols=3)
        spacer("1.5rem")

        # Batch actions
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Mass Accept All", type="primary", use_container_width=True):
                for v in pending: db.update_triage_status(v.video_id, "ACCEPTED", "bulk")
                st.rerun()
        
        spacer("1rem")
        for i, video in enumerate(pending[:15]):
            cols = video_card(video, key_prefix=f"pending_{i}")
            if cols:
                with cols[0]:
                    if st.button("Accept", key=f"ac_{i}"):
                        db.update_triage_status(video.video_id, "ACCEPTED", "manual"); st.rerun()
                with cols[1]:
                    if st.button("Reject", key=f"rj_{i}"):
                        db.update_triage_status(video.video_id, "REJECTED", "manual"); st.rerun()


def render_rejected_tab(db, run_pipeline_background):
    section_header("Rejected Intelligence Review", icon="⚠")
    
    rejected = db.get_videos_by_status_sorted("REJECTED", order_by="updated_at DESC", limit=50)

    if not rejected:
        success_card("Clean Vault", "No noise detected in the last scan.")
    else:
        metrics = [
            {"value": len(rejected), "label": "Suppressed"},
            {"value": "NOISE", "label": "Filter Level"}
        ]
        metric_grid(metrics, cols=2)
        
        spacer("1.5rem")
        for i, video in enumerate(rejected[:15]):
            cols = video_card(video, key_prefix=f"rej_{i}")
            if cols:
                with cols[0]:
                    if st.button("Override", key=f"ov_{i}"):
                        db.manual_override_rejected_video(video.video_id); st.rerun()


def render_reprocess_tab(db, run_pipeline_background):
    section_header("Forced Reprocessing Tunnel", icon="✦")
    
    manually_overridden = db.get_manually_overridden_videos(limit=50)
    if not manually_overridden:
        info_card("Ready to Intake", "No videos currently marked for manual override.")
    else:
        with glass_card():
            st.info(f"**{len(manually_overridden)}** videos staged for override.")
            if st.button("Execute Bulk Reprocess", type="primary", use_container_width=True):
                from src.pipeline.orchestrator import PipelineOrchestrator
                orchestrator = PipelineOrchestrator()
                orchestrator.process_manually_overridden_videos()
                orchestrator.close()
                st.rerun()


def render_bulk_tab(db, run_bulk_pipeline_background):
    section_header("Strategic Bulk Re-harvest", icon="◈")
    
    with glass_card():
        channels = db.get_all_channels()
        selected = st.multiselect("Select Targets", channels, format_func=lambda c: c.name)
        
        if st.button("Ignite Bulk Harvest", type="primary", disabled=not selected):
            urls = [c.url for c in selected]
            run_bulk_pipeline_background(urls, db, force_metadata_refresh=True)
            st.toast("Bulk harvest ignited!")
            st.rerun()
