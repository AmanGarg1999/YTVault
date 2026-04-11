"""Review Center — Intelligence Core Redesign."""

import streamlit as st
import logging
from src.ui.components import (
    page_header,
    section_header,
    video_card,
    spacer,
    info_card,
    success_card,
    glass_card,
    action_confirmation_dialog,
)

logger = logging.getLogger(__name__)

def render(db):
    """Render the redesigned Unified Review Center."""
    page_header(
        "Review Center",
        "Triage pending content, audit automated decisions, and manage the research queue."
    )

    try:
        tab_pending, tab_rejected = st.tabs([
            "Queue: Pending Triage",
            "Vault Audit: Rejected Videos"
        ])

        with tab_pending:
            render_pending_section(db)

        with tab_rejected:
            render_rejected_section(db)

    except Exception as e:
        st.error(f"Review Center error: {e}")
        logger.error(f"Review Center error: {e}", exc_info=True)


def render_pending_section(db):
    """Render the pending review queue with modern styling."""
    pending = db.get_videos_by_status("PENDING_REVIEW", limit=50)
    
    if not pending:
        success_card("Pipeline Optimized", "All discovered content has been successfully triaged.")
        return

    section_header(f"{len(pending)} Intelligence Targets Awaiting Triage", icon="◈")
    
    for i, video in enumerate(pending):
        cols = video_card(video, key_prefix=f"pend_rev_{i}")
        if cols:
            with cols[0]:
                if st.button("Accept", key=f"acc_rev_{i}_{video.video_id}", type="primary", use_container_width=True):
                    db.update_triage_status(video.video_id, "ACCEPTED", "manual_accept", 1.0)
                    action_confirmation_dialog(
                        "Intelligence Accepted",
                        f"Video '{video.title[:40]}' has been admitted to the knowledge vault.",
                        icon="✅"
                    )
            with cols[1]:
                st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
                if st.button("Reject", key=f"rej_rev_{i}_{video.video_id}", use_container_width=True):
                    db.update_triage_status(video.video_id, "REJECTED", "manual_reject", 1.0)
                    action_confirmation_dialog(
                        "Intelligence Rejected",
                        f"Target '{video.title[:40]}' suppressed and moved to audit.",
                        icon="✖"
                    )
                st.markdown('</div>', unsafe_allow_html=True)


def render_rejected_section(db):
    """Render the rejected videos audit section."""
    try:
        rejected = db.get_videos_by_status_sorted("REJECTED", order_by="updated_at DESC", limit=50)
        
        if not rejected:
            info_card("Vault Integrity Stable", "No videos have been suppressed by the filters yet.")
            return

        section_header(f"{len(rejected)} Suppressed Entries in Audit", icon="⚠")
        
        for i, video in enumerate(rejected):
            cols = video_card(video, key_prefix=f"rej_rev_{i}")
            if cols:
                with cols[0]:
                    if st.button("Override", key=f"ov_rev_{i}_{video.video_id}", type="primary", use_container_width=True):
                        db.manual_override_rejected_video(video.video_id)
                        action_confirmation_dialog(
                            "Override Complete",
                            "The automated rejection filter has been bypassed manually.",
                            icon="🔓"
                        )
                with cols[1]:
                    st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
                    if st.button("Purge Intel", key=f"del_rev_{i}_{video.video_id}", use_container_width=True):
                        db.delete_video_data(video.video_id)
                        action_confirmation_dialog(
                            "Intelligence Purged",
                            "All related metadata and artifacts have been permanently removed.",
                            icon="🗑"
                        )
                    st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Audit engine error: {e}")
        logger.error(f"Rejected audit error: {e}", exc_info=True)
