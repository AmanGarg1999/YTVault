"""Intelligence Lab - Unified research, exploration, and analysis interface."""

import logging
import streamlit as st
import pandas as pd

logger = logging.getLogger(__name__)


def render(db, vs):
    """Render the unified Intelligence Lab with research, exploration, and guest intelligence."""
    
    st.markdown("""
    <div class="main-header">
        <h1>🔬 Intelligence Lab</h1>
        <p>Research, explore relationships, browse guests, and analyze your knowledge vault</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        # =====================================================================
        # TABS: Research, Explorer, Guest Browser, Entity Browser
        # =====================================================================
        tab_research, tab_explorer, tab_guests, tab_entities = st.tabs([
            "🔍 Research Console",
            "🧠 Graph Explorer",
            "👥 Guest Browser",
            "📊 Entity Analysis"
        ])

        # =====================================================================
        # TAB 1: RESEARCH CONSOLE - RAG queries
        # =====================================================================
        with tab_research:
            render_research_tab(db, vs)

        # =====================================================================
        # TAB 2: GRAPH EXPLORER - Visualizations
        # =====================================================================
        with tab_explorer:
            render_explorer_tab(db)

        # =====================================================================
        # TAB 3: GUEST BROWSER - Guest-centric analytics
        # =====================================================================
        with tab_guests:
            render_guests_tab(db)

        # =====================================================================
        # TAB 4: ENTITY BROWSER - Topics, claims, quotes
        # =====================================================================
        with tab_entities:
            render_entities_tab(db)

    except Exception as e:
        st.error(f"Intelligence Lab error: {e}")
        logger.error(f"Intelligence Lab error: {e}", exc_info=True)


def render_research_tab(db, vs):
    """Tab 1: Research Console - RAG-based question answering."""
    
    st.markdown("### 🔍 Research Console")
    st.write("Ask natural language questions across your entire knowledge vault")
    
    # Query help
    with st.expander("🔧 Advanced Query Syntax & Filters"):
        st.markdown("""
        **Advanced Filters** (optional):
        
        | Filter | Example | Description |
        |--------|---------|-------------|
        | `channel:` | `channel:lexfridman` | Search within a channel |
        | `topic:` | `topic:"machine learning"` | Topic-aware search |
        | `guest:` | `guest:"Elon Musk"` | Guest-focused queries |
        | `after:` | `after:2024-01` | Filter by date (after) |
        | `before:` | `before:2025-06` | Filter by date (before) |
        | `lang:` | `lang:en` | Language filter |
        
        **Example Combined Query**:
        ```
        channel:lexfridman topic:AI after:2024 lang:en
        What is artificial general intelligence?
        ```
        """)

    if "conversation" not in st.session_state:
        st.session_state.conversation = []

    # Display previous conversation
    for entry in st.session_state.conversation:
        with st.chat_message("user"):
            st.markdown(entry["question"])
        with st.chat_message("assistant"):
            st.markdown(entry["answer"])
            if entry.get("citations"):
                with st.expander(f"📎 {len(entry['citations'])} sources"):
                    for c in entry["citations"]:
                        st.markdown(
                            f"- [{c['source_id']}] **{c['video_title']}** "
                            f"([{c['timestamp']}]({c['link']}))"
                        )
            st.caption(entry.get("meta", ""))

    # New question input
    question = st.chat_input(
        "Ask a research question... (supports channel:, topic:, guest:, after:, before:, lang:)",
    )

    if question:
        st.session_state.conversation.append({"question": question, "answer": "...", "citations": []})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching vault and synthesizing answer..."):
                try:
                    from src.intelligence.query_parser import parse_query
                    from src.intelligence.rag_engine import RAGEngine
                    
                    # Parse query
                    query_plan = parse_query(question)
                    
                    # Run RAG
                    rag_engine = RAGEngine(db, vs)
                    result = rag_engine.query(query_plan)
                    
                    # Display answer
                    st.markdown(result.answer)
                    
                    # Update conversation
                    if result.citations:
                        with st.expander(f"📎 {len(result.citations)} sources"):
                            for c in result.citations:
                                st.markdown(f"- {c}")
                    
                    # Store in session
                    st.session_state.conversation[-1].update({
                        "answer": result.answer,
                        "citations": result.citations or [],
                    })
                    
                except Exception as e:
                    st.error(f"Query failed: {e}")
                    logger.error(f"RAG query error: {e}", exc_info=True)


def render_explorer_tab(db):
    """Tab 2: Graph Explorer - Visualize relationships."""
    
    st.markdown("### 🧠 Knowledge Graph Explorer")
    
    try:
        from streamlit_agraph import agraph, Node, Edge, Config
        from src.storage.graph_store import GraphStore
        from src.intelligence.explorer import KnowledgeExplorer

        graph_db = GraphStore()
        explorer_obj = KnowledgeExplorer(db, graph_db)

        col1, col2 = st.columns([1, 4])

        with col1:
            st.markdown("### 🔭 Exploration Mode")
            explore_mode = st.radio("View Type", ["🎯 Target Search", "🌐 Entire Vault"], horizontal=False)

            if explore_mode == "🎯 Target Search":
                search_q = st.text_input("Entity Name", placeholder="Elon Musk, Mars, AGI...")
                search_type = st.selectbox("Type", ["Guest", "Topic", "Video"])

                if st.button("🚀 Visualize Connections"):
                    if search_q:
                        with st.spinner("Traversing graph..."):
                            data = explorer_obj.get_entity_connections(search_q, search_type)
                            st.session_state.explorer_graph = data
                            st.session_state.explorer_mode = "Target"
                    else:
                        st.warning("Please enter an entity name.")
            else:
                if st.button("🔭 Load Global Map", type="primary"):
                    with st.spinner("Mapping entire vault..."):
                        data = explorer_obj.get_global_graph()
                        st.session_state.explorer_graph = data
                        st.session_state.explorer_mode = "Global"

            # Discovery Sidebar
            st.markdown("---")
            st.markdown("### 📊 Trending Topics")
            try:
                stats = explorer_obj.get_vault_stats()
                for t in stats.get("top_topics", []):
                    if st.button(f"#{t['name']} ({t['weight']})", key=f"topic_{t['name']}", use_container_width=True):
                        with st.spinner(f"Mapping {t['name']}..."):
                            data = explorer_obj.get_entity_connections(t['name'], "Topic")
                            st.session_state.explorer_graph = data
                            st.session_state.explorer_mode = "Target"
                            st.rerun()
            except Exception as e:
                st.warning(f"Could not load trending topics: {e}")

        with col2:
            # Display graph if available
            if "explorer_graph" in st.session_state:
                try:
                    st.markdown("### Graph Visualization")
                    # TODO: Render graph with agraph component
                    st.info("Graph visualization (requires streamlit-agraph integration)")
                except Exception as e:
                    st.warning(f"Could not render graph: {e}")
            else:
                st.info("👈 Select an entity or view to visualize")

    except ImportError:
        st.error("Missing library: streamlit-agraph. Please install: pip install streamlit-agraph")
    except Exception as e:
        st.error(f"Knowledge Explorer error: {e}")
        logger.error(f"Knowledge Explorer error: {e}", exc_info=True)


def render_guests_tab(db):
    """Tab 3: Guest Browser - Guest-centric analytics."""
    
    st.markdown("### 👥 Guest Intelligence Browser")
    
    try:
        guests = db.get_all_guests()

        if not guests:
            st.info("No guests discovered yet. Run the pipeline to extract guests from transcripts.")
        else:
            guest_names = [g.canonical_name for g in guests]
            
            # Handle pre-selected guest from other pages
            default_index = 0
            if "selected_guest" in st.session_state:
                pre_selected = st.session_state.pop("selected_guest")
                if pre_selected in guest_names:
                    default_index = guest_names.index(pre_selected)

            selected_name = st.selectbox(
                "Select Guest",
                guest_names,
                index=default_index,
                help="Browse all discovered guests sorted by mention count",
            )

            if selected_name:
                guest = next(g for g in guests if g.canonical_name == selected_name)

                # Guest info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Mentions", guest.mention_count)
                with col2:
                    st.metric("Aliases", len(guest.aliases))
                with col3:
                    st.metric("Type", guest.entity_type)

                if guest.aliases:
                    st.markdown(f"**Also known as:** {', '.join(guest.aliases)}")

                if guest.bio:
                    st.markdown(f"**Bio:** {guest.bio}")

                # Guest appearances
                st.markdown("### 📺 Appearances")
                
                appearances = db.conn.execute(
                    """SELECT ga.context_snippet, ga.start_timestamp, ga.end_timestamp,
                              v.title, v.video_id, v.upload_date, v.channel_id
                       FROM guest_appearances ga
                       JOIN videos v ON ga.video_id = v.video_id
                       WHERE ga.guest_id = ?
                       ORDER BY v.upload_date DESC
                       LIMIT 50""",
                    (guest.guest_id,)
                ).fetchall()

                if appearances:
                    for app in appearances:
                        with st.container(border=True):
                            st.markdown(f"**{app['title']}**")
                            st.caption(f"{app['upload_date']} on {app['channel_id']}")
                            if app['context_snippet']:
                                st.caption(f"💬 \"{app['context_snippet'][:100]}...\"")
                            
                            # Video link
                            video_url = f"https://www.youtube.com/watch?v={app['video_id']}&t={int(app['start_timestamp'])}"
                            st.link_button("Watch", video_url, use_container_width=True)
                else:
                    st.info("No appearances recorded for this guest.")

                # Co-occurring guests
                st.markdown("### 🤝 Co-occurring Guests")
                co_guests = db.conn.execute(
                    """SELECT DISTINCT ga2.guest_id 
                       FROM guest_appearances ga1
                       JOIN guest_appearances ga2 ON ga1.video_id = ga2.video_id
                       WHERE ga1.guest_id = ? AND ga2.guest_id != ?
                       LIMIT 10""",
                    (guest.guest_id, guest.guest_id)
                ).fetchall()

                if co_guests:
                    for cg in co_guests:
                        co_guest = guest  # TODO: Fetch co-guest details
                        if st.button(f"👤 {co_guest.canonical_name}", key=f"cogues_{cg[0]}"):
                            st.session_state.selected_guest = co_guest.canonical_name
                            st.rerun()
                else:
                    st.info("No co-occurring guests found.")

    except Exception as e:
        st.error(f"Guest browser error: {e}")
        logger.error(f"Guest browser error: {e}", exc_info=True)


def render_entities_tab(db):
    """Tab 4: Entity Analysis - Topics, claims, quotes."""
    
    st.markdown("### 📊 Entity Analysis")
    
    entity_type = st.radio(
        "Entity Type",
        ["📌 Topics", "💬 Quotes", "✅ Claims"],
        horizontal=True
    )

    if entity_type == "📌 Topics":
        st.markdown("#### Top Topics Discussed")
        try:
            # Get all topic mentions from chunks
            rows = db.conn.execute(
                """SELECT topics_json FROM transcript_chunks 
                   WHERE topics_json != '[]'
                   LIMIT 100"""
            ).fetchall()
            
            topics_count = {}
            for row in rows:
                import json
                try:
                    topics = json.loads(row[0])
                    for topic in topics:
                        if isinstance(topic, dict):
                            name = topic.get('name', str(topic))
                        else:
                            name = str(topic)
                        topics_count[name] = topics_count.get(name, 0) + 1
                except:
                    pass
            
            if topics_count:
                df = pd.DataFrame([
                    {"Topic": k, "Mentions": v}
                    for k, v in sorted(topics_count.items(), key=lambda x: -x[1])[:20]
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No topics extracted yet.")
        except Exception as e:
            st.warning(f"Could not load topics: {e}")

    elif entity_type == "💬 Quotes":
        st.markdown("#### Notable Quotations")
        try:
            quotes = db.conn.execute(
                """SELECT speaker, quote_text, video_id, timestamp 
                   FROM quotes 
                   ORDER BY timestamp DESC 
                   LIMIT 50"""
            ).fetchall()
            
            if quotes:
                for q in quotes:
                    with st.container(border=True):
                        st.markdown(f'*"{q[1]}"*')
                        st.caption(f"— {q[0] or 'Unknown'}")
                        st.caption(f"[{q[2][:8]}]({q[3]:.0f}s)")
            else:
                st.info("No quotes extracted yet.")
        except Exception as e:
            st.warning(f"Could not load quotes: {e}")

    elif entity_type == "✅ Claims":
        st.markdown("#### Extracted Claims")
        try:
            claims = db.conn.execute(
                """SELECT speaker, claim_text, topic, confidence 
                   FROM claims 
                   ORDER BY confidence DESC 
                   LIMIT 50"""
            ).fetchall()
            
            if claims:
                for c in claims:
                    with st.container(border=True):
                        st.markdown(f"**{c[0] or 'Unknown'}**: {c[1]}")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption(f"📌 Topic: {c[2]}")
                        with col2:
                            st.caption(f"🎯 Confidence: {c[3]:.0%}")
            else:
                st.info("No claims extracted yet.")
        except Exception as e:
            st.warning(f"Could not load claims: {e}")
