import logging
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    orchestrator = PipelineOrchestrator()
    try:
        logger.info("Starting Vault Health Repair...")
        results = orchestrator.repair_vault_health()
        logger.info(f"Repair results: {results}")
    finally:
        orchestrator.close()

if __name__ == "__main__":
    main()
