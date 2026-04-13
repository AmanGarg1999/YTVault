"""Dashboard page for knowledgeVault-YT — Intelligence Core Redesign."""

import json
import logging
import streamlit as st
from src.ui.components import (
    page_header,
    section_header,
    metric_grid,
    info_card,
    success_card,
    warning_card,
    status_badge,
    key_value_display,
    spacer,
    tts_button,
    side_car_layout,
    render_side_car,
    video_card,
)

logger = logging.getLogger(__name__)

def render_insights(db, video_id):
    """Render details for the side-car panel."""
    try:
        from src.intelligence.summarizer import SummarizerEngine
        summarizer = SummarizerEngine(db)
        summary = summarizer.get_or_generate_summary(video_id)
        
        if summary:
            st.markdown(f"**Research Summary**")
            st.write(summary.summary_text)
            
            # Action Buttons
            col1, col2 = st.columns(2)
            with col1:
                tts_button(summary.summary_text, key=f"tts_side_{video_id}")
            
            st.divider()
            
            # Key Takeaways
            st.markdown("**Core Takeaways**")
            try:
                takeaways = json.loads(summary.takeaways_json)
                for tk in takeaways:
                    st.markdown(f"- {tk}")
            except:
                st.caption("No structured takeaways available.")
            
            st.divider()
            
            # Sentiment & Citations
            st.markdown("**Intelligence Metrics**")
            sentiment_data = db.get_video_sentiment_series(video_id)
            if sentiment_data:
                sent_str = ""
                for s in sentiment_data:
                    score = s.get("score", 0.0)
                    color = "#10b981" if score > 0.3 else ("#ef4444" if score < -0.3 else "#22d3ee")
                    sent_str += f"<span style='color: {color}; font-size: 1.2rem;'>▮</span>"
                st.markdown(f"<div style='letter-spacing: -1px;'>{sent_str}</div>", unsafe_allow_html=True)
                st.caption("Sentiment Velocity")
            
            citations = db.get_citations_for_video(video_id)
            if citations:
                st.markdown("**External Evidence**")
                for c in citations:
                    st.markdown(f"- {c.name}")
                    
        else:
            st.warning("Analysis in progress...")
    except Exception as e:
        st.error(f"Insight Engine Error: {e}")

