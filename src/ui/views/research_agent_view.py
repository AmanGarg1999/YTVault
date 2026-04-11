import streamlit as st
import os
import json
from src.ui.components import page_header, section_header, info_card, success_card
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.research_agent import ResearchAgent

def render(db: SQLiteStore):
    """Render the Autonomous Research Agent interface."""
    page_header("Research Agent", "Autonomous Synthesis & Briefing")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### New Mission")
        query = st.text_input("Enter a research topic (e.g. 'The future of AI ethics in medicine')", 
                             placeholder="What would you like to investigate?")
        
        if st.button("Launch Investigation"):
            if query:
                agent = ResearchAgent(db)
                with st.spinner(f"Agent investigating '{query}'..."):
                    try:
                        report = agent.generate_report(query)
                        if report:
                            st.toast("Investigation Complete!")
                            success_card("Investigation Complete", f"Created: {report.title}")
                            st.balloons()
                            st.rerun()
                    except Exception as e:
                        from src.ui.components import failure_confirmation_dialog
                        failure_confirmation_dialog("Agent Malfunction", str(e))
            else:
                from src.ui.components import failure_confirmation_dialog
                failure_confirmation_dialog(
                    "Mission Objective Required", 
                    "The autonomous agent requires a specific research query or investigative theme to initialize its synthesis cycle."
                )

    with col2:
        st.info("The agent deep-scans your vault, finds relevant topics, and synthesizes a formal white paper with citations.")

    st.write("---")
    section_header("Recent Briefs")

    reports = db.get_research_reports()
    
    if not reports:
        st.info("No research reports generated yet.")
        return

    for report in reports:
        with st.expander(f"{report.title} ({report.created_at})"):
            st.markdown(f"**Query**: {report.query}")
            st.markdown(f"**Brief**: {report.summary}")
            
            if os.path.exists(report.file_path):
                with open(report.file_path, "r") as f:
                    content = f.read()
                
                st.markdown("---")
                st.markdown(content)
                
                st.download_button(
                    label="Download Markdown",
                    data=content,
                    file_name=os.path.basename(report.file_path),
                    mime="text/markdown"
                )
            
            try:
                sources = json.loads(report.sources_json)
                st.write("**Sources Used:**")
                for s in sources:
                    st.caption(f"- {s['title']}")
            except:
                pass
