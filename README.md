<div align="center">

# 🧠 knowledgeVault-YT

**Local-First Research Intelligence System**

*Transform fragmented YouTube content into a structured, searchable Knowledge Graph — entirely on local hardware.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.com)
[![ChromaDB](https://img.shields.io/badge/Vector-ChromaDB-orange.svg)](https://www.trychroma.com)
[![Neo4j](https://img.shields.io/badge/Graph-Neo4j-008CC1.svg)](https://neo4j.com)

---

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Usage](#-usage) • [Configuration](#-configuration) • [Documentation](#-documentation)

</div>

---

## 🎯 Problem

YouTube is the world's largest repository of human expertise, but it's optimized for **engagement** (watch time) — not **extraction** (knowledge density). Researchers face:

| Friction | Impact |
|---|---|
| **High Noise-to-Signal** | Insights buried in hours of filler, sponsors, and entertainment |
| **Temporal Fragmentation** | Expert perspectives scattered across hundreds of videos/channels |
| **Search Limitations** | Keyword-based search misses deep semantic relationships in transcripts |

**knowledgeVault-YT** solves this by building a local, privacy-first pipeline that autonomously ingests, triages, and synthesizes video transcripts into a **Contextual Knowledge Graph**.

---

## ✨ Features

### 🔄 Multi-Stage Ingestion Pipeline
- **Smart Discovery** — Ingest entire channels, playlists, or individual videos via `yt-dlp`
- **Two-Phase Triage** — Rule-based pre-filter + LLM classifier separates knowledge-dense content from noise
- **Ambiguity Queue** — Manual review UI for uncertain classifications
- **SponsorBlock Integration** — Automatically strips sponsored segments, intros, and self-promotion
- **Text Normalization** — LLM-powered filler removal and punctuation fixing

### 💾 Hybrid Three-Layer Storage
- **Relational (SQLite)** — Structured metadata, triage status, pipeline checkpoints, claims, quotes
- **Vector (ChromaDB)** — Semantic embeddings with sliding-window or semantic-boundary chunking
- **Graph (Neo4j)** — Entity relationships: Gu### 🧠 Intelligence Layer
- **Hybrid RAG Engine** — Reciprocal Rank Fusion (RRF) combining ChromaDB semantic vectors with SQLite FTS5 exact full-text search.
- **Per-Chunk Deep Analysis** — Every transcript chunk is independently analyzed for topics, entities, claims, and quotes — not just the first few minutes.
- **Claim/Assertion Extraction** — Automatically identifies who said what: "Naval argues that specific knowledge can't be taught." Stored as structured graph data.
- **Quote Extraction** — Surfaces memorable, citable statements from every video.
- **Map-Reduce Summarization** — Full-video summaries covering every minute, not just a truncated prefix.
- **The Epiphany Engine** — Autonomous cross-channel insight generation with relationship classification (Consensus, Contradiction, Complementary, Evolution).
- **Semantic Chunking** — Optional topic-boundary-aware splitting using sentence embedding similarity for higher retrieval quality.
- **Hierarchical Topic Taxonomy** — LLM-organized parent-child topic hierarchy (`Technology > AI > Deep Learning > Transformers`).
- **Structured Querying** — Advanced filter syntax parsing (`channel:lex topic:AI after:2024 What is AGI?`) with multi-turn conversation memory.
- **Knowledge Density Leaderboard** — UI dashboard ranking videos by empirical informational density.
- **Clip Export** — Extract raw `.mp4` video soundbites from RAG citations using embedded `yt-dlp`.
- **Entity Resolution** — Fuzzy matching + LLM disambiguation for guest deduplication across channels.
- **Tiered Model Strategy** — Fast 3B model for triage/NER, deep 8B model for synthesis/claims.

### ⚡ Resilience & Control
- **Real-Time Logging** — Comprehensive event tracking with SUCCESS/INFO/WARNING/ERROR levels and full tracebacks.
- **Pipeline Control** — Pause, resume, or stop ingestion scans gracefully at any safe point (between videos).
- **Crash-safe Checkpoints** — Resume interrupted scans from the exact point of failure.
- **Video Queue Management** — Pre-processing queue control (skip/remove discovered videos).
- **Data Management** — Safe deletion of video/channel data with cascading cleanup and audit trail.
- **Per-video stage tracking** — Each video independently tracks its 10-stage pipeline progress.
- **Graceful degradation** — Neo4j/SponsorBlock failures don't break the pipeline.
 pipeline progress
- **Graceful degradation** — Neo4j/SponsorBlock failures don't break the pipeline

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Runtime |
| **Ollama** | Latest | Local LLM inference |
| **yt-dlp** | Latest | YouTube metadata extraction |
| **Neo4j** | 5.x (optional) | Knowledge graph |
| **Docker** | Latest (optional) | Containerized deployment |

### Option 1: Local Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-repo/knowledgeVault-YT.git
cd knowledgeVault-YT

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Pull required Ollama models
ollama pull llama3.2:3b              # Fast model (triage, NER)
ollama pull llama3.1:8b              # Deep model (summarization, RAG)
ollama pull nomic-embed-text         # Embeddings

# 5. Start the Streamlit UI
kvault ui
```

### Option 2: Docker Compose (Recommended)

```bash
# Start all services (knowledgeVault web app + Ollama + Neo4j)
docker compose up -d

# Pull LLM models into Ollama container
docker compose exec ollama ollama pull llama3:8b-instruct-q4_K_M
docker compose exec ollama ollama pull nomic-embed-text

# Access the UI
open http://localhost:8501
```

> **Note:** The Docker deployment mounts `./data` locally to persist your SQLite database, ChromaDB vectors, and Graph data permanently.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Streamlit Command Center               │
│  ┌────────┐ ┌─────────┐ ┌────────┐ ┌───────┐ ┌───────┐  │
│  │Harvest │ │Ambiguity│ │Research│ │Guest  │ │Explore│  │
│  │Manager │ │ Queue   │ │Console │ │Intel  │ │Graph  │  │
│  └───┬────┘ └────┬────┘ └───┬────┘ └──┬────┘ └──┬────┘  │
└──────┼───────────┼──────────┼─────────┼─────────┼────────┘
       │           │          │         │         │
┌──────▼───────────▼──────────▼─────────▼─────────▼────────┐
│                  Pipeline Orchestrator                    │
│  Discovery → Triage → Transcript → Refinement →          │
│  Chunking → Chunk Analysis → Embedding → Graph Sync      │
└─────┬──────────┬──────────┬──────────┬───────────────────┘
      │          │          │          │
 ┌────▼────┐ ┌──▼───┐ ┌───▼────┐ ┌──▼──────────────────┐
 │ SQLite  │ │Chroma│ │ Neo4j  │ │ Ollama              │
 │Metadata │ │Vector│ │ Graph  │ │ 3B fast + 8B deep   │
 │Claims   │ │      │ │ Claims │ │                     │
 │Quotes   │ │      │ │ Taxonomy│ │                    │
 └─────────┘ └──────┘ └────────┘ └─────────────────────┘
```

**Full architecture details:** See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 📖 Usage

### CLI Commands

```bash
# Harvest a channel
kvault harvest "https://youtube.com/@lexfridman"

# Harvest a playlist
kvault harvest "https://youtube.com/playlist?list=PLxxx"

# Harvest a single video
kvault harvest "https://youtube.com/watch?v=xxxxx"

# Resume an interrupted scan
kvault resume <scan_id>

# Query the knowledge vault
kvault query "What did Naval Ravikant say about wealth creation?"

# Export query as JSON
kvault query "Effects of AI on education" --format json

# View pipeline statistics
kvault stats

# List all scans
kvault scans

# Build hierarchical topic taxonomy
kvault taxonomy

# Check service health
kvault health

# Launch the web UI
kvault ui
```

### Streamlit UI

Launch with `kvault ui` and open `http://localhost:8501`:

| Page | Function |
|---|---|
| **🏠 Dashboard** | Overview metrics, Knowledge Density Leaderboard, active scanning jobs. |
| **🌾 Harvest Manager** | Start/resume highly concurrent metadata ingestion jobs. |
| **📋 Ambiguity Queue** | Accept/reject uncertain channel/video automated classifications. |
| **🔍 Research Console** | Hybrid Search, multi-turn RAG chat, inline summaries, and Clip Exporting. |
| **👤 Guest Intelligence** | Cross-channel guest appearances, topic evolution, mention tracking. |
| **🧠 Knowledge Explorer** | Interactive graph visualization, topic spotlights, entity connections. |
| **📊 Pipeline Monitor** | Real-time multi-stage process pipeline tracking with channel health. |
| **📋 Logs & Activity** | Real-time pipeline events, error analysis, and event timeline for troubleshooting. |
| **🎮 Pipeline Control** | Central hub for pausing/resuming scans and managing the discovery queue. |
| **🗑️ Data Management** | Safe data deletion tools with preview capability and audit history. |
| **📤 Export Center** | Export graph structures in Markdown/JSON/CSV. |

---

## ⚙️ Configuration

All configuration is in `config/settings.yaml`. Key sections:

```yaml
# Tiered LLM Models
ollama:
  triage_model: "llama3.2:3b"       # Fast: triage, NER, normalization
  deep_model: "llama3.1:8b"         # Deep: summarization, RAG, claims
  embedding_model: "nomic-embed-text"

# Triage tuning
triage:
  min_duration_seconds: 60
  llm_confidence_threshold: 0.7

# Chunking strategy
chunking:
  strategy: "sliding_window"   # or "semantic" for topic-boundary splitting
  window_size: 400
  overlap: 80

# Concurrent LLM processing
pipeline:
  llm_max_workers: 2
```

**Full configuration reference:** See [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

**Verified channels whitelist:** Edit `config/verified_channels.yaml` to auto-accept trusted channels.

---

## 📚 Documentation

| Document | Description |
|---|---|
| [Technical Specification](Technical_Specification.md) | Full system design with Mermaid diagrams |
| [Architecture Guide](docs/ARCHITECTURE.md) | System design, data flow, and component interactions |
| [API Reference](docs/API_REFERENCE.md) | Module and function documentation |
| [Developer Guide](docs/DEVELOPMENT.md) | Setup, testing, and contribution guidelines |
| [Configuration Reference](docs/CONFIGURATION.md) | Complete config file documentation |

---

## 📁 Project Structure

```
knowledgeVault-YT/
├── config/
│   ├── settings.yaml              # Main configuration
│   ├── verified_channels.yaml     # Channel whitelist
│   └── prompts/                   # LLM system prompts
│       ├── triage_classifier.txt
│       ├── text_normalizer.txt
│       ├── rag_synthesizer.txt
│       ├── entity_extractor.txt
│       ├── topic_extractor.txt
│       ├── claim_extractor.txt    # NEW: assertion extraction
│       ├── quote_extractor.txt    # NEW: notable quotes
│       ├── summarizer.txt         # Reduce-phase prompt
│       ├── map_reduce_summarizer.txt  # Map-phase prompt
│       └── epiphany_briefing.txt  # Cross-channel analysis
├── src/
│   ├── main.py                    # CLI entry point (Click)
│   ├── config.py                  # Config loader
│   ├── ingestion/                 # Ingestion pipeline
│   │   ├── discovery.py           # URL parsing, yt-dlp
│   │   ├── triage.py              # Two-phase triage engine
│   │   ├── transcript.py          # Transcript fetching
│   │   └── refinement.py          # SponsorBlock + LLM normalization
│   ├── storage/                   # Data layer
│   │   ├── sqlite_store.py        # Relational storage (12 migrations)
│   │   ├── vector_store.py        # ChromaDB embeddings
│   │   └── graph_store.py         # Neo4j graph + Claim nodes
│   ├── intelligence/              # AI features
│   │   ├── chunk_analyzer.py      # Per-chunk deep analysis
│   │   ├── semantic_chunker.py    # Topic-boundary chunking
│   │   ├── rag_engine.py          # Hybrid RAG query pipeline
│   │   ├── summarizer.py          # Map-reduce summarization
│   │   ├── epiphany_engine.py     # Cross-channel insights
│   │   ├── entity_resolver.py     # Guest NER + deduplication
│   │   ├── taxonomy_builder.py    # Topic hierarchy
│   │   ├── explorer.py            # Graph traversal + visualization
│   │   ├── query_parser.py        # Structured query syntax
│   │   └── export.py              # Multi-format export
│   ├── pipeline/                  # Orchestration
│   │   ├── orchestrator.py        # 10-stage pipeline coordinator
│   │   ├── checkpoint.py          # Crash-safe resume
│   │   └── worker.py              # Multiprocessing background worker
│   ├── utils/
│   │   ├── llm_pool.py            # Concurrent LLM batch executor
│   │   ├── retry.py               # Retry + circuit breaker
│   │   ├── health.py              # Service health checks
│   │   └── eta.py                 # Time estimates for ingestion
│   └── ui/
│       ├── app.py                 # Streamlit shell + routing
│       └── pages/                 # 11 page modules
│           ├── dashboard.py
│           ├── harvest.py
│           ├── ambiguity.py
│           ├── research.py
│           ├── guest_intel.py
│           ├── explorer.py
│           ├── pipeline_monitor.py
│           ├── logs_monitor.py
│           ├── pipeline_control.py
│           ├── data_management.py
│           └── export_center.py
├── tests/                         # Test suite (110+ tests)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── Technical_Specification.md
```

---

## 🔧 Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 4-core x86_64 | 8-core |
| RAM | 16 GB | 32 GB |
| GPU | None (CPU-only) | 8 GB VRAM (RTX 3060+) |
| Storage | 20 GB free | 50 GB SSD |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with** 🐍 Python • 🦙 Ollama • 🔍 ChromaDB • 🕸️ Neo4j • 🎯 Streamlit

</div>
