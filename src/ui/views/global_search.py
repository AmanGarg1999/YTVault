import streamlit as st
import pandas as pd
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.ui.components.ui_helpers import glass_card, video_card
import logging

logger = logging.getLogger(__name__)

def render_global_search(db: SQLiteStore, vs: VectorStore):
    """Unified Global Search interface with Hybrid Ranking (Keyword + Semantic)."""
    st.title("🌐 Unified Intelligence Search")
    st.markdown("---")

    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input("Deep search across transcripts, summaries, and claims...", placeholder="e.g. 'impact of generative AI on productivity'")
    with col2:
        top_k = st.slider("Top results", 5, 50, 20)

    if query:
        with st.spinner("Analyzing knowledge vault..."):
            # 1. Keyword Search (FTS5) - Ranking: Lower is better
            kw_results = db.fulltext_search(query, limit=top_k * 2)
            
            # 2. Semantic Search (ChromaDB) - Ranking: Lower is better (distance)
            vector_results = vs.search(query, top_k=top_k * 2)
            summary_results = vs.search_summaries(query, top_k=top_k)
            claim_results = vs.search_claims(query, top_k=top_k)

            # 3. Hybrid Ranking (Reciprocal Rank Fusion - RRF)
            # Map video_id/chunk_id to scores
            scores = {}
            k = 60 # RRF constant

            def update_rrf(results, weight=1.0):
                for i, res in enumerate(results):
                    # We group by video_id to avoid overwhelming with chunks
                    v_id = res.get("video_id")
                    if not v_id: continue
                    
                    if v_id not in scores:
                        scores[v_id] = {"rrf": 0.0, "matches": [], "type": "video"}
                    
                    scores[v_id]["rrf"] += weight * (1.0 / (k + i))
                    
                    # Store snippet/text
                    text = res.get("snippet") or res.get("text") or ""
                    if text not in [m["text"] for m in scores[v_id]["matches"]]:
                        scores[v_id]["matches"].append({
                            "text": text,
                            "type": "transcript" if "snippet" in res else ("summary" if "video_id" in res and "claim_id" not in res else "claim")
                        })

            update_rrf(kw_results, weight=1.2) # Keyword weight
            update_rrf(vector_results, weight=1.0) # Semantic weight
            
            # For summaries and claims, we also update RRF
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

            # Sort by RRF score descending
            ranked_results = sorted(scores.items(), key=lambda x: x[1]["rrf"], reverse=True)[:top_k]

            if not ranked_results:
                st.info("No matching insights found. Try broadening your query.")
                return

            st.write(f"Found {len(ranked_results)} relevant videos:")
            
            for v_id, data in ranked_results:
                video = db.get_video(v_id)
                if not video: continue
                
                with st.container():
                    # Custom card for search results
                    st.markdown(f"""
                    <div class="glass_card" style="margin-bottom: 20px; padding: 20px;">
                        <h3 style="margin-top: 0; color: #00f2fe;">{video.title}</h3>
                        <p style="font-size: 0.8em; color: #a0aec0;">{video.upload_date} | Impact Score: {data['rrf']:.4f}</p>
                    """, unsafe_allow_html=True)
                    
                    # Show matching snippets
                    if data["matches"]:
                        st.markdown("**Relevant Insights:**")
                        for m in data["matches"][:3]:
                            prefix = "📝" if m["type"] == "summary" else ("🔬" if m["type"] == "claim" else "💬")
                            st.markdown(f"> {prefix} {m['text']}", unsafe_allow_html=True)
                    
                    col_btn1, col_btn2 = st.columns([1, 4])
                    with col_btn1:
                        if st.button("Open Analysis", key=f"btn_{v_id}"):
                            st.session_state.selected_transcript_vid = v_id
                            st.session_state.navigate = "Transcripts"
                            st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)

    else:
        # Show some search tips or recent activity
        glass_card("Search Tips", "Use specific keywords for exact matches, or natural language for conceptual discovery. The hybrid engine will find the best overlap.")
