"""Comparative Lab - Analyze and compare topics across multiple channels."""

import logging
import streamlit as st
import pandas as pd
import time
from src.intelligence.rag_engine import RAGEngine
from src.config import load_prompt

logger = logging.getLogger(__name__)

def render(db, vs):
    """Render the Comparative Lab research interface."""
    
    st.markdown("""
    <div class="main-header">
        <h1>Comparative Lab</h1>
        <p>Synthesize and compare perspectives across multiple channels</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar parameters
    with st.sidebar:
        st.markdown("### Analysis Parameters")
        top_k = st.slider("Context chunks per channel", 5, 20, 10)
        diversity_weight = st.slider("Synthesis Focus", 0.0, 1.0, 0.5, 
                                   help="0: Detail heavy, 1: Comparison heavy")
        st.markdown("---")

    # Channel Selection
    channels = db.get_all_channels()
    if not channels:
        st.warning("No channels found. Please ingest some content first.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_channels = st.multiselect(
            "Select Channels to Compare",
            options=channels,
            format_func=lambda c: f"{c.name}",
            help="Choose 2 or more channels for the best comparative results."
        )
    
    with col2:
        topic = st.text_input(
            "Research Topic / Query",
            placeholder="e.g., 'Artificial Intelligence', 'Economic Policy'",
            help="Enter the specific topic you want to compare across these channels."
        )

    if st.button("Run Comparative Analysis", type="primary", disabled=not (selected_channels and topic)):
        with st.status("Analyzing cross-channel perspectives...", expanded=True) as status:
            try:
                # 1. Initialize RAG Engine
                rag = RAGEngine(db, vs)
                # Override system prompt for comparative analysis
                rag.system_prompt = load_prompt("comparative_analyst")
                
                channel_ids = [c.channel_id for c in selected_channels]
                channel_names = {c.channel_id: c.name for c in selected_channels}
                
                status.write(f"Searching across {len(channel_ids)} channels...")
                
                # 2. Perform RAG Query with channel filters
                # We use the 'filters' argument supported by RAGEngine.query
                where_filter = {"channel_id": {"$in": channel_ids}} if len(channel_ids) > 1 else {"channel_id": channel_ids[0]}
                
                response = rag.query(
                    question=topic,
                    filters=where_filter
                )
                
                status.update(label="Analysis complete!", state="complete")

                # 3. Display Results
                st.markdown("---")
                st.markdown("## Comparative Synthesis")
                st.markdown(response.answer)
                
                # 4. Display Sources & Citations
                with st.expander("Evidence & Citations"):
                    if response.citations:
                        # Group citations by channel
                        by_channel = {}
                        for c in response.citations:
                            by_channel.setdefault(c.channel_name, []).append(c)
                        
                        for chan_name, citations in by_channel.items():
                            st.markdown(f"**From {chan_name}:**")
                            for cit in citations:
                                st.markdown(
                                    f"- [{cit.source_id}] *\"{cit.video_title}\"* "
                                    f"([link]({cit.youtube_link}))\n"
                                    f"  > ...{cit.text_excerpt}..."
                                )
                    else:
                        st.info("No matching evidence found in the selected channels.")

                # 5. Metrics & Confidence
                if response.confidence:
                    cols = st.columns(3)
                    with cols[0]:
                        st.metric("Source Diversity", f"{response.confidence.source_diversity:.1%}")
                    with cols[1]:
                        st.metric("Context Relevance", f"{response.confidence.chunk_relevance:.1%}")
                    with cols[2]:
                        st.metric("Overall Confidence", f"{response.confidence.overall:.1%}")

                # 6. Content Gap Analysis (New Feature)
                st.divider()
                st.markdown("## Content Gap Analysis")
                st.caption("Identifying high-performing topics from one channel that are missing in others.")
                
                render_content_gap_analysis(db, channel_ids, channel_names)

            except Exception as e:
                status.update(label="Analysis failed", state="error")
                st.error(f"Analysis error: {e}")
                logger.error(f"Comparative Lab error: {e}", exc_info=True)

    # Footer - Sample Topics
    st.markdown("---")
    st.caption("Tip: Try comparing a technical topic like '3D rendering' or a conceptual one like 'Creative Freedom'.")


def render_content_gap_analysis(db, channel_ids, channel_names):
    """Analyze and display topic gaps between channels."""
    if len(channel_ids) < 2:
        st.info("Select at least 2 channels to enable Gap Analysis.")
        return

    try:
        # 1. Get top videos for each channel
        channel_data = {}
        for cid in channel_ids:
            videos = db.execute("""
                SELECT v.video_id, v.title, v.view_count,
                       (CAST(v.like_count + v.comment_count AS REAL) / NULLIF(v.view_count, 0)) as engagement_rate
                FROM videos v
                WHERE v.channel_id = ?
                ORDER BY engagement_rate DESC, v.view_count DESC
                LIMIT 10
            """, (cid,)).fetchall()
            
            # Simple keyword extraction from titles
            all_keywords = set()
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "is", "are", "how", "to", "you", "your", "that"}
            for v in videos:
                import re
                title_clean = re.sub(r'[^\w\s]', '', v["title"].lower())
                words = title_clean.split()
                keywords = [w for w in words if len(w) > 3 and w not in stop_words]
                all_keywords.update(keywords)
            
            channel_data[cid] = {
                "name": channel_names[cid],
                "keywords": all_keywords,
                "top_videos": videos
            }

        # 2. Compare and find gaps
        for i, cid_a in enumerate(channel_ids):
            other_cids = [cid for cid in channel_ids if cid != cid_a]
            
            unique_keywords = channel_data[cid_a]["keywords"].copy()
            for other_cid in other_cids:
                unique_keywords -= channel_data[other_cid]["keywords"]
            
            if unique_keywords:
                with st.expander(f"Unique Strengths of **{channel_data[cid_a]['name']}**", expanded=(i==0)):
                    st.write(f"Topics that are high-performing for {channel_data[cid_a]['name']} but missing from others:")
                    
                    # Sort keywords by how often they appear in top video titles
                    keyword_counts = {}
                    for v in channel_data[cid_a]["top_videos"]:
                        title = v["title"].lower()
                        for kw in unique_keywords:
                            if kw in title:
                                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
                    
                    sorted_kws = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
                    
                    if sorted_kws:
                        cols = st.columns(min(len(sorted_kws), 4) or 1)
                        for idx, (kw, count) in enumerate(sorted_kws[:12]):
                            with cols[idx % len(cols)]:
                                st.markdown(f"`{kw.upper()}`")
                                st.caption(f"Used in {count} top videos")
                    else:
                        st.info("No unique high-performing keywords detected in top videos.")
            else:
                st.info(f"No significant content gap found for **{channel_data[cid_a]['name']}**.")

    except Exception as e:
        st.error(f"Gap Analysis error: {e}")
        logger.error(f"Gap Analysis error: {e}", exc_info=True)
