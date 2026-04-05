import streamlit as st
import logging

from src.ui.components import (
    page_header,
    section_header,
    video_card,
    spacer,
    info_card,
    success_card,
    warning_card,
)

logger = logging.getLogger(__name__)


def render(db):
    """Render the Unified Review Center."""
    page_header(
        "Review Center",
        "Triage pending content and manage rejected videos",
        icon="⚖️"
    )

    try:
        tab_pending, tab_rejected = st.tabs([
            "⏳ Pending Review",
            "🚫 Rejected Videos"
        ])

        with tab_pending:
            render_pending_section(db)

        with tab_rejected:
            render_rejected_section(db)

    except Exception as e:
        st.error(f"Review Center error: {e}")
        logger.error(f"Review Center error: {e}", exc_info=True)


def render_pending_section(db):
    """Render the pending review queue."""
    pending = db.get_videos_by_status("PENDING_REVIEW", limit=50)
    
    if not pending:
        success_card("Queue Empty", "All videos have been triaged!")
        return

    st.markdown(f"### ⏳ {len(pending)} Videos Awaiting Review")
    
    for i, video in enumerate(pending):
        cols = video_card(video, key_prefix=f"pend_{i}")
        if cols:
            with cols[0]:
                if st.button("✅ Accept", key=f"acc_p_{i}_{video.video_id}", type="primary", use_container_width=True):
                    db.update_triage_status(video.video_id, "ACCEPTED", "manual_accept", 1.0)
                    st.rerun()
            with cols[1]:
                if st.button("❌ Reject", key=f"rej_p_{i}_{video.video_id}", use_container_width=True):
                    db.update_triage_status(video.video_id, "REJECTED", "manual_reject", 1.0)
                    st.rerun()


def render_rejected_section(db):
    """Render the rejected videos review."""
    try:
        rejected = db.get_videos_by_status_sorted("REJECTED", order_by="updated_at DESC", limit=50)
        
        if not rejected:
            info_card("No Rejected Videos", "Triage has been very selective!")
            return

        st.markdown(f"### 🚫 {len(rejected)} Rejected Videos")
        
        for i, video in enumerate(rejected):
            cols = video_card(video, key_prefix=f"rej_{i}")
            if cols:
                with cols[0]:
                    if st.button("🔄 Override", key=f"ov_r_{i}_{video.video_id}", type="primary", use_container_width=True):
                        db.manual_override_rejected_video(video.video_id, db_session=None)
                        st.rerun()
                with cols[1]:
                    if st.button("🗑️ Purge", key=f"del_r_{i}_{video.video_id}", use_container_width=True):
                        db.delete_video_data(video.video_id)
                        st.rerun()

                st.divider()

    except Exception as e:
        st.error(f"Failed to load Rejected Videos Review: {e}")
        logger.error(f"Rejected Videos Review error: {e}", exc_info=True)
