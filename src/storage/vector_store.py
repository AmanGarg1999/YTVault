"""
ChromaDB vector store for knowledgeVault-YT.

Handles sliding-window chunking, embedding generation via Ollama,
and semantic search over transcript chunks.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import chromadb
import ollama as ollama_client

from src.config import get_settings
from src.ingestion.transcript import TimestampedSegment
from src.storage.sqlite_store import TranscriptChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ollama Embedding Function (ChromaDB-compatible)
# ---------------------------------------------------------------------------

class OllamaEmbeddingFunction:
    """Custom embedding function using local Ollama with batch support."""

    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name
        self._name = f"ollama-{self.model_name}"

    def name(self):
        """Return the name of this embedding function (callable method for ChromaDB)."""
        return self._name

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Attempts batch embedding first, falls back to sequential.
        Respects the global LLM concurrency semaphore.
        """
        if not input:
            return []

        # Validate input
        if not isinstance(input, list):
            logger.error(f"Invalid input type to __call__: expected list, got {type(input)}")
            raise TypeError(f"Expected list of strings, got {type(input)}")

        from src.utils.llm_pool import get_llm_semaphore
        semaphore = get_llm_semaphore()

        with semaphore:
            # Try batch embedding (Ollama library 0.1.7+ supports .embed)
            try:
                if hasattr(ollama_client, "embed"):
                    response = ollama_client.embed(
                        model=self.model_name,
                        input=input,
                    )
                    embeddings = response.get("embeddings", [])
                    logger.debug(f"Batch embed succeeded: {len(embeddings)} embeddings")
                    return embeddings
            except Exception as e:
                logger.debug(f"Ollama batch embed failed, falling back to sequential: {e}")

            # Sequential fallback for older Ollama versions (.embeddings)
            embeddings = []
            try:
                for text in input:
                    if hasattr(ollama_client, "embeddings"):
                        response = ollama_client.embeddings(
                            model=self.model_name,
                            prompt=text,
                        )
                        embeddings.append(response["embedding"])
                    else:
                        # Last resort fallback if library structure is unexpected
                        raise AttributeError("Ollama client has neither 'embed' nor 'embeddings' methods")
            except Exception as e:
                logger.error(f"Ollama embedding failed: {e}")
                raise

            logger.debug(f"Sequential embed succeeded: {len(embeddings)} embeddings")
            return embeddings




# ---------------------------------------------------------------------------
# Sliding Window Chunker
# ---------------------------------------------------------------------------

def sliding_window_chunk(
    cleaned_text: str,
    video_id: str,
    segments: list[TimestampedSegment],
    window_size: int = 400,
    overlap: int = 80,
    min_chunk_size: int = 50,
) -> list[TranscriptChunk]:
    """Split cleaned transcript into overlapping chunks with timestamp mapping.

    Args:
        cleaned_text: The cleaned transcript text.
        video_id: YouTube video ID.
        segments: Original timestamped segments for timestamp estimation.
        window_size: Target words per chunk (default 400).
        overlap: Overlap words between consecutive chunks (default 80).
        min_chunk_size: Skip chunks shorter than this many words.

    Returns:
        List of TranscriptChunk objects ready for storage and embedding.
    """
    words = cleaned_text.split()
    if len(words) < min_chunk_size:
        return []

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(words):
        end = min(start + window_size, len(words))
        chunk_text = " ".join(words[start:end])
        word_count = end - start

        if word_count < min_chunk_size and chunk_index > 0:
            # Last chunk too small — merge with previous
            break

        # Estimate timestamps from word positions
        start_ts = _estimate_timestamp(start, len(words), segments)
        end_ts = _estimate_timestamp(end, len(words), segments)

        chunk_id = f"{video_id}__chunk_{chunk_index:04d}"
        chunks.append(TranscriptChunk(
            chunk_id=chunk_id,
            video_id=video_id,
            chunk_index=chunk_index,
            raw_text=chunk_text,
            cleaned_text=chunk_text,
            word_count=word_count,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
        ))

        start += window_size - overlap
        chunk_index += 1

    logger.info(f"Chunked video {video_id}: {len(chunks)} chunks from {len(words)} words")
    return chunks


