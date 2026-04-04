# Implementation Roadmap: From Analysis to Action

## Phase 0: This Week (Baseline Improvements)

### Task 0.1: Add Claim Certainty Markers

**File:** `src/intelligence/chunk_analyzer.py`

**Change:**
```python
# In _extract_claims() method, enhance LLM prompt:

CLAIM_EXTRACTION_PROMPT = """
Extract factual claims AND their certainty markers.

For each claim, identify:
1. The claim text (what is asserted)
2. Certainty level:
   - "fact": Presented as established fact
   - "high_conf": "Research shows...", "Data indicates..."
   - "provisional": "It seems...", "Evidence suggests..."
   - "speculative": "I think...", "Probably...", "Might be..."
   - "prediction": Time-bound forecast ("by 2030", "soon")

Return JSON array with BOTH fields.
"""

# Add to storage model:
@dataclass
class Claim:
    claim_text: str
    certainty_level: str  # 👈 NEW FIELD
    confidence: float     # (LLM confidence in extraction)
```

**Database Migration:**
```sql
ALTER TABLE claims ADD COLUMN certainty_level TEXT DEFAULT 'provisional';
CREATE INDEX idx_claims_certainty ON claims(certainty_level);
```

**Test:** 
- Extract 10 claims, verify certainty markers are assigned
- Query: `SELECT * FROM claims WHERE certainty_level = 'prediction'` should return forecasts

---

### Task 0.2: Build Guest Conflict Matrix

**File:** `src/storage/sqlite_store.py`

**Add Methods:**
```python
class SQLiteStore:
    def record_guest_conflict(self, guest_a: str, guest_b: str, topic: str):
        """Record when two guests express opposing views."""
        self.execute("""
            INSERT INTO guest_conflict_matrix 
                (guest_a, guest_b, topic, conflict_count, conflict_rate)
            VALUES (?, ?, ?, 1, 0)
            ON CONFLICT (guest_a, guest_b, topic) DO UPDATE SET
                conflict_count = conflict_count + 1
        """, (guest_a, guest_b, topic))
        self.commit()
    
    def get_guest_conflicts(self, topic: str = "") -> list[dict]:
        """Get all recorded conflicts, optionally filtered by topic."""
        query = "SELECT * FROM guest_conflict_matrix"
        params = []
        if topic:
            query += " WHERE topic = ?"
            params.append(topic)
        query += " ORDER BY conflict_count DESC"
        
        rows = self.execute(query, params).fetchall()
        return [dict(r) for r in rows]
```

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS guest_conflict_matrix (
    conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_a TEXT NOT NULL,
    guest_b TEXT NOT NULL,
    topic TEXT NOT NULL,
    conflict_count INTEGER DEFAULT 1,
    total_interactions INTEGER DEFAULT 1,
    conflict_rate REAL DEFAULT 0.0,
    first_noted DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_noted DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guest_a, guest_b, topic)
);
```

**Test:**
- Manually call `record_guest_conflict("Elon Musk", "Yann LeCun", "AI Safety")`
- Query should return the recorded conflict

---

### Task 0.3: Transcript Quality Scoring

**File:** `src/ingestion/refinement.py`

**Add Metrics:**
```python
@dataclass
class TranscriptQuality:
    raw_word_count: int
    cleaned_word_count: int
    filler_removal_pct: float
    sponsor_removal_pct: float
    sponsor_removal_minutes: float
    transcript_strategy: str  # 'manual_en', 'auto_en', etc.
    estimated_quality: str  # 'pristine', 'good', 'fair', 'poor'

def score_transcript_quality(
    raw_text: str,
    cleaned_text: str,
    sponsor_segments: list[SponsorSegment],
    transcript_strategy: str,
    duration_seconds: int
) -> TranscriptQuality:
    """Score overall quality of transcript after refinement."""
    raw_words = len(raw_text.split())
    cleaned_words = len(cleaned_text.split())
    
    filler_pct = (raw_words - cleaned_words) / raw_words * 100
    sponsor_time = sum((s.end - s.start) for s in sponsor_segments)
    sponsor_pct = (sponsor_time / duration_seconds) * 100
    
    # Determine quality tier
    if filler_pct < 5 and sponsor_pct < 5:
        quality = "pristine"
    elif filler_pct < 15 and sponsor_pct < 15:
        quality = "good"
    elif filler_pct < 30 and sponsor_pct < 30:
        quality = "fair"
    else:
        quality = "poor"
    
    return TranscriptQuality(
        raw_word_count=raw_words,
        cleaned_word_count=cleaned_words,
        filler_removal_pct=filler_pct,
        sponsor_removal_pct=sponsor_pct,
        sponsor_removal_minutes=sponsor_time / 60,
        transcript_strategy=transcript_strategy,
        estimated_quality=quality
    )
