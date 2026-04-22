"""Intelligence Center - Unified Discovery & Synthesis Hub."""

import streamlit as st
import logging
import json
import pandas as pd
from types import SimpleNamespace
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.ui.components import (
    page_header,
    section_header,
    metric_grid,
    info_card,
    success_card,
    glass_card,
    video_card,
    side_car_layout,
    render_side_car,
    spacer,
    tts_button
)

logger = logging.getLogger(__name__)

def render_insights(db, video_id):
    """Render details for the side-car panel."""
    try:
        from src.intelligence.summarizer import SummarizerEngine
        summarizer = SummarizerEngine(db)
        summary = summarizer.get_or_generate_summary(video_id)
        
        if summary:
            st.markdown(f"**Research Summary**")
            st.write(summary.summary_text)
            tts_button(summary.summary_text, key=f"tts_side_{video_id}")
            st.divider()
            st.markdown("**Core Takeaways**")
            try:
                takeaways = json.loads(summary.takeaways_json)
                for tk in takeaways: st.markdown(f"- {tk}")
            except: st.caption("No structured takeaways available.")
        else:
            st.warning("Analysis in progress...")
    except Exception as e:
        st.error(f"Insight Engine Error: {e}")

def render(db: SQLiteStore, vs: VectorStore, run_pipeline_background):
    """Render the unified Intelligence Center."""
    
    # Side-car logic
    main_col, side_col = side_car_layout()
    
    with main_col:
        page_header(
            "Intelligence Center",
            "Command center for discovery, ingestion, and knowledge synthesis."
        )

        # 1. COMMAND BAR (Search + Harvest)
        with glass_card():
            col_in, col_btn = st.columns([5, 1])
            with col_in:
                query = st.text_input(
                    "Command Search...", 
                    placeholder="Search vault or paste YouTube URL to harvest...",
                    label_visibility="collapsed",
                    key="intel_center_command"
                )
            with col_btn:
                # Contextual Button
                is_url = "youtube.com" in query or "youtu.be" in query
                if st.button("Harvest" if is_url else "Search", type="primary", use_container_width=True):
                    if is_url:
                        run_pipeline_background(query, db)
                        st.toast("Harvest Started", icon="✦")
                    elif query:
                        if "." in query:
                            # Use session state to ensure toast persists through re-render
                            st.session_state.harvest_fallback_hint = True
                    elif not query:
                        st.toast("Input Required", icon="⚠️")

        if st.session_state.get("harvest_fallback_hint"):
            st.toast("Note: YouTube only supported for Harvest. Searching instead.", icon="🔍")
            st.session_state.harvest_fallback_hint = False

        spacer("2rem")

        if query and not is_url:
            # Render Search Results
            render_search_results(db, vs, query)
        else:
            # Render Dashboard Overview
            render_overview(db)

    # Side-car Rendering
    if side_col and st.session_state.get("active_video_id"):
        with side_col:
            video_id = st.session_state.active_video_id
            v_title = db.conn.execute("SELECT title FROM videos WHERE video_id = ?", (video_id,)).fetchone()
            render_side_car(v_title[0][:40]+"..." if v_title else "Intel Detail", lambda: render_insights(db, video_id))


def render_overview(db):
    """Dashboard Stats & High-Density Intel."""
    stats = db.get_pipeline_stats()
    
    # 1. Metrics
    metrics = [
        {"value": stats.get("total_channels", 0), "label": "Channels", "glow": True},
        {"value": stats.get("total_videos", 0), "label": "Videos"},
        {"value": stats.get("accepted", 0), "label": "Indexed"},
        {"percentage": min(100, int((stats.get('done', 0) / max(stats.get('accepted', 1), 1) * 100))), "label": "Vault Health"}
    ]
    metric_grid(metrics, cols=4)
    
    spacer("2rem")
    section_header("High-Density Intel", icon="◈")
    leaderboard = db.get_knowledge_density_leaderboard(limit=5)
    if leaderboard:
        for row in leaderboard:
            v_obj = SimpleNamespace(**row)
            cols = video_card(v_obj, show_actions=True)
            if cols:
                with cols[0]:
                    if st.button("Analyze", key=f"btn_anal_{row['video_id']}", use_container_width=True):
                        st.session_state.side_car_active = True
                        st.session_state.active_video_id = row['video_id']
                        st.rerun()
                with cols[1]:
                    if st.button("Read", key=f"btn_src_{row['video_id']}", use_container_width=True):
                        st.session_state.navigate = "Transcripts"
                        st.session_state.selected_transcript_vid = row['video_id']
                        st.rerun()
    else:
        info_card("Knowledge Base Initializing", "Metadata is being harvested...")


def render_search_results(db, vs, query):
    """Hybrid Search Results."""
    section_header(f"Results for: {query[:30]}", icon="🔍")
    
    vector_online = vs is not None and hasattr(vs, 'is_ready') and vs.is_ready()
    
    # Simplified Hybrid Search logic
    try:
        kw_results = db.fulltext_search(query, limit=10)
        vector_results = vs.search(query, top_k=10) if vector_online else []
        
        # Merge for display
        seen_ids = set()
        all_results = []
        
        # Process Keyword
        for res in kw_results:
            v_id = res.get("video_id")
            if v_id not in seen_ids:
                all_results.append((v_id, res.get("snippet", ""), "Keyword"))
                seen_ids.add(v_id)
        
        # Process Vector
        for res in vector_results:
            v_id = res.get("metadata", {}).get("video_id")
            if v_id and v_id not in seen_ids:
                all_results.append((v_id, res.get("text", "")[:200], "Semantic"))
                seen_ids.add(v_id)

        if not all_results:
            info_card("No Results", "Try broader keywords.")
            return

        for v_id, snippet, r_type in all_results:
            video = db.get_video(v_id)
            if not video: continue
            with glass_card():
                st.markdown(f"### {video.title}")
                st.caption(f"{r_type} Match | {video.upload_date}")
                st.markdown(f"_{snippet}_")
                if st.button("Analyze Details", key=f"src_det_{v_id}"):
                    st.session_state.side_car_active = True
                    st.session_state.active_video_id = v_id
                    st.rerun()
    except Exception as e:
        st.error(f"Search failed: {e}")
