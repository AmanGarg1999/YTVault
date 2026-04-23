"""
Blueprint Center page for knowledgeVault-YT — The Execution OS.
Enhanced with rich, timestamped steps, progress tracking, and Nebula-Glassmorphism UI.
"""

import streamlit as st
import json
import logging
from datetime import datetime
from src.ui.components import (
    page_header,
    section_header,
    glass_card,
    info_card,
    spacer,
    status_badge
)
from src.config import get_settings
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.summarizer import SummarizerEngine
import threading

logger = logging.getLogger(__name__)

def render(db):
    """Render the Blueprint Center page."""
    
    page_header(
        title="Execution OS",
        subtitle="High-fidelity actionable blueprints extracted from your research vault"
    )

    # 1. Fetch all blueprints
    blueprints = db.get_all_blueprints()
    
    if not blueprints:
        info_card(
            "No Blueprints Identified", 
            "The Intelligence Engine identifies procedural blueprints from tutorials. Ingest more educational content to see them here."
        )
        return

    # Initialize upgrade registry in session state
    if "blueprint_upgrades" not in st.session_state:
        st.session_state.blueprint_upgrades = {}

    # 2. Sidebar Search & Stats
    st.sidebar.markdown("### 📊 Vault Intelligence")
    st.sidebar.metric("Execution Guides", len(blueprints))
    
    search_query = st.sidebar.text_input(
        "Search Blueprints", 
        "", 
        placeholder="Search procedures...",
    )
    
    # Filter by search
    if search_query:
        filtered = [
            b for b in blueprints 
            if search_query.lower() in b["title"].lower() or 
            search_query.lower() in b["channel_name"].lower()
        ]
    else:
        filtered = blueprints

    if not filtered:
        st.warning("No execution guides match your current filter.")
        return

    # 3. Main Content
    for bp in filtered:
        render_blueprint_card(db, bp)

def render_blueprint_card(db, bp):
    """Render a single blueprint card with progress tracking and rich steps."""
    video_id = bp["video_id"]
    title = bp["title"]
    channel = bp["channel_name"]
    created_at = bp["created_at"]
    
    # Parse steps
    steps_raw = bp.get("steps_json", "[]")
    try:
        if isinstance(steps_raw, str):
            steps = json.loads(steps_raw)
        else:
            steps = steps_raw
    except Exception as e:
        logger.error(f"Failed to parse steps for blueprint {video_id}: {e}")
        steps = []

    # Parse progress
    progress_raw = bp.get("progress_json", "{}")
    try:
        if isinstance(progress_raw, str):
            progress_state = json.loads(progress_raw)
        else:
            progress_state = progress_raw
    except Exception as e:
        logger.error(f"Failed to parse progress for blueprint {video_id}: {e}")
        progress_state = {}

    with glass_card():
        # Header Row
        col_title, col_meta = st.columns([3, 1])
        with col_title:
            st.markdown(f"### {title}")
            st.markdown(f"**Source**: {channel} | **Identified**: {created_at}")
        with col_meta:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            st.link_button("🎥 Watch Tutorial", video_url, use_container_width=True)
            
            # Progress calculation
            if steps:
                completed_count = sum(1 for i in range(len(steps)) if progress_state.get(str(i)))
                total = len(steps)
                prog_pct = completed_count / total
                st.progress(prog_pct, text=f"{completed_count}/{total} Complete")
                
                if prog_pct == 1.0:
                    st.markdown(status_badge("success", "FULLY MASTERED"), unsafe_allow_html=True)
                elif prog_pct > 0:
                    st.markdown(status_badge("warning", "IN PROGRESS"), unsafe_allow_html=True)
        
        # --- AUTOMATIC UPGRADE LOGIC ---
        is_legacy = False
        if steps and isinstance(steps[0], str):
            is_legacy = True
        
        if is_legacy:
            if video_id not in st.session_state.blueprint_upgrades:
                # Trigger silent upgrade
                st.session_state.blueprint_upgrades[video_id] = "processing"
                threading.Thread(target=trigger_blueprint_upgrade, args=(video_id,), daemon=True).start()
                st.toast(f"✨ Auto-upgrading {title[:20]} to rich format...", icon="🚀")
            
            st.info("✨ **Intelligence Upgrade in Progress**: We're automatically extracting rich descriptions and timestamps for this guide. Refresh in a few moments to see the enhanced view.")
            st.markdown(status_badge("info", "UPGRADING..."), unsafe_allow_html=True)
        # -------------------------------

        st.divider()

        if not steps:
            st.info("No procedural steps were extracted for this blueprint.")
            return

        # Render Steps
        for idx, step_data in enumerate(steps):
            render_step(db, video_id, idx, step_data, progress_state)

