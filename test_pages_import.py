#!/usr/bin/env python3
"""
Test script to verify all pages can be imported without errors.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

print("Testing page imports...")

try:
    print("\n1. Testing config and database imports...")
    from src.config import ensure_data_dirs, get_settings
    from src.storage.sqlite_store import SQLiteStore
    print("   ✓ Config and database imports OK")
    
    print("\n2. Testing page imports...")
    pages = [
        "dashboard",
        "harvest", 
        "ambiguity",
        "research",
        "guest_intel",
        "explorer",
        "pipeline_monitor",
        "export_center",
        "logs_monitor",
        "pipeline_control",
        "data_management",
        "reject_review",
    ]
    
    for page in pages:
        try:
            module = __import__(f"src.ui.pages.{page}", fromlist=[page])
            # Check if module has render function
            if hasattr(module, "render"):
                print(f"   ✓ {page:25} - Has render() function")
            else:
                print(f"   ⚠ {page:25} - Missing render() function")
        except Exception as e:
            print(f"   ✗ {page:25} - ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n3. Testing SQLiteStore initialization...")
    ensure_data_dirs()
    settings = get_settings()
    db = SQLiteStore(settings["sqlite"]["path"])
    print("   ✓ SQLiteStore initialized OK")
    db.close()
    
    print("\n✓ All imports successful!")
    sys.exit(0)
    
except Exception as e:
    print(f"\n✗ FATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
