"""
RAG (Retrieval-Augmented Generation) engine for knowledgeVault-YT.

Orchestrates the semantic search → context assembly → LLM synthesis
pipeline to answer natural language research queries with citations.

V3 Upgrades:
    - Structured query syntax (channel:, topic:, guest:, after:, before:)
    - Multi-turn conversation context
    - Hybrid search (vector + BM25 reciprocal rank fusion)
    - Answer confidence scoring
    - Topic-aware Neo4j graph enrichment
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import ollama as ollama_api

from src.config import get_settings, load_prompt
from src.intelligence.query_parser import QueryPlan, parse_query
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A source citation linking an answer to a transcript chunk."""
    source_id: str          # e.g., "source_1"
    chunk_id: str
    video_id: str
    video_title: str
    channel_name: str
    start_timestamp: float
    end_timestamp: float
    text_excerpt: str       # Relevant chunk text
    topic: str = ""         # Optional topic context for thematic clustering

    @property
    def timestamp_str(self) -> str:
        """Format timestamp as MM:SS."""
        mins = int(self.start_timestamp // 60)
        secs = int(self.start_timestamp % 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def youtube_link(self) -> str:
        """Generate a YouTube link with timestamp."""
        t = int(self.start_timestamp)
        return f"https://www.youtube.com/watch?v={self.video_id}&t={t}s"


@dataclass
class ConfidenceScore:
    """Quality metrics for a RAG response."""
    source_diversity: float = 0.0   # 0-1: how many unique channels contributed
    chunk_relevance: float = 0.0    # 0-1: avg vector similarity of used chunks
    coverage: float = 0.0           # 0-1: what fraction of query terms were found
    overall: float = 0.0            # weighted composite score

    def compute(self, citations: list[Citation], query_terms: list[str],
                distances: list[float]) -> None:
        """Calculate confidence sub-scores and overall composite."""
        # Source diversity: unique channels / total citations
        if citations:
            unique_channels = len(set(c.channel_name for c in citations))
            self.source_diversity = min(unique_channels / max(len(citations), 1), 1.0)
        else:
            self.source_diversity = 0.0

        # Chunk relevance: convert cosine distance to similarity (1 - dist)
        if distances:
            avg_similarity = 1.0 - (sum(distances) / len(distances))
            self.chunk_relevance = max(0.0, min(avg_similarity, 1.0))
        else:
            self.chunk_relevance = 0.0

        # Coverage: what fraction of query terms appear in citation excerpts
        if query_terms and citations:
            all_text = " ".join(c.text_excerpt.lower() for c in citations)
            matched = sum(1 for t in query_terms if t.lower() in all_text)
            self.coverage = matched / len(query_terms)
        else:
            self.coverage = 0.0

        # Weighted composite
        self.overall = (
            self.chunk_relevance * 0.5 +
            self.coverage * 0.3 +
            self.source_diversity * 0.2
        )


@dataclass
class RAGResponse:
    """Complete response from a RAG query with optional raw data for verification."""
    query: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: Optional[ConfidenceScore] = None
    total_chunks_retrieved: int = 0
    total_chunks_used: int = 0
    latency_ms: float = 0.0
    query_plan: Optional[QueryPlan] = None
    
    # Week 1 Enhancement: Raw data for verification workflow
    raw_chunks: list[dict] = field(default_factory=list)  # Full chunk text + metadata
    full_transcripts: list[dict] = field(default_factory=list)  # Full video transcripts
    verification_notes: str = ""  # How to verify answer


class RAGEngine:
    """Retrieval-Augmented Generation engine for research queries.

    Flow:
        1. Parse structured query filters (channel:, topic:, after:, etc.)
        2. Embed the query and search ChromaDB for top-K relevant chunks
        3. Run BM25 full-text search and fuse results (reciprocal rank fusion)
        4. Optionally enrich with topic-aware graph retrieval
        5. Enrich results with video metadata from SQLite
        6. Deduplicate overlapping chunks
        7. Build a context prompt with source citations + conversation history
        8. Send to Ollama LLM for synthesis
        9. Calculate confidence score and return
    """

    def __init__(self, db: SQLiteStore, vector_store: VectorStore):
        self.db = db
        self.vector_store = vector_store
        self.settings = get_settings()
        self.rag_cfg = self.settings["rag"]
        self.ollama_cfg = self.settings["ollama"]
        self.system_prompt = load_prompt("rag_synthesizer")

    def query(
        self,
        question: str,
        filters: Optional[dict] = None,
        conversation_history: Optional[str] = None,
    ) -> RAGResponse:
        """Execute a RAG query and return a synthesized answer with citations.

        Args:
            question: Natural language research question (may include filters).
            filters: Optional explicit ChromaDB metadata filters.
            conversation_history: Previous Q&A pairs for follow-up context.

        Returns:
            RAGResponse with answer, citations, confidence, and metrics.
        """
        start_time = time.perf_counter()
        top_k = self.rag_cfg.get("vector_top_k", 15)
        rerank_k = self.rag_cfg.get("rerank_top_k", 8)

        # Step 1: Parse structured query
        plan = parse_query(question)
        search_text = plan.free_text or question

        # Merge explicit filters with parsed filters
        where_filter = filters or plan.to_chromadb_where()

        # Step 2: Vector retrieval
        vector_results = self.vector_store.search(
            query=search_text,
            top_k=top_k,
            where=where_filter,
        )

        # Step 3: BM25 full-text search + fusion
        fts_results = self.db.fulltext_search(search_text, limit=top_k)
        fused_results = self._reciprocal_rank_fusion(
            vector_results, fts_results, k=60
        )

        total_retrieved = len(fused_results)

        if not fused_results:
            latency = (time.perf_counter() - start_time) * 1000
            return RAGResponse(
                query=question,
                answer="Insufficient context in the current vault. "
                       "No relevant transcript chunks were found. "
                       "Try ingesting more channels or broadening your query.",
                latency_ms=latency,
                query_plan=plan,
            )

        # Step 4: Topic-aware enrichment from Neo4j
        if plan.topic_filter:
            graph_results = self._topic_graph_enrichment(
                plan.topic_filter, fused_results
            )
            fused_results = graph_results or fused_results

        # Step 5: Deduplicate overlapping chunks
        if self.rag_cfg.get("chunk_overlap_dedup", True):
            fused_results = self._deduplicate_chunks(fused_results)

        # Step 6: Take top-K after dedup
        fused_results = fused_results[:rerank_k]

        # Step 7: Enrich with video metadata
        distances = [r.get("distance", 0.0) for r in fused_results]
        citations = self._build_citations(fused_results)

        # Step 8: Build LLM context (with conversation history if present)
        context_prompt = self._build_context(
            search_text, citations, conversation_history
        )

        # Step 9: LLM synthesis
        answer = self._synthesize(context_prompt)

        # Step 10: Confidence scoring
        query_terms = [w for w in search_text.split() if len(w) > 2]
        confidence = ConfidenceScore()
        confidence.compute(citations, query_terms, distances)

        latency = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"RAG query completed in {latency:.0f}ms: "
            f"{total_retrieved} retrieved → {len(citations)} used "
            f"(confidence: {confidence.overall:.2f})"
        )

        # Step 11: Enrich with raw transcript data for verification (Week 1 enhancement)
        raw_chunks = self._enrich_citations_with_raw(citations)
        full_transcripts = self._get_full_transcripts_for_citations(citations)

        return RAGResponse(
            query=question,
            answer=answer,
            citations=citations,
            confidence=confidence,
            total_chunks_retrieved=total_retrieved,
            total_chunks_used=len(citations),
            latency_ms=latency,
            query_plan=plan,
            raw_chunks=raw_chunks,
            full_transcripts=full_transcripts,
            verification_notes=f"Answer based on {len(citations)} citations from {len(set(c.channel_name for c in citations))} channels. "
                              f"View raw chunks and full transcripts to verify.",
        )

    # -------------------------------------------------------------------
    # Hybrid Search: Reciprocal Rank Fusion
    # -------------------------------------------------------------------

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        fts_results: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """Fuse vector and BM25 results using Reciprocal Rank Fusion.

        RRF score = Σ 1/(k + rank) for each result list.
        Higher RRF score = more relevant.

        Args:
            vector_results: Results from ChromaDB vector search.
            fts_results: Results from SQLite FTS5 BM25 search.
            k: Smoothing constant (default 60).

        Returns:
            Fused results sorted by RRF score, in vector_results format.
        """
        rrf_scores = {}  # chunk_id → (rrf_score, result_dict)

        # Score vector results by rank position
        for rank, r in enumerate(vector_results):
            cid = r["chunk_id"]
            score = 1.0 / (k + rank + 1)
            rrf_scores[cid] = (score, r)

        # Add FTS results (convert to vector result format)
        for rank, fts in enumerate(fts_results):
            cid = fts["chunk_id"]
            score = 1.0 / (k + rank + 1)

            if cid in rrf_scores:
                # Exists in both → boost score
                existing_score, existing_result = rrf_scores[cid]
                rrf_scores[cid] = (existing_score + score, existing_result)
            else:
                # FTS-only result: create a result dict compatible with vector format
                chunk = self.db.get_chunk(fts["chunk_id"]) if hasattr(self.db, 'get_chunk') else None
                if chunk:
                    rrf_scores[cid] = (score, {
                        "chunk_id": cid,
                        "text": chunk.cleaned_text or chunk.raw_text,
                        "metadata": {
                            "video_id": fts.get("video_id", ""),
                            "chunk_index": getattr(chunk, "chunk_index", 0),
                            "start_timestamp": getattr(chunk, "start_timestamp", 0.0),
                            "end_timestamp": getattr(chunk, "end_timestamp", 0.0),
                            "topic": "",
                        },
                        "distance": 0.5,  # Neutral distance for FTS-only results
                    })

        # Sort by RRF score descending (best first)
        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1][0], reverse=True)
        return [item[1][1] for item in sorted_items]

    # -------------------------------------------------------------------
    # Topic-Aware Neo4j Enrichment
    # -------------------------------------------------------------------

    def _topic_graph_enrichment(
        self, topic: str, existing_results: list[dict]
    ) -> Optional[list[dict]]:
        """Enrich results with videos related to a topic via Neo4j graph.

        If a topic: filter is specified, query the graph for videos that
        DISCUSS that topic and boost those results.
        """
        try:
            from src.storage.graph_store import GraphStore
            graph = GraphStore()

            # Find videos discussing this topic
            with graph.driver.session() as session:
                result = session.run(
                    """MATCH (v:Video)-[r:DISCUSSES]->(t:Topic)
                       WHERE t.name CONTAINS $topic
                       RETURN v.video_id AS video_id, r.relevance AS relevance
                       ORDER BY r.relevance DESC
                       LIMIT 20""",
                    topic=topic.lower().strip(),
                )
                topic_videos = {r["video_id"]: r["relevance"] for r in result}

            graph.close()

            if not topic_videos:
                return None

            # Boost existing results that match topic videos
            for r in existing_results:
                vid = r["metadata"].get("video_id", "")
                if vid in topic_videos:
                    # Reduce distance (improve ranking) by topic relevance
                    boost = topic_videos[vid] * 0.2
                    r["distance"] = max(0.0, r.get("distance", 0.5) - boost)

            # Re-sort by distance
            existing_results.sort(key=lambda x: x.get("distance", 1.0))
            logger.info(
                f"Topic enrichment: boosted {len(topic_videos)} videos for topic '{topic}'"
            )
            return existing_results

        except Exception as e:
            logger.debug(f"Topic graph enrichment skipped: {e}")
            return None

    # -------------------------------------------------------------------
    # Deduplication
    # -------------------------------------------------------------------

    def _deduplicate_chunks(self, results: list[dict]) -> list[dict]:
        """Remove overlapping chunks from the same video.

        For each (video_id, chunk_index) position, keeps only the result
        with the lowest distance. Also deduplicates adjacent chunks from
        the same video, keeping the most relevant one.

        Uses dict-based O(1) lookups instead of list.remove().
        """
        best = {}  # (video_id, chunk_index) → result

        for r in results:
            meta = r["metadata"]
            video_id = meta.get("video_id", "")
            chunk_idx = meta.get("chunk_index", 0)
            key = (video_id, chunk_idx)

            # Check current and adjacent positions
            for check_key in [key, (video_id, chunk_idx - 1), (video_id, chunk_idx + 1)]:
                if check_key in best and check_key != key:
                    # Adjacent chunk exists — keep the better one
                    if r["distance"] < best[check_key]["distance"]:
                        del best[check_key]
                        best[key] = r
                    break
            else:
                # No adjacent conflict — keep if best for this position
                if key not in best or r["distance"] < best[key]["distance"]:
                    best[key] = r

        # Return sorted by distance (most relevant first)
        return sorted(best.values(), key=lambda x: x["distance"])

    # -------------------------------------------------------------------
    # Citation Building
    # -------------------------------------------------------------------

    def _build_citations(self, results: list[dict]) -> list[Citation]:
        """Enrich search results with video metadata to create citations."""
        citations = []
        for i, result in enumerate(results):
            meta = result["metadata"]
            video_id = meta.get("video_id", "")

            # Fetch video metadata from SQLite
            video = self.db.get_video(video_id)
            video_title = video.title if video else "Unknown"
            channel_id = video.channel_id if video else ""

            channel = self.db.get_channel(channel_id) if channel_id else None
            channel_name = channel.name if channel else "Unknown"

            citations.append(Citation(
                source_id=f"source_{i + 1}",
                chunk_id=result["chunk_id"],
                video_id=video_id,
                video_title=video_title,
                channel_name=channel_name,
                start_timestamp=meta.get("start_timestamp", 0.0),
                end_timestamp=meta.get("end_timestamp", 0.0),
                text_excerpt=result["text"][:300],
                topic=meta.get("topic", "")
            ))

        return citations

    # -------------------------------------------------------------------
    # Context Building (with multi-turn support)
    # -------------------------------------------------------------------

    def _build_context(
        self,
        question: str,
        citations: list[Citation],
        conversation_history: Optional[str] = None,
    ) -> str:
        """Build the full prompt with context chunks, history, and question."""
        parts = []

        # Include conversation history for follow-up context
        if conversation_history:
            parts.append(
                f"PREVIOUS CONVERSATION:\n{conversation_history}\n\n---\n"
            )

        # Context chunks
        context_parts = []
        for c in citations:
            context_parts.append(
                f"[{c.source_id}] Video: \"{c.video_title}\" "
                f"(Channel: {c.channel_name}, Timestamp: {c.timestamp_str})\n"
                f"{c.text_excerpt}\n"
            )

        context_block = "\n---\n".join(context_parts)
        parts.append(f"CONTEXT CHUNKS:\n{context_block}")

        parts.append(f"\nRESEARCH QUESTION:\n{question}")

        return "\n\n".join(parts)

    # -------------------------------------------------------------------
    # LLM Synthesis
    # -------------------------------------------------------------------

    def _synthesize(self, context_prompt: str) -> str:
        """Send context + question to Ollama LLM for synthesis (HIGH priority)."""
        from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
        
        def call_ollama(prompt):
            return ollama_api.chat(
                model=self.ollama_cfg.get("deep_model", self.ollama_cfg.get("rag_model", "llama3.2:3b")),
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                options={
                    "num_predict": self.ollama_cfg.get("rag_max_tokens", 4096),
                    "temperature": self.ollama_cfg.get("temperature", 0.1),
                },
            )

        pool = LLMPool()
        task = LLMTask(
            task_id=f"rag_synth_{int(time.time())}",
            fn=call_ollama,
            args=(context_prompt,),
            priority=LLMPriority.HIGH
        )
        
        try:
            future = pool.submit(task)
            # RAG synthesis is time-sensitive (UI waiting)
            response = future.result(timeout=120) 
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"RAG synthesis failed via PriorityPool: {e}")
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"RAG synthesis failed: {e}")
            return (
                f"Error generating synthesis: {str(e)}. "
                "The context chunks were retrieved successfully — "
                "please check that Ollama is running."
            )

    # -------------------------------------------------------------------
    # Raw Data Enrichment (Week 1: Verification Workflow)
    # -------------------------------------------------------------------

    def _enrich_citations_with_raw(self, citations: list[Citation]) -> list[dict]:
        """Add raw transcript text to each citation for verification."""
        rich_data = []
        
        for c in citations:
            try:
                chunk = self.db.execute("""
                    SELECT raw_text, cleaned_text, chunk_id
                    FROM transcript_chunks
                    WHERE chunk_id = ?
                """, (c.chunk_id,)).fetchone()
                
                if chunk:
                    rich_data.append({
                        "chunk_id": c.chunk_id,
                        "video_id": c.video_id,
                        "video_title": c.video_title,
                        "channel": c.channel_name,
                        "timestamp": c.timestamp_str,
                        "timestamp_seconds": int(c.start_timestamp),
                        "youtube_link": c.youtube_link,
                        "raw_text": chunk['raw_text'],
                        "cleaned_text": chunk['cleaned_text'],
                        "relevance_score": 1.0 - (c.start_timestamp - int(c.start_timestamp))  # rough approximation
                    })
            except Exception as e:
                logger.warning(f"Failed to enrich citation {c.chunk_id}: {e}")
                continue
        
        return rich_data
    
    def _get_full_transcripts_for_citations(self, citations: list[Citation]) -> list[dict]:
        """Get full transcripts for cited videos."""
        video_ids = set(c.video_id for c in citations)
        full_transcripts = []
        
        for vid in video_ids:
            try:
                transcript = self.db.get_full_transcript(vid)
                if transcript:
                    full_transcripts.append({
                        "video_id": vid,
                        "title": transcript['title'],
                        "channel": transcript['channel'],
                        "duration": f"{transcript['duration_seconds'] // 60}m {transcript['duration_seconds'] % 60}s",
                        "upload_date": transcript['upload_date'],
                        "full_text": transcript['full_cleaned_text'],
                        "access_via": f"Transcript Viewer > {vid}",
                        "chunk_count": transcript['total_chunks']
                    })
            except Exception as e:
                logger.warning(f"Failed to get full transcript for {vid}: {e}")
                continue
        
        return full_transcripts

