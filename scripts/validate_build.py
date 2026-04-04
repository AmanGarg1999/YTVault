#!/usr/bin/env python3
"""
Comprehensive validation script for knowledgeVault-YT app
"""
import sys
sys.path.insert(0, '/app')

print("=" * 60)
print("knowledgeVault-YT Docker Build Validation Report")
print("=" * 60)

# Test 1: Core module imports
print("\n[1] Testing Core Module Imports...")
try:
    from src.config import ensure_data_dirs, get_settings
    from src.storage.sqlite_store import SQLiteStore
    from src.storage.vector_store import VectorStore
    from src.storage.graph_store import GraphStore
    print("    ✓ All core modules loaded successfully")
except Exception as e:
    print(f"    ✗ FAILED: {e}")
    sys.exit(1)

# Test 2: Pipeline modules
print("\n[2] Testing Pipeline Modules...")
try:
    from src.pipeline.orchestrator import PipelineOrchestrator
    from src.pipeline.checkpoint import CheckpointManager
    from src.pipeline.worker import PipelineWorker
    print("    ✓ All pipeline modules loaded successfully")
except Exception as e:
    print(f"    ✗ FAILED: {e}")
    sys.exit(1)

# Test 3: Intelligence modules
print("\n[3] Testing Intelligence Modules...")
try:
    from src.intelligence.rag_engine import RAGEngine
    from src.intelligence.summarizer import Summarizer
    from src.intelligence.entity_resolver import EntityResolver
    from src.intelligence.query_parser import QueryParser
    from src.intelligence.chunk_analyzer import ChunkAnalyzer
    print("    ✓ All intelligence modules loaded successfully")
except Exception as e:
    print(f"    ✗ FAILED: {e}")
    sys.exit(1)

# Test 4: Ingestion modules
print("\n[4] Testing Ingestion Modules...")
try:
    from src.ingestion.discovery import YoutubeDiscovery
    from src.ingestion.transcript import TranscriptExtractor
    from src.ingestion.refinement import ContentRefinement
    from src.ingestion.triage import ContentTriageClassifier
    print("    ✓ All ingestion modules loaded successfully")
except Exception as e:
    print(f"    ✗ FAILED: {e}")
    sys.exit(1)

# Test 5: Utility modules
print("\n[5] Testing Utility Modules...")
try:
    from src.utils.llm_pool import LLMPool
    from src.utils.health import HealthCheck
    from src.utils.retry import retry
    from src.utils.eta import ETACalculator
    print("    ✓ All utility modules loaded successfully")
except Exception as e:
    print(f"    ✗ FAILED: {e}")
    sys.exit(1)

# Test 6: Page modules (Streamlit pages)
print("\n[6] Testing Streamlit Page Modules...")
pages = [
    "dashboard",
    "ingestion_hub",
    "pipeline_center",
    "intelligence_lab",
    "explorer",
    "guest_intel",
    "export_center",
    "logs_monitor",
    "data_management",
    "reject_review",
    "transcript_viewer",
    "performance_metrics",
    "comparative_lab",
]

failed_pages = []
for page in pages:
    try:
        module = __import__(f"src.ui.views.{page}", fromlist=[page])
        if hasattr(module, "render"):
            print(f"    ✓ {page:25} page module OK")
        else:
            print(f"    ✗ {page:25} missing render() function")
            failed_pages.append(page)
    except Exception as e:
        print(f"    ✗ {page:25} FAILED: {str(e)[:40]}")
        failed_pages.append(page)

if failed_pages:
    print(f"\n    FAILED pages: {', '.join(failed_pages)}")
    sys.exit(1)

# Test 7: Database initialization
print("\n[7] Testing Database Initialization...")
try:
    ensure_data_dirs()
    settings = get_settings()
    db = SQLiteStore(settings["sqlite"]["path"])
    print("    ✓ SQLiteStore initialized successfully")
    db.close()
except Exception as e:
    print(f"    ✗ FAILED: {e}")
    sys.exit(1)

# Test 8: Settings validation
print("\n[8] Testing Configuration Settings...")
try:
    settings = get_settings()
    required_keys = ["sqlite", "chromadb", "neo4j", "pipeline"]
    for key in required_keys:
        if key not in settings:
            raise ValueError(f"Missing required setting: {key}")
        print(f"    ✓ {key:15} configured")
except Exception as e:
    print(f"    ✗ FAILED: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ ALL VALIDATION TESTS PASSED")
print("=" * 60)
print("\nDocker build is ready for production!")
