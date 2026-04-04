"""
Pipeline orchestrator for knowledgeVault-YT.

Coordinates the full ingestion pipeline from URL input through to
indexed knowledge graph. Handles both fresh scans and resumed scans.
"""

import json
import logging
import time
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
        ensure_data_dirs()
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self.db = SQLiteStore(self.settings["sqlite"]["path"])
        self.checkpoint = CheckpointManager(self.db)
        self.triage = TriageEngine()
        self.normalizer = TextNormalizer()
        self.translator = TranslationEngine()

        # Performance metrics collector
        self.metrics = PerformanceMetricsCollector(self.settings["sqlite"]["path"])
        self.current_scan_id = None

        # Vector store (lazy init — may fail if Ollama isn't running)
        self._vector_store: Optional[VectorStore] = None

        # Graph store (lazy init — may fail if Neo4j isn't running)
        self._graph_store = None

        # Callbacks for UI progress updates
        self._on_progress = None
        self._on_status = None

    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = VectorStore()
        return self._vector_store

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

            thread = Thread(target=discovery_worker, daemon=True)
            thread.start()

            processed_count = 0
            while True:
                # Check for pause/stop requests
                if self._check_stop_requested(scan_id):
                    self._report_status("Pipeline stop requested - aborting")
                    self.checkpoint.fail_scan(scan_id)
                    return scan_id
                
                # Wait while paused
                while self._check_pause_state(scan_id):
                    import time
                    time.sleep(1)
                
                item = discovery_queue.get()
                if item is None:
                    break
                
                vid, is_new = item
                if is_new:
                    self._report_status(f"Processing new video: {vid}")
                    self._process_single_video(vid, scan_id)
                
                processed_count += 1
                self.checkpoint.update_scan_progress(
                    scan_id, total_processed=processed_count,
                    last_video_id=vid,
                )

            self.checkpoint.complete_scan(scan_id)
            self.db.set_control_state(scan_id, "RUNNING")
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

        self._report_status(f"Resuming scan {scan_id}: {len(pending)} videos remaining")

        for i, video in enumerate(pending):
            self._report_status(
                f"Resuming {i + 1}/{len(pending)}: {video.title[:50]}... "
                f"(from stage: {video.checkpoint_stage})"
            )
            self._resume_video(video)

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
            self._report_status(
                f"Processing manually-accepted {i + 1}/{len(manually_overridden)}: "
                f"{video.title[:50]}..."
            )
            self._resume_video(video)
        
        self._report_status(
            f"Completed processing {len(manually_overridden)} manually-overridden videos"
        )
        return len(manually_overridden)

    # -------------------------------------------------------------------
    # Stage Implementations
    # -------------------------------------------------------------------

    def _stage_discover_stream(
        self, url: str, parsed: ParsedURL, scan_id: str, discovery_queue,
        force_metadata_refresh: bool = False
    ) -> None:
        """Stage 1: Discover video IDs and harvest metadata (Streaming)."""
        self._report_status("Stage 1: Discovering videos...")

        # For channel/playlist, extract channel info first
        if parsed.url_type in ("channel", "playlist"):
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
        for vid in discover_video_ids(url, parsed):
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
                        # Record initial stats snapshot
                        self.db.record_stats_snapshot(
                            video.video_id, video.view_count, video.like_count, video.comment_count
                        )
                        discovery_queue.put((vid, is_new))
                except Exception as e:
                    logger.error(f"Metadata extraction failed for {vid}: {e}")
            else:
                discovery_queue.put((vid, False))

            if discovered_count % 10 == 0:
                self.checkpoint.update_scan_progress(
                    scan_id, total_discovered=discovered_count
                )
                self._report_status(f"Discovered {discovered_count} videos...")

        self.checkpoint.update_scan_progress(
            scan_id, total_discovered=discovered_count
        )
        self._report_status(f"Discovery complete: {discovered_count} videos found")

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
            llm_tasks = [
                LLMTask(
                    task_id=v.video_id,
                    fn=self.triage._llm_classify,
                    args=(v,),
                )
                for v in needs_llm
            ]
            llm_results = pool.submit_batch(llm_tasks)

            for lr in llm_results:
                if lr.success and lr.result:
                    self.db.update_triage_status(
                        lr.task_id,
                        status=lr.result.decision.value,
                        reason=lr.result.reason,
                        confidence=lr.result.confidence,
                    )
                    results[lr.task_id] = lr.result.decision.value
                else:
                    self.db.update_triage_status(
                        lr.task_id, status="PENDING_REVIEW",
                        reason=f"batch_llm_error: {lr.error or 'unknown'}",
                    )
                    results[lr.task_id] = "PENDING_REVIEW"

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
        video = self.db.get_video(video_id)
        if video is None:
            logger.warning(f"Video {video_id} not found in DB")
            return

        self.current_scan_id = scan_id
        self._resume_video(video, scan_id)

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

                elif next_stage == "TRANSLATED":
                    self._stage_translate(video, scan_id)

                elif next_stage == "SPONSOR_FILTERED":
                    self._stage_sponsor_filter(video, scan_id)

                elif next_stage == "TEXT_NORMALIZED":
                    self._stage_normalize(video, scan_id)

                elif next_stage == "CHUNKED":
                    self._stage_chunk(video, scan_id)

                elif next_stage == "CHUNK_ANALYZED":
                    self._stage_chunk_analysis(video, scan_id)

                elif next_stage == "EMBEDDED":
                    self._stage_embed(video, scan_id)

                elif next_stage == "GRAPH_SYNCED":
                    self._stage_graph_sync(video, scan_id)

                elif next_stage == "DONE":
                    self.checkpoint.advance(video.video_id, "DONE")
                    return  # Don't fall through to the advance below

                self.checkpoint.advance(video.video_id, next_stage)

            except Exception as e:
                logger.error(
                    f"Stage {next_stage} failed for {video.video_id}: {e}"
                )
                break  # Stop processing, checkpoint is at last successful stage

    def _stage_triage(self, video, scan_id: str) -> None:
        """Stage 2: Run triage classification."""
        with StageTimer(self.metrics, "TRIAGE", video.video_id, scan_id):
            result = self.triage.classify(video)
            self.db.update_triage_status(
                video.video_id,
                status=result.decision.value,
                reason=result.reason,
                confidence=result.confidence,
            )
            log_level = "SUCCESS" if result.decision.value == "ACCEPTED" else "INFO"
            self.db.log_pipeline_event(
                level=log_level,
                message=f"Triage: {video.title[:50]}... → {result.decision.value} ({result.confidence:.0%})",
                video_id=video.video_id,
                channel_id=video.channel_id,
                stage="TRIAGE",
            )
            logger.info(
                f"Triage: {video.title[:50]}... → {result.decision.value} "
                f"({result.phase}, {result.latency_ms:.0f}ms)"
            )

    def _stage_transcript(self, video, scan_id: str) -> bool:
        """Stage 3: Fetch transcript. Returns True if transcript was found."""
        with StageTimer(self.metrics, "TRANSCRIPT_FETCHED", video.video_id, scan_id):
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

    def _stage_translate(self, video, scan_id: str) -> None:
        """Stage 4 (NEW): Translate non-English transcripts to English.
        
        Only runs if:
        1. Video language is not English
        2. Translation is enabled in config
        3. A transcript exists
        """
        with StageTimer(self.metrics, "TRANSLATED", video.video_id, scan_id):
            state = self.db.get_temp_state(video.video_id)
            if not state:
                logger.debug(f"No temp state for {video.video_id}, skipping translation")
                return

            # Check if translation is needed
            if video.language_iso == "en":
                logger.debug(f"Video {video.video_id} is English, skipping translation")
                return

            raw_text = state.get("raw_text", "")
            if not raw_text:
                logger.debug(f"No text to translate for {video.video_id}")
                return

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
                
                # Mark that translation was performed
                self.db.conn.execute(
                    "UPDATE videos SET translated_text_stored = 1 WHERE video_id = ?",
                    (video.video_id,)
                )
                self.db.conn.commit()
                
                self.db.log_pipeline_event(
                    level="SUCCESS",
                    message=f"Translated {video.language_iso}→en: {video.title[:50]}...",
                    video_id=video.video_id,
                    channel_id=video.channel_id,
                    stage="TRANSLATED",
                )
            else:
                logger.warning(
                    f"Translation failed for {video.video_id}: {result.error}. "
                    f"Proceeding with original text."
                )
                # Store original text as translated (graceful fallback)
                self.db.save_temp_state(
                    video_id=video.video_id,
                    raw_text=state.get("raw_text", ""),
                    segments_json=state.get("segments_json", "[]"),
                    translated_text=raw_text,  # Fallback to original
                )
                
                self.db.log_pipeline_event(
                    level="WARNING",
                    message=f"Translation failed, using original: {video.title[:50]}...",
                    video_id=video.video_id,
                    channel_id=video.channel_id,
                    stage="TRANSLATED",
                    error_detail=result.error,
                )

    def _stage_sponsor_filter(self, video, scan_id: str) -> None:
        """Stage 5: Strip SponsorBlock segments (reads stored data, no re-fetch)."""
        with StageTimer(self.metrics, "SPONSOR_FILTERED", video.video_id, scan_id):
            state = self.db.get_temp_state(video.video_id)
        if not state or not state["segments_json"]:
            return

        # Deserialize stored segments
        try:
            segments_data = json.loads(state["segments_json"])
            segments = [
                TimestampedSegment(text=s["text"], start=s["start"], duration=s["duration"])
                for s in segments_data
            ]
        except (json.JSONDecodeError, KeyError):
            return

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

    def _stage_normalize(self, video, scan_id: str) -> None:
        """Stage 6: Normalize transcript text via LLM.
        
        Uses translated text if available, otherwise uses raw text.
        """
        with StageTimer(self.metrics, "TEXT_NORMALIZED", video.video_id, scan_id):
            state = self.db.get_temp_state(video.video_id)
            if not state:
                return
            
            # Prefer translated text if available, otherwise use raw
            text_to_normalize = state.get("translated_text") or state.get("raw_text")
            if not text_to_normalize:
                return
                
            cleaned = self.normalizer.normalize(text_to_normalize)
        self.db.save_temp_state(
            video_id=video.video_id,
            raw_text=state.get("raw_text", ""),
            segments_json=state.get("segments_json", "[]"),
            cleaned_text=cleaned,
            translated_text=state.get("translated_text", ""),
        )

    def _stage_chunk(self, video, scan_id: str) -> None:
        """Stage 7: Chunking with semantic or sliding-window strategy."""
        with StageTimer(self.metrics, "CHUNKED", video.video_id, scan_id):
            state = self.db.get_temp_state(video.video_id)
            if not state:
                return

            text = state["cleaned_text"] or state["raw_text"]
            if not text:
                return

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

            self.db.insert_chunks(chunks)
            self.db.delete_temp_state(video.video_id)

    def _stage_chunk_analysis(self, video, scan_id: str) -> None:
        """Stage 6.5: Deep analysis of each chunk (topics, entities, claims, quotes)."""
        with StageTimer(self.metrics, "CHUNK_ANALYZED", video.video_id, scan_id):
            from src.intelligence.chunk_analyzer import ChunkAnalyzer

            analyzer = ChunkAnalyzer(self.db)
            totals = analyzer.analyze_video_chunks(video.video_id)
            self._report_status(
                f"Chunk analysis: {totals['topics']}T {totals['entities']}E "
                f"{totals['claims']}C {totals['quotes']}Q"
            )

    def _stage_embed(self, video, scan_id: str) -> None:
        """Stage 7: Embed chunks into ChromaDB."""
        with StageTimer(self.metrics, "EMBEDDED", video.video_id, scan_id):
            chunks = self.db.get_chunks_for_video(video.video_id)
            if chunks:
                channel = self.db.get_channel(video.channel_id)
                self.vector_store.upsert_chunks(
                    chunks,
                    channel_id=video.channel_id,
                    upload_date=video.upload_date,
                    language_iso=video.language_iso,
                )

    def _stage_graph_sync(self, video, scan_id: str) -> None:
        """Stage 8: Sync to Neo4j knowledge graph (optional).

        Uses pre-computed chunk-level analysis (from CHUNK_ANALYZED stage)
        instead of re-extracting from raw text. This means the graph
        reflects analysis of the ENTIRE video, not just the first N chars.
        """
        with StageTimer(self.metrics, "GRAPH_SYNCED", video.video_id, scan_id):
            try:
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
                        claim_text=claim.claim_text,
                        speaker=claim.speaker,
                        video_id=video.video_id,
                        topic=claim.topic,
                    )

            except Exception as e:
                logger.warning(f"Graph sync skipped for {video.video_id}: {e}")

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
