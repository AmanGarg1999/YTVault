import streamlit as st
import pandas as pd
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.ui.components.ui_helpers import glass_card, video_card
import logging

logger = logging.getLogger(__name__)

def render_global_search(db: SQLiteStore, vs: VectorStore):
    """Unified Global Search interface with Hybrid Ranking (Keyword + Semantic) and Advanced Filtering."""
    st.title("🌐 Unified Intelligence Search")
    st.markdown("---")

    # Sidebar: Advanced Filters
    with st.sidebar:
        st.markdown("### Search Filters")
        
        # Channel Filter
        channels = db.get_all_channels()
        selected_channels = st.multiselect(
            "Filter by Channel",
            options=channels,
            format_func=lambda c: c.name,
            help="Restrict search results to specific research sources."
        )
        
        # Date Filter
        use_date_filter = st.checkbox("Filter by Date Range")
        if use_date_filter:
            date_range = st.date_input("Capture Date Range", value=[])
        else:
            date_range = None
            
        st.markdown("---")
        top_k = st.slider("Results to display", 5, 50, 20)

    # Main Search Input
    query = st.text_input("Deep search across transcripts, summaries, and claims...", placeholder="e.g. 'impact of generative AI on productivity'", label_visibility="collapsed")

    if query:
        # Prepare filters for VectorStore
        where_filter = {}
        if selected_channels:
            ids = [c.channel_id for c in selected_channels]
            where_filter["channel_id"] = ids[0] if len(ids) == 1 else {"$in": ids}
        
        if use_date_filter and date_range and len(date_range) == 2:
            # Note: upload_date is usually ISO string. Direct comparison might be tricky with ChromaDB 'where'.
            # If dates are stored as YYYY-MM-DD
            where_filter["upload_date"] = {
                "$gte": date_range[0].isoformat(),
                "$lte": date_range[1].isoformat()
            }

        with st.spinner("Executing hybrid intelligence search..."):
            try:
                # 1. Keyword Search (FTS5)
                kw_results = db.fulltext_search(query, limit=top_k * 2)
                
                # 2. Semantic Search (resilient check for methods)
                vector_results = []
                summary_results = []
                claim_results = []
                
                if vs and vs.is_ready():
                    vector_results = vs.search(query, top_k=top_k * 2, where=where_filter)
                    
                    if hasattr(vs, "search_summaries"):
                        summary_results = vs.search_summaries(query, top_k=top_k, where=where_filter)
                    
                    if hasattr(vs, "search_claims"):
                        try:
                            claim_results = vs.search_claims(query, top_k=top_k, where=where_filter)
                        except Exception as e:
                            logger.warning(f"Claims search failed: {e}")
                else:
                    st.warning("Vector core is currently offline. Falling back to keyword-only search.")

                # 3. Hybrid Ranking (Reciprocal Rank Fusion - RRF)
                scores = {}
                k = 60 

                def update_rrf(results, weight=1.0):
                    for i, res in enumerate(results):
                        v_id = res.get("video_id")
                        if not v_id: continue
                        
                        if v_id not in scores:
                            scores[v_id] = {"rrf": 0.0, "matches": [], "type": "video"}
                        
                        scores[v_id]["rrf"] += weight * (1.0 / (k + i))
                        
                        text = res.get("snippet") or res.get("text") or ""
                        if text not in [m["text"] for m in scores[v_id]["matches"]]:
                            scores[v_id]["matches"].append({
                                "text": text,
                                "type": "transcript" if "snippet" in res else ("summary" if "video_id" in res and "claim_id" not in res else "claim")
                            })

                update_rrf(kw_results, weight=1.2) 
                update_rrf(vector_results, weight=1.0) 
                
                for i, res in enumerate(summary_results):
                    v_id = res.get("video_id")
                    if v_id:
                        if v_id not in scores: scores[v_id] = {"rrf": 0.0, "matches": [], "type": "video"}
                        scores[v_id]["rrf"] += 1.0 / (k + i)
                        scores[v_id]["matches"].append({"text": res["text"][:200] + "...", "type": "summary"})

                for i, res in enumerate(claim_results):
                    v_id = res["metadata"].get("video_id")
                    if v_id:
                        if v_id not in scores: scores[v_id] = {"rrf": 0.0, "matches": [], "type": "video"}
                        scores[v_id]["rrf"] += 1.0 / (k + i)
                        scores[v_id]["matches"].append({"text": res["text"], "type": "claim"})

                # Sort and Render
                ranked_results = sorted(scores.items(), key=lambda x: x[1]["rrf"], reverse=True)[:top_k]

                if not ranked_results:
                    st.info("No matching insights found for the given filters.")
                    return

                st.write(f"Found {len(ranked_results)} relevant videos:")
                
                for v_id, data in ranked_results:
                    video = db.get_video(v_id)
                    if not video: continue
                    
                    with glass_card():
                        st.markdown(f"### {video.title}")
                        st.caption(f"{video.upload_date} | Synthesis Strength: {data['rrf']:.4f}")
                        
                        if data["matches"]:
                            for m in data["matches"][:3]:
                                prefix = "📝" if m["type"] == "summary" else ("🔬" if m["type"] == "claim" else "💬")
                                st.markdown(f"> {prefix} {m['text']}")
                        
                        if st.button("Drill Down", key=f"srch_drill_{v_id}"):
                            st.session_state.selected_transcript_vid = v_id
                            st.session_state.navigate = "Transcripts"
                            st.rerun()

            except Exception as e:
                st.error("Search engine encountered an unexpected error.")
                logger.error(f"Global search fatal: {e}", exc_info=True)

    else:
        glass_card("Intelligence Search", "Enter a query and use the sidebar filters to narrow down themes or dates across your entire vault.")
