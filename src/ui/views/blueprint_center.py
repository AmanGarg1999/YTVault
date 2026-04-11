"""Blueprint Center page for knowledgeVault-YT — Actionable checklists from tutorials."""

import streamlit as st
from src.ui.components import (
    page_header,
    section_header,
    info_card,
    spacer
)

def render(db):
    """Render the Blueprint Center page."""
    
    page_header(
        title="Blueprint Center",
        subtitle="Step-by-step actionable checklists extracted from your vault"
    )

    # 1. Fetch all blueprints
    blueprints = db.get_all_blueprints()
    
    if not blueprints:
        info_card(
            "No Blueprints Found", 
            "Injest tutorials or educational content, or run the backfill script to see checklists here."
        )
        return

    # 2. Sidebar Stats
    st.sidebar.markdown("### Checklist Stats")
    st.sidebar.metric("Total Blueprints", len(blueprints))
    
    # 3. Main Search
    search_query = st.text_input(
        "Search Checklists", 
        "", 
        placeholder="Search procedural blueprints...",
        label_visibility="collapsed"
    )
    
    if search_query:
        filtered = [b for b in blueprints if search_query.lower() in b["title"].lower() or search_query.lower() in b["channel_name"].lower()]
    else:
        filtered = blueprints

    # 3. Main Content
    if not filtered:
        st.warning("No checklists match your search.")
        return

    for bp in filtered:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {bp['title']}")
                st.caption(f"{bp['channel_name']} | {bp['created_at']}")
            with col2:
                # Add a "View Video" button or link
                video_url = f"https://www.youtube.com/watch?v={bp['video_id']}"
                st.link_button("Watch Video", video_url)

            spacer("0.5rem")
            
            steps = bp.get("steps_json", "[]")
            import json
            try:
                if isinstance(steps, str):
                    steps_list = json.loads(steps)
                else:
                    steps_list = steps
            except:
                steps_list = []

            if steps_list:
                for idx, step in enumerate(steps_list):
                    st.checkbox(step, key=f"bp_{bp['video_id']}_{idx}")
            else:
                st.info("No steps extracted for this blueprint.")

            st.divider()
