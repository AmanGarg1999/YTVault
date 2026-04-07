"""
Saga Worker for knowledgeVault-YT — P0-A: Triple-Store Atomic Sync.

Implements the Saga (outbox) pattern to ensure ChromaDB and Neo4j stay
consistent with SQLite.  After every ingestion scan, `SagaWorker.drain()`
reads pending rows from `sync_outbox` and retries each incomplete store
sync idempotently.

Usage:
    worker = SagaWorker(db, vector_store, graph_store)
    fixed = worker.drain()   # Returns number of entries repaired
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SagaWorker:
    """Drains the sync_outbox table and retries failed store syncs.

    Design:
        - ChromaDB upsert is idempotent (same chunk_id → overwrite).
        - Neo4j MERGE is idempotent by design.
        - We retry each store independently so a partial success is not lost.
        - Rows with no pending work are cleaned up at the end.
    """

    # Maximum retries before we log an error and skip the entry
    MAX_RETRIES = 5

    def __init__(self, db, vector_store=None, graph_store=None):
        """
        Args:
            db: SQLiteStore instance (thread-local, already initialised).
            vector_store: VectorStore instance (optional — skipped if None).
            graph_store: GraphStore instance (optional — skipped if None).
        """
        self.db = db
        self.vector_store = vector_store
        self.graph_store = graph_store

    def drain(self) -> int:
        """Process all pending outbox entries.

        Returns:
            Number of entries fully resolved (both stores done).
        """
        pending = self.db.get_pending_outbox(limit=200)
        if not pending:
            logger.debug("SagaWorker: no pending outbox entries")
            return 0

        logger.info(f"SagaWorker: draining {len(pending)} pending outbox entries")
        resolved = 0

        for entry in pending:
            video_id = entry["video_id"]

            if entry.get("retry_count", 0) >= self.MAX_RETRIES:
                logger.warning(
                    f"SagaWorker: skipping {video_id} — exceeded {self.MAX_RETRIES} retries"
                )
                continue

            try:
                fixed = self._repair_entry(video_id, entry)
                if fixed:
                    resolved += 1
            except Exception as e:
                logger.error(f"SagaWorker: error repairing {video_id}: {e}")
                self.db.mark_outbox_error(video_id, str(e))

        # Remove fully completed rows to keep the outbox small
        cleaned = self.db.cleanup_done_outbox()
        logger.info(
            f"SagaWorker: resolved {resolved}, cleaned up {cleaned} completed entries"
        )
        return resolved

    def _repair_entry(self, video_id: str, entry: dict) -> bool:
        """Retry incomplete store syncs for a single video.

        Returns True if both stores are now confirmed done.
        """
        chroma_done = bool(entry.get("chroma_done", False))
        neo4j_done = bool(entry.get("neo4j_done", False))
        all_done = True

        # --- Retry ChromaDB ---
        if not chroma_done:
            if self.vector_store is None:
                logger.debug(f"SagaWorker: VectorStore not available, skipping chroma for {video_id}")
                all_done = False
            else:
                try:
                    chunks = self.db.get_chunks_for_video(video_id)
                    if chunks:
                        video = self.db.get_video(video_id)
                        channel_id = video.channel_id if video else ""
                        upload_date = video.upload_date if video else ""
                        language_iso = video.language_iso if video else "en"

                        self.vector_store.upsert_chunks(
                            chunks,
                            channel_id=channel_id,
                            upload_date=upload_date,
                            language_iso=language_iso,
                        )
                    self.db.mark_outbox_chroma_done(video_id)
                    logger.info(f"SagaWorker: ChromaDB sync repaired for {video_id}")
                    chroma_done = True
                except Exception as e:
                    logger.warning(f"SagaWorker: ChromaDB retry failed for {video_id}: {e}")
                    self.db.mark_outbox_error(video_id, f"chroma: {e}")
                    all_done = False

        # --- Retry Neo4j ---
        if not neo4j_done:
            if self.graph_store is None:
                logger.debug(f"SagaWorker: GraphStore not available, skipping neo4j for {video_id}")
                all_done = False
            else:
                try:
                    self._resync_neo4j(video_id)
                    self.db.mark_outbox_neo4j_done(video_id)
                    logger.info(f"SagaWorker: Neo4j sync repaired for {video_id}")
                    neo4j_done = True
                except Exception as e:
                    logger.warning(f"SagaWorker: Neo4j retry failed for {video_id}: {e}")
                    self.db.mark_outbox_error(video_id, f"neo4j: {e}")
                    all_done = False

        return all_done and chroma_done and neo4j_done

    def _resync_neo4j(self, video_id: str) -> None:
        """Re-push a video's nodes and relationships to Neo4j."""
        video = self.db.get_video(video_id)
        if not video:
            logger.warning(f"SagaWorker: video {video_id} not found in SQLite, skipping Neo4j sync")
            return

        graph = self.graph_store
        graph.upsert_video(
            video_id=video.video_id,
            title=video.title,
            channel_id=video.channel_id,
            upload_date=video.upload_date,
            duration=video.duration_seconds,
        )

        topics = self.db.get_video_aggregated_topics(video_id)
        entity_names = self.db.get_video_aggregated_entities(video_id)

        for topic in topics:
            graph.link_video_to_topic(video_id, topic["name"], topic.get("relevance", 1.0))

        for name in entity_names:
            graph.upsert_guest(name)
            graph.link_guest_to_video(name, video_id)
            for topic in topics:
                graph.link_guest_to_topic(name, topic["name"])

        topic_names = [t["name"] for t in topics]
        for i, t1 in enumerate(topic_names):
            for t2 in topic_names[i + 1:]:
                graph.link_related_topics(t1, t2)

    def get_status(self) -> dict:
        """Return a human-readable outbox health summary."""
        stats = self.db.get_outbox_stats()
        return {
            "total_entries": stats.get("total", 0) or 0,
            "pending_chroma": stats.get("pending_chroma", 0) or 0,
            "pending_neo4j": stats.get("pending_neo4j", 0) or 0,
            "fully_done": stats.get("fully_done", 0) or 0,
        }
