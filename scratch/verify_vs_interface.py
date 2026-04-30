import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.vector_store import VectorStore, OllamaEmbeddingFunction

def test_vector_store_interface():
    print("--- Testing VectorStore Interface ---")
    vs = VectorStore()
    if not vs.is_ready():
        print("VectorStore not ready (Ollama might be down), but we can still check the object methods.")
    
    embed_fn = vs.embedding_fn
    print(f"Embedding function: {type(embed_fn).__name__}")
    
    # Check for methods
    methods = ["embed_query", "embed_documents", "__call__"]
    for m in methods:
        has_m = hasattr(embed_fn, m)
        print(f"Has {m}: {has_m}")
        if not has_m:
            print(f"ERROR: Missing {m} method!")
            return False
            
    print("Interface check PASSED.")
    return True

if __name__ == "__main__":
    test_vector_store_interface()
