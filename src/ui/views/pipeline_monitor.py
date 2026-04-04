import logging
import time
from datetime import datetime

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def render(db, run_pipeline_background):
    """Render the Pipeline Monitor page with advanced channel and video insights."""
    st.markdown("""
    <div class="main-header">
        <h1>📊 Pipeline Monitor</h1>
        <p>Real-time pipeline progress, channel health, and video quality metrics</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        # =====================================================================
        # SECTION 1: Active Scans Quick Status
        # =====================================================================
        st.markdown("### 🔄 Active Ingestion Scans")
        active_scans = db.get_active_scans()

        if active_scans:
            for scan in active_scans:
                with st.container(border=True):
                    processed = getattr(scan, 'total_processed', 0)
                    discovered = getattr(scan, 'total_discovered', 0)
                    
                    col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 1])
                    with col1:
                        st.markdown(f"**Scan ID:** `{getattr(scan, 'scan_id', 'unknown')}`")
                        st.caption(f"📍 {getattr(scan, 'source_url', 'N/A')[:60]}...")
                    with col2:
                        st.metric("Progress", f"{processed}/{discovered}")
                    with col3:
                        if discovered > 0:
                            pct = (processed / discovered) * 100
                            st.metric("Complete", f"{pct:.0f}%")
                        else:
                            st.metric("Complete", "0%")
                    with col4:
                        global_orch = getattr(st, "_global_orchestrators", {})
                        is_running = (getattr(scan, "scan_id", "") in global_orch or
                                      getattr(scan, "source_url", "") in global_orch)
                        status_label = "🟢 RUNNING" if is_running else "🟡 PAUSED"
                        st.markdown(f"**{status_label}**")

            if st.button("🔄 Refresh Status", type="secondary", key="refresh_scans"):
                st.rerun()
        else:
            st.info("No active scans running at the moment.")

        st.markdown("---")

        # =====================================================================
        # SECTION 2: Channel Quality & Performance Breakdown
        # =====================================================================
        st.markdown("### 📺 Channel Health & Quality Dashboard")
        
        try:
            channels = db.get_all_channels()
        except Exception as e:
            st.warning(f"Could not load channels: {e}")
            channels = []

        if channels:
            # Create channel summary dataframe
            channel_data = []
            for ch in channels:
                try:
                    videos = db.get_videos_by_channel(ch.channel_id)
                    if videos:
                        total = len(videos)
                        done = sum(1 for v in videos if getattr(v, "checkpoint_stage", "") == "DONE")
                        accepted = sum(1 for v in videos if getattr(v, "triage_status", "") == "ACCEPTED")
                        rejected = sum(1 for v in videos if getattr(v, "triage_status", "") == "REJECTED")
                        
                        # Calculate quality metrics
                        quality_score = (done / total * 0.4) + (accepted / max(1, accepted + rejected) * 0.6 if accepted + rejected > 0 else 0) * 100
                        
                        channel_data.append({
                            "channel_id": ch.channel_id,
                            "name": getattr(ch, 'name', 'Unknown'),
                            "videos": total,
                            "completed": done,
                            "accepted": accepted,
                            "rejected": rejected,
                            "quality_score": quality_score,
                            "last_scanned": getattr(ch, "last_scanned_at", "Never"),
                            "ch_obj": ch,
                        })
                except Exception as e:
                    logger.error(f"Error processing channel {ch.channel_id}: {e}")
                    continue

            if channel_data:
                # Display channels with expandable details
                for idx, ch_summary in enumerate(channel_data):
                    with st.expander(f"📺 **{ch_summary['name']}** | {ch_summary['completed']}/{ch_summary['videos']} videos | Quality: {ch_summary['quality_score']:.0f}%", expanded=False):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Total Videos", ch_summary['videos'])
                            st.metric("Completed", ch_summary['completed'])
                        
                        with col2:
                            st.metric("Accepted", ch_summary['accepted'])
                            st.metric("Rejected", ch_summary['rejected'])
                        
                        with col3:
                            st.metric("Quality Score", f"{ch_summary['quality_score']:.1f}%")
                            st.metric("Last Scanned", "Today" if ch_summary['last_scanned'] else "Never")
                        
                        st.markdown(f"**Channel ID:** `{ch_summary['channel_id']}`")
                        
                        # Video details sub-section
                        st.markdown("#### 📹 Recent Videos in Channel")
                        videos = db.get_videos_by_channel(ch_summary['channel_id'], limit=5)
                        if videos:
                            video_records = []
                            for v in videos:
                                try:
                                    # Get chunk/topic info
                                    topics = _get_video_topics(db, v.video_id)
                                    guests = _get_video_guests(db, v.video_id)
                                    
                                    video_records.append({
                                        "title": v.title[:45] + "..." if len(v.title) > 45 else v.title,
                                        "status": getattr(v, "triage_status", "UNKNOWN"),
                                        "stage": getattr(v, "checkpoint_stage", "UNKNOWN"),
                                        "topics": ", ".join(topics[:2]) if topics else "—",
                                        "guests": len(guests),
                                        "confidence": f"{getattr(v, 'triage_confidence', 0):.0%}",
                                    })
                                except Exception as e:
                                    logger.error(f"Error processing video {v.video_id}: {e}")
                            
                            if video_records:
                                df = pd.DataFrame(video_records)
                                st.dataframe(df, use_container_width=True, hide_index=True)
                        
                        # Guest list for channel
                        st.markdown("#### 👥 Channel Guests")
                        all_guests = set()
                        for v in db.get_videos_by_channel(ch_summary['channel_id']):
                            guests = _get_video_guests(db, v.video_id)
                            all_guests.update(guests)
                        
                        if all_guests:
                            guest_list = sorted(list(all_guests))
                            st.write(", ".join(guest_list[:10]))
                            if len(all_guests) > 10:
                                st.caption(f"... and {len(all_guests) - 10} more guests")
                        else:
                            st.caption("No guests identified yet")
                        
                        # Quick actions
                        st.markdown("#### ⚙️ Channel Actions")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🔄 Re-harvest", key=f"harvest_{ch_summary['channel_id']}", use_container_width=True):
                                if getattr(ch_summary['ch_obj'], 'url', None):
                                    run_pipeline_background(ch_summary['ch_obj'].url, db)
                                    st.success(f"Re-harvest queued for {ch_summary['name']}")
                                    st.toast("⏱️ Harvest started")
                                    time.sleep(0.5)
                                    st.rerun()
                        
                        with col2:
                            if st.button("📊 Refresh", key=f"refresh_{ch_summary['channel_id']}", use_container_width=True):
                                st.rerun()
            else:
                st.info("No channels ingested yet. Start a Harvest to begin!")

        st.markdown("---")

        # =====================================================================
        # SECTION 3: Overall Pipeline Health
        # =====================================================================
        st.markdown("### 📊 Overall Pipeline Health")
        try:
            stats = db.get_pipeline_stats()
        except Exception as e:
            st.warning(f"Metadata stats unavailable: {e}")
            stats = {}

        stages = [
            ("📥 Discovered", stats.get("discovered", 0) + stats.get("accepted", 0)
             + stats.get("rejected", 0) + stats.get("pending_review", 0)),
            ("✅ Triage Passed", stats.get("accepted", 0)),
            ("📝 Transcripts", stats.get("transcript_fetched", 0)),
            ("🧹 Refined", stats.get("refined", 0)),
            ("🔍 Indexed", stats.get("done", 0)),
        ]

        cols = st.columns(len(stages))
        for i, (label, count) in enumerate(stages):
            with cols[i]:
                st.metric(label, count)

        # Progress bars
        total = stats.get("total_videos", 1) or 1
        st.markdown("#### Pipeline Stages Progress")
        for label, count in stages:
            # Clamp progress between 0 and 1.0 to avoid Streamlit ValueError
            pct = max(0.0, min(1.0, count / total))
            st.progress(pct, text=f"{label}: {count}/{total}")

    except Exception as e:
        st.error(f"Failed to load Pipeline Monitor: {e}")
        logger.error(f"Pipeline Monitor error: {e}", exc_info=True)


def _get_video_topics(db, video_id: str) -> list[str]:
    """Extract topics for a video from its chunks."""
    try:
        chunks = db.conn.execute(
            "SELECT topics_json FROM transcript_chunks WHERE video_id = ? LIMIT 5",
            (video_id,)
        ).fetchall()
        
        topics = set()
        import json
        for chunk in chunks:
            try:
                topics_data = json.loads(chunk[0] or "[]")
                for t in topics_data:
                    if isinstance(t, dict):
                        topics.add(t.get("name", ""))
                    elif isinstance(t, str):
                        topics.add(t)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return list(topics)[:5]
    except Exception as e:
        logger.debug(f"Could not get topics for {video_id}: {e}")
        return []


def _get_video_guests(db, video_id: str) -> list[str]:
    """Extract guest names for a video."""
    try:
        guests = db.conn.execute(
            """SELECT DISTINCT g.canonical_name FROM guest_appearances ga
               JOIN guests g ON ga.guest_id = g.guest_id
               WHERE ga.video_id = ?
               LIMIT 10""",
            (video_id,)
        ).fetchall()
        
        return [g[0] for g in guests if g[0]]
    except Exception as e:
        logger.debug(f"Could not get guests for {video_id}: {e}")
        return []

