"""Research Console page for knowledgeVault-YT."""

import json
import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(db):
    """Render the Research Console page."""
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Research Console</h1>
        <p>Ask natural language questions across your entire knowledge vault</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        with st.sidebar.expander("🔧 Query Syntax"):
            st.markdown("""
            **Filters** (optional):
            - `channel:name` — search within a channel
            - `topic:"machine learning"` — topic-aware search
            - `guest:"Elon Musk"` — guest-focused queries
            - `after:2024-01` — date filter
            - `before:2025-06` — date filter
            - `lang:en` — language filter

            **Example**:
            `channel:lexfridman topic:AI after:2024 What is AGI?`
            """)

        if "conversation" not in st.session_state:
            st.session_state.conversation = []

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
                        st.markdown(response.answer)

                        citations_data = []
                        if response.citations:
                            grouped = {}
                            for c in response.citations:
                                if c.video_title not in grouped:
                                    grouped[c.video_title] = []
                                grouped[c.video_title].append(c)

                            for video_title, group in grouped.items():
                                with st.expander(f"📁 Theme: {video_title} ({len(group)} citations)", expanded=True):
                                    for c in group:
                                        col1, col2 = st.columns([5, 1])
                                        with col1:
                                            st.markdown(
                                                f"- [{c.source_id}] **{c.video_title}** "
                                                f"([{c.timestamp_str}]({c.youtube_link}))"
                                            )
                                            topic = getattr(c, "topic", "") if hasattr(c, "topic") else c.get("topic", "")
                                            st.caption(f"📂 Topic: {topic or 'General Context'}")
                                        with col2:
                                            c1, c2 = st.columns(2)
                                            with c1:
                                                if st.button("✂️", key=f"clip_{c.source_id}", help="Extract raw MP4 clip"):
                                                    st.toast(f"Extracting {c.timestamp_str} clip.", icon="✂️")
                                            with c2:
                                                if st.button("📝", key=f"sum_{c.source_id}", help="Summarize full video"):
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
                            f"⏱️ {response.latency_ms:.0f}ms │ "
                            f"📄 {response.total_chunks_retrieved} retrieved → "
                            f"{response.total_chunks_used} used"
                            f"{conf_str}"
                        )
                        st.caption(meta)

                        if response.query_plan and response.query_plan.channel_filter:
                            st.caption(
                                f"🔧 Filters: channel={response.query_plan.channel_filter}, "
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
                        error_msg = f"Query failed: {e}. Make sure Ollama is running."
                        st.error(error_msg)
                        st.session_state.conversation[-1]["answer"] = error_msg

        if st.session_state.conversation:
            if st.sidebar.button("🗑️ Clear Conversation"):
                st.session_state.conversation = []
                st.rerun()
    except Exception as e:
        st.error(f"Failed to load Research Console: {e}")
        logger.error(f"Research Console error: {e}", exc_info=True)


def _render_inline_summary(db, citation):
    """Render an inline video summary within the Research Console."""
    from src.intelligence.summarizer import SummarizerEngine
    summarizer = SummarizerEngine(db)
    summary = summarizer.get_or_generate_summary(citation.video_id)
    if summary:
        with st.info(f"📝 Active Insights: {citation.video_title}"):
            st.markdown(f"**Executive Summary:** {summary.summary_text}")

            t_col1, t_col2 = st.columns(2)
            with t_col1:
                st.markdown("#### 📊 Topics & Sentiment")
                topics = json.loads(summary.topics_json)
                for t in topics:
                    s_icon = "⚖️"
                    if t.get("sentiment") == "Bullish":
                        s_icon = "📈"
                    elif t.get("sentiment") == "Bearish":
                        s_icon = "📉"
                    st.markdown(f"- **{t['name']}** {s_icon}")
                    if t.get("opportunities"):
                        for opp in t["opportunities"]:
                            st.caption(f"   💡 *Opp:* {opp}")

            with t_col2:
                st.markdown("#### ⏳ Narrative Timeline")
                timeline = json.loads(summary.timeline_json)
                if timeline:
                    for item in timeline:
                        st.markdown(f"- {item['topic']} (`{item.get('timestamp_hint', '—')}`)")
                else:
                    st.caption("No timeline available.")

            st.markdown("---")
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                st.markdown("#### 📚 Bibliography/References")
                refs = json.loads(summary.references_json)
                if refs:
                    for r in refs:
                        st.markdown(f"- {r}")
                else:
                    st.caption("No explicit references detected.")

            with r_col2:
                st.markdown("#### 🏆 Top Takeaways")
                takes = json.loads(summary.takeaways_json)
                for t in takes:
                    st.markdown(f"- {t}")

            if st.button("✖️ Close Insights", key=f"close_sum_{citation.source_id}"):
                st.session_state[f"show_sum_{citation.video_id}"] = False
                st.rerun()
