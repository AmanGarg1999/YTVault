# Configuration Reference

> Complete documentation for all configuration files in knowledgeVault-YT

---

## Configuration Files

| File | Purpose |
|---|---|
| `config/settings.yaml` | Main application config |
| `config/verified_channels.yaml` | Auto-accept channel whitelist |
| `config/prompts/triage_classifier.txt` | LLM triage system prompt |
| `config/prompts/text_normalizer.txt` | LLM normalization prompt |
| `config/prompts/rag_synthesizer.txt` | LLM RAG synthesis prompt |
| `config/prompts/entity_extractor.txt` | LLM NER extraction prompt |
| `config/prompts/topic_extractor.txt` | Topic identification prompt |
| `config/prompts/claim_extractor.txt` | Claim/assertion extraction prompt |
| `config/prompts/quote_extractor.txt` | Notable quote extraction prompt |
| `config/prompts/summarizer.txt` | Map-reduce reduce-phase prompt |
| `config/prompts/map_reduce_summarizer.txt` | Map-reduce map-phase prompt |
| `config/prompts/epiphany_briefing.txt` | Cross-channel analysis with relationship classification |

---

## `config/settings.yaml`

### `app` — Application Metadata

```yaml
app:
  name: "knowledgeVault-YT"
  version: "0.1.0"
  data_dir: "./data"      # Relative to project root
  log_level: "INFO"        # DEBUG, INFO, WARNING, ERROR
```

### `ollama` — LLM Configuration (Tiered)

```yaml
ollama:
  host: "http://localhost:11434"        # Ollama API endpoint
  triage_model: "llama3.2:3b"           # Fast: triage, NER, normalization
  normalizer_model: "llama3.2:3b"       # Fast: transcript cleaning
  deep_model: "llama3.1:8b"             # Deep: summarization, RAG, claims, quotes
  rag_model: "llama3.1:8b"              # Deep: RAG synthesis (alias for deep_model)
  embedding_model: "nomic-embed-text"   # Embedding model (768-dim)
  triage_max_tokens: 100
  normalizer_max_tokens: 2048
  rag_max_tokens: 4096
  temperature: 0.1
```

**Tiered model strategy:** Speed-critical tasks (triage, NER, normalization) use the fast 3B model. Quality-critical tasks (summarization, RAG synthesis, claim/quote extraction) use the deeper 8B model. You can set both to the same model if you only have one available.

> **Changing models:** Swap to any Ollama-compatible model. Larger models (13B, 70B) improve quality but require more VRAM.

### `sqlite` — Relational Database

```yaml
sqlite:
  path: "./data/knowledgevault.db"   # Database file path
  journal_mode: "WAL"                 # Write-Ahead Logging for concurrency
  busy_timeout: 5000                  # ms to wait on locked DB
```

### `chromadb` — Vector Database

```yaml
chromadb:
  path: "./data/chromadb"             # Persistent storage directory
  collection_name: "transcript_chunks" # Collection name
  similarity_space: "cosine"           # Distance metric
```

### `neo4j` — Graph Database

```yaml
neo4j:
  uri: "bolt://localhost:7687"    # Bolt protocol endpoint
  user: "neo4j"                    # Username
  password: "knowledgevault"       # Password (change in production!)
```

> **Disabling Neo4j:** If Neo4j is not running, the pipeline will skip graph sync gracefully. All other features continue to work.

### `ingestion` — Pipeline Tuning

```yaml
ingestion:
  concurrent_metadata_fetches: 3   # Parallel yt-dlp calls
  checkpoint_interval: 10          # Save progress every N videos
  rate_limit_delay: 1.0            # Seconds between API calls
```

| Parameter | Effect of Increasing | Effect of Decreasing |
|---|---|---|
| `concurrent_metadata_fetches` | Faster discovery, more API pressure | Slower, safer |
| `checkpoint_interval` | Less I/O overhead | More granular resume points |
| `rate_limit_delay` | Fewer rate limit errors | Faster ingestion |

### `triage` — Classification Settings

```yaml
triage:
  min_duration_seconds: 60         # Auto-reject below this
  llm_confidence_threshold: 0.7   # Below this → manual review
  knowledge_keywords:              # Auto-accept if in title
    - "lecture"
    - "tutorial"
    - "analysis"
    - "interview"
    - "podcast"
    - "documentary"
    - "explained"
    - "deep dive"
    - "masterclass"
    - "workshop"
    - "seminar"
    - "breakdown"
    - "research"
    - "history"
    - "science"
```

**Tuning tips:**
- Lower `llm_confidence_threshold` (e.g., 0.5) → fewer manual reviews, more false positives
- Raise `min_duration_seconds` (e.g., 120) → stricter filtering of short content
- Add domain-specific keywords to auto-accept relevant content

### `refinement` — Content Cleaning