```

**Database Update:**
```sql
ALTER TABLE videos ADD COLUMN quality_score_json TEXT DEFAULT '{}';

-- Track quality metrics
CREATE TABLE video_quality_metrics (
    video_id TEXT PRIMARY KEY REFERENCES videos(video_id),
    raw_word_count INTEGER,
    cleaned_word_count INTEGER,
    filler_removal_pct REAL,
    sponsor_removal_pct REAL,
    transcript_strategy TEXT,
    quality_tier TEXT,  -- 'pristine', 'good', 'fair', 'poor'
    calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Test:**
- Process a video, check quality metrics are stored
- Query: `SELECT * FROM video_quality_metrics WHERE quality_tier = 'pristine'`

---

### Task 0.4: Prediction Tracker

**File:** `src/intelligence/chunk_analyzer.py`

**Add Extraction:**
```python
def extract_predictions(self, text: str, chunk: TranscriptChunk) -> list[dict]:
    """Extract time-bound predictions for later verification."""
    
    PREDICTION_PROMPT = """
    Extract explicit time-bound predictions from this text.
    
    For each prediction, identify:
    1. The prediction text
    2. Target date (when it's supposed to happen)
    3. Speaker belief (certainty: high/medium/low)
    4. Domain (AI, energy, technology, etc.)
    
    Example inputs:
    - "AGI will exist by 2030"
    - "We'll have fusion power plants within 5 years"
    
    Return as JSON array of predictions.
    """
    
    return self._call_llm_json_list(
        self.deep_model,
        PREDICTION_PROMPT,
        text[:3000],
        "prediction"
    )
```

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT REFERENCES videos(video_id),
    chunk_id TEXT REFERENCES transcript_chunks(chunk_id),
    speaker TEXT,
    prediction_text TEXT,
    domain TEXT,  -- 'AI', 'energy', 'medicine', etc.
    target_date DATE,
    speaker_confidence: 'high' | 'medium' | 'low',
    extracted_at DATETIME,
    verified_date DATE,
    verification_status: 'unverified' | 'verified_correct' | 'verified_wrong' DEFAULT 'unverified',
    verification_notes TEXT
);
```

**Storage Method:**
```python
def insert_prediction(self, pred: dict, video_id: str, chunk_id: str):
    """Store a prediction for later verification."""
    self.execute("""
        INSERT INTO predictions 
            (video_id, chunk_id, speaker, prediction_text, domain, 
             target_date, speaker_confidence, extracted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        video_id, chunk_id, pred.get('speaker', ''),
        pred.get('prediction', ''), pred.get('domain', 'general'),
        pred.get('target_date'), pred.get('confidence', 'medium')
    ))
    self.commit()
```

**Test:**
- Extract predictions from video
- Manually verify one prediction
- Query accuracy: `SELECT COUNT(*) FILTER (WHERE verification_status = 'verified_correct') / COUNT(*) as accuracy FROM predictions`

---

## Phase 1: Week 1-2 (Enhanced Extraction)

### Task 1.1: Evidence Extraction Module

**New File:** `src/intelligence/evidence_extractor.py`

```python
"""
Evidence extraction for claims.

Identifies and extracts:
- Study citations ("Research from MIT showed...")
- Personal experience ("In my 10 years in the industry...")
- Reasoning chains ("Because A and B imply C...")
- Authority references ("According to Yann, ...")
- Data points ("The statistic is 72%...")
"""

import json
import re
import ollama
from dataclasses import dataclass
from src.config import get_settings, load_prompt


@dataclass
class Evidence:
    evidence_type: str  # 'study', 'personal_exp', 'authority', 'reasoning', 'data'
    text: str
    specificity: str    # 'vague', 'general', 'specific', 'quantified'
    source_citation: str  # "According to...", "I read that..."
    confidence: float   # How sure is this evidence signal


class EvidenceExtractor:
    """Extracts evidence references from transcript chunks."""
    
    def __init__(self):
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self.evidence_prompt = load_prompt("evidence_extractor")
    
    def extract_evidence(self, text: str) -> list[Evidence]:
        """Extract evidence statements from a transcript chunk."""
        
        # Pattern-based pre-filtering
        pattern_evidence = self._pattern_match_evidence(text)
        
        # LLM-based comprehensive extraction
        llm_evidence = self._llm_extract_evidence(text)
        
        # Merge and deduplicate
        all_evidence = self._deduplicate_evidence(pattern_evidence + llm_evidence)
        
        return all_evidence
    
    def _pattern_match_evidence(self, text: str) -> list[Evidence]:
        """Quick regex-based evidence detection."""
        evidence = []
        
        # Study patterns
        study_pattern = r'study|research|paper|publication|research shows|study found'
        if re.search(study_pattern, text, re.IGNORECASE):
            # Extract sentence containing pattern
            sentence = self._extract_sentence_with_pattern(text, study_pattern)
            evidence.append(Evidence(
                evidence_type='study',
                text=sentence,
                specificity='general',
                source_citation='study',
                confidence=0.6
            ))
        
        # Personal experience patterns
        exp_pattern = r"in my|my experience|I observed|I found|I saw|based on|during my|working in"
        if re.search(exp_pattern, text, re.IGNORECASE):
            sentence = self._extract_sentence_with_pattern(text, exp_pattern)
            evidence.append(Evidence(
                evidence_type='personal_exp',
                text=sentence,
                specificity='specific',
                source_citation='personal experience',
                confidence=0.7
            ))
        
        # Data patterns (numbers, percentages)
        data_pattern = r'(\d+\.?\d*%|$\d+(?:,\d{3})*|[\d,]+ percent)'
        if re.search(data_pattern, text):
            match = re.search(data_pattern, text)
            sentence = self._extract_sentence_with_pattern(text, re.escape(match.group()))
            evidence.append(Evidence(
                evidence_type='data',
                text=sentence,
                specificity='quantified',
                source_citation='statistic',
                confidence=0.5
            ))
        
        return evidence
    
    def _llm_extract_evidence(self, text: str) -> list[Evidence]:
        """Use LLM for comprehensive evidence extraction."""
        try:
            response = ollama.chat(
                model=self.ollama_cfg["deep_model"],
                messages=[
                    {"role": "system", "content": self.evidence_prompt},
                    {"role": "user", "content": text[:3000]},
                ],
                options={"num_predict": 500, "temperature": 0.1}
            )
            
            raw = response["message"]["content"].strip()
            evidence_list = self._parse_evidence_json(raw)
            return evidence_list
            
        except Exception as e:
            print(f"Evidence extraction failed: {e}")
            return []
    
    def _parse_evidence_json(self, raw: str) -> list[Evidence]:
        """Parse LLM evidence JSON response."""
        try:
            # Clean markdown
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0].strip()
            
            data = json.loads(clean)
            if not isinstance(data, list):
                return []
            
            evidence = []
            for item in data:
                if isinstance(item, dict):
                    evidence.append(Evidence(
                        evidence_type=item.get('type', 'other'),
                        text=item.get('text', ''),
                        specificity=item.get('specificity', 'general'),
                        source_citation=item.get('source', ''),
                        confidence=item.get('confidence', 0.5)
                    ))
            return evidence
            
        except json.JSONDecodeError:
            return []
    
    def _extract_sentence_with_pattern(self, text: str, pattern: str) -> str:
        """Extract the sentence containing the pattern."""
        sentences = text.split('.')
        for sent in sentences:
            if re.search(pattern, sent, re.IGNORECASE):
                return sent.strip() + "."
        return ""
    
    def _deduplicate_evidence(self, evidence_list: list[Evidence]) -> list[Evidence]:
        """Remove near-duplicate evidence."""
        unique = {}
        for e in evidence_list:
            key = (e.evidence_type, e.text[:50])  # Hash on type + first 50 chars
            if key not in unique or e.confidence > unique[key].confidence:
                unique[key] = e
        return list(unique.values())
```

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER REFERENCES claims(claim_id),
    video_id TEXT,
    chunk_id TEXT REFERENCES transcript_chunks(chunk_id),
    evidence_type TEXT,  -- 'study', 'personal_exp', 'authority', 'reasoning', 'data'
    text TEXT,
    source_citation TEXT,  -- "According to...", "My research showed..."
    specificity TEXT,  -- 'vague', 'general', 'specific', 'quantified'
    supporting_degree REAL,  -- 0.0-1.0, how much it supports the claim
    confidence REAL,   -- Model confidence in extraction
    extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_evidence_claim ON evidence(claim_id);
CREATE INDEX idx_evidence_type ON evidence(evidence_type);
```

**Integration Point:**
```python
# In chunk_analyzer.py, add to _analyze_single_chunk():

from src.intelligence.evidence_extractor import EvidenceExtractor

evidence_extractor = EvidenceExtractor()

# After extracting claims:
for claim in claims:
    evidence = evidence_extractor.extract_evidence(text)
    for e in evidence:
        db.insert_evidence(
            claim_id=claim['claim_id'],
            evidence=e
        )
```

---

### Task 1.2: Claim Relationship Schema

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS claim_relationships (
    relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_claim_id INTEGER REFERENCES claims(claim_id),
    to_claim_id INTEGER REFERENCES claims(claim_id),
    relationship_type TEXT,  -- 'supports', 'contradicts', 'refines', 'complicates', 'assumes'
    relationship_strength REAL,  -- 0.0-1.0
    reasoning TEXT,  -- Why this relationship exists
    detected_by TEXT,  -- 'manual', 'llm', 'pattern'
    created_at DATETIME
);

CREATE INDEX idx_relationship_from ON claim_relationships(from_claim_id);
CREATE INDEX idx_relationship_to ON claim_relationships(to_claim_id);
```

**Relationship Detector:**
```python
# In src/intelligence/claim_relationships.py

def detect_claim_relationships(db: SQLiteStore) -> dict:
    """Detect relationships between all claims in vault."""
    
    claims = db.get_all_claims()
    relationships = []
    
    for i, claim_a in enumerate(claims):
        for claim_b in claims[i+1:]:
            rel = detect_single_relationship(claim_a, claim_b)
            if rel:
                relationships.append(rel)
                db.insert_claim_relationship(rel)
    
    return {"total_detected": len(relationships)}


def detect_single_relationship(claim_a: dict, claim_b: dict) -> dict:
    """Detect if claim_b contradicts/supports/relates to claim_a."""
    
    # Logical contradiction detection
    if is_contradictory(claim_a['text'], claim_b['text']):
        return {
            'from_claim': claim_a['id'],
            'to_claim': claim_b['id'],
            'type': 'contradicts',
            'strength': 0.8
        }
    
    # Semantic support detection
    if is_supporting(claim_a['text'], claim_b['text']):
        return {
            'from_claim': claim_a['id'],
            'to_claim': claim_b['id'],
            'type': 'supports',
            'strength': 0.7
        }
    
    return None
```

---

## Phase 2: Week 3-4 (Analysis & Quality)

### Task 2.1: Contradiction Detection Engine

**New File:** `src/intelligence/contradiction_detector.py`

```python
"""
Detects logical contradictions between claims.
"""

import ollama
from sklearn.cluster import DBSCAN
import numpy as np
from src.storage.vector_store import VectorStore


class ContradictionDetector:
    """Identifies contradictory positions and consensus groups."""
    
    def __init__(self, db, vector_store: VectorStore):
        self.db = db
        self.vector_store = vector_store
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
    
    def find_contradictions(self, topic: str = None) -> list[dict]:
        """Find all contradictions, optionally filtered by topic."""
        
        # Get all claims relevant to topic
        if topic:
            claims = self.db.get_claims_by_topic(topic)
        else:
            claims = self.db.get_all_claims()
        
        # Embed claims
        claim_vectors = []
        for claim in claims:
            vec = self.vector_store.embed_text(claim['text'])
            claim_vectors.append((claim['id'], vec))
        
        # Cluster by semantic similarity
        vectors_array = np.array([v[1] for v in claim_vectors])
        clustering = DBSCAN(eps=0.1, min_samples=2).fit(vectors_array)
        
        # Find contradictions within high-similarity clusters
        contradictions = []
        for cluster_id in set(clustering.labels_):
            if cluster_id == -1:  # noise
                continue
            
            cluster_claims = [
                claims[i] for i, c_id in enumerate(clustering.labels_)
                if c_id == cluster_id
            ]
            
            # Check pairs within cluster
            for i, claim_a in enumerate(cluster_claims):
                for claim_b in cluster_claims[i+1:]:
                    if self._is_contradictory(claim_a, claim_b):
                        contradictions.append({
                            'claim_a': claim_a,
                            'claim_b': claim_b,
                            'contradiction_type': self._classify_contradiction(claim_a, claim_b)
                        })
        
        return contradictions
    
    def _is_contradictory(self, claim_a: dict, claim_b: dict) -> bool:
        """Check if two claims are logically contradictory."""
        
        # Pattern matching for obvious contradictions
        negation_patterns = [
            ("will happen", "won't happen"),
            ("is true", "is false"),
            ("necessary", "unnecessary"),
            ("beneficial", "harmful"),
        ]
        
        text_a = claim_a['text'].lower()
        text_b = claim_b['text'].lower()
        
        for pattern_pos, pattern_neg in negation_patterns:
            if pattern_pos in text_a and pattern_neg in text_b:
                return True
            if pattern_neg in text_a and pattern_pos in text_b:
                return True
        
        # LLM-based detection for subtle contradictions
        return self._llm_check_contradiction(claim_a, claim_b)
    
    def _llm_check_contradiction(self, claim_a: dict, claim_b: dict) -> bool:
        """Use LLM to detect subtle contradictions."""
        prompt = f"""
Are these two statements contradictory?

Statement A: "{claim_a['text']}"
Speaker A: {claim_a['speaker']}

Statement B: "{claim_b['text']}"
Speaker B: {claim_b['speaker']}

Respond with JSON:
{{"contradictory": true/false, "reasoning": "..."}}
"""
        try:
            response = ollama.chat(
                model=self.ollama_cfg.get("deep_model"),
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": 100, "temperature": 0.1}
            )
            result = json.loads(response["message"]["content"])
            return result.get("contradictory", False)
        except:
            return False
    
    def _classify_contradiction(self, claim_a: dict, claim_b: dict) -> str:
        """Classify the type of contradiction."""
        # Logical vs empirical vs value-based
        if any(kw in claim_a['text'].lower() for kw in ["should", "must", "ought"]):
            return "value_judgment"
        if any(kw in claim_a['text'].lower() for kw in ["will", "must", "inevitable"]):
            return "prediction"
        return "factual"
    
    def calculate_consensus(self, topic: str) -> dict:
        """Calculate consensus on a topic."""
        claims = self.db.get_claims_by_topic(topic)
        
        # Cluster by semantic similarity
        # Find majority view
        # Calculate agreement percentage
        
        return {
            "topic": topic,
            "total_claims": len(claims),
            "consensus_view": "...",
            "consensus_percentage": 0.75,
            "dissenting_views": []
        }
```

---

### Task 2.2: Quality Metrics Dashboard Page

**New File:** `src/ui/pages/quality_analytics.py`

```python
"""
Data quality analytics dashboard.

Shows extraction completeness, claim quality, knowledge depth,
and other metrics that indicate how useful the vault is.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from src.storage.sqlite_store import SQLiteStore
from src.config import get_settings


def render_quality_analytics():
    """Render the quality metrics dashboard."""
    
    st.title("📊 Data Quality Analytics")
    
    db = SQLiteStore(get_settings()["sqlite"]["path"])
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Extraction Quality",
        "Knowledge Depth",
        "Cross-Video Patterns",
        "Trends"
    ])
    
    with tab1:
        render_extraction_quality(db)
    
    with tab2:
        render_knowledge_depth(db)
    
    with tab3:
        render_patterns(db)
    
    with tab4:
        render_trends(db)


