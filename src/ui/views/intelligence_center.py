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
    
    try:
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
                    # Contextual Button with Robust Validation
                    import re
                    yt_pattern = r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$"
                    is_url = bool(re.match(yt_pattern, query))
                    
                    if st.button("Harvest" if is_url else "Search", type="primary", use_container_width=True):
                        if is_url:
                            run_pipeline_background(query, db)
                            st.toast("Intelligence Harvest Started", icon="✦")
                        elif query:
                            if "." in query:
                                # Use session state to ensure toast persists through re-render
                                st.session_state.harvest_fallback_hint = True
                        elif not query.strip():
                            st.toast("Search Query Required", icon="⚠️")

            if st.session_state.get("harvest_fallback_hint"):
                st.toast("Note: YouTube only supported for Harvest. Searching instead.", icon="🔍")
                st.session_state.harvest_fallback_hint = False

            # 1.5 Pinned Searches (Quick access)
            pins = db.get_pinned_searches()
            if pins:
                st.markdown("<div style='display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;'>", unsafe_allow_html=True)
                for p in pins:
                    if st.button(f"📌 {p['query'][:20]}", key=f"pin_{p['id']}", help=p['query']):
                        # Set query and trigger search logic by rerunning with the query set
                        st.session_state.intel_center_command = p['query']
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            if query and not is_url:
                if st.button("Pin this Search Query", key="pin_current_query"):
                    db.pin_search(query)
                    st.toast("Query Pinned to Command Bar", icon="📌")
                    st.rerun()

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
    except Exception as e:
        from src.ui.components.ui_helpers import error_card
        error_card("Intelligence Discovery Failure", f"A component error occurred: {e}")
        logger.error(f"Intelligence Center Error: {e}", exc_info=True)


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
    
    # 2. Saved Discoveries
    saved = db.get_saved_discoveries(limit=3)
    if saved:
        spacer("2rem")
        section_header("Saved Discoveries", icon="🛡")
        for s in saved:
            with glass_card():
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{s['query']}**")
                    st.caption(f"Source: {s['title']} | Saved {s['created_at'][:10]}")
                    st.write(f"_{s['snippet'][:150]}..._")
                with c2:
                    if st.button("Details", key=f"saved_det_{s['id']}", use_container_width=True):
                        st.session_state.side_car_active = True
                        st.session_state.active_video_id = s['video_id']
                        st.rerun()
                    if st.button("Delete", key=f"saved_del_{s['id']}", use_container_width=True):
                        db.delete_saved_discovery(s['id'])
                        st.rerun()

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
    
    # Hybrid Search logic with progress indicators
    try:
        with st.status("✦ Hybrid Intelligence Discovery...", expanded=True) as status:
            st.write("✦ Scanning relational archives (SQL)...")
            kw_results = db.fulltext_search(query, limit=10)
            
            if vector_online:
                st.write("✦ Activating neural retrieval (Vector DB)...")
                vector_results = vs.search(query, top_k=10)
            else:
                st.write("✦ Neural store offline, skipping semantic pass.")
                vector_results = []
            
            st.write("✦ Synthesizing and ranking results...")
            
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
            
            status.update(label=f"✦ Found {len(all_results)} Relevant Matches", state="complete", expanded=False)

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
                c_act1, c_act2 = st.columns(2)
                with c_act1:
                    if st.button("Analyze Details", key=f"src_det_{v_id}", use_container_width=True):
                        st.session_state.side_car_active = True
                        st.session_state.active_video_id = v_id
                        st.rerun()
                with c_act2:
                    if st.button("Save Discovery", key=f"src_save_{v_id}", use_container_width=True):
                        db.save_discovery(query, v_id, snippet, r_type)
                        st.toast("Intelligence Saved to Vault", icon="🛡")
    except Exception as e:
        st.error(f"Search failed: {e}")
