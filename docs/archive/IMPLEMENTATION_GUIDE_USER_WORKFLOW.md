# Implementation Guide: Transcript Access & Multi-Channel Understanding

## Part 1: Immediately Add Transcript Access (Week 1)

### 1.1 New Database View: Easy Transcript Retrieval

**Add to `src/storage/sqlite_store.py`:**

```python
class SQLiteStore:
    
    def get_full_transcript(self, video_id: str) -> dict:
        """Retrieve full transcript for a video."""
        video = self.get_video(video_id)
        if not video:
            return None
        
        chunks = self.execute("""
            SELECT chunk_id, chunk_index, raw_text, cleaned_text,
                   start_timestamp, end_timestamp, word_count
            FROM transcript_chunks
            WHERE video_id = ?
            ORDER BY chunk_index ASC
        """, (video_id,)).fetchall()
        
        # Reconstruct transcript
        full_raw = " ".join([c['raw_text'] for c in chunks])
        full_cleaned = " ".join([c['cleaned_text'] for c in chunks])
        
        return {
            "video_id": video_id,
            "title": video.title,
            "channel": self.get_channel(video.channel_id).name,
            "duration_seconds": video.duration_seconds,
            "upload_date": video.upload_date,
            "language": video.language_iso,
            "transcript_strategy": video.transcript_strategy,
            "full_raw_text": full_raw,
            "full_cleaned_text": full_cleaned,
            "chunks": chunks,
            "total_chunks": len(chunks)
        }
    
    def search_transcript(self, video_id: str, search_term: str) -> list[dict]:
        """Find occurrences of a term in a video's transcript."""
        results = self.execute("""
            SELECT chunk_id, chunk_index, cleaned_text, 
                   start_timestamp, end_timestamp
            FROM transcript_chunks
            WHERE video_id = ? 
              AND cleaned_text LIKE ?
            ORDER BY chunk_index ASC
        """, (video_id, f"%{search_term}%")).fetchall()
        
        return results
    
    def get_transcript_at_timestamp(self, video_id: str, seconds: float, 
                                     context_seconds: int = 30) -> dict:
        """Get transcript around a specific timestamp."""
        chunks = self.execute("""
            SELECT chunk_id, cleaned_text, start_timestamp, end_timestamp
            FROM transcript_chunks
            WHERE video_id = ?
              AND start_timestamp <= ? + ?
              AND end_timestamp >= ? - ?
            ORDER BY start_timestamp ASC
        """, (video_id, seconds, context_seconds, seconds, context_seconds)).fetchall()
        
        return {
            "target_timestamp": seconds,
            "context_seconds": context_seconds,
            "chunks": chunks
        }
    
    def compare_transcripts(self, video_ids: list[str]) -> dict:
        """Get transcripts for multiple videos for comparison."""
        transcripts = {}
        for vid in video_ids:
            transcripts[vid] = self.get_full_transcript(vid)
        return transcripts
```

---

### 1.2 New UI Page: Transcript Browser

**Create `src/ui/pages/transcript_viewer.py`:**

