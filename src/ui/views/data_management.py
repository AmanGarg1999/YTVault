"""
Data Management Center - Delete and manage processed video/channel data.

Features:
- Soft-delete with Recycle Bin for easy recovery
- Permanent purge across Triple-Store (SQL, Vector, Graph)
- Source Explorer for auditing intelligence targets
- Deletion history tracking
"""

import logging
import streamlit as st
import pandas as pd
import json
from src.ui.components import page_header, destructive_action_dialog, glass_card

logger = logging.getLogger(__name__)

def render(db, run_repair=None, get_diagnostics=None):
    """Render the Data Management Center page."""
    page_header("Data Management Center", "Manage storage, audit sources, and restore deleted intelligence")

    tab_explorer, tab_recycle, tab_bulk, tab_history, tab_sync = st.tabs([
        "Vault Explorer",
        "Recycle Bin",
        "Bulk Management",
        "Deletion History",
        "Sync Monitor"
    ])

    with tab_explorer:
        render_explorer_section(db)

    with tab_recycle:
        render_recycle_bin(db)

    with tab_channel:
        render_channel_actions(db)

    with tab_history:
        render_deletion_history(db)

    with tab_health:
        render_store_health(db)


def render_explorer_section(db):
    st.info("""
    **Intelligence Lifecycle:**
    - **Recycle Bin**: Soft-deleted videos can be restored within this session.
    - **Reprocessing**: Purged videos will be re-discovered on next harvest.
    - **Sync**: Always verify Triple-Store health after bulk deletions.
    """)

    st.markdown("### Intelligence Source Explorer")
    st.caption("Inspect, audit, and manage high-fidelity source indexes across the triple-store architecture.")
    
    # Undo Action Bar
    if st.session_state.get("last_deleted_id"):
        last_id = st.session_state.last_deleted_id
        with glass_card():
            col_u1, col_u2 = st.columns([3, 1])
            col_u1.markdown(f"**Recently trashed intelligence can be recovered.**")
            if col_u2.button("UNDO DELETION", type="primary", use_container_width=True, key="undo_dm"):
                db.restore_video(last_id)
                st.session_state.last_deleted_id = None
                st.toast("Intelligence Restored", icon="↩")
                st.rerun()
            if st.button("Dismiss", key="dismiss_undo_dm"):
                st.session_state.last_deleted_id = None
                st.rerun()

    all_videos = db.get_videos_by_status(["ACCEPTED", "DONE", "PENDING_REVIEW", "REJECTED"], limit=5000)
    if all_videos:
        source_data = []
        for v in all_videos:
            source_data.append({
                "Video ID": v.video_id,
                "Title": v.title,
                "Channel": v.channel_id[:12] + "...",
                "Status": v.triage_status,
                "Stage": v.checkpoint_stage,
                "Confidence": f"{v.triage_confidence * 100:.0f}%" if v.triage_confidence else "N/A",
            })
        
        df_sources = pd.DataFrame(source_data)
        
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            search_term = st.text_input("Filter Sources", placeholder="Search by title or ID...", key="source_search")
        with col_s2:
            status_filter = st.multiselect("Status Filter", options=["ACCEPTED", "DONE", "PENDING_REVIEW", "REJECTED"], default=["ACCEPTED", "DONE"])

        if search_term:
            df_sources = df_sources[df_sources["Title"].str.contains(search_term, case=False) | df_sources["Video ID"].str.contains(search_term, case=False)]
        if status_filter:
            df_sources = df_sources[df_sources["Status"].isin(status_filter)]

        st.markdown(f"**Found {len(df_sources)} matching sources**")
        
        selected_indices = st.dataframe(
            df_sources, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="source_explorer_table"
        )

        if selected_indices and selected_indices["selection"]["rows"]:
            row_idx = selected_indices["selection"]["rows"][0]
            selected_v_id = df_sources.iloc[row_idx]["Video ID"]
            selected_video = db.get_video(selected_v_id)
            
            if selected_video:
                with glass_card(title="Source Audit: " + selected_video.title):
                    col_dt1, col_dt2 = st.columns(2)
                    with col_dt1:
                        st.write(f"**Video ID:** `{selected_video.video_id}`")
                        st.write(f"**Channel:** `{selected_video.channel_id}`")
                        st.write(f"**Duration:** {selected_video.duration_seconds // 60}:{selected_video.duration_seconds % 60:02d}")
                    with col_dt2:
                        st.write(f"**Status:** {selected_video.triage_status}")
                        st.write(f"**Confidence:** {selected_video.triage_confidence:.2f}")
                        st.write(f"**Last Stage:** `{selected_video.checkpoint_stage}`")
                    
                    st.markdown("---")
                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button("Quick Drill Down (Transcript)", use_container_width=True, key="explorer_drill"):
                            st.session_state.selected_transcript_vid = selected_video.video_id
                            st.session_state.navigate = "Transcripts"
                            st.rerun()
                    with col_act2:
                        if st.button("Move to Recycle Bin", type="secondary", use_container_width=True, key="explorer_mark_del"):
                            def on_confirm_trash():
                                if db.delete_video_data(selected_video.video_id, "Manual explorer management"):
                                    st.toast(f"Moved to Trash: {selected_video.video_id[:8]}", icon="🗑")
                                    st.session_state.last_deleted_id = selected_video.video_id
                                    st.rerun()
                            
                            destructive_action_dialog(
                                title="Move to Recycle Bin",
                                message=f"Are you sure you want to move '{selected_video.title[:40]}...' to the Recycle Bin?",
                                on_confirm=on_confirm_trash,
                                confirm_label="TRASH INTEL"
                            )
        
        st.divider()
        render_delete_single_section(db)
    else:
        st.info("No indexed sources found in the intelligence vault yet.")

