import unittest
from unittest.mock import MagicMock, patch
import json
import os
from pathlib import Path

from src.storage.sqlite_store import SQLiteStore, Video, Channel, MonitoredChannel, ThematicBridge
from src.intelligence.research_agent import ResearchAgent
from src.intelligence.live_monitor import LiveMonitor
from src.intelligence.bridge_discovery import BridgeDiscoveryEngine

class TestIntelligenceExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use in-memory DB or temporary file
        cls.db_path = "test_expansion.db"
        cls.db = SQLiteStore(cls.db_path)

    def setUp(self):
        """Reset database for each test in correct order to avoid FK issues."""
        self.db.execute("DELETE FROM weekly_briefs")
        self.db.execute("DELETE FROM research_reports")
        self.db.execute("DELETE FROM thematic_bridges")
        self.db.execute("DELETE FROM video_sentiment")
        self.db.execute("DELETE FROM video_summaries")
        self.db.execute("DELETE FROM monitored_channels")
        self.db.execute("DELETE FROM videos")
        self.db.execute("DELETE FROM channels")
        self.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    @patch('src.intelligence.research_agent.VectorStore')
    @patch('src.intelligence.research_agent.Path.mkdir')
    def test_metadata_inclusion(self, mock_mkdir, mock_vs):
        """Verify view_count and sentiment are included in context."""
        # Setup fake channel, video and sentiment
        c = Channel(channel_id="c1", name="Test Channel", url="u1")
        v = Video(video_id="v1", channel_id="c1", title="Test Video", url="url1", view_count=1000, like_count=100)
        self.db.upsert_channel(c)
        self.db.insert_video(v)
        self.db.execute("INSERT INTO video_sentiment (video_id, label, score) VALUES (?, ?, ?)", ("v1", "Positive", 0.9))
        self.db.commit()

        agent = ResearchAgent(self.db)
        agent.output_dir = Path("test_reports") # Local path
        
        # Mock retrieval to return our test video
        from src.intelligence.rag_engine import RAGResponse, Citation
        mock_cit = Citation(
            source_id="s1", chunk_id="ch1", video_id="v1", 
            video_title="Test Video", channel_name="Test Channel",
            start_timestamp=0, end_timestamp=10, text_excerpt="Hello world",
        )
        agent.rag.query = MagicMock(return_value=RAGResponse(query="q", answer="a", citations=[mock_cit]))
        agent.vs.search_summaries = MagicMock(return_value=[])
        
        # Test report generation (mocking LLM synthesis)
        with patch('ollama.chat') as mock_chat:
            mock_chat.return_value = {"message": {"content": "Test Paper content"}}
            # Mock the file write
            with patch("builtins.open", MagicMock()):
                agent.generate_report("test query")
                
                # Verify the prompt sent to LLM contains metadata
                call_args = mock_chat.call_args_list[0]
                prompt_content = call_args[1]['messages'][0]['content']
                self.assertIn("1,000", prompt_content)
                self.assertIn("Positive (0.90)", prompt_content)

    @patch('src.intelligence.research_agent.VectorStore')
    @patch('src.intelligence.research_agent.Path.mkdir')
    def test_peer_review_logic(self, mock_mkdir, mock_vs):
        """Verify peer review identifies hallucinations."""
        agent = ResearchAgent(self.db)
        with patch('ollama.chat') as mock_chat:
            # Just one call to _peer_review in this test
            mock_chat.return_value = {"message": {"content": "- Hallucination: The context says the moon is basaltic rock, not cheese."}}
            
            # Mock context
            context = "SOURCE: Moon Data\nEXCERPT: The moon is made of basaltic rock."
            
            review = agent._peer_review("What is the moon made of?", "The moon is made of cheese [^1].", context)
            self.assertIsNotNone(review)
            self.assertIn("basaltic rock", review)

    def test_bridge_discovery_categories(self):
        """Verify bridge discovery uses multiple categories."""
        # Add categorized topics
        c1 = Channel(channel_id="tech_ch", name="Tech", url="u1", category="Technology")
        c2 = Channel(channel_id="bio_ch", name="Bio", url="u2", category="Biology")
        self.db.upsert_channel(c1)
        self.db.upsert_channel(c2)
        
        v1 = Video(video_id="v_tech", channel_id="tech_ch", title="AI", url="u1")
        v2 = Video(video_id="v_bio", channel_id="bio_ch", title="Cells", url="u2")
        self.db.insert_video(v1)
        self.db.insert_video(v2)
        
        # We need the real VideoSummary class or a mock
        from src.storage.sqlite_store import VideoSummary
        self.db.upsert_video_summary(VideoSummary(video_id="v_tech", topics_json=json.dumps([{"name": "Neural Networks"}])))
        self.db.upsert_video_summary(VideoSummary(video_id="v_bio", topics_json=json.dumps([{"name": "Mitochondria"}])))
        self.db.commit()

        engine = BridgeDiscoveryEngine(self.db)
        with patch.object(engine, '_find_connection') as mock_find:
            mock_find.return_value = ThematicBridge(topic_a="Neural Networks", topic_b="Mitochondria", insight="Synergy!")
            bridges = engine.discover_bridges(sample_size=1)
            
            self.assertEqual(len(bridges), 1)
            # Depending on sorting/randomness
            self.assertTrue(bridges[0].topic_a in ["Neural Networks", "Mitochondria"])

    @patch('src.intelligence.research_agent.VectorStore')
    @patch('src.intelligence.research_agent.Path.mkdir')
    def test_live_monitor_logic(self, mock_mkdir, mock_vs):
        """Verify LiveMonitor detects new videos and triggers synthesis."""
        monitor = LiveMonitor(self.db)
        
        # Follow a channel
        c_url = "https://www.youtube.com/@test"
        with patch('src.ingestion.discovery.extract_channel_info') as mock_info:
            mock_info.return_value = Channel(channel_id="c_test", name="Test", url=c_url)
            monitor.follow_channel(c_url)
        
        # Check if subscription saved
        subs = self.db.get_monitored_channels()
        self.assertEqual(len(subs), 1)
        
        # Mock discovery find new video
        with patch('src.intelligence.live_monitor.discover_video_ids') as mock_disc:
            mock_disc.return_value = ["new_vid_1"]
            self.db.insert_video(Video(video_id="new_vid_1", channel_id="c_test", title="New!", url="u"))
            
            # Mock ResearchAgent report generation
            with patch.object(monitor.research_agent, 'generate_report') as mock_gen:
                from src.storage.sqlite_store import ResearchReport
                mock_gen.return_value = ResearchReport(report_id=1, file_path="n/a", summary="New summary")
                
                brief = monitor.run_subscriptions_check()
                self.assertIsNotNone(brief)

if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
