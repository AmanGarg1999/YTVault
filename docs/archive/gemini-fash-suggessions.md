# knowledgeVault-YT Deep Analysis & Improvement Framework

## 1. Architecture & Pipeline Analysis

### 10-Stage (11 actual) Ingestion Pipeline
The current implementation in `orchestrator.py` and `checkpoint.py` follows an 11-stage flow:
1. **Discovery**: URL parsing and initial metadata harvest.
2. **Triage**: Rule-based + LLM classification.
3. **Transcript**: Fetching raw transcripts.
4. **Translation**: (NEW) Auto-translating non-English content to English.
5. **Sponsor Filtering**: SponsorBlock-based segment removal.
6. **Refinement (Normalization)**: Text cleaning and formatting.
7. **Chunking**: Sliding window or semantic segmentation.
8. **Chunk Analysis**: Entity, Topic, Claim, and Quote extraction.
9. **Summarization**: Map-Reduce hierarchical synthesis.
10. **Embedding**: ChromaDB vector indexing.
11. **Graph Sync**: Neo4j relationship mapping.

### Identified Bottlenecks & Failure Points
- **LLM Over-subscription**: `llm_max_workers` (8) is applied per `LLMPool` instance. Since `ChunkAnalyzer` and others instantiate their own pools during parallel video processing (`max_parallel_videos=4`), the system can attempt up to 32 concurrent Ollama calls, potentially thrashing the LLM server.
- **Resume Race Conditions**: `CheckpointManager.get_resumable_videos()` has no "claim" mechanism. Multiple orchestrator instances running `resume` will attempt to process the same videos simultaneously, leading to redundant work and potential DB deadlocks.
- **Graceful Degradation**: Robust fallback exists for translation (original text preserved) and transcript fetching (marks as DONE). However, Neo4j connectivity is a "fail-soft" rather than "fail-open" (it logs errors but proceeds).

---

## 2. Intelligence Layer Evaluation

### Hybrid RAG & RRF
- **Implementation**: Reciprocal Rank Fusion (RRF) with $k=60$ effectively merges Vector (Chroma) and FTS5 (SQLite) results.
- **Quality**: Keyword-only (FTS5) provides better precision for specific terms, while Semantic-only (Vector) provides better recall for conceptual queries. Hybrid successfully balances both.
- **Claim Extraction**: High fidelity using deep-model prompts in `ChunkAnalyzer`. Validated against ground truth logic.
- **Knowledge Density**: Current heuristic `(2*chunks + 10*guests)/duration` is objective but lacks "concept uniqueness" weighting.

---

## 3. UX & Operational Audit

### Streamlit Command Center
- **Cognitive Load**: 13+ views is high. Recommendations include a "Condensed View" for power users and tabbed sub-navigation.
- **Freshness Latency**: Real-time monitoring is tied to the 10-second checkpoint interval. Latency is acceptable for local use but may lag on high-volume channels.
- **Data Safety Rails**: **CRITICAL** - `delete_video_data` only clears SQLite. It does NOT remove data from ChromaDB or Neo4j, leading to orphaned vectors and graph nodes that cause duplicates upon reprocessing.

---

## Deliverables & Recommendations

### Critical Issues
1. **Vector/Graph Deletion Sync**: Fix the mismatch between relational and external stores to prevent data corruption.
2. **LLM Concurrency Guardrails**: Implement a global semaphore or shared pool for Ollama calls.
3. **Resume Locking**: Add a `LOCKED_BY_SCAN_ID` column to videos to prevent race conditions during resume.

### Enhancement Roadmap

| Priority | Feature | Description |
| :--- | :--- | :--- |
| **P0** | **Atomic Deletion** | Ensure `delete_video` wipes specific IDs from ChromaDB and Neo4j. |
| **P0** | **Global LLM Pool** | Centralize concurrency management to respect hardware limits. |
| **P1** | **Entity-based Density** | Refine Density Score to count *unique* entities per minute. |
| **P1** | **Multi-modal Heatmaps** | Correlate visual interest peaks with transcript segments for "Key Highlights" view. |
| **P2** | **Self-Healing Pipeline** | Automated "Repair" triggers when data gaps are detected mid-query. |

### Testing Strategy: Neo4j Fail-Open
To verify fail-open behavior, implement an integration test that:
1. Mocks a connection failure to Neo4j.
2. Triggers the `GRAPH_SYNCED` stage.
3. Asserts that the pipeline advances to `DONE` and logs a WARNING without crashing.

### Documentation Gaps
- **Stage Transition Guide**: Detailed docs for the 11-stage transitions.
- **Ollama Optimization**: Recommended `num_ctx` and `num_thread` settings for various hardware tiers.
- **Config Validation**: Explicit schema for `settings.yaml` to prevent runtime errors on malformed configs.
