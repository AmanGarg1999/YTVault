# KnowledgeVault-YT: User Guide

Welcome to KnowledgeVault-YT, a local-first research intelligence system that transforms YouTube content into a structured Knowledge Graph. This guide provides comprehensive instructions for setting up and using the platform’s features.

---

## 1. Getting Started

### Prerequisites

| Requirement | Purpose |
|---|---|
| Python 3.11+ | Application runtime |
| Ollama | Local LLM inference engine |
| yt-dlp | YouTube metadata extraction |
| Neo4j 5.x | Knowledge graph storage (optional) |
| Docker | Recommended for containerized deployment |

### Installation

#### Option 1: Docker Compose (Recommended)

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-repo/knowledgeVault-YT.git
    cd knowledgeVault-YT
    ```
2.  Start the services:
    ```bash
    docker compose up -d
    ```
3.  Pull the required LLM models:
    ```bash
    docker compose exec ollama ollama pull llama3.2:3b
    docker compose exec ollama ollama pull llama3.1:8b
    docker compose exec ollama ollama pull nomic-embed-text
    ```
4.  Access the UI at `http://localhost:8501`.

#### Option 2: Local Installation

1.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/Mac
    ```
2.  Install dependencies:
    ```bash
    pip install -e ".[dev]"
    ```
3.  Ensure Ollama is running and models are downloaded locally.
4.  Start the UI:
    ```bash
    kvault ui
    ```

---

## 2. Interface Overview

The Streamlit dashboard is organized into several key modules:

*   **Dashboard**: A high-level overview of system metrics, active jobs, and the Knowledge Density Leaderboard.
*   **Harvest Manager**: The entry point for starting new content ingestion jobs via YouTube URLs.
*   **Ambiguity Queue**: A manual review interface for videos that the automated triage system couldn't confidently classify.
*   **Research Console**: The primary interface for querying the knowledge vault using natural language.
*   **Pipeline Monitor**: Real-time tracking of the multi-stage ingestion process.
*   **Pipeline Control**: A central hub for pausing, resuming, or stopping active scans.
*   **Data Management**: Tools for safely deleting video or channel data with a full audit trail.
*   **Logs & Activity**: A comprehensive feed of pipeline events and error details for troubleshooting.

---

## 3. Core Workflows

### 3.1 Ingesting Content (Harvesting)

To add content to your vault:
1.  Navigate to the **Harvest Manager**.
2.  Enter a YouTube URL (Video, Playlist, or Channel).
3.  Click **Start Harvest**.
4.  The system will begin the 10-stage ingestion process. You can track progress in the **Pipeline Monitor**.

### 3.2 Managing the Ingestion Pipeline

The **Pipeline Control Center** allows you to manage active scans:
*   **Pause**: Stops the pipeline at the next safe point (between videos).
*   **Resume**: Continues a paused scan from where it left off.
*   **Remove from Queue**: Skip specific videos before they enter the processing pipeline.

### 3.3 Research and Synthesis

The **Research Console** uses a Hybrid RAG (Retrieval-Augmented Generation) engine:
1.  Enter a research question in natural language.
2.  The system retrieves relevant segments from the vector and text stores.
3.  The LLM synthesizes a response with citations and clickable timestamp links.
4.  You can explore related entities and topics directly from the results.

---

## 4. Operational Maintenance

### 4.1 Data Deletion

The **Data Management** page provides a safe way to remove content:
*   **Preview**: Before deleting, you can see exactly which chunks, claims, and quotes will be removed.
*   **Cascade**: Deleting a video removes all its associated transcript data and metadata from the relational store.
*   **Audit Trail**: All deletions are logged for accountability.

### 4.2 Logging and Troubleshooting

If you encounter issues:
1.  Check the **Logs & Activity** page for ERROR or WARNING events.
2.  Expand error logs to see the full stack trace and context (Stage, Video ID, Scan ID).
3.  Use the **Error Analysis** dashboard to identify recurring patterns.

---

## 5. Advanced Usage

### CLI Reference

KnowledgeVault-YT provides a robust CLI for power users:

```bash
# Harvest a channel
kvault harvest "https://youtube.com/@channel"

# Query the vault
kvault query "What is the impact of LLMs on software engineering?"

# View system statistics
kvault stats

# List all scans and their status
kvault scans

# Check health of external services (Ollama, Neo4j)
kvault health
```

### Configuration

Configuration settings are managed in `config/settings.yaml`. You can tune triage thresholds, chunking strategies, and LLM concurrency levels here.
