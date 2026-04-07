# Developer Guide

> Setup, testing, and development practices for knowledgeVault-YT

---

## Development Setup

### Prerequisites

```bash
# System dependencies
sudo apt install python3.11 python3.11-venv ffmpeg   # Ubuntu/Debian
brew install python@3.11 ffmpeg                       # macOS

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b-instruct-q4_K_M
ollama pull nomic-embed-text
```

### Local Environment

```bash
# Clone and enter project
git clone https://github.com/your-repo/knowledgeVault-YT.git
cd knowledgeVault-YT

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Verify installation
kvault --help
```

### Neo4j (Optional)

```bash
# Docker (recommended)
docker run -d \
    --name kvault-neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/knowledgevault \
    neo4j:5-community

# Or install locally: https://neo4j.com/download/
```

---

## Project Structure

```
src/
├── main.py              # CLI entry point (Click)
├── config.py            # Config loader (YAML + prompts)
├── ingestion/           # Pipeline stage implementations
│   ├── discovery.py     # URL parsing, yt-dlp integration
│   ├── triage.py        # Two-phase classification
│   ├── transcript.py    # youtube-transcript-api wrapper
│   └── refinement.py    # SponsorBlock + LLM normalization
├── storage/             # Data access layer
│   ├── sqlite_store.py  # Relational DB (metadata, checkpoints)
│   ├── vector_store.py  # ChromaDB (embeddings, search)
│   └── graph_store.py   # Neo4j (entity graph)
├── intelligence/        # AI/ML features
│   ├── rag_engine.py    # RAG synthesis pipeline
│   ├── entity_resolver.py # Guest NER + deduplication
│   └── export.py        # Multi-format export
├── pipeline/            # Orchestration
│   ├── orchestrator.py  # Stage coordinator
│   └── checkpoint.py    # Resume capability
└── ui/
    └── app.py           # Streamlit dashboard (6 pages)
```

---

## Running the Application

### CLI

```bash
# Full usage
kvault --help

# Harvest
kvault harvest "https://youtube.com/@channel"
kvault -v harvest "https://youtube.com/watch?v=xxxxx"  # verbose

# Query
kvault query "Tell me about quantum computing"
kvault query "AI ethics" --format json

# Diagnostics
kvault stats
kvault scans
```

### Streamlit UI

```bash
# Via CLI
kvault ui

# Or directly
streamlit run src/ui/app.py --server.port 8501
```

### Docker

```bash
# Full stack (app + Ollama + Neo4j)
docker compose up -d

# View logs
docker compose logs -f app

# Pull models into Ollama
docker compose exec ollama ollama pull llama3:8b-instruct-q4_K_M
docker compose exec ollama ollama pull nomic-embed-text

# Rebuild after code changes
docker compose up -d --build app
```

---

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_discovery.py

# Run with coverage
pytest --cov=src --cov-report=html
```

### Writing Tests

Tests live in `tests/` and follow the convention `test_{module}.py`:

```python
# tests/test_discovery.py
from src.ingestion.discovery import parse_youtube_url

def test_parse_single_video():
    result = parse_youtube_url("https://youtube.com/watch?v=dQw4w9WgXcQ")
    assert result.url_type == "video"
    assert result.video_id == "dQw4w9WgXcQ"

def test_parse_channel_handle():
    result = parse_youtube_url("https://youtube.com/@lexfridman")
    assert result.url_type == "channel"
    assert result.channel_handle == "lexfridman"
```

---

## Code Style

- **Formatter**: Ruff (configured in `pyproject.toml`)
- **Line length**: 100 characters
- **Python version**: 3.11+ (uses `list[str]` type hints, not `List[str]`)

```bash
# Lint
ruff check src/

# Format
ruff format src/

# Fix auto-fixable issues
ruff check --fix src/
```

---

## Key Design Decisions

### Why SQLite over PostgreSQL?

For MVP: zero-config, single-file, WAL mode handles concurrent reads from UI. Migration to PostgreSQL is straightforward via SQLAlchemy if multi-user support is needed later.

### Why Sliding Window over Sentence-Based Chunking?

Fixed 400-word windows with 80-word overlap provide consistent chunk sizes for embedding quality while preserving context across sentence boundaries. Sentence-based chunking produces highly variable sizes, degrading retrieval precision.

### Why Separate Triage Phases?

Phase 1 (rules) filters ~40% of videos in < 1ms, significantly reducing LLM calls. This keeps the overall triage budget under 2s/video while preserving accuracy for ambiguous cases.

### Why Neo4j is Optional?

The core value proposition (triage + semantic search) works with SQLite + ChromaDB alone. Neo4j adds cross-channel intelligence but shouldn't be a deployment blocker for MVP users.

---

## Adding a New Pipeline Stage

1. Add the stage name to `STAGE_ORDER` in `src/pipeline/checkpoint.py`
2. Create the stage method in `src/pipeline/orchestrator.py`
3. Wire it into `_resume_video()` in the orchestrator
4. Update `docs/ARCHITECTURE.md` data flow diagram

---

## Common Issues

| Issue | Solution |
|---|---|
| `ConnectionError: Ollama not running` | Start Ollama: `ollama serve` |
| `yt-dlp: HTTP Error 429` | Rate limiting — increase `rate_limit_delay` in settings |
| `Neo4j connection refused` | Start Neo4j or set `neo4j.uri` to empty in settings |
| `ChromaDB dimension mismatch` | Delete `data/chromadb/` and re-embed |
| `No transcript available` | Video may have disabled captions |
