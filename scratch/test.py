import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from src.pipeline.orchestrator import PipelineOrchestrator
orchestrator = PipelineOrchestrator()
orchestrator.run("https://www.youtube.com/watch?v=EAMNgSdTzIg", force_metadata_refresh=True)
