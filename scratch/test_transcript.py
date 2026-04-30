import sys
import logging
sys.path.append('.')
from src.ingestion.transcript import fetch_transcript
logging.basicConfig(level=logging.INFO)

# force youtube_transcript_api to raise exception
import youtube_transcript_api
class MockApi:
    def __init__(self, *args, **kwargs):
        pass
    def list(self, *args, **kwargs):
        raise youtube_transcript_api._errors.TooManyRequests("YouTube is blocking requests")

youtube_transcript_api.YouTubeTranscriptApi = MockApi

result = fetch_transcript("prTAsdltgHU")
print(f"Success: {result.success}")
print(f"Strategy: {result.strategy}")
print(f"Segments: {len(result.segments)}")
