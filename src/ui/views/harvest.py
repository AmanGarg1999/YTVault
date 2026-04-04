"""Ingestion Hub - Unified intake, triage, and override management."""

import logging
import time

import streamlit as st

logger = logging.getLogger(__name__)


def render(db, run_pipeline_background):
    """Render the unified Ingestion Hub with all intake operations."""
    
    st.markdown("""
    <div class="main-header">
        <h1>🌾 Ingestion Hub</h1>
        <p>Start harvests, manage triage queue, and override rejections</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        # =====================================================================
        # TABS: Start Scan, Pending Review, Rejected, Force-Accepted
        # =====================================================================
        tab_start, tab_pending, tab_rejected, tab_overrides = st.tabs([
            "🚀 Start Scan",
            "📋 Pending Review",
            "❌ Rejected Videos",
            "⚡ Force-Accepted"
        ])

        # =====================================================================
        # TAB 1: START NEW SCAN
        # =====================================================================
        with tab_start:
            _render_start_scan_tab(db, run_pipeline_background)

        # =====================================================================
        # TAB 2: PENDING REVIEW (TRIAGE QUEUE)
        # =====================================================================
        with tab_pending:
            _render_pending_review_tab(db)

        # =====================================================================
        # TAB 3: REJECTED VIDEOS (OVERRIDE)
        # =====================================================================
        with tab_rejected:
            _render_rejected_videos_tab(db, run_pipeline_background)

        # =====================================================================
        # TAB 4: FORCE-ACCEPTED VIDEOS (MANUAL OVERRIDES)
        # =====================================================================
        with tab_overrides:
            _render_forcibly_accepted_tab(db, run_pipeline_background)

    except Exception as e:
        st.error(f"Ingestion Hub error: {e}")
        logger.error(f"Ingestion Hub error: {e}", exc_info=True)


def _render_start_scan_tab(db, run_pipeline_background):
    """Tab 1: Start a new ingestion scan."""
    
    st.markdown("### 🚀 Start New Ingestion Scan")
    st.markdown("""
    Paste a YouTube URL to begin ingestion. Supports:
    - **Channels:** `youtube.com/@channelname` or `youtube.com/channel/XXXX`
    - **Playlists:** `youtube.com/playlist?list=XXXX`
    - **Videos:** `youtube.com/watch?v=XXXX` or `youtu.be/XXXX`
    """)
    
    url = st.text_input(
        "YouTube URL",
        placeholder="https://youtube.com/@channel or https://youtube.com/playlist?list=...",
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
            st.info("Pipeline started in background. Monitor progress in the **📊 Pipeline Center**.")
            st.toast("Harvest started!", icon="🚀")
            time.sleep(1)
            st.rerun()

        except ValueError as e:
            st.error(f"Invalid URL: {e}")
        except Exception as e:
            st.error(f"Failed to start harvest: {e}")


def _render_pending_review_tab(db):
    """Tab 2: Manual triage of uncertain videos (Ambiguity Queue)."""
    
    st.markdown("### 📋 Ambiguity Queue - Videos Pending Manual Review")
    
    pending = db.get_videos_by_status("PENDING_REVIEW", limit=50)

    if not pending:
        st.success("🎉 Queue is empty! All videos have been classified.")
    else:
        st.info(f"**{len(pending)}** videos awaiting review")

        # Batch actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ Accept All", type="primary"):
                for v in pending:
                    db.update_triage_status(v.video_id, "ACCEPTED", "manual_batch_accept")
                st.success(f"Accepted {len(pending)} videos")
                st.rerun()
        with col2:
            if st.button("❌ Reject All"):
                for v in pending:
                    db.update_triage_status(v.video_id, "REJECTED", "manual_batch_reject")
                st.success(f"Rejected {len(pending)} videos")
                st.rerun()

        st.markdown("---")

        # Display pending videos
        for video in pending:
            with st.container(border=True):
                col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])

                with col1:
                    # Language badge
                    lang_badge = f"🌐 {_get_language_name(video.language_iso)}"
                    if video.needs_translation:
                        lang_badge += " (needs translation)"
                    
                    st.markdown(f"**{video.title}**")
                    st.caption(lang_badge)
                    st.image(
                        f"https://img.youtube.com/vi/{video.video_id}/mqdefault.jpg",
                        width=200,
                    )
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
                    if st.button("✅", key=f"acc_{video.video_id}",
                                 help="Accept as knowledge-dense"):
                        db.update_triage_status(
                            video.video_id, "ACCEPTED", "manual_accept", 1.0
                        )
                        st.rerun()

                with col3:
                    if st.button("❌", key=f"rej_{video.video_id}",
                                 help="Reject as noise"):
                        db.update_triage_status(
                            video.video_id, "REJECTED", "manual_reject", 1.0
                        )
                        st.rerun()

                with col4:
                    st.link_button("▶️", video.url, help="Watch on YouTube")
                
                with col5:
                    st.caption("")  # Placeholder


def _render_rejected_videos_tab(db, run_pipeline_background):
    """Tab 3: Review and force-accept rejected videos."""
    
    st.markdown("### 🚫 Rejected Videos Review - Override Rejections")
    
    rejected = db.get_videos_by_status_sorted(
        "REJECTED", order_by="updated_at DESC", limit=100
    )

    if not rejected:
        st.success("🎉 No rejected videos! Your triage is perfect.")
    else:
        st.info(f"**{len(rejected)}** videos have been rejected by triage")

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
            cols = st.columns(len(rejection_reasons))
            for i, (reason, count) in enumerate(sorted(
                rejection_reasons.items(), key=lambda x: -x[1]
            )[:5]):
                with cols[i % len(cols)]:
                    st.metric(reason, count)

        st.markdown("---")

        # Batch actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ Force Accept All", type="primary"):
                for v in rejected:
                    db.update_triage_status(
                        v.video_id, "ACCEPTED", "force_accept_all", 1.0
                    )
                st.success(f"Force-accepted {len(rejected)} videos")
                st.rerun()
        with col2:
            if st.button("🔄 Reprocess All"):
                from src.pipeline.orchestrator import PipelineOrchestrator
                orchestrator = PipelineOrchestrator()
                try:
                    count = 0
                    for v in rejected:
                        db.update_triage_status(
                            v.video_id, "ACCEPTED", "force_accept_reprocess", 1.0
                        )
                        orchestrator._resume_video(v)
                        count += 1
                    st.success(f"Reprocessing {count} videos")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
                finally:
                    orchestrator.close()

        st.markdown("---")

        # Display rejected videos
        for i, video in enumerate(rejected[:20]):
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 1, 1])

                with col1:
                    lang_badge = f"🌐 {_get_language_name(video.language_iso)}"
                    st.markdown(f"**{video.title}**")
                    st.caption(lang_badge)
                    st.caption(f"Reason: {video.triage_reason}")

                with col2:
                    if st.button("✅ Accept", key=f"force_acc_{i}_{video.video_id}"):
                        db.update_triage_status(
                            video.video_id, "ACCEPTED", "force_accept", 1.0
                        )
                        st.rerun()

                with col3:
                    st.link_button("▶️", video.url, help="Watch")


def _render_forcibly_accepted_tab(db, run_pipeline_background):
    """Tab 4: Manage force-accepted videos waiting for reprocessing."""
    
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

        st.markdown("---")

        # Show the manually-overridden videos
        for i, v in enumerate(manually_overridden[:10]):
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    lang_badge = f"🌐 {_get_language_name(v.language_iso)}"
                    st.markdown(f"🔄 **{v.title[:60]}...** (Manual Override)")
                    st.caption(lang_badge)
                
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
                
                with col3:
                    st.link_button("▶️", v.url, help="Watch")
    else:
        st.info("No manually-overridden videos waiting for processing.")


def _get_language_name(lang_code: str) -> str:
    """Get full language name from ISO code."""
    language_map = {
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
    return language_map.get(lang_code, lang_code.upper())