def render_delete_single_section(db):
    st.markdown("### Delete Single Video")
    col1, col2 = st.columns(2)
    with col1:
        processed_videos = []
        for status in ["ACCEPTED", "DONE"]:
            processed_videos.extend(db.get_videos_by_status(status, limit=1000))
        
        if processed_videos:
            selected_video = st.selectbox(
                "Select video to manage",
                processed_videos,
                format_func=lambda v: f"{v.title[:50]}... | {v.video_id[:8]}",
                key="video_select_mgmt",
            )
            
            if selected_video:
                with col2:
                    st.markdown("**Video Details**")
                    st.write(f"**Title:** {selected_video.title}")
                    st.write(f"**Status:** {selected_video.triage_status}")
                
                if st.button("MOVE TO RECYCLE BIN", type="secondary", use_container_width=True):
                    def on_confirm():
                        db.delete_video_data(selected_video.video_id, "Manual management")
                        st.toast("Intelligence moved to Recycle Bin.", icon="🗑")
                        st.rerun()
                    destructive_action_dialog(
                        title="Move to Recycle Bin",
                        message=f"Are you sure you want to move '{selected_video.title[:40]}...' to the Recycle Bin?",
                        on_confirm=on_confirm,
                        confirm_label="SOFT DELETE"
                    )

def render_recycle_bin(db):
    st.markdown("### Recycle Bin")
    st.caption("Restore soft-deleted intelligence or permanently purge from all stores.")
    
    # We fetch ALL videos with is_deleted=1
    rows = db.conn.execute("SELECT * FROM videos WHERE is_deleted = 1 ORDER BY updated_at DESC").fetchall()
    deleted_videos = [db.Video.from_row(dict(r)) for r in rows]
    
    if not deleted_videos:
        st.success("Recycle Bin is empty.")
        return

    for v in deleted_videos:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{v.title}**")
                st.caption(f"ID: {v.video_id} | Deleted on {v.updated_at[:16]}")
            with col2:
                if st.button("Restore", key=f"rest_{v.video_id}", use_container_width=True):
                    if db.restore_video(v.video_id):
                        st.toast(f"Restored: {v.title[:30]}...", icon="🔄")
                        st.rerun()
            with col3:
                if st.button("Purge", key=f"purge_{v.video_id}", use_container_width=True, type="secondary"):
                    def on_purge():
                        db.purge_video_data(v.video_id)
                        st.toast(f"Permanently Purged: {v.video_id[:8]}", icon="🔥")
                        st.rerun()
                    destructive_action_dialog(
                        title="Permanent Destruction",
                        message=f"PERMANENTLY delete all extracted intelligence for '{v.title[:30]}...' from SQL, Vector, and Graph stores? This cannot be undone.",
                        on_confirm=on_purge,
                        confirm_label="PURGE PERMANENTLY"
                    )

