"""
Transcript Viewer page for knowledgeVault-YT.

Enables verification workflow:
- View full transcripts without re-fetching from YouTube
- Search across transcripts
- Compare multiple transcripts side-by-side
- Export transcripts for reference
"""

import streamlit as st
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.analysis_engine import AnalysisEngine
from src.ui.components.ui_helpers import pipeline_trace_timeline


def render(db: SQLiteStore):
    """Main transcript viewer interface."""
    
    st.markdown("""
    <div class="main-header">
        <h1>Transcript Viewer</h1>
        <p>Access all stored transcripts - no re-fetching from YouTube</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation between modes
    mode = st.radio(
        "View Mode",
        ["Single Transcript", "Compare Multiple", "Global Search"],
        horizontal=True
    )
    
    if mode == "Single Transcript":
        render_single_transcript(db)
    elif mode == "Compare Multiple":
        render_compare_transcripts(db)
    else:
        render_global_search(db)


def render_single_transcript(db: SQLiteStore):
    """View a single transcript with search and navigation."""
    
    st.subheader("View Single Transcript")
    
    # =====================================================================
    # Navigation & Video Selection (Scalable)
    # =====================================================================
    
    # Fetch all accepted videos
    all_videos = db.get_videos_by_status("ACCEPTED", limit=2000)
    
    if not all_videos:
        st.info("No accepted videos found. Process some videos first!")
        return

    # Selection Logic using cards
    if "selected_transcript_vid" not in st.session_state:
        st.session_state.selected_transcript_vid = None

    # Search filter
    search_query = st.text_input("🔍 Search videos...", placeholder="Type to filter titles or channels...", key="transcript_vid_search")
    
    filtered_vids = all_videos
    if search_query:
        filtered_vids = [v for v in all_videos if search_query.lower() in v.title.lower() or search_query.lower() in v.channel_id.lower()]
    
    # Display results as a grid of selection cards
    if filtered_vids:
        st.write(f"Showing {len(filtered_vids[:12])} of {len(filtered_vids)} videos")
        cols = st.columns(3)
        for i, video in enumerate(filtered_vids[:12]):
            with cols[i % 3]:
                with st.container(border=True):
                    st.caption(video.channel_id[:20])
                    st.markdown(f"**{video.title[:60]}...**")
                    if st.button("VIEW TRANSCRIPT", key=f"sel_vid_{video.video_id}", use_container_width=True, type="primary"):
                        st.session_state.selected_transcript_vid = video.video_id
                        st.rerun()

    if not st.session_state.selected_transcript_vid:
        st.info("Select a video from the grid above to view its transcript.")
        return

    selected_vid_id = st.session_state.selected_transcript_vid
    
    video = db.get_video(selected_vid_id)
    
    if not video:
        st.error("Selected video not found.")
        return
    
    video_id = video.video_id
    
    # Fetch transcript
    transcript = db.get_full_transcript(video_id)
    
    if not transcript:
        st.error("Transcript not found in database")
        return
    
    # Display metadata
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Channel", transcript['channel'])
    col2.metric("Duration", f"{transcript['duration_seconds'] // 60}m {transcript['duration_seconds'] % 60}s")
    col3.metric("Date", transcript['upload_date'])
    col4.metric("Chunks", transcript['total_chunks'])
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Full Transcript", "Search", "Timestamp Jump", "Audience Highlights", "Intelligence Trace", "Export"])
    
    with tab1:
        st.subheader("Full Transcript")
        
        col_ctrl1, col_ctrl2 = st.columns([1, 1])
        with col_ctrl1:
            view_type = st.radio("Content Source", ["Cleaned (normalized)", "Raw (original)"], horizontal=True, key="view_type")
        with col_ctrl2:
            show_highlights = st.checkbox("Highlight High-Attention Segments", value=True, help="Segments with high audience retention/rewatch interest are highlighted in indigo.")
        
        if view_type == "Cleaned (normalized)" and show_highlights:
            content = ""
            for c in transcript['chunks']:
                text = c['cleaned_text']
                if c.get('is_high_attention'):
                    content += f"<span style='background: rgba(99, 102, 241, 0.25); border-bottom: 2px solid #6366f1; border-radius: 2px;' title='High Audience Retention'>{text}</span> "
                else:
                    content += f"{text} "
            
            st.markdown(f"""
            <div style="
                background: rgba(15, 23, 42, 0.6);
                color: #e2e8f0;
                padding: 1.5rem;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.05);
                height: 600px;
                overflow-y: auto;
                font-family: 'Inter', sans-serif;
                line-height: 1.8;
                font-size: 1rem;
                white-space: pre-wrap;
            ">
                {content}
            </div>
            """, unsafe_allow_html=True)
        else:
            text = transcript['full_cleaned_text'] if view_type == "Cleaned (normalized)" else transcript['full_raw_text']
            st.text_area(
                "Transcript Text",
                value=text,
                height=500,
                disabled=True,
                key="transcript_text"
            )
    
    with tab2:
        st.subheader("Search Within Transcript")
        
        search_term = st.text_input("Search term", key="search_input")
        
        if search_term:
            results = db.search_transcript(video_id, search_term)
            st.success(f"Found {len(results)} matches")
            
            if results:
                for i, r in enumerate(results, 1):
                    # Format timestamp
                    mins = int(r['start_timestamp'] // 60)
                    secs = int(r['start_timestamp'] % 60)
                    timestamp_str = f"{mins:02d}:{secs:02d}"
                    
                    # Create expander with timestamp info
                    with st.expander(
                        f"**Match {i}** ({timestamp_str}) - {r['chunk_id'][:20]}...",
                        expanded=(i == 1)
                    ):
                        col1, col2 = st.columns([1, 20])
                        
                        with col1:
                            st.write(f"**{timestamp_str}**")
                        
                        with col2:
                            # Show context
                            text = r['cleaned_text']
                            
                            # Highlight search term
                            highlighted = text.replace(
                                search_term,
                                f"**{search_term}**"
                            )
                            st.write(highlighted)
                            
                            st.caption(
                                f"Chunk: {r['chunk_id']} | "
                                f"Range: {int(r['start_timestamp'])}s - {int(r['end_timestamp'])}s"
                            )
    
    with tab3:
        st.subheader("Jump to Timestamp")
        
        col1, col2 = st.columns(2)
        with col1:
            minutes = st.number_input("Minutes", min_value=0, max_value=1000, key="ts_min")
        with col2:
            seconds = st.number_input("Seconds", min_value=0, max_value=59, key="ts_sec")
        
        timestamp = minutes * 60 + seconds
        
        if st.button("Jump to timestamp", key="jump_btn", type="primary"):
            context = db.get_transcript_at_timestamp(video_id, timestamp, context_seconds=30)
            
            if context and context['chunks']:
                st.info(f"Context around {minutes}:{seconds:02d}")
                
                for chunk in context['chunks']:
                    st.write(chunk['cleaned_text'])
                    st.caption(
                        f"{chunk['chunk_id']} | "
                        f"{int(chunk['start_timestamp'])}s - {int(chunk['end_timestamp'])}s"
                    )
                    st.divider()
            else:
                st.warning("No transcript found at that timestamp")
    
    with tab4:
        st.subheader("Audience Highlights")
        st.caption("Segments with the highest re-watch interest on YouTube, correlated with transcript text.")
        
        analyzer = AnalysisEngine(db)
        highlights = analyzer.get_heatmap_highlights(video_id)
        
        if not highlights:
            st.info("No heatmap data available for this video yet. Heatmaps are harvested during the 'Discovery' stage.")
        else:
            for i, h in enumerate(highlights, 1):
                # Format timestamp
                mins = int(h.start_time // 60)
                secs = int(h.start_time % 60)
                timestamp_str = f"{mins:02d}:{secs:02d}"
                
                with st.expander(f"**Highlight {i}** ({timestamp_str}) - Interest Score: {h.score:.1f}", expanded=(i == 1)):
                    st.markdown(f"> {h.transcript_text}")
                    
                    if st.button(f"Jump to {timestamp_str}", key=f"jump_h_{i}", type="primary"):
                        st.session_state.ts_min = mins
                        st.session_state.ts_sec = secs
                        # We would need a more complex way to force tab change,
                        # for now just showing the info is great.
                        st.success(f"Selected {timestamp_str}. Switch to 'Timestamp Jump' to see context.")

    with tab5:
        st.subheader("Intelligence Trace")
        st.caption("Detailed chronological telemetry of the intelligence gathering process.")
        
        logs = db.get_video_pipeline_history(video_id)
        pipeline_trace_timeline(logs)

    with tab6:
        st.subheader("Export Transcript")
        
        export_format = st.radio("Format", ["Text (.txt)", "Markdown (.md)"], key="export_fmt")
        
        if export_format == "Markdown (.md)":
            export_text = f"""# {transcript['title']}