def render(db):
    """Render the redesigned Intelligence Core Dashboard."""
    
    # Initialize layout: Main / Side-Car
    main_col, side_col = side_car_layout()
    
    with main_col:
        page_header(
            "Intelligence Overview",
            "Synthesizing YouTube content into a verified local Knowledge Graph"
        )

        try:
            stats = db.get_pipeline_stats()

            # =====================================================================
            # KEY METRICS & VAULT HEALTH
            # =====================================================================
            
            total_channels = stats.get("total_channels", 0)
            
            if total_channels == 0:
                st.markdown("---")
                info_card(
                    "Welcome to your Research Intelligence OS", 
                    "Your vault is currently empty. To begin synthesizing intelligence, follow these steps:"
                )
                
                col_on1, col_on2, col_on3 = st.columns(3)
                with col_on1:
                    with glass_card(title="1. Harvest Sources"):
                        st.write("Paste a YouTube URL into the Command Bar at the top to start a harvest.")
                with col_on2:
                    with glass_card(title="2. Automated Triage"):
                        st.write("The engine will automatically analyze and index your content.")
                with col_on3:
                    with glass_card(title="3. Explore Connections"):
                        st.write("Use the Intelligence Lab to map neural pathways across your vault.")
                
                if st.button("PROCEED TO INGESTION HUB", type="primary", use_container_width=True):
                    st.session_state.navigate = "Ingestion Hub"
                    st.rerun()
                st.markdown("---")

            metrics = [
                {
                    "value": stats.get("total_channels", 0),
                    "label": "Channel" if stats.get("total_channels") == 1 else "Channels",
                    "delta": f"+{stats.get('new_channels', 0)}" if stats.get('new_channels') else None,
                    "delta_color": "positive",
                    "glow": True
                },
                {
                    "value": stats.get("total_videos", 0),
                    "label": "Video" if stats.get("total_videos") == 1 else "Videos",
                    "delta": f"+{stats.get('new_videos', 0)}" if stats.get('new_videos') else None,
                    "delta_color": "positive"
                },
                {
                    "value": stats.get("accepted", 0),
                    "label": "Indexed",
                    "delta": f"{stats.get('total_chunks', 0)} chunks",
                    "delta_color": "info"
                },
                {
                    "percentage": int((stats.get('done', 0) / max(stats.get('accepted', 1), 1) * 100)),
                    "label": "Vault Health",
                    "description": "Ready for Search"
                }
            ]
            metric_grid(metrics, cols=4)
            spacer("2rem")
            
            # =====================================================================
            # CHANNEL VELOCITY / LEADERBOARD
            # =====================================================================
            
            st.divider()
            section_header("High-Density Intel", icon="◈")
            st.caption("Top research targets ranked by knowledge density and sentiment weight.")
            
            leaderboard = db.get_knowledge_density_leaderboard(limit=5)
            if leaderboard:
                for row in leaderboard:
                    # Capture video object for the card
                    from types import SimpleNamespace
                    v_obj = SimpleNamespace(**row)
                    
                    cols = video_card(v_obj, show_actions=True)
                    if cols:
                        with cols[0]:
                            if st.button("Analyze", key=f"btn_anal_{row['video_id']}", use_container_width=True):
                                st.session_state.side_car_active = True
                                st.session_state.active_video_id = row['video_id']
                                st.rerun()
                        with cols[1]:
                            if st.button("Read Source", key=f"btn_src_{row['video_id']}", use_container_width=True):
                                st.session_state.navigate = "Transcripts"
                                st.session_state.selected_transcript_vid = row['video_id']
                                st.rerun()
            else:
                info_card("Knowledge Base Initializing", "Metadata is being harvested from your channels...")

            # =====================================================================
            # SYSTEM STATUS & OPERATIONS
            # =====================================================================
            
            st.divider()
            col_ops_l, col_ops_r = st.columns(2)
            
            with col_ops_l:
                section_header("Review Queue", icon="◯")
                pending = db.get_videos_by_status("PENDING_REVIEW", limit=2)
                if pending:
                    for v in pending:
                        st.markdown(f"<p style='font-size:0.9rem; color:var(--text-muted);'>• {v.title[:60]}...</p>", unsafe_allow_html=True)
                    if st.button("Enter Review Hub", type="primary", use_container_width=True):
                        st.session_state.navigate = "Review Center"
                        st.rerun()
                else:
                    success_card("Pipeline Optimized", "All triage decisions completed.")
            
            with col_ops_r:
                section_header("Active Pulse", icon="✦")
                scans = db.get_active_scans()
                if scans:
                    for s in scans:
                        progress_pct = (s.total_processed / max(s.total_discovered, 1))
                        safe_pct = max(0.0, min(1.0, progress_pct))
                        st.caption(f"{s.channel_name or 'System'} | {progress_pct:.0%}")
                        st.progress(safe_pct)
                else:
                    st.caption("Intelligence engine idling...")

        except Exception as e:
            st.error(f"Dashboard Fault: {e}")
            logger.error(f"Dashboard error: {e}", exc_info=True)

    # =====================================================================
    # SIDE-CAR PANEL RENDERING
    # =====================================================================
    if side_col and st.session_state.get("active_video_id"):
        with side_col:
            video_id = st.session_state.active_video_id
            # Get video title for header
            v_title = db.conn.execute("SELECT title FROM videos WHERE video_id = ?", (video_id,)).fetchone()
            v_title = v_title[0] if v_title else "Intel Detail"
            
            render_side_car(v_title[:40]+"...", lambda: render_insights(db, video_id))

