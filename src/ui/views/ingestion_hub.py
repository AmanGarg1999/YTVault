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
)


def render(db, run_pipeline_background, run_bulk_pipeline_background):
    """Render the unified Ingestion Hub with all intake operations."""
    
    page_header(
        "Ingestion Hub",
        "Start harvests, manage overrides, and reprocess content"
    )

    try:
        # =====================================================================
        # TABS: Start Harvest, Bulk Re-harvest, Reprocessing, Pending Review
        # =====================================================================
        tab_harvest, tab_bulk, tab_reprocess, tab_pending, tab_rejected = st.tabs([
            "Start Harvest",
            "Bulk Re-harvest",
            "Reprocessing",
            "Pending Review",
            "Rejected Videos"
        ])

        # =====================================================================
        # TAB 1: START NEW HARVEST
        # =====================================================================
        with tab_harvest:
            render_harvest_tab(db, run_pipeline_background)

        # =====================================================================
        # TAB 2: BULK RE-HARVEST - Multi-channel backfill
        # =====================================================================
        with tab_bulk:
            render_bulk_tab(db, run_bulk_pipeline_background)

        # =====================================================================
        # TAB 3: REPROCESSING - Force-accepted videos
        # =====================================================================
        with tab_reprocess:
            render_reprocess_tab(db, run_pipeline_background)

        # =====================================================================
        # TAB 4: PENDING REVIEW - Manual triage
        # =====================================================================
        with tab_pending:
            render_pending_tab(db)

        # =====================================================================
        # TAB 5: REJECTED VIDEOS - Override rejections
        # =====================================================================
        with tab_rejected:
            render_rejected_tab(db, run_pipeline_background)

    except Exception as e:
        st.error(f"Ingestion Hub error: {e}")
        logger.error(f"Ingestion Hub error: {e}", exc_info=True)


