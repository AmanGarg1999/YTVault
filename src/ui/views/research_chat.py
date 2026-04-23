import logging
import streamlit as st
import json
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.intelligence.research_chat_engine import ResearchChatEngine
from src.ui.components.ui_helpers import page_header, discovery_chips, citation_card, spacer

logger = logging.getLogger(__name__)

def render_research_chat(db: SQLiteStore, vs: VectorStore):
    """Render the high-end Research Chat Hub."""
    
    # Header with Design System
    page_header(
        "Research Chat Hub", 
        "Talk to your Knowledge Vault. Discover hidden insights through multi-turn intelligence synthesis."
    )

    # Initialize Engine (Reuse provided Vector Store)
    engine = ResearchChatEngine(db, vs)

    # Note: Sidebar is now managed by app.py for integration consistency

    # --- MAIN CONTENT: Chat Logic ---
    session_id = st.session_state.get("chat_session_id")

    # Load history if session exists
    if session_id:
        messages = db.get_chat_history(session_id)
    else:
        messages = []

    # Display Chat History 
    if not messages:
        st.markdown("### Welcome to the Research Chat Hub")
        st.info("Start by asking a question about your knowledge vault or choose a topic below to begin.")
        suggestions = [
            "What are the key insights from recent uploads?", 
            "Summarize the latest research.", 
            "What is the most frequently discussed topic?"
        ]
        selected_suggestion = discovery_chips(suggestions, key_prefix="welcome_chips")
        if selected_suggestion:
            if not session_id:
                session_id = engine.create_session(selected_suggestion)
                st.session_state.chat_session_id = session_id
            process_chat_input(engine, db, session_id, selected_suggestion)
            st.rerun()

    for msg in messages:
        role = "user" if msg.role == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(msg.content)
            
            # Render citations if assistant and present
            if msg.citations_json and msg.citations_json != "[]":
                render_citations_list(json.loads(msg.citations_json))

    # Suggested Questions (Discovery Chips)
    last_assistant_msg = next((m for m in reversed(messages) if m.role == "assistant"), None)
    if last_assistant_msg and last_assistant_msg.suggested_json:
        try:
            suggestions = json.loads(last_assistant_msg.suggested_json)
            if suggestions:
                st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
                selected_suggestion = discovery_chips(suggestions, key_prefix=f"chip_{last_assistant_msg.message_id}")
                if selected_suggestion:
                    process_chat_input(engine, db, session_id, selected_suggestion)
                    st.rerun()
        except Exception as e:
            logger.error(f"Error rendering discovery chips: {e}")

    # Chat Input
    if prompt := st.chat_input("Ask your Vault anything..."):
        # If no session, create one
        if not session_id:
            session_id = engine.create_session(prompt)
            st.session_state.chat_session_id = session_id
        
        process_chat_input(engine, db, session_id, prompt)
        st.rerun()

def process_chat_input(engine, db, session_id, prompt):
    """Execute RAG query and update state."""
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.status("✦ Synthesizing Vault intelligence...", expanded=True) as status:
            st.write("✦ Initializing Neural Search...")
            st.write("✦ Retrieving Context from Triple-Store...")
            response = engine.get_conversation_response(session_id, prompt)
            st.write("✦ Formulating Response...")
            status.update(label="✦ Synthesis Complete", state="complete", expanded=False)
            
        st.markdown(response["answer"])
        if response["citations"]:
            render_citations_list([engine._cit_to_dict(c) for c in response["citations"]])

def render_citations_list(citations):
    """Helper to render standardized citation cards."""
    with st.expander(f"📚 View {len(citations)} Supporting Citations", expanded=False):
        for i, cit in enumerate(citations):
            citation_card(cit, i + 1)

if __name__ == "__main__":
    # Test stub
    pass