```python
"""
Transcript viewer for exploring raw data.

Features:
- View full transcript with search
- Jump to specific timestamp
- Compare multiple transcripts
- Export transcript as text/markdown
"""

import streamlit as st
from datetime import timedelta
from src.storage.sqlite_store import SQLiteStore
from src.config import get_settings


def render_transcript_viewer():
    """Main transcript viewer interface."""
    
    st.title("📜 Transcript Viewer")
    st.write("View and search raw transcripts without re-fetching from YouTube")
    
    db = SQLiteStore(get_settings()["sqlite"]["path"])
    
    # Navigation
    mode = st.radio("View Mode", ["Single Transcript", "Compare Multiple", "Search"])
    
    if mode == "Single Transcript":
        render_single_transcript(db)
    elif mode == "Compare Multiple":
        render_compare_transcripts(db)
    else:
        render_search_transcripts(db)


def render_single_transcript(db: SQLiteStore):
    """View a single transcript with search and navigation."""
    
    st.subheader("View Single Transcript")
    
    # Select video
    videos = db.execute("""
        SELECT v.video_id, v.title, c.name as channel, v.upload_date
        FROM videos v
        JOIN channels c ON v.channel_id = c.channel_id
        WHERE v.checkpoint_stage = 'DONE'
        ORDER BY v.upload_date DESC
        LIMIT 100
    """).fetchall()
    
    if not videos:
        st.warning("No processed videos found")
        return
    
    video_options = {
        f"{v['title'][:60]} ({v['channel']}, {v['upload_date']})": v['video_id']
        for v in videos
    }
    
    selected = st.selectbox("Select Video", video_options.keys())
    video_id = video_options[selected]
    
    # Fetch transcript
    transcript = db.get_full_transcript(video_id)
    
    if not transcript:
        st.error("Transcript not found")
        return
    
    # Metadata
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Channel", transcript['channel'])
    col2.metric("Duration", f"{transcript['duration_seconds'] // 60}m")
    col3.metric("Date", transcript['upload_date'])
    col4.metric("Chunks", transcript['total_chunks'])
    
    # Search within transcript
    st.subheader("Search")
    search_term = st.text_input("Search in this transcript")
    
    if search_term:
        results = db.search_transcript(video_id, search_term)
        st.write(f"Found {len(results)} matches:")
        
        for r in results:
            col1, col2 = st.columns([1, 5])
            
            with col1:
                mins = int(r['start_timestamp'] // 60)
                secs = int(r['start_timestamp'] % 60)
                st.write(f"**{mins:02d}:{secs:02d}**")
            
            with col2:
                # Highlight search term
                highlighted = r['cleaned_text'].replace(
                    search_term,
                    f"🔍 **{search_term}**"
                )
                st.write(highlighted)
                st.divider()
    
    # Timestamp jump
    st.subheader("Jump to Timestamp")
    
    col1, col2 = st.columns(2)
    with col1:
        minutes = st.number_input("Minutes", min_value=0)
    with col2:
        seconds = st.number_input("Seconds", min_value=0, max_value=59)
    
    timestamp = minutes * 60 + seconds
    
    if st.button("Jump to timestamp"):
        context = db.get_transcript_at_timestamp(video_id, timestamp, context_seconds=30)
        
        st.info(f"Around {minutes}:{seconds:02d}")
        for chunk in context['chunks']:
            st.write(chunk['cleaned_text'])
            st.caption(f"{chunk['chunk_id']} | "
                      f"{int(chunk['start_timestamp'])}s - "
                      f"{int(chunk['end_timestamp'])}s")
    
    # Full transcript viewer
    st.subheader("Full Transcript")
    
    view_type = st.radio("View", ["Cleaned (normalized)", "Raw (original)"])
    
    if view_type == "Cleaned (normalized)":
        text = transcript['full_cleaned_text']
    else:
        text = transcript['full_raw_text']
    
    st.text_area(
        "Transcript",
        value=text,
        height=400,
        disabled=True
    )
    
    # Export
    st.subheader("Export")
    
    export_format = st.radio("Format", ["Text", "Markdown"])
    
    if export_format == "Markdown":
        export_text = f"""# {transcript['title']}

**Channel:** {transcript['channel']}  
**Date:** {transcript['upload_date']}  
**Duration:** {transcript['duration_seconds'] // 60}m  
**Strategy:** {transcript['transcript_strategy']}  

## Transcript

{transcript['full_cleaned_text']}
"""
    else:
        export_text = transcript['full_cleaned_text']
    
    st.download_button(
        f"Download as {export_format}",
        export_text,
        f"transcript_{video_id}.{'md' if export_format == 'Markdown' else 'txt'}",
        "text/plain"
    )


def render_compare_transcripts(db: SQLiteStore):
    """View and compare multiple transcripts side-by-side."""
    
    st.subheader("Compare Multiple Transcripts")
    
    # Select videos
    videos = db.execute("""
        SELECT v.video_id, v.title, c.name as channel
        FROM videos v
        JOIN channels c ON v.channel_id = c.channel_id
        WHERE v.checkpoint_stage = 'DONE'
        ORDER BY v.upload_date DESC
        LIMIT 100
    """).fetchall()
    
    video_options = {
        f"{v['title'][:50]} ({v['channel']})": v['video_id']
        for v in videos
    }
    
    selected_ids = st.multiselect(
        "Select 2-3 videos to compare",
        video_options.keys()
    )
    
    if len(selected_ids) < 2:
        st.warning("Select at least 2 videos")
        return
    
    if len(selected_ids) > 3:
        st.warning("Select at most 3 videos")
        return
    
    video_ids = [video_options[sel] for sel in selected_ids]
    transcripts = db.compare_transcripts(video_ids)
    
    # Side-by-side view
    if len(selected_ids) == 2:
        col1, col2 = st.columns(2)
        
        with col1:
            t1 = transcripts[video_ids[0]]
            st.write(f"**{t1['title']}**")
            st.text_area(
                "Transcript 1",
                value=t1['full_cleaned_text'][:2000],
                height=400,
                disabled=True
            )
        
        with col2:
            t2 = transcripts[video_ids[1]]
            st.write(f"**{t2['title']}**")
            st.text_area(
                "Transcript 2",
                value=t2['full_cleaned_text'][:2000],
                height=400,
                disabled=True
            )
    
    else:  # 3 videos
        col1, col2, col3 = st.columns(3)
        
        for i, col in enumerate([col1, col2, col3]):
            with col:
                t = transcripts[video_ids[i]]
                st.write(f"**{t['title'][:40]}**")
                st.text_area(
                    f"Transcript {i+1}",
                    value=t['full_cleaned_text'][:1500],
                    height=300,
                    disabled=True
                )


def render_search_transcripts(db: SQLiteStore):
    """Global search across all transcripts."""
    
    st.subheader("Search All Transcripts")
    
    search_term = st.text_input("Search term (across all videos)")
    
    if not search_term:
        st.info("Enter a search term to find it across your vault")
        return
    
    # Search
    results = db.execute("""
        SELECT DISTINCT
            v.video_id,
            v.title,
            c.name as channel,
            COUNT(DISTINCT tc.chunk_id) as chunk_count,
            GROUP_CONCAT(tc.chunk_id, ', ') as chunks
        FROM transcript_chunks tc
        JOIN videos v ON tc.video_id = v.video_id
        JOIN channels c ON v.channel_id = c.channel_id
        WHERE tc.cleaned_text LIKE ?
        GROUP BY v.video_id
        ORDER BY v.upload_date DESC
    """, (f"%{search_term}%",)).fetchall()
    
    if not results:
        st.warning(f"No results for '{search_term}'")
        return
    
    st.success(f"Found in {len(results)} videos")
    
    for r in results:
        with st.expander(f"{r['title']} ({r['channel']})"):
            st.write(f"Found in {r['chunk_count']} chunks")
            
            # Show specific chunks with search term
            chunks = db.search_transcript(r['video_id'], search_term)
            
            for chunk in chunks[:3]:  # Show first 3 matches
                st.write(f"**{int(chunk['start_timestamp'])}s** - "
                        f"{int(chunk['end_timestamp'])}s")
                
                # Highlight search term
                text = chunk['cleaned_text']
                highlighted = text.replace(
                    search_term,
                    f"🔍 **{search_term}**"
                )
                st.write(highlighted)
                st.divider()
            
            if r['chunk_count'] > 3:
                st.caption(f"... and {r['chunk_count'] - 3} more matches")
```

