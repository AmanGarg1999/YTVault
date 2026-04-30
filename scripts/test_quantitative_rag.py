import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.intelligence.rag_engine import RAGEngine
from src.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_quant_rag")

def test_quantitative_rag():
    settings = get_settings()
    db = SQLiteStore(settings["sqlite"]["path"])
    vs = VectorStore()
    rag = RAGEngine(db, vs)
    
    # Choose a topic likely to exist in the vault
    query = "topic:AI What are the latest developments in artificial intelligence?"
    
    print(f"Executing Query: {query}")
    print("-" * 50)
    
    response = rag.query(query)
    
    print(f"\nQuery Plan Topic Filter: {response.query_plan.topic_filter if response.query_plan else 'None'}")
    print(f"Number of Citations: {len(response.citations)}")
    for i, c in enumerate(response.citations):
        print(f"Citation {i+1} topic: '{c.topic}'")

    print(f"\nAnswer:\n{response.answer}\n")
    print("-" * 50)
    
    if response.quantitative_metrics:
        qm = response.quantitative_metrics
        print("\nQuantitative Metrics Found:")
        print(f"- Coverage: {qm.topic_coverage}")
        print(f"- Claims: {qm.claim_stats}")
        print(f"- Sentiment: {qm.sentiment_distribution}")
        print(f"- Authorities: {len(qm.authorities)}")
        print(f"- Contradictions: {len(qm.contradictions)}")
        print(f"- Taxonomy: {qm.taxonomy_context}")
        print(f"- Heatmap Boost Applied: {qm.heatmap_boost_applied}")
    else:
        print("\nNo quantitative metrics returned.")

    print(f"\nLatency: {response.latency_ms:.0f}ms")
    print(f"Confidence: {response.confidence.overall if response.confidence else 0.0:.2f}")

if __name__ == "__main__":
    test_quantitative_rag()
