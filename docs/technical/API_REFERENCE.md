# API Reference

> Module and class documentation for knowledgeVault-YT

---

## Table of Contents

- [Configuration (`src/config.py`)](#configuration)
- [Ingestion Pipeline](#ingestion-pipeline)
  - [Discovery (`src/ingestion/discovery.py`)](#discovery)
  - [Triage (`src/ingestion/triage.py`)](#triage)
  - [Transcript (`src/ingestion/transcript.py`)](#transcript)
  - [Refinement (`src/ingestion/refinement.py`)](#refinement)
- [Storage Layer](#storage-layer)
  - [SQLite Store (`src/storage/sqlite_store.py`)](#sqlite-store)
  - [Vector Store (`src/storage/vector_store.py`)](#vector-store)
  - [Graph Store (`src/storage/graph_store.py`)](#graph-store)
- [Intelligence Layer](#intelligence-layer)
  - [RAG Engine (`src/intelligence/rag_engine.py`)](#rag-engine)
  - [Entity Resolver (`src/intelligence/entity_resolver.py`)](#entity-resolver)
  - [Export (`src/intelligence/export.py`)](#export)
- [Pipeline](#pipeline)
  - [Orchestrator (`src/pipeline/orchestrator.py`)](#orchestrator)
  - [Checkpoint (`src/pipeline/checkpoint.py`)](#checkpoint)

---

## Configuration

### `src/config.py`

Central configuration loader for the application.

| Function | Description |
|---|---|
| `load_settings() → dict` | Load `config/settings.yaml` with resolved paths |
| `get_settings() → dict` | Cached singleton — load once, reuse everywhere |
| `load_verified_channels() → dict` | Load channel whitelist from YAML |
| `load_prompt(name: str) → str` | Load LLM prompt from `config/prompts/{name}.txt` |
| `ensure_data_dirs()` | Create `data/` and `data/chromadb/` directories |

**Constants:**
- `PROJECT_ROOT` — Auto-detected project root (via `pyproject.toml`)
- `CONFIG_DIR` — `{PROJECT_ROOT}/config`
- `DATA_DIR` — `{PROJECT_ROOT}/data`

---

## Ingestion Pipeline

### Discovery

#### `src/ingestion/discovery.py`

**Classes:**

| Class | Fields | Description |
|---|---|---|
| `ParsedURL` | `url_type`, `video_id`, `playlist_id`, `channel_handle`, `channel_id`, `raw_url` | Result of URL parsing |

**Functions:**

| Function | Signature | Description |
|---|---|---|
| `parse_youtube_url` | `(url: str) → ParsedURL` | Parse any YouTube URL into type + identifiers |
| `extract_video_metadata` | `(video_id: str) → Video` | Full metadata via `yt-dlp --dump-json` |
| `extract_channel_info` | `(url: str) → Channel` | Channel name, ID, description |
| `discover_video_ids` | `(url: str, parsed: ParsedURL) → list[str]` | All video IDs from channel/playlist |

**URL Patterns Supported:**
- `youtube.com/watch?v=XXXX` — Single video
- `youtu.be/XXXX` — Short URL
- `youtube.com/playlist?list=XXXX` — Playlist
- `youtube.com/@handle` — Channel handle
- `youtube.com/channel/UCXXXX` — Channel ID
- `youtube.com/c/name` — Custom URL

---

### Triage

#### `src/ingestion/triage.py`

**Enums:**

| Enum | Values |
|---|---|
| `TriageDecision` | `ACCEPT`, `REJECT`, `PENDING`, `NEEDS_LLM` |

**Classes:**

#### `TriageResult`
| Field | Type | Description |
|---|---|---|
| `decision` | `TriageDecision` | Classification result |
| `reason` | `str` | Human-readable reason |
| `confidence` | `float` | 0.0–1.0 confidence score |
| `phase` | `str` | `"rule"` or `"llm"` |
| `latency_ms` | `float` | Processing time |

#### `TriageEngine`
| Method | Description |
|---|---|
| `classify(video: Video) → TriageResult` | Full triage pipeline (rules + LLM) |
| `_rule_filter(video) → TriageResult` | Phase 1: Fast rule-based filter |
| `_llm_classify(video) → TriageResult` | Phase 2: Ollama LLM classification |

**Rule Priority:**
1. Duration < 60s → REJECT (unless shorts-whitelisted)
2. Verified channel → ACCEPT
3. Knowledge keyword in title → ACCEPT
4. All others → LLM classification

---

### Transcript

#### `src/ingestion/transcript.py`

**Classes:**

#### `TimestampedSegment`
| Field | Type | Description |
|---|---|---|
| `text` | `str` | Segment text |
| `start` | `float` | Start time (seconds) |
| `duration` | `float` | Duration (seconds) |

#### `TranscriptResult`
| Field | Type | Description |
|---|---|---|
| `segments` | `list[TimestampedSegment]` | All segments with timing |
| `full_text` | `str` | Concatenated text |
| `strategy` | `str` | `manual_en`, `auto_en`, `manual_any`, `auto_any`, `none` |
| `language_iso` | `str` | Language code |
| `needs_translation` | `bool` | True if non-English |
| `success` | `bool` | (property) Whether fetch succeeded |

**Functions:**

| Function | Signature | Description |
|---|---|---|
| `fetch_transcript` | `(video_id: str) → TranscriptResult` | Priority-ordered transcript fetch |

---

### Refinement

#### `src/ingestion/refinement.py`

**Functions:**

| Function | Signature | Description |
|---|---|---|
| `fetch_sponsor_segments` | `(video_id: str) → list[SponsorSegment]` | Get SponsorBlock data |
| `strip_sponsored_segments` | `(segments, sponsors) → list[TimestampedSegment]` | Remove sponsored text |
| `quick_normalize` | `(text: str) → str` | Regex-only filler removal (no LLM) |

**Classes:**

#### `TextNormalizer`
| Method | Description |
|---|---|
| `normalize(text: str) → str` | Full LLM normalization with chunking |

---

## Storage Layer

### SQLite Store

#### `src/storage/sqlite_store.py`

**Data Classes:** `Channel`, `Video`, `Guest`, `TranscriptChunk`, `ScanCheckpoint`

#### `SQLiteStore`

| Method | Description |
|---|---|
| **Channels** | |
| `upsert_channel(channel)` | Insert or update channel |
| `get_channel(id) → Channel` | Get by ID |
| `get_all_channels() → list` | List all channels |
| **Videos** | |
| `insert_video(video) → bool` | Insert (True if new) |
| `get_video(id) → Video` | Get by ID |
| `get_videos_by_status(status) → list` | Filter by triage status |
| `get_videos_by_channel(id) → list` | All videos for a channel |
| `update_triage_status(id, status, ...)` | Update triage result |
| `update_checkpoint_stage(id, stage)` | Advance pipeline stage |
| `get_resumable_videos() → list` | Accepted but not DONE |
| **Guests** | |
| `upsert_guest(name) → Guest` | Create or increment |
| `add_guest_alias(id, alias)` | Add name alias |
| `find_guest_exact(name) → Guest` | Exact name/alias lookup |
| `get_all_guests() → list` | All guests |
| **Chunks** | |
| `insert_chunks(chunks) → int` | Bulk insert |
| `get_chunks_for_video(id) → list` | Get video's chunks |
| **Checkpoints** | |
| `create_scan_checkpoint(url, type) → str` | New scan |
| `update_scan_checkpoint(id, ...)` | Update progress |
| `get_active_scans() → list` | In-progress scans |
| **Stats** | |
| `get_pipeline_stats() → dict` | Aggregate dashboard metrics |

---

### Vector Store

#### `src/storage/vector_store.py`

**Functions:**

| Function | Signature | Description |
|---|---|---|
| `sliding_window_chunk` | `(text, video_id, segments, ...) → list[TranscriptChunk]` | Create overlapping chunks with timestamps |

**Classes:**

#### `VectorStore`
| Method | Description |
|---|---|
| `upsert_chunks(chunks, ...) → int` | Embed and store chunks |
| `search(query, top_k, where) → list[dict]` | Semantic search |
| `delete_video_chunks(video_id)` | Remove a video's chunks |
| `get_stats() → dict` | Collection statistics |

---

### Graph Store

#### `src/storage/graph_store.py`

#### `GraphStore`
| Method | Description |
|---|---|
| **Nodes** | |
| `upsert_channel(id, name, ...)` | Create/update Channel node |
| `upsert_video(id, title, ...)` | Create/update Video + PUBLISHED link |
| `upsert_guest(name, ...)` | Create/update Guest node |
| `upsert_topic(name)` | Create/update Topic node |
| **Relationships** | |
| `link_guest_to_video(guest, video, ...)` | APPEARED_IN |
| `link_video_to_topic(video, topic, ...)` | DISCUSSES |
| `link_guest_to_topic(guest, topic, ...)` | EXPERT_ON |
| `link_related_topics(a, b, ...)` | RELATED_TO |
| **Queries** | |
| `get_guest_appearances(name) → list` | Cross-channel appearances |
| `get_cross_channel_topics(limit) → list` | Shared topics across channels |
| `get_guest_topic_evolution(name) → list` | Topic timeline for guest |
| `get_graph_stats() → dict` | Node/relationship counts |

---

## Intelligence Layer

### RAG Engine

#### `src/intelligence/rag_engine.py`

**Classes:**

#### `Citation`
| Field | Type | Description |
|---|---|---|
| `source_id` | `str` | e.g., `"source_1"` |
| `chunk_id` | `str` | ChromaDB document ID |
| `video_id` | `str` | YouTube video ID |
| `video_title` | `str` | |
| `channel_name` | `str` | |
| `start_timestamp` | `float` | Seconds |
| `timestamp_str` | `str` | (property) `"MM:SS"` format |
| `youtube_link` | `str` | (property) Timestamped YouTube URL |

#### `RAGResponse`
| Field | Type | Description |
|---|---|---|
| `query` | `str` | Original question |
| `answer` | `str` | Synthesized answer |
| `citations` | `list[Citation]` | Cited sources |
| `latency_ms` | `float` | End-to-end latency |

#### `RAGEngine`
| Method | Description |
|---|---|
| `query(question, filters) → RAGResponse` | Full RAG pipeline |

---

### Entity Resolver

#### `src/intelligence/entity_resolver.py`

#### `EntityResolver`
| Method | Description |
|---|---|
| `extract_entities(text) → list[ExtractedEntity]` | NER via LLM |
| `resolve(name) → Guest` | 4-tier resolution pipeline |
| `process_video_entities(video_id, text) → list[Guest]` | Full extract + resolve |

---

### Export

#### `src/intelligence/export.py`

#### `ExportEngine`
| Method | Description |
|---|---|
| `export_rag_response(response, fmt) → str` | Format RAG answer |
| `export_guests(fmt) → str` | Export guest registry |
| `export_pipeline_stats() → str` | Pipeline statistics |

Formats: `"markdown"`, `"json"`, `"csv"`

---

## Pipeline

### Orchestrator

#### `src/pipeline/orchestrator.py`

#### `PipelineOrchestrator`
| Method | Description |
|---|---|
| `run(url) → scan_id` | Full pipeline from URL to indexed |
| `resume(scan_id)` | Resume interrupted scan |
| `set_callbacks(on_progress, on_status)` | UI progress hooks |

### Checkpoint

#### `src/pipeline/checkpoint.py`

#### `CheckpointManager`
| Method | Description |
|---|---|
| `create_scan(url, type) → str` | New scan checkpoint |
| `advance(video_id, stage)` | Atomic stage transition |
| `get_resumable_videos() → list` | Videos needing processing |
| `complete_scan(scan_id)` | Mark scan as done |

**Stage Order:** `METADATA_HARVESTED` → `TRIAGE_COMPLETE` → `TRANSCRIPT_FETCHED` → `SPONSOR_FILTERED` → `TEXT_NORMALIZED` → `CHUNKED` → `EMBEDDED` → `GRAPH_SYNCED` → `DONE`