def render_harvest_tab(db, run_pipeline_background):
    """Tab 1: Start new ingestion jobs."""
    
    st.markdown("### Start New Harvest")
    
    url = st.text_input(
        "YouTube URL",
        placeholder="https://youtube.com/@channel or playlist/video URL",
        help="Paste a YouTube channel, playlist, or single video URL",
        key="harvest_url_input"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        start_btn = st.button("Start Harvest", type="primary", use_container_width=True, key="start_harvest_btn_ingestion")

    if start_btn and url:
        try:
            from src.ingestion.discovery import parse_youtube_url
            parsed = parse_youtube_url(url)
            
            col_msg, col_status = st.columns([3, 1])
            with col_msg:
                st.success(f"Ingestion queued for **{parsed.url_type}**: {url}")
            
            with col_status:
                st.info(f"Type: {parsed.url_type}")

            run_pipeline_background(url, db)
            st.info("Harvest started in background. Monitor progress in **Pipeline Center**.")
            st.toast("Harvest started!")
            time.sleep(1)
            st.rerun()

        except ValueError as e:
            st.error(f"Invalid URL: {e}")
        except Exception as e:
            st.error(f"Failed to start harvest: {e}")

    # Show recent harvests
    st.markdown("---")
    st.markdown("### Recent Harvest History")
    
    try:
        scans = db.get_active_scans()
        if scans:
            scan_data = []
            for scan in scans[:10]:  # Show last 10
                scan_data.append({
                    "Scan ID": scan.scan_id,
                    "Source": scan.source_url[:60] + "..." if len(scan.source_url) > 60 else scan.source_url,
                    "Type": scan.scan_type,
                    "Discovered": scan.total_discovered,
                    "Processed": scan.total_processed,
                    "Status": scan.status,
                })
            
            df = pd.DataFrame(scan_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No active harvests.")
    except Exception as e:
        st.warning(f"Could not load harvest history: {e}")


def render_pending_tab(db):
    """Tab 2: Ambiguity Queue - Manual triage."""
    
    st.markdown("### Videos Pending Manual Review")
    
    pending = db.get_videos_by_status("PENDING_REVIEW", limit=50)

    if not pending:
        st.success("Queue is empty! All videos have been classified.")
    else:
        # Summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pending Videos", len(pending))
        with col2:
            avg_confidence = sum(v.triage_confidence for v in pending) / len(pending) if pending else 0
            st.metric("Avg Confidence", f"{avg_confidence:.0%}")
        with col3:
            languages = {}
            for v in pending:
                lang = getattr(v, "language_iso", "en")
                languages[lang] = languages.get(lang, 0) + 1
            st.metric("Languages", len(languages))

        st.markdown("---")

        # Batch actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Accept All", type="primary", key="batch_accept_pending"):
                for v in pending:
                    db.update_triage_status(v.video_id, "ACCEPTED", "manual_batch_accept")
                st.success(f"Accepted {len(pending)} videos")
                time.sleep(0.5)
                st.rerun()
        with col2:
            if st.button("Reject All", key="batch_reject_pending"):
                for v in pending:
                    db.update_triage_status(v.video_id, "REJECTED", "manual_batch_reject")
                st.success(f"Rejected {len(pending)} videos")
                time.sleep(0.5)
                st.rerun()

        st.markdown("---")
        st.markdown("### Individual Reviews")

        for i, video in enumerate(pending[:20]):  # Show first 20
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

                with col1:
                    st.markdown(f"**{video.title}**")
                    
                    # Show language if not English
                    lang = getattr(video, "language_iso", "en")
                    if lang != "en":
                        st.caption(f"Language: {LANGUAGE_MAP.get(lang, lang.upper())}")
                    
                    try:
                        st.image(
                            f"https://img.youtube.com/vi/{video.video_id}/mqdefault.jpg",
                            width=200,
                        )
                    except:
                        pass
                    
                    dur_min = video.duration_seconds // 60
                    dur_sec = video.duration_seconds % 60
                    st.caption(
                        f"Duration: {dur_min}m {dur_sec}s │ "
                        f"Views: {video.view_count:,} │ "
                        f"Confidence: {video.triage_confidence:.0%}"
                    )
                    if video.triage_reason:
                        st.caption(f"Reason: {video.triage_reason}")

                with col2:
                    if st.button("Accept", key=f"acc_pending_{i}_{video.video_id}",
                                 help="Accept as knowledge-dense"):
                        db.update_triage_status(
                            video.video_id, "ACCEPTED", "manual_accept", 1.0
                        )
                        st.rerun()

                with col3:
                    if st.button("Reject", key=f"rej_pending_{i}_{video.video_id}",
                                 help="Reject as noise"):
                        db.update_triage_status(
                            video.video_id, "REJECTED", "manual_reject", 1.0
                        )
                        st.rerun()

                with col4:
                    st.link_button("Watch", video.url, help="Watch on YouTube")


def render_rejected_tab(db, run_pipeline_background):
    """Tab 3: Rejected Videos - Override and force accept."""
    
    st.markdown("### Rejected Videos Review")
    
    rejected = db.get_videos_by_status_sorted(
        "REJECTED", order_by="updated_at DESC", limit=100
    )

    if not rejected:
        st.success("No rejected videos! Your triage is perfect.")
    else:
        # Statistics section
        col1, col2, col3 = st.columns(3)
        
        rejection_reasons = {}
        for v in rejected:
            reason = v.triage_reason.split(':')[0] if v.triage_reason else "unknown"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        with col1:
            st.metric("Total Rejected", len(rejected))
        with col2:
            avg_confidence = sum(v.triage_confidence for v in rejected) / len(rejected)
            st.metric("Avg Confidence", f"{avg_confidence:.0%}")
        with col3:
            st.metric("Rejection Reasons", len(rejection_reasons))

        # Show rejection reason breakdown
        if rejection_reasons:
            st.markdown("**Rejection Reasons Breakdown:**")
            reason_cols = st.columns(min(5, len(rejection_reasons)))
            for i, (reason, count) in enumerate(sorted(
                rejection_reasons.items(), key=lambda x: -x[1]
            )[:5]):
                with reason_cols[i % len(reason_cols)]:
                    st.metric(reason, count)

        st.markdown("---")

        # Batch actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Force Accept All", type="primary", key="batch_override_all"):
                count = 0
                for v in rejected:
                    db.manual_override_rejected_video(v.video_id, db_session=None)
                    count += 1
                st.success(f"{count} rejected videos marked for reprocessing!")
                time.sleep(0.5)
                st.rerun()
        with col2:
            if st.button("Permanently Reject All", key="batch_permanent_reject"):
                for v in rejected:
                    db.conn.execute(
                        "UPDATE videos SET triage_status = 'PERMANENTLY_REJECTED' WHERE video_id = ?",
                        (v.video_id,)
                    )
                    db.conn.commit()
                st.warning(f"Permanently rejected {len(rejected)} videos")
                time.sleep(0.5)
                st.rerun()

        st.markdown("---")
        st.markdown("### Individual Overrides")

        for i, video in enumerate(rejected[:20]):  # Show first 20
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 1, 1])

                with col1:
                    st.markdown(f"**{video.title}**")
                    
                    # Show language if not English
                    lang = getattr(video, "language_iso", "en")
                    if lang != "en":
                        st.caption(f"Language: {LANGUAGE_MAP.get(lang, lang.upper())}")
                    
                    st.caption(f"Reason: {video.triage_reason}")
                    st.caption(f"Confidence: {video.triage_confidence:.0%}")

                with col2:
                    if st.button("Override", key=f"override_{i}_{video.video_id}",
                                 help="Force accept for reprocessing"):
                        db.manual_override_rejected_video(video.video_id, db_session=None)
                        st.success("Marked for reprocessing!")
                        time.sleep(0.5)
                        st.rerun()

                with col3:
                    st.link_button("Watch", video.url, help="Watch on YouTube")


