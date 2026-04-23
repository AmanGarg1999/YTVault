"""Review Center — Intelligence Core Redesign."""

import streamlit as st
import logging
import time
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


def get_selection_state():
    """Manage selection state for batch triage."""
    if "selected_vids" not in st.session_state:
        st.session_state.selected_vids = set()
    return st.session_state.selected_vids


def render_pending_section(db):
    """Render the pending review queue with modern styling."""
    pending = db.get_videos_by_status("PENDING_REVIEW", limit=50)
    
    if not pending:
        success_card("Pipeline Optimized", "All discovered content has been successfully triaged.")
        return

    # Batch Mode Control
    col_h, col_b = st.columns([3, 1])
    with col_h:
        section_header(f"{len(pending)} Intelligence Targets Awaiting Triage", icon="◈")
    with col_b:
        batch_mode = st.toggle("Master Batch Control", key="batch_mode_toggle", help="Enable multi-selection for rapid triage.")

    selected_vids = get_selection_state()

    # Sticky Batch Actions Bar
    if batch_mode and selected_vids:
        with st.container():
            st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid var(--primary-glow); border-radius: 12px; padding: 1rem; margin-bottom: 2rem; display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-weight: 700; color: white;">⚡ BATCH ACTION: <span style="color: var(--primary-glow);">""" + str(len(selected_vids)) + """ Selected</span></div>
                </div>
            """, unsafe_allow_html=True)
            
            b_col1, b_col2, b_col3 = st.columns([1, 1, 2])
            with b_col1:
                if st.button("Fast-Track Selection", type="primary", use_container_width=True):
                    for vid_id in list(selected_vids):
                        db.update_triage_status(vid_id, "ACCEPTED", "batch_accept", 1.0)
                    st.toast(f"Admitted {len(selected_vids)} intelligence targets.", icon="🚀")
                    selected_vids.clear()
                    st.rerun()
            with b_col2:
                if st.button("Suppress Selection", use_container_width=True):
                    for vid_id in list(selected_vids):
                        db.update_triage_status(vid_id, "REJECTED", "batch_reject", 1.0)
                    st.toast(f"Suppressed {len(selected_vids)} intelligence targets.", icon="✖")
                    selected_vids.clear()
                    st.rerun()
            with b_col3:
                if st.button("Reset Selection", type="secondary", use_container_width=True):
                    selected_vids.clear()
                    st.rerun()
            spacer("1rem")

    for i, video in enumerate(pending):
        if batch_mode:
            c_check, c_card = st.columns([0.1, 4])
            with c_check:
                is_selected = video.video_id in selected_vids
                if st.checkbox("", value=is_selected, key=f"check_{video.video_id}", label_visibility="collapsed"):
                    selected_vids.add(video.video_id)
                else:
                    selected_vids.discard(video.video_id)
            with c_card:
                # In batch mode, we don't show per-video buttons to reduce clutter
                video_card(video, key_prefix=f"pend_rev_{i}", show_actions=False)
        else:
            cols = video_card(video, key_prefix=f"pend_rev_{i}")
            if cols:
                with cols[0]:
                    if st.button("Accept", key=f"acc_rev_{i}_{video.video_id}", type="primary", use_container_width=True):
                        db.update_triage_status(video.video_id, "ACCEPTED", "manual_accept", 1.0)
                        st.toast(f"Intelligence Admitted: {video.title[:30]}...", icon="✅")
                        st.rerun()
                with cols[1]:
                    st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
                    if st.button("Reject", key=f"rej_rev_{i}_{video.video_id}", use_container_width=True):
                        db.update_triage_status(video.video_id, "REJECTED", "manual_reject", 1.0)
                        st.toast(f"Target Suppressed: {video.title[:30]}...", icon="✖")
                        st.session_state.needs_rerun = True
                    st.markdown('</div>', unsafe_allow_html=True)
                    if st.session_state.get("needs_rerun"):
                        st.session_state.needs_rerun = False
                        st.rerun()


def render_rejected_section(db):
    """Render the rejected videos audit section."""
    try:
        rejected = db.get_videos_by_status_sorted("REJECTED", order_by="updated_at DESC", limit=50)
        
        if not rejected:
            info_card("Vault Integrity Stable", "No videos have been suppressed by the filters yet.")
            return

        section_header(f"{len(rejected)} Suppressed Entries in Audit", icon="⚠")
        
        # Undo Action Bar
        if st.session_state.get("last_deleted_id"):
            last_id = st.session_state.last_deleted_id
            with glass_card():
                col_u1, col_u2 = st.columns([3, 1])
                col_u1.markdown(f"**Recently trashed intelligence can be recovered.**")
                if col_u2.button("UNDO DELETION", type="primary", use_container_width=True):
                    db.restore_video(last_id)
                    st.session_state.last_deleted_id = None
                    st.toast("Intelligence Restored", icon="↩")
                    st.rerun()
                if st.button("Dismiss", key="dismiss_undo"):
                    st.session_state.last_deleted_id = None
                    st.rerun()
        
        for i, video in enumerate(rejected):
            cols = video_card(video, key_prefix=f"rej_rev_{i}")
            if cols:
                with cols[0]:
                    if st.button("Override", key=f"ov_rev_{i}_{video.video_id}", type="primary", use_container_width=True):
                        db.manual_override_rejected_video(video.video_id)
                        st.toast("Override Complete: Automated filter bypassed.", icon="🔓")
                        st.rerun()
                with cols[1]:
                    if st.button("Move to Trash", key=f"del_rev_{i}_{video.video_id}", use_container_width=True):
                        if db.delete_video_data(video.video_id, reason="Manual triage rejection"):
                            st.toast(f"Moved to Trash: {video.title[:20]}...", icon="🗑")
                            # Add a temporary session state for undo
                            st.session_state.last_deleted_id = video.video_id
                            st.rerun()
                        st.toast("Intelligence moved to Recycle Bin.", icon="🗑")
                        st.rerun()

    except Exception as e:
        st.error(f"Audit engine error: {e}")
        logger.error(f"Rejected audit error: {e}", exc_info=True)