def render_extraction_quality(db):
    """Extraction quality metrics."""
    st.subheader("Extraction Completeness")
    
    stats = db.execute("""
        SELECT
            COUNT(*) as total_videos,
            SUM(CASE WHEN checkpoint_stage = 'DONE' THEN 1 ELSE 0 END) as processed,
            COUNT(DISTINCT video_id) as with_claims,
            AVG(claim_confidence) as avg_claim_confidence
        FROM videos v
        LEFT JOIN claims c ON v.video_id = c.video_id
    """).fetchone()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Videos", stats['total_videos'])
    col2.metric("Processed", stats['processed'])
    col3.metric("With Claims", stats['with_claims'])
    col4.metric("Avg Confidence", f"{stats['avg_claim_confidence']:.2f}")
    
    # Claim certainty distribution
    certainty = db.execute("""
        SELECT certainty_level, COUNT(*) as count
        FROM claims
        GROUP BY certainty_level
        ORDER BY count DESC
    """).fetchall()
    
    cert_df = pd.DataFrame(certainty, columns=['Certainty', 'Count'])
    st.bar_chart(cert_df.set_index('Certainty'))


def render_knowledge_depth(db):
    """Knowledge depth metrics."""
    st.subheader("Knowledge Depth")
    
    # Claims with evidence
    evidence_stats = db.execute("""
        SELECT
            COUNT(DISTINCT c.claim_id) as claims,
            COUNT(DISTINCT CASE WHEN e.evidence_id IS NOT NULL THEN c.claim_id END) as with_evidence,
            COUNT(DISTINCT CASE WHEN c.reasoning IS NOT NULL AND c.reasoning != '' THEN c.claim_id END) as with_reasoning
        FROM claims c
        LEFT JOIN evidence e ON c.claim_id = e.claim_id
    """).fetchone()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Claims", evidence_stats['claims'])
    col2.metric("With Evidence", evidence_stats['with_evidence'])
    col3.metric("With Reasoning", evidence_stats['with_reasoning'])
    
    # Contradiction detection
    contradictions = db.execute("""
        SELECT COUNT(*) as total FROM claim_relationships WHERE relationship_type = 'contradicts'
    """).fetchone()['total']
    
    st.metric("Detected Contradictions", contradictions)


