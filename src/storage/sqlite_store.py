"""
SQLite storage layer for knowledgeVault-YT.

Manages the relational database: Channels, Videos, Guests,
Guest Appearances, Transcript Chunks, and Scan Checkpoints.
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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
    checkpoint_stage: str = "METADATA_HARVESTED"
    created_at: str = ""
    updated_at: str = ""


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
]


class SQLiteStore:
    """SQLite database manager for knowledgeVault-YT.

    Supports context manager protocol for automatic cleanup:
        with SQLiteStore(path) as db:
            db.insert_video(...)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._run_migrations()
        logger.info(f"SQLite store initialized: {db_path}")

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

    # -------------------------------------------------------------------
    # Channels
    # -------------------------------------------------------------------

    def upsert_channel(self, channel: Channel) -> None:
        """Insert or update a channel record."""
        self.conn.execute(
            """INSERT INTO channels (channel_id, name, url, description, category,
                   language_iso, discovered_at, total_videos)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
               ON CONFLICT(channel_id) DO UPDATE SET
                   name = excluded.name,
                   description = excluded.description,
                   total_videos = excluded.total_videos,
                   last_scanned_at = CURRENT_TIMESTAMP""",
            (channel.channel_id, channel.name, channel.url,
             channel.description, channel.category,
             channel.language_iso, channel.total_videos),
        )
        self.conn.commit()

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
                       language_iso, triage_status, checkpoint_stage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED', 'METADATA_HARVESTED')""",
                (video.video_id, video.channel_id, video.title, video.url,
                 video.description, video.duration_seconds, video.upload_date,
                 video.view_count, json.dumps(video.tags),
                 video.language_iso),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Duplicate video_id

    def get_video(self, video_id: str) -> Optional[Video]:
        """Get a video by ID."""
        row = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["tags"] = json.loads(d.pop("tags_json", "[]"))
        return Video(**d)

    def get_videos_by_status(self, status: str, limit: int = 100) -> list[Video]:
        """Get videos by triage status."""
        rows = self.conn.execute(
            "SELECT * FROM videos WHERE triage_status = ? ORDER BY created_at LIMIT ?",
            (status, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.pop("tags_json", "[]"))
            result.append(Video(**d))
        return result

    def get_videos_by_channel(self, channel_id: str) -> list[Video]:
        """Get all videos for a channel."""
        rows = self.conn.execute(
            "SELECT * FROM videos WHERE channel_id = ? ORDER BY upload_date DESC",
            (channel_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.pop("tags_json", "[]"))
            result.append(Video(**d))
        return result

    def update_triage_status(
        self, video_id: str, status: str, reason: str = "", confidence: float = 0.0
    ) -> None:
        """Update a video's triage status."""
        self.conn.execute(
            """UPDATE videos
               SET triage_status = ?, triage_reason = ?, triage_confidence = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE video_id = ?""",
            (status, reason, confidence, video_id),
        )
        self.conn.commit()

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
                 AND checkpoint_stage != 'DONE'
               ORDER BY created_at ASC""",
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.pop("tags_json", "[]"))
            result.append(Video(**d))
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
            self.conn.execute(
                """UPDATE guests SET mention_count = mention_count + 1,
                       last_seen = CURRENT_TIMESTAMP WHERE guest_id = ?""",
                (row["guest_id"],),
            )
            self.conn.commit()
            d = dict(row)
            d["aliases"] = json.loads(d.pop("aliases_json", "[]"))
            d["mention_count"] = d["mention_count"] + 1
            return Guest(**d)
        else:
            cursor = self.conn.execute(
                """INSERT INTO guests (canonical_name, entity_type, mention_count)
                   VALUES (?, ?, 1)""",
                (name, entity_type),
            )
            self.conn.commit()
            return Guest(
                guest_id=cursor.lastrowid,
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
            pass  # Duplicate appearance

    # -------------------------------------------------------------------
    # Transcript Chunks
    # -------------------------------------------------------------------

    def insert_chunks(self, chunks: list[TranscriptChunk]) -> int:
        """Bulk insert transcript chunks. Returns count inserted."""
        inserted = 0
        for chunk in chunks:
            try:
                self.conn.execute(
                    """INSERT INTO transcript_chunks
                           (chunk_id, video_id, chunk_index, raw_text, cleaned_text,
                            word_count, start_timestamp, end_timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (chunk.chunk_id, chunk.video_id, chunk.chunk_index,
                     chunk.raw_text, chunk.cleaned_text, chunk.word_count,
                     chunk.start_timestamp, chunk.end_timestamp),
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
        quotes_json: str = "[]"
    ) -> None:
        """Save per-chunk analysis results (topics, entities, claims, quotes)."""
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
    # Pipeline Temp State
    # -------------------------------------------------------------------

    def save_temp_state(
        self, video_id: str, raw_text: str = "",
        segments_json: str = "[]", cleaned_text: str = ""
    ) -> None:
        """Save or update intermediate pipeline state for a video."""
        self.conn.execute(
            """INSERT INTO pipeline_temp_state (video_id, raw_text, segments_json, cleaned_text)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(video_id) DO UPDATE SET
                   raw_text = excluded.raw_text,
                   segments_json = excluded.segments_json,
                   cleaned_text = excluded.cleaned_text""",
            (video_id, raw_text, segments_json, cleaned_text),
        )
        self.conn.commit()

    def get_temp_state(self, video_id: str) -> Optional[dict]:
        """Get intermediate pipeline state for a video.

        Returns dict with keys: video_id, raw_text, segments_json, cleaned_text.
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

    def update_scan_checkpoint(
        self, scan_id: str, total_discovered: int = 0,
        total_processed: int = 0, last_video_id: str = "",
        status: str = ""
    ) -> None:
        """Update an existing scan checkpoint."""
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
        self.conn.execute(
            f"UPDATE scan_checkpoints SET {', '.join(updates)} WHERE scan_id = ?",
            params,
        )
        self.conn.commit()

    def get_scan_checkpoint(self, scan_id: str) -> Optional[ScanCheckpoint]:
        """Get a scan checkpoint by ID."""
        row = self.conn.execute(
            "SELECT * FROM scan_checkpoints WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        if row is None:
            return None
        return ScanCheckpoint(**dict(row))

    def get_active_scans(self) -> list[ScanCheckpoint]:
        """Get all in-progress scans."""
        rows = self.conn.execute(
            "SELECT * FROM scan_checkpoints WHERE status = 'IN_PROGRESS' ORDER BY started_at DESC"
        ).fetchall()
        return [ScanCheckpoint(**dict(r)) for r in rows]

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
            WHERE v.duration_seconds > 0 AND v.checkpoint_stage = 'DONE'
            """
        ).fetchall()
        
        result = []
        for row in rows:
            dur_mins = max(1, row["duration_seconds"] // 60)
            score = (row["chunk_count"] * 1.5 + row["guest_count"] * 5.0) / dur_mins
            r_dict = dict(row)
            r_dict["density_score"] = score
            result.append(r_dict)
            
        result.sort(key=lambda x: x["density_score"], reverse=True)
        return result[:limit]

    # -------------------------------------------------------------------
    # Pipeline Statistics
    # -------------------------------------------------------------------

    def get_pipeline_stats(self) -> dict:
        """Get aggregate pipeline statistics for the dashboard."""
        stats = {}
        for status in ["DISCOVERED", "ACCEPTED", "REJECTED", "PENDING_REVIEW"]:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM videos WHERE triage_status = ?",
                (status,),
            ).fetchone()
            stats[status.lower()] = row["cnt"]

        # Checkpoint stages
        for stage in ["TRANSCRIPT_FETCHED", "REFINED", "CHUNKED", "EMBEDDED", "DONE"]:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM videos WHERE checkpoint_stage = ?",
                (stage,),
            ).fetchone()
            stats[stage.lower()] = row["cnt"]

        # Totals
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM videos").fetchone()
        stats["total_videos"] = row["cnt"]

        row = self.conn.execute("SELECT COUNT(*) as cnt FROM channels").fetchone()
        stats["total_channels"] = row["cnt"]

        row = self.conn.execute("SELECT COUNT(*) as cnt FROM guests").fetchone()
        stats["total_guests"] = row["cnt"]

        row = self.conn.execute("SELECT COUNT(*) as cnt FROM transcript_chunks").fetchone()
        stats["total_chunks"] = row["cnt"]

        return stats

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
            rows = self.conn.execute(
                """SELECT chunk_id, video_id,
                          rank AS bm25_score,
                          snippet(chunks_fts, 2, '<b>', '</b>', '...', 30) AS snippet
                   FROM chunks_fts
                   WHERE content MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
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