---

### 1.3 Enhance RAG to Include Raw Transcripts

**Modify `src/intelligence/rag_engine.py`:**

```python
@dataclass
class RAGResponse:
    """Enhanced RAG response with raw data."""
    query: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: Optional[ConfidenceScore] = None
    
    # NEW FIELDS:
    raw_chunks: list[dict] = field(default_factory=list)
    full_transcripts: list[dict] = field(default_factory=list)
    verification_notes: str = ""
    
    total_chunks_retrieved: int = 0
    total_chunks_used: int = 0
    latency_ms: float = 0.0


class RAGEngine:
    
    def query(self, question: str, include_raw_data: bool = True) -> RAGResponse:
        """Enhanced query that optionally includes raw transcripts."""
        
        # ... existing RAG logic ...
        
        response = RAGResponse(
            query=question,
            answer=answer,
            citations=citations,
            confidence=confidence,
            total_chunks_retrieved=total_retrieved,
            total_chunks_used=len(citations),
            latency_ms=latency
        )
        
        # ADD: Raw data
        if include_raw_data:
            response.raw_chunks = self._enrich_citations_with_raw(citations)
            response.full_transcripts = self._get_full_transcripts_for_citations(citations)
            response.verification_notes = (
                f"Raw data available for {len(citations)} sources. "
                f"Verify answer by reviewing raw transcripts."
            )
        
        return response
    
    def _enrich_citations_with_raw(self, citations: list[Citation]) -> list[dict]:
        """Add raw transcript text to each citation."""
        rich_data = []
        for c in citations:
            chunk = self.db.execute("""
                SELECT raw_text, cleaned_text, chunk_id
                FROM transcript_chunks
                WHERE chunk_id = ?
            """, (c.chunk_id,)).fetchone()
            
            if chunk:
                rich_data.append({
                    "chunk_id": c.chunk_id,
                    "video_id": c.video_id,
                    "video_title": c.video_title,
                    "channel": c.channel_name,
                    "timestamp": c.timestamp_str,
                    "youtube_link": c.youtube_link,
                    "raw_text": chunk['raw_text'],
                    "cleaned_text": chunk['cleaned_text'],
                    "relevance_reason": "Matched query semantically"
                })
        
        return rich_data
    
    def _get_full_transcripts_for_citations(self, citations: list[Citation]) -> list[dict]:
        """Get full transcripts for cited videos."""
        video_ids = set(c.video_id for c in citations)
        full_transcripts = []
        
        for vid in video_ids:
            transcript = self.db.get_full_transcript(vid)
            if transcript:
                full_transcripts.append({
                    "video_id": vid,
                    "title": transcript['title'],
                    "channel": transcript['channel'],
                    "duration": f"{transcript['duration_seconds'] // 60}m",
                    "full_text": transcript['full_cleaned_text'],
                    "access_via": f"Transcript Viewer > {vid}"
                })
        
        return full_transcripts
```

