"""Topic Explorer page for knowledgeVault-YT — Consolidated thematic insights."""

import json
import streamlit as st
from src.ui.components import (
    page_header,
    section_header,
    metric_grid,
    info_card,
    status_badge,
    spacer,
    tts_button
)

def render(db):
    """Render the Topic Explorer page."""
    
    # 1. Page Header
    page_header(
        title="Topic Explorer",
        subtitle="Consolidated thematic insights across your entire knowledge vault"
    )

    # 2. Fetch Consolidated Topics
    topics = db.get_consolidated_topics()
    
    if not topics:
        info_card("No Topics Found", "Injest and analyze more videos to see consolidated topics here.")
        return

    # 3. Sidebar Filters & Stats
    st.sidebar.markdown("### Vault Summary")
    st.sidebar.metric("Unique Topics", len(topics))
    
    search_query = st.sidebar.text_input("Search Topics", "")
    
    # Filter topics based on search
    if search_query:
        filtered_topics = [t for t in topics if search_query.lower() in t["name"].lower()]
    else:
        filtered_topics = topics

    # 4. Detail View vs. Gallery View
    selected_topic = st.session_state.get("selected_topic")
    
    if selected_topic:
        _render_topic_detail(db, selected_topic)
    else:
        _render_topic_gallery(filtered_topics)

def _render_topic_gallery(topics):
    """Render the grid of topic cards."""
    st.markdown("#### Knowledge Clusters")
    
    # Responsive grid for topics
    cols = st.columns(3)
    for idx, topic in enumerate(topics):
        with cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"### {topic['name']}")
                
                # Metrics in a small row
                st.markdown(f"""
                <div style="display: flex; gap: 1rem; color: #888; font-size: 0.9rem;">
                    <span>{topic['video_count']} Videos</span>
                    <span>{topic['channel_count']} Channels</span>
                </div>
                """, unsafe_allow_html=True)
                
                spacer("0.5rem")
                
                if st.button("Deep Dive", key=f"btn_{topic['name']}"):
                    st.session_state.selected_topic = topic["name"]
                    st.rerun()

def _render_topic_detail(db, topic_name):
    """Render the detailed view for a single topic."""
    
    if st.button("Back to Gallery"):
        st.session_state.selected_topic = None
        st.rerun()
        
    details = db.get_topic_details(topic_name)
    
    if not details:
        st.error(f"No details found for topic: {topic_name}")
        return

    # Header with topic name and consolidated stats
    channels = sorted(list(set(d["channel_name"] for d in details)))
    
    st.markdown(f"# {topic_name}")
    
    m_grid = [
        {"value": len(details), "label": "Source Videos"},
        {"value": len(channels), "label": "Discussing Channels"},
    ]
    metric_grid(m_grid, cols=2)
    
    st.divider()
    
    # 1. Synthesized Perspective (Aggregate takeaways)
    section_header("Consolidated Insights")
    
    # Create a mega-summary for TTS
    all_takeaways = []
    for d in details:
        all_takeaways.extend(d["takeaways"])
    
    # Deduplicate takeaways (simple list unique)
    unique_takeaways = sorted(list(set(all_takeaways)))[:15] # Top 15
    
    takeaway_text = "\n".join([f"- {t}" for t in unique_takeaways])
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(takeaway_text)
    with col2:
        tts_button(f"Topic Summary for {topic_name}: {takeaway_text}", label="Listen to Brief")

    st.divider()

    # 2. Channel Perspectives
    section_header("Expert Perspectives")
    
    for channel in channels:
        channel_clips = [d for d in details if d["channel_name"] == channel]
        with st.expander(f"{channel} ({len(channel_clips)} insights)", expanded=False):
            for clip in channel_clips:
                st.markdown(f"**Video:** [{clip['title']}]({clip['url']}) (`{clip['upload_date']}`)")
                st.info(clip["summary_text"])
                
                # Check for specific topic meta
                meta = clip.get("topic_meta", {})
                if meta.get("sentiment"):
                    st.caption(f"Sentiment: {meta['sentiment']}")
                
                if meta.get("opportunities"):
                    st.markdown("**Opportunities Identified:**")
                    for opp in meta["opportunities"]:
                        st.caption(f" - {opp}")
                
                st.divider()

    # 3. Expert Clashes (Debates)
    clashes = db.get_clashes_by_topic(topic_name)
    if clashes:
        st.divider()
        section_header("Expert Clashes & Debates")
        for clash in clashes:
            with st.container(border=True):
                col_a, col_vs, col_b = st.columns([2, 1, 2])
                with col_a:
                    st.markdown(f"**{clash.expert_a}**")
                    st.info(clash.claim_a)
                with col_vs:
                    st.markdown("<h3 style='text-align: center; color: #ef4444;'>VS</h3>", unsafe_allow_html=True)
                with col_b:
                    st.markdown(f"**{clash.expert_b}**")
                    st.warning(clash.claim_b)
                
                st.caption(f"Topic: {clash.topic} | Source A: [View Video](https://www.youtube.com/watch?v={clash.source_a})")

    # 4. Source Library
    section_header("Source Library")
    st.dataframe(
        [{"Date": d["upload_date"], "Channel": d["channel_name"], "Title": d["title"]} for d in details],
        use_container_width=True,
        hide_index=True
    )
