"""Rejected Videos Review page for knowledgeVault-YT."""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(db, run_pipeline_background):
    """Render the Rejected Videos Review page."""
    st.markdown("""
    <div class="main-header">
        <h1>Rejected Videos Review</h1>
        <p>Review videos that were rejected by triage and manually force ingestion</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        rejected = db.get_videos_by_status_sorted(
            "REJECTED", order_by="updated_at DESC", limit=100
        )

        if not rejected:
            st.success("No rejected videos! Your triage is perfect.")
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
                if st.button("Force Accept All", type="primary"):
                    count = 0
                    for v in rejected:
                        if db.manual_override_rejected_video(v.video_id, "batch_force_accept"):
                            count += 1
                    st.success(f"Force-accepted {count}/{len(rejected)} videos")
                    st.rerun()
            with col2:
                if st.button("Export Rejection Report"):
                    csv_data = "Video ID,Title,Channel ID,Rejection Reason,Confidence,Upload Date\n"
                    for v in rejected:
                        csv_data += f'"{v.video_id}","{v.title}","{v.channel_id}","{v.triage_reason}",{v.triage_confidence},"{v.upload_date}"\n'
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name="rejected_videos_report.csv",
                        mime="text/csv"
                    )
            with col3:
                if st.button("Clear All Oldest"):
                    # Clear oldest 10 rejected videos
                    count = 0
                    for v in rejected[-10:]:
                        db.remove_video_from_queue(v.video_id)
                        count += 1
                    st.info(f"Cleared {count} oldest rejected videos")
                    st.rerun()

            st.markdown("---")
            st.markdown("### Individual Video Review")

            # Filter and sorting options
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_reason = st.selectbox(
                    "Filter by rejection reason",
                    ["All"] + sorted(list(rejection_reasons.keys())),
                    key="reason_filter"
                )
            with col2:
                sort_by = st.selectbox(
                    "Sort by",
                    ["Most Recent", "Highest Confidence", "Longest Duration", "Most Views"]
                )
            with col3:
                search_term = st.text_input("Search title/description", "")

            # Apply filters
            filtered = rejected
            if filter_reason != "All":
                filtered = [v for v in filtered if filter_reason in v.triage_reason]
            if search_term:
                search_lower = search_term.lower()
                filtered = [
                    v for v in filtered
                    if search_lower in v.title.lower() or search_lower in v.description.lower()
                ]

            # Apply sorting
            if sort_by == "Highest Confidence":
                filtered = sorted(filtered, key=lambda v: -v.triage_confidence)
            elif sort_by == "Longest Duration":
                filtered = sorted(filtered, key=lambda v: -v.duration_seconds)
            elif sort_by == "Most Views":
                filtered = sorted(filtered, key=lambda v: -v.view_count)

            st.info(f"Showing **{len(filtered)}** videos" + 
                   (f" ({len(filtered)}/{len(rejected)})" if filter_reason != "All" or search_term else ""))

            # Render individual video cards
            for idx, video in enumerate(filtered):
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                    with col1:
                        st.markdown(f"**{video.title}**")
                        st.image(
                            f"https://img.youtube.com/vi/{video.video_id}/mqdefault.jpg",
                            width=250,
                        )
                        
                        dur_min = video.duration_seconds // 60
                        dur_sec = video.duration_seconds % 60
                        st.caption(
                            f"Duration: {dur_min}m {dur_sec}s │ "
                            f"Views: {video.view_count:,} │ "
                            f"Uploaded: {video.upload_date}"
                        )
                        
                        if video.triage_reason:
                            st.warning(f"Reason: **{video.triage_reason}**")
                        
                        st.caption(f"Confidence: {video.triage_confidence:.0%}")
                        
                        if video.description:
                            with st.expander("View Description"):
                                st.text(video.description[:500] + "..." if len(video.description) > 500 else video.description)

                    with col2:
                        col_reason, col_btn = st.columns([1, 1])
                        with col_reason:
                            override_reason = st.text_input(
                                "Reason",
                                value="",
                                key=f"reason_{video.video_id}_{idx}",
                                help="Optional override reason",
                                placeholder="Why?"
                            )
                        with col_btn:
                            st.write("")  # Spacer
                            if st.button(
                                "Accept",
                                key=f"accept_{video.video_id}_{idx}",
                                help="Force accept and ingest",
                                use_container_width=True
                            ):
                                if db.manual_override_rejected_video(
                                    video.video_id, 
                                    override_reason or "manual_override"
                                ):
                                    st.success("Video force-accepted")
                                    st.rerun()
                                else:
                                    st.error("Failed to override")

                    with col3:
                        if st.button(
                            "Details",
                            key=f"details_{video.video_id}_{idx}",
                            use_container_width=True
                        ):
                            with st.expander("Full Details", expanded=True):
                                st.json({
                                    "video_id": video.video_id,
                                    "title": video.title,
                                    "channel_id": video.channel_id,
                                    "url": video.url,
                                    "duration_seconds": video.duration_seconds,
                                    "view_count": video.view_count,
                                    "upload_date": video.upload_date,
                                    "triage_status": video.triage_status,
                                    "triage_reason": video.triage_reason,
                                    "triage_confidence": video.triage_confidence,
                                    "language": video.language_iso,
                                    "tags": video.tags[:10] if video.tags else [],
                                })

                    with col4:
                        st.link_button(
                            "Watch",
                            video.url,
                            help="Watch on YouTube",
                            use_container_width=True
                        )

                    # Additional action: remove from queue
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(
                            "Skip & Delete",
                            key=f"skip_{video.video_id}_{idx}",
                            help="Permanently remove from review queue",
                            use_container_width=True
                        ):
                            db.delete_video_data(video.video_id, reason="manual_reject_purge")
                            st.info("Video removed from system")
                            st.rerun()
                    
                    with col_b:
                        if st.button(
                            "Retry Triage",
                            key=f"retry_{video.video_id}_{idx}",
                            help="Reset to DISCOVERED for re-evaluation",
                            use_container_width=True
                        ):
                            db.update_triage_status(
                                video.video_id,
                                "DISCOVERED",
                                "retry_triage_request"
                            )
                            st.info("Video reset to DISCOVERED - will be re-triaged")
                            st.rerun()

                    st.divider()

    except Exception as e:
        st.error(f"Failed to load Rejected Videos Review: {e}")
        logger.error(f"Rejected Videos Review error: {e}", exc_info=True)
