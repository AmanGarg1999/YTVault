"""
SQLite storage layer for knowledgeVault-YT.

Manages the relational database: Channels, Videos, Guests,
Guest Appearances, Transcript Chunks, and Scan Checkpoints.
"""

import json
import logging
import sqlite3
import uuid
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class ChatSession:
    session_id: str
    name: str
    created_at: str = ""
    last_active: str = ""

@dataclass
class ChatMessage:
    message_id: str
    session_id: str
    role: str # 'user' or 'assistant'
    content: str
    suggested_json: str = "[]"
    citations_json: str = "[]"
    created_at: str = ""

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Channel:
    channel_id: str
    name: str
    url: str
    description: str = ""
    category: str = "UNCLASSIFIED"
    language_iso: str = "en"
    discovered_at: str = ""
    last_scanned_at: str = ""
    total_videos: int = 0
    processed_videos: int = 0
    follower_count: int = 0
    handle: str = ""
    thumbnail_url: str = ""
    is_verified: bool = False


@dataclass
class Video:
    video_id: str
    channel_id: str
    title: str
    url: str
    description: str = ""
    duration_seconds: int = 0
    upload_date: str = ""
    view_count: int = 0
    tags: list[str] = field(default_factory=list)
    language_iso: str = "en"
    triage_status: str = "DISCOVERED"
    triage_reason: str = ""
    triage_confidence: float = 0.0
    transcript_strategy: str = ""
    needs_translation: bool = False
    translated_text_stored: bool = False
    checkpoint_stage: str = "METADATA_HARVESTED"
    locked_by_scan_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    like_count: int = 0
    comment_count: int = 0
    category: str = ""
    thumbnail_url: str = ""
    heatmap_json: str = "[]"
    is_tutorial: bool = False

    def __post_init__(self):
        """Handle potential data migration or extra fields."""
        pass

    @classmethod
    def from_row(cls, row: dict):
        """Create a Video from a database row, ignoring extra fields."""
        # Get the fields of the dataclass
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        
        # Prepare data by popping tags_json and cleaning up
        d = dict(row)
        if "tags_json" in d:
            d["tags"] = json.loads(d.pop("tags_json", "[]") or "[]")
        
        # Filter only valid fields
        filtered_d = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered_d)


@dataclass
class Guest:
    guest_id: int = 0
    canonical_name: str = ""
    aliases: list[str] = field(default_factory=list)
    bio: str = ""
    entity_type: str = "PERSON"
    mention_count: int = 0
    first_seen: str = ""
    last_seen: str = ""


@dataclass
class TranscriptChunk:
    chunk_id: str = ""
    video_id: str = ""
    chunk_index: int = 0
    raw_text: str = ""
    cleaned_text: str = ""
    word_count: int = 0
    start_timestamp: float = 0.0
    end_timestamp: float = 0.0
    topics_json: str = "[]"
    entities_json: str = "[]"
    claims_json: str = "[]"
    quotes_json: str = "[]"
    is_high_attention: bool = False
    content_hash: str = ""  # Fixed: Added to match schema migration v20


@dataclass
class ScanCheckpoint:
    scan_id: str = ""
    source_url: str = ""
    scan_type: str = ""
    total_discovered: int = 0
    total_processed: int = 0
    last_video_id: str = ""
    status: str = "IN_PROGRESS"
    started_at: str = ""
    updated_at: str = ""
    id: int = 0  # Auto-increment PK from SQL — must be present for **dict(row)
    channel_name: str = "" # Populated via JOIN in get_active_scans
    
@dataclass
class VideoSummary:
    video_id: str
    summary_text: str = ""
    topics_json: str = "[]"
    takeaways_json: str = "[]"
    entities_json: str = "[]"
    references_json: str = "[]"
    timeline_json: str = "[]"
    last_updated: str = ""


@dataclass
class Claim:
    """An extracted claim/assertion from a transcript."""
    claim_id: int = 0
    video_id: str = ""
    chunk_id: str = ""
    speaker: str = ""
    claim_text: str = ""
    topic: str = ""
    timestamp: float = 0.0
    confidence: float = 0.0
    corroboration_count: int = 1
    cluster_id: Optional[str] = None
    created_at: str = ""


@dataclass
class Quote:
    """A notable quote extracted from a transcript."""
    quote_id: int = 0
    video_id: str = ""
    chunk_id: str = ""
    speaker: str = ""
    quote_text: str = ""
    topic: str = ""
    timestamp: float = 0.0
    created_at: str = ""


@dataclass
class ActionableBlueprint:
    video_id: str
    steps_json: str = "[]"
    created_at: str = ""


@dataclass
class ExpertClash:
    clash_id: int = 0
    topic: str = ""
    expert_a: str = ""
    expert_b: str = ""
    claim_a: str = ""
    claim_b: str = ""
    source_a: Optional[str] = None
    source_b: Optional[str] = None
    created_at: str = ""


@dataclass
class VideoSentiment:
    video_id: str
    chunk_id: Optional[str] = None
    score: float = 0.0
    label: str = ""
    created_at: str = ""


@dataclass
class ExternalCitation:
    citation_id: int = 0
    video_id: str = ""
    name: str = ""
    url: str = ""
    type: str = ""
    created_at: str = ""


@dataclass
class ThematicBridge:
    bridge_id: int = 0
    topic_a: str = ""
    topic_b: str = ""
    insight: str = ""
    llm_model: str = ""
    created_at: str = ""


@dataclass
class ResearchReport:
    report_id: int = 0
    query: str = ""
    title: str = ""
    file_path: str = ""
    summary: str = ""
    sources_json: str = "[]"
    created_at: str = ""


@dataclass
class MonitoredChannel:
    channel_id: str
    last_brief_at: Optional[str] = None
    created_at: str = ""


@dataclass
class WeeklyBrief:
    brief_id: int = 0
    channel_ids_json: str = "[]"
    content: str = ""
    created_at: str = ""




@dataclass
class PipelineLog:
    """Pipeline activity log entry."""
    log_id: int = 0
    scan_id: str = ""
    video_id: str = ""
    channel_id: str = ""
    level: str = "INFO"  # INFO, WARNING, ERROR, DEBUG, SUCCESS
    stage: str = ""  # DISCOVERY, TRIAGE, TRANSCRIPT, REFINEMENT, CHUNKING, EMBEDDING, etc.
    message: str = ""
    error_detail: str = ""  # Full traceback if ERROR
    timestamp: str = ""
    created_at: str = ""


