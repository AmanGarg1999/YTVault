"""
Integration tests for Week 1 enhancements: Transcript access and raw data.

Tests:
- Transcript retrieval methods
- Search across transcripts
- Timestamp-based retrieval
- Transcript comparison
- Global search functionality
- RAG response enhancement with raw data
"""

import pytest
from datetime import datetime
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.rag_engine import RAGEngine, Citation
from pathlib import Path


class TestTranscriptAccess:
    """Test transcript retrieval from database."""
    
    @pytest.fixture
    def db(self):
        """Create test database connection."""
        settings = {
            "sqlite": {
                "path": ":memory:"  # Use in-memory DB for testing
            }
        }
        db = SQLiteStore(settings["sqlite"]["path"])
        # db._init_schema() is already called in __init__, but we can call it again or just remove
        return db
    
    def test_get_full_transcript_empty(self, db):
        """Test get_full_transcript with non-existent video."""
        result = db.get_full_transcript("nonexistent_video_id")
        assert result is None
    
    def test_get_full_transcript_with_data(self, db):
        """Test get_full_transcript with actual data."""
        # Setup: Create test data
        channel = db.execute(
            "INSERT INTO channels (channel_id, name, url) VALUES (?, ?, ?)",
            ("test_channel", "Test Channel", "https://youtube.com/@test")
        )
        db.conn.commit()
        
        video_id = "test_video_123"
        db.execute(
            """INSERT INTO videos 
               (video_id, channel_id, title, url, checkpoint_stage, upload_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (video_id, "test_channel", "Test Video", "https://youtube.com/watch?v=test",
             "DONE", "2024-01-01")
        )
        db.conn.commit()
        
        # Add transcript chunks
        chunk_data = [
            ("chunk_1", video_id, 0, "This is raw text", "This is cleaned text", 
             0.0, 10.0, 4),
            ("chunk_2", video_id, 1, "More raw", "More cleaned",
             10.0, 20.0, 2),
        ]
        
        for chunk_id, vid, idx, raw, cleaned, start, end, wc in chunk_data:
            db.execute(
                """INSERT INTO transcript_chunks
                   (chunk_id, video_id, chunk_index, raw_text, cleaned_text,
                    start_timestamp, end_timestamp, word_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (chunk_id, vid, idx, raw, cleaned, start, end, wc)
            )
        db.conn.commit()
        
        # Test
        result = db.get_full_transcript(video_id)
        
        assert result is not None
        assert result["video_id"] == video_id
        assert result["title"] == "Test Video"
        assert result["channel"] == "Test Channel"
        assert result["total_chunks"] == 2
        assert "This is cleaned text" in result["full_cleaned_text"]
        assert "This is raw text" in result["full_raw_text"]
    
    def test_search_transcript(self, db):
        """Test searching within a transcript."""
        # Setup test data
        channel_id = "ch_1"
        db.execute("INSERT INTO channels (channel_id, name, url) VALUES (?, ?, ?)",
                  (channel_id, "Channel", "https://youtube.com/@ch"))
        
        video_id = "vid_1"
        db.execute(
            """INSERT INTO videos 
               (video_id, channel_id, title, url, checkpoint_stage)
               VALUES (?, ?, ?, ?, ?)""",
            (video_id, channel_id, "Video", "https://youtube.com/watch?v=1", "DONE")
        )
        
        db.execute(
            """INSERT INTO transcript_chunks
               (chunk_id, video_id, chunk_index, raw_text, cleaned_text,
                start_timestamp, end_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("c1", video_id, 0, "This talks about AI machine learning",
             "This talks about AI machine learning", 0.0, 10.0)
        )
        
        db.execute(
            """INSERT INTO transcript_chunks
               (chunk_id, video_id, chunk_index, raw_text, cleaned_text,
                start_timestamp, end_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("c2", video_id, 1, "Neural networks and deep learning models",
             "Neural networks and deep learning models", 10.0, 20.0)
        )
        db.conn.commit()
        
        # Test
        results = db.search_transcript(video_id, "machine learning")
        assert len(results) >= 1
        assert any("machine learning" in r["cleaned_text"].lower() for r in results)
    
    def test_search_transcript_empty(self, db):
        """Test search with no results."""
        channel_id = "ch_1"
        db.execute("INSERT INTO channels (channel_id, name, url) VALUES (?, ?, ?)",
                  (channel_id, "Channel", "https://youtube.com/@ch"))
        
        video_id = "vid_1"
        db.execute(
            """INSERT INTO videos 
               (video_id, channel_id, title, url, checkpoint_stage)
               VALUES (?, ?, ?, ?, ?)""",
            (video_id, channel_id, "Video", "https://youtube.com/watch?v=1", "DONE")
        )
        
        db.execute(
            """INSERT INTO transcript_chunks
               (chunk_id, video_id, chunk_index, raw_text, cleaned_text,
                start_timestamp, end_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("c1", video_id, 0, "This is about cats",
             "This is about cats", 0.0, 10.0)
        )
        db.conn.commit()
        
        # Test
        results = db.search_transcript(video_id, "unicorn")
        assert len(results) == 0
    
    def test_get_transcript_at_timestamp(self, db):
        """Test getting transcript around specific timestamp."""
        # Setup
        channel_id = "ch_1"
        db.execute("INSERT INTO channels (channel_id, name, url) VALUES (?, ?, ?)",
                  (channel_id, "Channel", "https://youtube.com/@ch"))
        
        video_id = "vid_1"
        db.execute(
            """INSERT INTO videos 
               (video_id, channel_id, title, url, checkpoint_stage)
               VALUES (?, ?, ?, ?, ?)""",
            (video_id, channel_id, "Video", "https://youtube.com/watch?v=1", "DONE")
        )
        
        # Create chunks around 50 second mark
        for i, ts in enumerate([40.0, 50.0, 60.0]):
            db.execute(
                """INSERT INTO transcript_chunks
                   (chunk_id, video_id, chunk_index, raw_text, cleaned_text,
                    start_timestamp, end_timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f"c{i}", video_id, i, f"Text at {ts}s",
                 f"Text at {ts}s", ts, ts + 10.0)
            )
        db.conn.commit()
        
        # Test: get context around 50 seconds with 30 second context
        result = db.get_transcript_at_timestamp(video_id, 50.0, context_seconds=30)
        
        assert result is not None
        assert result["target_timestamp"] == 50.0
        assert result["context_seconds"] == 30
        assert len(result["chunks"]) >= 1  # Should have at least the 50s chunk


class TestRAGEnhancement:
    """Test RAG response enhancement with raw data."""
    
    def test_rag_response_has_raw_data_fields(self):
        """Test that RAGResponse includes raw data fields."""
        from src.intelligence.rag_engine import RAGResponse
        
        response = RAGResponse(
            query="Test query",
            answer="Test answer",
            raw_chunks=[{"chunk_id": "c1", "text": "Raw"}],
            full_transcripts=[{"video_id": "v1", "title": "Video"}],
            verification_notes="Raw data available"
        )
        
        assert hasattr(response, "raw_chunks")
        assert hasattr(response, "full_transcripts")
        assert hasattr(response, "verification_notes")
        assert len(response.raw_chunks) == 1
        assert len(response.full_transcripts) == 1
        assert response.verification_notes == "Raw data available"
    
    def test_citation_has_youtube_link(self):
        """Test Citation generates correct YouTube link."""
        citation = Citation(
            source_id="s1",
            chunk_id="c1",
            video_id="dQw4w9WgXcQ",
            video_title="Test Video",
            channel_name="Test Channel",
            start_timestamp=120.0,
            end_timestamp=130.0,
            text_excerpt="Test text"
        )
        
        assert "youtube.com/watch?v=" in citation.youtube_link
        assert "dQw4w9WgXcQ" in citation.youtube_link
        assert "t=120" in citation.youtube_link


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_transcript_search_integration(self):
        """Test full transcript search workflow."""
        # This would require a real database with data
        # For now, just verify the methods exist and are callable
        from src.storage.sqlite_store import SQLiteStore
        
        # Check methods exist
        assert hasattr(SQLiteStore, "get_full_transcript")
        assert hasattr(SQLiteStore, "search_transcript")
        assert hasattr(SQLiteStore, "get_transcript_at_timestamp")
        assert hasattr(SQLiteStore, "compare_transcripts")
        assert hasattr(SQLiteStore, "search_all_transcripts")
    
    def test_rag_enhancement_integration(self):
        """Test RAG enhancement for verification workflow."""
        from src.intelligence.rag_engine import RAGEngine
        
        # Check methods exist
        assert hasattr(RAGEngine, "_enrich_citations_with_raw")
        assert hasattr(RAGEngine, "_get_full_transcripts_for_citations")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
