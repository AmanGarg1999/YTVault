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
from src.ui.views import (
    dashboard, ingestion_hub, pipeline_center, intelligence_lab,
    explorer, guest_intel, export_center,
    logs_monitor, data_management, reject_review,
    transcript_viewer, performance_metrics, comparative_lab,
    blueprint_center, research_agent_view, monitoring_hub,
    global_search, research_chat
)
from src.ingestion.discovery import validate_target_availability

from src.ui.components.ui_helpers import action_confirmation_dialog, failure_confirmation_dialog

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="KnowledgeVault Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS - Professional Design System (UI/UX Pro Max)
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* =====================================================================
       INTELLIGENCE CORE - THEME DEFINITIONS
       ===================================================================== */
    
    :root {
        /* Active Theme Variables - Injected by Intelligence Orchestrator */
        --bg-deep: {"#030712" if st.session_state.get("theme") == "dark" else "#f8fafc"};
        --bg-nebula: {"radial-gradient(circle at 0% 0%, #0f172a 0%, #030712 50%, #020617 100%)" if st.session_state.get("theme") == "dark" else "radial-gradient(circle at 0% 0%, #f1f5f9 0%, #f8fafc 100%)"};
        
        --primary-glow: {"#6366f1" if st.session_state.get("theme") == "dark" else "#4f46e1"};
        --primary-active: {"#4f46e1" if st.session_state.get("theme") == "dark" else "#3730a3"};
        --accent-glow: {"#22d3ee" if st.session_state.get("theme") == "dark" else "#0891b2"};
        
        --glass-bg: {"rgba(15, 23, 42, 0.4)" if st.session_state.get("theme") == "dark" else "rgba(255, 255, 255, 0.7)"};
        --glass-border: {"rgba(255, 255, 255, 0.05)" if st.session_state.get("theme") == "dark" else "rgba(0, 0, 0, 0.08)"};
        --glass-active: {"rgba(99, 102, 241, 0.1)" if st.session_state.get("theme") == "dark" else "rgba(79, 70, 225, 0.05)"};
        
        --success-glow: {"#10b981" if st.session_state.get("theme") == "dark" else "#059669"};
        --warning-glow: {"#f59e0b" if st.session_state.get("theme") == "dark" else "#d97706"};
        --error-glow: {"#ef4444" if st.session_state.get("theme") == "dark" else "#dc2626"};
        
        --text-stellar: {"#f8fafc" if st.session_state.get("theme") == "dark" else "#0f172a"};
        --text-muted: {"#94a3b8" if st.session_state.get("theme") == "dark" else "#475569"};
    }
    
    /* =====================================================================
       GLOBAL STYLES & TYPOGRAPHY
       ===================================================================== */
    
    .stApp {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 14px;
        color: var(--text-stellar);
        background: var(--bg-nebula) !important;
    }
    
    h1, h2, h3, h4 { 
        font-family: 'Plus Jakarta Sans', sans-serif; 
        letter-spacing: -0.025em;
    }
    
    h1 { font-size: 2.75rem; font-weight: 800; color: var(--text-stellar); margin-bottom: 0.5rem; }
    h2 { font-size: 2rem; font-weight: 700; color: var(--text-stellar); }
    h3 { font-size: 1.5rem; font-weight: 650; color: var(--text-stellar); }
    
    p { line-height: 1.7; color: var(--text-muted); font-size: 1rem; }
    
    /* =====================================================================
       ENHANCED COMPONENTS - GLASSMORPHISM
       ===================================================================== */
    
    /* Metric Cards */
    .metric-card {
        background: var(--glass-bg);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border);
        border-radius: 20px;
        padding: 1.75rem;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .metric-card:hover {
        background: rgba(30, 41, 59, 0.6);
        border-color: rgba(99, 102, 241, 0.4);
        transform: translateY(-6px);
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3), 0 0 15px rgba(99, 102, 241, 0.1);
    }
    
    .metric-card::after {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.05) 0%, transparent 70%);
        opacity: 0;
        transition: opacity 0.4s ease;
        pointer-events: none;
    }
    
    .metric-card:hover::after {
        opacity: 1;
    }
    
    .metric-card .value {
        font-family: 'Outfit', sans-serif;
        font-size: 1.85rem;
        font-weight: 800;
        color: var(--text-stellar);
        margin-bottom: 0.15rem;
        letter-spacing: -0.04em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .metric-card .label {
        font-size: 0.75rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 700;
    }
    
    /* Sidebar Navigation */
    .stSidebar {
        background-color: var(--bg-deep) !important;
        border-right: 1px solid var(--glass-border) !important;
    }
    
    .stSidebar [data-testid="stSidebarNav"] {
        background-color: transparent !important;
    }
    
    /* System Pulse Animation */
    @keyframes pulse-glow {
        0% { opacity: 0.5; box-shadow: 0 0 5px rgba(99, 102, 241, 0.2); }
        50% { opacity: 1; box-shadow: 0 0 20px rgba(99, 102, 241, 0.5); }
        100% { opacity: 0.5; box-shadow: 0 0 5px rgba(99, 102, 241, 0.2); }
    }
    
    .status-pulse {
        width: 8px;
        height: 8px;
        background: var(--primary-glow);
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse-glow 2s infinite ease-in-out;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 14px;
        background: linear-gradient(135deg, var(--primary-glow) 0%, var(--primary-active) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: white;
        font-weight: 700;
        font-size: 1rem;
        padding: 0.75rem 1.75rem;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        text-transform: none;
        letter-spacing: 0.02em;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        white-space: nowrap;
        min-width: 120px;
    }
    
    .stButton > button:hover {
        box-shadow: 0 0 35px rgba(99, 102, 241, 0.5);
        transform: translateY(-3px);
        border-color: rgba(255, 255, 255, 0.3);
        filter: brightness(1.15);
    }
    
    .stButton > button:active {
        transform: translateY(1px) scale(0.96);
        box-shadow: inset 0 4px 10px rgba(0, 0, 0, 0.4);
        filter: brightness(0.9);
        transition: all 0.1s ease;
    }

    .stButton > button:focus:not(:active) {
        border-color: var(--accent-glow);
        box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.3);
    }

    /* Secondary Buttons */
    div[data-testid="stButton"] button[kind="secondary"] {
        background: rgba(15, 23, 42, 0.9) !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        backdrop-filter: blur(12px) !important;
        color: #f8fafc !important;
    }
    
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background: var(--glass-active);
        border-color: var(--primary-glow);
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
    }

    div[data-testid="stButton"] button[kind="secondary"]:active {
        background: rgba(99, 102, 241, 0.2);
        transform: translateY(1px) scale(0.97);
        box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3);
    }

    /* Danger Button Variant */
    div.danger-btn button {
        background: rgba(239, 68, 68, 0.15) !important;
        border: 1px solid rgba(239, 68, 68, 0.4) !important;
        color: #fca5a5 !important;
    }
    
    div.danger-btn button:hover {
        background: rgba(239, 68, 68, 0.4) !important;
        border-color: #ef4444 !important;
        color: white !important;
        box-shadow: 0 0 25px rgba(239, 68, 68, 0.3) !important;
    }

    /* Command Bar Focal Point */
    .command-bar-container {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 16px;
        padding: 0.5rem 1rem;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
    }

    /* Inputs */
    .stTextInput input {
        background-color: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        color: var(--text-stellar) !important;
        font-size: 1rem !important;
        padding: 0.75rem 1rem !important;
    }
    
    .stButton > button:focus:visible {
        border-color: var(--accent-glow) !important;
        box-shadow: 0 0 0 2px var(--bg-deep), 0 0 0 4px var(--accent-glow) !important;
        outline: none !important;
    }

    /* Card Focus States */
    .metric-card:focus-within, .glass-card:focus-within {
        border-color: var(--primary-glow) !important;
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.2) !important;
    }

    /* Accessibility */
    *:focus-visible {
        outline: 2px solid var(--primary-glow) !important;
        outline-offset: 2px !important;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
    }
    ::-webkit-scrollbar-track {
        background: #020617;
    }
    ::-webkit-scrollbar-thumb {
        background: #1e293b;
        border: 2px solid #020617;
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #334155;
    }
    /* Standardize Streamlit Link Buttons to use Nebula Glassmorphism */
    div[data-testid="stLinkButton"] a {
        border-radius: 14px !important;
        background: linear-gradient(135deg, var(--primary-glow) 0%, var(--primary-active) 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        font-weight: 700 !important;
        padding: 0.75rem 1.75rem !important;
        font-size: 1rem !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        text-transform: none !important;
        letter-spacing: 0.02em !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
        text-decoration: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    div[data-testid="stLinkButton"] a:hover {
        box-shadow: 0 0 35px rgba(99, 102, 241, 0.5) !important;
        transform: translateY(-3px) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
        filter: brightness(1.15) !important;
    }

    div[data-testid="stLinkButton"] a:active {
        transform: translateY(1px) scale(0.96) !important;
        box-shadow: inset 0 4px 10px rgba(0, 0, 0, 0.4) !important;
        filter: brightness(0.9) !important;
    }
    
    /* Hide Redundant Streamlit Sidebar Navigation */
    div[data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* =====================================================================
       RESEARCH CHAL HUB - MESSAGING STYLES
       ===================================================================== */
    
    /* Standardize Chat Messages */
    div[data-testid="stChatMessage"] {
        background: rgba(15, 23, 42, 0.3) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 20px !important;
        padding: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2) !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
    }

    /* User Message Specifics - Force Right Alignment */
    div[data-testid="stChatMessage"][data-testid="stChatMessageUser"] {
        background: rgba(99, 102, 241, 0.1) !important;
        border-color: rgba(99, 102, 241, 0.3) !important;
        margin-left: auto !important;
        width:  fit-content !important;
        max-width: 80% !important;
    }

    /* Assistant Message Specifics - Width Control */
    div[data-testid="stChatMessage"] {
        width: fit-content !important;
        max-width: 90% !important;
    }

    /* Avatar Icons */
    div[data-testid="stChatMessageAvatar"] {
        background-color: var(--primary-glow) !important;
        border-radius: 12px !important;
    }

    /* Chat Input FIXED Aesthetic - Removal of White Footer */
    footer {display: none !important;}
    header {display: none !important;}
    
    div[data-testid="stBottom"] {
        background-color: transparent !important;
    }

    div[data-testid="stBottomBlockContainer"] {
        background-color: var(--bg-deep) !important;
        border-top: 1px solid var(--glass-border) !important;
        padding-top: 1rem !important;
    }

    div[data-testid="stChatInput"] {
        background-color: transparent !important;
        padding: 0 !important;
    }

    div[data-testid="stChatInput"] textarea {
        background-color: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 14px !important;
        color: white !important;
    }

    /* Discovery Chips */
    .discovery-chip {
        display: inline-block;
        padding: 0.5rem 1rem;
        background: rgba(99, 102, 241, 0.15);
        color: #818cf8;
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 30px;
        font-size: 0.85rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        margin: 0.25rem;
        white-space: nowrap;
    }

    .discovery-chip:hover {
        background: rgba(99, 102, 241, 0.3);
        border-color: var(--primary-glow);
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2);
        color: white;
    }

    /* Session List Items (Sidebar) */
    .session-item {
        border-radius: 12px;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        transition: background 0.2s ease;
    }
    .session-active {
        background: var(--glass-active);
        border-left: 3px solid var(--primary-glow);
    }
</style>
<script>
    (function() {
        const navItems = [
            "Dashboard", "Ingestion Hub", "Monitoring Hub", "Review Center",
            "Intelligence Lab", "Research Agent", "Research Chat", "Global Search", "Settings"
        ];
        
        function tryNavigate(targetPage) {
            const docs = [document];
            try { if (window.parent && window.parent.document) docs.push(window.parent.document); } catch(e) {}
            try { if (window.top && window.top.document) docs.push(window.top.document); } catch(e) {}
            
            for (const doc of docs) {
                const buttons = Array.from(doc.querySelectorAll('button'));
                const btn = buttons.find(b => {
                    const text = b.innerText.replace(/\s+/g,' ').trim().toLowerCase();
                    return text === targetPage.toLowerCase();
                });
                if (btn) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }

        const handler = (e) => {
            if (e.altKey && e.key >= '1' && e.key <= '9') {
                const index = parseInt(e.key) - 1;
                if (index < navItems.length) {
                    if (tryNavigate(navItems[index])) {
                        e.preventDefault();
                    }
                }
            }
        };

        window.addEventListener('keydown', handler);
        try { if (window.parent) window.parent.addEventListener('keydown', handler); } catch(e) {}
    })();
</script>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------

@st.cache_resource
def init_db(cache_key="nebula_v2_hardened_final_purge"):
    """Initialize database connection (cached across reruns)."""
    # FORCE RELOAD: If we changed the code, the class definition in memory might be stale.
    # We use a new cache_key and ensure the imports are fresh.
    ensure_data_dirs()
    settings = get_settings()
    
    from src.storage.sqlite_store import SQLiteStore
    logger.info(f"System: Deep cache re-initialization triggered (key: {cache_key})")
    return SQLiteStore(settings["sqlite"]["path"])


@st.cache_resource
def init_vs():
    """Initialize vector store (cached across reruns)."""
    try:
        from src.storage.vector_store import VectorStore
        return VectorStore()
    except Exception as e:
        logger.error(f"Failed to initialize VectorStore: {e}")
        return None


# ---------------------------------------------------------------------------
# Service Health Checks
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def check_service_health():
    """Check health of critical services (cached for 60 seconds)."""
    health_status = {
        "database": False,
        "ollama": False,
        "vector_store": False,
        "errors": []
    }
    
    # Check Database
    try:
        settings = get_settings()
        import sqlite3
        conn = sqlite3.connect(settings["sqlite"]["path"], timeout=5)
        conn.execute("SELECT 1")
        conn.close()
        health_status["database"] = True
    except Exception as e:
        health_status["errors"].append(f"Database: {str(e)[:50]}")
    
    # Check Ollama Service
    try:
        import requests
        settings = get_settings()
        ollama_host = settings["ollama"]["host"]
        resp = requests.get(f"{ollama_host}/api/tags", timeout=3)
        if resp.status_code == 200:
            health_status["ollama"] = True
    except Exception as e:
        health_status["errors"].append(f"Ollama: Service unavailable")

    # Check Vector Store (Direct check if instance exists and is ready)
    # Note: We rely on the global 'vs' instance defined later
    return health_status


# ---------------------------------------------------------------------------
# Background Pipeline Registry
# ---------------------------------------------------------------------------

if "active_threads" not in st.session_state:
    st.session_state.active_threads = {}

# Global (module-level) registry to keep threads alive even if session state is cleared
if not hasattr(st, "_global_orchestrators"):
    st._global_orchestrators = {}



def run_pipeline_background(url: str, db: SQLiteStore, scan_id: Optional[str] = None, force_metadata_refresh: bool = False):
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
                current_scan_id = orchestrator.run(url, force_metadata_refresh=force_metadata_refresh)
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


def run_bulk_pipeline_background(urls: list[str], db: SQLiteStore, force_metadata_refresh: bool = False):
    """Run multiple pipelines sequentially in a single background thread."""
    from src.pipeline.orchestrator import PipelineOrchestrator
    import threading
    import time
    
    unique_id = f"bulk_{int(time.time())}"
    
    def target():
        thread_db = None
        orchestrator = None
        try:
            settings = get_settings()
            thread_db = SQLiteStore(settings["sqlite"]["path"])
            orchestrator = PipelineOrchestrator()
            
            # Set callbacks to ensure progress is logged to DB
            orchestrator.set_callbacks(
                on_status=lambda msg: orchestrator.db.log_pipeline_event(
                    level="INFO", message=msg, stage="BULK"
                )
            )
            
            for i, url in enumerate(urls):
                logger.info(f"Bulk start {i+1}/{len(urls)}: {url}")
                orchestrator.run(url, force_metadata_refresh=force_metadata_refresh)
                # Sync counts after each channel in bulk
                orchestrator.db.sync_channel_video_counts()
                
        except Exception as e:
            logger.error(f"Bulk background pipeline failed: {e}", exc_info=True)
        finally:
            if unique_id in st._global_orchestrators:
                del st._global_orchestrators[unique_id]
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


def run_repair_background():
    """Run the comprehensive vault health repair in a background thread."""
    from src.pipeline.orchestrator import PipelineOrchestrator
    import threading
    import time
    
    unique_id = f"repair_{int(time.time())}"
    
    def target():
        thread_db = None
        orchestrator = None
        try:
            settings = get_settings()
            thread_db = SQLiteStore(settings["sqlite"]["path"])
            orchestrator = PipelineOrchestrator()
            
            def update_progress(current, total):
                if unique_id in st._global_orchestrators:
                    st._global_orchestrators[unique_id]["progress_current"] = current
                    st._global_orchestrators[unique_id]["progress_total"] = total
            
            orchestrator.set_callbacks(on_progress=update_progress)
            orchestrator.repair_vault_health()
        except Exception as e:
            logger.error(f"Background repair failed: {e}", exc_info=True)
        finally:
            if unique_id in st._global_orchestrators:
                del st._global_orchestrators[unique_id]
            if orchestrator:
                orchestrator.close()
            if thread_db:
                thread_db.close()

    thread = threading.Thread(target=target, daemon=True)
    st._global_orchestrators[unique_id] = {
        "thread": thread,
        "orchestrator": None,
        "start_time": time.time(),
        "progress_current": 0,
        "progress_total": 0,
        "type": "repair"
    }
    thread.start()
    return unique_id


def get_vault_diagnostics(db):
    """Get a summary of vault health and gaps."""
    total_accepted = db.conn.execute(
        "SELECT COUNT(*) FROM videos WHERE triage_status = 'ACCEPTED'"
    ).fetchone()[0]
    
    if total_accepted == 0:
        return {
            "total": 0, "transcripts": 0, "summaries": 0, "heatmaps": 0,
            "pct_transcripts": 100, "pct_summaries": 100, "pct_heatmaps": 100
        }
        
    missing_tx = len(db.get_videos_missing_transcripts())
    missing_sm = len(db.get_videos_missing_summaries())
    missing_hm = len(db.get_videos_missing_heatmaps())
    
    return {
        "total": total_accepted,
        "missing_transcripts": missing_tx,
        "missing_summaries": missing_sm,
        "missing_heatmaps": missing_hm,
        "pct_transcripts": int(((total_accepted - missing_tx) / total_accepted) * 100),
        "pct_summaries": int(((total_accepted - missing_sm) / total_accepted) * 100),
        "pct_heatmaps": int(((total_accepted - missing_hm) / total_accepted) * 100),
    }


db = init_db(cache_key="nebula_v3_production_ready")
vs = init_vs()

# Check service health and display status
health = check_service_health()


# ---------------------------------------------------------------------------
# Sidebar Navigation - Enhanced with Professional Branding
# ---------------------------------------------------------------------------

# Sidebar Header with Branding
st.sidebar.markdown("""
<div style="padding: 1.5rem; background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(34, 211, 238, 0.05)); border-radius: 16px; border: 1px solid rgba(99, 102, 241, 0.2); margin-bottom: 2rem; text-align: left; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
    <h1 style="margin: 0; font-size: 1.5rem; font-weight: 800; color: white; letter-spacing: -0.03em;">KnowledgeVault</h1>
    <p style="margin: 0.25rem 0 0; font-size: 0.7rem; color: var(--accent-glow); text-transform: uppercase; letter-spacing: 0.15em; font-weight: 700; opacity: 0.9;">Research Intelligence OS</p>
</div>
""", unsafe_allow_html=True)

# Service Health Status
with st.sidebar:
    cols = st.columns(3)
    with cols[0]:
        if health["database"]:
            st.markdown("<div style='text-align:center; color:#10b981; font-weight:700; font-size:0.7rem;'>DB</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align:center; color:#ef4444; font-weight:700; font-size:0.7rem;'>DB</div>", unsafe_allow_html=True)
    
    with cols[1]:
        if health["ollama"]:
            st.markdown("<div style='text-align:center; color:#10b981; font-weight:700; font-size:0.7rem;'>LLM</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align:center; color:#f59e0b; font-weight:700; font-size:0.7rem;'>LLM</div>", unsafe_allow_html=True)
            
    with cols[2]:
        if vs and hasattr(vs, 'is_ready') and vs.is_ready():
            st.markdown("<div style='text-align:center; color:#10b981; font-weight:700; font-size:0.7rem;'>VEC</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align:center; color:#ef4444; font-weight:700; font-size:0.7rem;'>VEC</div>", unsafe_allow_html=True)
    
    # Theme Switcher
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
    theme_choice = st.toggle(
        "Stellar Lab Theme", 
        value=st.session_state.get("theme", "dark") == "light",
        help="Toggle between Void Nebula (Dark) and Stellar Lab (Light) themes."
    )
    new_theme = "light" if theme_choice else "dark"
    if new_theme != st.session_state.get("theme", "dark"):
        st.session_state.theme = new_theme
        st.rerun()

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    # Categorized Navigation Structure
    NAV_STRUCTURE = {
        "Intelligence Hub": [
            "Dashboard", 
            "Global Search",
            "Blueprint Center",
            "Ingestion Hub",
        ],
        "Analysis Core": [
            "Research Agent",
            "Research Chat",
            "Intelligence Lab",
            "Comparative Lab",
            "Transcripts", 
        ],
        "System Health": [
            "Monitoring Hub",
            "Performance",
            "Review Center",
            "Pipeline Center",
            "Export & Integration",
            "Settings"
        ]
    }

    selected_page = st.session_state.get("current_page", "Dashboard")
    
    for category, items in NAV_STRUCTURE.items():
        st.markdown(f"<p style='font-size:0.75rem; color:#475569; font-weight:800; margin-top:1.5rem; margin-bottom:0.5rem;'>{category.upper()}</p>", unsafe_allow_html=True)
        for item in items:
            is_active = (item == selected_page)
            if st.sidebar.button(
                item, 
                key=f"nav_{item}", 
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.current_page = item
                st.rerun()

    # Research Chat History Integration
    if st.session_state.get("current_page") == "Research Chat":
        st.markdown("---")
        st.markdown("<p style='font-size:0.75rem; color:#475569; font-weight:800; margin-bottom:0.5rem;'>INTEL SESSIONS</p>", unsafe_allow_html=True)
        
        if st.sidebar.button("➕ New Session", use_container_width=True, type="primary", key="new_chat_btn_sidebar"):
            st.session_state.chat_session_id = None
            st.session_state.chat_messages = []
            st.rerun()

        sessions = db.get_chat_sessions(limit=15)
        for s in sessions:
            is_active = st.session_state.get("chat_session_id") == s.session_id
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                if st.button(f"📄 {s.name[:18]}...", key=f"hist_{s.session_id}", use_container_width=True, type="primary" if is_active else "secondary"):
                    st.session_state.chat_session_id = s.session_id
                    st.rerun()
            with col2:
                st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
                if st.button("❌", key=f"del_h_{s.session_id}", use_container_width=True):
                    db.delete_chat_session(s.session_id)
                    if is_active:
                        st.session_state.chat_session_id = None
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


# Flatten for radio component
nav_options = []
for category, items in NAV_STRUCTURE.items():
    nav_options.extend(items)

# Support programmatic navigation
if "navigate" in st.session_state:
    target_page = st.session_state.pop("navigate")
    # Handle flat page names
    if target_page in nav_options:
        st.session_state.current_page = target_page

page = st.session_state.get("current_page", "Dashboard")


# Sidebar Footer - Active Scans Tray & Help
st.sidebar.markdown("---")
with st.sidebar:
    active_scans = db.get_active_scans()
    st.markdown("<p style='font-size:0.75rem; color:#475569; font-weight:800; margin-top:1.5rem; margin-bottom:0.5rem;'>TASK QUEUE MONITOR</p>", unsafe_allow_html=True)
    if active_scans:
        with st.expander(f"⚙️ {len(active_scans)} Active Scans", expanded=True):
            for scan in active_scans[:3]:
                progress = (scan.total_processed / max(scan.total_discovered, 1))
                safe_progress = max(0.0, min(1.0, progress))
                display_name = scan.channel_name if scan.channel_name else f"Scan {scan.scan_id[-4:]}"
                st.caption(f"{display_name}")
                st.progress(safe_progress, text=f"{safe_progress:.0%}")
            if len(active_scans) > 3:
                st.caption(f"+ {len(active_scans) - 3} more...")
    else:
        st.info("System Engine Idling. No active tasks.")

    # Footer links correctly pointing to help/docs
    st.markdown(f"<div style='margin-top:2rem; border-top:1px solid rgba(255,255,255,0.05); padding-top:1rem;'>", unsafe_allow_html=True)
    if st.button("User Documentation", key="nav_btn_docs", use_container_width=True):
        st.session_state.navigate = "Blueprint Center"
        st.rerun()
    if st.button("System Performance", key="nav_btn_perf", use_container_width=True):
        st.session_state.navigate = "Performance"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="padding: 1rem; border-top: 1px solid rgba(14, 165, 233, 0.1); margin-top: 1rem; font-size: 0.8rem; color: #888; text-align: center;">
    <p style="margin: 0; line-height: 1.5;">
        <a href='https://github.com/AmanGarg1999/YTVault' style='color: #0ea5e9; text-decoration: none;'>Documentation</a> • 
        <a href='mailto:support@knowledgevault.local' style='color: #0ea5e9; text-decoration: none;'>Support</a>
    </p>
    <p style="margin: 0.5rem 0 0; opacity: 0.7;">v1.1 • Architecture Overhaul</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page Routing
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Global Command Bar & Rendering
# ---------------------------------------------------------------------------

# Global Command Bar & Rendering (Contextual Visibility)
if page in ["Dashboard", "Global Search"]:
    with st.container():
        col_cmd, col_btn = st.columns([5, 1])
        with col_cmd:
            harvest_url = st.text_input(
                "Global Harvest", 
                placeholder="Paste a YouTube URL here to start a research harvest...",
                label_visibility="collapsed",
                key="global_harvest_input"
            )
        with col_btn:
            if st.button("Harvest", type="primary", use_container_width=True, key="global_harvest_btn"):
                if not harvest_url:
                    st.toast("Input Required: Please enter a target YouTube URL.", icon="⚠️")
                    st.error("The harvest engine requires a target YouTube URL to begin ingestion.")
                else:
                    with st.spinner("Analyzing target intelligence..."):
                        try:
                            # Basic validation or initial check
                            if "youtube.com" not in harvest_url and "youtu.be" not in harvest_url:
                                raise ValueError("Invalid YouTube URL provided. Must be a youtube.com or youtu.be link.")
                            
                            # Pre-harvest availability check
                            validate_target_availability(harvest_url)
                                
                            run_pipeline_background(harvest_url, db)
                            action_confirmation_dialog(
                                "Harvest Initialized",
                                f"Intelligence gathering has started for {harvest_url[:40]}...",
                                icon="✦"
                            )
                        except Exception as e:
                            failure_confirmation_dialog(
                                "Harvest Failed to Initialize",
                                str(e),
                                retry_callback=lambda: run_pipeline_background(harvest_url, db),
                                queue_callback=lambda: db.add_to_user_queue("URL", harvest_url, str(e))
                            )
else:
    # Spacer to ensure consistent vertical alignment when command bar is absent
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

PAGE_MAP = {
    "Dashboard": lambda: dashboard.render(db),
    "Ingestion Hub": lambda: ingestion_hub.render(db, run_pipeline_background, run_bulk_pipeline_background),
    "Pipeline Center": lambda: pipeline_center.render(db, run_pipeline_background, run_repair_background, get_vault_diagnostics),
    "Review Center": lambda: reject_review.render(db),
    "Performance": lambda: performance_metrics.render(),
    "Intelligence Lab": lambda: intelligence_lab.render(db, run_repair_background),
    "Research Agent": lambda: research_agent_view.render(db),
    "Research Chat": lambda: research_chat.render_research_chat(db),
    "Global Search": lambda: global_search.render_global_search(db, vs),
    "Comparative Lab": lambda: comparative_lab.render(db, vs),
    "Blueprint Center": lambda: blueprint_center.render(db),
    "Transcripts": lambda: transcript_viewer.render(db),
    "Export & Integration": lambda: export_center.render(db),
    "Monitoring Hub": lambda: monitoring_hub.render(db),
    "Settings": lambda: data_management.render(db, run_repair_background, get_vault_diagnostics),
}

PAGE_MAP[page]()
# Reload trigger
