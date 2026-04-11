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
    action_confirmation_dialog,
    failure_confirmation_dialog,
)

def render(db, run_pipeline_background, run_bulk_pipeline_background):
    """Render the redesigned unified Ingestion Hub."""
    
    page_header(
        "Ingestion Hub",
        "Control content intake, manage metadata overrides, and orchestrate research harvests."
    )

    try:
        # TABS: Start Harvest, Bulk Re-harvest
        tab_harvest, tab_bulk = st.tabs([
            "Quick Harvest",
            "Bulk Operations"
        ])

        with tab_harvest:
            render_harvest_tab(db, run_pipeline_background)

        with tab_bulk:
            render_bulk_tab(db, run_bulk_pipeline_background)

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
                if not url:
                    failure_confirmation_dialog(
                        "Target Required",
                        "The ingestion engine needs a valid YouTube URL to initiate the discovery phase.",
                        retry_callback=None
                    )
                else:
                    with st.spinner("Initializing research harvest..."):
                        try:
                            if "youtube.com" not in url and "youtu.be" not in url:
                                raise ValueError("Invalid YouTube URL provided. Must be a youtube.com or youtu.be link.")
                            run_pipeline_background(url, db)
                            action_confirmation_dialog(
                                "Harvest Initialized",
                                f"Target URL: {url[:60]}\n\nScanning and processing background tasks has started.",
                                icon="✦"
                            )
                        except Exception as e:
                            failure_confirmation_dialog(
                                "Harvest Failed to Initialize",
                                str(e),
                                retry_callback=lambda: run_pipeline_background(url, db),
                                queue_callback=lambda: db.add_to_user_queue("URL", url, str(e))
                            )
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


def render_bulk_tab(db, run_bulk_pipeline_background):
    section_header("Strategic Bulk Re-harvest", icon="◈")
    
    with glass_card():
        channels = db.get_all_channels()
        selected = st.multiselect("Select Targets", channels, format_func=lambda c: c.name)
        
        if st.button("Ignite Bulk Harvest", type="primary", disabled=not selected):
            urls = [c.url for c in selected]
            try:
                run_bulk_pipeline_background(urls, db, force_metadata_refresh=True)
                action_confirmation_dialog(
                    "Bulk Harvest Ignited",
                    f"Processing {len(urls)} channels sequentially in the background.",
                    icon="◈"
                )
            except Exception as e:
                failure_confirmation_dialog(
                    "Bulk Harvest Failed",
                    str(e),
                    retry_callback=lambda: run_bulk_pipeline_background(urls, db, force_metadata_refresh=True),
                    queue_callback=lambda: [db.add_to_user_queue("URL", u, str(e)) for u in urls]
                )