def render_channel_actions(db):
    st.markdown("### Delete All Videos from Channel")
    channels = db.get_all_channels()
    if channels:
        selected_channel = st.selectbox(
            "Select channel",
            channels,
            format_func=lambda c: f"{c.name}",
            key="channel_select_mgmt",
        )
        if selected_channel:
            videos = db.get_videos_by_channel(selected_channel.channel_id)
            st.warning(f"This will soft-delete ALL {len(videos)} videos in '{selected_channel.name}'.")
            if st.button("MOVE CHANNEL TO TRASH", type="secondary", use_container_width=True):
                def on_confirm_channel():
                    for v in videos:
                        db.delete_video_data(v.video_id, f"Bulk channel deletion: {selected_channel.name}")
                    st.success(f"Channel {selected_channel.name} moved to Recycle Bin.")
                    st.rerun()
                destructive_action_dialog(
                    title="Bulk Channel Deletion",
                    message=f"Move {len(videos)} videos to the Recycle Bin?",
                    on_confirm=on_confirm_channel,
                    confirm_label="TRASH CHANNEL"
                )

def render_deletion_history(db):
    st.markdown("### Deletion History")
    history = db.get_deletion_history(limit=50)
    if history:
        history_data = []
        for h in history:
            history_data.append({
                "Date": h.get("deleted_at", "—")[:16],
                "Type": h.get("deletion_type", "—").upper(),
                "Target": h.get("video_id", h.get("channel_id", "—"))[:12],
                "Reason": h.get("reason", "—"),
            })
        st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)
    else:
        st.info("No deletion history found.")

def render_store_health(db):
    st.markdown("### Triple-Store Health Monitor")
    st.caption("Compare video counts across SQL, Vector, and Graph stores.")
    
    # Simple metrics
    try:
        sql_count = db.conn.execute("SELECT COUNT(*) as cnt FROM videos WHERE is_deleted = 0").fetchone()["cnt"]
        
        # Try to get Vector/Graph counts if possible
        try:
            from src.storage.vector_store import VectorStore
            vs_internal = VectorStore()
            vec_count = vs_internal.count_unique_videos()
        except Exception as e:
            logger.warning(f"Vector store count failed: {e}")
            vec_count = "OFFLINE"
        
        try:
            from src.storage.graph_store import GraphStore
            gs = GraphStore()
            res = gs.run_query("MATCH (v:Video) RETURN count(v) as cnt")
            graph_count = res[0]["cnt"]
            gs.close()
        except Exception as e:
            logger.warning(f"Graph store count failed: {e}")
            graph_count = "OFFLINE"

        c1, c2, c3 = st.columns(3)
        c1.metric("SQL (Active)", sql_count)
        c2.metric("ChromaDB", vec_count, help="Vector store connectivity status" if vec_count == "OFFLINE" else None)
        c3.metric("Neo4j", graph_count, help="Graph engine connectivity status" if graph_count == "OFFLINE" else None)
        
        if vec_count == "OFFLINE" or graph_count == "OFFLINE":
            st.warning("One or more auxiliary stores are offline. Intelligence synthesis may be limited.")
        
    except Exception as e:
        st.error(f"Sync monitor error: {e}")
        logger.error(f"Sync monitor error: {e}", exc_info=True)
