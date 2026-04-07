1. Functional Requirements (FR)
These define the specific behaviors and features the system must provide.

1.1 Data Ingestion & Extraction
Source Input: Support for individual YouTube URLs, Playlist URLs, and Channel Homepages.

Discovery Engine: For channel-level inputs, the system must scrape the "Videos" tab to build a queue of all video IDs.

Metadata Harvesting: Extract Title, Description, Duration, Upload Date, View Count, Tags, and Channel Name using yt-dlp.

Transcript Acquisition: * Fetch manual English transcripts first.

Fall back to auto-generated English transcripts.

If no English version exists, store the original language code and flag for translation.

No Media Download: Strictly forbid downloading .mp4 or .mp3 files to save bandwidth and local storage.

1.2 The Triage Engine (Filtering)
Metadata Classifier: Analyze metadata (Title/Desc) via a local LLM to categorize content into Knowledge-Dense (History, Tech, Science, Podcast) or Noise (Vlog, Meme, Comedy).

Rule-Based Sorting: * Auto-Reject: Videos under a specific duration (e.g., < 60 seconds) unless part of a "Shorts Insight" whitelist.

Auto-Accept: Videos containing specific educational keywords or from "Verified Knowledge" channels.

Ambiguity Management: Any video failing clear classification must be routed to a Manual Review Queue with a "Pending" status in the DB.

1.3 Content Refinement
Sponsor Filtering: Integrate with SponsorBlock API (or local regex) to identify and strip segments categorized as "Sponsor," "Intro," or "Interaction Reminder."

Text Normalization: Remove verbal fillers ("um," "uh," "like") and fix transcript punctuation using a lightweight local model (e.g., DeepFilter or Llama-3-8B-Instruct).

1.4 Search & Intelligence
Semantic Search: Allow natural language queries (e.g., "What did Guest X say about the future of Agri-tech?") across the entire database.

Cross-Channel Guest Mapping: Automatically identify if a specific entity (Guest) appears on multiple channels and link their discussions.

Data Export: Capability to export research insights in Markdown, JSON, or CSV formats.

2. Non-Functional Requirements (NFR)
These define the quality attributes of the system.

Local-First Privacy: All processing (LLM inference, Vector indexing) must happen on local hardware (e.g., via Ollama/LocalStack).

Zero-Cost Scaling: Utilize only free, open-source libraries and APIs. No dependency on paid OpenAI/Claude API keys.

Resilience: The system must implement a "Checkpoint" feature—if a channel scan of 500 videos is interrupted, it must resume from the last unprocessed ID.

Language Integrity: The DB must maintain a language_iso tag for every entry to ensure search results are accurate to the source material.

Performance: Triage analysis (metadata-only) should take < 2 seconds per video.

3. Data Requirements (Schema & Storage)
To support complex research, you need a Hybrid Database approach:

3.1 Relational Layer (PostgreSQL / SQLite)
Channels Table: Name, URL, Description, Category.

Videos Table: Title, URL, Duration, Metadata, Triage_Status (Processed/Skipped/Pending).

Guests Table: Entity Name, Bio, Mention Count.

3.2 Vector Layer (ChromaDB / Qdrant)
Chunks Table: Stores 300-500 word "windows" of cleaned transcripts with associated embeddings for semantic retrieval.

3.3 Graph Layer (Neo4j - Optional but Recommended)
Nodes: Video, Channel, Topic, Guest.

Edges: (Guest)-[APPEARED_IN]->(Video), (Video)-[DISCUSSES]->(Topic).

4. Interaction Requirements (User Experience)
Command Center: A simple UI (built-in Streamlit or a local web app) to:

Paste a Channel URL to start the "Harvest."

View the "Ambiguity Queue" to approve/reject videos.

Input a Research Question to get a synthesized answer with citations (video timestamps).

Status Dashboard: Real-time progress bar showing: Videos Discovered -> Triage Passed -> Transcript Cleaned -> Indexed.