"""Intelligence Studio - Advanced Analysis & Synthetic Research Hub."""

import streamlit as st
import logging
import json
import os
import time
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config
from src.ui.components import (
    page_header,
    section_header,
    glass_card,
    info_card,
    metric_grid,
    spacer,
    tts_button
)
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.storage.graph_store import GraphStore
from src.intelligence.research_agent import ResearchAgent
from src.intelligence.rag_engine import RAGEngine
from src.config import load_prompt
from src.intelligence.bridge_discovery import BridgeDiscoveryEngine

logger = logging.getLogger(__name__)

def render(db: SQLiteStore, vs: VectorStore, run_repair_background=None):
    """Render the unified Intelligence Studio."""
    
    page_header(
        "Intelligence Studio",
        "Deep synthesis, cross-channel comparison, and autonomous research."
    )

    tab_lab, tab_comparative, tab_agent = st.tabs([
        "Analytical Lab",
        "Comparative Studio",
        "Research Agent"
    ])

    with tab_lab:
        render_analytical_lab(db, run_repair_background)

    with tab_comparative:
        render_comparative_studio(db, vs)

    with tab_agent:
        render_research_agent(db)


def render_analytical_lab(db, run_repair_background):
    """Knowledge Map, Clusters, Experts, Bridges."""
    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
        "Knowledge Map",
        "Topic Clusters",
        "Expert Network",
        "Thematic Bridges"
    ])
    
    with sub_tab1:
        render_mind_map(db)
    
    with sub_tab2:
        render_knowledge_clusters(db)

    with sub_tab3:
        render_guest_network(db)
        
    with sub_tab4:
        render_thematic_bridges(db, run_repair_background)


# --- Analytical Lab Implementation ---

def render_mind_map(db: SQLiteStore):
    section_header("Thematic Connectivity Map", icon="◈")
    with glass_card():
        threshold = st.slider("Connection Strength", 1, 10, 1, key="mind_map_res")
    
    # Simple Topic Graph logic
    rows = db.conn.execute(f"""
        SELECT json_extract(t1.value, '$.name') as topic_a, json_extract(t2.value, '$.name') as topic_b, COUNT(*) as weight
        FROM video_summaries vs
        CROSS JOIN json_each(vs.topics_json) as t1
        CROSS JOIN json_each(vs.topics_json) as t2
        WHERE topic_a < topic_b
        GROUP BY 1, 2 HAVING weight >= {threshold}
        LIMIT 50
    """).fetchall()

    nodes, edges, seen = [], [], set()
    for r in rows:
        for t in [r['topic_a'], r['topic_b']]:
            if t not in seen:
                nodes.append(Node(id=t, label=t, size=25, color="#6366f1"))
                seen.add(t)
        edges.append(Edge(source=r['topic_a'], target=r['topic_b'], width=r['weight'], color="#475569"))

    if nodes:
        config = Config(width='100%', height=500, physics=True)
        agraph(nodes=nodes, edges=edges, config=config)
    else:
        info_card("No Nodes", "Need more data.")

def render_knowledge_clusters(db):
    topics = db.get_consolidated_topics()
    if not topics:
        info_card("No Clusters", "Index more content.")
        return
    
    cols = st.columns(3)
    for idx, t in enumerate(topics[:12]):
        with cols[idx % 3]:
            with glass_card():
                st.markdown(f"**{t['name']}**")
                st.caption(f"{t['video_count']} Videos")