**Channel:** {transcript['channel']}  
**Date:** {transcript['upload_date']}  
**Duration:** {transcript['duration_seconds'] // 60}m  
**Language:** {transcript['language']}  
**Strategy:** {transcript['transcript_strategy']}  

## Full Transcript

{transcript['full_cleaned_text']}

---

*Exported from knowledgeVault-YT*
"""
            filename = f"transcript_{video_id}.md"
        else:
            export_text = transcript['full_cleaned_text']
            filename = f"transcript_{video_id}.txt"
        
        st.download_button(
            f"Download as {export_format.split('.')[0]}",
            export_text,
            filename,
            "text/plain",
            key="export_btn"
        )


def render_compare_transcripts(db: SQLiteStore):
    """View and compare multiple transcripts side-by-side."""
    
    st.subheader("Compare Multiple Transcripts")
    
    # Select videos
    videos = db.execute("""
        SELECT v.video_id, v.title, c.name as channel, v.upload_date
        FROM videos v
        JOIN channels c ON v.channel_id = c.channel_id
        WHERE v.video_id IN (SELECT DISTINCT video_id FROM transcript_chunks)
        ORDER BY v.upload_date DESC
        LIMIT 2000
    """).fetchall()
    
    if not videos:
        st.warning("No processed videos found")
        return
    
    if "compare_list" not in st.session_state:
        st.session_state.compare_list = []
    
    st.write("Add 2-3 videos to your comparison list")
    
    col_search, col_reset = st.columns([4, 1])
    with col_search:
        search_q = st.text_input("🔍 Search for videos to compare...", placeholder="Search vidoes...", key="compare_search")
    with col_reset:
        if st.button("Reset List", use_container_width=True):
            st.session_state.compare_list = []
            st.rerun()

    # Filtered list
    filtered_compare = [v for v in videos if search_q.lower() in v['title'].lower()] if search_q else videos[:10]
    
    if filtered_compare:
        cols = st.columns(2)
        for i, v in enumerate(filtered_compare[:6]):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{v['title'][:60]}...**")
                    st.caption(f"{v['channel']} | {v['upload_date']}")
                    if v['video_id'] in st.session_state.compare_list:
                        st.success("Selected")
                    elif len(st.session_state.compare_list) < 3:
                        if st.button("Select", key=f"comp_sel_{v['video_id']}", use_container_width=True, type="primary"):
                            st.session_state.compare_list.append(v['video_id'])
                            st.rerun()

    if len(st.session_state.compare_list) < 2:
        st.info(f"Comparison list: {len(st.session_state.compare_list)}/3 selected. Select at least 2 videos.")
        return
    
    video_ids = st.session_state.compare_list
    transcripts = db.compare_transcripts(video_ids)
    
    if not transcripts:
        st.error("Could not fetch transcripts")
        return
    
    # Side-by-side view
    if len(transcripts) == 2:
        st.subheader("Side-by-Side Comparison")
        col1, col2 = st.columns(2)
        
        transcripts_list = list(transcripts.values())
        
        with col1:
            t1 = transcripts_list[0]
            st.write(f"### {t1['title']}")
            st.caption(f"{t1['channel']} | {t1['upload_date']}")
            
            text1 = t1['full_cleaned_text']
            st.text_area(
                "Transcript 1",
                value=text1[:3000],
                height=400,
                disabled=True,
                key="compare_1"
            )
            
            if len(text1) > 3000:
                st.caption(f"Showing first 3000 chars of {len(text1)} total")
        
        with col2:
            t2 = transcripts_list[1]
            st.write(f"### {t2['title']}")
            st.caption(f"{t2['channel']} | {t2['upload_date']}")
            
            text2 = t2['full_cleaned_text']
            st.text_area(
                "Transcript 2",
                value=text2[:3000],
                height=400,
                disabled=True,
                key="compare_2"
            )
            
            if len(text2) > 3000:
                st.caption(f"Showing first 3000 chars of {len(text2)} total")
    
    else:  # 3 videos
        st.subheader("Three-Way Comparison")
        col1, col2, col3 = st.columns(3)
        
        transcripts_list = list(transcripts.values())
        
        for i, col in enumerate([col1, col2, col3]):
            if i < len(transcripts_list):
                with col:
                    t = transcripts_list[i]
                    st.write(f"### {t['title'][:40]}")
                    st.caption(f"{t['channel']}")
                    
                    text = t['full_cleaned_text']
                    st.text_area(
                        f"Transcript {i+1}",
                        value=text[:2000],
                        height=300,
                        disabled=True,
                        key=f"compare_{i}"
                    )
                    
                    if len(text) > 2000:
                        st.caption(f"Showing first 2000 chars of {len(text)}")


def render_global_search(db: SQLiteStore):
    """Global search across all transcripts."""
    
    st.subheader("Search All Transcripts")
    
    st.write("Find any term across your entire vault of stored transcripts")
    
    search_term = st.text_input("Search term", key="global_search")
    
    if not search_term:
        st.info("Enter a search term to find it across all transcripts")
        return
    
    # Search
    results = db.search_all_transcripts(search_term, limit=100)
    
    if not results:
        st.warning(f"No results found for '{search_term}'")
        return
    
    st.success(f"Found in **{len(results)} videos**")
    
    # Show results grouped by video
    for r in results:
        with st.expander(
            f"{r['title'][:60]} ({r['channel']}) - {r['chunk_count']} matches",
            expanded=False
        ):
            # Get specific matching chunks
            chunks = db.search_transcript(r['video_id'], search_term)
            
            st.write(f"**Total matches:** {len(chunks)}")
            
            # Show first 5 matches
            shown = min(5, len(chunks))
            
            for i, chunk in enumerate(chunks[:5], 1):
                with st.expander(f"Match {i} - {int(chunk['start_timestamp'])}s", expanded=(i == 1)):
                    
                    # Highlight the search term
                    text = chunk['cleaned_text']
                    highlighted = text.replace(
                        search_term,
                        f"**{search_term}**"
                    )
                    st.write(highlighted)
                    
                    mins = int(chunk['start_timestamp'] // 60)
                    secs = int(chunk['start_timestamp'] % 60)
                    
                    st.caption(
                        f"{mins:02d}:{secs:02d} | "
                        f"Chunk: {chunk['chunk_id'][:30]}..."
                    )
            
            if len(chunks) > 5:
                st.caption(f"... and {len(chunks) - 5} more matches")