def render_patterns(db):
    """Cross-video patterns."""
    st.subheader("Cross-Video Patterns")
    
    # Consensus topics
    consensus = db.execute("""
        SELECT topic, COUNT(DISTINCT video_id) as videos, COUNT(*) as claims
        FROM claims
        GROUP BY topic
        ORDER BY videos DESC
        LIMIT 10
    """).fetchall()
    
    consensus_df = pd.DataFrame(consensus, columns=['Topic', 'Videos', 'Claims'])
    st.write("**Most Discussed Topics:**")
    st.dataframe(consensus_df)


def render_trends(db):
    """Temporal trends."""
    st.subheader("Trends (Last 90 Days)")
    
    trends = db.execute("""
        SELECT 
            DATE(v.upload_date) as date,
            COUNT(DISTINCT v.video_id) as videos,
            COUNT(DISTINCT c.claim_id) as claims
        FROM videos v
        LEFT JOIN claims c ON v.video_id = c.video_id
        WHERE v.upload_date >= date('now', '-90 days')
        GROUP BY DATE(v.upload_date)
        ORDER BY date ASC
    """).fetchall()
    
    trends_df = pd.DataFrame(trends, columns=['Date', 'Videos', 'Claims'])
    st.line_chart(trends_df.set_index('Date'))
