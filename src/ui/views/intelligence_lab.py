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
    tts_button
)
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.summarizer import SummarizerEngine
from src.intelligence.bridge_discovery import BridgeDiscoveryEngine

def render(db: SQLiteStore, run_repair_background=None):
    page_header(
        "Intelligence Lab",
        "Exploring non-linear connections, market trends, and thematic bridges within your vault."
    )


    # 1. Visualization Tabs
    tab1, tab2, tab2b, tab3, tab4 = st.tabs([
        "Knowledge Mind-Map", 
        "Knowledge Clusters",
        "Market Trends", 
        "Expert Network", 
        "Thematic Bridges"
    ])

    with tab1:
        render_mind_map(db)

    with tab2:
        render_knowledge_clusters(db)

    with tab2b:
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
        selected_topic = agraph(nodes=nodes, edges=edges, config=config)
        if selected_topic:
            st.session_state.selected_graph_topic = selected_topic
        
        if st.session_state.get("selected_graph_topic"):
            render_topic_side_car(db, st.session_state.selected_graph_topic)
    else:
        info_card("Sparse Graph", "Synthesize more content to reveal connection clusters.")

def render_topic_side_car(db: SQLiteStore, topic_name: str):
    """Render a side-panel with details for the selected topic."""
    st.markdown("---")
    st.markdown(f"### ◈ Insight Detail: {topic_name}")
    
    if st.button("Clear Selection"):
        st.session_state.selected_graph_topic = None
        st.rerun()

    details = db.get_topic_details(topic_name)
    if not details:
        st.info("No detailed insights stored for this specific topic node.")
        return

    st.write(f"Found in {len(details)} videos:")
    
    for d in details[:5]:
        with glass_card():
            st.markdown(f"**{d['title']}**")
            st.caption(f"{d['channel_name']} | {d['upload_date']}")
            
            # Show top takeaways
            if d.get("takeaways"):
                for t in d["takeaways"][:2]:
                    st.markdown(f"- {t}")
            
            if st.button("Deep Analysis", key=f"lab_vid_{d['video_id']}"):
                st.session_state.selected_transcript_vid = d['video_id']
                st.session_state.navigate = "Transcripts"
                st.rerun()

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
    selected_guest = agraph(nodes=nodes, edges=edges, config=config)
    if selected_guest:
        st.session_state.selected_graph_guest = selected_guest
    
    if st.session_state.get("selected_graph_guest"):
        render_guest_side_car(db, st.session_state.selected_graph_guest)

def render_guest_side_car(db: SQLiteStore, guest_name: str):
    """Render a side-panel with details for the selected guest."""
    st.markdown("---")
    st.markdown(f"### ✦ Expert Profile: {guest_name}")

    if st.button("Clear Profile"):
        st.session_state.selected_graph_guest = None
        st.rerun()
    
    # We can use our existing guest logic if available
    guest = db.find_guest_exact(guest_name)
    if not guest:
        st.info("No verified profile data for this entity.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Mentions", guest.mention_count)
    col2.metric("Type", guest.entity_type)

    if guest.aliases:
        st.write(f"**Aliases:** {', '.join(guest.aliases)}")

    # Fetch appearances if possible
    rows = db.conn.execute("""
        SELECT v.title, v.video_id, ga.context_snippet, c.name as channel
        FROM guest_appearances ga
        JOIN videos v ON ga.video_id = v.video_id
        JOIN channels c ON v.channel_id = c.channel_id
        WHERE ga.guest_id = ?
        ORDER BY v.upload_date DESC
    """, (guest.guest_id,)).fetchall()

    if rows:
        st.markdown("**Notable Appearances:**")
        for r in rows:
            with st.expander(f"{r['title'][:60]}..."):
                st.caption(f"Channel: {r['channel']}")
                if r['context_snippet']:
                    st.markdown(f"> {r['context_snippet']}")
                if st.button("Jump to Intelligence Trace", key=f"guest_vid_{r['video_id']}"):
                    st.session_state.selected_transcript_vid = r['video_id']
                    st.session_state.navigate = "Transcripts"
                    st.rerun()