@dataclass
class PipelineControl:
    """Pipeline control state (pause/resume/stop flags)."""
    control_id: int = 0
    scan_id: str = ""
    status: str = "RUNNING"  # RUNNING, PAUSED, STOPPING, STOPPED
    pause_reason: str = ""
    resumed_at: str = ""
    stopped_at: str = ""
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# SQL Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS channels (
    channel_id    TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    url           TEXT NOT NULL,
    description   TEXT DEFAULT '',
    category      TEXT DEFAULT 'UNCLASSIFIED',
    language_iso  TEXT DEFAULT 'en',
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_scanned_at DATETIME,
    total_videos  INTEGER DEFAULT 0,
    processed_videos INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS videos (
    video_id         TEXT PRIMARY KEY,
    channel_id       TEXT REFERENCES channels(channel_id),
    title            TEXT NOT NULL,
    url              TEXT NOT NULL,
    description      TEXT DEFAULT '',
    duration_seconds INTEGER DEFAULT 0,
    upload_date      DATE,
    view_count       INTEGER DEFAULT 0,
    tags_json        TEXT DEFAULT '[]',
    language_iso     TEXT DEFAULT 'en',
    triage_status    TEXT DEFAULT 'DISCOVERED',
    triage_reason    TEXT DEFAULT '',
    triage_confidence REAL DEFAULT 0.0,
    transcript_strategy TEXT DEFAULT '',
    needs_translation BOOLEAN DEFAULT 0,
    checkpoint_stage TEXT DEFAULT 'METADATA_HARVESTED',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_videos_triage ON videos(triage_status);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_checkpoint ON videos(checkpoint_stage);

CREATE TABLE IF NOT EXISTS guests (
    guest_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    aliases_json   TEXT DEFAULT '[]',
    bio            TEXT DEFAULT '',
    entity_type    TEXT DEFAULT 'PERSON',
    mention_count  INTEGER DEFAULT 0,
    first_seen     DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS guest_appearances (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id       INTEGER REFERENCES guests(guest_id),
    video_id       TEXT REFERENCES videos(video_id),
    context_snippet TEXT DEFAULT '',
    start_timestamp REAL DEFAULT 0.0,
    end_timestamp   REAL DEFAULT 0.0,
    UNIQUE(guest_id, video_id, start_timestamp)
);

CREATE TABLE IF NOT EXISTS transcript_chunks (
    chunk_id    TEXT PRIMARY KEY,
    video_id    TEXT REFERENCES videos(video_id),
    chunk_index INTEGER DEFAULT 0,
    raw_text    TEXT DEFAULT '',
    cleaned_text TEXT DEFAULT '',
    word_count  INTEGER DEFAULT 0,
    start_timestamp REAL DEFAULT 0.0,
    end_timestamp   REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_chunks_video ON transcript_chunks(video_id);

CREATE TABLE IF NOT EXISTS scan_checkpoints (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id          TEXT NOT NULL UNIQUE,
    source_url       TEXT NOT NULL,
    scan_type        TEXT NOT NULL,
    total_discovered INTEGER DEFAULT 0,
    total_processed  INTEGER DEFAULT 0,
    last_video_id    TEXT DEFAULT '',
    status           TEXT DEFAULT 'IN_PROGRESS',
    started_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""

# Schema migrations: list of (version, sql) tuples applied sequentially.
# Add new migrations at the end with the next version number.
SCHEMA_MIGRATIONS = [
    # Version 1: base schema (created by SCHEMA_SQL above)
    (1, "INSERT OR IGNORE INTO schema_version (version) VALUES (1);"),
    # Version 2: FTS5 full-text index on transcript chunks
    (2, """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
        USING fts5(
            chunk_id,
            video_id,
            content,
            content_rowid='rowid'
        );
    """),
    # Version 3: Auto-sync triggers for FTS5 table
    (3, """
        CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON transcript_chunks BEGIN
            INSERT INTO chunks_fts(rowid, chunk_id, video_id, content)
            VALUES (new.rowid, new.chunk_id, new.video_id, COALESCE(new.cleaned_text, new.raw_text));
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON transcript_chunks BEGIN
            DELETE FROM chunks_fts WHERE rowid = old.rowid;
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE ON transcript_chunks BEGIN
            DELETE FROM chunks_fts WHERE rowid = old.rowid;
            INSERT INTO chunks_fts(rowid, chunk_id, video_id, content)
            VALUES (new.rowid, new.chunk_id, new.video_id, COALESCE(new.cleaned_text, new.raw_text));
        END;
    """),
    # Version 4: Video Summaries and Deep Intelligence Cache
    (4, """
        CREATE TABLE IF NOT EXISTS video_summaries (
            video_id        TEXT PRIMARY KEY REFERENCES videos(video_id),
            summary_text    TEXT DEFAULT '',
            topics_json     TEXT DEFAULT '[]',
            takeaways_json  TEXT DEFAULT '[]',
            entities_json   TEXT DEFAULT '[]',
            last_updated    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """),
    # Version 5: Video Summary Expansion (References and Timeline)
    (5, """
        ALTER TABLE video_summaries ADD COLUMN references_json TEXT DEFAULT '[]';
        ALTER TABLE video_summaries ADD COLUMN timeline_json TEXT DEFAULT '[]';
    """),
    # Version 6: Dedicated pipeline temp state (replaces overloaded transcript_chunks buffer)
    (6, """
        CREATE TABLE IF NOT EXISTS pipeline_temp_state (
            video_id      TEXT PRIMARY KEY,
            raw_text      TEXT DEFAULT '',
            segments_json TEXT DEFAULT '[]',
            cleaned_text  TEXT DEFAULT '',
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """),
    # Version 7: Per-chunk analysis columns (topics, entities, claims, quotes)
    (7, """
        ALTER TABLE transcript_chunks ADD COLUMN topics_json TEXT DEFAULT '[]';
        ALTER TABLE transcript_chunks ADD COLUMN entities_json TEXT DEFAULT '[]';
        ALTER TABLE transcript_chunks ADD COLUMN claims_json TEXT DEFAULT '[]';
        ALTER TABLE transcript_chunks ADD COLUMN quotes_json TEXT DEFAULT '[]';
    """),
    # Version 8: Claims table for structured assertion tracking
    (8, """
        CREATE TABLE IF NOT EXISTS claims (
            claim_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    TEXT REFERENCES videos(video_id),
            chunk_id    TEXT REFERENCES transcript_chunks(chunk_id),
            speaker     TEXT DEFAULT '',
            claim_text  TEXT NOT NULL,
            topic       TEXT DEFAULT '',
            timestamp   REAL DEFAULT 0.0,
            confidence  REAL DEFAULT 0.0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_claims_video ON claims(video_id);
        CREATE INDEX IF NOT EXISTS idx_claims_speaker ON claims(speaker);
        CREATE INDEX IF NOT EXISTS idx_claims_topic ON claims(topic);
    """),
    # Version 9: Quotes table for notable quotations
    (9, """
        CREATE TABLE IF NOT EXISTS quotes (
            quote_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    TEXT REFERENCES videos(video_id),
            chunk_id    TEXT REFERENCES transcript_chunks(chunk_id),
            speaker     TEXT DEFAULT '',
            quote_text  TEXT NOT NULL,
            topic       TEXT DEFAULT '',
            timestamp   REAL DEFAULT 0.0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_quotes_video ON quotes(video_id);
        CREATE INDEX IF NOT EXISTS idx_quotes_speaker ON quotes(speaker);
    """),
    # Version 10: Pipeline activity logging table
    (10, """
        CREATE TABLE IF NOT EXISTS pipeline_logs (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id     TEXT DEFAULT '',
            video_id    TEXT DEFAULT '',
            channel_id  TEXT DEFAULT '',
            level       TEXT DEFAULT 'INFO',
            stage       TEXT DEFAULT '',
            message     TEXT NOT NULL,
            error_detail TEXT DEFAULT '',
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_logs_scan ON pipeline_logs(scan_id);
        CREATE INDEX IF NOT EXISTS idx_logs_video ON pipeline_logs(video_id);
        CREATE INDEX IF NOT EXISTS idx_logs_channel ON pipeline_logs(channel_id);
        CREATE INDEX IF NOT EXISTS idx_logs_level ON pipeline_logs(level);
        CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON pipeline_logs(timestamp);
    """),
    # Version 11: Pipeline control state table
    (11, """
        CREATE TABLE IF NOT EXISTS pipeline_control (
            control_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id     TEXT NOT NULL UNIQUE,
            status      TEXT DEFAULT 'RUNNING',
            pause_reason TEXT DEFAULT '',
            resumed_at  DATETIME,
            stopped_at  DATETIME,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_control_scan ON pipeline_control(scan_id);
        CREATE INDEX IF NOT EXISTS idx_control_status ON pipeline_control(status);
    """),
    # Version 12: Video deletion tracking
    (12, """
        CREATE TABLE IF NOT EXISTS deletion_history (
            deletion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            deletion_type TEXT NOT NULL,
            channel_id TEXT DEFAULT '',
            video_id TEXT DEFAULT '',
            deleted_by TEXT DEFAULT 'user',
            reason TEXT DEFAULT '',
            data_deleted TEXT DEFAULT '[]',
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_deletion_history ON deletion_history(deleted_at);
    """),
    # Version 13: Multilingual support - add translated text storage
    (13, """
        ALTER TABLE pipeline_temp_state ADD COLUMN translated_text TEXT DEFAULT '';
        ALTER TABLE videos ADD COLUMN translated_text_stored BOOLEAN DEFAULT 0;
    """),
    # Version 14: Enhanced metadata (likes, comments, subs, categories, thumbnails, heatmaps)
    (14, """
        ALTER TABLE channels ADD COLUMN follower_count INTEGER DEFAULT 0;
        ALTER TABLE channels ADD COLUMN handle TEXT DEFAULT '';
        ALTER TABLE channels ADD COLUMN thumbnail_url TEXT DEFAULT '';
        ALTER TABLE channels ADD COLUMN is_verified BOOLEAN DEFAULT 0;
        ALTER TABLE videos ADD COLUMN like_count INTEGER DEFAULT 0;
        ALTER TABLE videos ADD COLUMN comment_count INTEGER DEFAULT 0;
        ALTER TABLE videos ADD COLUMN category TEXT DEFAULT '';
        ALTER TABLE videos ADD COLUMN thumbnail_url TEXT DEFAULT '';
        ALTER TABLE videos ADD COLUMN heatmap_json TEXT DEFAULT '[]';
    """),
    # Version 15: Historical performance tracking
    (15, """
        CREATE TABLE IF NOT EXISTS video_stats_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT REFERENCES videos(video_id),
            snapshot_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            view_count INTEGER,
            like_count INTEGER,
            comment_count INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_stats_history_video ON video_stats_history(video_id);
    """),
    # Version 16: Advanced Intelligence Suite (Clashes, Blueprints, Sentiment, Citations)
    (16, """
        CREATE TABLE IF NOT EXISTS actionable_blueprints (
            video_id    TEXT PRIMARY KEY REFERENCES videos(video_id),
            steps_json  TEXT DEFAULT '[]',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS expert_clashes (
            clash_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            topic       TEXT NOT NULL,
            expert_a    TEXT NOT NULL,
            expert_b    TEXT NOT NULL,
            claim_a     TEXT NOT NULL,
            claim_b     TEXT NOT NULL,
            source_a    TEXT REFERENCES videos(video_id),
            source_b    TEXT REFERENCES videos(video_id),
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS video_sentiment (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    TEXT REFERENCES videos(video_id),
            chunk_id    TEXT REFERENCES transcript_chunks(chunk_id),
            score       REAL DEFAULT 0.0,
            label       TEXT DEFAULT 'Neutral',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS external_citations (
            citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    TEXT REFERENCES videos(video_id),
            name        TEXT NOT NULL,
            url         TEXT DEFAULT '',
            type        TEXT DEFAULT 'OTHER',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_clashes_topic ON expert_clashes(topic);
        CREATE INDEX IF NOT EXISTS idx_sentiment_video ON video_sentiment(video_id);
        CREATE INDEX IF NOT EXISTS idx_citations_video ON external_citations(video_id);
    """),
    # Version 17: Phase 3 Intelligence (Bridges, Research Reports)
    (17, """
        CREATE TABLE IF NOT EXISTS thematic_bridges (
            bridge_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_a     TEXT NOT NULL,
            topic_b     TEXT NOT NULL,
            insight     TEXT NOT NULL,
            llm_model   TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS research_reports (
            report_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            query       TEXT NOT NULL,
            title       TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            summary     TEXT,
            sources_json TEXT DEFAULT '[]',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_bridges_topics ON thematic_bridges(topic_a, topic_b);
    """),
    # Version 18: Resume locking for concurrent scans
    (18, """
        ALTER TABLE videos ADD COLUMN locked_by_scan_id TEXT DEFAULT NULL;
        CREATE INDEX IF NOT EXISTS idx_videos_locked ON videos(locked_by_scan_id);
    """),
    # Version 19: P0-A — Sync outbox for saga-based triple-store atomicity
    (19, """
        CREATE TABLE IF NOT EXISTS sync_outbox (
            video_id      TEXT PRIMARY KEY REFERENCES videos(video_id),
            chroma_done   BOOLEAN DEFAULT 0,
            neo4j_done    BOOLEAN DEFAULT 0,
            retry_count   INTEGER DEFAULT 0,
            last_error    TEXT DEFAULT '',
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_outbox_pending ON sync_outbox(chroma_done, neo4j_done);
    """),
    # Version 20: P0-B — Content hash per chunk to skip re-embedding unchanged content
    (20, """
        ALTER TABLE transcript_chunks ADD COLUMN content_hash TEXT DEFAULT '';
        CREATE INDEX IF NOT EXISTS idx_chunks_hash ON transcript_chunks(content_hash);
    """),
    # Version 21: P1-B — High-attention flag for heatmap correlation
    (21, """
        ALTER TABLE transcript_chunks ADD COLUMN is_high_attention BOOLEAN DEFAULT 0;
        CREATE INDEX IF NOT EXISTS idx_chunks_attention ON transcript_chunks(is_high_attention);
    """),
    # Version 22: P1-E — Claim Corroboration & Clustering
    (22, """
        ALTER TABLE claims ADD COLUMN cluster_id TEXT DEFAULT NULL;
        CREATE INDEX IF NOT EXISTS idx_claims_cluster ON claims(cluster_id);
    """),
    # Version 23: Tutorial classification for Blueprints
    (23, """
        ALTER TABLE videos ADD COLUMN is_tutorial BOOLEAN DEFAULT 0;
    """),
    # Version 24: User-driven retry queue for failures
    (24, """
        CREATE TABLE IF NOT EXISTS user_queue (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL, -- 'URL', 'VIDEO_ID'
            item_value TEXT NOT NULL,
            failure_reason TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_user_queue_type ON user_queue(item_type);
    """),
    # Version 25: Phase 4 Intelligence (Monitored Channels, Weekly Briefs)
    (25, """
        CREATE TABLE IF NOT EXISTS monitored_channels (
            channel_id    TEXT PRIMARY KEY REFERENCES channels(channel_id),
            last_brief_at DATETIME,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS weekly_briefs (
            brief_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_ids_json TEXT DEFAULT '[]',
            content       TEXT NOT NULL,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """),
    # Version 26: Research Chat Hub Persistence
    (26, """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id  TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_active DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id  TEXT PRIMARY KEY,
            session_id  TEXT REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            suggested_json TEXT DEFAULT '[]',
            citations_json TEXT DEFAULT '[]',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
    """),
]


class SQLiteStore:
    """SQLite database manager for knowledgeVault-YT.

    Supports context manager protocol for automatic cleanup:
        with SQLiteStore(path) as db:
            db.insert_video(...)
    
    Features:
        - WAL mode for concurrent access
        - Connection pooling via check_same_thread=False
        - Automatic retry on database locked errors
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            db_path, 
            check_same_thread=False,
            timeout=30.0  # 30-second timeout for locked DB
        )
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._verify_wal_mode()
        self._run_migrations()
        logger.info(f"SQLite store initialized: {db_path}")

    def _verify_wal_mode(self):
        """Verify WAL mode is enabled for concurrent access."""
        try:
            result = self.conn.execute("PRAGMA journal_mode").fetchone()
            mode = result[0] if result else "unknown"
            if mode.upper() != "WAL":
                logger.warning(f"Expected WAL mode, got {mode}. Enabling WAL...")
                self.conn.execute("PRAGMA journal_mode = WAL")
                self.conn.commit()
                logger.info("WAL mode enabled successfully")
            else:
                logger.debug(f"WAL mode verified: {mode}")
        except Exception as e:
            logger.warning(f"Could not verify WAL mode: {e}")

    def _init_schema(self):
        """Create all tables if they don't exist."""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def _run_migrations(self):
        """Apply pending schema migrations."""
        current = self._get_schema_version()
        pending = [(v, sql) for v, sql in SCHEMA_MIGRATIONS if v > current]
        for version, sql in sorted(pending):
            try:
                self.conn.executescript(sql)
                self.conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (version,),
                )
                self.conn.commit()
                logger.info(f"Applied migration v{version}")
                
                # Backfill FTS5 after its version is applied
                if version == 2:
                    self.populate_fts_index()
            except Exception as e:
                logger.error(f"Migration v{version} failed: {e}")
                raise

    def _get_schema_version(self) -> int:
        """Get current schema version (0 if no migrations applied)."""
        try:
            row = self.conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            return row[0] if row and row[0] else 0
        except Exception:
            return 0

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def execute(self, sql: str, params: tuple = ()):
        """Execute a SQL query directly on the connection."""
        return self.conn.execute(sql, params)

    def commit(self):
        """Commit the current transaction."""
        self.conn.commit()

    # -------------------------------------------------------------------
    # Channels
    # -------------------------------------------------------------------

    def upsert_channel(self, channel: Channel) -> None:
        """Insert or update a channel record."""
        try:
            self.conn.execute(
                """INSERT INTO channels (channel_id, name, url, description, category,
                       language_iso, discovered_at, total_videos, follower_count,
                       handle, thumbnail_url, is_verified)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
                   ON CONFLICT(channel_id) DO UPDATE SET
                       name = excluded.name,
                       description = excluded.description,
                       total_videos = excluded.total_videos,
                       follower_count = excluded.follower_count,
                       handle = excluded.handle,
                       thumbnail_url = excluded.thumbnail_url,
                       is_verified = excluded.is_verified,
                       last_scanned_at = CURRENT_TIMESTAMP""",
                (channel.channel_id, channel.name, channel.url,
                 channel.description, channel.category,
                 channel.language_iso, channel.total_videos,
                 channel.follower_count, channel.handle,
                 channel.thumbnail_url, channel.is_verified),
            )
            self.conn.commit()
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                import time
                logger.debug("Database locked during upsert_channel, retrying...")
                time.sleep(0.5)
                self.conn.commit()
            else:
                raise

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """Get a channel by ID."""
        row = self.conn.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        if row is None:
            return None
        return Channel(**dict(row))

    def get_all_channels(self) -> list[Channel]:
        """Get all channels."""
        rows = self.conn.execute("SELECT * FROM channels ORDER BY name").fetchall()
        return [Channel(**dict(r)) for r in rows]

    # -------------------------------------------------------------------
    # Videos
    # -------------------------------------------------------------------

    def insert_video(self, video: Video) -> bool:
        """Insert a video, returns True if inserted, False if duplicate."""
        try:
            self.conn.execute(
                """INSERT INTO videos (video_id, channel_id, title, url, description,
                       duration_seconds, upload_date, view_count, tags_json,
                       language_iso, triage_status, checkpoint_stage,
                       like_count, comment_count, category, thumbnail_url, heatmap_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED', 'METADATA_HARVESTED',
                           ?, ?, ?, ?, ?)
                   ON CONFLICT(video_id) DO UPDATE SET
                       view_count = excluded.view_count,
                       like_count = excluded.like_count,
                       comment_count = excluded.comment_count,
                       heatmap_json = excluded.heatmap_json,
                       thumbnail_url = excluded.thumbnail_url,
                       updated_at = CURRENT_TIMESTAMP""",
                (video.video_id, video.channel_id, video.title, video.url,
                 video.description, video.duration_seconds, video.upload_date,
                 video.view_count, json.dumps(video.tags),
                 video.language_iso, video.like_count, video.comment_count,
                 video.category, video.thumbnail_url, video.heatmap_json),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error upserting video {video.video_id}: {e}")
            self.conn.rollback()
            return False

    def get_video(self, video_id: str) -> Optional[Video]:
        """Get a video by ID."""
        row = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row is None:
            return None
        return Video.from_row(row)

    def record_stats_snapshot(
        self, video_id: str, view_count: int, like_count: int, comment_count: int
    ):
        """No-op: Historical engagement tracking disabled."""
        pass

    def get_videos_by_status(self, status: str, limit: int = 100) -> list[Video]:
        """Get videos by triage status."""
        rows = self.conn.execute(
            "SELECT * FROM videos WHERE triage_status = ? ORDER BY created_at LIMIT ?",
            (status, limit),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def get_videos_by_status_sorted(
        self, status: str, order_by: str = "created_at DESC", limit: int = 100
    ) -> list[Video]:
        """Get videos by triage status with custom sort order."""
        rows = self.conn.execute(
            f"SELECT * FROM videos WHERE triage_status = ? ORDER BY {order_by} LIMIT ?",
            (status, limit),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def get_videos_by_channel(self, channel_id: str, limit: int = None) -> list[Video]:
        """Get all videos for a channel, optionally limited."""
        query = "SELECT * FROM videos WHERE channel_id = ? ORDER BY upload_date DESC"
        params = (channel_id,)
        if limit:
            query += f" LIMIT {limit}"
        
        rows = self.conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def update_triage_status(
        self, video_id: str, status: str, reason: str = "", confidence: float = 0.0, is_tutorial: bool = False
    ) -> None:
        """Update a video's triage status and tutorial classification."""
        self.conn.execute(
            """UPDATE videos
               SET triage_status = ?, triage_reason = ?, triage_confidence = ?,
                   is_tutorial = ?, updated_at = CURRENT_TIMESTAMP
               WHERE video_id = ?""",
            (status, reason, confidence, int(is_tutorial), video_id),
        )
        self.conn.commit()

    def manual_override_rejected_video(
        self, video_id: str, override_reason: str = ""
    ) -> bool:
        """
        Manually override a rejected video to ACCEPTED status for re-ingestion.
        
        Returns True if successful, False if video not found or not in REJECTED status.
        Resets checkpoint to METADATA_HARVESTED so full pipeline runs again.
        """
        try:
            video = self.get_video(video_id)
            if not video:
                logger.warning(f"Video {video_id} not found")
                return False
            
            if video.triage_status != "REJECTED":
                logger.warning(f"Video {video_id} is not in REJECTED status (current: {video.triage_status})")
                return False
            
            # Reset to ACCEPTED and push back to beginning of pipeline
            self.conn.execute(
                """UPDATE videos
                   SET triage_status = 'ACCEPTED',
                       triage_reason = ?,
                       checkpoint_stage = 'METADATA_HARVESTED',
                       triage_confidence = 1.0,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE video_id = ?""",
                (f"manual_override: {override_reason}" if override_reason else "manual_override",
                 video_id),
            )
            self.conn.commit()
            
            # Log the manual override
            self.log_pipeline_event(
                level="INFO",
                message=f"Manual override of REJECTED video: {video.title[:60]}",
                video_id=video_id,
                channel_id=video.channel_id,
                stage="MANUAL_OVERRIDE",
            )
            
            logger.info(f"Manually overrode rejected video {video_id}: {override_reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to manually override rejected video {video_id}: {e}")
            return False

    def update_checkpoint_stage(self, video_id: str, stage: str) -> None:
        """Atomically advance a video's pipeline checkpoint stage."""
        self.conn.execute(
            """UPDATE videos
               SET checkpoint_stage = ?, updated_at = CURRENT_TIMESTAMP
               WHERE video_id = ?""",
            (stage, video_id),
        )
        self.conn.commit()

    def update_transcript_strategy(
        self, video_id: str, strategy: str, language_iso: str, needs_translation: bool
    ) -> None:
        """Record the transcript acquisition strategy."""
        self.conn.execute(
            """UPDATE videos
               SET transcript_strategy = ?, language_iso = ?,
                   needs_translation = ?, updated_at = CURRENT_TIMESTAMP
               WHERE video_id = ?""",
            (strategy, language_iso, needs_translation, video_id),
        )
        self.conn.commit()

    def get_discovered_video_ids(self) -> set[str]:
        """Get set of all known video IDs."""
        rows = self.conn.execute("SELECT video_id FROM videos").fetchall()
        return {r["video_id"] for r in rows}

    def get_resumable_videos(self) -> list[Video]:
        """Get accepted videos that haven't reached DONE checkpoint."""
        rows = self.conn.execute(
            """SELECT * FROM videos
               WHERE triage_status = 'ACCEPTED' 
                 AND checkpoint_stage != 'GRAPH_SYNCED'
                 AND locked_by_scan_id IS NULL
               ORDER BY created_at ASC""",
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def get_videos_missing_transcripts(self, limit: int = 200) -> list[Video]:
        """Get accepted videos that are missing transcripts."""
        rows = self.conn.execute(
            """SELECT v.* FROM videos v
               LEFT JOIN transcript_chunks tc ON v.video_id = tc.video_id
               WHERE v.triage_status = 'ACCEPTED'
                 AND tc.chunk_id IS NULL
               LIMIT ?""",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def get_videos_by_status(self, status: str, limit: int = 500) -> list[Video]:
        """Get all videos with a specific triage_status."""
        rows = self.conn.execute(
            """SELECT * FROM videos 
               WHERE triage_status = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (status, limit),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def get_videos_missing_summaries(self, limit: int = 200) -> list[Video]:
        """Get accepted videos that are missing summaries."""
        rows = self.conn.execute(
            """SELECT v.* FROM videos v
               LEFT JOIN video_summaries vs ON v.video_id = vs.video_id
               WHERE v.triage_status = 'ACCEPTED'
                 AND (vs.summary_text IS NULL OR vs.summary_text = '')
               LIMIT ?""",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def get_videos_missing_heatmaps(self, limit: int = 200) -> list[Video]:
        """Get accepted videos that have empty or default heatmap JSON."""
        rows = self.conn.execute(
            """SELECT * FROM videos 
               WHERE triage_status = 'ACCEPTED' 
                 AND (heatmap_json IS NULL OR heatmap_json = '[]')
               LIMIT ?""",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result


    def get_temp_state(self, video_id: str) -> Optional[dict]:
        """Get the temporary processing state for a video."""
        row = self.conn.execute(
            "SELECT * FROM pipeline_temp_state WHERE video_id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def save_temp_state(
        self, video_id: str, raw_text: str = "", segments_json: str = "[]",
        cleaned_text: str = "", translated_text: str = ""
    ) -> None:
        """Save temporary processing state for a video."""
        self.conn.execute(
            """INSERT INTO pipeline_temp_state (video_id, raw_text, segments_json, cleaned_text, translated_text)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(video_id) DO UPDATE SET
                   raw_text = CASE WHEN excluded.raw_text != '' THEN excluded.raw_text ELSE raw_text END,
                   segments_json = CASE WHEN excluded.segments_json != '[]' THEN excluded.segments_json ELSE segments_json END,
                   cleaned_text = CASE WHEN excluded.cleaned_text != '' THEN excluded.cleaned_text ELSE cleaned_text END,
                   translated_text = CASE WHEN excluded.translated_text != '' THEN excluded.translated_text ELSE translated_text END""",
            (video_id, raw_text, segments_json, cleaned_text, translated_text),
        )
        self.conn.commit()

    def get_videos_for_channels(self, channel_ids: list[str], limit: int = 500) -> list[Video]:
        """Get all videos belonging to a set of channels."""
        if not channel_ids:
            return []
        placeholders = ",".join(["?"] * len(channel_ids))
        rows = self.conn.execute(
            f"SELECT * FROM videos WHERE channel_id IN ({placeholders}) LIMIT ?",
            (*channel_ids, limit),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    def get_high_momentum_videos(self, limit: int = 5) -> list[dict]:
        """Identify videos with the highest hourly view growth.
        
        Compares current views with the oldest snapshot in history
        to calculate velocity (views/hour).
        """
        rows = self.conn.execute(
            """
            WITH first_stats AS (
                SELECT video_id, view_count, snapshot_at,
                       ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY snapshot_at ASC) as rn
                FROM video_stats_history
            )
            SELECT 
                v.video_id, 
                v.title, 
                c.name as channel_name,
                v.view_count as current_views,
                fs.view_count as initial_views,
                (v.view_count - fs.view_count) as growth,
                (julianday('now') - julianday(fs.snapshot_at)) * 24 as hours_elapsed
            FROM videos v
            JOIN channels c ON v.channel_id = c.channel_id
            JOIN first_stats fs ON v.video_id = fs.video_id
            WHERE fs.rn = 1 
              AND hours_elapsed > 0.1  -- Need at least 6 minutes of history
            ORDER BY (v.view_count - fs.view_count) / (hours_elapsed + 0.01) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        
        result = []
        for r in rows:
            d = dict(r)
            d["velocity"] = d["growth"] / max(0.1, d["hours_elapsed"])
            result.append(d)
        return result

    def get_manually_overridden_videos(self, limit: int = 100) -> list[Video]:
        """Get recently manually-overridden rejected videos ready for re-ingestion.
        
        These are ACCEPTED videos with checkpoint_stage = METADATA_HARVESTED
        and recent triage_reason containing 'manual_override'.
        """
        rows = self.conn.execute(
            """SELECT * FROM videos
               WHERE triage_status = 'ACCEPTED'
                 AND checkpoint_stage = 'METADATA_HARVESTED'
                 AND triage_reason LIKE '%manual_override%'
               ORDER BY updated_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            result.append(Video.from_row(r))
        return result

    # -------------------------------------------------------------------
    # Guests
    # -------------------------------------------------------------------

    def upsert_guest(self, name: str, entity_type: str = "PERSON") -> Guest:
        """Create or get a guest by canonical name."""
        row = self.conn.execute(
            "SELECT * FROM guests WHERE canonical_name = ?", (name,)
        ).fetchone()
        if row:
            try:
                self.conn.execute(
                    """UPDATE guests SET mention_count = mention_count + 1,
                           last_seen = CURRENT_TIMESTAMP WHERE guest_id = ?""",
                    (row["guest_id"],),
                )
                self.conn.commit()
            except sqlite3.OperationalError:
                self.conn.rollback()
            d = dict(row)
            d["aliases"] = json.loads(d.pop("aliases_json", "[]"))
            d["mention_count"] = d["mention_count"] + 1
            return Guest(**d)
        else:
            try:
                cursor = self.conn.execute(
                    """INSERT INTO guests (canonical_name, entity_type, mention_count)
                       VALUES (?, ?, 1)""",
                    (name, entity_type),
                )
                self.conn.commit()
            except sqlite3.OperationalError:
                self.conn.rollback()
            return Guest(
                guest_id=cursor.lastrowid if cursor else 0,
                canonical_name=name,
                entity_type=entity_type,
                mention_count=1,
            )

    def add_guest_alias(self, guest_id: int, alias: str) -> None:
        """Add an alias to a guest's alias list."""
        row = self.conn.execute(
            "SELECT aliases_json FROM guests WHERE guest_id = ?", (guest_id,)
        ).fetchone()
        if row:
            aliases = json.loads(row["aliases_json"])
            if alias not in aliases:
                aliases.append(alias)
                self.conn.execute(
                    "UPDATE guests SET aliases_json = ? WHERE guest_id = ?",
                    (json.dumps(aliases), guest_id),
                )
                self.conn.commit()

    def find_guest_exact(self, name: str) -> Optional[Guest]:
        """Find guest by exact canonical name or alias."""
        # Check canonical name first (indexed)
        row = self.conn.execute(
            "SELECT * FROM guests WHERE canonical_name = ?", (name,)
        ).fetchone()
        if row:
            d = dict(row)
            d["aliases"] = json.loads(d.pop("aliases_json", "[]"))
            return Guest(**d)
        # Check aliases via SQL LIKE on JSON column (avoids full table scan)
        escaped = name.replace('"', '\\"')
        row = self.conn.execute(
            "SELECT * FROM guests WHERE aliases_json LIKE ?",
            (f'%"{escaped}"%',),
        ).fetchone()
        if row:
            aliases = json.loads(row["aliases_json"])
            if name in aliases:  # Confirm exact match (LIKE can be loose)
                d = dict(row)
                d.pop("aliases_json", None)
                d["aliases"] = aliases
                return Guest(**d)
        return None

    def get_all_guests(self) -> list[Guest]:
        """Get all guest records."""
        rows = self.conn.execute(
            "SELECT * FROM guests ORDER BY mention_count DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["aliases"] = json.loads(d.pop("aliases_json", "[]"))
            result.append(Guest(**d))
        return result

    # -------------------------------------------------------------------
    # Guest Appearances
    # -------------------------------------------------------------------

    def add_guest_appearance(
        self, guest_id: int, video_id: str,
        context: str = "", start_ts: float = 0.0, end_ts: float = 0.0
    ) -> None:
        """Record a guest appearance in a video."""
        try:
            self.conn.execute(
                """INSERT INTO guest_appearances
                       (guest_id, video_id, context_snippet, start_timestamp, end_timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (guest_id, video_id, context, start_ts, end_ts),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            self.conn.rollback()
        except sqlite3.OperationalError as e:
            self.conn.rollback()
            logger.debug(f"Database locked during add_guest_appearance: {e}")

    # -------------------------------------------------------------------
    # Transcript Chunks
    # -------------------------------------------------------------------

    def insert_chunks(self, chunks: list[TranscriptChunk]) -> int:
        """Bulk insert transcript chunks. Returns count inserted."""
        inserted = 0
        for chunk in chunks:
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO transcript_chunks
                           (chunk_id, video_id, chunk_index, raw_text, cleaned_text,
                            word_count, start_timestamp, end_timestamp, topics_json,
                            entities_json, claims_json, quotes_json, is_high_attention,
                            content_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (chunk.chunk_id, chunk.video_id, chunk.chunk_index,
                     chunk.raw_text, chunk.cleaned_text, chunk.word_count,
                     chunk.start_timestamp, chunk.end_timestamp,
                     chunk.topics_json, chunk.entities_json, chunk.claims_json,
                     chunk.quotes_json, int(chunk.is_high_attention),
                     chunk.content_hash),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        self.conn.commit()
        return inserted

    def get_chunks_for_video(self, video_id: str) -> list[TranscriptChunk]:
        """Get all transcript chunks for a video, ordered by index."""
        rows = self.conn.execute(
            """SELECT * FROM transcript_chunks
               WHERE video_id = ? ORDER BY chunk_index""",
            (video_id,),
        ).fetchall()
        return [TranscriptChunk(**dict(r)) for r in rows]

    def update_chunk_analysis(
        self, chunk_id: str, topics_json: str = "[]",
        entities_json: str = "[]", claims_json: str = "[]",
        quotes_json: str = "[]", is_high_attention: Optional[bool] = None
    ) -> None:
        """Save per-chunk analysis results (topics, entities, claims, quotes)."""
        if is_high_attention is not None:
            self.conn.execute(
                """UPDATE transcript_chunks
                   SET topics_json = ?, entities_json = ?, claims_json = ?, quotes_json = ?, is_high_attention = ?
                   WHERE chunk_id = ?""",
                (topics_json, entities_json, claims_json, quotes_json, int(is_high_attention), chunk_id),
            )
        else:
            self.conn.execute(
                """UPDATE transcript_chunks
                   SET topics_json = ?, entities_json = ?, claims_json = ?, quotes_json = ?
                   WHERE chunk_id = ?""",
                (topics_json, entities_json, claims_json, quotes_json, chunk_id),
            )
        self.conn.commit()

    def get_video_aggregated_topics(self, video_id: str) -> list[dict]:
        """Aggregate topics across all chunks for a video, deduplicating by name."""
        chunks = self.get_chunks_for_video(video_id)
        topic_scores = {}  # name → max relevance
        for chunk in chunks:
            for t in json.loads(chunk.topics_json or "[]"):
                name = t.get("name", "").lower().strip()
                if name:
                    topic_scores[name] = max(
                        topic_scores.get(name, 0.0), t.get("relevance", 0.5)
                    )
        return [{"name": n, "relevance": s} for n, s in
                sorted(topic_scores.items(), key=lambda x: -x[1])]

    def get_video_aggregated_entities(self, video_id: str) -> list[str]:
        """Aggregate unique entity names across all chunks for a video."""
        chunks = self.get_chunks_for_video(video_id)
        names = set()
        for chunk in chunks:
            for e in json.loads(chunk.entities_json or "[]"):
                name = e.get("name", "").strip()
                if name:
                    names.add(name)
        return sorted(names)

    # -------------------------------------------------------------------
    # Claims
    # -------------------------------------------------------------------

    def insert_claim(self, claim: Claim) -> int:
        """Insert a claim and return its ID."""
        cursor = self.conn.execute(
            """INSERT INTO claims (video_id, chunk_id, speaker, claim_text,
                   topic, timestamp, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (claim.video_id, claim.chunk_id, claim.speaker,
             claim.claim_text, claim.topic, claim.timestamp, claim.confidence),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_claims_for_video(self, video_id: str) -> list[Claim]:
        """Get all claims for a video."""
        rows = self.conn.execute(
            "SELECT * FROM claims WHERE video_id = ? ORDER BY timestamp",
            (video_id,),
        ).fetchall()
        return [Claim(**dict(r)) for r in rows]

    def search_claims(self, query: str, limit: int = 20) -> list[Claim]:
        """Search claims by text content."""
        rows = self.conn.execute(
            "SELECT * FROM claims WHERE claim_text LIKE ? ORDER BY confidence DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [Claim(**dict(r)) for r in rows]

    # -------------------------------------------------------------------
    # Quotes
    # -------------------------------------------------------------------

    def insert_quote(self, quote: Quote) -> int:
        """Insert a quote and return its ID."""
        cursor = self.conn.execute(
            """INSERT INTO quotes (video_id, chunk_id, speaker, quote_text,
                   topic, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (quote.video_id, quote.chunk_id, quote.speaker,
             quote.quote_text, quote.topic, quote.timestamp),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_quotes_for_video(self, video_id: str) -> list[Quote]:
        """Get all quotes for a video."""
        rows = self.conn.execute(
            "SELECT * FROM quotes WHERE video_id = ? ORDER BY timestamp",
            (video_id,),
        ).fetchall()
        return [Quote(**dict(r)) for r in rows]

    def get_quotes_by_speaker(self, speaker: str, limit: int = 50) -> list[Quote]:
        """Get quotes by a specific speaker."""
        rows = self.conn.execute(
            "SELECT * FROM quotes WHERE speaker LIKE ? ORDER BY timestamp LIMIT ?",
            (f"%{speaker}%", limit),
        ).fetchall()
        return [Quote(**dict(r)) for r in rows]

    # -------------------------------------------------------------------
    # Actionable Blueprints
    # -------------------------------------------------------------------

    def upsert_blueprint(self, video_id: str, steps: list[str]) -> None:
        """Insert or update an actionable blueprint for a video."""
        self.conn.execute(
            """INSERT INTO actionable_blueprints (video_id, steps_json)
               VALUES (?, ?)
               ON CONFLICT(video_id) DO UPDATE SET
                   steps_json = excluded.steps_json,
                   created_at = CURRENT_TIMESTAMP""",
            (video_id, json.dumps(steps)),
        )
        self.conn.commit()

    def get_blueprint(self, video_id: str) -> Optional[ActionableBlueprint]:
        """Get the actionable blueprint for a specific video."""
        row = self.conn.execute(
            "SELECT * FROM actionable_blueprints WHERE video_id = ?", (video_id,)
        ).fetchone()
        return ActionableBlueprint(**dict(row)) if row else None

    def get_all_blueprints(self) -> list[dict]:
        """Get all blueprints with video titles, filtered by tutorial status."""
        rows = self.conn.execute(
            """SELECT b.*, v.title, c.name as channel_name 
               FROM actionable_blueprints b
               JOIN videos v ON b.video_id = v.video_id
               JOIN channels c ON v.channel_id = c.channel_id
               WHERE v.is_tutorial = 1
               ORDER BY b.created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Expert Clashes
    # -------------------------------------------------------------------

    def insert_clash(self, clash: ExpertClash) -> int:
        """Record a conflict/clash between two experts."""
        cursor = self.conn.execute(
            """INSERT INTO expert_clashes 
               (topic, expert_a, expert_b, claim_a, claim_b, source_a, source_b)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (clash.topic, clash.expert_a, clash.expert_b, 
             clash.claim_a, clash.claim_b, 
             clash.source_a if clash.source_a else None, 
             clash.source_b if clash.source_b else None),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_clashes_by_topic(self, topic: str) -> list[ExpertClash]:
        """Get all recorded clashes for a specific topic."""
        rows = self.conn.execute(
            "SELECT * FROM expert_clashes WHERE topic = ?", (topic,)
        ).fetchall()
        return [ExpertClash(**dict(r)) for r in rows]

    # -------------------------------------------------------------------
    # Video Sentiment
    # -------------------------------------------------------------------

    def insert_sentiment(self, sentiment: VideoSentiment) -> None:
        """Record sentiment for a transcript chunk (or video timeline if chunk_id is None)."""
        self.conn.execute(
            """INSERT INTO video_sentiment (video_id, chunk_id, score, label)
               VALUES (?, ?, ?, ?)""",
            (sentiment.video_id, 
             sentiment.chunk_id if sentiment.chunk_id else None, 
             sentiment.score, sentiment.label),
        )
        self.conn.commit()

    def get_video_sentiment_series(self, video_id: str) -> list[dict]:
        """Get the chronological sentiment series for a video."""
        rows = self.conn.execute(
            """SELECT vs.*, tc.start_timestamp 
               FROM video_sentiment vs
               LEFT JOIN transcript_chunks tc ON vs.chunk_id = tc.chunk_id
               WHERE vs.video_id = ?
               ORDER BY vs.id ASC""",
            (video_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # External Citations
    # -------------------------------------------------------------------

    def insert_citation(self, video_id: str, name: str, url: str, c_type: str = "OTHER") -> int:
        """Record an external citation (paper, book, etc.)."""
        cursor = self.conn.execute(
            "INSERT INTO external_citations (video_id, name, url, type) VALUES (?, ?, ?, ?)",
            (video_id, name, url, c_type),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_citations_for_video(self, video_id: str) -> list[ExternalCitation]:
        """Get all external citations for a video."""
        rows = self.conn.execute(
            "SELECT * FROM external_citations WHERE video_id = ?", (video_id,)
        ).fetchall()
        return [ExternalCitation(**dict(r)) for r in rows]

    # -------------------------------------------------------------------
    # Phase 3: Advanced Discovery & Research
    # -------------------------------------------------------------------

    def insert_thematic_bridge(self, bridge: ThematicBridge) -> int:
        """Record a discovered connection between two topics."""
        cursor = self.conn.execute(
            """INSERT INTO thematic_bridges (topic_a, topic_b, insight, llm_model)
               VALUES (?, ?, ?, ?)""",
            (bridge.topic_a, bridge.topic_b, bridge.insight, bridge.llm_model),
        )
        self.conn.commit()
        return cursor.lastrowid

    # -------------------------------------------------------------------
    # Pipeline Locking (for concurrent/resume safety)
    # -------------------------------------------------------------------

    def claim_video(self, video_id: str, scan_id: str) -> bool:
        """Attempt to lock a video for a specific scan.
        
        Returns True if successfully locked, False if already locked 
        by another scan.
        """
        try:
            # Atomic update: only set if currently NULL
            result = self.conn.execute(
                """UPDATE videos 
                   SET locked_by_scan_id = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE video_id = ? AND (locked_by_scan_id IS NULL OR locked_by_scan_id = ?)""",
                (scan_id, video_id, scan_id),
            )
            self.conn.commit()
            return result.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to claim video {video_id}: {e}")
            return False

    def release_video(self, video_id: str, scan_id: str) -> None:
        """Unlock a video, provided it was locked by this scan."""
        try:
            self.conn.execute(
                """UPDATE videos 
                   SET locked_by_scan_id = NULL, updated_at = CURRENT_TIMESTAMP
                   WHERE video_id = ? AND locked_by_scan_id = ?""",
                (video_id, scan_id),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to release video {video_id}: {e}")

    def release_all_locks(self, scan_id: str) -> int:
        """Clear all video locks for a specific scan."""
        try:
            result = self.conn.execute(
                "UPDATE videos SET locked_by_scan_id = NULL WHERE locked_by_scan_id = ?",
                (scan_id,),
            )
            self.conn.commit()
            return result.rowcount
        except sqlite3.Error as e:
            logger.error(f"Failed to release locks for scan {scan_id}: {e}")
            return 0

    def get_thematic_bridges(self, topic: Optional[str] = None) -> list[ThematicBridge]:
        """Get all thematic bridges, optionally filtered by topic."""
        if topic:
            rows = self.conn.execute(
                """SELECT * FROM thematic_bridges 
                   WHERE topic_a = ? OR topic_b = ? 
                   ORDER BY created_at DESC""",
                (topic, topic),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM thematic_bridges ORDER BY created_at DESC"
            ).fetchall()
        return [ThematicBridge(**dict(r)) for r in rows]

    def insert_research_report(self, report: ResearchReport) -> int:
        """Record a generated research report."""
        cursor = self.conn.execute(
            """INSERT INTO research_reports 
               (query, title, file_path, summary, sources_json)
               VALUES (?, ?, ?, ?, ?)""",
            (report.query, report.title, report.file_path, 
             report.summary, report.sources_json),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_research_reports(self, limit: int = 20) -> list[ResearchReport]:
        """Get recent research reports."""
        rows = self.conn.execute(
            "SELECT * FROM research_reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [ResearchReport(**dict(r)) for r in rows]

    # -------------------------------------------------------------------
    # Phase 4: Live Monitoring & Subscription
    # -------------------------------------------------------------------

    def insert_monitored_channel(self, channel_id: str) -> None:
        """Subscribe to a channel for automated briefs."""
        self.conn.execute(
            "INSERT OR IGNORE INTO monitored_channels (channel_id) VALUES (?)",
            (channel_id,)
        )
        self.conn.commit()

    def remove_monitored_channel(self, channel_id: str) -> None:
        """Unsubscribe from a channel."""
        self.conn.execute(
            "DELETE FROM monitored_channels WHERE channel_id = ?",
            (channel_id,)
        )
        self.conn.commit()

    def get_monitored_channels(self) -> list[MonitoredChannel]:
        """Get all channels currently being followed."""
        rows = self.conn.execute(
            "SELECT * FROM monitored_channels ORDER BY created_at DESC"
        ).fetchall()
        return [MonitoredChannel(**dict(r)) for r in rows]

    def update_last_brief_time(self, channel_ids: list[str]) -> None:
        """Update the last brief timestamp for monitored channels."""
        placeholders = ",".join(["?"] * len(channel_ids))
        self.conn.execute(
            f"UPDATE monitored_channels SET last_brief_at = CURRENT_TIMESTAMP WHERE channel_id IN ({placeholders})",
            channel_ids
        )
        self.conn.commit()

    def insert_weekly_brief(self, brief: WeeklyBrief) -> int:
        """Record a generated weekly intelligence brief."""
        cursor = self.conn.execute(
            "INSERT INTO weekly_briefs (channel_ids_json, content) VALUES (?, ?)",
            (brief.channel_ids_json, brief.content)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_weekly_briefs(self, limit: int = 10) -> list[WeeklyBrief]:
        """Get recent weekly briefs."""
        rows = self.conn.execute(
            "SELECT * FROM weekly_briefs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [WeeklyBrief(**dict(r)) for r in rows]

    def get_topic_trends(self, limit: int = 10) -> list[dict]:
        """Get topic mention frequency over time (monthly)."""
        # We join videos to get the publication date
        rows = self.conn.execute(
            """SELECT json_extract(t.value, '$.name') as topic, strftime('%Y-%m', v.upload_date) as month, COUNT(*) as count
               FROM video_summaries vs
               CROSS JOIN json_each(vs.topics_json) as t
               JOIN videos v ON vs.video_id = v.video_id
               WHERE v.upload_date IS NOT NULL
               GROUP BY 1, 2
               ORDER BY 2 ASC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def get_guest_network(self) -> list[dict]:
        """Get guest co-occurrence and thematic links."""
        # ... logic as before ...
        rows = self.conn.execute(
            """SELECT json_extract(t1.value, '$.name') as topic, g1.canonical_name as guest_a, g2.canonical_name as guest_b
               FROM video_summaries vs1
               CROSS JOIN json_each(vs1.topics_json) as t1
               JOIN guest_appearances ga1 ON vs1.video_id = ga1.video_id
               JOIN guests g1 ON ga1.guest_id = g1.guest_id
               
               JOIN video_summaries vs2
               CROSS JOIN json_each(vs2.topics_json) as t2
               JOIN guest_appearances ga2 ON vs2.video_id = ga2.video_id
               JOIN guests g2 ON ga2.guest_id = g2.guest_id
               
               WHERE json_extract(t1.value, '$.name') = json_extract(t2.value, '$.name') 
               AND g1.guest_id < g2.guest_id
               GROUP BY 1, 2, 3
               ORDER BY 1"""
        ).fetchall()
        return [dict(r) for r in rows]


    def get_videos_for_summarization(self, limit: int = 50) -> list[str]:
        """Find videos ready for summarization but not yet processed."""
        rows = self.conn.execute(
            """SELECT video_id FROM videos 
               WHERE (checkpoint_stage IN ('TRIAGE_COMPLETE', 'DONE', 'CHUNK_ANALYZED')) 
               AND video_id NOT IN (SELECT video_id FROM video_summaries)
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [r[0] for r in rows]

    # -------------------------------------------------------------------
    # Pipeline Temp State
    # -------------------------------------------------------------------

    def save_temp_state(
        self, video_id: str, raw_text: str = "",
        segments_json: str = "[]", cleaned_text: str = "", translated_text: str = ""
    ) -> None:
        """Save or update intermediate pipeline state for a video."""
        self.conn.execute(
            """INSERT INTO pipeline_temp_state (video_id, raw_text, segments_json, cleaned_text, translated_text)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(video_id) DO UPDATE SET
                   raw_text = excluded.raw_text,
                   segments_json = excluded.segments_json,
                   cleaned_text = excluded.cleaned_text,
                   translated_text = excluded.translated_text""",
            (video_id, raw_text, segments_json, cleaned_text, translated_text),
        )
        self.conn.commit()

    def get_temp_state(self, video_id: str) -> Optional[dict]:
        """Get intermediate pipeline state for a video.

        Returns dict with keys: video_id, raw_text, segments_json, cleaned_text, translated_text.
        """
        row = self.conn.execute(
            "SELECT * FROM pipeline_temp_state WHERE video_id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def delete_temp_state(self, video_id: str) -> None:
        """Delete intermediate pipeline state after chunking completes."""
        self.conn.execute(
            "DELETE FROM pipeline_temp_state WHERE video_id = ?", (video_id,)
        )
        self.conn.commit()

    # -------------------------------------------------------------------
    # P0-A: Sync Outbox (Saga Pattern for Triple-Store Atomicity)
    # -------------------------------------------------------------------

    def create_sync_outbox_entry(self, video_id: str) -> None:
        """Create or reset an outbox entry before starting store sync stages.

        Called at the start of _stage_embed so that a post-crash drain can
        detect and retry incomplete syncs.
        """
        self.conn.execute(
            """INSERT INTO sync_outbox (video_id, chroma_done, neo4j_done, retry_count)
               VALUES (?, 0, 0, 0)
               ON CONFLICT(video_id) DO UPDATE SET
                   chroma_done = 0,
                   neo4j_done  = 0,
                   retry_count = retry_count + 1,
                   updated_at  = CURRENT_TIMESTAMP""",
            (video_id,),
        )
        self.conn.commit()

    def mark_outbox_chroma_done(self, video_id: str) -> None:
        """Mark ChromaDB sync complete in the outbox."""
        self.conn.execute(
            """UPDATE sync_outbox
               SET chroma_done = 1, updated_at = CURRENT_TIMESTAMP
               WHERE video_id = ?""",
            (video_id,),
        )
        self.conn.commit()

    def mark_outbox_neo4j_done(self, video_id: str) -> None:
        """Mark Neo4j sync complete in the outbox."""
        self.conn.execute(
            """UPDATE sync_outbox
               SET neo4j_done = 1, updated_at = CURRENT_TIMESTAMP
               WHERE video_id = ?""",
            (video_id,),
        )
        self.conn.commit()

    def get_pending_outbox(self, limit: int = 100) -> list[dict]:
        """Return outbox entries with incomplete chroma or neo4j sync."""
        rows = self.conn.execute(
            """SELECT so.video_id, so.chroma_done, so.neo4j_done, so.retry_count,
                      v.channel_id, v.checkpoint_stage
               FROM sync_outbox so
               LEFT JOIN videos v ON so.video_id = v.video_id
               WHERE so.chroma_done = 0 OR so.neo4j_done = 0
               ORDER BY so.created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_outbox_error(self, video_id: str, error: str) -> None:
        """Record an error on an outbox entry for diagnostics."""
        self.conn.execute(
            """UPDATE sync_outbox
               SET last_error = ?, retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP
               WHERE video_id = ?""",
            (error[:500], video_id),
        )
        self.conn.commit()

    def cleanup_done_outbox(self) -> int:
        """Delete completed outbox rows (both chroma and neo4j done)."""
        cursor = self.conn.execute(
            "DELETE FROM sync_outbox WHERE chroma_done = 1 AND neo4j_done = 1"
        )
        self.conn.commit()
        return cursor.rowcount

    def get_outbox_stats(self) -> dict:
        """Return summary counts for the sync outbox."""
        row = self.conn.execute(
            """SELECT
                   COUNT(*) AS total,
                   SUM(CASE WHEN chroma_done = 0 THEN 1 ELSE 0 END) AS pending_chroma,
                   SUM(CASE WHEN neo4j_done  = 0 THEN 1 ELSE 0 END) AS pending_neo4j,
                   SUM(CASE WHEN chroma_done = 1 AND neo4j_done = 1 THEN 1 ELSE 0 END) AS fully_done
               FROM sync_outbox"""
        ).fetchone()
        return dict(row) if row else {}

    def mark_translation_stored(self, video_id: str) -> None:
        """Set translated_text_stored flag without exposing raw conn.

        Replaces the bare self.db.conn.execute() call in _stage_translate.
        """
        self.conn.execute(
            "UPDATE videos SET translated_text_stored = 1 WHERE video_id = ?",
            (video_id,),
        )
        self.conn.commit()

    # -------------------------------------------------------------------
    # P0-B: Content Hash Helpers for Embedding Skip
    # -------------------------------------------------------------------

    def get_chunks_with_hashes(self, video_id: str) -> dict:
        """Return {chunk_id: content_hash} for all chunks of a video.

        Used by _stage_embed to identify chunks whose content has not changed
        since the last embedding pass.
        """
        rows = self.conn.execute(
            "SELECT chunk_id, content_hash FROM transcript_chunks WHERE video_id = ?",
            (video_id,),
        ).fetchall()
        return {r["chunk_id"]: (r["content_hash"] or "") for r in rows}

    # -------------------------------------------------------------------
    # P0-C: Temp State Cleanup + Stats
    # -------------------------------------------------------------------

    def cleanup_done_temp_states(self) -> int:
        """Delete pipeline_temp_state rows for fully-processed videos.

        Targets videos at GRAPH_SYNCED / DONE checkpoint stage — they no
        longer need their raw/cleaned text buffered in temp state.
        Returns the number of rows deleted.
        """
        cursor = self.conn.execute(
            """DELETE FROM pipeline_temp_state
               WHERE video_id IN (
                   SELECT video_id FROM videos
                   WHERE checkpoint_stage IN ('GRAPH_SYNCED', 'DONE')
               )"""
        )
        self.conn.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info(f"Temp state cleanup: removed {deleted} rows for completed videos")
        return deleted

    def get_temp_state_stats(self) -> dict:
        """Return diagnostic stats for pipeline_temp_state storage usage."""
        row = self.conn.execute(
            """SELECT
                   COUNT(*) AS row_count,
                   COALESCE(SUM(LENGTH(raw_text) + LENGTH(cleaned_text)
                            + LENGTH(translated_text)) / 1024, 0) AS total_size_kb
               FROM pipeline_temp_state"""
        ).fetchone()
        return dict(row) if row else {"row_count": 0, "total_size_kb": 0}

    # -------------------------------------------------------------------
    # P0-D: Store Divergence Stats
    # -------------------------------------------------------------------

    def get_store_sync_stats(self) -> dict:
        """Return counts needed to detect SQLite vs ChromaDB vs Neo4j divergence.

        Used by the Graph Health dashboard to surface out-of-sync stores.
        """
        accepted_row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM videos WHERE triage_status = 'ACCEPTED'"
        ).fetchone()
        done_row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM videos WHERE checkpoint_stage IN ('GRAPH_SYNCED', 'DONE')"
        ).fetchone()
        outbox_stats = self.get_outbox_stats()
        return {
            "sqlite_accepted": accepted_row["cnt"] if accepted_row else 0,
            "sqlite_done": done_row["cnt"] if done_row else 0,
            "pending_outbox_chroma": outbox_stats.get("pending_chroma", 0) or 0,
            "pending_outbox_neo4j": outbox_stats.get("pending_neo4j", 0) or 0,
        }

    # -------------------------------------------------------------------
    # Scan Checkpoints
    # -------------------------------------------------------------------

    def create_scan_checkpoint(self, source_url: str, scan_type: str) -> str:
        """Create a new scan checkpoint, returns scan_id."""
        scan_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            """INSERT INTO scan_checkpoints (scan_id, source_url, scan_type)
               VALUES (?, ?, ?)""",
            (scan_id, source_url, scan_type),
        )
        self.conn.commit()
        logger.info(f"Created scan checkpoint: {scan_id} for {source_url}")
        return scan_id

    # -------------------------------------------------------------------
    # Video Summaries
    # -------------------------------------------------------------------

    def upsert_video_summary(self, summary: VideoSummary) -> None:
        """Insert or update a video summary."""
        self.conn.execute(
            """INSERT INTO video_summaries 
                   (video_id, summary_text, topics_json, takeaways_json, entities_json, references_json, timeline_json, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(video_id) DO UPDATE SET
                   summary_text = excluded.summary_text,
                   topics_json = excluded.topics_json,
                   takeaways_json = excluded.takeaways_json,
                   entities_json = excluded.entities_json,
                   references_json = excluded.references_json,
                   timeline_json = excluded.timeline_json,
                   last_updated = CURRENT_TIMESTAMP""",
            (summary.video_id, summary.summary_text, summary.topics_json,
             summary.takeaways_json, summary.entities_json, summary.references_json,
             summary.timeline_json),
        )
        self.conn.commit()

    def get_video_summary(self, video_id: str) -> Optional[VideoSummary]:
        """Get a video summary by video ID."""
        row = self.conn.execute(
            "SELECT * FROM video_summaries WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row:
            return VideoSummary(**dict(row))
        return None

    # -------------------------------------------------------------------
    # Transcript Access & Search (Week 1 Enhancement)
    # -------------------------------------------------------------------

    def get_full_transcript(self, video_id: str) -> Optional[dict]:
        """Retrieve full transcript for a video with all metadata."""
        video = self.get_video(video_id)
        if not video:
            return None
        
        chunks = self.execute("""
            SELECT chunk_id, chunk_index, raw_text, cleaned_text,
                   start_timestamp, end_timestamp, word_count, is_high_attention
            FROM transcript_chunks
            WHERE video_id = ?
            ORDER BY chunk_index ASC
        """, (video_id,)).fetchall()
        
        # Reconstruct transcript with null safety
        full_raw = " ".join([c['raw_text'] or "" for c in chunks]) if chunks else ""
        full_cleaned = " ".join([c['cleaned_text'] or "" for c in chunks]) if chunks else ""
        
        channel = self.get_channel(video.channel_id)
        
        return {
            "video_id": video_id,
            "title": video.title,
            "channel": channel.name if channel else "Unknown",
            "duration_seconds": video.duration_seconds,
            "upload_date": video.upload_date,
            "language": video.language_iso,
            "transcript_strategy": video.transcript_strategy,
            "full_raw_text": full_raw,
            "full_cleaned_text": full_cleaned,
            "chunks": [dict(c) for c in chunks],
            "total_chunks": len(chunks) if chunks else 0
        }
    
    def get_chunk(self, chunk_id: str) -> Optional[TranscriptChunk]:
        """Get a single transcript chunk by ID."""
        row = self.execute(
            "SELECT * FROM transcript_chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        if row:
            return TranscriptChunk(**dict(row))
        return None

    def search_transcript(self, video_id: str, search_term: str) -> list[dict]:
        """Find occurrences of a term in a video's transcript (using FTS5 if possible)."""
        try:
            # P1: Try FTS5 first for phrase support and snippets
            results = self.execute("""
                SELECT chunk_id, video_id, 
                       snippet(chunks_fts, 2, '**', '**', '...', 30) AS snippet,
                       (SELECT chunk_index FROM transcript_chunks WHERE rowid = chunks_fts.rowid) as chunk_index,
                       (SELECT start_timestamp FROM transcript_chunks WHERE rowid = chunks_fts.rowid) as start_timestamp,
                       (SELECT end_timestamp FROM transcript_chunks WHERE rowid = chunks_fts.rowid) as end_timestamp,
                       (SELECT cleaned_text FROM transcript_chunks WHERE rowid = chunks_fts.rowid) as cleaned_text
                FROM chunks_fts
                WHERE video_id = ? AND content MATCH ?
                ORDER BY rank ASC
            """, (video_id, search_term)).fetchall()
            
            if results:
                return [dict(r) for r in results]
        except Exception as e:
            logger.debug(f"FTS5 search_transcript failed (falling back to LIKE): {e}")

        # Fallback to basic LIKE
        results = self.execute("""
            SELECT chunk_id, chunk_index, cleaned_text, raw_text,
                   start_timestamp, end_timestamp, word_count
            FROM transcript_chunks
            WHERE video_id = ? 
              AND (cleaned_text LIKE ? OR raw_text LIKE ?)
            ORDER BY chunk_index ASC
        """, (video_id, f"%{search_term}%", f"%{search_term}%")).fetchall()
        
        return [dict(r) for r in results]
    
    def get_transcript_at_timestamp(self, video_id: str, seconds: float, 
                                     context_seconds: int = 30) -> Optional[dict]:
        """Get transcript around a specific timestamp."""
        chunks = self.execute("""
            SELECT chunk_id, chunk_index, cleaned_text, raw_text,
                   start_timestamp, end_timestamp
            FROM transcript_chunks
            WHERE video_id = ?
              AND start_timestamp <= ? + ?
              AND end_timestamp >= ? - ?
            ORDER BY start_timestamp ASC
        """, (video_id, seconds, context_seconds, seconds, context_seconds)).fetchall()
        
        if not chunks:
            return None
        
        return {
            "target_timestamp": seconds,
            "context_seconds": context_seconds,
            "chunks": chunks
        }
    
    def compare_transcripts(self, video_ids: list[str]) -> dict:
        """Get transcripts for multiple videos for comparison."""
        transcripts = {}
        for vid in video_ids:
            transcript = self.get_full_transcript(vid)
            if transcript:
                transcripts[vid] = transcript
        return transcripts
    
    def search_all_transcripts(self, search_term: str, limit: int = 100) -> list[dict]:
        """Global search across all transcripts with enhanced relevance ranking."""
        try:
            results = self.execute("""
                SELECT 
                    tc.video_id,
                    v.title,
                    c.name as channel,
                    COUNT(DISTINCT tc.chunk_id) as chunk_count,
                    MIN(rank) as min_score
                FROM chunks_fts fts
                JOIN transcript_chunks tc ON fts.rowid = tc.rowid
                JOIN videos v ON tc.video_id = v.video_id
                JOIN channels c ON v.channel_id = c.channel_id
                WHERE fts.content MATCH ?
                GROUP BY tc.video_id
                ORDER BY min_score ASC, chunk_count DESC, v.upload_date DESC
                LIMIT ?
            """, (search_term, limit)).fetchall()
            
            if results:
                return [dict(r) for r in results]
        except Exception as e:
            logger.debug(f"FTS5 search_all_transcripts failed (falling back to LIKE): {e}")

        # Fallback to basic LIKE
        results = self.execute("""
            SELECT DISTINCT
                tc.video_id,
                v.title,
                c.name as channel,
                COUNT(DISTINCT tc.chunk_id) as chunk_count
            FROM transcript_chunks tc
            JOIN videos v ON tc.video_id = v.video_id
            JOIN channels c ON v.channel_id = c.channel_id
            WHERE tc.cleaned_text LIKE ? OR tc.raw_text LIKE ?
            GROUP BY tc.video_id
            ORDER BY v.upload_date DESC
            LIMIT ?
        """, (f"%{search_term}%", f"%{search_term}%", limit)).fetchall()
        
        return [dict(r) for r in results]

    def update_scan_checkpoint(
        self, scan_id: str, total_discovered: int = 0,
        total_processed: int = 0, last_video_id: str = "",
        status: str = ""
    ) -> None:
        """Update an existing scan checkpoint with retry logic."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        if total_discovered:
            updates.append("total_discovered = ?")
            params.append(total_discovered)
        if total_processed:
            updates.append("total_processed = ?")
            params.append(total_processed)
        if last_video_id:
            updates.append("last_video_id = ?")
            params.append(last_video_id)
        if status:
            updates.append("status = ?")
            params.append(status)
        params.append(scan_id)
        
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.conn.execute(
                    f"UPDATE scan_checkpoints SET {', '.join(updates)} WHERE scan_id = ?",
                    params,
                )
                self.conn.commit()
                return
            except (sqlite3.OperationalError, sqlite3.DatabaseError, SystemError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"SQLite commit retry {attempt + 1}/{max_retries}: {e}")
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    # Attempt to reset connection on SystemError
                    if isinstance(e, SystemError):
                        try:
                            self.conn.close()
                            import sqlite3 as sqlite3_module
                            self.conn = sqlite3_module.connect(
                                self.db_path, 
                                detect_types=sqlite3_module.PARSE_DECLTYPES,
                                timeout=5.0
                            )
                            self.conn.row_factory = sqlite3_module.Row
                            self.conn.execute("PRAGMA journal_mode = WAL")
                            self.conn.execute("PRAGMA foreign_keys = ON")
                        except Exception as reconnect_err:
                            logger.error(f"Failed to reconnect: {reconnect_err}")
                else:
                    logger.error(f"SQLite commit failed after {max_retries} attempts: {e}")
                    raise

    def get_scan_checkpoint(self, scan_id: str) -> Optional[ScanCheckpoint]:
        """Get a scan checkpoint by ID."""
        row = self.conn.execute(
            "SELECT * FROM scan_checkpoints WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        if row is None:
            return None
        return ScanCheckpoint(**dict(row))

    def get_active_scans(self) -> list[ScanCheckpoint]:

        """Get all currently running scans with their metadata, strictly deduplicated."""
        try:
            # P0: Strictly deduplicate by picking THE latest scan ID for every source_url
            # P1: Improved channel name resolution fallback
            sql = """
                SELECT 
                    s.*, 
                    COALESCE(
                        (SELECT name FROM channels WHERE url = s.source_url OR channel_id = s.source_url LIMIT 1),
                        (SELECT c.name FROM channels c 
                         JOIN videos v ON c.channel_id = v.channel_id 
                         WHERE v.url = s.source_url LIMIT 1),
                        'Generic Scan'
                    ) as channel_name
                FROM scan_checkpoints s
                WHERE s.id IN (
                    SELECT MAX(id) 
                    FROM scan_checkpoints 
                    WHERE status = 'IN_PROGRESS' 
                    GROUP BY source_url
                )
                ORDER BY s.started_at DESC
            """
            rows = self.conn.execute(sql).fetchall()
            results = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('channel_name') == 'Generic Scan':
                    url = row_dict.get('source_url', '')
                    if '@' in url:
                        handle = url.split('@')[-1].split('/')[0].split('?')[0]
                        row_dict['channel_name'] = f"@{handle}"
                    elif 'youtube.com/channel/' in url:
                        c_id = url.split('youtube.com/channel/')[-1].split('/')[0].split('?')[0]
                        row_dict['channel_name'] = f"Channel {c_id[:8]}..."
                results.append(ScanCheckpoint(**row_dict))
            return results
        except Exception as e:
            logger.error(f"Failed to get active scans: {e}")
            return []

    def set_global_control_state(self, status: str, pause_reason: str = None):
        """Set control state for ALL active scans."""
        try:
            active = self.get_active_scans()
            for scan in active:
                self.set_control_state(scan.scan_id, status, pause_reason)
            return len(active)
        except Exception as e:
            logger.error(f"Failed to set global control state: {e}")
            return 0

    def get_active_scan_for_url(self, url: str) -> Optional[ScanCheckpoint]:
        """Check if there is already an active scan for this URL."""
        row = self.conn.execute(
            "SELECT * FROM scan_checkpoints WHERE source_url = ? AND status = 'IN_PROGRESS' LIMIT 1",
            (url,)
        ).fetchone()
        if row:
            return ScanCheckpoint(**dict(row))
        return None



    # -------------------------------------------------------------------
    # Product Features
    # -------------------------------------------------------------------
    
    def get_knowledge_density_leaderboard(self, limit: int = 10) -> list[dict]:
        """Rank videos by empirical knowledge density.
        
        Score is simplified here using chunk count and duration.
        In a real scenario, this would aggregate unique entities.
        """
        rows = self.conn.execute(
            """
            SELECT 
                v.video_id, 
                v.title, 
                c.name AS channel_name,
                v.duration_seconds,
                (SELECT COUNT(*) FROM transcript_chunks WHERE video_id = v.video_id) AS chunk_count,
                (SELECT COUNT(*) FROM guest_appearances WHERE video_id = v.video_id) AS guest_count
            FROM videos v
            JOIN channels c ON v.channel_id = c.channel_id
            WHERE v.duration_seconds > 0 
              AND v.checkpoint_stage IN ('CHUNK_ANALYZED', 'EMBEDDED', 'GRAPH_SYNCED', 'DONE')
            """
        ).fetchall()
        
        result = []
        for row in rows:
            dur_mins = max(1, row["duration_seconds"] / 60.0)
            # Weighting: 2.0 per chunk (knowledge units) + 10.0 per guest (high value entities)
            score = (row["chunk_count"] * 2.0 + row["guest_count"] * 10.0) / dur_mins
            r_dict = dict(row)
            r_dict["density_score"] = score
            result.append(r_dict)
            
        result.sort(key=lambda x: x["density_score"], reverse=True)
        return result[:limit]

    def get_consolidated_topics(self) -> list[dict]:
        """Aggregate all topics across the vault, with channel and video counts."""
        query = """
        WITH topic_items AS (
            SELECT 
                v.channel_id,
                json_extract(t.value, '$.name') as topic_name,
                v.video_id
            FROM video_summaries, json_each(topics_json) as t
            JOIN videos v ON video_summaries.video_id = v.video_id
        )
        SELECT 
            topic_name as name,
            COUNT(DISTINCT channel_id) as channel_count,
            COUNT(DISTINCT video_id) as video_count,
            GROUP_CONCAT(DISTINCT channel_id) as channel_ids
        FROM topic_items
        WHERE topic_name IS NOT NULL
        GROUP BY topic_name
        ORDER BY video_count DESC;
        """
        rows = self.conn.execute(query).fetchall()
        return [dict(r) for r in rows]

    def get_topic_details(self, topic_name: str) -> list[dict]:
        """Get all videos and summary snippets associated with a specific topic."""
        query = """
        SELECT 
            v.video_id,
            v.title,
            v.url,
            v.upload_date,
            c.name as channel_name,
            vs.summary_text,
            vs.takeaways_json,
            t.value as topic_data
        FROM video_summaries vs
        JOIN videos v ON vs.video_id = v.video_id
        JOIN channels c ON v.channel_id = c.channel_id,
        json_each(vs.topics_json) as t
        WHERE json_extract(t.value, '$.name') = ?
        ORDER BY v.upload_date DESC
        """
        rows = self.conn.execute(query, (topic_name,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Use 'or' to handle NULL values from DB
            d["takeaways"] = json.loads(d.pop("takeaways_json", "[]") or "[]")
            d["topic_meta"] = json.loads(d.pop("topic_data", "{}") or "{}")
            result.append(d)
        return result

    # -------------------------------------------------------------------
    # Pipeline Statistics
    # -------------------------------------------------------------------

    def get_pipeline_stats(self) -> dict:
        """Get aggregate pipeline statistics for the dashboard with intuitive mapping."""
        stats = {}
        
        # 1. Total counts
        """Fetch high-level and granular statistics for pipeline monitoring."""
        stats = {
            "total_videos": 0,
            "discovered": 0,
            "accepted": 0,
            "rejected": 0,
            "pending_review": 0,
            "in_progress": 0,
            "done": 0,
            "stages": {}
        }
        
        # 1. Total videos, channels, and chunks
        stats["total_videos"] = self.conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        stats["total_channels"] = self.conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        stats["total_chunks"] = self.conn.execute("SELECT COUNT(*) FROM transcript_chunks").fetchone()[0]
        
        # 2. Triage breakdown
        res = self.conn.execute(
            "SELECT triage_status, COUNT(*) as cnt FROM videos GROUP BY triage_status"
        ).fetchall()
        triage_map = {row["triage_status"]: row["cnt"] for row in res}
        
        stats["discovered"] = triage_map.get("DISCOVERED", 0)
        stats["accepted"] = triage_map.get("ACCEPTED", 0)
        stats["rejected"] = triage_map.get("REJECTED", 0)
        stats["pending_review"] = triage_map.get("PENDING_REVIEW", 0)
        
        # 3. Checkpoint stages (Granular)
        res = self.conn.execute(
            "SELECT checkpoint_stage, COUNT(*) as cnt FROM videos GROUP BY checkpoint_stage"
        ).fetchall()
        stage_map = {row["checkpoint_stage"]: row["cnt"] for row in res}
        stats["stages"] = stage_map
        
        stats["done"] = stage_map.get("DONE", 0) + stage_map.get("SUMMARIZED", 0) + stage_map.get("GRAPH_SYNCED", 0)
        
        # 4. In Progress Metrics
        stats["in_progress"] = self.conn.execute(
            """SELECT COUNT(*) FROM videos 
               WHERE triage_status = 'ACCEPTED' 
                 AND checkpoint_stage NOT IN ('DONE', 'SUMMARIZED', 'GRAPH_SYNCED')"""
        ).fetchone()[0]
        
        # ETA calculation (30s per stage per video roughly)
        # Find which stages are pending for accepted videos
        stats["eta_minutes"] = max(1, (stats["in_progress"] * 45) // 60) if stats["in_progress"] > 0 else 0
        
        return stats

    # -------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------

    def get_top_performing_videos(self, limit: int = 10) -> list[dict]:
        """Get videos with highest view counts."""
        rows = self.conn.execute(
            """SELECT video_id, title, view_count, channel_id, upload_date
               FROM videos
               ORDER BY view_count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_most_engaged_videos(self, limit: int = 10, min_views: int = 1000) -> list[dict]:
        """Get videos with highest engagement rate (likes+comments / views)."""
        rows = self.conn.execute(
            """SELECT video_id, title, view_count, like_count, comment_count,
                      (CAST(like_count + comment_count AS REAL) / NULLIF(view_count, 0)) as engagement_rate
               FROM videos
               WHERE view_count >= ?
               ORDER BY engagement_rate DESC
               LIMIT ?""",
            (min_views, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_video_stats_history_data(self, video_id: str) -> list[dict]:
        """Get historical stats for a specific video."""
        rows = self.conn.execute(
            """SELECT snapshot_at, view_count, like_count, comment_count
               FROM video_stats_history
               WHERE video_id = ?
               ORDER BY snapshot_at ASC""",
            (video_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Full-Text Search (FTS5)
    # -------------------------------------------------------------------

    def fulltext_search(self, query: str, limit: int = 20) -> list[dict]:
        """BM25 full-text search across transcript chunks.

        Uses the chunks_fts FTS5 virtual table for keyword-exact matching.

        Returns:
            List of dicts with chunk_id, video_id, rank (BM25 score), snippet.
        """
        try:
            # Stricter matching: Wrap in quotes if multi-token or has underscores to force phrase-like matching
            sanitized_query = query.replace('"', ' ').strip()
            if not sanitized_query: return []
            
            # Use phrase match if it looks like a complex id/token
            match_query = f'"{sanitized_query}"' if ("_" in sanitized_query or " " in sanitized_query) else sanitized_query
            
            rows = self.conn.execute(
                """SELECT chunk_id, video_id,
                          rank AS bm25_score,
                          snippet(chunks_fts, 2, '<b>', '</b>', '...', 30) AS snippet
                   FROM chunks_fts
                   WHERE content MATCH ? AND rank < 0 -- BM25 scores are negative, lower is better
                   ORDER BY rank
                   LIMIT ?""",
                (match_query, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"FTS5 search failed (index may not exist): {e}")
            return []

    def populate_fts_index(self) -> int:
        """Populate the FTS5 index from existing transcript chunks.

        Should be called after schema migration v2 to backfill the index.
        Returns the number of rows indexed.
        """
        try:
            # Clear existing FTS data
            self.conn.execute("DELETE FROM chunks_fts;")
            # Insert from source table
            result = self.conn.execute(
                """INSERT INTO chunks_fts (chunk_id, video_id, content)
                   SELECT chunk_id, video_id, COALESCE(cleaned_text, raw_text)
                   FROM transcript_chunks
                   WHERE cleaned_text != '' OR raw_text != ''"""
            )
            self.conn.commit()
            count = result.rowcount
            logger.info(f"FTS5 index populated: {count} chunks")
            return count
        except Exception as e:
            logger.error(f"FTS5 index population failed: {e}")
            return 0

    # -------------------------------------------------------------------
    # Pipeline Logging
    # -------------------------------------------------------------------

    def log_pipeline_event(
        self, level: str = "INFO", message: str = "",
        scan_id: str = "", video_id: str = "", channel_id: str = "",
        stage: str = "", error_detail: str = ""
    ) -> int:
        """Log a pipeline activity event. Returns log_id."""
        cursor = self.conn.execute(
            """INSERT INTO pipeline_logs 
               (level, message, scan_id, video_id, channel_id, stage, error_detail, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (level, message, scan_id, video_id, channel_id, stage, error_detail),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_logs(
        self, scan_id: str = "", video_id: str = "",
        level: str = "", limit: int = 1000,
        order: str = "DESC"
    ) -> list[PipelineLog]:
        """Fetch pipeline logs with optional filtering."""
        query = "SELECT * FROM pipeline_logs WHERE 1=1"
        params = []
        
        if scan_id:
            query += " AND scan_id = ?"
            params.append(scan_id)
        if video_id:
            query += " AND video_id = ?"
            params.append(video_id)
        if level:
            query += " AND level = ?"
            params.append(level)
        
        query += f" ORDER BY timestamp {order} LIMIT ?"
        params.append(limit)
        
        rows = self.conn.execute(query, params).fetchall()
        return [PipelineLog(**dict(r)) for r in rows]

        summary = {}
        for row in rows:
            summary[row["level"]] = row["count"]
        return summary

    def get_video_pipeline_history(self, video_id: str) -> list[dict]:
        """Fetch chronological log history for a specific video."""
        rows = self.conn.execute(
            """SELECT * FROM pipeline_logs 
               WHERE video_id = ? 
               ORDER BY timestamp ASC""",
            (video_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_logs(self, older_than_days: int = 30) -> int:
        """Delete old logs. Returns count deleted."""
        result = self.conn.execute(
            """DELETE FROM pipeline_logs 
               WHERE timestamp < datetime('now', ? || ' days')""",
            (f"-{older_than_days}",),
        )
        self.conn.commit()
        return result.rowcount

    # -------------------------------------------------------------------
    # Pipeline Control (Pause/Resume/Stop)
    # -------------------------------------------------------------------

    def set_control_state(
        self, scan_id: str, status: str = "RUNNING",
        pause_reason: str = ""
    ) -> None:
        """Set pipeline control state (RUNNING, PAUSED, STOPPED, STOPPING)."""
        try:
            self.conn.execute(
                """INSERT INTO pipeline_control (scan_id, status, pause_reason)
                   VALUES (?, ?, ?)
                   ON CONFLICT(scan_id) DO UPDATE SET
                       status = excluded.status,
                       pause_reason = excluded.pause_reason,
                       updated_at = CURRENT_TIMESTAMP""",
                (scan_id, status, pause_reason),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to set control state: {e}")

    def get_control_state(self, scan_id: str) -> Optional[PipelineControl]:
        """Get pipeline control state for a scan."""
        row = self.conn.execute(
            "SELECT * FROM pipeline_control WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        if row:
            return PipelineControl(**dict(row))
        return None

    def pause_scan(self, scan_id: str, reason: str = "") -> None:
        """Pause a running scan."""
        self.set_control_state(scan_id, "PAUSED", reason)
        self.log_pipeline_event(
            level="INFO",
            message=f"Scan paused: {reason}",
            scan_id=scan_id
        )

    def resume_scan(self, scan_id: str) -> None:
        """Resume a paused scan."""
        self.conn.execute(
            """UPDATE pipeline_control 
               SET status = 'RUNNING', pause_reason = '', resumed_at = CURRENT_TIMESTAMP
               WHERE scan_id = ?""",
            (scan_id,),
        )
        self.conn.commit()
        self.log_pipeline_event(
            level="INFO",
            message="Scan resumed",
            scan_id=scan_id
        )

    def stop_scan(self, scan_id: str) -> None:
        """Stop a scan gracefully."""
        self.set_control_state(scan_id, "STOPPED", "User stopped")
        self.log_pipeline_event(
            level="WARNING",
            message="Scan stopped by user",
            scan_id=scan_id
        )

    # -------------------------------------------------------------------
    # Video Removal & Discovery Queue Management
    # -------------------------------------------------------------------

    def remove_video_from_queue(self, video_id: str) -> bool:
        """Remove a video from processing queue (only before ACCEPTED status)."""
        try:
            # Only remove if still in DISCOVERED state
            result = self.conn.execute(
                """UPDATE videos SET triage_status = 'SKIPPED'
                   WHERE video_id = ? AND triage_status = 'DISCOVERED'""",
                (video_id,),
            )
            self.conn.commit()
            if result.rowcount > 0:
                self.log_pipeline_event(
                    level="INFO",
                    message=f"Video removed from queue: {video_id}",
                    video_id=video_id
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove video from queue: {e}")
            return False

    # -------------------------------------------------------------------
    # Data Deletion with Cascade
    # -------------------------------------------------------------------

    def delete_video_data(self, video_id: str, reason: str = "") -> dict:
        """
        Delete all data associated with a video.
        
        Returns dict with:
        - chunks_deleted: count
        - guests_removed: count  
        - appearances_removed: count
        - claims_deleted: count
        - quotes_deleted: count
        - video_deleted: bool
        
        Note: Video WILL be reprocessable after deletion - just upload same URL again
        """
        deleted = {
            "chunks_deleted": 0,
            "guests_removed": 0,
            "appearances_removed": 0,
            "claims_deleted": 0,
            "quotes_deleted": 0,
            "video_deleted": False,
        }
        
        try:
            # Get video details before deletion
            video = self.get_video(video_id)
            if not video:
                return deleted
            
            # 1. Get all guests for this video to decide if we should delete them
            guest_appearances = self.conn.execute(
                """SELECT DISTINCT guest_id FROM guest_appearances 
                   WHERE video_id = ?""",
                (video_id,),
            ).fetchall()
            
            guest_ids_in_video = [row["guest_id"] for row in guest_appearances]
            
            # 2. Delete guest appearances
            result = self.conn.execute(
                "DELETE FROM guest_appearances WHERE video_id = ?",
                (video_id,),
            )
            deleted["appearances_removed"] = result.rowcount
            
            # 3. Delete claims
            result = self.conn.execute(
                "DELETE FROM claims WHERE video_id = ?",
                (video_id,),
            )
            deleted["claims_deleted"] = result.rowcount
            
            # 4. Delete quotes
            result = self.conn.execute(
                "DELETE FROM quotes WHERE video_id = ?",
                (video_id,),
            )
            deleted["quotes_deleted"] = result.rowcount
            
            # 5. Delete chunks (also updates FTS via triggers)
            result = self.conn.execute(
                "DELETE FROM transcript_chunks WHERE video_id = ?",
                (video_id,),
            )
            deleted["chunks_deleted"] = result.rowcount
            
            # 6. Delete temp state if exists
            self.conn.execute(
                "DELETE FROM pipeline_temp_state WHERE video_id = ?",
                (video_id,),
            )
            
            # 7. Delete video summary
            self.conn.execute(
                "DELETE FROM video_summaries WHERE video_id = ?",
                (video_id,),
            )
            
            # 8. Reset video to DISCOVERED state so it can be reprocessed
            self.conn.execute(
                """UPDATE videos 
                   SET checkpoint_stage = 'METADATA_HARVESTED',
                       triage_status = 'DISCOVERED',
                       triage_reason = 'Re-discoverable after data deletion',
                       updated_at = CURRENT_TIMESTAMP
                   WHERE video_id = ?""",
                (video_id,),
            )
            deleted["video_deleted"] = True
            
            # 9. Check if any guests only appeared in this video and delete them
            for guest_id in guest_ids_in_video:
                remaining = self.conn.execute(
                    "SELECT COUNT(*) as cnt FROM guest_appearances WHERE guest_id = ?",
                    (guest_id,),
                ).fetchone()
                if remaining["cnt"] == 0:
                    # This guest no longer appears anywhere
                    self.conn.execute(
                        "DELETE FROM guests WHERE guest_id = ?",
                        (guest_id,),
                    )
                    deleted["guests_removed"] += 1
            
            # 10. Log the deletion
            import json
            self.conn.execute(
                """INSERT INTO deletion_history 
                   (deletion_type, video_id, deleted_by, reason, data_deleted)
                   VALUES (?, ?, ?, ?, ?)""",
                ("video", video_id, "user", reason, json.dumps(deleted)),
            )
            
            self.conn.commit()
            logger.info(f"Deleted data for video {video_id}: {deleted}")
            
        except Exception as e:
            logger.error(f"Error deleting video data: {e}")
            self.conn.rollback()
        
        return deleted

    def sync_channel_video_counts(self, channel_id: str = None) -> None:
        """Synchronize the total_videos and processed_videos counts in channels table."""
        try:
            if channel_id:
                # Update specific channel
                self.conn.execute(
                    """UPDATE channels 
                       SET total_videos = (SELECT COUNT(*) FROM videos WHERE channel_id = ?),
                           processed_videos = (SELECT COUNT(*) FROM videos WHERE channel_id = ? AND checkpoint_stage = 'DONE')
                       WHERE channel_id = ?""",
                    (channel_id, channel_id, channel_id),
                )
            else:
                # Update all channels
                self.conn.execute(
                    """UPDATE channels 
                       SET total_videos = (SELECT COUNT(*) FROM videos v WHERE v.channel_id = channels.channel_id),
                           processed_videos = (SELECT COUNT(*) FROM videos v WHERE v.channel_id = channels.channel_id AND v.checkpoint_stage = 'DONE')"""
                )
            self.conn.commit()
            logger.debug(f"Synced video counts for {'channel ' + channel_id if channel_id else 'all channels'}")
        except Exception as e:
            logger.error(f"Failed to sync channel video counts: {e}")
            self.conn.rollback()

    def delete_channel_data(self, channel_id: str, reason: str = "") -> dict:
        """
        Delete all videos and associated data for a channel.
        
        Returns summary of what was deleted.
        """
        deleted = {
            "videos_deleted": 0,
            "chunks_deleted": 0,
            "guests_removed": 0,
            "channel_reset": False,
        }
        
        try:
            # Get all videos in channel
            videos = self.get_videos_by_channel(channel_id)
            
            for video in videos:
                video_deleted = self.delete_video_data(video.video_id, reason)
                deleted["videos_deleted"] += 1
                deleted["chunks_deleted"] += video_deleted.get("chunks_deleted", 0)
                deleted["guests_removed"] += video_deleted.get("guests_removed", 0)
            
            # Reset channel stats
            self.conn.execute(
                """UPDATE channels 
                   SET processed_videos = 0, last_scanned_at = NULL
                   WHERE channel_id = ?""",
                (channel_id,),
            )
            deleted["channel_reset"] = True
            
            # Log the deletion
            import json
            self.conn.execute(
                """INSERT INTO deletion_history 
                   (deletion_type, channel_id, deleted_by, reason, data_deleted)
                   VALUES (?, ?, ?, ?, ?)""",
                ("channel", channel_id, "user", reason, json.dumps(deleted)),
            )
            
            self.conn.commit()
            logger.info(f"Deleted data for channel {channel_id}: {deleted}")
            
        except Exception as e:
            logger.error(f"Error deleting channel data: {e}")
            self.conn.rollback()
        
        return deleted

    def get_deletion_history(self, limit: int = 50) -> list[dict]:
        """Get deletion history."""
        rows = self.conn.execute(
            """SELECT * FROM deletion_history 
               ORDER BY deleted_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Research Chat Methods
    # -------------------------------------------------------------------

    def create_chat_session(self, name: str) -> str:
        """Create a new chat session and return its ID."""
        session_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO chat_sessions (session_id, name) VALUES (?, ?)",
            (session_id, name)
        )
        self.conn.commit()
        return session_id

    def get_chat_sessions(self, limit: int = 20) -> list[ChatSession]:
        """Get recent chat sessions."""
        rows = self.conn.execute(
            "SELECT * FROM chat_sessions ORDER BY last_active DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [ChatSession(**dict(r)) for r in rows]

    def delete_chat_session(self, session_id: str):
        """Delete a chat session and all its messages."""
        self.conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()

    def insert_chat_message(self, session_id: str, role: str, content: str, 
                            suggested_json: str = "[]", citations_json: str = "[]"):
        """Save a message to the chat history."""
        message_id = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO chat_messages 
               (message_id, session_id, role, content, suggested_json, citations_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (message_id, session_id, role, content, suggested_json, citations_json)
        )
        # Update session activity
        self.conn.execute(
            "UPDATE chat_sessions SET last_active = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,)
        )
        self.conn.commit()

    def get_chat_history(self, session_id: str) -> list[ChatMessage]:
        """Retrieve full message history for a session."""
        rows = self.conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        ).fetchall()
        return [ChatMessage(**dict(r)) for r in rows]

    def rename_chat_session(self, session_id: str, new_name: str):
        """Update the name of a chat session."""
        self.conn.execute(
            "UPDATE chat_sessions SET name = ? WHERE session_id = ?",
            (new_name, session_id)
        )
        self.conn.commit()