---

### 1.4 Update Streamlit UI to Show Raw Data

**Modify `src/ui/pages/research.py` (Research Console):**

```python
def render_research_console():
    """Enhanced research console with raw transcript access."""
    
    st.title("🔬 Research Console")
    
    # Query input
    query = st.text_area("Research Question", height=100)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        include_raw = st.checkbox("Show raw transcripts", value=True)
    with col2:
        deep_dive = st.checkbox("Include all chunks (not just top 8)")
    with col3:
        show_reasoning = st.checkbox("Show extraction reasoning")
    
    if st.button("Search"):
        with st.spinner("Querying..."):
            response = rag.query(query, include_raw_data=include_raw)
        
        # LEVEL 1: Synthesis
        st.subheader("Answer")
        st.write(response.answer)
        
        if response.confidence:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Overall Confidence", f"{response.confidence.overall:.0%}")
            col2.metric("Source Diversity", f"{response.confidence.source_diversity:.0%}")
            col3.metric("Chunk Relevance", f"{response.confidence.chunk_relevance:.0%}")
            col4.metric("Coverage", f"{response.confidence.coverage:.0%}")
        
        # LEVEL 2: Sources (citations)
        st.subheader("Sources")
        
        for citation in response.citations:
            col1, col2 = st.columns([1, 20])
            
            with col1:
                st.write(citation.source_id)
            
            with col2:
                st.write(f"**{citation.video_title}**")
                st.write(f"Channel: {citation.channel_name} | "
                        f"Time: {citation.timestamp_str}")
                st.link_button("Open on YouTube", citation.youtube_link)
                
                with st.expander("View excerpt"):
                    st.text(citation.text_excerpt)
        
        # LEVEL 3: Raw chunks
        if include_raw:
            st.subheader("Raw Source Data")
            
            for i, raw in enumerate(response.raw_chunks):
                with st.expander(f"{raw['chunk_id']} ({raw['channel']}) [{raw['timestamp']}]"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Cleaned:**")
                        st.text(raw['cleaned_text'][:500])
                    
                    with col2:
                        st.write("**Raw (original filler):**")
                        st.text(raw['raw_text'][:500])
        
        # LEVEL 4: Full transcripts
        if response.full_transcripts:
            st.subheader("Full Transcripts (Reference)")
            
            for transcript in response.full_transcripts:
                with st.expander(f"Full: {transcript['title']} ({transcript['duration']})"):
                    st.text_area(
                        "Full transcript",
                        value=transcript['full_text'][:2000],
                        height=300,
                        disabled=True
                    )
                    
                    st.caption(f"Access via: Transcript Viewer ({transcript['video_id']})")
        
        # Export
        st.subheader("Export")
        
        export_md = f"""# Research: {query}

## Answer

{response.answer}

### Confidence

- Overall: {response.confidence.overall:.0%}
- Source Diversity: {response.confidence.source_diversity:.0%}
- Chunk Relevance: {response.confidence.chunk_relevance:.0%}
- Coverage: {response.confidence.coverage:.0%}

## Sources

"""
        
        for citation in response.citations:
            export_md += f"""
### {citation.source_id}: {citation.video_title}

- **Channel:** {citation.channel_name}
- **Time:** {citation.timestamp_str}
- **Video:** {citation.youtube_link}

**Excerpt:**
```
{citation.text_excerpt}
```

"""
        
        st.download_button(
            "Download Research as Markdown",
            export_md,
            "research.md",
            "text/markdown"
        )
```