```

---

### Task 2.3: Authority Scoring System

**New File:** `src/intelligence/authority_scorer.py`

```python
"""
Calculate dynamic credibility scores for guests.
"""

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass
class AuthorityScore:
    guest_name: str
    topic: str
    overall_score: float  # 0.0-1.0
    mention_frequency: float
    prediction_accuracy: float
    peer_agreement: float
    recency_boost: float
    confidence_marker: str  # 'high', 'medium', 'low'


class AuthorityScorer:
    """Calculate guest authority scores across topics."""
    
    def __init__(self, db):
        self.db = db
    
    def calculate_authority(self, guest_name: str, topic: str) -> AuthorityScore:
        """Calculate authority score for a guest on a topic."""
        
        # Component 1: Mention frequency (normalized)
        mention_freq = self._calculate_mention_frequency(guest_name, topic)
        
        # Component 2: Prediction accuracy
        pred_accuracy = self._calculate_prediction_accuracy(guest_name, topic)
        
        # Component 3: Peer agreement
        peer_agree = self._calculate_peer_agreement(guest_name, topic)
        
        # Component 4: Recency boost
        recency = self._calculate_recency_boost(guest_name, topic)
        
        # Weighted composite
        overall = (
            0.25 * mention_freq +
            0.40 * pred_accuracy +
            0.25 * peer_agree +
            0.10 * recency
        )
        
        # Confidence in the score
        data_points = self._count_data_points(guest_name, topic)
        if data_points > 10:
            confidence = "high"
        elif data_points > 3:
            confidence = "medium"
        else:
            confidence = "low"
        
        return AuthorityScore(
            guest_name=guest_name,
            topic=topic,
            overall_score=overall,
            mention_frequency=mention_freq,
            prediction_accuracy=pred_accuracy,
            peer_agreement=peer_agree,
            recency_boost=recency,
            confidence_marker=confidence
        )
    
    def _calculate_mention_frequency(self, guest_name: str, topic: str) -> float:
        """Higher mention = higher authority (normalized)."""
        result = self.db.execute("""
            SELECT COUNT(*) as count FROM claims
            WHERE speaker = ? AND topic = ?
        """, (guest_name, topic)).fetchone()
        
        total = result['count']
        # Normalize: log scale (1 mention = 0.1, 10 mentions = 0.3, 100+ = 0.5)
        import math
        return min(0.5 * math.log(total + 1) / math.log(100), 1.0)
    
    def _calculate_prediction_accuracy(self, guest_name: str, topic: str) -> float:
        """What percentage of their predictions were correct."""
        result = self.db.execute("""
            SELECT
                COUNT(CASE WHEN verification_status = 'verified_correct' THEN 1 END) as correct,
                COUNT(CASE WHEN verification_status IN ('verified_correct', 'verified_wrong') THEN 1 END) as total_verified
            FROM predictions
            WHERE speaker = ? AND domain = ?
        """, (guest_name, topic)).fetchone()
        
        if result['total_verified'] == 0:
            return 0.5  # No data = neutral score
        
        return result['correct'] / result['total_verified']
    
    def _calculate_peer_agreement(self, guest_name: str, topic: str) -> float:
        """Do other experts agree with this guest's positions?"""
        result = self.db.execute("""
            SELECT
                COUNT(CASE WHEN conflict_count = 0 THEN 1 END) as agreements,
                COUNT(*) as total_interactions
            FROM guest_conflict_matrix
            WHERE (guest_a = ? OR guest_b = ?) AND topic = ?
        """, (guest_name, guest_name, topic)).fetchone()
        
        if result['total_interactions'] == 0:
            return 0.5
        
        # Agreement rate: (total - conflicts) / total
        return 1.0 - (result['agreements'] / max(result['total_interactions'], 1))
    
    def _calculate_recency_boost(self, guest_name: str, topic: str) -> float:
        """Boost score if recent appearances (trending expertise)."""
        result = self.db.execute("""
            SELECT DATE(MAX(v.upload_date)) as last_appearance
            FROM claims c
            JOIN videos v ON c.video_id = v.video_id
            WHERE c.speaker = ? AND c.topic = ?
        """, (guest_name, topic)).fetchone()
        
        if not result['last_appearance']:
            return 0.0
        
        from datetime import datetime, timedelta
        last_date = datetime.fromisoformat(result['last_appearance'])
        days_ago = (datetime.now() - last_date).days
        
        # Decay: recent = 1.0, 180 days ago = 0.0
        return max(1.0 - (days_ago / 180), 0.0)
    
    def _count_data_points(self, guest_name: str, topic: str) -> int:
        """Count how many data points inform this score."""
        result = self.db.execute("""
            SELECT
                (SELECT COUNT(*) FROM claims WHERE speaker = ? AND topic = ?) +
                (SELECT COUNT(*) FROM predictions WHERE speaker = ? AND domain = ?)
            as total
        """, (guest_name, topic, guest_name, topic)).fetchone()
        
        return result['total']
