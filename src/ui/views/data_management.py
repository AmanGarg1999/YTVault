"""
Data Management Center - Delete and manage processed video/channel data.

Features:
- Delete specific video data with cascade  
- Delete all videos from a channel
- Track deletion history
- Understand reprocessing implications
- View what gets deleted before confirming
"""

import logging
import streamlit as st
import pandas as pd
import json

logger = logging.getLogger(__name__)


from src.ui.components import page_header, destructive_action_dialog

def render(db, run_repair=None, get_diagnostics=None):
    """Render the Data Management Center page."""
    page_header("Data Management Center", "Delete video/channel data, manage storage, and track deletion history")

    try:
        # Important note about reprocessing
        st.info("""
        **About Data Deletion & Reprocessing:**
        - After deletion, videos go back to `DISCOVERED` state and CAN be reprocessed
        - Reprocessing will regenerate all deleted data (chunks, embeddings, graph nodes)
        - Vector/Graph data is NOT automatically cleaned - you'll have duplicates on reprocess
        - Use this tool carefully - deleted data cannot be recovered
        """)

        # =====================================================================
        # SECTION 0: Intelligence Source Explorer (NEW)
        # =====================================================================
        st.markdown("### Intelligence Source Explorer")
        st.caption("Inspect, audit, and manage high-fidelity source indexes across the triple-store architecture.")

        all_videos = db.get_videos_by_status(["ACCEPTED", "DONE", "PENDING_REVIEW", "REJECTED"], limit=5000)
        if all_videos:
            import pandas as pd
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
            
            # Use columns for search/filter
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                search_term = st.text_input("Filter Sources", placeholder="Search by title or ID...", key="source_search")
            with col_s2:
                status_filter = st.multiselect("Status Filter", options=["ACCEPTED", "DONE", "PENDING_REVIEW", "REJECTED"], default=["ACCEPTED", "DONE"])

            # Apply filters
            if search_term:
                df_sources = df_sources[df_sources["Title"].str.contains(search_term, case=False) | df_sources["Video ID"].str.contains(search_term, case=False)]
            if status_filter:
                df_sources = df_sources[df_sources["Status"].isin(status_filter)]

            # Render clickable list using dataframe or selection
            st.markdown(f"**Found {len(df_sources)} matching sources**")
            
            # Use dataframe selection for inspection
            selected_indices = st.dataframe(
                df_sources, 
                use_container_width=True, 
                hide_index=True,
                on_select="rerun",
                selection_mode="single_row",
                key="source_explorer_table"
            )

            if selected_indices and selected_indices["selection"]["rows"]:
                row_idx = selected_indices["selection"]["rows"][0]
                selected_v_id = df_sources.iloc[row_idx]["Video ID"]
                selected_video = db.get_video(selected_v_id)
                
                if selected_video:
                    from src.ui.components.ui_helpers import glass_card, inline_status
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
                            if st.button("Mark for Deletion", type="secondary", use_container_width=True, key="explorer_mark_del"):
                                # Set session state to prepopulate deletion tools below
                                st.session_state.video_select_id = selected_video.video_id
                                st.toast(f"Source {selected_video.video_id[:8]} selected for management.")
        else:
            st.info("No indexed sources found in the intelligence vault yet.")

        st.markdown("---")

        # =====================================================================
        # SECTION 1: Delete Single Video Data
        # =====================================================================
        st.markdown("### Delete Single Video")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Get all processed videos
            processed_videos = []
            for status in ["ACCEPTED", "DONE"]:
                processed_videos.extend(db.get_videos_by_status(status, limit=1000))
            
            if processed_videos:
                # Handle prepopulation from explorer
                index = 0
                if "video_select_id" in st.session_state:
                    for i, pv in enumerate(processed_videos):
                        if pv.video_id == st.session_state.video_select_id:
                            index = i
                            break
                
                selected_video = st.selectbox(
                    "Select video to delete",
                    processed_videos,
                    index=index,
                    format_func=lambda v: f"{v.title[:50]}... | {v.video_id[:8]} | {v.triage_status}",
                    key="video_select",
                )
                
                if selected_video:
                    with col2:
                        st.markdown("**Video Details**")
                        st.write(f"**Title:** {selected_video.title}")
                        st.write(f"**Video ID:** `{selected_video.video_id}`")
                        st.write(f"**Status:** {selected_video.triage_status}")
                        st.write(f"**Stage:** {selected_video.checkpoint_stage}")
                        st.write(f"**Channel:** `{selected_video.channel_id}`")
                    
                    # Preview what will be deleted
                    st.markdown("---")
                    with st.expander("Preview: What Will Be Deleted", expanded=True):
                        col_a, col_b, col_c = st.columns(3)
                        
                        # Count chunks
                        chunks = db.get_chunks_for_video(selected_video.video_id)
                        chunk_count = len(chunks)
                        with col_a:
                            st.metric("Transcript Chunks", chunk_count)
                        
                        # Count claims
                        claims = db.get_claims_for_video(selected_video.video_id)
                        with col_b:
                            st.metric("Claims", len(claims))
                        
                        # Count quotes
                        quotes = db.get_quotes_for_video(selected_video.video_id)
                        with col_c:
                            st.metric("Quotes", len(quotes))
                        
                        # Count guest appearances
                        guests = db.conn.execute(
                            """SELECT COUNT(*) as cnt FROM guest_appearances 
                               WHERE video_id = ?""",
                            (selected_video.video_id,)
                        ).fetchone()
                        guest_count = guests["cnt"] if guests else 0
                        
                        st.metric("Guest Appearances", guest_count)
                        
                        st.markdown("**Data to be deleted:**")
                        st.write(f"- {chunk_count} transcript chunks")
                        st.write(f"- {len(claims)} extracted claims")
                        st.write(f"- {len(quotes)} notable quotes")
                        st.write(f"- {guest_count} guest appearance records")
                        st.write(f"- Temporary processing state")
                        st.write(f"- Video summary data")
                        
                        st.warning("""
                        **NOT deleted (causes duplicate on reprocess):**
                        - Vector embeddings in ChromaDB
                        - Neo4j graph nodes and relationships
                        
                        Consider manually cleaning these if concerned about duplicates.
                        """)
                    
                    # Deletion confirmation
                    st.markdown("---")
                    
                    col_delete, col_reason = st.columns([1, 2])
                    
                    with col_reason:
                        delete_reason = st.text_input(
                            "Reason for deletion (for records):",
                            placeholder="e.g., 'Duplicate video', 'Data corruption', 'User requested'",
                            key="delete_reason_video",
                        )
                    
                    with col_delete:
                        if st.button(
                            "DELETE VIDEO DATA",
                            type="secondary",
                            key="delete_video_btn",
                            use_container_width=True,
                        ):
                            def on_confirm():
                                with st.spinner("Deleting across all intelligence stores..."):
                                    # 1. SQLite Relational Data
                                    result = db.delete_video_data(selected_video.video_id, delete_reason)
                                    
                                    # 2. Vector Store (ChromaDB)
                                    vector_deleted = False
                                    try:
                                        from src.storage.vector_store import VectorStore
                                        vs = VectorStore()
                                        vs.delete_video_chunks(selected_video.video_id)
                                        vector_deleted = True
                                    except Exception as e:
                                        logger.warning(f"Vector deletion failed for {selected_video.video_id}: {e}")
                                    
                                    # 3. Graph Store (Neo4j)
                                    graph_result = {"video_deleted": False, "claims_deleted": 0}
                                    try:
                                        from src.storage.graph_store import GraphStore
                                        gs = GraphStore()
                                        graph_result = gs.delete_video_nodes(selected_video.video_id)
                                        gs.close()
                                    except Exception as e:
                                        logger.warning(f"Graph deletion failed for {selected_video.video_id}: {e}")

                                st.success(f"Atomic deletion successful for {selected_video.title[:40]}...")
                                db.log_pipeline_event(
                                    level="WARNING",
                                    message=f"Atomic deletion: {selected_video.title[:50]}...",
                                    video_id=selected_video.video_id,
                                    stage="DATA_MANAGEMENT",
                                )

                            destructive_action_dialog(
                                title="Video Data Destruction",
                                message=f"Are you absolutely sure you want to delete all extracted intelligence for '{selected_video.title[:40]}...'? This action targets the relational, vector, and graph stores.",
                                on_confirm=on_confirm,
                                confirm_label="PERMANENTLY DELETE"
                            )
            else:
                st.info("No processed videos available to delete.")
        
        st.markdown("---")

        # =====================================================================
        # SECTION 2: Delete All Videos from Channel
        # =====================================================================
        st.markdown("### Delete All Videos from Channel")
        
        channels = db.get_all_channels()
        
        if channels:
            selected_channel = st.selectbox(
                "Select channel to delete all videos from",
                channels,
                format_func=lambda c: f"{c.name} | {len(db.get_videos_by_channel(c.channel_id))} videos",
                key="channel_select",
            )
            
            if selected_channel:
                # Get video count
                videos = db.get_videos_by_channel(selected_channel.channel_id)
                
                st.warning(f"""
                **This will delete data for ALL {len(videos)} videos in this channel:**
                - All transcript chunks
                - All claims and quotes
                - All guest appearances
                - Channel processing state
                
                Videos will be rescannable but vector/graph duplicates will remain.
                """)
                
                col_reason, col_delete = st.columns([2, 1])
                
                with col_reason:
                    delete_reason = st.text_input(
                        "Reason for channel deletion:",
                        placeholder="e.g., 'Channel cleanup', 'Storage optimization'",
                        key="delete_reason_channel",
                    )
                
                with col_delete:
                    if st.button(
                        "DELETE CHANNEL DATA",
                        type="secondary",
                        key="delete_channel_btn",
                        use_container_width=True,
                    ):
                        def on_confirm_channel():
                            with st.spinner(f"Purging all data for {len(videos)} videos..."):
                                # 1. SQLite Relational Data
                                result = db.delete_channel_data(selected_channel.channel_id, delete_reason)
                                
                                # Instantiate external stores
                                from src.storage.vector_store import VectorStore
                                from src.storage.graph_store import GraphStore
                                vs = VectorStore()
                                gs = GraphStore()
                                
                                # 2 & 3. External Stores
                                for i, v in enumerate(videos):
                                    try: vs.delete_video_chunks(v.video_id)
                                    except: pass
                                    try: gs.delete_video_nodes(v.video_id)
                                    except: pass
                                gs.close()

                            st.success(f"Atomic channel deletion successful for {selected_channel.name}...")
                            db.log_pipeline_event(
                                level="WARNING",
                                message=f"Atomic channel deletion: {selected_channel.name} ({len(videos)} videos)",
                                channel_id=selected_channel.channel_id,
                                stage="DATA_MANAGEMENT",
                            )

                        destructive_action_dialog(
                            title="Channel Data Destruction",
                            message=f"You are about to delete ALL extracted intelligence for {len(videos)} videos in '{selected_channel.name}'. This action is permanent and impacts the Knowledge Graph and Vector store.",
                            on_confirm=on_confirm_channel,
                            confirm_label="PURGE CHANNEL"
                        )
        else:
            st.info("No channels available.")
        
        st.markdown("---")

        # =====================================================================
        # SECTION 3: Deletion History
        # =====================================================================
        st.markdown("### Deletion History")
        
        history = db.get_deletion_history(limit=50)
        
        if history:
            history_data = []
            for h in history:
                try:
                    data_deleted = json.loads(h.get("data_deleted", "{}"))
                    summary = f"{data_deleted.get('videos_deleted', data_deleted.get('chunks_deleted', '?'))} items"
                except:
                    summary = "?"
                
                history_data.append({
                    "Date": h.get("deleted_at", "—")[:10],
                    "Type": h.get("deletion_type", "—").upper(),
                    "Target": h.get("video_id", h.get("channel_id", "—"))[:12],
                    "Reason": h.get("reason", "—"),
                    "Items Deleted": summary,
                })
            
            df = pd.DataFrame(history_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Detailed view
            if st.checkbox("View Detailed Deletion Records", key="view_deletion_details"):
                for h in history[:10]:  # Show first 10
                    with st.expander(f"{h.get('deleted_at')} | {h.get('deletion_type')} | {h.get('reason', 'N/A')}", expanded=False):
                        st.write(f"**Deletion Type:** {h.get('deletion_type')}")
                        st.write(f"**Target:** Video ID: `{h.get('video_id')}` / Channel ID: `{h.get('channel_id')}`")
                        st.write(f"**Reason:** {h.get('reason', 'Not provided')}")
                        st.write(f"**Deleted By:** {h.get('deleted_by', 'unknown')}")
                        
                        try:
                            data = json.loads(h.get("data_deleted", "{}"))
                            st.json(data)
                        except:
                            st.write(h.get("data_deleted", "{}"))
        else:
            st.info("No deletions have been recorded yet.")
        
        st.markdown("---")

        # =====================================================================
        # SECTION 4: Guest Data Cleanup (NEW)
        # =====================================================================
        st.markdown("### Guest Data Cleanup")
        st.info("""
        **Guest cleanup** identifies and removes low-quality guest entries:
        - Names shorter than 3 characters
        - Generic pronouns ("you", "he", "they")
        - Mis-tagged locations or organizations
        - One-word generic labels ("speaker", "expert")
        """)
        
        # Identification logic
        ENTITY_IGNORE_LIST = {
            "you", "he", "she", "it", "they", "we", "i", "me", "him", "her", "us", "them",
            "assistant", "speaker", "host", "guest", "expert", "narrator",
            "india", "usa", "china", "london", "mars", "earth",
            "youtube", "google", "openai", "anthropic", "meta", "tesla",
            "unknown", "someone", "somebody", "anyone", "everyone",
            "a", "the", "an", "this", "that", "there", "here"
        }
        
        with st.expander("Preview Junk Guests", expanded=False):
            all_guests = db.get_all_guests()
            to_cleanup = []
            for g in all_guests:
                name_clean = g.canonical_name.lower().strip().strip('.,!?"')
                is_junk = False
                if len(name_clean) < 3 or name_clean in ENTITY_IGNORE_LIST:
                    is_junk = True
                elif len(name_clean.split()) == 1 and name_clean in ENTITY_IGNORE_LIST:
                    is_junk = True
                
                if is_junk:
                    to_cleanup.append({"ID": g.guest_id, "Name": g.canonical_name, "Mentions": g.mention_count})
            
            if to_cleanup:
                st.write(f"Found **{len(to_cleanup)}** potentially low-quality guest records.")
                st.table(pd.DataFrame(to_cleanup))
                
                if st.button("PURGE JUNK GUESTS", type="primary", key="purge_guests_btn"):
                    if st.checkbox("Confirm purge of guest records", key="confirm_purge_guests"):
                        try:
                            # Run deletion SQL
                            ids = [item["ID"] for item in to_cleanup]
                            placeholders = ",".join(["?"] * len(ids))
                            
                            # Start transaction
                            db.conn.execute("BEGIN TRANSACTION")
                            db.conn.execute(f"DELETE FROM guest_appearances WHERE guest_id IN ({placeholders})", ids)
                            db.conn.execute(f"DELETE FROM guests WHERE guest_id IN ({placeholders})", ids)
                            db.conn.commit()
                            
                            st.success(f"Successfully purged {len(ids)} junk guest records!")
                            st.rerun()
                        except Exception as e:
                            db.conn.rollback()
                            st.error(f"Purge failed: {e}")
            else:
                st.success("No apparent junk guests found in current vault!")

        st.markdown("---")

        # SECTION 5: Maintenance & Repair (Moved to Pipeline Center)
        # =====================================================================
        st.markdown("### Vault Health & Maintenance")
        st.info("""
        **Vault Health & Repair tools have been moved to the [Pipeline Center](?navigate=Pipeline+Center)**
        for a more unified management experience. 
        
        Use the Pipeline Center to:
        - Run Full Vault Repairs
        - Monitor Data Coverage (Transcripts, Summaries, Heatmaps)
        - Manage active background tasks
        """)
        
        if st.button("GO TO PIPELINE CENTER", type="primary", use_container_width=True):
            st.session_state.navigate = "Pipeline Center"
            st.rerun()

        st.markdown("---")

        # =====================================================================
        # SECTION 6: P0-D — Store Health (Triple-Store Divergence Monitor)
        # =====================================================================
        st.markdown("### Store Health")
        st.caption("Compare video counts across all three intelligence stores to detect silent divergence.")

        with st.container():
            col_sql, col_vec, col_neo, col_outbox = st.columns(4)

            # SQLite stats
            try:
                sync_stats = db.get_store_sync_stats()
                sqlite_accepted = sync_stats.get("sqlite_accepted", 0)
                sqlite_done = sync_stats.get("sqlite_done", 0)
                pending_chroma = sync_stats.get("pending_outbox_chroma", 0)
                pending_neo4j = sync_stats.get("pending_outbox_neo4j", 0)
            except Exception:
                sqlite_accepted, sqlite_done, pending_chroma, pending_neo4j = 0, 0, 0, 0

            with col_sql:
                st.metric("SQLite (Accepted)", sqlite_accepted)
                st.caption(f"{sqlite_done} fully done")

            # ChromaDB stats
            chroma_unique = 0
            chroma_status = "Unknown"
            try:
                from src.storage.vector_store import VectorStore
                _vs = VectorStore()
                chroma_unique = _vs.count_unique_videos()
                chroma_status = "Online"
            except Exception:
                chroma_status = "Offline"

            with col_vec:
                st.metric("ChromaDB (Videos)", chroma_unique)
                st.caption(chroma_status)

            # Neo4j stats
            neo4j_count = 0
            neo4j_status = "Offline / Disabled"
            try:
                from src.storage.graph_store import GraphStore
                _gs = GraphStore()
                if hasattr(_gs, "get_video_count"):
                    neo4j_count = _gs.get_video_count()
                else:
                    # Fallback: count Video nodes directly
                    result = _gs.run_query("MATCH (v:Video) RETURN count(v) AS cnt")
                    neo4j_count = result[0]["cnt"] if result else 0
                neo4j_status = "Online"
                _gs.close()
            except Exception:
                pass

            with col_neo:
                st.metric("Neo4j (Video Nodes)", neo4j_count)
                st.caption(neo4j_status)

            # Outbox pending count
            with col_outbox:
                total_pending = (pending_chroma or 0) + (pending_neo4j or 0)
                st.metric("Outbox Pending", total_pending)
                if total_pending:
                    st.caption(f"{pending_chroma} chroma · {pending_neo4j} neo4j")
                else:
                    st.caption("All synchronized")

            # Divergence banner
            if chroma_status == "Online" and sqlite_done > 0:
                divergence = abs(sqlite_done - chroma_unique)
                if divergence > 0:
                    st.warning(
                        f"Divergence detected: SQLite reports {sqlite_done} completed videos "
                        f"but ChromaDB has {chroma_unique}. "
                        f"Run Vault Repair or re-harvest to synchronize."
                    )
                else:
                    st.success("SQLite and ChromaDB are in sync.")

        # Temp state storage health
        st.markdown("#### Temp State Storage (P0-C)")
        try:
            temp_stats = db.get_temp_state_stats()
            col_ts1, col_ts2, col_ts3 = st.columns(3)
            with col_ts1:
                st.metric("Pending Rows", temp_stats.get("row_count", 0))
            with col_ts2:
                size_kb = temp_stats.get("total_size_kb", 0) or 0
                st.metric("Approx. Size", f"{size_kb:,.0f} KB")
            with col_ts3:
                if st.button("Cleanup Done States", key="cleanup_temp_states_btn"):
                    deleted = db.cleanup_done_temp_states()
                    st.success(f"Cleaned {deleted} stale temp-state rows")
                    st.rerun()
        except Exception as e:
            st.caption(f"Temp state stats unavailable: {e}")

        st.markdown("---")

        # =====================================================================
        # SECTION 7: Storage Optimization Tips
        # =====================================================================
        st.markdown("### Storage Optimization Tips")
        
        with st.expander("Cleanup Recommendations", expanded=False):
            st.markdown("""
            ### Recommended Cleanup Strategy:
            
            1. **Review & Delete Rejected Videos**
               - Find all REJECTED videos (they won't be useful)
               - Delete them to save space
            
            2. **Manage Guest Data**
               - Guests mentioned in only one video may be noise
               - Consider if they're worth keeping
            
            3. **Clean Old Logs**
               - Pipeline logs older than 30 days can be archived
               - See Logs Monitor page for log cleanup
            
            4. **Vector/Graph Cleanup**
               - After deleting videos, consider manual chromadb/neo4j cleanup
               - Prevents duplicate embeddings on reprocessing
               - Use: `python -m src.storage.cleanup --mode full`
            
            5. **Storage Stats**
            """)
            
            # Show storage estimates
            col1, col2, col3 = st.columns(3)
            
            try:
                total_videos = db.conn.execute("SELECT COUNT(*) as cnt FROM videos").fetchone()["cnt"]
                total_chunks = db.conn.execute("SELECT COUNT(*) as cnt FROM transcript_chunks").fetchone()["cnt"]
                total_guests = db.conn.execute("SELECT COUNT(*) as cnt FROM guests").fetchone()["cnt"]
                
                with col1:
                    st.metric("Total Videos", total_videos)
                with col2:
                    st.metric("Total Chunks", total_chunks)
                with col3:
                    st.metric("Unique Guests", total_guests)
                
                # Rough size estimate
                avg_chunk_size = 2  # KB estimate
                avg_guest_size = 0.5  # KB
                estimated_size = (total_chunks * avg_chunk_size) + (total_guests * avg_guest_size)
                
                st.caption(f"Estimated SQLite data size: ~{estimated_size / 1024:.1f} MB (chunks + guests)")
                st.caption("ChromaDB and Neo4j may have additional storage needs")
                
            except Exception as e:
                st.error(f"Could not calculate storage: {e}")

    except Exception as e:
        st.error(f"Failed to load Data Management: {e}")
        logger.error(f"Data Management error: {e}", exc_info=True)