def render_step(db, video_id, idx, step_data, progress_state):
    """Render a single step within a blueprint."""
    # Handle different step formats (newest → oldest)
    if isinstance(step_data, str):
        # Legacy: plain string
        title = step_data
        description = ""
        timestamp = ""
        difficulty = ""
    elif isinstance(step_data, dict) and "action" in step_data:
        # New structured format: {step_number, action, detail}
        title = step_data.get("action", f"Step {idx+1}")
        description = step_data.get("detail", "")
        timestamp = step_data.get("timestamp", "")
        difficulty = step_data.get("difficulty", "")
    else:
        # Intermediate format: {step/title, description, timestamp, difficulty}
        title = step_data.get("step", step_data.get("title", f"Step {idx+1}"))
        description = step_data.get("description", "")
        timestamp = step_data.get("timestamp", "")
        difficulty = step_data.get("difficulty", "Standard")

    step_key = str(idx)
    is_checked = progress_state.get(step_key, False)

    # UI for the step
    with st.container():
        c1, c2, c3 = st.columns([0.1, 3.5, 0.8])
        
        with c1:
            # Checkbox for completion
            new_val = st.checkbox("", value=is_checked, key=f"check_{video_id}_{idx}", label_visibility="collapsed")
            if new_val != is_checked:
                progress_state[step_key] = new_val
                # Force module reload to bypass deep caching issues
                try:
                    import importlib
                    import src.storage.sqlite_store as storage_mod
                    importlib.reload(storage_mod)
                    from src.storage.sqlite_store import SQLiteStore as LocalDB
                    
                    if hasattr(db, "update_blueprint_progress"):
                        db.update_blueprint_progress(video_id, progress_state)
                    elif hasattr(LocalDB, "update_blueprint_progress"):
                         LocalDB.update_blueprint_progress(db, video_id, progress_state)
                    else:
                        st.error(f"Storage Error: Method '{'update_blueprint_progress'}' still missing after reload. Please restart container.")
                except Exception as e:
                    st.error(f"Internal Reload Error: {e}")
                st.rerun()

        with c2:
            st.markdown(f"**{title}**")
            if description:
                with st.expander("Details", expanded=False):
                    st.write(description)
            
            # Metadata row for step
            meta_items = []
            if timestamp:
                meta_items.append(f"⏱️ `{timestamp}`")
            if difficulty:
                meta_items.append(f"🎯 {difficulty}")
            
            if meta_items:
                st.caption(" | ".join(meta_items))

        with c3:
            if timestamp:
                # Convert timestamp (MM:SS or HH:MM:SS) to seconds
                seconds = timestamp_to_seconds(timestamp)
                jump_url = f"https://www.youtube.com/watch?v={video_id}&t={seconds}"
                st.link_button("🕒 Jump", jump_url, use_container_width=True)

    spacer("0.5rem")

def timestamp_to_seconds(ts_str):
    """Convert common timestamp formats to total seconds."""
    if not ts_str:
        return 0
    try:
        parts = ts_str.split(':')
        if len(parts) == 3: # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2: # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        return 0
    except:
        return 0

def trigger_blueprint_upgrade(video_id):
    """Background task to re-summarize a video and upgrade its blueprint."""
    try:
        settings = get_settings()
        # Create fresh DB connection for this thread
        thread_db = SQLiteStore(settings["sqlite"]["path"])
        summarizer = SummarizerEngine(thread_db)
        
        logger.info(f"Auto-upgrade started for video: {video_id}")
        # Force re-generation of the summary which includes the rich blueprint
        summarizer.generate_summary(video_id)
        
        logger.info(f"Auto-upgrade completed for video: {video_id}")
        thread_db.close()
    except Exception as e:
        logger.error(f"Auto-upgrade failed for {video_id}: {e}")
