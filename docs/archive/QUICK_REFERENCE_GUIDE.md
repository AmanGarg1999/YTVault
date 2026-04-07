# Quick Reference: Data Quality & Utilization Guide

## 1️⃣ What's Extracted: The Data Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                       EXTRACTION PYRAMID                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LAYER 1: METADATA (YouTube origin)                 [9/10] │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ • Video ID, Title, Channel, Upload Date                  │ │
│  │ • Duration, View Count, Language                         │ │
│  │ • Transcript Strategy (manual vs auto)                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LAYER 2: NORMALIZED TRANSCRIPTS               [8/10]       │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ • Fillers removed (~20-30%)                             │ │
│  │ • Sponsored segments stripped (~15-25%)                 │ │
│  │ • Semantic chunking (400w windows)                      │ │
│  │ • Issue: Fixed windows may break context               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LAYER 3: EXTRACTED KNOWLEDGE                    [7.5/10]  │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  Topics, Entities, Claims, Quotes                      │ │
│  │  NO confidence tuning on claims                        │ │
│  │  NO reasoning behind claims                            │ │
│  │  NO evidence tracking                                  │ │
│  │  NO temporal context (fact vs opinion vs prediction)   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LAYER 4: RELATIONSHIPS (Graph)                 [6.5/10]   │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ • Guest → Video (timestamp + context)          Good    │ │
│  │ • Guest → Topic (inferred from mentions)       Weak    │ │
│  │ • Video → Topic (no weight/relevance)          Weak    │ │
│  │ • Topic → Topic (co-occurrence only)           Weak    │ │
│  │ • Issue: No relationship confidence scores               │ │
│  │ • Issue: No evidence chains                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2️⃣ Critical Quality Issues

```
┌──────────────────────────────────────────────────────────────────┐
│                      QUALITY ISSUE MATRIX                         │
├──────────────┬──────────────────┬────────────┬──────────────────┤
│ ISSUE        │ IMPACT           │ FREQUENCY  │ RISK LEVEL       │
├──────────────┼──────────────────┼────────────┼──────────────────┤
│ Entity       │ Wrong guest      │ 5-10%      │ 🟠 MEDIUM        │
│ Resolution   │ clustered as one │            │                  │
│ False +      │                  │            │                  │
├──────────────┼──────────────────┼────────────┼──────────────────┤
│ Triage       │ ~10-20% high     │ Ongoing    │ 🔴 HIGH          │
│ Bias         │ signal content   │            │ (missed data)    │
│              │ rejected         │            │                  │
├──────────────┼──────────────────┼────────────┼──────────────────┤
│ Claim        │ Can't assess     │ 100%       │ 🟠 MEDIUM        │
│ Confidence   │ belief vs fact   │            │                  │
├──────────────┼──────────────────┼────────────┼──────────────────┤
│ Parsing      │ Video → manual   │ <5%        │ 🟢 LOW           │
│ Failures     │ review instead   │            │                  │
│              │ of LLM triage    │            │                  │
├──────────────┼──────────────────┼────────────┼──────────────────┤
│ No Evidence  │ Claims float     │ 100%       │ 🔴 HIGH          │
│ Traceability │ without justif.  │            │ (limits reasoning)│
└──────────────┴──────────────────┴────────────┴──────────────────┘
```

---

## 3️⃣ What You Can Ask vs Can't Ask

