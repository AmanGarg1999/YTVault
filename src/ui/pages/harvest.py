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

        # Manually overridden videos section
        st.markdown("---")
        st.markdown("### ⚡ Force-Accepted Videos (Manual Overrides)")

        manually_overridden = db.get_manually_overridden_videos(limit=20)
        if manually_overridden:
            col1, col2 = st.columns([2, 2])
            with col1:
                st.info(f"**{len(manually_overridden)}** videos waiting to be re-ingested after manual override")
            with col2:
                if st.button("🔄 Process All Force-Accepted Videos", key="process_overridden"):
                    from src.pipeline.orchestrator import PipelineOrchestrator
                    orchestrator = PipelineOrchestrator()
                    try:
                        count = orchestrator.process_manually_overridden_videos()
                        st.success(f"Processing {count} manually-overridden videos in background")
                        st.toast(f"Processing {count} videos!", icon="⚡")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to process: {e}")
                    finally:
                        orchestrator.close()

            # Show the manually-overridden videos
            for i, v in enumerate(manually_overridden[:5]):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"🔄 **{v.title[:60]}...** (Manual Override)")
                with col2:
                    if st.button("Process", key=f"process_single_{i}_{v.video_id}"):
                        from src.pipeline.orchestrator import PipelineOrchestrator
                        orchestrator = PipelineOrchestrator()
                        try:
                            orchestrator._resume_video(v)
                            st.success(f"Processing {v.title[:40]}...")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                        finally:
                            orchestrator.close()
        else:
            st.info("No manually-overridden videos waiting for processing.")

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
