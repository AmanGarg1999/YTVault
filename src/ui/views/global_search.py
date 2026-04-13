import streamlit as st
import pandas as pd
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.ui.components.ui_helpers import glass_card, video_card, failure_confirmation_dialog, info_card
import logging

logger = logging.getLogger(__name__)

from src.ui.components import page_header, section_header, glass_card, video_card, failure_confirmation_dialog, info_card

def render_global_search(db: SQLiteStore, vs: VectorStore):
    """Unified Global Search interface with Hybrid Ranking (Keyword + Semantic) and Advanced Filtering."""
    page_header("Intelligence Search", "Unified deep-search across transcripts, summaries, and claims with hybrid ranking.")

    # -----------------------------------------------------------------------
    # SYSTEM STATUS & CIRCUIT BREAKER
    # -----------------------------------------------------------------------
    vector_online = vs and vs.is_ready()
    
    with st.sidebar:
        with st.expander("🛡️ System Health", expanded=False):
            if vector_online:
                st.success("🟢 Vector Core: Operational")
            else:
                st.error("🔴 Vector Core: Offline")
                st.info("Falling back to high-fidelity keyword search (Degraded Mode).")
        st.markdown("### Advanced Filters")
        
        # Channel Filter
        channels = db.get_all_channels()
        selected_channels = st.multiselect(
            "Research Sources",
            options=channels,
            format_func=lambda c: c.name,
            help="Restrict search results to specific channels."
        )
        
        # Date Filter
        use_date_filter = st.checkbox("Filter by Date")
        if use_date_filter:
            date_range = st.date_input("Range", value=[])
        else:
            date_range = None
            
        st.markdown("---")
        top_k = st.slider("Result Density", 5, 50, 20)

    # Main Search Input
    query = st.text_input(
        "Search your intelligence vault...", 
        placeholder="e.g. 'impact of generative AI on productivity' or 'expert debate on nutrition'", 
        label_visibility="collapsed",
        key="search_query_main"
    )

    if query:
        # Check for empty query after strip
        if not query.strip():
            st.toast("Search Error: Please enter a valid search term.", icon="⚠️")
            return
            
        # Prepare filters
        where_filter = {}
        if selected_channels:
            ids = [c.channel_id for c in selected_channels]
            where_filter["channel_id"] = ids[0] if len(ids) == 1 else {"$in": ids}
        
        if use_date_filter and date_range and len(date_range) == 2:
            where_filter["upload_date"] = {
                "$gte": date_range[0].isoformat(),
                "$lte": date_range[1].isoformat()
            }

        st.toast(f"Searching vault for: {query[:30]}...", icon="🔍")
        with st.spinner("Decoding semantic patterns and ranking results..."):
            try:
                # 1. Keyword Search (FTS5) - Always run as baseline
                kw_results = db.fulltext_search(query, limit=top_k * 2)
                
                # 2. Semantic Search (resilient check)
                vector_results = []
                summary_results = []
                claim_results = []
                
                if vector_online:
                    try:
                        vector_results = vs.search(query, top_k=top_k * 2, where=where_filter)
                        
                        if hasattr(vs, "search_summaries"):
                            summary_results = vs.search_summaries(query, top_k=top_k, where=where_filter)
                        
                        if hasattr(vs, "search_claims"):
                            claim_results = vs.search_claims(query, top_k=top_k, where=where_filter)
                    except Exception as e:
                        logger.warning(f"Semantic search component failed: {e}")
                        st.caption("⚠️ Semantic results temporarily unavailable. Using keyword matching.")

                # 3. Hybrid Ranking (Reciprocal Rank Fusion - RRF)
                scores = {}
                k = 60 

                def update_rrf(results, weight=1.0):
                    for i, res in enumerate(results):
                        # Handle different result types
                        v_id = None
                        if isinstance(res, dict):
                            # Try multiple possible keys for video_id
                            v_id = res.get("video_id") or res.get("metadata", {}).get("video_id")
                        
                        if not v_id: continue
                        
                        if v_id not in scores:
                            scores[v_id] = {"rrf": 0.0, "matches": [], "type": "video"}
                        
                        scores[v_id]["rrf"] += weight * (1.0 / (k + i))
                        
                        text = ""
                        m_type = "transcript"
                        if isinstance(res, dict):
                            text = res.get("snippet") or res.get("text") or ""
                            # Infer type from structure or presence of keys
                            if "snippet" in res: m_type = "transcript"
                            elif "claim_id" in str(res) or "claim" in str(res).lower(): m_type = "claim"
                            else: m_type = "summary"
                        
                        if text and text not in [m["text"] for m in scores[v_id]["matches"]]:
                            scores[v_id]["matches"].append({"text": text, "type": m_type})

                # Apply weights
                kw_weight = 1.0 if vector_online else 2.0  # Boost keyword relevance in degraded mode
                update_rrf(kw_results, weight=kw_weight) 
                
                if vector_online:
                    update_rrf(vector_results, weight=1.0) 
                    update_rrf(summary_results, weight=0.8)
                    update_rrf(claim_results, weight=1.2)

                # Sort and Render
                ranked_results = sorted(scores.items(), key=lambda x: x[1]["rrf"], reverse=True)[:top_k]
                
                # Keyword Presence Guard: Validate that query terms actually appear in the findings
                # This prevents "semantic drift" or loose FTS5 matches from appearing as high-relevance
                def has_keyword_correlation(matches, query):
                    q_tokens = [t.lower() for t in query.split() if len(t) > 2]
                    if not q_tokens: return True # Fallback for short queries
                    for m in matches:
                        m_text = m["text"].lower()
                        if any(t in m_text for t in q_tokens):
                            return True
                    return False

                # Filter and Rank
                valid_results = []
                for v_id, data in ranked_results:
                    # Threshold check + Presence Guard
                    if data["rrf"] > 0.02 and has_keyword_correlation(data["matches"], query):
                        valid_results.append((v_id, data))
                
                ranked_results = valid_results

                if not ranked_results:
                    st.markdown("---")
                    info_card(
                        "No Intelligence Found", 
                        f"The search core could not find matching patterns for '{query}'. "
                        "Try using broader keywords, removing filters, or ensuring the vector core is synced."
                    )
                    return

                st.write(f"Showing {len(ranked_results)} high-relevance matches:")
                
                for v_id, data in ranked_results:
                    video = db.get_video(v_id)
                    if not video: continue
                    
                    with glass_card():
                        st.markdown(f"### {video.title}")
                        st.caption(f"{video.upload_date} | Synthesis Strength: {data['rrf']:.4f}")
                        
                        if not vector_online:
                            st.caption("⚡ Result returned via legacy keyword index")

                        if data["matches"]:
                            for m in data["matches"][:3]:
                                icon = "📝" if m["type"] == "summary" else ("🔬" if m["type"] == "claim" else "💬")
                                label = m["type"].upper()
                                # Clean snippet
                                raw_text = m["text"]
                                # Safely convert FTS5 bold tags to markdown
                                raw_text = raw_text.replace("<b>", "**").replace("</b>", "**")
                                clean_text = raw_text[:250] + "..." if len(raw_text) > 250 else raw_text
                                st.markdown(f"**{icon} {label}**: _{clean_text}_")
                        
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if st.button("Drill Down", key=f"srch_drill_{v_id}"):
                                st.session_state.selected_transcript_vid = v_id
                                st.session_state.navigate = "Transcripts"
                                st.rerun()

            except Exception as e:
                failure_confirmation_dialog(
                    "Search Core Anomaly",
                    f"The unified search engine encountered a non-fatal error: {str(e)}",
                    retry_callback=None
                )
                logger.error(f"Global search error: {e}", exc_info=True)

    else:
        # Default State: System Info
        with glass_card():
            st.markdown("### 🔍 Searching your Research OS")
            st.markdown("""
                Our hybrid engine searches through:
                - **Transcripts**: Full conversations and lectures.
                - **Summaries**: High-level distilled research findings.
                - **Claims**: Evidence-based extractions from across the vault.
                
                *Use the sidebar to filter by specific channels or time periods.*
            """)