```yaml
refinement:
  sponsorblock_api: "https://sponsor.ajay.app/api/skipSegments"
  sponsorblock_categories:
    - "sponsor"
    - "selfpromo"
    - "interaction"
    - "intro"
    - "outro"
  sponsorblock_timeout: 5          # API timeout (seconds)
  normalizer_chunk_size: 1000      # Words per LLM normalization call
  normalizer_chunk_overlap: 100    # Overlap between normalization chunks
```

### `chunking` — Vector Chunk Parameters

```yaml
chunking:
  strategy: "sliding_window"       # "sliding_window" or "semantic"
  window_size: 400                 # Words per chunk (sliding_window mode)
  overlap: 80                      # Overlap between chunks (sliding_window mode)
  min_chunk_size: 50               # Skip chunks smaller than this
  semantic_similarity_threshold: 0.4  # Cosine distance threshold for topic splits
```

**Chunking strategies:**
- `sliding_window` — Fixed 400-word windows with 80-word overlap. Deterministic, consistent chunk sizes.
- `semantic` — Splits at topic boundaries using sentence embedding cosine similarity. Produces topically coherent chunks. Falls back to sliding_window if Ollama embedding is unavailable.

| Parameter | Effect |
|---|---|
| `window_size: 300` | More chunks, finer granularity, more storage |
| `window_size: 500` | Fewer chunks, broader context per chunk |
| `overlap: 0` | No redundancy, may miss context at boundaries |
| `overlap: 120` | More redundancy, better boundary coverage |
| `semantic_similarity_threshold: 0.3` | More splits, smaller chunks |
| `semantic_similarity_threshold: 0.5` | Fewer splits, larger topical blocks |

### `pipeline` — Concurrency

```yaml
pipeline:
  llm_max_workers: 2    # Concurrent Ollama calls for batch triage/normalization/chunk analysis
```

Higher values speed up processing but increase GPU memory pressure. Set to 1 for low-VRAM systems.

### `rag` — Query Configuration

```yaml
rag:
  vector_top_k: 15               # Initial retrieval breadth
  rerank_top_k: 8                # Final chunks sent to LLM
  similarity_threshold: 0.65     # Minimum cosine similarity
  max_context_tokens: 4096       # Context window budget
  chunk_overlap_dedup: true      # Remove duplicate sliding-window chunks
  default_language: "en"          # Default language filter
```

### `retry` — Error Recovery

```yaml
retry:
  yt_dlp_metadata:    {max_retries: 3, backoff: [1, 5, 15]}
  transcript_fetch:   {max_retries: 3, backoff: [2, 10, 30]}
  sponsorblock_api:   {max_retries: 2, backoff: [1, 5]}
  ollama_inference:   {max_retries: 2, backoff: [5, 15]}
  chromadb_upsert:    {max_retries: 3, backoff: [1, 3, 10]}
  neo4j_write:        {max_retries: 3, backoff: [1, 3, 10]}
```

`backoff` values are in seconds. Retries use fixed delays (not exponential).

---

## `config/verified_channels.yaml`

Channels listed here bypass LLM triage (always auto-accepted).

```yaml
verified_channels:
  - id: "UCsXVk37bltHxD1rDPwtNM8Q"
    name: "Kurzgesagt"
    category: "Science"
  - id: "UCsooa4yRKGN_zEE8iknghZA"
    name: "TED-Ed"
    category: "Education"

shorts_whitelist:
  - "UCsXVk37bltHxD1rDPwtNM8Q"  # Allow Kurzgesagt shorts
```

**Finding channel IDs:**
1. Go to a channel's page on YouTube
2. View page source → search for `"channelId"`
3. Or use: `yt-dlp --print channel_id "https://youtube.com/@handle"`

---

## LLM Prompts

All prompts are in `config/prompts/` and can be edited directly:

| File | When Used | Model Tier | Tuning Focus |
|---|---|---|---|
| `triage_classifier.txt` | Phase 2 triage | Fast (3B) | Category definitions |
| `text_normalizer.txt` | Transcript cleaning | Fast (3B) | Filler patterns |
| `entity_extractor.txt` | Per-chunk NER | Fast (3B) | Role categories |
| `topic_extractor.txt` | Per-chunk topics | Fast (3B) | Topic granularity |
| `claim_extractor.txt` | Per-chunk claims | Deep (8B) | Assertion specificity |
| `quote_extractor.txt` | Per-chunk quotes | Deep (8B) | Quote memorability |
| `rag_synthesizer.txt` | RAG query answering | Deep (8B) | Citation format, tone |
| `summarizer.txt` | Map-reduce reduce phase | Deep (8B) | Summary structure |
| `map_reduce_summarizer.txt` | Map-reduce map phase | Deep (8B) | Bullet point detail |
| `epiphany_briefing.txt` | Cross-channel analysis | Deep (8B) | Relationship classification |

> **Important:** Prompts that request JSON output must instruct the LLM to respond with valid JSON only. Changing the response format requires updating the corresponding parser in the Python code.