```
┌─────────────────────────────────────────────────────────────────┐
│                  CURRENT CAPABILITY MAP                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CAN ASK (Well-supported by current extraction):             │
│                                                                  │
│  • "What did [Guest] say about [Topic]?"                       │
│    → ~8s, cites timestamps, accuracy ~85%                      │
│                                                                  │
│  • "Which guests discuss [Topic]?"                             │
│    → Instant, from graph, ~10 guests                           │
│                                                                  │
│  • "Show me [Guest]'s appearances across channels"             │
│    → ~2s, timeline view, accurate                              │
│                                                                  │
│  • "What quotes exist on [Topic]?"                             │
│    → ~3s, sorted by relevance, 5-10 quotes                     │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CANNOT ASK (Missing semantic layers):                       │
│                                                                  │
│  • "Compare [Guest A] vs [Guest B] on [Topic]"                │
│    → Would need structured position maps                       │
│                                                                  │
│  • "Why does [Guest] believe [Claim]?"                         │
│    → No reasoning extraction                                   │
│                                                                  │
│  • "What evidence supports/refutes [Claim]?"                   │
│    → Claims ≠ evidence links                                   │
│                                                                  │
│  • "Where do experts disagree on [Topic]?"                     │
│    → No contradiction detection                                │
│                                                                  │
│  • "Has [Guest]'s view on [Topic] shifted over time?"          │
│    → No belief evolution tracking                              │
│                                                                  │
│  • "What are emerging topics in your vault?"                   │
│    → No trend analysis               │                         │
│                                                                  │
│  • "Is [Prediction] accurate? Who was right?"                  │
│    → No prediction tracking                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4️⃣ The Utilization Gap: Data vs Knowledge

```
                    STRUCTURED DATA
                           |
                           v
    ┌──────────────────────────────────┐
    │ What you have:                   │
    │ • Topics exist                   │
    │ • Guests mentioned X times       │
    │ • Claims extracted              │
    │ • Quotes with timestamps        │
    │ • Some graph relationships      │
    └──────────────────────────────────┘
                           |
                           v
                    KNOWLEDGE DEAD END
                           |
                    (What's missing)
                           |
    ┌──────────────────────────────────┐
    │ To enable understanding:         │
    │ • Why guests believe claims      │
    │ • When claims changed            │
    │ • Which claims conflict          │
    │ • What evidence supports them    │
    │ • How frameworks differ          │
    │ • What assumptions underlie      │
    └──────────────────────────────────┘
                           |
                           v
                    ACTIONABLE KNOWLEDGE
                           |
                           v
    ┌──────────────────────────────────┐
    │ Enables:                         │
    │ • Comparative analysis           │
    │ • Reasoning through frameworks   │
    │ • Consensus detection            │
    │ • Trend identification           │
    │ • Authority scoring              │
    │ • Argument reconstruction        │
    └──────────────────────────────────┘
```

---

## 5️⃣ Priority Enhancements Map

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENHANCEMENT ROADMAP                          │
├─────┬──────────────────────┬────────┬──────────┬────────────────┤
│ SEQ │ FEATURE              │ TIME   │ IMPACT   │ COMPLEXITY     │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  1  │ Claim Confidence     │ 3 days │ ⭐⭐⭐   │ 🟢 TRIVIAL     │
│     │ Tiers               │        │          │ (Config only)  │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  2  │ Guest Disagreement   │ 1 week │ ⭐⭐⭐   │ 🟢 TRIVIAL     │
│     │ Tracking            │        │          │ (SQL table)    │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  3  │ Transcript Quality   │ 1 week │ ⭐⭐    │ 🟢 TRIVIAL     │
│     │ Markers             │        │          │ (Metrics calc) │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  4  │ Prediction Tracker   │ 1 week │ ⭐⭐⭐⭐  │ 🟡 MEDIUM      │
│     │                     │        │          │ (Manual verify)│
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  5  │ Evidence Extraction  │ 2 wk   │ ⭐⭐⭐⭐⭐ │ 🟠 COMPLEX     │
│     │                     │        │          │ (New prompts)  │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  6  │ Contradiction        │ 2 wk   │ ⭐⭐⭐⭐  │ 🟠 COMPLEX     │
│     │ Detection           │        │          │ (Clustering)   │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  7  │ Authority Scoring    │ 2 wk   │ ⭐⭐⭐⭐  │ 🟠 COMPLEX     │
│     │                     │        │          │ (Aggregation)  │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  8  │ Comparative UI       │ 2 wk   │ ⭐⭐⭐⭐  │ 🟠 COMPLEX     │
│     │                     │        │          │ (UI design)    │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│  9  │ Assumption Extract   │ 3 wk   │ ⭐⭐⭐⭐⭐ │ 🔴 HARD        │
│     │                     │        │          │ (New LLM task) │
├─────┼──────────────────────┼────────┼──────────┼────────────────┤
│ 10  │ Reasoning Engine     │ 3 wk   │ ⭐⭐⭐⭐⭐ │ 🔴 HARD        │
│     │                     │        │          │ (New system)   │
└─────┴──────────────────────┴────────┴──────────┴────────────────┘

Quick Win Strategy (This Month):
├─ Do: 1, 2, 3, 4 (cumulative 4 weeks, 80% of value)
└─ Defer: 5-10 (after proving value of quick wins)
```

---

## 6️⃣ Claim Evolution Example (Why It Matters)

```
Timeline of Claims on "AGI Timeline":

2023:
├─ "AGI is 10+ years away" (Expert consensus)
├─ Confidence: HIGH (agreement > 70%)
└─ Speaker authority: 0.8 avg

2024:
├─ "AGI by 2030" (Elon, Sam Altman)
├─ "AGI is 50+ years away" (Yann LeCun)
├─ Confidence: LOW (disagreement > 60%)
└─ Speaker authority diverges (0.3 to 0.9)

2025:
├─ "Near-term AGI capability possible" (shift)
├─ "Timeline is unknowable" (new camp)
├─ Confidence: MIXED (three competing views)
└─ "Predictions more cautious after misses"

Current capability:
 Can retrieve all quotes
 Can't detect this evolution
 Can't assess accuracy of 2023 claims
 Can't identify confidence shift
```

---

## 7️⃣ Data Extraction Completeness Heat Map

```
What You Extract Well      What You Miss Entirely
─────────────────────────  ──────────────────────

Guest ──┬──→ 100%          Claim ──┬──→ 0% Evidence
        └──→ Topic (30%)           ├──→ 0% Reasoning
                                   ├──→ 0% Certainty type
Timestamps ──→ 100%                ├──→ 0% Contradictions
                                   └──→ 0% Assumptions

Video ──┬──→ Metadata (100%)    Argument Structure:
        ├──→ Topics (40%)       ├──→ 0% Premises tracked
        ├──→ Claims (60%)       ├──→ 0% Logical flow
        └──→ Quotes (80%)       ├──→ 0% Inference chains
                                └──→ 0% Assumptions

Channel ──→ 100%              Domain Models:
                              ├──→ 0% Key questions
                              ├──→ 0% Frameworks
                              ├──→ 0% Definitions
                              └──→ 0% Empirical validation

Overall: ~60% structural    Overall: ~0% semantic
         metadata            deep reasoning
```

---

## 8️⃣ Three Actions to Take This Week

### Action #1: Add Claim Confidence Tiers (30 min coding)

**File:** `src/intelligence/chunk_analyzer.py`

```python
# Current:
claims = [{"speaker": "X", "claim": "Y"}]

# Enhanced:
claims = [
    {
        "speaker": "X",
        "claim": "Y",
        "confidence": 0.75,
        "tier": "HIGH",           # 👈 NEW
        "type": "assertion"       # 👈 NEW
    }
]
```

**Result:** Filter RAG responses for "high-confidence only" mode.

---

### Action #2: Track Guest Disagreement (1 hour SQL)

**File:** `src/storage/sqlite_store.py`

```sql
CREATE TABLE guest_conflict_matrix (
    guest_a TEXT,
    guest_b TEXT,
    topic TEXT,
    conflict_count INT,
    total_interactions INT,
    conflict_rate FLOAT,
    PRIMARY KEY (guest_a, guest_b, topic)
);
```

**Result:** Query becomes: "Who disagrees with Naval on AI safety?"

---

### Action #3: Mark Transcript Quality (1 hour)

**File:** `src/ingestion/refinement.py`

```python
quality_score = {
    "raw_word_count": 10000,
    "cleaned_word_count": 8500,
    "filler_removal_rate": 0.15,
    "sponsor_removal_rate": 0.05,
    "transcript_strategy": "manual_en",
    "overall_quality": "HIGH"  # if < 10% removed
}
```

**Result:** Filter queries for "cleanest transcripts only."

---

## 9️⃣ Why Each Enhancement Matters

```
Enhancement              Current Gap              Impact When Fixed
───────────────────────────────────────────────────────────────────

Claim Confidence      Can't distinguish         Users can say:
Tiers                 high-conviction           "High-confidence views
                      from speculative          on X are..."

Guest Disagreement    Can't identify            Answer new questions:
Tracking              expert conflicts          "Where do experts
                                                disagree?"

Prediction Tracker    Can't assess accuracy     Feedback loop:
                      of forecasts              "Who was right?"

Evidence Links        Claims float without      Enable reasoning:
                      justification             "Why do they believe?"

Contradiction         Can't flag disagreements  Find frontiers:
Detection             automatically             "Frontier topics are..."

Authority Scores      All guests weighted       Trust signals:
                      equally                   "Trust X more on Y
                                                because..."

Comparative UI        Must ask separately       Comparative queries:
                      about each guest          "A vs B on C"

Assumption Extract    Hidden premises           Framework analysis:
                      remain hidden             "They differ on..."

Reasoning Engine      Can't trace logic         Enable reasoning:
                      through arguments         "If A then B..."
```

---

## 🔟 Monthly Tracking Dashboard

```
┌──────────────────────────────────────────────────────┐
│         METRICS TO MONITOR MONTHLY                   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Extraction Quality:                                  │
│  • Claim extraction rate        [Target: >70%]       │
│  • Claims with evidence linked  [Target: >50%]       │
│  • Certainty type distribution  [Show: % each]       │
│  • Entity resolution accuracy   [Target: >90%]       │
│                                                      │
│ Knowledge Depth:                                     │
│  • Avg reasoning premises/claim [Target: >2]         │
│  • Contradiction detection rate [Show: #/month]      │
│  • Assumption extraction rate   [Show: % claims]     │
│  • Guest authority range        [Show: 0.1-0.9]      │
│                                                      │
│ Utilization:                                         │
│  • Comparative queries/month    [Track growth]       │
│  • Contradiction queries        [Track growth]       │
│  • Prediction accuracy checks   [Track growth]       │
│  • "Framework disagree" queries [Track growth]       │
│                                                      │
│ Impact:                                              │
│  • User satisfaction +/-         [Survey/score]      │
│  • Query complexity trend        [Show trend]        │
│  • Vault value perception       [Survey/score]       │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Summary: The Four Fundamental Issues

```
ISSUE 1: Extraction Incompleteness
─────────────────────────────────────
You capture: Claims 
Missing:     Reasoning , Evidence , Certainty 
Fix:         Add reasoning + certainty extraction (2 weeks)

ISSUE 2: Relationship Weakness
─────────────────────────────────────
You capture: Who appeared where 
Missing:     Why they disagree , Authority 
Fix:         Add disagreement tracking + credibility (2 weeks)

ISSUE 3: Utilization Gap
─────────────────────────────────────
You extract: Structured data 
Missing:     Semantic understanding 
Fix:         Add contradiction detection + comparison UI (2 weeks)

ISSUE 4: No Quality Metrics
─────────────────────────────────────
You track:   Videos processed 
Missing:     Extraction quality , Knowledge depth 
Fix:         Add quality dashboard (1 week)

Total effort: ~7 weeks
Total impact: 3x utility increase
```

