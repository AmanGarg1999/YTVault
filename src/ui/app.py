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
    topic_explorer, blueprint_center, research_agent_view
)

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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* =====================================================================
       MODERN DESIGN SYSTEM - INDIGO & SLATE
       ===================================================================== */
    
    :root {
        /* Primary - Indigo */
        --primary-50: #eef2ff;
        --primary-100: #e0e7ff;
        --primary-500: #6366f1;
        --primary-600: #4f46e1;
        --primary-700: #4338ca;
        
        /* Semantic Colors */
        --success-500: #10b981;
        --warning-500: #f59e0b;
        --error-500: #ef4444;
        --info-500: #3b82f6;
        
        /* Neutrals - Slate (Dark Mode) */
        --neutral-50: #f8fafc;
        --neutral-100: #f1f5f9;
        --neutral-200: #e2e8f0;
        --neutral-300: #cbd5e1;
        --neutral-400: #94a3b8;
        --neutral-500: #64748b;
        --neutral-600: #475569;
        --neutral-700: #334155;
        --neutral-800: #1e293b;
        --neutral-900: #0f172a;
        --neutral-950: #020617;
    }
    
    /* =====================================================================
       GLOBAL STYLES & TYPOGRAPHY
       ===================================================================== */
    
    .stApp {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 14px;
        color: var(--neutral-100);
        background: radial-gradient(circle at top left, #1e293b, #0f172a 60%, #020617);
    }
    
    h1, h2, h3, h4 { 
        font-family: 'Plus Jakarta Sans', sans-serif; 
        letter-spacing: -0.02em;
    }
    
    h1 { font-size: 2.25rem; font-weight: 800; color: white; }
    h2 { font-size: 1.75rem; font-weight: 700; color: var(--neutral-100); }
    h3 { font-size: 1.25rem; font-weight: 650; color: var(--neutral-200); }
    
    p { line-height: 1.6; color: var(--neutral-400); }
    
    /* =====================================================================
       ENHANCED COMPONENTS
       ===================================================================== */
    
    /* Progress Bars */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #6366f1, #a855f7);
        border-radius: 999px;
    }

    /* Cards */
    .metric-card {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 1.5rem;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        background: rgba(30, 41, 59, 0.6);
        border-color: rgba(99, 102, 241, 0.3);
        transform: translateY(-4px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
    }
    
    .metric-card .value {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        color: white;
        margin-bottom: 0.25rem;
    }
    
    .metric-card .label {
        font-size: 0.8rem;
        color: var(--neutral-500);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    
    /* Sidebar Navigation */
    .stSidebar {
        background-color: var(--neutral-950) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    
    .stSidebar [data-testid="stSidebarNav"] {
        background-color: transparent !important;
    }
    
    /* Professional Sidebar Nav Items */
    .nav-item {
        padding: 0.6rem 1rem;
        margin: 0.25rem 0;
        border-radius: 10px;
        color: var(--neutral-400);
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    
    .nav-item:hover {
        background: rgba(99, 102, 241, 0.1);
        color: white;
    }
    
    .nav-item.active {
        background: rgba(99, 102, 241, 0.15);
        color: var(--primary-500);
        border-left: 3px solid var(--primary-500);
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 12px;
        background: linear-gradient(135deg, #6366f1 0%, #4f46e1 100%);
        border: none;
        color: white;
        font-weight: 600;
        padding: 0.6rem 1.5rem;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        transform: translateY(-1px);
    }
    
    /* Inputs */
    .stTextInput input, .stTextArea textarea {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        color: white !important;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--primary-500) !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
    }

    /* Accessibility */
    *:focus {
        outline: none !important;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--neutral-950);
    }
    ::-webkit-scrollbar-thumb {
        background: var(--neutral-800);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--neutral-700);
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


@st.cache_resource
def init_vs():
    """Initialize vector store (cached across reruns)."""
    from src.storage.vector_store import VectorStore
    return VectorStore()


# ---------------------------------------------------------------------------
# Service Health Checks
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def check_service_health():
    """Check health of critical services (cached for 60 seconds)."""
    health_status = {
        "database": False,
        "ollama": False,
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


db = init_db()
vs = init_vs()

# Check service health and display status
health = check_service_health()


# ---------------------------------------------------------------------------
# Sidebar Navigation - Enhanced with Professional Branding
# ---------------------------------------------------------------------------

# Sidebar Header with Branding
st.sidebar.markdown("""
<div style="
    padding: 1.5rem;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(79, 70, 225, 0.05));
    border-radius: 12px;
    border: 1px solid rgba(99, 102, 241, 0.1);
    margin-bottom: 2rem;
    text-align: left;
">
    <h1 style="margin: 0; font-size: 1.25rem; font-weight: 800; color: white;">KnowledgeVault</h1>
    <p style="margin: 0.25rem 0 0; font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600;">Research Intelligence</p>
</div>
""", unsafe_allow_html=True)

# Service Health Status
with st.sidebar:
    cols = st.columns(2)
    with cols[0]:
        if health["database"]:
            st.success("Database")
        else:
            st.error("Database")
    
    with cols[1]:
        if health["ollama"]:
            st.success("Ollama")
        else:
            st.warning("Ollama")
    
    if health["errors"]:
        with st.expander("Service Details"):
            for error in health["errors"]:
                st.caption(error)

# Categorized Navigation Structure
NAV_STRUCTURE = {
    "Research": [
        "Dashboard", 
        "Intelligence Lab",
        "Research Agent",
        "Topic Explorer",
        "Blueprint Center",
        "Comparative Lab",
        "Transcripts", 
    ],
    "Operations": [
        "Ingestion Hub", 
        "Pipeline Center",
        "Review Center",
    ],
    "Systems": [
        "Performance",
        "Export & Integration",
        "Settings"
    ]
}

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

# Set default page
if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

# Render Sidebar with Categorized Navigation
with st.sidebar:
    st.markdown("## Navigation")
    
    # We use a custom radio implementation to show categories
    selected_page = st.session_state.current_page
    
    for category, items in NAV_STRUCTURE.items():
        st.markdown(f"**{category.upper()}**")
        for item in items:
            # Simple button-based nav or styled radio
            if st.sidebar.button(
                item, 
                key=f"nav_{item}", 
                use_container_width=True,
                type="secondary" if item != selected_page else "primary"
            ):
                st.session_state.current_page = item
                st.rerun()
        st.markdown("")

page = st.session_state.current_page


# Sidebar Footer - Active Scans Tray & Help
st.sidebar.markdown("---")
with st.sidebar:
    active_scans = db.get_active_scans()
    if active_scans:
        with st.container(border=True):
            st.markdown(f"**<span class='status-pulse'></span> {len(active_scans)} Active Scans**", unsafe_allow_html=True)
            for scan in active_scans[:3]:
                progress = (scan.total_processed / max(scan.total_discovered, 1))
                safe_progress = max(0.0, min(1.0, progress))
                st.caption(f"Scan {scan.scan_id[-4:]}: {safe_progress:.0%}")
                st.progress(safe_progress)
            if len(active_scans) > 3:
                st.caption(f"+ {len(active_scans) - 3} more...")
    else:
        st.caption("No active background scans")

st.sidebar.markdown("""
<div style="
    padding: 1rem;
    border-top: 1px solid rgba(14, 165, 233, 0.1);
    margin-top: 1rem;
    font-size: 0.8rem;
    color: #888;
    text-align: center;
">
    <p style="margin: 0; line-height: 1.5;">
        <a href='#' style='color: #0ea5e9; text-decoration: none;'>Documentation</a> • 
        <a href='#' style='color: #0ea5e9; text-decoration: none;'>Support</a>
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

# Inject Global Command Bar at the top of the main area
st.markdown("""
<div class="command-bar-container">
    <div style="display: flex; align-items: center; gap: 1rem;">
        <span style="font-weight: 600; color: var(--neutral-400);">COMMAND BAR</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Command Bar Functionality (hidden until triggered or persistent)
with st.container():
    col_cmd, col_btn = st.columns([5, 1])
    with col_cmd:
        harvest_url = st.text_input(
            "Quick Harvest URL", 
            placeholder="Paste a YouTube URL here to start a harvest from any page...",
            label_visibility="collapsed",
            key="global_harvest_input"
        )
    with col_btn:
        if st.button("Harvest", type="primary", use_container_width=True, key="global_harvest_btn"):
            if harvest_url:
                run_pipeline_background(harvest_url, db)
                st.toast(f"Harvest started for {harvest_url[:30]}...")
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

PAGE_MAP = {
    "Dashboard": lambda: dashboard.render(db),
    "Ingestion Hub": lambda: ingestion_hub.render(db, run_pipeline_background, run_bulk_pipeline_background),
    "Pipeline Center": lambda: pipeline_center.render(db, run_pipeline_background),
    "Review Center": lambda: reject_review.render(db),
    "Performance": lambda: performance_metrics.render(),
    "Intelligence Lab": lambda: intelligence_lab.render_intelligence_lab(db),
    "Research Agent": lambda: research_agent_view.render_research_agent(db),
    "Topic Explorer": lambda: topic_explorer.render(db),
    "Comparative Lab": lambda: comparative_lab.render(db, vs),
    "Blueprint Center": lambda: blueprint_center.render(db),
    "Transcripts": lambda: transcript_viewer.render(db),
    "Export & Integration": lambda: export_center.render(db),
    "Settings": lambda: data_management.render(db, run_repair_background, get_vault_diagnostics),
}

PAGE_MAP[page]()