---

## Part 2: Add Framework Comparison (Week 2-3)

This enables answering "Why do channels disagree?"

### 2.1 Framework Extraction

**Create `src/intelligence/framework_extractor.py`:**

```python
"""
Extract implicit frameworks and worldviews from transcripts.
"""

import json
import ollama
from dataclasses import dataclass
from src.config import get_settings, load_prompt


@dataclass
class Framework:
    speaker: str
    domain: str
    core_belief: str
    assumptions: list[str]
    value_hierarchy: list[str]
    risk_orientation: str  # 'cautious', 'balanced', 'optimistic'
    confidence: float
    supporting_evidence: list[str]


class FrameworkExtractor:
    """Extract guest's implicit framework from interviews."""
    
    def __init__(self, db):
        self.db = db
        self.ollama_cfg = get_settings()["ollama"]
    
    def extract_framework(self, speaker: str, topic: str) -> Framework:
        """Extract speaker's framework on a topic from all their videos."""
        
        # Get all statements by this speaker on this topic
        claims = self.db.execute("""
            SELECT c.claim_text, c.claim_type, v.title, v.upload_date
            FROM claims c
            JOIN videos v ON c.video_id = v.video_id
            WHERE c.speaker = ? AND c.topic = ?
            ORDER BY v.upload_date DESC
            LIMIT 20
        """, (speaker, topic)).fetchall()
        
        if not claims:
            return None
        
        # Construct prompt with their statements
        prompt = self._build_extraction_prompt(speaker, topic, claims)
        
        # Call LLM
        response = ollama.chat(
            model=self.ollama_cfg["deep_model"],
            messages=[
                {"role": "user", "content": prompt}
            ],
            options={"num_predict": 1000, "temperature": 0.1}
        )
        
        # Parse response
        framework_data = self._parse_framework_response(response)
        
        return Framework(
            speaker=speaker,
            domain=topic,
            **framework_data
        )
    
    def _build_extraction_prompt(self, speaker: str, topic: str, claims: list) -> str:
        """Build prompt for framework extraction."""
        
        claims_text = "\n".join([
            f"- [{c['upload_date']}] {c['claim_text']}"
            for c in claims
        ])
        
        return f"""
Analyze {speaker}'s implicit framework on {topic}.

Their statements:
{claims_text}

Extract:
1. Core belief: One sentence summarizing their fundamental worldview
2. Key assumptions: 3-5 unstated assumptions driving their views
3. Value hierarchy: What matters most to them? Order: [1st, 2nd, 3rd]
4. Risk orientation: Are they optimistic, cautious, or balanced?
5. Supporting evidence: What validates their framework?

Return as JSON:
{{
  "core_belief": "...",
  "assumptions": ["...", "..."],
  "value_hierarchy": ["...", "..."],
  "risk_orientation": "optimistic|cautious|balanced",
  "supporting_evidence": ["...", "..."],
  "confidence": 0.8
}}
"""
    
    def _parse_framework_response(self, response) -> dict:
        """Parse LLM response into framework data."""
        try:
            text = response["message"]["content"]
            
            # Extract JSON
            import re
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return {
            "core_belief": "",
            "assumptions": [],
            "value_hierarchy": [],
            "risk_orientation": "balanced",
            "supporting_evidence": [],
            "confidence": 0.0
        }
    
    def compare_frameworks(self, speakers: list[str], topic: str) -> dict:
        """Compare frameworks of multiple speakers on a topic."""
        
        frameworks = {}
        for speaker in speakers:
            framework = self.extract_framework(speaker, topic)
            if framework:
                frameworks[speaker] = framework
        
        # Compare
        comparison = {
            "topic": topic,
            "frameworks": frameworks,
            "key_differences": self._identify_differences(frameworks),
            "areas_of_agreement": self._identify_agreement(frameworks)
        }
        
        return comparison
    
    def _identify_differences(self, frameworks: dict) -> list[str]:
        """Identify where frameworks differ."""
        if len(frameworks) < 2:
            return []
        
        speakers = list(frameworks.keys())
        fw1 = frameworks[speakers[0]]
        fw2 = frameworks[speakers[1]]
        
        differences = []
        
        # Compare assumptions
        unique_to_1 = set(fw1.assumptions) - set(fw2.assumptions)
        unique_to_2 = set(fw2.assumptions) - set(fw1.assumptions)
        
        if unique_to_1:
            differences.append(
                f"{speakers[0]} assumes: {', '.join(unique_to_1)}"
            )
        if unique_to_2:
            differences.append(
                f"{speakers[1]} assumes: {', '.join(unique_to_2)}"
            )
        
        # Compare risk orientation
        if fw1.risk_orientation != fw2.risk_orientation:
            differences.append(
                f"{speakers[0]} is {fw1.risk_orientation}, "
                f"{speakers[1]} is {fw2.risk_orientation}"
            )
        
        # Compare core beliefs
        if fw1.core_belief != fw2.core_belief:
            differences.append(
                f"Core belief differs:\n"
                f"  {speakers[0]}: {fw1.core_belief}\n"
                f"  {speakers[1]}: {fw2.core_belief}"
            )
        
        return differences
    
    def _identify_agreement(self, frameworks: dict) -> list[str]:
        """Find areas where frameworks agree."""
        if len(frameworks) < 2:
            return []
        
        frameworks_list = list(frameworks.values())
        agreements = []
        
        # Find common assumptions
        common_assumptions = set(frameworks_list[0].assumptions)
        for fw in frameworks_list[1:]:
            common_assumptions &= set(fw.assumptions)
        
        if common_assumptions:
            agreements.append(
                f"Shared assumptions: {', '.join(common_assumptions)}"
            )
        
        return agreements
```

