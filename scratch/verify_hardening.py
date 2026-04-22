
import threading
import time
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.vector_store import VectorStore
from src.storage.graph_store import GraphStore
from src.storage.sqlite_store import SQLiteStore
from src.intelligence.entity_resolver import EntityResolver

def test_singleton_thread_safety(store_class, name):
    print(f"Testing thread-safety for {name}...")
    instances = []
    def get_instance():
        instances.append(store_class())
    
    threads = [threading.Thread(target=get_instance) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    unique_ids = {id(inst) for inst in instances}
    if len(unique_ids) == 1:
        print(f"✅ {name} Singleton is thread-safe.")
    else:
        print(f"❌ {name} Singleton FAILED: {len(unique_ids)} instances created.")

def test_entity_sync():
    print("Testing Entity Sync (SQLite -> Neo4j)...")
    db = SQLiteStore(":memory:")
    # Initialize schema
    with open("src/storage/sqlite_store.py", "r") as f:
        # This is a bit hacky, but better to use real schema if possible
        # For simplicity, we just check if EntityResolver calls the mocks
        pass
    
    # Mock GraphStore
    class MockGraph:
        def __init__(self):
            self.deleted = []
            self.merged = []
        def delete_guest(self, name):
            self.deleted.append(name)
        def merge_guests(self, s, m):
            self.merged.append((s, m))
    
    graph = MockGraph()
    resolver = EntityResolver(db, graph)
    
    # Test Noise Purge Sync Call
    from src.intelligence.entity_resolver import NOISE_GUEST_BLACKLIST
    noise_name = list(NOISE_GUEST_BLACKLIST)[0]
    
    # Manually insert noise into SQLite (mocking the table presence)
    db.execute("CREATE TABLE IF NOT EXISTS guests (guest_id INTEGER PRIMARY KEY, canonical_name TEXT, mention_count INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS guest_appearances (guest_id INTEGER)")
    db.execute("INSERT INTO guests (canonical_name, mention_count) VALUES (?, 1)", [noise_name])
    
    resolver.purge_noise_entities()
    if noise_name in graph.deleted:
        print(f"✅ Noise Purge Sync successful for: {noise_name}")
    else:
        print(f"❌ Noise Purge Sync FAILED")

def test_vector_counter_perf():
    print("Testing Vector Counter Optimization...")
    vs = VectorStore()
    if not vs.is_ready():
        print("Skipping Vector Store test (not ready)")
        return
    
    start = time.time()
    count = vs.count_unique_videos()
    duration = time.time() - start
    print(f"✅ Count unique videos: {count} (Time: {duration:.4f}s)")

if __name__ == "__main__":
    test_singleton_thread_safety(VectorStore, "VectorStore")
    test_singleton_thread_safety(GraphStore, "GraphStore")
    test_entity_sync()
    test_vector_counter_perf()
