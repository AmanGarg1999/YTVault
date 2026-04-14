import sys
import os
from pathlib import Path

# Fix path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.discovery import validate_target_availability

print("--- Testing Valid URL ---")
try:
    validate_target_availability("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print("✅ Valid URL passed")
except Exception as e:
    print(f"❌ Valid URL failed: {e}")

print("\n--- Testing Invalid URL ---")
try:
    validate_target_availability("https://www.youtube.com/watch?v=invalid_id_000")
    print("❌ Invalid URL passed (Expected Failure)")
except Exception as e:
    print(f"✅ Invalid URL correctly caught: {e}")