def render_thematic_bridges(db: SQLiteStore, run_repair_background=None):
    section_header("Thematic Bridge Discovery", icon="⚿")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Probe Neural Bridges", type="primary", use_container_width=True):
            with st.spinner("Synthesizing bridges..."):
                if run_repair_background:
                    try:
                        run_repair_background()
                        action_confirmation_dialog("Intelligence synthesis engaged in the background...")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        failure_confirmation_dialog("Synthesis Failed", str(e))
                else:
                    engine = BridgeDiscoveryEngine(db)
                    engine.discover_bridges(sample_size=3)
                    action_confirmation_dialog(
                        "Neural Bridges Synthesized",
                        "The thematic discovery engine has completed its sweep of the knowledge vault.",
                        icon="⚿"
                    )
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


# =====================================================================
# KNOWLEDGE CLUSTERS (RE-HOMED FROM TOPIC EXPLORER)
# =====================================================================

def render_knowledge_clusters(db):
    """Render the consolidated cluster discovery interface."""
    topics = db.get_consolidated_topics()
    
    if not topics:
        info_card("No Clusters Detected", "The automated insight engine requires more summarized content to form clusters.")
        return

    # Cluster Search
    search_query = st.text_input("Filter Clusters", "", placeholder="Search research entities or themes...", label_visibility="collapsed", key="cluster_search")
    
    filtered_topics = [t for t in topics if search_query.lower() in t["name"].lower()] if search_query else topics

    # Detail View vs. Gallery View
    selected_topic = st.session_state.get("selected_cluster")
    
    if selected_topic:
        _render_cluster_detail(db, selected_topic)
    else:
        _render_cluster_gallery(filtered_topics)


def _render_cluster_gallery(topics):
    """Render the grid of topic cards."""
    cols = st.columns(3)
    for idx, topic in enumerate(topics):
        with cols[idx % 3]:
            with glass_card():
                st.markdown(f"**{topic['name']}**")
                st.caption(f"{topic['video_count']} Videos | {topic['channel_count']} Channels")
                if st.button("Probe Cluster", key=f"cl_btn_{topic['name']}", use_container_width=True):
                    st.session_state.selected_cluster = topic["name"]
                    st.rerun()


def _render_cluster_detail(db, topic_name):
    """Render the detailed view for a single topic."""
    if st.button("← Back to Discovery", key="back_to_clusters"):
        st.session_state.selected_cluster = None
        st.rerun()
        
    details = db.get_topic_details(topic_name)
    if not details:
        st.error(f"Cluster synchronization error for: {topic_name}")
        return

    channels = sorted(list(set(d["channel_name"] for d in details)))
    section_header(f"Cluster Intelligence: {topic_name}", icon="◈")
    
    m_grid = [
        {"value": len(details), "label": "Source Videos"},
        {"value": len(channels), "label": "Channels"},
    ]
    metric_grid(m_grid, cols=2)
    
    st.divider()
    
    # 1. Synthesized Perspective
    st.markdown("#### Consolidated Synthesis")
    all_takeaways = []
    for d in details: all_takeaways.extend(d["takeaways"])
    unique_takeaways = sorted(list(set(all_takeaways)))[:15]
    
    takeaway_text = "\n".join([f"- {t}" for t in unique_takeaways])
    st.markdown(takeaway_text)
    tts_button(f"Brief for {topic_name}: {takeaway_text}", label="Listen to Synthesis")

    st.divider()

    # 2. Expert Perspectives
    st.markdown("#### Channel-Specific Trace")
    for channel in channels:
        channel_clips = [d for d in details if d["channel_name"] == channel]
        with st.expander(f"{channel} ({len(channel_clips)} insights)"):
            for clip in channel_clips:
                st.markdown(f"**Video:** [{clip['title']}]({clip['url']})")
                st.info(clip["summary_text"])
                st.divider()
