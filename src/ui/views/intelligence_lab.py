import streamlit as st
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config
from src.ui.components import page_header, section_header, info_card, metric_grid
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.summarizer import SummarizerEngine
from src.intelligence.bridge_discovery import BridgeDiscoveryEngine

def render_intelligence_lab(db: SQLiteStore):
    st.title("Intelligence Lab")
    st.markdown("---")

    # 0. Vault Readiness Metrics
    stats = db.get_pipeline_stats()
    total_vids = stats.get("total_videos", 0)
    summarized = stats.get("summarized", 0)
    
    with st.expander("Vault Intelligence Readiness", expanded=summarized < 100):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Summarized Videos", f"{summarized}/{total_vids}")
        with col2:
            st.progress(summarized / total_vids if total_vids > 0 else 0)
            st.caption(f"Intelligence features (Mind-Maps, Trends) require the 'Summarization' stage. {total_vids - summarized} videos pending.")
            
        if st.button("Prioritize Summarization Backfill"):
            to_process = db.get_videos_for_summarization(limit=20)
            if not to_process:
                st.success("All available videos are already summarized!")
            else:
                st.info(f"Processing {len(to_process)} videos. Please wait...")
                summarizer = SummarizerEngine(db)
                progress_bar = st.progress(0)
                for i, vid_id in enumerate(to_process):
                    summarizer.generate_summary(vid_id)
                    progress_bar.progress((i + 1) / len(to_process))
                st.success(f"Successfully summarized {len(to_process)} videos! Refreshing Lab...")
                st.rerun()

    # 1. Visualization Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Knowledge Mind-Map", 
        "Market Trends", 
        "Guest Network", 
        "Thematic Bridges"
    ])

    with tab1:
        st.subheader("Knowledge Mind-Map")
        st.info("Visualizing thematic connections across your vault.")
        
        # Threshold Slider
        threshold = st.slider(
            "Connection Strength (Minimum co-occurrences)", 
            min_value=1, 
            max_value=10, 
            value=1,
            help="1 = Show all links within single videos. >1 = Show only shared connections across videos."
        )
        
        render_mind_map(db, threshold)

    with tab2:
        render_market_trends(db)

    with tab3:
        render_guest_network(db)
        
    with tab4:
        render_thematic_bridges(db)

def render_mind_map(db: SQLiteStore, threshold: int = 1):
    """Render a semantic mind-map of the knowledge vault."""
    section_header("Semantic Mind-Map")
    st.caption("A non-linear visual explorer of your vault's core themes.")

    # 1. Fetch topics and their relationships
    # We use positional indices and explicit json_extract for robustness
    rows = db.conn.execute(f"""
        SELECT json_extract(t1.value, '$.name') as topic_a, json_extract(t2.value, '$.name') as topic_b, COUNT(*) as weight
        FROM video_summaries vs
        CROSS JOIN json_each(vs.topics_json) as t1
        CROSS JOIN json_each(vs.topics_json) as t2
        WHERE json_extract(t1.value, '$.name') < json_extract(t2.value, '$.name')
        GROUP BY 1, 2
        HAVING COUNT(*) >= {threshold}
        ORDER BY 3 DESC
        LIMIT 50
    """).fetchall()

    nodes = []
    edges = []
    seen_nodes = set()

    for r in rows:
        if r["topic_a"] not in seen_nodes:
            # Use Indigo primary-500
            nodes.append(Node(id=r["topic_a"], label=r["topic_a"], size=25, color="#6366f1"))
            seen_nodes.add(r["topic_a"])
        if r["topic_b"] not in seen_nodes:
            nodes.append(Node(id=r["topic_b"], label=r["topic_b"], size=25, color="#6366f1"))
            seen_nodes.add(r["topic_b"])
        
        # Use Slate-600 for edges
        edges.append(Edge(source=r["topic_a"], target=r["topic_b"], width=r["weight"], color="#475569"))

    config = Config(width=800, height=600, directed=False, physics=True, hierarchical=False)
    
    if nodes:
        agraph(nodes=nodes, edges=edges, config=config)
    else:
        info_card("No Connections Found", "Process more videos to see the knowledge graph emerge.")

def render_market_trends(db: SQLiteStore):
    """Render topic mention frequency over time."""
    section_header("Thematic Market Trends")
    
    trends_data = db.get_topic_trends()
    if not trends_data:
        st.info("Insufficient data for trend analysis.")
        return

    df = pd.DataFrame(trends_data)
    
    # Pivot for multi-line chart
    pivot_df = df.pivot(index='month', columns='topic', values='count').fillna(0)
    
    st.line_chart(pivot_df)
    
    st.write("---")
    st.subheader("Topic Momentum (Recent)")
    # Calculate % change or just most active topics
    st.dataframe(pivot_df.iloc[-3:].T, use_container_width=True)

def render_guest_network(db: SQLiteStore):
    """Render the social graph of experts."""
    section_header("Guest Co-Occurrence Network")
    
    network_data = db.get_guest_network()
    
    if not network_data:
        st.info("No guest co-occurrences found yet.")
        return

    nodes = []
    edges = []
    seen_guests = set()

    for r in network_data:
        if r["guest_a"] not in seen_guests:
            # Use Warning Amber
            nodes.append(Node(id=r["guest_a"], label=r["guest_a"], size=20, color="#f59e0b"))
            seen_guests.add(r["guest_a"])
        if r["guest_b"] not in seen_guests:
            nodes.append(Node(id=r["guest_b"], label=r["guest_b"], size=20, color="#f59e0b"))
            seen_guests.add(r["guest_b"])
            
        edges.append(Edge(source=r["guest_a"], target=r["guest_b"], label=r["topic"], color="#475569"))

    config = Config(width=800, height=600, directed=False, physics=True)
    agraph(nodes=nodes, edges=edges, config=config)

def render_thematic_bridges(db: SQLiteStore):
    """Render LLM-discovered bridges."""
    col1, col2 = st.columns([3, 1])
    with col1:
        section_header("Thematic Bridge Discovery")
    with col2:
        if st.button("Explore New Bridges"):
            with st.spinner("LLM discovering hidden connections..."):
                engine = BridgeDiscoveryEngine(db)
                engine.discover_bridges(sample_size=3)
                st.rerun()

    bridges = db.get_thematic_bridges()
    
    if not bridges:
        st.info("Click the button above to start discovering hidden thematic connections.")
        return

    for bridge in bridges:
        with st.container(border=True):
            cols = st.columns([1, 1, 3])
            cols[0].markdown(f"### {bridge.topic_a}")
            cols[1].markdown(f"### {bridge.topic_b}")
            with cols[2]:
                st.markdown(bridge.insight)
            st.caption(f"Discovered via {bridge.llm_model} • {bridge.created_at}")