def render_guest_network(db: SQLiteStore):
    section_header("Expert Network", icon="✦")
    
    # Maintenance Toolbar
    m1, m2 = st.columns([3, 1])
    with m2:
        if st.button("Resolve Entities", use_container_width=True, help="Deduplicate guests and purge noise."):
            from src.intelligence.entity_resolver import EntityResolver
            resolver = EntityResolver(db, GraphStore())
            if hasattr(resolver, "sanitize_expert_network"):
                stats = resolver.sanitize_expert_network()
                st.toast(f"Network Hardened: Purged {stats['purged']}, Merged {stats['merged']} (Synced to Graph)", icon="🛡")
            else:
                st.error("Intelligence Error: Sanitization engine out of sync. Please refresh.")
            st.rerun()

    network_data = db.get_guest_network()
    if not network_data:
        info_card("No experts", "Synthesize more content.")
        return
    
    nodes, edges, seen = [], [], set()
    for r in network_data[:30]:
        for g in [r['guest_a'], r['guest_b']]:
            if g not in seen:
                # Optimized node styling for legibility
                nodes.append(Node(
                    id=g, 
                    label=g, 
                    size=20, 
                    color="#22d3ee", 
                    font={'size': 24, 'color': 'white', 'face': 'Inter, sans-serif'}
                ))
                seen.add(g)
        edges.append(Edge(source=r['guest_a'], target=r['guest_b'], color="rgba(71, 85, 105, 0.4)"))
    
    # Use validated config from explorer.py with improved scaling for readability
    config = Config(
        width=1000,
        height=700,
        directed=False,
        physics=True,
        hierarchical=False,
        collapsible=True,
        nodeHighlightBehavior=True,
        highlightColor="#22d3ee",
        staticGraph=False,
        # Enhance label visibility
        scaling={'enabled': True, 'label': {'enabled': True, 'min': 14, 'max': 30}}
    )
    st.markdown("<div style='background: rgba(15, 23, 42, 0.2); border-radius: 16px; padding: 1rem;'>", unsafe_allow_html=True)
    agraph(nodes=nodes, edges=edges, config=config)
    st.markdown("</div>", unsafe_allow_html=True)

def render_thematic_bridges(db: SQLiteStore, run_repair_background=None):
    section_header("Thematic Bridge Discovery", icon="⚿")
    if st.button("Probe Neural Bridges", type="primary"):
        if run_repair_background: run_repair_background()
        st.toast("Discovery started")
    
    def safe_topic(t):
        if not t: return "Unknown"
        # Case 1: Already a dictionary
        if isinstance(t, dict):
            return t.get("name", str(t))
        # Case 2: Serialized JSON string
        if isinstance(t, str) and (t.strip().startswith('{') or t.strip().startswith('[')):
            try:
                import json
                data = json.loads(t)
                if isinstance(data, dict):
                    return data.get("name", t)
                elif isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    return item.get("name", str(item)) if isinstance(item, dict) else str(item)
            except: 
                pass
        # Case 3: Raw string
        return str(t)

    bridges = db.get_thematic_bridges()
    for b in bridges[:5]:
        with glass_card():
            topic_a = safe_topic(b.topic_a)
            topic_b = safe_topic(b.topic_b)
            st.markdown(f"**{topic_a}** ↔ **{topic_b}**")
            st.write(b.insight)


# --- Comparative Studio Implementation ---

def render_comparative_studio(db, vs):
    channels = db.get_all_channels()
    if not channels:
        st.warning("No channels found.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_channels = st.multiselect("Select Channels", channels, format_func=lambda c: c.name)
    with col2:
        topic = st.text_input("Research Topic", placeholder="e.g. AI Ethics", key="comp_topic")

    if st.button("Run Comparison", type="primary", disabled=not (selected_channels and topic)):
        with st.spinner("Synthesizing..."):
            try:
                rag = RAGEngine(db, vs)
                rag.system_prompt = load_prompt("comparative_analyst")
                channel_ids = [c.channel_id for c in selected_channels]
                where_filter = {"channel_id": {"$in": channel_ids}} if len(channel_ids) > 1 else {"channel_id": channel_ids[0]}
                response = rag.query(question=topic, filters=where_filter)
                
                st.markdown("## Comparative Synthesis")
                st.markdown(response.answer)
                
                with st.expander("Evidence & Citations"):
                    if response.citations:
                        for cit in response.citations:
                            st.markdown(f"- [{cit.source_id}] *\"{cit.video_title}\"*")
            except Exception as e:
                st.error(f"Analysis failed: {e}")


# --- Research Agent Implementation ---

def render_research_agent(db):
    col1, col2 = st.columns([2, 1])
    with col1:
        query = st.text_input("Launch Investigation", placeholder="e.g. Future of energy", key="agent_query")
        if st.button("Initialize Agent", type="primary", use_container_width=True, disabled=not query):
            agent = ResearchAgent(db)
            with st.spinner("Investigating..."):
                report = agent.generate_report(query)
                if report:
                    st.success("Report Generated")
                    st.rerun()
    with col2:
        st.info("The agent deep-scans your vault to synthesize formal briefs.")

    st.divider()
    section_header("Recent Briefs")
    reports = db.get_research_reports()
    for report in reports:
        with st.expander(f"{report.title} ({report.created_at})"):
            st.markdown(report.summary)
            if os.path.exists(report.file_path):
                with open(report.file_path, "r") as f:
                    content = f.read()
                st.download_button("Download", content, os.path.basename(report.file_path), key=f"dl_{report.report_id}")
