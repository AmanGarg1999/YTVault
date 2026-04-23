# KnowledgeVault-YT: Professional Research Intelligence OS

KnowledgeVault-YT is a specialized research intelligence system that autonomously ingests, triages, and synthesizes YouTube content into a structured Knowledge Graph. Built with a privacy-first, local-only architecture, it enables high-fidelity knowledge extraction from video transcripts without cloud dependencies.

---

## ✦ System Capabilities

KnowledgeVault-YT delivers professional-grade intelligence through a robust multi-stage pipeline:

*   **Autonomous Ingestion Hub**: Discovers and harvests metadata and transcripts from channels, playlists, or individual videos with robust URL validation.
*   **Intelligent Triage Engine**: Uses a dual-phase LLM system to filter signal from noise, ensuring only knowledge-dense content enters the vault.
*   **Hybrid Three-Layer Storage**: Combines relational (SQLite), vector (ChromaDB), and graph (Neo4j) databases for comprehensive retrieval and connection discovery.
*   **Advanced Intelligence Center**: A unified command bar for hybrid semantic search, saved discoveries, and pinned research queries.
*   **Operational Resilience**: 10-stage pipeline with atomic checkpoints, fleet monitoring, and automated repair utilities.
*   **Atmospheric Design**: A premium "Nebula-Glass" aesthetic with native dark/light mode toggles and micro-animations.

---

## 📖 Documentation

| Document | Description |
|---|---|
| [User Guide](docs/guides/user_guide.md) | Comprehensive setup, workflow, and maintenance instructions. |
| [System Architecture](docs/core/system_architecture.md) | Technical design, data flow, and schema specifications. |
| [Logging & Monitoring](docs/core/logging_and_monitoring.md) | Operational guide for logs, data management, and troubleshooting. |
| [Quality Audit Report](docs/reports/AUDIT_REPORT_E2E_QUALITY.md) | Detailed findings from the Phase 3 quality remediation sprint. |
| [API Reference](docs/core/api_reference.md) | Detailed documentation of modules and internal functions. |

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Purpose |
|---|---|
| **Python 3.11+** | Core Runtime |
| **Ollama** | Local LLM inference (Llama 3.2 + Nomic Embed) |
| **Docker Compose** | Production-grade deployment (Recommended) |

### Installation (Docker)

1.  **Clone and Navigate**:
    ```bash
    git clone https://github.com/AmanGarg1999/YTVault.git
    cd YTVault
    ```
2.  **Start Services**:
    ```bash
    docker compose up -d
    ```
3.  **Access UI**:
    Open `http://localhost:8501` to access the Intelligence OS.

---

## 🏛 Architecture

The platform employs a modular architecture designed for failure isolation and consistent data integrity.

```mermaid
graph TB
    subgraph "Interface (Nebula-Glass)"
        UI["Intelligence Center"]
        OP["Operations Dashboard"]
        EX["Execution OS"]
    end

    subgraph "Orchestration"
        OR["10-Stage Pipeline Orchestrator"]
        CP["Checkpoint & Resume Manager"]
    end

    subgraph "Intelligence"
        RAG["Hybrid RAG Engine"]
        ENT["Entity & Topic Resolver"]
    end

    subgraph "Storage"
        SQL["SQLite (Metadata & Logs)"]
        VEC["ChromaDB (Semantic Vectors)"]
        GRA["Neo4j (Knowledge Graph)"]
    end

    UI --> OR
    OR --> SQL
    OR --> VEC
    OR --> GRA
    UI --> RAG
```

---

## 📦 Data Portability & Collaboration

*   **Vault Snapshots**: Generate portable `.kvvault` ZIP packages containing your entire database and intelligence logs.
*   **Mission Packages**: Export specific research missions or chat briefings for collaboration with other investigators.
*   **Obsidian Sync**: One-click generation of a Markdown-based knowledge base for Obsidian.

---

## 🔒 Security & Privacy

KnowledgeVault-YT is **Local-First**:
*   **No API Keys Required**: Uses Ollama for local LLM inference.
*   **No Cloud Tracking**: All video transcripts and analysis remain in your private volumes.
*   **Audit-Ready**: Full deletion history and soft-delete (Recycle Bin) capabilities ensure data sovereignty.

---

<div align="center">

**Built with** 🐍 Python • 🦙 Ollama • 🔍 ChromaDB • 🕸️ Neo4j • 🎯 Streamlit

</div>
