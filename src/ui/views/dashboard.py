"""Dashboard page for knowledgeVault-YT — Professional analytics and overview."""

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
)

logger = logging.getLogger(__name__)


def render(db):
    """Render the Dashboard page with professional UI components."""
    
    # Page header with proper branding
    page_header(
        "KnowledgeVault Dashboard",
        "Local-first Research Intelligence System — Transform YouTube into a Knowledge Graph"
    )

    try:
        stats = db.get_pipeline_stats()

        # =====================================================================
        # KEY METRICS - Professional Metric Grid
        # =====================================================================
        
        section_header("System Overview")
        metrics = [
            {
                "value": stats.get("total_channels", 0),
                "label": "Channels",
                "delta": f"+{stats.get('new_channels', 0)} new" if stats.get('new_channels') else None,
                "delta_color": "positive"
            },
            {
                "value": stats.get("total_videos", 0),
                "label": "Videos",
                "delta": f"+{stats.get('new_videos', 0)} new" if stats.get('new_videos') else None,
                "delta_color": "positive"
            },
            {
                "value": stats.get("accepted", 0),
                "label": "Accepted",
                "delta_color": "positive"
            },
            {
                "value": stats.get("total_chunks", 0),
                "label": "Indexed Chunks",
                "delta_color": "positive"
            },
            {
                "value": stats.get("total_subscribers", 0),
                "label": "Total Followers",
                "delta_color": "info"
            },
            {
                "value": f"{(stats.get('done', 0) / max(stats.get('total_videos', 1), 1) * 100):.0f}%",
                "label": "Health Index",
                "delta_color": "info"
            }
        ]
        metric_grid(metrics, cols=3)
        spacer()
        
        # =====================================================================
        # LANGUAGE DISTRIBUTION
        # =====================================================================
        
        st.divider()
        section_header("Language Distribution")
        
        try:
            # Get all videos and their languages
            all_videos = db.conn.execute(
                "SELECT language_iso, COUNT(*) as count FROM videos GROUP BY language_iso ORDER BY count DESC"
            ).fetchall()
            
            if all_videos:
                lang_map = {
                    "en": "English",
                    "es": "Spanish",
                    "fr": "French",
                    "de": "German",
                    "it": "Italian",
                    "pt": "Portuguese",
                    "nl": "Dutch",
                    "ru": "Russian",
                    "ja": "Japanese",
                    "zh": "Chinese",
                    "ko": "Korean",
                    "ar": "Arabic",
                    "hi": "Hindi",
                    "th": "Thai",
                    "vi": "Vietnamese",
                }
                
                lang_cols = st.columns(len(all_videos[:5]))
                
                for i, (lang_iso, count) in enumerate(all_videos[:5]):
                    with lang_cols[i]:
                        lang_name = lang_map.get(lang_iso, lang_iso.upper())
                        st.metric(lang_name, count)
                
                # Translation status
                st.markdown("---")
                needs_translation = db.conn.execute(
                    "SELECT COUNT(*) FROM videos WHERE needs_translation = 1 AND language_iso != 'en'"
                ).fetchone()[0]
                
                if needs_translation > 0:
                    warning_card(
                        f"{needs_translation} Videos Need Translation",
                        "Non-English content is ready for automated translation. Visit the Ingestion Hub to process."
                    )
        except Exception as e:
            logger.warning(f"Could not load language statistics: {e}")
        
        # =====================================================================
        # PIPELINE PROGRESS
        # =====================================================================
        
        st.divider()
        section_header("Pipeline Progress")
        
        total = stats.get("total_videos", 0)
        if total > 0:
            done = stats.get("done", 0)
            progress = done / total
            
            # Detailed progress breakdown
            progress_data = {
                "Total Videos": total,
                "Completed": done,
                "In Progress": stats.get("in_progress", 0),
                "Pending": stats.get("pending", 0),
                "Rejected": stats.get("rejected", 0),
            }
            
            col_a, col_b = st.columns([2, 1])
            with col_a:
                # Clamp progress between 0 and 1.0 to avoid Streamlit ValueError
                safe_progress = max(0.0, min(1.0, progress))
                st.progress(safe_progress, text=f"Overall Progress: {done}/{total} ({progress:.0%})")
            with col_b:
                st.markdown(f"**Est. Time Remaining:** {stats.get('eta_minutes', 'N/A')} min" if stats.get('eta_minutes') else "**ETA:** Computing...")
            
            with st.expander("Detailed Pipeline Breakdown"):
                key_value_display(progress_data)
        else:
            warning_card("No Videos Ingested Yet", "Start a Harvest from the Harvest Manager to begin processing YouTube content.")
        
        # =====================================================================
        # ACTIVE OPERATIONS
        # =====================================================================
        
        st.divider()
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            section_header("Pending Review")
            pending = db.get_videos_by_status("PENDING_REVIEW", limit=3)
            if pending:
                for v in pending:
                    st.markdown(f"- **{v.title[:50]}...**")
                if st.button("Manage Review Queue", type="primary", use_container_width=True):
                    st.session_state.navigate = "Review Center"
                    st.rerun()
            else:
                success_card("All Clear!", "No videos pending review.")
        
        with col_right:
            section_header("Active Operations")
            scans = db.get_active_scans()
            if scans:
                for s in scans:
                    progress_pct = (s.total_processed / max(s.total_discovered, 1))
                    display_name = s.channel_name if s.channel_name else f"Scan {s.scan_id[-8:]}"
                    st.caption(f"{display_name} — {s.scan_type} ({progress_pct:.0%})")
                    safe_pct = max(0.0, min(1.0, progress_pct))
                    st.progress(safe_pct)
            else:
                info_card("No Active Scans", "System is idle.")
        
        # =====================================================================
        # KNOWLEDGE DENSITY LEADERBOARD
        # =====================================================================
        
        st.divider()
        section_header("Top Research Insights")
        st.caption("Top videos ranked by extracted topics, guest appearances, and chunk density per minute")
        
        leaderboard = db.get_knowledge_density_leaderboard(limit=10)
        if leaderboard:
            for idx, row in enumerate(leaderboard, 1):
                # Use columns for responsive layout
                col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 1.5, 1.5, 1.5, 1.2])
                
                with col1:
                    st.markdown(f"### {idx}")
                
                with col2:
                    st.markdown(f"**{row['title'][:45]}...**")
                    st.caption(f"{row['channel_name']}")
                
                with col3:
                    st.metric("Density", f"{row['density_score']:.2f}", label_visibility="collapsed")
                
                with col4:
                    st.metric("Guests", row["guest_count"], label_visibility="collapsed")
                
                with col5:
                    st.metric("Chunks", row["chunk_count"], label_visibility="collapsed")
                
                with col6:
                    if st.button("View", key=f"dash_view_{row['video_id']}", use_container_width=True):
                        st.session_state[f"show_sum_{row['video_id']}"] = True
                        st.rerun()
                
                # Expandable summary view
                if st.session_state.get(f"show_sum_{row['video_id']}", False):
                    try:
                        from src.intelligence.summarizer import SummarizerEngine
                        summarizer = SummarizerEngine(db)
                        summary = summarizer.get_or_generate_summary(row['video_id'])
                        if summary:
                            with st.expander("Deep Video Insights", expanded=True):
                                col_text, col_tts = st.columns([4, 1])
                                with col_text:
                                    st.write(summary.summary_text)
                                with col_tts:
                                    tts_button(summary.summary_text, key=f"tts_dash_{row['video_id']}")
                                
                                col_topics, col_takeaways = st.columns(2)
                                with col_topics:
                                    st.markdown("**Core Topics**")
                                    try:
                                        topics = json.loads(summary.topics_json)
                                        for t in topics:
                                            relevance = t.get('relevance', 0.5)
                                            badge_html = status_badge('info', f"{relevance:.1f}")
                                            st.markdown(
                                                f"- **{t['name']}** {badge_html}",
                                                unsafe_allow_html=True
                                            )
                                    except Exception:
                                        st.write("No topics available.")
                                
                                with col_takeaways:
                                    st.markdown("**Key Takeaways**")
                                    try:
                                        takeaways = json.loads(summary.takeaways_json)
                                        for tk in takeaways:
                                            st.markdown(f"- {tk}")
                                    except Exception:
                                        st.write("No takeaways available.")
                                
                                # --- Advanced Suite additions ---
                                st.divider()
                                col_sent, col_cite = st.columns(2)
                                
                                with col_sent:
                                    st.markdown("**Sentiment Heatmap**")
                                    sentiment_data = db.get_video_sentiment_series(row['video_id'])
                                    if sentiment_data:
                                        # Simple Sparkline-style visualization using markdown
                                        sent_str = ""
                                        for s in sentiment_data:
                                            score = s.get("score", 0.0)
                                            color = "#10b981" if score > 0.3 else ("#ef4444" if score < -0.3 else "#3b82f6")
                                            sent_str += f"<span style='color: {color}; font-size: 1.5rem;' title='{s.get('label', 'Neutral')}'>▮</span>"
                                        st.markdown(f"<div style='letter-spacing: -2px;'>{sent_str}</div>", unsafe_allow_html=True)
                                        st.caption("Timeline: Left (Start) - Right (End)")
                                    else:
                                        st.caption("No sentiment data available for this video.")

                                with col_cite:
                                    st.markdown("**External Citations**")
                                    citations = db.get_citations_for_video(row['video_id'])
                                    if citations:
                                        for c in citations:
                                            icon = "Paper" if c.type == "PAPER" else ("Book" if c.type == "BOOK" else "Link")
                                            if c.url:
                                                st.markdown(f"{icon} [{c.name}]({c.url})")
                                            else:
                                                st.markdown(f"{icon} {c.name}")
                                    else:
                                        st.caption("No citations detected.")
                                
                                if st.button("Close", key=f"close_dash_{row['video_id']}", use_container_width=True):
                                    st.session_state[f"show_sum_{row['video_id']}"] = False
                                    st.rerun()
                    except Exception as e:
                        error_msg = f"Could not load insights: {str(e)[:60]}"
                        warning_card("Error Loading Details", error_msg)
                
                st.divider()

        else:
            info_card(
                "Leaderboard Coming Soon",
                "Videos will appear here once they're fully ingested and indexed. Start harvesting to populate this list!"
            )

        # =====================================================================
        # ENGAGEMENT LEADERBOARD
        # =====================================================================
        
        st.divider()
        section_header("Engagement Analysis")
        st.caption("Videos with the highest engagement rate (likes + comments per view)")
        
        engaged = db.get_most_engaged_videos(limit=5)
        if engaged:
            for idx, row in enumerate(engaged, 1):
                col1, col2, col3, col4, col5 = st.columns([1, 4, 1.5, 1.5, 1.5])
                
                with col1:
                    st.markdown(f"### {idx}")
                
                with col2:
                    st.markdown(f"**{row['title'][:55]}...**")
                    st.caption(f"{row['view_count']:,} views")
                
                with col3:
                    st.metric("Engagement", f"{row['engagement_rate']*100:.1f}%")
                
                with col4:
                    st.metric("Likes", f"{row['like_count']:,}")
                
                with col5:
                    st.metric("Comments", f"{row['comment_count']:,}")
                
                st.divider()
        else:
            info_card("No Engagement Data", "Engagement metrics will appear once videos are harvested with likes and comments.")
    
        # =====================================================================
        # VIRAL MOMENTUM
        # =====================================================================
        
        st.divider()
        section_header("Content Momentum")
        st.caption("Videos gaining views the fastest (hourly velocity)")
        
        momentum = db.get_high_momentum_videos(limit=5)
        if momentum:
            for idx, row in enumerate(momentum, 1):
                col1, col2, col3, col4, col5 = st.columns([0.8, 4, 1.5, 1.5, 1.5])
                
                with col1:
                    st.markdown(f"### {idx}")
                
                with col2:
                    st.markdown(f"**{row['title'][:55]}...**")
                    st.caption(f"{row['channel_name']}")
                
                with col3:
                    st.metric("Velocity", f"{row['velocity']:.1f}/hr")
                
                with col4:
                    st.metric("Total Views", f"{row['current_views']:,}")
                
                with col5:
                    st.metric("Growth", f"+{row['growth']:,}")
                
                st.divider()
        else:
            info_card("No Momentum Data", "Velocity tracking requires at least two harvests per channel.")

    except Exception as e:
        import traceback
        st.error(f"Dashboard Error: {e}")
        with st.expander("Error Details"):
            st.code(traceback.format_exc())
        logger.error(f"Dashboard error: {e}", exc_info=True)
