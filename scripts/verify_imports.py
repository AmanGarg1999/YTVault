import sys
from pathlib import Path
sys.path.append(str(Path.cwd()))

try:
    print("Checking view imports...")
    from src.ui.views import (
        intelligence_center, intelligence_studio, ops_dashboard,
        research_chat, transcript_viewer, harvest,
        blueprint_center, export_center, data_management,
        performance_metrics
    )
    print("✅ All views imported successfully!")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
