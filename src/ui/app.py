"""
knowledgeVault-YT — Streamlit Command Center

Main entry point for the Streamlit UI. Handles page configuration,
CSS theming, sidebar navigation, and routes to page modules.
"""

import sys
from pathlib import Path

import streamlit as st
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ensure_data_dirs, get_settings
from src.storage.sqlite_store import SQLiteStore

# Page modules
from src.ui.pages import (
    dashboard, harvest, ambiguity, research,
    guest_intel, explorer, pipeline_monitor, export_center,
    logs_monitor, pipeline_control, data_management,
)

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="knowledgeVault-YT",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.95rem; }

    .metric-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid rgba(102, 126, 234, 0.3);
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
    }
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    .metric-card .label {
        font-size: 0.8rem;
        color: #a0a0b0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .stSidebar > div:first-child {
        background: linear-gradient(180deg, #0f0f23, #1a1a2e);
    }
    .sidebar-nav-item {
        padding: 0.6rem 1rem;
        margin: 0.2rem 0;
        border-radius: 8px;
        cursor: pointer;
    }
    .sidebar-nav-item:hover {
        background: rgba(102, 126, 234, 0.15);
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------

@st.cache_resource
def init_db():
    """Initialize database connection (cached across reruns)."""
    ensure_data_dirs()
    settings = get_settings()
    return SQLiteStore(settings["sqlite"]["path"])


# ---------------------------------------------------------------------------
# Background Pipeline Registry
# ---------------------------------------------------------------------------

if "active_threads" not in st.session_state:
    st.session_state.active_threads = {}

# Global (module-level) registry to keep threads alive even if session state is cleared
if not hasattr(st, "_global_orchestrators"):
    st._global_orchestrators = {}


def run_pipeline_background(url: str, db: SQLiteStore, scan_id: Optional[str] = None):
    """Run the pipeline in a background thread.
    
    IMPORTANT: Creates a fresh SQLiteStore for the background thread since 
    SQLite connections are thread-specific and cannot be shared across threads.
    """
    from src.pipeline.orchestrator import PipelineOrchestrator
    import threading

    unique_id = scan_id or url

    def target():
        # Create a fresh SQLiteStore in this thread - cannot reuse the one from main thread
        thread_db = None
        orchestrator = None
        current_scan_id = scan_id
        try:
            settings = get_settings()
            thread_db = SQLiteStore(settings["sqlite"]["path"])
            orchestrator = PipelineOrchestrator()
            
            if scan_id:
                orchestrator.resume(scan_id)
            else:
                current_scan_id = orchestrator.run(url)
                if current_scan_id and url in st._global_orchestrators:
                    st._global_orchestrators[current_scan_id] = st._global_orchestrators.pop(url)
        except Exception as e:
            logger.error(f"Background pipeline failed for {unique_id}: {e}", exc_info=True)
        finally:
            if unique_id in st._global_orchestrators:
                del st._global_orchestrators[unique_id]
            if current_scan_id and current_scan_id in st._global_orchestrators:
                del st._global_orchestrators[current_scan_id]
            if orchestrator:
                orchestrator.close()
            if thread_db:
                thread_db.close()

    thread = threading.Thread(target=target, daemon=True)
    st._global_orchestrators[unique_id] = {
        "thread": thread,
        "orchestrator": None,
        "start_time": time.time(),
    }
    thread.start()
    return unique_id


db = init_db()


# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------

st.sidebar.markdown("## 🧠 knowledgeVault-YT")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Dashboard", "🌾 Harvest Manager", "📋 Ambiguity Queue",
     "🔍 Research Console", "👤 Guest Intelligence", "🧠 Knowledge Explorer",
     "📊 Pipeline Monitor", "📤 Export Center", "📋 Logs & Activity",
     "🎮 Pipeline Control", "🗑️ Data Management"],
    label_visibility="collapsed",
)


# ---------------------------------------------------------------------------
# Page Routing
# ---------------------------------------------------------------------------

PAGE_MAP = {
    "🏠 Dashboard": lambda: dashboard.render(db),
    "🌾 Harvest Manager": lambda: harvest.render(db, run_pipeline_background),
    "📋 Ambiguity Queue": lambda: ambiguity.render(db),
    "🔍 Research Console": lambda: research.render(db),
    "👤 Guest Intelligence": lambda: guest_intel.render(db),
    "🧠 Knowledge Explorer": lambda: explorer.render(db),
    "📊 Pipeline Monitor": lambda: pipeline_monitor.render(db, run_pipeline_background),
    "📤 Export Center": lambda: export_center.render(db),
    "📋 Logs & Activity": lambda: logs_monitor.render(db),
    "🎮 Pipeline Control": lambda: pipeline_control.render(db, run_pipeline_background),
    "🗑️ Data Management": lambda: data_management.render(db),
}

PAGE_MAP[page]()
