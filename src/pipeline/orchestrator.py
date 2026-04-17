"""
Pipeline orchestrator for knowledgeVault-YT.

Coordinates the full ingestion pipeline from URL input through to
indexed knowledge graph. Handles both fresh scans and resumed scans.
"""

import json
import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from src.config import ensure_data_dirs, get_settings
from src.ingestion.discovery import (
    ParsedURL,
    discover_video_ids,
    extract_channel_info,
    extract_video_metadata,
    parse_youtube_url,
)
from src.ingestion.refinement import (
    TextNormalizer,
    fetch_sponsor_segments,
    strip_sponsored_segments,
)
from src.ingestion.transcript import TimestampedSegment, fetch_transcript
from src.ingestion.translator import TranslationEngine
from src.ingestion.triage import TriageDecision, TriageEngine
from src.pipeline.checkpoint import CheckpointManager
from src.pipeline.metrics import PerformanceMetricsCollector, StageTimer
from src.storage.sqlite_store import Channel, SQLiteStore, TranscriptChunk
from src.storage.vector_store import VectorStore, sliding_window_chunk

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the full ingestion-to-index pipeline.

    Stages:
        1. Discovery — Parse URL, discover video IDs, harvest metadata
        2. Triage — Rule-based + LLM classification
        3. Transcript — Fetch and clean transcripts
        4. Refinement — SponsorBlock filtering + text normalization
        5. Chunking — Sliding window chunking
        6. Embedding — ChromaDB vector indexing
        7. Graph Sync — Neo4j entity and relationship creation
    """

    def __init__(self):
        """Initialize orchestrator core services and internal state."""
        ensure_data_dirs()
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self._db_path = self.settings["sqlite"]["path"]
        self.current_scan_id = None

        # Thread-local storage for DB and CheckpointManager
        self._tl = threading.local()

        # Callbacks for UI progress updates
        self._on_progress = None
        self._on_status = None

        # Service lazy-load markers
        self._vector_store: Optional[VectorStore] = None
        self._graph_store = None
        self._metrics = None
        self._triage = None
        self._normalizer = None
        self._translator = None
        self._corroborator = None

    @property
    def _thread_local(self) -> threading.local:
        """Access thread-local storage."""
        if not hasattr(self, "_tl"):
            self._tl = threading.local()
        return self._tl

    @property
    def db_path(self) -> str:
        """Get the SQLite database path."""
        if not hasattr(self, "_db_path") or self._db_path is None:
            self._db_path = get_settings()["sqlite"]["path"]
        return self._db_path

    @property
    def db(self) -> SQLiteStore:
        """Get or create a thread-local SQLiteStore instance."""
        if not hasattr(self._thread_local, "db") or self._thread_local.db is None:
            self._thread_local.db = SQLiteStore(self.db_path)
        return self._thread_local.db

    @db.setter
    def db(self, value: SQLiteStore):
        self._thread_local.db = value

    @property
    def checkpoint(self) -> CheckpointManager:
        """Get or create a thread-local CheckpointManager instance."""
        if not hasattr(self._thread_local, "checkpoint") or self._thread_local.checkpoint is None:
            self._thread_local.checkpoint = CheckpointManager(self.db)
        return self._thread_local.checkpoint

    @checkpoint.setter
    def checkpoint(self, value: CheckpointManager):
        self._thread_local.checkpoint = value

    @property
    def metrics(self) -> PerformanceMetricsCollector:
        """Lazy-init metrics collector."""
        if not hasattr(self, "_metrics") or self._metrics is None:
            self._metrics = PerformanceMetricsCollector(self.db_path)
        return self._metrics

    @metrics.setter
    def metrics(self, value: PerformanceMetricsCollector):
        self._metrics = value

    @property
    def triage(self) -> TriageEngine:
        """Lazy-init triage engine."""
        if not hasattr(self, "_triage") or self._triage is None:
            self._triage = TriageEngine()
        return self._triage

    @triage.setter
    def triage(self, value: TriageEngine):
        self._triage = value

    @property
    def normalizer(self) -> TextNormalizer:
        """Lazy-init text normalizer."""
        if not hasattr(self, "_normalizer") or self._normalizer is None:
            self._normalizer = TextNormalizer()
        return self._normalizer

    @normalizer.setter
    def normalizer(self, value: TextNormalizer):
        self._normalizer = value

    @property
    def translator(self) -> TranslationEngine:
        """Lazy-init translation engine."""
        if not hasattr(self, "_translator") or self._translator is None:
            self._translator = TranslationEngine()
        return self._translator

    @translator.setter
    def translator(self, value: TranslationEngine):
        self._translator = value

    @property
    def vector_store(self) -> VectorStore:
        """Lazy-init the vector store."""
        if self._vector_store is None:
            from src.storage.vector_store import VectorStore
            self._vector_store = VectorStore()
        return self._vector_store

    @vector_store.setter
    def vector_store(self, value: VectorStore):
        self._vector_store = value

    @property
    def corroborator(self):
        """Lazy-init claim corroborator."""
        if self._corroborator is None:
            from src.intelligence.claim_corroborator import ClaimCorroborator
            self._corroborator = ClaimCorroborator(self.db, self.vector_store)
        return self._corroborator

    @property
    def graph_store(self):
        """Lazy-init the Neo4j graph store (created once, reused across videos)."""
        if self._graph_store is None:
            from src.storage.graph_store import GraphStore
            self._graph_store = GraphStore()
        return self._graph_store

    def close(self):
        """Release all resources."""
        self.db.close()
        if self._graph_store is not None:
            self._graph_store.close()
            self._graph_store = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def set_callbacks(self, on_progress=None, on_status=None):
        """Set UI callback functions for progress reporting."""
        self._on_progress = on_progress
        self._on_status = on_status

    def _report_status(self, message: str):
        """Report status to UI callback if set."""
        logger.info(message)
        if self._on_status:
            self._on_status(message)

    def _check_pause_state(self, scan_id: str) -> bool:
        """Check if scan is paused. Returns True if paused/stopped."""
        control = self.db.get_control_state(scan_id)
        if control:
            if control.status in ("PAUSED", "STOPPED"):
                reason = control.pause_reason or "No reason given"
                self._report_status(f"Pipeline {control.status}: {reason}")
                return True
        return False

    def _check_stop_requested(self, scan_id: str) -> bool:
        """Check if stop was requested. Returns True if should stop."""
        control = self.db.get_control_state(scan_id)
        return control and control.status == "STOPPED"

    # -------------------------------------------------------------------
    # Full Pipeline
    # -------------------------------------------------------------------

    def run(self, url: str, force_metadata_refresh: bool = False) -> str:
        """Run the full pipeline for a given YouTube URL."""
        parsed = parse_youtube_url(url)
        self._report_status(f"Parsed URL: {parsed.url_type} — {url}")

        # Create scan checkpoint
        active_scan = self.db.get_active_scan_for_url(url)
        
        # Track counts
        processed_count = 0
        discovered_count = 0
        session_vids = set()
        
        if active_scan:
            logger.info(f"Using existing active scan {active_scan.scan_id} for {url}")
            scan_id = active_scan.scan_id
            # Initialize with latest DB values for continuity
            processed_count = active_scan.total_processed
            discovered_count = active_scan.total_discovered
        else:
            scan_id = self.checkpoint.create_scan(url, parsed.url_type)
            self.db.set_control_state(scan_id, "RUNNING")


        try:
            import queue
            from threading import Thread

            discovery_queue = queue.Queue()
            
            def discovery_worker():
                try:
                    self._stage_discover_stream(url, parsed, scan_id, discovery_queue, force_metadata_refresh)
                except Exception as e:
                    logger.error(f"Discovery thread failed: {e}")
                    self.db.log_pipeline_event(
                        level="ERROR",
                        message=f"Discovery failed: {str(e)}",
                        scan_id=scan_id,
                        stage="DISCOVERY",
                        error_detail=str(e)
                    )
                finally:
                    discovery_queue.put(None)  # Sentinel

            thread = threading.Thread(target=discovery_worker, daemon=True)
            thread.start()

            max_workers = self.settings.get("pipeline", {}).get("max_parallel_videos", 4)
            active_futures = {} # vid -> future
            
            self._report_status(f"Starting parallel processing with max_workers={max_workers}")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while True:
                    # 1. Check for stop requests
                    if self._check_stop_requested(scan_id):
                        self._report_status("Pipeline stop requested - aborting")
                        # We don't cancel active futures here to allow clean DB state, 
                        # but we stop submitting new ones.
                        break
                    
                    # 2. Wait while paused
                    while self._check_pause_state(scan_id):
                        time.sleep(1)
                    
                    # 3. Reaper: clean up completed futures and update progress
                    done_vids = [vid for vid, f in active_futures.items() if f.done()]
                    for vid in done_vids:
                        future = active_futures.pop(vid)
                        processed_count += 1
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"Video {vid} failed in parallel worker: {e}")
                        
                        self.checkpoint.update_scan_progress(
                            scan_id, total_processed=processed_count,
                            last_video_id=vid,
                        )

                    # 4. Get next item from discovery (non-blocking enough to allow reaped/flags)
                    try:
                        item = discovery_queue.get(timeout=0.5)
                    except queue.Empty:
                        if not thread.is_alive() and not active_futures:
                            break # Everything done
                        continue
                    
                    if item is None: # Sentinel from discovery worker
                        if not active_futures:
                            break
                        continue # Wait for active futures to finish
                    
                    vid, is_new = item
                    
                    if is_new or force_metadata_refresh:
                        if vid not in session_vids:
                            discovered_count += 1
                            session_vids.add(vid)
                            
                        # Report DISCOVERY progress immediately to DB
                        self.checkpoint.update_scan_progress(
                            scan_id, total_discovered=discovered_count
                        )
                        
                        if self.db.claim_video(vid, scan_id):
                            self._report_status(f"Queuing video {vid}")
                            
                            # If forcing refresh on an existing video, reset its checkpoint
                            if not is_new and force_metadata_refresh:
                                logger.info(f"Forcing re-process: resetting checkpoint for {vid}")
                                self.db.update_checkpoint_stage(vid, "METADATA_HARVESTED")
                                
                            active_futures[vid] = executor.submit(self._process_single_video, vid, scan_id)
                        else:
                            logger.info(f"Skipping video {vid}: already locked by another scan")
                    else:
                        # Already processed; ensure we count it toward discovery if it's new to this session
                        if vid not in session_vids:
                             # DO NOT increment discovered_count if it's already in the resumed baseline
                             # Actually, we should only increment if we exceed the resumed baseline
                             # or if we started from 0 (though we start from DB value now).
                             session_vids.add(vid)

                # Final reaper for remaining active futures
                while active_futures:
                    done_vids = [vid for vid, f in active_futures.items() if f.done()]
                    if not done_vids:
                        time.sleep(1)
                        continue
                        
                    for vid in done_vids:
                        future = active_futures.pop(vid)
                        processed_count += 1
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"Video {vid} failed in final cleanup: {e}")
                        
                        self.checkpoint.update_scan_progress(
                            scan_id, total_processed=processed_count,
                            last_video_id=vid,
                        )

            self.checkpoint.complete_scan(scan_id)
            self.db.release_all_locks(scan_id)
            self.db.set_control_state(scan_id, "RUNNING")

            # P0-A: Drain any incomplete outbox entries caused by mid-scan crashes
            try:
                from src.pipeline.saga_worker import SagaWorker
                saga = SagaWorker(
                    db=self.db,
                    vector_store=self._vector_store,
                    graph_store=self._graph_store,
                )
                fixed = saga.drain()
                if fixed:
                    self._report_status(f"Saga worker repaired {fixed} diverged entries")
            except Exception as e:
                logger.warning(f"Saga drain failed (non-critical): {e}")

            # P0-C: Clean up temp state rows for completed videos
            try:
                cleaned = self.db.cleanup_done_temp_states()
                if cleaned:
                    self._report_status(f"Temp state cleanup: removed {cleaned} stale rows")
            except Exception as e:
                logger.warning(f"Temp state cleanup failed (non-critical): {e}")

            self._report_status(f"Scan {scan_id} completed: {processed_count} videos processed")
            return scan_id

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.db.log_pipeline_event(
                level="ERROR",
                message=f"Pipeline failed: {str(e)}",
                scan_id=scan_id,
                error_detail=str(e)
            )
            self.checkpoint.fail_scan(scan_id)
            raise

    def resume(self, scan_id: str) -> None:
        """Resume an interrupted scan from the last checkpoint.

        Each video resumes from its individual checkpoint stage.
        """
        pending = self.checkpoint.get_resumable_videos()
        if not pending:
            self._report_status(f"No videos to resume for scan {scan_id}")
            return

        for i, video in enumerate(pending):
            if self.db.claim_video(video.video_id, scan_id):
                try:
                    self._report_status(
                        f"Resuming {i + 1}/{len(pending)}: {video.title[:50]}... "
                        f"(from stage: {video.checkpoint_stage})"
                    )
                    self._resume_video(video, scan_id)
                finally:
                    self.db.release_video(video.video_id, scan_id)
            else:
                logger.info(f"Skipping video {video.video_id}: locked by another scan")

        self.checkpoint.complete_scan(scan_id)

    def process_manually_overridden_videos(self) -> int:
        """Process all recently manually-overridden videos (force-accepted rejected ones).
        
        Returns count of videos processed.
        """
        manually_overridden = self.db.get_manually_overridden_videos()
        
        if not manually_overridden:
            self._report_status("No manually-overridden videos to process")
            return 0
        
        self._report_status(
            f"Processing {len(manually_overridden)} manually-overridden videos..."
        )
        
        for i, video in enumerate(manually_overridden):
            # Use a dummy scan_id since this is manual
            man_scan_id = f"manual_{int(time.time())}"
            if self.db.claim_video(video.video_id, man_scan_id):
                try:
                    self._report_status(
                        f"Processing manually-accepted {i + 1}/{len(manually_overridden)}: "
                        f"{video.title[:50]}..."
                    )
                    self._resume_video(video, man_scan_id)
                finally:
                    self.db.release_video(video.video_id, man_scan_id)
            else:
                logger.info(f"Skipping manual override for {video.video_id}: locked")
        
        self._report_status(
            f"Completed processing {len(manually_overridden)} manually-overridden videos"
        )
        return len(manually_overridden)

    def repair_vault_health(self) -> dict:
        """Systematically identify and repair data gaps across the vault.
        
        Returns:
            Dict with repair counts by category.
        """
        self._report_status("Starting Comprehensive Vault Health Check...")
        
        counts = {"transcripts": 0, "summaries": 0, "heatmaps": 0, "discovery": 0}
        
        # 1. Identify missing transcripts (Critical)
        missing_transcripts = self.db.get_videos_missing_transcripts()
        counts["transcripts"] = len(missing_transcripts)
        
        # 2. Identify missing summaries (New Stage)
        missing_summaries = self.db.get_videos_missing_summaries()
        counts["summaries"] = len(missing_summaries)
        
        # 3. Identify missing heatmaps (V14 Migration)
        missing_heatmaps = self.db.get_videos_missing_heatmaps()
        counts["heatmaps"] = len(missing_heatmaps)

        # 4. Identify stuck in discovery (New)
        stuck_discovery = self.db.get_videos_by_status_any("DISCOVERED")
        counts["discovery"] = len(stuck_discovery)
        
        total_to_repair = len(set(
            [v.video_id for v in missing_transcripts] +
            [v.video_id for v in missing_summaries] +
            [v.video_id for v in missing_heatmaps] +
            [v.video_id for v in stuck_discovery]
        ))
        
        if total_to_repair == 0:
            self._report_status("✅ Vault Health is 100%. No repairs needed.")
            if self._on_progress:
                self._on_progress(100, 100)
            return counts
            
        self._report_status(f"Repairing {total_to_repair} videos with identified gaps...")
        
        processed_ids = set()
        
        def _do_repair(vids, label):
            for video in vids:
                if video.video_id in processed_ids: continue
                self._report_status(f"Repairing {label}: {video.title[:40]}...")
                
                if label == "Stuck Discovery":
                    self.db.update_checkpoint_stage(video.video_id, "METADATA_HARVESTED")
                elif label == "Heatmap/MetaData":
                    self.db.update_checkpoint_stage(video.video_id, "METADATA_HARVESTED")
                elif label == "Transcript":
                    self.db.update_checkpoint_stage(video.video_id, "TRIAGE_COMPLETE")
                elif label == "Summary":
                    chunks = self.db.get_chunks_for_video(video.video_id)
                    if chunks:
                        self.db.update_checkpoint_stage(video.video_id, "CHUNK_ANALYZED")
                    else:
                        self.db.update_checkpoint_stage(video.video_id, "TRIAGE_COMPLETE")
                
                v_to_resume = self.db.get_video(video.video_id)
                self._resume_video(v_to_resume, "health_repair")
                processed_ids.add(video.video_id)
                
                if self._on_progress:
                    self._on_progress(len(processed_ids), total_to_repair)

        # Process in priority order
        _do_repair(stuck_discovery, "Stuck Discovery")
        _do_repair(missing_heatmaps, "Heatmap/MetaData")
        _do_repair(missing_transcripts, "Transcript")
        _do_repair(missing_summaries, "Summary")
            
        self._report_status(f"Vault Health Repair completed for {len(processed_ids)} videos.")
        return counts

    # -------------------------------------------------------------------
    # Stage Implementations
    # -------------------------------------------------------------------

    def _stage_discover_stream(
        self, url: str, parsed: ParsedURL, scan_id: str, discovery_queue,
        force_metadata_refresh: bool = False
    ) -> None:
        """Stage 1: Discover video IDs and harvest metadata (Streaming).

        P0-E: When force_metadata_refresh=False and the channel has a prior
        last_scanned_at date, passes --dateafter to yt-dlp so only new videos
        are discovered, reducing re-harvest cost from O(n) to O(delta).
        """
        self._report_status("Stage 1: Discovering videos...")

        # P0-E: Determine incremental after_date from channel last_scanned_at
        after_date = None
        if not force_metadata_refresh and parsed.url_type in ("channel", "playlist"):
            try:
                channel_info = extract_channel_info(url)
                self.db.upsert_channel(channel_info)
                # Read back the stored channel to get last_scanned_at
                existing_channel = self.db.get_channel(channel_info.channel_id)
                if existing_channel and existing_channel.last_scanned_at:
                    # last_scanned_at is a datetime string; extract just the date part
                    raw_date = str(existing_channel.last_scanned_at)
                    date_part = raw_date[:10] if len(raw_date) >= 10 else None
                    if date_part and date_part != "None":
                        after_date = date_part
                        self._report_status(
                            f"P0-E Incremental harvest: fetching videos after {after_date}"
                        )
            except Exception as e:
                logger.warning(f"Channel info extraction failed: {e}")
        elif parsed.url_type in ("channel", "playlist"):
            # force_metadata_refresh=True: full harvest, extract channel info
            try:
                channel_info = extract_channel_info(url)
                self.db.upsert_channel(channel_info)
            except Exception as e:
                logger.warning(f"Channel info extraction failed: {e}")

        # Discover video IDs line-by-line
        known_ids = self.db.get_discovered_video_ids()
        discovered_count = 0
        new_ids = []

        from src.ingestion.discovery import discover_video_ids
        for vid in discover_video_ids(url, parsed, after_date=after_date):
            discovered_count += 1
            is_new = vid not in known_ids
            if is_new or force_metadata_refresh:
                new_ids.append(vid)
                # First video identified? Start metadata harvest and put in queue
                # We harvest metadata here to satisfy DB constraints before putting in queue
                try:
                    video, channel = extract_video_metadata(vid)
                    if video and channel:
                        self.db.upsert_channel(channel)
                        self.db.insert_video(video)
                        discovery_queue.put((vid, is_new))
                except Exception as e:
                    logger.error(f"Metadata extraction failed for {vid}: {e}")
            else:
                discovery_queue.put((vid, False))

        self.db.sync_channel_video_counts() # Update counts in channels table
        mode_label = f"(incremental after {after_date})" if after_date else "(full)"
        self._report_status(f"Discovery complete {mode_label}: {discovered_count} videos found")

    def batch_triage(self, video_ids: list[str]) -> dict[str, str]:
        """Run triage classification on a batch of videos concurrently.

        Uses LLMPool for parallel LLM calls when rule-based triage
        yields NEEDS_LLM. Returns dict mapping video_id → triage decision.
        """
        from src.utils.llm_pool import LLMPool, LLMTask

        pool = LLMPool()
        results = {}

        # First pass: rule-based triage (fast, no LLM needed)
        needs_llm = []
        for vid in video_ids:
            video = self.db.get_video(vid)
            if video is None:
                continue
            rule_result = self.triage._rule_filter(video)
            if rule_result.decision.value != "NEEDS_LLM":
                self.db.update_triage_status(
                    vid, status=rule_result.decision.value,
                    reason=rule_result.reason, confidence=rule_result.confidence,
                )
                results[vid] = rule_result.decision.value
            else:
                needs_llm.append(video)

        # Second pass: batch LLM triage for ambiguous videos
        if needs_llm:
            self._report_status(
                f"Batch LLM triage: {len(needs_llm)} videos (rule-based resolved {len(results)})"
            )
            # CALL BATCH CLASSIFY (NEW OPTIMIZATION)
            batch_results = self.triage.batch_classify(needs_llm)

            for vid, res in batch_results.items():
                self.db.update_triage_status(
                    vid,
                    status=res.decision.value,
                    reason=res.reason,
                    confidence=res.confidence,
                )
                results[vid] = res.decision.value

        return results

    def batch_normalize(self, video_ids: list[str]) -> int:
        """Run text normalization on a batch of videos concurrently.

        Returns count of successfully normalized videos.
        """
        from src.utils.llm_pool import LLMPool, LLMTask

        pool = LLMPool()
        tasks = []

        for vid in video_ids:
            state = self.db.get_temp_state(vid)
            if state and state["raw_text"]:
                tasks.append(LLMTask(
                    task_id=vid,
                    fn=self.normalizer.normalize,
                    args=(state["raw_text"],),
                ))

        if not tasks:
            return 0

        self._report_status(f"Batch normalizing {len(tasks)} transcripts...")
        results = pool.submit_batch(tasks)

        count = 0
        for lr in results:
            if lr.success and lr.result:
                state = self.db.get_temp_state(lr.task_id)
                if state:
                    self.db.save_temp_state(
                        video_id=lr.task_id,
                        raw_text=state["raw_text"],
                        segments_json=state["segments_json"],
                        cleaned_text=lr.result,
                    )
                    count += 1

        return count

    def _process_single_video(self, video_id: str, scan_id: str) -> None:
        """Process a single video through all remaining pipeline stages."""
        try:
            video = self.db.get_video(video_id)
            if video is None:
                logger.warning(f"Video {video_id} not found in DB")
                return

            self.current_scan_id = scan_id
            self._resume_video(video, scan_id)
        finally:
            self.db.release_video(video_id, scan_id)

    def _resume_video(self, video, scan_id: str) -> None:
        """Resume processing a video from its current checkpoint stage."""
        stage = video.checkpoint_stage
        remaining = self.checkpoint.get_remaining_stages(stage)

        for next_stage in remaining:
            try:
                if next_stage == "TRIAGE_COMPLETE":
                    self._stage_triage(video, scan_id)
                    # Check if rejected
                    video = self.db.get_video(video.video_id)
                    if video.triage_status == "REJECTED":
                        self.checkpoint.advance(video.video_id, "DONE")
                        return
                    if video.triage_status == "PENDING_REVIEW":
                        return  # Wait for manual review

                elif next_stage == "TRANSCRIPT_FETCHED":
                    success = self._stage_transcript(video, scan_id)
                    if not success:
                        return  # No transcript — already advanced to DONE

                # Execute the stage
                success = True
                if next_stage == "TRANSLATED":
                    success = self._stage_translate(video, scan_id)

                elif next_stage == "SPONSOR_FILTERED":
                    success = self._stage_sponsor_filter(video, scan_id)

                elif next_stage == "TEXT_NORMALIZED":
                    success = self._stage_normalize(video, scan_id)

                elif next_stage == "CHUNKED":
                    success = self._stage_chunk(video, scan_id)

                elif next_stage == "CHUNK_ANALYZED":
                    success = self._stage_chunk_analysis(video, scan_id)

                elif next_stage == "SUMMARIZED":
                    success = self._stage_summarize(video, scan_id)

                elif next_stage == "EMBEDDED":
                    success = self._stage_embed(video, scan_id)

                elif next_stage == "GRAPH_SYNCED":
                    success = self._stage_graph_sync(video, scan_id)

                elif next_stage == "CORROBORATED":
                    success = self._stage_corroborate(video, scan_id)

                elif next_stage == "DONE":
                    self.checkpoint.advance(video.video_id, "DONE")
                    return  # Don't fall through to the advance below

                # STRICT VALIDATION: Only advance if the stage succeeded
                if success is not False:  # None or True are considered "proceed"
                    self.checkpoint.advance(video.video_id, next_stage)
                else:
                    logger.error(f"Stage {next_stage} returned failure for {video.video_id}. Halting.")
                    break

            except Exception as e:
                logger.error(
                    f"Stage {next_stage} failed for {video.video_id}: {e}"
                )
                break  # Stop processing, checkpoint is at last successful stage

    def _stage_triage(self, video, scan_id: str = None) -> bool:
        """Stage 2: Run triage classification."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "TRIAGE", video.video_id, sid):
                result = self.triage.classify(video)
                self.db.update_triage_status(
                    video.video_id,
                    status=result.decision.value,
                    reason=result.reason,
                    confidence=result.confidence,
                    is_tutorial=result.is_tutorial,
                )
                log_level = "SUCCESS" if result.decision.value == "ACCEPTED" else "INFO"
                self.db.log_pipeline_event(
                    level=log_level,
                    message=f"Triage: {video.title[:50]}... → {result.decision.value} ({result.confidence:.0%})",
                    video_id=video.video_id,
                    channel_id=video.channel_id,
                    scan_id=sid,
                    stage="TRIAGE",
                )
                logger.debug(
                    f"Triage: {video.title[:50]}... → {result.decision.value} "
                    f"({result.phase}, {result.latency_ms:.0f}ms)"
                )
                return True
        except Exception as e:
            logger.error(f"Triage failed for {video.video_id}: {e}")
            return False

    def _stage_transcript(self, video, scan_id: str = None) -> bool:
        """Stage 3: Fetch transcript. Returns True if transcript was found."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        with StageTimer(self.metrics, "TRANSCRIPT_FETCHED", video.video_id, sid):
            result = fetch_transcript(video.video_id)
            if result.success:
                self.db.update_transcript_strategy(
                    video.video_id,
                    strategy=result.strategy,
                    language_iso=result.language_iso,
                    needs_translation=result.needs_translation,
                )
                # Serialize segments for later stages (avoids re-fetching)
                segments_json = json.dumps([
                    {"text": s.text, "start": s.start, "duration": s.duration}
                    for s in result.segments
                ])
                # Store in dedicated temp state table (not transcript_chunks)
                self.db.save_temp_state(
                    video_id=video.video_id,
                    raw_text=result.full_text,
                    segments_json=segments_json,
                )
                return True
            else:
                logger.warning(f"No transcript for {video.video_id}: {result.error}")
                self.checkpoint.advance(video.video_id, "DONE")
                return False

    def _stage_translate(self, video, scan_id: str = None) -> bool:
        """Stage 4 (NEW): Translate non-English transcripts to English."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "TRANSLATED", video.video_id, sid):
                state = self.db.get_temp_state(video.video_id)
                if not state:
                    logger.debug(f"No temp state for {video.video_id}, skipping translation")
                    return True

                # Check if translation is needed
                if video.language_iso == "en":
                    logger.debug(f"Video {video.video_id} is English, skipping translation")
                    return True

                raw_text = state.get("raw_text", "")
                if not raw_text:
                    logger.debug(f"No text to translate for {video.video_id}")
                    return True

                logger.info(f"Translating {video.language_iso} transcript for {video.video_id}...")
                
                # Translate the full transcript
                result = self.translator.translate(
                    text=raw_text,
                    source_lang=video.language_iso,
                    target_lang="en"
                )
                
                if result.success:
                    logger.info(
                        f"Translation successful: {video.video_id} "
                        f"({len(raw_text)} → {len(result.translated_text)} chars, {result.latency_ms:.0f}ms)"
                    )
                    
                    # Store translated text
                    self.db.save_temp_state(
                        video_id=video.video_id,
                        raw_text=state.get("raw_text", ""),
                        segments_json=state.get("segments_json", "[]"),
                        translated_text=result.translated_text,
                    )
                    
                    self.db.mark_translation_stored(video.video_id)
                    
                    self.db.log_pipeline_event(
                        level="SUCCESS",
                        message=f"Translated {video.language_iso}→en: {video.title[:50]}...",
                        video_id=video.video_id,
                        channel_id=video.channel_id,
                        scan_id=sid,
                        stage="TRANSLATED",
                    )
                    return True
                else:
                    logger.error(f"Translation failed for {video.video_id}: {result.error}")
                    self.db.log_pipeline_event(
                        level="ERROR",
                        message=f"Translation failed: {video.title[:50]}...",
                        video_id=video.video_id,
                        channel_id=video.channel_id,
                        scan_id=sid,
                        stage="TRANSLATED",
                        error_detail=result.error,
                    )
                    return False
        except Exception as e:
            logger.error(f"Translation stage crashed for {video.video_id}: {e}")
            return False

    def _stage_sponsor_filter(self, video, scan_id: str = None) -> bool:
        """Stage 5: Strip SponsorBlock segments."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "SPONSOR_FILTERED", video.video_id, sid):
                state = self.db.get_temp_state(video.video_id)
                if not state or not state["segments_json"]:
                    return True

                # Deserialize stored segments
                try:
                    segments_data = json.loads(state["segments_json"])
                    segments = [
                        TimestampedSegment(text=s["text"], start=s["start"], duration=s["duration"])
                        for s in segments_data
                    ]
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse segments for {video.video_id}: {e}")
                    return False

                # Fetch SponsorBlock data and filter
                sponsor_segments = fetch_sponsor_segments(video.video_id)
                filtered = strip_sponsored_segments(segments, sponsor_segments)
                filtered_text = " ".join(seg.text for seg in filtered)

                # Store filtered segments back into temp state
                filtered_json = json.dumps([
                    {"text": s.text, "start": s.start, "duration": s.duration}
                    for s in filtered
                ])
                self.db.save_temp_state(
                    video_id=video.video_id,
                    raw_text=filtered_text,
                    segments_json=filtered_json,
                    translated_text=state.get("translated_text", ""),
                )
                return True
        except Exception as e:
            logger.error(f"Sponsor filter stage failed for {video.video_id}: {e}")
            return False

    def _stage_normalize(self, video, scan_id: str = None) -> bool:
        """Stage 6: Normalize transcript text via LLM."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "TEXT_NORMALIZED", video.video_id, sid):
                state = self.db.get_temp_state(video.video_id)
                if not state:
                    return True
                
                # Prefer translated text if available, otherwise use raw
                text_to_normalize = state.get("translated_text") or state.get("raw_text")
                if not text_to_normalize:
                    return True
                    
                cleaned = self.normalizer.normalize(text_to_normalize)
                if not cleaned:
                    logger.warning(f"Normalization returned empty for {video.video_id}")
                    cleaned = text_to_normalize # Safe fallback
                    
                self.db.save_temp_state(
                    video_id=video.video_id,
                    raw_text=state.get("raw_text", ""),
                    segments_json=state.get("segments_json", "[]"),
                    cleaned_text=cleaned,
                    translated_text=state.get("translated_text", ""),
                )
                return True
        except Exception as e:
            logger.error(f"Normalization stage failed for {video.video_id}: {e}")
            return False

    def _stage_chunk(self, video, scan_id: str = None) -> bool:
        """Stage 7: Chunking with semantic or sliding-window strategy."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "CHUNKED", video.video_id, sid):
                state = self.db.get_temp_state(video.video_id)
                if not state:
                    logger.debug(f"No temp state for {video.video_id}, skipping chunking")
                    return True

                text = state["cleaned_text"] or state["translated_text"] or state["raw_text"]
                if not text:
                    logger.debug(f"No text to chunk for {video.video_id}")
                    return True

                # Deserialize stored segments for timestamp estimation
                segments = []
                if state["segments_json"]:
                    try:
                        segments_data = json.loads(state["segments_json"])
                        segments = [
                            TimestampedSegment(
                                text=s["text"], start=s["start"], duration=s["duration"]
                            )
                            for s in segments_data
                        ]
                    except (json.JSONDecodeError, KeyError):
                        pass

                cfg = self.settings.get("chunking", {})
                strategy = cfg.get("strategy", "sliding_window")
                chunks = []

                # Try semantic chunking first if configured
                if strategy == "semantic":
                    try:
                        from src.intelligence.semantic_chunker import semantic_chunk
                        chunks = semantic_chunk(
                            cleaned_text=text,
                            video_id=video.video_id,
                            segments=segments,
                            max_chunk_words=cfg.get("window_size", 400) + 200,
                            min_chunk_words=cfg.get("min_chunk_size", 50),
                            similarity_threshold=cfg.get("semantic_similarity_threshold", 0.4),
                        )
                    except Exception as e:
                        logger.warning(f"Semantic chunking failed, falling back: {e}")
                        chunks = []

                # Fallback to sliding-window
                if not chunks:
                    chunks = sliding_window_chunk(
                        cleaned_text=text,
                        video_id=video.video_id,
                        segments=segments,
                        window_size=cfg.get("window_size", 400),
                        overlap=cfg.get("overlap", 80),
                        min_chunk_size=cfg.get("min_chunk_size", 50),
                    )

                if chunks:
                    self.db.insert_chunks(chunks)
                    self.db.delete_temp_state(video.video_id)
                    return True
                else:
                    logger.warning(f"No chunks generated for {video.video_id}")
                    return False
        except Exception as e:
            logger.error(f"Chunking stage failed for {video.video_id}: {e}")
            return False

    def _stage_chunk_analysis(self, video, scan_id: str = None) -> bool:
        """Stage 6.5: Deep analysis of each chunk (topics, entities, claims, quotes)."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "CHUNK_ANALYZED", video.video_id, sid):
                from src.intelligence.chunk_analyzer import ChunkAnalyzer

                analyzer = ChunkAnalyzer(self.db)
                totals = analyzer.analyze_video_chunks(video.video_id)
                
                # P1-B: Heatmap × Transcript Correlation
                try:
                    heatmap_data = video.heatmap_json
                    if not heatmap_data or heatmap_data == "[]":
                        # Re-fetch video to be sure we have the latest metadata
                        v_latest = self.db.get_video(video.video_id)
                        heatmap_data = v_latest.heatmap_json if v_latest else "[]"
                    
                    heatmap = json.loads(heatmap_data or "[]")
                    if heatmap:
                        values = [h.get("value", 0) for h in heatmap]
                        if values:
                            threshold = sorted(values)[-max(1, int(len(values) * 0.2))]
                            high_attention_intervals = [
                                (h["start_time"], h["end_time"]) 
                                for h in heatmap if h.get("value", 0) >= threshold
                            ]
                            
                            chunks = self.db.get_chunks_for_video(video.video_id)
                            for chunk in chunks:
                                is_high = False
                                for start, end in high_attention_intervals:
                                    overlap_start = max(chunk.start_timestamp, start)
                                    overlap_end = min(chunk.end_timestamp, end)
                                    overlap_dur = max(0, overlap_end - overlap_start)
                                    chunk_dur = max(1, chunk.end_timestamp - chunk.start_timestamp)
                                    
                                    if (overlap_dur / chunk_dur) >= 0.3:
                                        is_high = True
                                        break
                                
                                if is_high:
                                    self.db.execute(
                                        "UPDATE transcript_chunks SET is_high_attention = 1 WHERE chunk_id = ?",
                                        (chunk.chunk_id,)
                                    )
                            self.db.commit()
                            logger.info(f"P1-B: Flagged high-attention segments for video {video.video_id}")
                except Exception as e:
                    logger.warning(f"Heatmap correlation failed for {video.video_id}: {e}")

                self._report_status(
                    f"Chunk analysis: {totals['topics']}T {totals['entities']}E "
                    f"{totals['claims']}C {totals['quotes']}Q"
                )
                return True
        except Exception as e:
            logger.error(f"Chunk analysis failed for {video.video_id}: {e}")
            return False


    def batch_graph_sync(self, video_ids: list[str]) -> int:
        """Synchronize a batch of videos to Neo4j for performance.
        
        Uses UNWIND queries to minimize transaction overhead.
        """
        videos_to_sync = []
        links_to_sync = []
        
        for vid in video_ids:
            video = self.db.get_video(vid)
            if not video: continue
            
            videos_to_sync.append({
                "video_id": video.video_id,
                "title": video.title,
                "channel_id": video.channel_id,
                "upload_date": video.upload_date,
                "duration": video.duration_seconds
            })
            
            topics = self.db.get_video_aggregated_topics(vid)
            for t in topics:
                links_to_sync.append({
                    "video_id": vid,
                    "topic_name": t["name"],
                    "relevance": t.get("relevance", 1.0)
                })
        
        if videos_to_sync:
            self.graph_store.batch_upsert_videos(videos_to_sync)
        if links_to_sync:
            self.graph_store.batch_link_topics(links_to_sync)
            
        for vid in video_ids:
            self.db.mark_outbox_neo4j_done(vid)
            self.checkpoint.advance(vid, "GRAPH_SYNCED")
            
        return len(video_ids)

    def _stage_graph_sync(self, video, scan_id: str = None) -> bool:
        """Stage 8: Synchronize video, topics, and guests to Neo4j (with P0-A outbox)."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "GRAPH_SYNCED", video.video_id, sid):
                graph = self.graph_store

                # Upsert video node
                graph.upsert_video(
                    video_id=video.video_id,
                    title=video.title,
                    channel_id=video.channel_id,
                    upload_date=video.upload_date,
                    duration=video.duration_seconds,
                )

                # Use aggregated chunk-level data (covers full video)
                topics = self.db.get_video_aggregated_topics(video.video_id)
                entity_names = self.db.get_video_aggregated_entities(video.video_id)

                # Resolve entities and create Guest nodes
                from src.intelligence.entity_resolver import EntityResolver
                resolver = EntityResolver(self.db)
                guests = []
                for name in entity_names:
                    guest = resolver.resolve(name)
                    guests.append(guest)
                    graph.upsert_guest(guest.canonical_name)
                    graph.link_guest_to_video(guest.canonical_name, video.video_id)
                # Create Topic nodes and relationships
                for topic in topics:
                    graph.link_video_to_topic(
                        video.video_id, topic["name"], topic.get("relevance", 1.0)
                    )
                    for guest in guests:
                        graph.link_guest_to_topic(guest.canonical_name, topic["name"])

                # Create RELATED_TO between co-occurring topics
                topic_names = [t["name"] for t in topics]
                for i, t1 in enumerate(topic_names):
                    for t2 in topic_names[i + 1:]:
                        graph.link_related_topics(t1, t2)

                # Sync claims to graph
                claims = self.db.get_claims_for_video(video.video_id)
                for claim in claims:
                    graph.upsert_claim(
                        claim_id=claim.claim_id,
                        video_id=video.video_id,
                        speaker=claim.speaker,
                        text=claim.claim_text,
                        topic=claim.topic,
                    )
                
                self.db.mark_outbox_neo4j_done(video.video_id)
                return True
        except Exception as e:
            logger.error(f"Graph sync failed for {video.video_id}: {e}")
            self.db.log_pipeline_event(
                level="ERROR",
                message=f"Graph sync failed: {str(e)}",
                video_id=video.video_id,
                scan_id=sid,
                stage="GRAPH_SYNCED",
                error_detail=str(e)
            )
            return False

    def _stage_summarize(self, video, scan_id: str = None) -> bool:
        """Stage 6.8: Generate hierarchical Map-Reduce summary."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "SUMMARIZED", video.video_id, sid):
                from src.intelligence.summarizer import SummarizerEngine
                summarizer = SummarizerEngine(self.db)
                summary = summarizer.generate_summary(video.video_id)
                if summary:
                    self._report_status("Map-Reduce summary generated")
                    return True
                else:
                    logger.error(f"Summary generation returned empty for {video.video_id}")
                    return False
        except Exception as e:
            logger.error(f"Summarization stage failed for {video.video_id}: {e}")
            return False

    def _stage_embed(self, video, scan_id: str = None) -> bool:
        """Stage 7: Embed chunks into ChromaDB (with P0-A outbox + P0-B hash skip)."""
        import hashlib
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "EMBEDDED", video.video_id, sid):
                chunks = self.db.get_chunks_for_video(video.video_id)
                if not chunks:
                    logger.debug(f"No chunks to embed for {video.video_id}")
                    return True

                # P0-A: Register outbox entry before touching external stores
                try:
                    self.db.create_sync_outbox_entry(video.video_id)
                except Exception as e:
                    logger.warning(f"Could not create outbox entry for {video.video_id}: {e}")

                # P0-B: Compute content hashes for each chunk, store in DB
                existing_hashes = self.db.get_chunks_with_hashes(video.video_id)
                skip_ids: set = set()

                for chunk in chunks:
                    new_hash = hashlib.sha256(
                        (chunk.cleaned_text or chunk.raw_text).encode("utf-8", errors="replace")
                    ).hexdigest()
                    # Update hash in DB regardless (cheap write)
                    self.db.conn.execute(
                        "UPDATE transcript_chunks SET content_hash = ? WHERE chunk_id = ?",
                        (new_hash, chunk.chunk_id),
                    )
                    # If hash matches what was stored last run → already embedded
                    if existing_hashes.get(chunk.chunk_id) == new_hash:
                        skip_ids.add(chunk.chunk_id)

                self.db.conn.commit()

                if skip_ids:
                    logger.info(
                        f"P0-B: {len(skip_ids)}/{len(chunks)} chunks unchanged, skipping re-embedding"
                    )

                channel = self.db.get_channel(video.channel_id)
                self.vector_store.upsert_chunks(
                    chunks,
                    channel_id=video.channel_id,
                    upload_date=video.upload_date,
                    language_iso=video.language_iso,
                    skip_ids=skip_ids,
                )

                # P0-A: Mark ChromaDB sync done in outbox
                try:
                    self.db.mark_outbox_chroma_done(video.video_id)
                except Exception as e:
                    logger.warning(f"Could not mark chroma done in outbox for {video.video_id}: {e}")
                
                return True
        except Exception as e:
            logger.error(f"Embedding stage failed for {video.video_id}: {e}")
            return False

    def _extract_topics(self, text: str) -> list[dict]:
        """Extract topics from transcript text via LLM.

        Returns list of {"name": str, "relevance": float} dicts.
        """
        try:
            import ollama
            from src.config import load_prompt

            prompt = load_prompt("topic_extractor")
            response = ollama.chat(
                model=self.ollama_cfg.get("triage_model", "llama3.2:3b"),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                options={"num_predict": 300, "temperature": 0.1},
            )

            raw = response["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                raw = raw.rsplit("```", 1)[0].strip()

            topics = json.loads(raw)
            if isinstance(topics, list):
                return [
                    {"name": t.get("name", "").lower().strip(),
                     "relevance": float(t.get("relevance", 0.5))}
                    for t in topics
                    if t.get("name", "").strip()
                ]
        except Exception as e:
            logger.warning(f"Topic extraction failed: {e}")

        return []

    def _stage_corroborate(self, video, scan_id: str = None) -> bool:
        """Stage: Corroborate claims against the vault."""
        sid = scan_id or getattr(self, "current_scan_id", None) or "manual_scan"
        try:
            with StageTimer(self.metrics, "CORROBORATED", video.video_id, sid):
                self.corroborator.corroborate_all()
                return True
        except Exception as e:
            logger.warning(f"Claim corroboration failed (non-critical): {e}")
            return True # Non-critical: allow pipeline to finish
