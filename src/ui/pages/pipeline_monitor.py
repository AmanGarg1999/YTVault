import logging
import time

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def render(db, run_pipeline_background):
    """Render the Pipeline Monitor page."""
    st.markdown("""
    <div class="main-header">
        <h1>📊 Pipeline Monitor</h1>
        <p>Real-time pipeline progress and channel health tracking</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        st.markdown("### 🔄 Active Ingestion Scans")
        active_scans = db.get_active_scans()

        if active_scans:
            for scan in active_scans:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(f"**Scan ID:** `{getattr(scan, 'scan_id', 'unknown')}`")
                        st.caption(f"📍 {getattr(scan, 'source_url', 'N/A')}")
                    with c2:
                        processed = getattr(scan, 'total_processed', 0)
                        discovered = getattr(scan, 'total_discovered', 0)
                        st.metric("Progress", f"{processed}/{discovered}")
                    with c3:
                        # Defensive check for global orchestrators
                        global_orch = getattr(st, "_global_orchestrators", {})
                        is_running = (getattr(scan, "scan_id", "") in global_orch or
                                      getattr(scan, "source_url", "") in global_orch)
                        status_label = "🟢 RUNNING" if is_running else "🟡 PAUSED/QUEUED"
                        st.markdown(f"**Status:** {status_label}")

            if st.button("🔄 Refresh Status", type="secondary"):
                st.rerun()
        else:
            st.info("No active scans running at the moment.")

        st.markdown("---")
        try:
            stats = db.get_pipeline_stats()
        except Exception as e:
            st.warning(f"Metadata stats temporarily unavailable: {e}")
            stats = {}

        stages = [
            ("📥 Discovered", stats.get("discovered", 0) + stats.get("accepted", 0)
             + stats.get("rejected", 0) + stats.get("pending_review", 0)),
            ("✅ Triage Passed", stats.get("accepted", 0)),
            ("📝 Transcripts", stats.get("transcript_fetched", 0)),
            ("🧹 Refined", stats.get("refined", 0)),
            ("🔍 Indexed", stats.get("done", 0)),
        ]

        st.markdown("### 📊 Overall Pipeline Health")
        cols = st.columns(len(stages))
        for i, (label, count) in enumerate(stages):
            with cols[i]:
                st.metric(label, count)

        # Progress bars for main flow
        for label, count in stages:
            total = stats.get("total_videos", 1) or 1
            pct = min(1.0, count / total)
            st.progress(pct, text=f"{label}: {count}")

        # Channel health breakdown
        st.markdown("### 📺 Channel Health")
        try:
            channels = db.get_all_channels()
        except Exception:
            channels = []

        if channels:
            for ch in channels:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    try:
                        videos = db.get_videos_by_channel(ch.channel_id)
                        total = len(videos)
                        done = sum(1 for v in videos if getattr(v, "checkpoint_stage", "") == "DONE")
                        
                        with c1:
                            st.markdown(f"**{getattr(ch, 'name', 'Unknown')}**")
                            st.caption(f"📍 {getattr(ch, 'url', 'N/A')}")
                        with c2:
                            st.metric("Total/Done", f"{total}/{done}")
                        with c3:
                            last_scan = getattr(ch, "last_scanned_at", "Never")
                            st.caption(f"Last Scanned:\n{last_scan}")
                        with c4:
                            if st.button("🌾 Quick Harvest", key=f"harvest_{ch.channel_id}", use_container_width=True):
                                if ch.url:
                                    run_pipeline_background(ch.url, db)
                                    st.success(f"Queued re-harvest for {ch.name}")
                                    st.toast(f"Harvest started: {ch.name}")
                                    time.sleep(0.5)
                                    st.rerun()
                    except Exception as e:
                        st.error(f"Error loading channel {ch.channel_id}: {e}")
        else:
            st.info("No channels ingested yet.")
    except Exception as e:
        st.error(f"Failed to load Pipeline Monitor: {e}")
        logger.error(f"Pipeline Monitor error: {e}", exc_info=True)
