"""Knowledge Explorer page for knowledgeVault-YT."""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(db):
    """Render the Knowledge Explorer page."""
    st.markdown("""
<div class="main-header">
<h1>Knowledge Explorer</h1>
<p>Visualize connections and discover cross-entity relationships</p>
</div>
""", unsafe_allow_html=True)

    try:
        from streamlit_agraph import agraph, Node, Edge, Config
        from src.storage.graph_store import GraphStore
        from src.intelligence.explorer import KnowledgeExplorer

        graph_db = GraphStore()
        explorer_obj = KnowledgeExplorer(db, graph_db)

        tab1, tab2 = st.tabs(["Connection Graph", "Topic Spotlight"])

        with tab1:
            _render_connection_graph(explorer_obj, agraph, Node, Edge, Config)

        with tab2:
            _render_topic_spotlight(graph_db, explorer_obj)

    except ImportError:
        st.error("Missing library: streamlit-agraph. Please ensure it is installed.")
    except Exception as e:
        st.error(f"Failed to load Knowledge Explorer: {e}")
        logger.error(f"Knowledge Explorer error: {e}", exc_info=True)


def _render_connection_graph(explorer_obj, agraph, Node, Edge, Config):
    """Render the Connection Graph tab."""
    col1, col2 = st.columns([1, 4])

    with col1:
        st.markdown("### Exploration Mode")
        explore_mode = st.radio("View Type", ["Target Search", "Entire Vault"], horizontal=True)

        if explore_mode == "Target Search":
            search_q = st.text_input("Entity Name", placeholder="Elon Musk, Mars, etc.")
            search_type = st.selectbox("Type", ["Guest", "Topic", "Video"])

            if st.button("Visualize Connections", use_container_width=True):
                if search_q:
                    with st.spinner("Traversing graph..."):
                        data = explorer_obj.get_entity_connections(search_q, search_type)
                        st.session_state.explorer_graph = data
                        st.session_state.explorer_mode = "Target"
                else:
                    st.warning("Please enter an entity name.")
        else:
            if st.button("Load Global Map", type="primary", use_container_width=True):
                with st.spinner("Mapping entire vault..."):
                    data = explorer_obj.get_global_graph()
                    st.session_state.explorer_graph = data
                    st.session_state.explorer_mode = "Global"

        # Discovery Sidebar (Stats)
        st.markdown("---")
        st.markdown("### Vault Discovery")
        try:
            stats = explorer_obj.get_vault_stats()
            with st.expander("Trending Topics", expanded=True):
                for t in stats["top_topics"]:
                    if st.button(f"#{t['name']} ({t['weight']})", key=f"top_t_{t['name']}", use_container_width=True):
                        with st.spinner(f"Mapping {t['name']}..."):
                            data = explorer_obj.get_entity_connections(t['name'], "Topic")
                            st.session_state.explorer_graph = data
                            st.session_state.explorer_mode = "Target"
                            st.rerun()

            with st.expander("Top Experts", expanded=False):
                for g in stats["top_guests"]:
                    if st.button(f"{g['name']} ({g['weight']})", key=f"top_g_{g['name']}", use_container_width=True):
                        with st.spinner(f"Mapping {g['name']}..."):
                            data = explorer_obj.get_entity_connections(g['name'], "Guest")
                            st.session_state.explorer_graph = data
                            st.session_state.explorer_mode = "Target"
                            st.rerun()
        except Exception:
            st.caption("Stats loading...")

    with col2:
        if "explorer_graph" in st.session_state:
            graph_data = st.session_state.explorer_graph
            if graph_data["nodes"]:
                type_colors = {
                    "Video": "#FF4B4B",
                    "Guest": "#5D3FD3",
                    "Topic": "#00D4FF",
                    "Channel": "#FFD700"
                }

                nodes = [
                    Node(
                        id=n["id"],
                        label=n["label"],
                        size=25 if n["type"] == "Video" else 20,
                        color=type_colors.get(n["type"], "#808080"),
                        title=f"Type: {n['type']}\n{n['label']}"
                    )
                    for n in graph_data["nodes"]
                ]

                edges = [
                    Edge(
                        source=e["source"],
                        target=e["target"],
                        label=e["type"],
                        color="#4B4B4B"
                    )
                    for e in graph_data["edges"]
                ]

                config = Config(
                    width=1000,
                    height=700,
                    directed=True,
                    physics=True,
                    hierarchical=False,
                    collapsible=True,
                    nodeHighlightBehavior=True,
                    highlightColor="#F7A7A7",
                    staticGraph=False
                )

                st.markdown(f"**Viewing:** {st.session_state.get('explorer_mode', 'Vault')} Network")
                st.caption("Color Key: Video (Red) | Guest (Purple) | Topic (Blue) | Channel (Yellow)")
                
                # agraph returns the id of the clicked node
                # Note: streamlit-agraph returns None if no node is clicked
                selected_node_id = agraph(nodes=nodes, edges=edges, config=config)
                
                if selected_node_id:
                    # Find the node in our graph data
                    node = next((n for n in graph_data["nodes"] if n["id"] == selected_node_id), None)
                    if node:
                        st.markdown("---")
                        st.markdown(f"### Node Details: {node['label']}")
                        
                        d_col1, d_col2 = st.columns(2)
                        with d_col1:
                            st.write(f"**Type:** {node['type']}")
                            if node["type"] == "Video":
                                st.write(f"**Video ID:** `{node['internal_id']}`")
                                vid_url = f"https://www.youtube.com/watch?v={node['internal_id']}"
                                st.link_button("Watch on YouTube", vid_url)
                                
                                # Show Thematic Bridges
                                st.markdown("---")
                                st.markdown("Thematic Bridges")
                                bridges = explorer_obj.get_thematic_bridges(node["internal_id"])
                                if bridges:
                                    for b in bridges:
                                        with st.expander(f"{b['title'][:40]}...", expanded=False):
                                            st.write(f"Connects via: **{', '.join(b['bridge_types'])}**")
                                            st.write(f"Strength: {b['shared_count']} shared entities")
                                            if st.button(f"Explore {b['video_id'][:8]}", key=f"bridge_{b['video_id']}"):
                                                st.session_state.explorer_mode = "Video"
                                                st.session_state.explorer_entity = b["video_id"]
                                                st.rerun()
                                else:
                                    st.caption("No thematic bridges found yet.")
                        
                        with d_col2:
                            if node["type"] == "Guest":
                                st.write(f"**Canonical Name:** {node['internal_id']}")
                                if st.button(f"View Guest Intel: {node['label']}"):
                                    st.session_state.navigate = "Guest Intelligence"
                                    st.session_state.selected_guest = node["internal_id"]
                                    st.rerun()
                            
                            if node["type"] == "Topic":
                                if st.button(f"Spotlight Topic: {node['label']}"):
                                    # Switch to tab2 and select topic
                                    # Note: Streamlit tabs don't easily switch via code without index state
                                    st.info(f"Go to **Topic Spotlight** tab to explore '{node['label']}' in depth.")
            else:
                st.info("No connections found for this entity.")
        else:
            st.info("Select an exploration mode to visualize your knowledge network.")


