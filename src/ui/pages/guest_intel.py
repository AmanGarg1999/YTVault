"""Guest Intelligence page for knowledgeVault-YT."""

import logging

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def render(db):
    """Render the Guest Intelligence page."""
    st.markdown("""
    <div class="main-header">
        <h1>👤 Guest Intelligence</h1>
        <p>Explore guests across channels — appearances, topics, and cross-references</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        guests = db.get_all_guests()

        if not guests:
            st.info("No guests discovered yet. Run the pipeline with graph sync enabled.")
        else:
            guest_names = [g.canonical_name for g in guests]
            selected_name = st.selectbox(
                "Select Guest", guest_names,
                help="Browse all discovered guests sorted by mention count",
            )

            if selected_name:
                guest = next(g for g in guests if g.canonical_name == selected_name)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Mentions", guest.mention_count)
                with col2:
                    st.metric("Aliases", len(guest.aliases))
                with col3:
                    st.metric("Type", guest.entity_type)

                if guest.aliases:
                    st.markdown(f"**Also known as:** {', '.join(guest.aliases)}")

                st.markdown("### 📺 Appearances")
                appearances = db.conn.execute(
                    """SELECT ga.context_snippet, ga.start_timestamp, ga.end_timestamp,
                              v.title, v.video_id, v.upload_date, v.channel_id
                       FROM guest_appearances ga
                       JOIN videos v ON ga.video_id = v.video_id
                       WHERE ga.guest_id = ?
                       ORDER BY v.upload_date DESC""",
                    (guest.guest_id,),
                ).fetchall()

                if appearances:
                    for app in appearances:
                        d = dict(app)
                        vid_url = f"https://www.youtube.com/watch?v={d['video_id']}"
                        ts = int(d.get('start_timestamp', 0))
                        ts_str = f"{ts // 60:02d}:{ts % 60:02d}"

                        channel = db.get_channel(d.get('channel_id', ''))
                        ch_name = channel.name if channel else 'Unknown'

                        with st.expander(f"📺 {d['title'][:60]}... ({ch_name})"):
                            st.markdown(f"**Channel:** {ch_name}")
                            st.markdown(f"**Date:** {d.get('upload_date', 'Unknown')}")
                            st.markdown(f"**Timestamp:** [{ts_str}]({vid_url}&t={ts}s)")
                            if d.get('context_snippet'):
                                st.markdown(f"**Context:** {d['context_snippet'][:300]}")
                else:
                    st.info("No recorded appearances yet. Process more videos with graph sync.")

            # Top guests overview
            st.markdown("---")
            st.markdown("### 🏆 Most Referenced Guests")

            guest_data = [{
                "Name": g.canonical_name,
                "Mentions": g.mention_count,
                "Type": g.entity_type,
                "Aliases": len(g.aliases),
                "First Seen": g.first_seen[:10] if g.first_seen else "",
            } for g in guests[:20]]

            if guest_data:
                df = pd.DataFrame(guest_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Failed to load Guest Intelligence: {e}")
        logger.error(f"Guest Intelligence error: {e}", exc_info=True)
