"""Harvest Manager page for knowledgeVault-YT."""

import logging
import time

import streamlit as st

logger = logging.getLogger(__name__)


def render(db, run_pipeline_background):
    """Render the Harvest Manager page."""
    st.markdown("""
    <div class="main-header">
        <h1>🌾 Harvest Manager</h1>
        <p>Start new ingestion jobs from YouTube channels, playlists, or videos</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        url = st.text_input(
            "YouTube URL",
            placeholder="https://youtube.com/@channel or playlist/video URL",
            help="Paste a YouTube channel, playlist, or single video URL",
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            start_btn = st.button("🚀 Start Harvest", type="primary", use_container_width=True, key="start_harvest_btn")

        if start_btn and url:
            try:
                from src.ingestion.discovery import parse_youtube_url
                parsed = parse_youtube_url(url)
                st.success(f"🚀 Ingestion queued for **{parsed.url_type}**: {url}")

                run_pipeline_background(url, db)
                st.info("Pipeline started in background. Monitor progress in the **📊 Pipeline Monitor**.")
                st.toast("Harvest started!", icon="🚀")
                time.sleep(1)
                st.rerun()

            except ValueError as e:
                st.error(f"Invalid URL: {e}")
            except Exception as e:
                st.error(f"Failed to start harvest: {e}")

        # Resume section
        st.markdown("---")
        st.markdown("### 🔄 Resume Interrupted Scan")

        scans = db.get_active_scans()
        if scans:
            for scan in scans:
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**{scan.scan_id}** — {scan.source_url[:50]}...")
                with col2:
                    st.markdown(f"{scan.total_processed}/{scan.total_discovered} videos")
                with col3:
                    is_active = scan.scan_id in getattr(st, "_global_orchestrators", {})
                    if is_active:
                        st.button("Running...", key=f"active_{scan.scan_id}", disabled=True)
                    elif st.button("Resume", key=f"resume_{scan.scan_id}"):
                        run_pipeline_background(scan.source_url, db, scan_id=scan.scan_id)
                        st.success(f"Resumed scan {scan.scan_id}")
                        st.rerun()
        else:
            st.info("No interrupted scans to resume.")
    except Exception as e:
        st.error(f"Failed to load Harvest Manager: {e}")
        logger.error(f"Harvest Manager error: {e}", exc_info=True)