def _render_topic_spotlight(graph_db, explorer_obj):
    """Render the Topic Spotlight tab."""
    import pandas as pd

    st.markdown("### Topic Deep-Dive")
    with graph_db.driver.session() as session:
        topics_res = session.run("MATCH (t:Topic) RETURN t.name AS name ORDER BY name")
        all_topics = [r["name"] for r in topics_res]

    selected_topic = st.selectbox("Select Topic", all_topics)

    if selected_topic:
        with st.spinner(f"Analyzing '{selected_topic}'..."):
            landscape = explorer_obj.get_topic_landscape(selected_topic)

            l_col1, l_col2 = st.columns(2)
            with l_col1:
                st.markdown(f"#### Related Videos ({len(landscape['videos'])})")
                for v in landscape["videos"]:
                    st.markdown(f"- **{v['title']}** (`{v['video_id']}`)")

            with l_col2:
                st.markdown(f"#### Expert Guests ({len(landscape['guests'])})")
                for g in landscape["guests"]:
                    st.markdown(f"- **{g['canonical_name']}**")

            st.markdown("#### Related Topics")
            if landscape["related"]:
                rel_df = pd.DataFrame(landscape["related"]).sort_values(
                    "co_occurrence", ascending=False
                )
                st.dataframe(rel_df, use_container_width=True, hide_index=True)
            else:
                st.info("No related topics found.")
