"""
Semantic chunker for knowledgeVault-YT.

Splits transcripts at topic boundaries using sentence-level embedding
similarity, producing chunks that are topically coherent rather than
fixed-size windows that may split mid-argument.

Falls back to sliding-window chunking if embeddings are unavailable.
"""

import logging
import re
from typing import Optional

from src.config import get_settings
from src.ingestion.transcript import TimestampedSegment
from src.storage.sqlite_store import TranscriptChunk
from src.storage.vector_store import _estimate_timestamp

logger = logging.getLogger(__name__)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex heuristics.

    Handles common abbreviations and decimal numbers to avoid false splits.
    """
    # Protect known abbreviations and decimals from splitting
    text = re.sub(r'(\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|approx))\.',
                  r'\1<DOT>', text)
    text = re.sub(r'(\d)\. ', r'\1<DOT> ', text)  # "3.5" shouldn't split

    sentences = re.split(r'(?<=[.!?])\s+', text)

    # Restore protected dots
    sentences = [s.replace('<DOT>', '.') for s in sentences]

    return [s.strip() for s in sentences if s.strip()]


def _compute_sentence_embeddings(sentences: list[str]) -> Optional[list[list[float]]]:
    """Compute embeddings for a list of sentences via Ollama.

    Returns None if Ollama is unavailable (triggers fallback to sliding-window).
    """
    try:
        import ollama as ollama_client
        settings = get_settings()
        model = settings["ollama"].get("embedding_model", "nomic-embed-text")

        # Batch embed
        response = ollama_client.embed(model=model, input=sentences)
        return response["embeddings"]
    except Exception as e:
        logger.warning(f"Sentence embedding failed (will fallback to sliding-window): {e}")
        return None


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


def semantic_chunk(
    cleaned_text: str,
    video_id: str,
    segments: list[TimestampedSegment],
    max_chunk_words: int = 600,
    min_chunk_words: int = 100,
    similarity_threshold: float = 0.4,
    group_size: int = 3,
) -> list[TranscriptChunk]:
    """Split text into topically coherent chunks using sentence embeddings.

    Algorithm:
        1. Split text into sentences
        2. Group sentences into windows of `group_size`
        3. Embed each group
        4. Compute cosine distance between consecutive groups
        5. Place chunk boundaries where distance exceeds threshold
        6. Merge undersized chunks with neighbors; split oversized ones

    Falls back to empty list if embeddings unavailable (caller should
    then use sliding_window_chunk).

    Args:
        cleaned_text: Full cleaned transcript text.
        video_id: YouTube video ID.
        segments: Original timestamped segments for timestamp estimation.
        max_chunk_words: Split chunks exceeding this word count.
        min_chunk_words: Merge chunks below this word count.
        similarity_threshold: Cosine distance above this triggers a split.
        group_size: Number of sentences per embedding group.

    Returns:
        List of TranscriptChunk objects, or empty list on failure.
    """
    sentences = _split_sentences(cleaned_text)
    if len(sentences) < group_size * 2:
        # Too few sentences for meaningful semantic splitting
        return []

    # Group sentences into windows
    groups = []
    for i in range(0, len(sentences) - group_size + 1, group_size):
        groups.append(" ".join(sentences[i:i + group_size]))

    if len(groups) < 2:
        return []

    # Compute embeddings
    embeddings = _compute_sentence_embeddings(groups)
    if embeddings is None:
        return []  # Caller falls back to sliding-window

    # Find topic boundaries (where cosine distance spikes)
    boundaries = []
    for i in range(1, len(embeddings)):
        dist = _cosine_distance(embeddings[i - 1], embeddings[i])
        if dist > similarity_threshold:
            # Boundary at the start of group i
            boundaries.append(i * group_size)

    # Build chunks from sentence ranges
    total_words = len(cleaned_text.split())
    split_points = [0] + boundaries + [len(sentences)]
    chunks = []
    chunk_index = 0

    for i in range(len(split_points) - 1):
        start_sent = split_points[i]
        end_sent = split_points[i + 1]
        chunk_text = " ".join(sentences[start_sent:end_sent])
        word_count = len(chunk_text.split())

        if word_count < min_chunk_words and chunks:
            # Merge with previous chunk
            prev = chunks[-1]
            merged_text = prev.cleaned_text + " " + chunk_text
            chunks[-1] = TranscriptChunk(
                chunk_id=prev.chunk_id,
                video_id=video_id,
                chunk_index=prev.chunk_index,
                raw_text=merged_text,
                cleaned_text=merged_text,
                word_count=len(merged_text.split()),
                start_timestamp=prev.start_timestamp,
                end_timestamp=_estimate_word_timestamp(
                    end_sent, len(sentences), total_words, segments
                ),
            )
            continue

        # Split oversized chunks
        if word_count > max_chunk_words:
            words = chunk_text.split()
            for sub_start in range(0, len(words), max_chunk_words):
                sub_text = " ".join(words[sub_start:sub_start + max_chunk_words])
                sub_wc = len(sub_text.split())
                if sub_wc < min_chunk_words and chunks:
                    prev = chunks[-1]
                    merged = prev.cleaned_text + " " + sub_text
                    chunks[-1] = TranscriptChunk(
                        chunk_id=prev.chunk_id,
                        video_id=video_id,
                        chunk_index=prev.chunk_index,
                        raw_text=merged,
                        cleaned_text=merged,
                        word_count=len(merged.split()),
                        start_timestamp=prev.start_timestamp,
                        end_timestamp=prev.end_timestamp,
                    )
                    continue
                chunk_id = f"{video_id}__chunk_{chunk_index:04d}"
                chunks.append(TranscriptChunk(
                    chunk_id=chunk_id,
                    video_id=video_id,
                    chunk_index=chunk_index,
                    raw_text=sub_text,
                    cleaned_text=sub_text,
                    word_count=sub_wc,
                    start_timestamp=_estimate_word_timestamp(
                        start_sent, len(sentences), total_words, segments
                    ),
                    end_timestamp=_estimate_word_timestamp(
                        end_sent, len(sentences), total_words, segments
                    ),
                ))
                chunk_index += 1
        else:
            chunk_id = f"{video_id}__chunk_{chunk_index:04d}"
            chunks.append(TranscriptChunk(
                chunk_id=chunk_id,
                video_id=video_id,
                chunk_index=chunk_index,
                raw_text=chunk_text,
                cleaned_text=chunk_text,
                word_count=word_count,
                start_timestamp=_estimate_word_timestamp(
                    start_sent, len(sentences), total_words, segments
                ),
                end_timestamp=_estimate_word_timestamp(
                    end_sent, len(sentences), total_words, segments
                ),
            ))
            chunk_index += 1

    logger.info(
        f"Semantic chunking for {video_id}: {len(chunks)} chunks "
        f"from {len(sentences)} sentences ({len(boundaries)} topic boundaries)"
    )
    return chunks


def _estimate_word_timestamp(
    sentence_index: int,
    total_sentences: int,
    total_words: int,
    segments: list[TimestampedSegment],
) -> float:
    """Estimate timestamp from sentence position."""
    if not segments or total_sentences == 0:
        return 0.0
    proportion = sentence_index / total_sentences
    word_pos = int(proportion * total_words)
    return _estimate_timestamp(word_pos, total_words, segments)
