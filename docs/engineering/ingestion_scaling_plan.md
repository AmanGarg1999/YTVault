# Ingestion Scaling & Pipeline Stabilization Plan

This document outlines the architectural strategy for transforming the KnowledgeVault-YT ingestion pipeline into a high-throughput, research-grade intelligence engine capable of large-scale channel harvesting.

## 1. Performance: "Batch All The Things"
To handle thousands of videos efficiently, we are shifting from per-video transactions to bulk processing across all major pipeline stages.

### Multi-Video Triage
- **Current**: 1 LLM call per video.
- **Scaling**: Groups 10-20 videos into a single LLM context. Reduces LLM round-trips by 90% and optimizes token usage.
- **Implementation**: `TriageEngine.batch_classify()` uses a structured JSON list-based prompt.

### High-Throughput Embedding
- **Current**: Batch size of 50 chunks per vector store upsert.
- **Scaling**: Increased to 100 chunks. Integrated native Ollama batch embedding (`.embed`) to saturate GPU/NPU utilization.
- **Deduplication**: Content-hash based "Diff-Embedding" (P0-B) ensures only new/changed text segments incur inference costs.

### Deferred Graph Synchronization
- **Current**: Synchronous Neo4j write after every video.
- **Scaling**: Buffers Graph/Neo4j updates into batches of 10-50 videos. Uses Cypher `UNWIND` queries for massive write persistence speedup.

## 2. Resilience: Circuit Breakers
The pipeline depends on several external/heavy services (Ollama, YouTube API, Neo4j). We implement **Circuit Breakers** to prevent cascading failures.

- **Ollama Breaker**: If Ollama timeouts or fails 5 times consecutively, the circuit opens for 60s, failing background tasks instantly to preserve system responsiveness.
- **yt-dlp Breaker**: Protects against YouTube IP bans. Trips on consistent 403 or 429 errors, halting discovery until the timeout expires.

## 3. Large-Scale Discovery Optimization
- **Flat-Playlist Discovery**: Bypasses heavy frontend parsing by using `--flat-playlist` and `--playlist-end 1` for instant metadata.
- **Tab-Targeted Extraction**: Specifically targets the `/videos` tab to avoid the overhead of featured content and channel homepages.
- **Incremental Diff-Harvesting (P0-E)**: Uses `--dateafter` to only discover content released since the last successful scan.

## 4. Integrity & Observability
- **Saga Outbox Pattern (P0-A)**: Ensures atomic synchronization between SQLite, ChromaDB, and Neo4j. If one store fails, the Outbox tracks the pending sync for automatic retry.
- **Strict Boolean Flow**: Every pipeline stage in `Orchestrator` returns a success signal. Checkpoints ONLY advance on `True`, preventing silent failures and lost data.
- **Unified Pipeline Center**: Provides real-time visibility into scan progress, ETA (P1-D), and detailed error logs via `pipeline_logs`.