### 2.2 Framework Comparison UI

**Create `src/ui/pages/framework_comparison.py`:**

```python
"""
Compare how different guests understand a topic.
"""

import streamlit as st
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.framework_extractor import FrameworkExtractor
from src.config import get_settings


def render_framework_comparison():
    """Compare frameworks on a specific topic."""
    
    st.title("🧠 Framework Comparison")
    st.write("Understand *why* different guests disagree by examining their underlying worldviews")
    
    db = SQLiteStore(get_settings()["sqlite"]["path"])
    extractor = FrameworkExtractor(db)
    
    # Select topic
    topics = db.execute("""
        SELECT DISTINCT topic FROM claims WHERE topic IS NOT NULL
        ORDER BY topic
    """).fetchall()
    
    topic_names = [t['topic'] for t in topics if t['topic']]
    
    if not topic_names:
        st.warning("No topics found in vault")
        return
    
    topic = st.selectbox("Select Topic", topic_names)
    
    # Get speakers on this topic
    speakers = db.execute("""
        SELECT DISTINCT speaker FROM claims WHERE topic = ? AND speaker IS NOT NULL
        ORDER BY speaker
    """, (topic,)).fetchall()
    
    speaker_names = [s['speaker'] for s in speakers]
    
    if not speaker_names:
        st.warning(f"No speakers found for topic '{topic}'")
        return
    
    # Select speakers to compare
    selected_speakers = st.multiselect(
        "Select 2-3 speakers to compare",
        speaker_names,
        default=speaker_names[:2]
    )
    
    if len(selected_speakers) < 2:
        st.warning("Select at least 2 speakers")
        return
    
    if len(selected_speakers) > 3:
        st.warning("Select at most 3 speakers")
        return
    
    if st.button("Compare Frameworks"):
        with st.spinner("Extracting and analyzing frameworks..."):
            comparison = extractor.compare_frameworks(selected_speakers, topic)
        
        # Display comparison
        st.subheader(f"Framework Comparison: {topic}")
        
        # Individual frameworks
        st.subheader("Individual Frameworks")
        
        cols = st.columns(len(selected_speakers))
        
        for i, (speaker, fw) in enumerate(comparison['frameworks'].items()):
            with cols[i]:
                st.write(f"### {speaker}")
                
                st.write(f"**Core Belief:**\n{fw.core_belief}")
                
                st.write(f"**Risk Orientation:** {fw.risk_orientation.capitalize()}")
                
                st.write("**Key Assumptions:**")
                for assumption in fw.assumptions:
                    st.write(f"- {assumption}")
                
                st.write("**Value Hierarchy:**")
                for i, value in enumerate(fw.value_hierarchy, 1):
                    st.write(f"{i}. {value}")
        
        # Key differences
        if comparison['key_differences']:
            st.subheader("Key Differences")
            
            for diff in comparison['key_differences']:
                st.write(f"• {diff}")
        
        # Areas of agreement
        if comparison['areas_of_agreement']:
            st.subheader("Areas of Agreement")
            
            for agreement in comparison['areas_of_agreement']:
                st.write(f" {agreement}")
        
        # Quotes supporting frameworks
        st.subheader("Supporting Evidence")
        
        for speaker in selected_speakers:
            with st.expander(f"{speaker}'s quotes on this topic"):
                quotes = db.execute("""
                    SELECT quote_text, v.title, v.upload_date
                    FROM quotes q
                    JOIN videos v ON q.video_id = v.video_id
                    WHERE q.speaker = ? AND q.topic = ?
                    ORDER BY v.upload_date DESC
                    LIMIT 5
                """, (speaker, topic)).fetchall()
                
                for q in quotes:
                    st.write(f"> {q['quote_text']}")
                    st.caption(f"{q['title']} ({q['upload_date']})")
                    st.divider()
```

---

## Quick Implementation Checklist

**Week 1: Transcript Access**
- [ ] Add database methods (get_full_transcript, search_transcript, etc.)
- [ ] Create transcript_viewer.py UI page
- [ ] Enhance RAG response with raw data
- [ ] Update research console UI

**Week 2: Framework Understanding**
- [ ] Create framework_extractor.py
- [ ] Add framework storage to database
- [ ] Create framework_comparison.py UI page
- [ ] Test with 5 real speakers on 3 topics

**Week 3: Refinement**
- [ ] Test end-to-end workflow
- [ ] Optimize query performance
- [ ] Gather feedback on understanding quality

---

**This gives you exactly what you asked for:**
1.  Go through information (transcript browser)
2.  Talk with LLM (enhanced RAG with context)
3.  Understand topics across channels (framework comparison)
4.  All data accessible without re-fetch (transcript viewer + full access)
