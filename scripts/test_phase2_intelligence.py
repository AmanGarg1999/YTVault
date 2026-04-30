import sys
import os
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.sqlite_store import SQLiteStore
from src.storage.graph_store import GraphStore
from src.intelligence.dossier_engine import DossierEngine
from src.intelligence.analysis_engine import AnalysisEngine, CoverageAnalyzer
from src.intelligence.epiphany_engine import EpiphanyEngine
from src.intelligence.rag_engine import RAGEngine
from src.storage.vector_store import VectorStore

def test_phase2():
    db_path = "data/knowledgevault.db"
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    with SQLiteStore(db_path) as db:
        graph = GraphStore()
        analysis = AnalysisEngine(db)
        dossier_engine = DossierEngine(db, graph, analysis)
        coverage_analyzer = CoverageAnalyzer(db)
        
        # 1. Test Topic Velocity
        print("\n--- Testing Topic Velocity ---")
        test_topic = "Artificial Intelligence" # Adjust if needed
        velocity = analysis.get_topic_velocity(test_topic)
        print(f"Topic: {test_topic}")
        print(f"Velocity: {velocity['velocity']}x, Trend: {velocity['trend']}")
        
        # 2. Test Coverage Analysis
        print("\n--- Testing Coverage Analysis ---")
        coverage = coverage_analyzer.analyze_topic_coverage(test_topic)
        print(f"Score: {coverage['score']*100:.1f}%, Status: {coverage['status']}")
        print(f"Gaps: {coverage['gaps']}")
        
        # 3. Test Dossier Generation
        print("\n--- Testing Dossier Generation ---")
        dossier = dossier_engine.generate_topic_dossier(test_topic)
        print(f"Dossier Version: {dossier['metadata']['version']}")
        print(f"Sections found: {list(dossier['sections'].keys())}")
        
        markdown = dossier_engine.format_dossier_markdown(dossier)
        print(f"Markdown Length: {len(markdown)} chars")
        print("First 200 chars of markdown:")
        print(markdown[:200])
        
        # 4. Test Epiphany Briefing Persistence
        print("\n--- Testing Epiphany Persistence ---")
        rag = RAGEngine(db, VectorStore())
        ee = EpiphanyEngine(db, graph, rag)
        
        # Fetch latest briefings
        briefings = ee.get_latest_briefings(limit=1)
        print(f"Found {len(briefings)} historical briefings.")
        if briefings:
            print(f"Latest briefing topic: {briefings[0].topic}")

if __name__ == "__main__":
    test_phase2()
