"""Research Console page for knowledgeVault-YT — Hybrid RAG search and chat."""

import json
import logging

import streamlit as st
from src.ui.components import (
    page_header,
    section_header,
    progress_step,
    info_card,
    warning_card,
    error_card,
    metric_grid,
    status_badge,
    spacer,
    tts_button,
)

logger = logging.getLogger(__name__)


def render(db, vs):
    """Render the Research Console page with professional UI."""
    
    # Professional page header
    page_header(
        title="Research Console",
        subtitle="Ask natural language questions across your entire knowledge vault"
    )

    try:
        # Query Syntax Helper
        with st.sidebar.expander("Query Syntax & Filters"):
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
            channel:lexfridman topic:AI after:2024 
            What is the definition of artificial general intelligence?
            ```
            """)

        if "conversation" not in st.session_state:
            st.session_state.conversation = []

        for entry in st.session_state.conversation:
            with st.chat_message("user"):
                st.markdown(entry["question"])
            with st.chat_message("assistant"):
                col_ans, col_tts = st.columns([6, 1])
                with col_ans:
                    st.markdown(entry["answer"])
                with col_tts:
                    tts_button(entry["answer"], key=f"tts_hist_{hash(entry['answer'])}")
                if entry.get("citations"):
                    with st.expander(f"Sources: {len(entry['citations'])}"):
                        for c in entry["citations"]:
                            st.markdown(
                                f"- [{c['source_id']}] **{c['video_title']}** "
                                f"([{c['timestamp']}]({c['link']}))"
                            )
                st.caption(entry.get("meta", ""))

        question = st.chat_input(
            "Ask a research question... (supports channel:, topic:, guest:, after:, before:)",
        )

        if question:
            st.session_state.conversation.append({"question": question, "answer": "...", "citations": []})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Searching vault and synthesizing answer..."):
                    try:
                        from src.intelligence.rag_engine import RAGEngine
                        from src.storage.vector_store import VectorStore

                        vs = VectorStore()
                        rag = RAGEngine(db, vs)

                        conv_history = None
                        if len(st.session_state.conversation) > 1:
                            history_parts = []
                            for prev in st.session_state.conversation[:-1][-3:]:
                                history_parts.append(
                                    f"Q: {prev['question']}\nA: {prev['answer'][:500]}"
                                )
                            conv_history = "\n\n".join(history_parts)

                        response = rag.query(question, conversation_history=conv_history)
                        col_ans, col_tts = st.columns([6, 1])
                        with col_ans:
                            st.markdown(response.answer)
                        with col_tts:
                            tts_button(response.answer, key="tts_current")

                        citations_data = []
                        if response.citations:
                            grouped = {}
                            for c in response.citations:
                                if c.video_title not in grouped:
                                    grouped[c.video_title] = []
                                grouped[c.video_title].append(c)

                            for video_title, group in grouped.items():
                                with st.expander(f"Theme: {video_title} ({len(group)} citations)", expanded=True):
                                    for c in group:
                                        col1, col2 = st.columns([5, 1])
                                        with col1:
                                            st.markdown(
                                                f"- [{c.source_id}] **{c.video_title}** "
                                                f"([{c.timestamp_str}]({c.youtube_link}))"
                                            )
                                            # Handle both dataclass properties and dict-like access
                                            topic = ""
                                            if hasattr(c, "topic"):
                                                topic = c.topic
                                            elif isinstance(c, dict):
                                                topic = c.get("topic", "")
                                            st.caption(f"Topic: {topic or 'General Context'}")
                                        with col2:
                                            c1, c2 = st.columns(2)
                                            with c1:
                                                if st.button("Clip", key=f"clip_{c.source_id}", help="Extract raw MP4 clip"):
                                                    st.toast(f"Extracting {c.timestamp_str} clip.")
                                            with c2:
                                                if st.button("Summary", key=f"sum_{c.source_id}", help="Summarize full video"):
                                                    st.session_state[f"show_sum_{c.video_id}"] = True

                                    if st.session_state.get(f"show_sum_{c.video_id}", False):
                                        _render_inline_summary(db, c)

                                    citations_data.append({
                                        "source_id": c.source_id,
                                        "video_id": c.video_id,
                                        "video_title": c.video_title,
                                        "timestamp": c.timestamp_str,
                                        "link": c.youtube_link,
                                        "topic": getattr(c, "topic", ""),
                                    })

                        # Week 1 Enhancement: Show raw data for verification
                        st.divider()
                        section_header("Verification Layer")
                        
                        # Query metrics
                        metrics = [
                            {
                                "value": len(response.citations),
                                "label": "Citations",
                                "delta_color": "info"
                            },
                            {
                                "value": response.total_chunks_retrieved,
                                "label": "Chunks Retrieved",
                                "delta_color": "info"
                            },
                            {
                                "value": f"{response.latency_ms:.0f}ms",
                                "label": "Query Time",
                                "delta_color": "info"
                            },
                        ]
                        metric_grid(metrics, cols=3)
                        
                        if response.verification_notes:
                            info_card("Verification Notes", response.verification_notes)
                        
                        # Raw chunks with original text
                        if response.raw_chunks:
                            with st.expander("Raw Source Chunks (Original Text)", expanded=False):
                                for i, raw in enumerate(response.raw_chunks, 1):
                                    with st.expander(
                                        f"{i}. {raw['chunk_id'][:20]}... ({raw['channel']}) [{raw['timestamp']}]",
                                        expanded=(i == 1)
                                    ):
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.write("**Cleaned Text:**")
                                            st.text_area(
                                                "Cleaned",
                                                value=raw['cleaned_text'][:500],
                                                height=150,
                                                disabled=True,
                                                key=f"raw_cleaned_{i}"
                                            )
                                        
                                        with col2:
                                            st.write("**Raw Text (Original):**")
                                            st.text_area(
                                                "Raw",
                                                value=raw['raw_text'][:500],
                                                height=150,
                                                disabled=True,
                                                key=f"raw_original_{i}"
                                            )
                                        
                                        st.caption(
                                            f"Link: {raw['youtube_link']} | "
                                            f"Chunk ID: {raw['chunk_id']}"
                                        )
                        
                        # Full transcripts for reference
                        if response.full_transcripts:
                            with st.expander(f"Full Transcripts ({len(response.full_transcripts)} videos)", expanded=False):
                                for transcript in response.full_transcripts:
                                    with st.expander(
                                        f"{transcript['title'][:50]} ({transcript['duration']})",
                                        expanded=False
                                    ):
                                        st.write(f"**Channel:** {transcript['channel']}")
                                        st.write(f"**Date:** {transcript['upload_date']}")
                                        st.write(f"**Chunks:** {transcript['chunk_count']}")
                                        
                                        st.text_area(
                                            "Full Transcript",
                                            value=transcript['full_text'][:2000],
                                            height=300,
                                            disabled=True,
                                            key=f"full_transcript_{transcript['video_id']}"
                                        )
                                        
                                        if len(transcript['full_text']) > 2000:
                                            st.caption(f"Showing first 2000 chars of {len(transcript['full_text'])} total. "
                                                      f"View full transcript in Transcripts page.")
                                        
                                        st.caption(f"Access via: {transcript['access_via']}")
                        
                        st.divider()

                        conf = response.confidence
                        conf_str = ""
                        if conf:
                            conf_str = (
                                f" │ 🎯 Confidence: {conf.overall:.0%} "
                                f"(relevance: {conf.chunk_relevance:.0%}, "
                                f"coverage: {conf.coverage:.0%}, "
                                f"diversity: {conf.source_diversity:.0%})"
                            )

                        meta = (
                            f"{response.latency_ms:.0f}ms │ "
                            f"{response.total_chunks_retrieved} retrieved - "
                            f"{response.total_chunks_used} used"
                            f"{conf_str}"
                        )
                        st.caption(meta)

                        if response.query_plan and response.query_plan.channel_filter:
                            st.caption(
                                f"Filters: channel={response.query_plan.channel_filter}, "
                                f"topic={response.query_plan.topic_filter or '—'}, "
                                f"guest={response.query_plan.guest_filter or '—'}"
                            )

                        st.session_state.conversation[-1] = {
                            "question": question,
                            "answer": response.answer,
                            "citations": citations_data,
                            "meta": meta,
                        }

                    except Exception as e:
                        import traceback
                        error_msg = f"Query failed: {e}. Make sure Ollama is running."
                        error_card("Query Processing Error", error_msg)
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())
                        st.session_state.conversation[-1]["answer"] = error_msg

        if st.session_state.conversation:
            if st.sidebar.button("Clear Conversation"):
                st.session_state.conversation = []
                st.rerun()
    except Exception as e:
        error_card("Console Error", f"Failed to load Research Console: {e}")
        with st.expander("🔍 Error Details"):
            import traceback
            st.code(traceback.format_exc())
        logger.error(f"Research Console error: {e}", exc_info=True)


def _render_inline_summary(db, citation):
    """Render an inline video summary within the Research Console."""
    from src.intelligence.summarizer import SummarizerEngine
    summarizer = SummarizerEngine(db)
    summary = summarizer.get_or_generate_summary(citation.video_id)
    if summary:
        with st.info(f"Active Insights: {citation.video_title}"):
            col_sum, col_tts = st.columns([4, 1])
            with col_sum:
                st.write(f"**Executive Summary:** {summary.summary_text}")
            with col_tts:
                tts_button(summary.summary_text, key=f"tts_inline_{citation.source_id}")

            t_col1, t_col2 = st.columns(2)
            with t_col1:
                st.markdown("#### Topics & Sentiment")
                topics = json.loads(summary.topics_json)
                for t in topics:
                    st.markdown(f"- **{t['name']}** ({t.get('sentiment', 'Neutral')})")
                    if t.get("opportunities"):
                        for opp in t["opportunities"]:
                            st.caption(f"   Opportunity: {opp}")

            with t_col2:
                st.markdown("#### Narrative Timeline")
                timeline = json.loads(summary.timeline_json)
                if timeline:
                    for item in timeline:
                        st.markdown(f"- {item['topic']} (`{item.get('timestamp_hint', '—')}`)")
                else:
                    st.caption("No timeline available.")

            st.markdown("---")
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                st.markdown("#### Bibliography & References")
                refs = json.loads(summary.references_json)
                if refs:
                    for r in refs:
                        st.markdown(f"- {r}")
                else:
                    st.caption("No explicit references detected.")

            with r_col2:
                st.markdown("#### Top Takeaways")
                takes = json.loads(summary.takeaways_json)
                for t in takes:
                    st.markdown(f"- {t}")

            if st.button("Close Insights", key=f"close_sum_{citation.source_id}"):
                st.session_state[f"show_sum_{citation.video_id}"] = False
                st.rerun()