```

---

## Phase 3: Week 5-6 (UI & Discovery)

### Task 3.1: Comparative Analysis UI

**New File:** `src/ui/pages/comparative_analysis.py`

```python
"""
Comparative analysis interface.

Compare guest positions on topics:
- Dimensional analysis
- Evidence comparison
- Assumption differences
- Temporal evolution
"""

import streamlit as st
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.authority_scorer import AuthorityScorer


def render_comparative_analysis():
    """Main comparative analysis interface."""
    
    st.title("🔍 Comparative Analysis")
    st.write("Compare how different guests approach the same topics.")
    
    db = SQLiteStore()
    
    # Select guests to compare
    col1, col2, col3 = st.columns(3)
    
    with col1:
        guests = db.execute("SELECT DISTINCT speaker FROM claims ORDER BY speaker").fetchall()
        guest_names = [g['speaker'] for g in guests]
        guest_a = st.selectbox("Guest A", guest_names, key="guest_a")
    
    with col2:
        guest_b = st.selectbox("Guest B", guest_names, key="guest_b", index=1)
    
    with col3:
        # Select topic
        topics = db.execute("SELECT DISTINCT topic FROM claims ORDER BY topic").fetchall()
        topic_names = [t['topic'] for t in topics if t['topic']]
        topic = st.selectbox("Topic", topic_names) if topic_names else None
    
    if not (guest_a and guest_b and topic):
        st.warning("Select two guests and a topic to compare")
        return
    
    # Fetch claims for both guests
    claims_a = db.execute("""
        SELECT * FROM claims WHERE speaker = ? AND topic = ? ORDER BY timestamp
    """, (guest_a, topic)).fetchall()
    
    claims_b = db.execute("""
        SELECT * FROM claims WHERE speaker = ? AND topic = ? ORDER BY timestamp
    """, (guest_b, topic)).fetchall()
    
    if not claims_a or not claims_b:
        st.info(f"No claims found for one or both guests on {topic}")
        return
    
    # Authority scores
    scorer = AuthorityScorer(db)
    auth_a = scorer.calculate_authority(guest_a, topic)
    auth_b = scorer.calculate_authority(guest_b, topic)
    
    # Display comparison
    st.subheader(f"{guest_a} vs {guest_b} on {topic}")
    
    # Authority comparison
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"### {guest_a}")
        st.metric("Authority Score", f"{auth_a.overall_score:.2f}")
        st.metric("Mention Frequency", f"{auth_a.mention_frequency:.2f}")
        st.metric("Prediction Accuracy", f"{auth_a.prediction_accuracy:.0%}")
        
        st.write("**Claims:**")
        for claim in claims_a[:5]:
            st.write(f"- {claim['claim_text'][:80]}...")
    
    with col2:
        st.write(f"### {guest_b}")
        st.metric("Authority Score", f"{auth_b.overall_score:.2f}")
        st.metric("Mention Frequency", f"{auth_b.mention_frequency:.2f}")
        st.metric("Prediction Accuracy", f"{auth_b.prediction_accuracy:.0%}")
        
        st.write("**Claims:**")
        for claim in claims_b[:5]:
            st.write(f"- {claim['claim_text'][:80]}...")
    
    # Agreement/disagreement analysis
    st.subheader("Agreement Analysis")
    
    conflict = db.execute("""
        SELECT * FROM guest_conflict_matrix
        WHERE (guest_a = ? AND guest_b = ?) OR (guest_a = ? AND guest_b = ?)
    """, (guest_a, guest_b, guest_b, guest_a)).fetchone()
    
    if conflict:
        st.write(f"**Documented disagreements:** {conflict['conflict_count']}")
    else:
        st.write("**No documented disagreements** (or views are complementary)")
