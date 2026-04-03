"""Dashboard page for knowledgeVault-YT."""

import json
import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(db):
    """Render the Dashboard page."""
    st.markdown("""
    <div class="main-header">
        <h1>🧠 knowledgeVault-YT</h1>
        <p>Local-first Research Intelligence System — Transform YouTube into a Knowledge Graph</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        stats = db.get_pipeline_stats()

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📺 Channels", stats.get("total_channels", 0))
        with col2:
            st.metric("🎬 Videos", stats.get("total_videos", 0))
        with col3:
            st.metric("✅ Accepted", stats.get("accepted", 0))
        with col4:
            st.metric("🔍 Indexed Chunks", stats.get("total_chunks", 0))
        with col5:
            st.metric("👤 Guests", stats.get("total_guests", 0))

        # Pipeline progress
        st.markdown("### Pipeline Progress")
        total = stats.get("total_videos", 0)
        if total > 0:
            done = stats.get("done", 0)
            progress = done / total
            st.progress(progress, text=f"{done}/{total} videos fully processed ({progress:.0%})")
        else:
            st.info("No videos ingested yet. Start a Harvest to begin!")

        # Recent activity
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("### 📋 Pending Review")
            pending = db.get_videos_by_status("PENDING_REVIEW", limit=5)
            if pending:
                for v in pending:
                    st.markdown(f"- **{v.title[:60]}...** ({v.triage_confidence:.0%} conf)")
            else:
                st.success("No videos pending review!")

        with col_b:
            st.markdown("### 🔄 Active Scans")
            scans = db.get_active_scans()
            if scans:
                for s in scans:
                    st.markdown(
                        f"- `{s.scan_id}` — {s.total_processed}/{s.total_discovered} "
                        f"({s.scan_type})"
                    )
            else:
                st.info("No active scans.")

        # Knowledge Density Leaderboard
        st.markdown("---")
        st.markdown("### 🏆 Knowledge Density Leaderboard")
        st.caption("Top 10 videos ranked by density of extracted topics and guest entities per minute of runtime.")

        leaderboard = db.get_knowledge_density_leaderboard(limit=10)
        if leaderboard:
            for row in leaderboard:
                with st.container(border=True):
                    col1, col2, col3, col4, col5 = st.columns([4, 2, 2, 2, 2])
                    with col1:
                        st.markdown(f"**{row['title']}**")
                        st.caption(f"📺 {row['channel_name']}")
                    with col2:
                        st.metric("Density", f"{row['density_score']:.2f}")
                    with col3:
                        st.metric("Guests", row["guest_count"])
                    with col4:
                        st.metric("Chunks", row["chunk_count"])
                    with col5:
                        if st.button("📝 Summarize", key=f"dash_sum_{row['video_id']}"):
                            st.session_state[f"show_sum_{row['video_id']}"] = True

                    # Expanded summary view
                    if st.session_state.get(f"show_sum_{row['video_id']}", False):
                        from src.intelligence.summarizer import SummarizerEngine
                        summarizer = SummarizerEngine(db)
                        summary = summarizer.get_or_generate_summary(row['video_id'])
                        if summary:
                            with st.expander("📝 Deep Video Insights", expanded=True):
                                st.write(summary.summary_text)
                                s_col1, s_col2 = st.columns(2)
                                with s_col1:
                                    st.markdown("**Core Topics**")
                                    try:
                                        topics = json.loads(summary.topics_json)
                                        for t in topics:
                                            st.markdown(f"- **{t['name']}** ({t.get('relevance', 0.5):.1f})")
                                    except Exception:
                                        st.write("No topics available.")
                                with s_col2:
                                    st.markdown("**Key Takeaways**")
                                    try:
                                        takeaways = json.loads(summary.takeaways_json)
                                        for tk in takeaways:
                                            st.markdown(f"📌 {tk}")
                                    except Exception:
                                        st.write("No takeaways available.")
                                if st.button("Close", key=f"close_dash_{row['video_id']}"):
                                    st.session_state[f"show_sum_{row['video_id']}"] = False
                                    st.rerun()
        else:
            st.info("Leaderboard will populate once videos are fully ingested and indexed.")
    except Exception as e:
        st.error(f"Failed to load Dashboard: {e}")
        logger.error(f"Dashboard error: {e}", exc_info=True)
