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


def render(db, run_repair=None, get_diagnostics=None):
    """Render the Data Management Center page."""
    st.markdown("""
    <div class="main-header">
        <h1>🗑️ Data Management Center</h1>
        <p>Delete video/channel data, manage storage, and track deletion history</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        # Important note about reprocessing
        st.info("""
        **ℹ️ About Data Deletion & Reprocessing:**
        - After deletion, videos go back to `DISCOVERED` state and CAN be reprocessed
        - Reprocessing will regenerate all deleted data (chunks, embeddings, graph nodes)
        - Vector/Graph data is NOT automatically cleaned - you'll have duplicates on reprocess
        - Use this tool carefully - deleted data cannot be recovered
        """)

        # =====================================================================
        # SECTION 1: Delete Single Video Data
        # =====================================================================
        st.markdown("### 📹 Delete Single Video")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Get all processed videos
            processed_videos = []
            for status in ["ACCEPTED", "DONE"]:
                processed_videos.extend(db.get_videos_by_status(status, limit=1000))
            
            if processed_videos:
                selected_video = st.selectbox(
                    "Select video to delete",
                    processed_videos,
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
                    with st.expander("👀 Preview: What Will Be Deleted", expanded=True):
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
                        st.write(f"- ✂️ {chunk_count} transcript chunks")
                        st.write(f"- 💭 {len(claims)} extracted claims")
                        st.write(f"- 💬 {len(quotes)} notable quotes")
                        st.write(f"- 👤 {guest_count} guest appearance records")
                        st.write(f"- 📄 Temporary processing state")
                        st.write(f"- 📊 Video summary data")
                        
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
                            "🗑️ DELETE VIDEO DATA",
                            type="secondary",
                            key="delete_video_btn",
                            use_container_width=True,
                        ):
                            if st.checkbox("⚠️ I understand this cannot be undone", key="confirm_delete_video"):
                                try:
                                    result = db.delete_video_data(selected_video.video_id, delete_reason)
                                    
                                    st.success(f"""
                                    ✅ **Video data deleted successfully!**
                                    
                                    - Chunks deleted: {result['chunks_deleted']}
                                    - Claims deleted: {result['claims_deleted']}
                                    - Quotes deleted: {result['quotes_deleted']}
                                    - Guest appearances removed: {result['appearances_removed']}
                                    - Guests cleaned up: {result['guests_removed']}
                                    
                                    **Video is now in DISCOVERED state and can be reprocessed.**
                                    """)
                                    
                                    # Log to activity
                                    db.log_pipeline_event(
                                        level="WARNING",
                                        message=f"Video data deleted: {selected_video.title[:50]}...",
                                        video_id=selected_video.video_id,
                                        stage="DATA_MANAGEMENT",
                                    )
                                    
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Deletion failed: {e}")
                                    logger.error(f"Video deletion error: {e}", exc_info=True)
            else:
                st.info("No processed videos available to delete.")
        
        st.markdown("---")

        # =====================================================================
        # SECTION 2: Delete All Videos from Channel
        # =====================================================================
        st.markdown("### 📺 Delete All Videos from Channel")
        
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
                        "🗑️ DELETE CHANNEL DATA",
                        type="secondary",
                        key="delete_channel_btn",
                        use_container_width=True,
                    ):
                        if st.checkbox("⚠️ I understand this will delete data for ALL videos", key="confirm_delete_channel"):
                            try:
                                result = db.delete_channel_data(selected_channel.channel_id, delete_reason)
                                
                                st.success(f"""
                                ✅ **Channel data deleted successfully!**
                                
                                - Videos processed: {result['videos_deleted']}
                                - Total chunks deleted: {result['chunks_deleted']}
                                - Guests cleaned up: {result['guests_removed']}
                                - Channel reset: {'✓' if result['channel_reset'] else '✗'}
                                
                                **All videos are now rescannable.**
                                """)
                                
                                # Log to activity
                                db.log_pipeline_event(
                                    level="WARNING",
                                    message=f"Channel data deleted: {selected_channel.name} ({len(videos)} videos)",
                                    channel_id=selected_channel.channel_id,
                                    stage="DATA_MANAGEMENT",
                                )
                                
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Deletion failed: {e}")
                                logger.error(f"Channel deletion error: {e}", exc_info=True)
        else:
            st.info("No channels available.")
        
        st.markdown("---")

        # =====================================================================
        # SECTION 3: Deletion History
        # =====================================================================
        st.markdown("### 📋 Deletion History")
        
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
            if st.checkbox("📖 View Detailed Deletion Records", key="view_deletion_details"):
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
        st.markdown("### 👤 Guest Data Cleanup")
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
        
        with st.expander("🔍 Preview Junk Guests", expanded=False):
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
                
                if st.button("🔴 PURGE JUNK GUESTS", type="primary", key="purge_guests_btn"):
                    if st.checkbox("⚠️ Confirm purge of guest records", key="confirm_purge_guests"):
                        try:
                            # Run deletion SQL
                            ids = [item["ID"] for item in to_cleanup]
                            placeholders = ",".join(["?"] * len(ids))
                            
                            # Start transaction
                            db.conn.execute("BEGIN TRANSACTION")
                            db.conn.execute(f"DELETE FROM guest_appearances WHERE guest_id IN ({placeholders})", ids)
                            db.conn.execute(f"DELETE FROM guests WHERE guest_id IN ({placeholders})", ids)
                            db.conn.commit()
                            
                            st.success(f"✅ Successfully purged {len(ids)} junk guest records!")
                            st.rerun()
                        except Exception as e:
                            db.conn.rollback()
                            st.error(f"❌ Purge failed: {e}")
            else:
                st.success("No apparent junk guests found in current vault!")

        st.markdown("---")

        # =====================================================================
        # SECTION 5: Vault Health & Repair (UPDATED)
        # =====================================================================
        st.markdown("### 🏥 Vault Health & Repair")
        
        if get_diagnostics:
            diag = get_diagnostics(db)
            
            # Health Overview Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Videos", diag["total"])
            with col2:
                st.metric("Transcripts", f"{diag['pct_transcripts']}%", delta=f"-{diag['missing_transcripts']} missing" if diag['missing_transcripts'] else None, delta_color="inverse")
            with col3:
                st.metric("Summaries", f"{diag['pct_summaries']}%", delta=f"-{diag['missing_summaries']} missing" if diag['missing_summaries'] else None, delta_color="inverse")
            with col4:
                st.metric("Heatmaps", f"{diag['pct_heatmaps']}%", delta=f"-{diag['missing_heatmaps']} missing" if diag['missing_heatmaps'] else None, delta_color="inverse")
            
            # Progress Bars
            st.write("#### Data Coverage")
            st.progress(diag['pct_transcripts'] / 100, text=f"Transcripts: {diag['pct_transcripts']}%")
            st.progress(diag['pct_summaries'] / 100, text=f"Summaries: {diag['pct_summaries']}%")
            st.progress(diag['pct_heatmaps'] / 100, text=f"Heatmaps: {diag['pct_heatmaps']}%")
            
            st.info("""
            **Vault Repair** systematically fixes identified gaps:
            - **Missing Transcripts**: Resets videos to re-fetch transcripts.
            - **Missing Summaries**: Triggers the new Map-Reduce summarization stage.
            - **Missing Heatmaps**: Refreshes metadata to include audience interest heatmaps.
            """)
            
            if st.button("🚀 RUN FULL VAULT REPAIR", type="primary", use_container_width=True):
                if run_repair:
                    run_repair()
                    st.success("✅ Unified Vault Repair started in background!")
                    st.toast("Vault health repair in progress...", icon="🏥")
                    db.log_pipeline_event(
                        level="INFO",
                        message="Manual full vault health repair started",
                        stage="REPAIR"
                    )
                    st.rerun()
                else:
                    st.error("Repair runner not available")
        else:
            st.warning("Diagnostics engine not available")

        st.markdown("---")

        # =====================================================================
        # SECTION 6: Storage Optimization Tips
        # =====================================================================
        st.markdown("### 💾 Storage Optimization Tips")
        
        with st.expander("🧹 Cleanup Recommendations", expanded=False):
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
                
                st.caption(f"📊 Estimated SQLite data size: ~{estimated_size / 1024:.1f} MB (chunks + guests)")
                st.caption("📦 ChromaDB and Neo4j may have additional storage needs")
                
            except Exception as e:
                st.error(f"Could not calculate storage: {e}")

    except Exception as e:
        st.error(f"Failed to load Data Management: {e}")
        logger.error(f"Data Management error: {e}", exc_info=True)
