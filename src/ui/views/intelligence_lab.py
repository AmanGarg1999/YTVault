"""Intelligence Lab - Intelligence Core Redesign."""

import streamlit as st
import pandas as pd
import json
import time
from streamlit_agraph import agraph, Node, Edge, Config
from src.ui.components import (
    page_header, 
    section_header, 
    info_card, 
    metric_grid, 
    glass_card,
    spacer,
    action_confirmation_dialog,
    failure_confirmation_dialog,
)
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.summarizer import SummarizerEngine
from src.intelligence.bridge_discovery import BridgeDiscoveryEngine

def render(db: SQLiteStore):
    page_header(
        "Intelligence Lab",
        "Exploring non-linear connections, market trends, and thematic bridges within your vault."
    )

    # 0. Vault Readiness Metrics
    stats = db.get_pipeline_stats()
    total_vids = stats.get("total_videos", 0)
    summarized = stats.get("summarized", 0)
    
    with glass_card():
        cols = st.columns([1, 2])
        with cols[0]:
            st.metric("Intelligence Core Readiness", f"{summarized}/{total_vids}")
        with cols[1]:
            prog = summarized / total_vids if total_vids > 0 else 0
            st.progress(prog)
            st.caption(f"Knowledge Graph features require the 'Summarization' stage. {total_vids - summarized} videos pending.")
            
            if st.button("Prioritize Summarization Backfill", type="primary"):
                to_process = db.get_videos_for_summarization(limit=20)
                if not to_process:
                    st.success("Internal state synchronized.")
                else:
                    try:
                        st.toast("Backfill prioritization engaged...")
                        summarizer = SummarizerEngine(db)
                        prog_bar = st.progress(0, text="Synthesizing Knowledge...")
                        for i, vid_id in enumerate(to_process):
                            summarizer.generate_summary(vid_id)
                            prog_bar.progress((i + 1) / len(to_process))
                        
                        action_confirmation_dialog(
                            "Summarization Complete",
                            f"Successfully synthesized intelligence for {len(to_process)} target videos.",
                            icon="◈"
                        )
                    except Exception as e:
                        failure_confirmation_dialog(
                            "Summarization Batch Interrupted",
                            str(e),
                            retry_callback=None, # Too complex for a simple lambda here
                            queue_callback=lambda: [db.add_to_user_queue("VIDEO_ID", vid_id, str(e)) for vid_id in to_process]
                        )

    spacer("2rem")

    # 1. Visualization Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Knowledge Mind-Map", 
        "Market Trends", 
        "Expert Network", 
        "Thematic Bridges"
    ])

    with tab1:
        render_mind_map(db)

    with tab2:
        render_market_trends(db)

    with tab3:
        render_guest_network(db)
        
    with tab4:
        render_thematic_bridges(db)

def render_mind_map(db: SQLiteStore):
    section_header("Thematic Connectivity Map", icon="◈")
    
    with glass_card():
        threshold = st.slider(
            "Connection Strength Threshold", 
            1, 10, 1,
            help="Higher values show more robust connections shared across multiple videos."
        )

    # Fetch relationships
    rows = db.conn.execute(f"""
        SELECT json_extract(t1.value, '$.name') as topic_a, json_extract(t2.value, '$.name') as topic_b, COUNT(*) as weight
        FROM video_summaries vs
        CROSS JOIN json_each(vs.topics_json) as t1
        CROSS JOIN json_each(vs.topics_json) as t2
        WHERE json_extract(t1.value, '$.name') < json_extract(t2.value, '$.name')
        GROUP BY 1, 2
        HAVING COUNT(*) >= {threshold}
        ORDER BY 3 DESC
        LIMIT 60
    """).fetchall()

    nodes = []
    edges = []
    seen_nodes = set()

    for r in rows:
        if r["topic_a"] not in seen_nodes:
            # Nebula Indigo
            nodes.append(Node(id=r["topic_a"], label=r["topic_a"], size=25, color="#6366f1"))
            seen_nodes.add(r["topic_a"])
        if r["topic_b"] not in seen_nodes:
            nodes.append(Node(id=r["topic_b"], label=r["topic_b"], size=25, color="#6366f1"))
            seen_nodes.add(r["topic_b"])
        
        # Stellar Slate edges
        edges.append(Edge(source=r["topic_a"], target=r["topic_b"], width=r["weight"], color="#475569"))

    config = Config(width=800, height=500, directed=False, physics=True, hierarchical=False)
    
    if nodes:
        agraph(nodes=nodes, edges=edges, config=config)
    else:
        info_card("Sparse Graph", "Synthesize more content to reveal connection clusters.")

def render_market_trends(db: SQLiteStore):
    section_header("Topic Momentum Analysis", icon="📈")
    
    trends_data = db.get_topic_trends()
    if not trends_data:
        st.info("Insufficient data for frequency analysis.")
        return

    df = pd.DataFrame(trends_data)
    pivot_df = df.pivot(index='month', columns='topic', values='count').fillna(0)
    
    with glass_card():
        st.line_chart(pivot_df)
    
    spacer("1rem")
    st.markdown("#### High-Velocity Themes")
    st.dataframe(pivot_df.iloc[-3:].T, use_container_width=True)

def render_guest_network(db: SQLiteStore):
    section_header("Expert Network Graph", icon="✦")
    
    network_data = db.get_guest_network()
    if not network_data:
        st.info("No cross-expert co-occurrences detected.")
        return

    nodes = []
    edges = []
    seen_guests = set()

    for r in network_data:
        if r["guest_a"] not in seen_guests:
            # Cyber Cyan for experts
            nodes.append(Node(id=r["guest_a"], label=r["guest_a"], size=20, color="#22d3ee"))
            seen_guests.add(r["guest_a"])
        if r["guest_b"] not in seen_guests:
            nodes.append(Node(id=r["guest_b"], label=r["guest_b"], size=20, color="#22d3ee"))
            seen_guests.add(r["guest_b"])
            
        edges.append(Edge(source=r["guest_a"], target=r["guest_b"], label=r["topic"], color="#475569"))

    config = Config(width=800, height=500, directed=False, physics=True)
    agraph(nodes=nodes, edges=edges, config=config)

def render_thematic_bridges(db: SQLiteStore):
    section_header("Thematic Bridge Discovery", icon="⚿")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Probe Neural Bridges", type="primary", use_container_width=True):
            with st.spinner("Synthesizing bridges..."):
                engine = BridgeDiscoveryEngine(db)
                engine.discover_bridges(sample_size=3)
                st.toast("Neural bridges synthesized!")
                time.sleep(0.5)
                st.rerun()

    bridges = db.get_thematic_bridges()
    if not bridges:
        st.info("Probe the Neural Network to discover hidden thematic bridges.")
        return

    for bridge in bridges:
        with glass_card(border_accent="#6366f1"):
            cols = st.columns([1, 1, 3])
            cols[0].markdown(f"**{bridge.topic_a}**")
            cols[1].markdown(f"**{bridge.topic_b}**")
            with cols[2]:
                st.markdown(f"_{bridge.insight}_")
            st.caption(f"Synthesized via {bridge.llm_model} | {bridge.created_at}")