def _estimate_timestamp(
    word_index: int,
    total_words: int,
    segments: list[TimestampedSegment],
) -> float:
    """Estimate video timestamp from word position using segment timing.

    Uses a cumulative word-count index from actual segments to map word
    positions to timestamps more accurately than linear interpolation.
    Falls back to linear if segments lack text data.
    """
    if not segments:
        return 0.0

    total_duration = segments[-1].start + segments[-1].duration
    if total_words == 0:
        return 0.0

    # Build cumulative word-count index from segments
    cumulative_words = 0
    for seg in segments:
        seg_words = len(seg.text.split()) if seg.text else 0
        cumulative_words += seg_words
        if cumulative_words >= word_index:
            # Found the segment containing this word position
            # Interpolate within the segment
            words_into_seg = seg_words - (cumulative_words - word_index)
            if seg_words > 0:
                seg_proportion = words_into_seg / seg_words
            else:
                seg_proportion = 0.0
            return round(seg.start + seg_proportion * seg.duration, 2)

    # Word index beyond all segments — return end of last segment
    return round(total_duration, 2)


# ---------------------------------------------------------------------------
# Vector Store
# ---------------------------------------------------------------------------

class VectorStore:
    """ChromaDB-backed vector store for semantic transcript search."""

    def __init__(self):
        settings = get_settings()
        cfg = settings["chromadb"]
        ollama_cfg = settings["ollama"]

        self.client = chromadb.PersistentClient(path=cfg["path"])
        self.embedding_fn = OllamaEmbeddingFunction(
            model_name=ollama_cfg.get("embedding_model", "nomic-embed-text")
        )
        self.collection = self.client.get_or_create_collection(
            name=cfg.get("collection_name", "transcript_chunks"),
            metadata={"hnsw:space": cfg.get("similarity_space", "cosine")},
            embedding_function=self.embedding_fn,
        )
        logger.info(
            f"VectorStore initialized: {self.collection.count()} existing documents"
        )

    def upsert_chunks(self, chunks: list[TranscriptChunk], channel_id: str = "",
                      upload_date: str = "", language_iso: str = "en",
                      skip_ids: set = None) -> int:
        """Embed and upsert transcript chunks into ChromaDB with deduplication.

        Args:
            chunks: List of TranscriptChunk objects.
            channel_id: Channel ID for metadata filtering.
            upload_date: Upload date for temporal queries.
            language_iso: Language code for filtering.
            skip_ids: Set of chunk_ids to skip embedding (content unchanged).

        Returns:
            Number of chunks upserted (excludes skipped).
        """
        if not chunks:
            return 0

        # P0-B: Skip chunks already embedded with unchanged content
        if skip_ids:
            original_count = len(chunks)
            chunks = [c for c in chunks if c.chunk_id not in skip_ids]
            skipped_embed = original_count - len(chunks)
            if skipped_embed:
                logger.info(f"P0-B: Skipped {skipped_embed} unchanged chunks (embedding skip)")

        if not chunks:
            return 0

        # Deduplication: track unique text hashes to avoid duplicate embeddings
        seen_hashes = set()
        deduplicated_chunks = []
        skipped = 0
        
        for chunk in chunks:
            # Simple hash-based deduplication (first 100 chars)
            chunk_hash = hash(chunk.cleaned_text[:100])
            if chunk_hash not in seen_hashes:
                seen_hashes.add(chunk_hash)
                deduplicated_chunks.append(chunk)
            else:
                skipped += 1
        
        if skipped > 0:
            logger.debug(f"Deduplication: skipped {skipped} duplicate chunks")

        # Batch upsert for performance
        batch_size = 50
        total = 0

        try:
            for i in range(0, len(deduplicated_chunks), batch_size):
                batch = deduplicated_chunks[i:i + batch_size]
                try:
                    # Verify embedding function is callable
                    if not callable(self.embedding_fn):
                        logger.error(f"embedding_fn is not callable: {type(self.embedding_fn)}")
                        raise TypeError(f"embedding_fn must be callable, got {type(self.embedding_fn)}")
                    
                    self.collection.upsert(
                        ids=[c.chunk_id for c in batch],
                        documents=[c.cleaned_text for c in batch],
                        metadatas=[{
                            "video_id": c.video_id,
                            "channel_id": channel_id,
                            "chunk_index": c.chunk_index,
                            "start_timestamp": c.start_timestamp,
                            "end_timestamp": c.end_timestamp,
                            "word_count": c.word_count,
                            "upload_date": upload_date,
                            "language_iso": language_iso,
                        } for c in batch],
                    )
                    total += len(batch)
                    logger.debug(f"Upserted batch {i // batch_size + 1}: {len(batch)} chunks")
                except Exception as e:
                    logger.error(f"Failed to upsert batch {i // batch_size + 1}: {e}")
                    raise

            logger.info(f"Upserted {total} chunks to vector store (deduplicated {skipped})")
            return total
        except Exception as e:
            logger.error(f"upsert_chunks failed: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 15,
        channel_ids: Optional[list[str]] = None,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None,
    ) -> list[dict]:
        """Semantic search across transcript chunks.

        Args:
            query: Natural language query.
            top_k: Number of results to return.
            channel_ids: List of channel IDs to filter by.
            where: Custom metadata filter (merged with channel_ids if provided).
            where_document: Document content filter.

        Returns:
            List of result dicts with keys: chunk_id, text, metadata, distance.
        """
        # Build metadata filter
        final_where = where or {}
        if channel_ids:
            if len(channel_ids) == 1:
                final_where["channel_id"] = channel_ids[0]
            else:
                final_where["channel_id"] = {"$in": channel_ids}

        # Generate embeddings explicitly to avoid ChromaDB dispatcher issues
        query_vecs = self.embedding_fn([query])
        
        kwargs = {
            "query_embeddings": query_vecs,
            "n_results": top_k,
        }
        if final_where:
            kwargs["where"] = final_where
        if where_document:
            kwargs["where_document"] = where_document

        results = self.collection.query(**kwargs)

        # Flatten results into a list of dicts
        output = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                output.append({
                    "chunk_id": chunk_id,
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                })

        logger.info(f"Vector search for '{query[:60]}...': {len(output)} results")
        return output

    def delete_video_chunks(self, video_id: str) -> None:
        """Delete all chunks for a specific video."""
        self.collection.delete(where={"video_id": video_id})
        logger.info(f"Deleted vector chunks for video {video_id}")

    def get_existing_chunk_ids(self, video_id: str) -> set:
        """P0-B: Return set of chunk_ids already stored in ChromaDB for a video.

        Used by _stage_embed to diff against current DB chunks so only
        new or changed chunks incur embedding cost.
        """
        try:
            results = self.collection.get(
                where={"video_id": video_id},
                include=[],  # Only IDs, no documents/embeddings needed
            )
            return set(results["ids"]) if results and results.get("ids") else set()
        except Exception as e:
            logger.warning(f"Could not fetch existing chunk IDs for {video_id}: {e}")
            return set()

    def count_unique_videos(self) -> int:
        """P0-D: Count distinct video_ids indexed in ChromaDB.

        Used by the Graph Health dashboard to compare ChromaDB coverage
        against SQLite and Neo4j.
        """
        try:
            # ChromaDB does not have a GROUP BY—fetch all metadatas with just video_id
            results = self.collection.get(include=["metadatas"])
            if not results or not results.get("metadatas"):
                return 0
            unique_vids = {m.get("video_id", "") for m in results["metadatas"]}
            unique_vids.discard("")  # remove blanks
            return len(unique_vids)
        except Exception as e:
            logger.warning(f"count_unique_videos failed: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        return {
            "total_documents": self.collection.count(),
            "collection_name": self.collection.name,
        }
