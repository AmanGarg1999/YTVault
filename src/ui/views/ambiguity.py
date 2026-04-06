"""Ambiguity Queue page for knowledgeVault-YT."""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(db):
    """Render the Ambiguity Queue page."""
    st.markdown("""
    <div class="main-header">
        <h1>Ambiguity Queue</h1>
        <p>Review and classify videos that couldn't be auto-triaged</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        pending = db.get_videos_by_status("PENDING_REVIEW", limit=50)

        if not pending:
            st.success("Queue is empty! All videos have been classified.")
        else:
            st.info(f"**{len(pending)}** videos awaiting review")

            # Batch actions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Accept All", type="primary"):
                    for v in pending:
                        db.update_triage_status(v.video_id, "ACCEPTED", "manual_batch_accept")
                    st.success(f"Accepted {len(pending)} videos")
                    st.rerun()
            with col2:
                if st.button("Reject All"):
                    for v in pending:
                        db.update_triage_status(v.video_id, "REJECTED", "manual_batch_reject")
                    st.success(f"Rejected {len(pending)} videos")
                    st.rerun()

            st.markdown("---")

            for video in pending:
                with st.container():
                    col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

                    with col1:
                        st.markdown(f"**{video.title}**")
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
                        if st.button("Accept", key=f"acc_{video.video_id}",
                                     help="Accept as knowledge-dense"):
                            db.update_triage_status(
                                video.video_id, "ACCEPTED", "manual_accept", 1.0
                            )
                            st.rerun()

                    with col3:
                        if st.button("Reject", key=f"rej_{video.video_id}",
                                     help="Reject as noise"):
                            db.update_triage_status(
                                video.video_id, "REJECTED", "manual_reject", 1.0
                            )
                            st.rerun()

                    with col4:
                        st.link_button("Watch", video.url, help="Watch on YouTube")

                    st.divider()
    except Exception as e:
        st.error(f"Failed to load Ambiguity Queue: {e}")
        logger.error(f"Ambiguity Queue error: {e}", exc_info=True)