def render_reprocess_tab(db, run_pipeline_background):
    """Tab 4: Reprocessing - Force-accepted and manual overrides."""
    
    st.markdown("### Videos Ready for Reprocessing")
    
    manually_overridden = db.get_manually_overridden_videos(limit=50)
    
    if not manually_overridden:
        st.info("No videos waiting for reprocessing.")
    else:
        col1, col2 = st.columns([2, 2])
        with col1:
            st.info(f"**{len(manually_overridden)}** videos ready to be re-ingested after manual override")
        with col2:
            if st.button("Process All", type="primary", key="process_all_overridden"):
                from src.pipeline.orchestrator import PipelineOrchestrator
                orchestrator = PipelineOrchestrator()
                try:
                    count = orchestrator.process_manually_overridden_videos()
                    st.success(f"Processing {count} manually-overridden videos in background")
                    st.toast(f"Processing {count} videos!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to process: {e}")
                finally:
                    orchestrator.close()

        st.markdown("---")
        st.markdown("### Individual Reprocessing")

        for i, video in enumerate(manually_overridden[:20]):
            cols = video_card(video, key_prefix=f"reproc_{i}")
            if cols:
                with cols[3]:
                    if st.button("Process", key=f"process_single_{i}_{video.video_id}"):
                        from src.pipeline.orchestrator import PipelineOrchestrator
                        orchestrator = PipelineOrchestrator()
                        try:
                            orchestrator._resume_video(video)
                            st.success(f"Processing {video.title[:40]}...")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                        finally:
                            orchestrator.close()


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


def render_bulk_tab(db, run_bulk_pipeline_background):
    """Tab 5: Bulk Re-harvest - Select multiple channels for backfill."""
    
    st.markdown("### Bulk Channel Re-harvest")
    st.info("Select channels to re-scan. This will refresh likes, comments, and follower counts for all videos.")
    
    channels = db.get_all_channels()
    if not channels:
        st.warning("No channels found in the database. Start a harvest first.")
        return
        
    selected_channels = st.multiselect(
        "Select Channels to Re-harvest",
        options=channels,
        format_func=lambda c: f"{c.name} ({c.channel_id})",
        help="Select one or more channels to add to the bulk harvesting queue."
    )
    
    force_refresh = st.checkbox(
        "Force Metadata Refresh", 
        value=True,
        help="If checked, the pipeline will re-fetch metadata for ALL videos, even if they are already in the database."
    )
    
    if st.button("Start Bulk Harvest", type="primary", disabled=not selected_channels):
        urls = [c.url for c in selected_channels]
        run_bulk_pipeline_background(urls, db, force_metadata_refresh=force_refresh)
        st.success(f"Bulk harvest started for {len(urls)} channels!")
        st.info("Monitor the sequential progress in the **Pipeline Center** logs.")
        st.toast("Bulk harvest started!")
        time.sleep(1)
        st.rerun()

    # Show channel stats
    if selected_channels:
        st.markdown("---")
        st.markdown("#### Selected Channel Summary")
        stats_data = []
        for c in selected_channels:
            stats_data.append({
                "Channel": c.name,
                "Followers": f"{c.follower_count:,}",
                "Videos": c.total_videos,
                "Language": c.language_iso
            })
        st.table(stats_data)