```

---

## Testing & Validation Checklist

```
✓ = Done    ○ = In Progress    × = Not Started

PHASE 0 (Baseline):
─────────────────────────────────
✓ Task 0.1: Claim certainty markers extracted
✓ Task 0.2: Guest conflict matrix populated
✓ Task 0.3: Transcript quality scores calculated
○ Task 0.4: Prediction extractor integrated

PHASE 1 (Enhanced Extraction):
─────────────────────────────────
○ Task 1.1: Evidence extraction working
○ Task 1.2: Claim relationships detected
○ 10 sample claims manually verified for correctness

PHASE 2 (Analysis):
─────────────────────────────────
○ Task 2.1: Contradiction detection engine
○ Task 2.2: Quality metrics dashboard loads
○ Task 2.3: Authority scores calculated for 5 guests

PHASE 3 (UI):
─────────────────────────────────
○ Task 3.1: Comparative analysis page renders
○ Dashboard queries execute in <2s
○ Export functionality works

QUALITY ASSURANCE:
─────────────────────────────────
○ 50 claims manually reviewed
○ Entity resolution accuracy > 90%
○ Contradiction detection precision > 85%
○ Evidence extraction recall > 70%

PERFORMANCE:
─────────────────────────────────
○ Dashboard queries < 2s
○ Comparative analysis < 3s
○ Contradiction detection < 5s for 100 claims
○ Authority scoring < 1s per guest-topic pair
```

---

## Success Metrics

After completing all phases, you should be able to:

- ✅ Answer 15+ new question types (vs 5 currently)
- ✅ Track consensus shifts on any topic
- ✅ Identify emerging disagreements automatically
- ✅ Assess guest credibility by topic
- ✅ Reconstruct full arguments (not just quotes)
- ✅ Detect contradictions between guests
- ✅ Compare worldviews with dimensional analysis
- ✅ Explain *why* guests disagree (framework differences)

---

## Estimated Timeline

- Phase 0: **1 week** (quick wins)
- Phase 1: **2 weeks** (extraction depth)
- Phase 2: **2 weeks** (analysis engines)
- Phase 3: **2 weeks** (UI integration)

**Total: ~7 weeks from analysis to production enhancements**

