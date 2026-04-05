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
# Custom CSS - Professional Design System (UI/UX Pro Max)
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* =====================================================================
       DESIGN SYSTEM TOKENS
       ===================================================================== */
    
    :root {
        /* Primary Palette */
        --primary-50: #f0f9ff;
        --primary-100: #e0f2fe;
        --primary-500: #0ea5e9;
        --primary-600: #0284c7;
        --primary-700: #0369a1;
        --primary-800: #075985;
        
        /* Semantic Colors */
        --success-500: #10b981;
        --warning-500: #f59e0b;
        --error-500: #ef4444;
        --info-500: #3b82f6;
        
        /* Neutral Palette (Dark Mode) */
        --neutral-50: #f9fafb;
        --neutral-100: #f3f4f6;
        --neutral-200: #e5e7eb;
        --neutral-300: #d1d5db;
        --neutral-400: #9ca3af;
        --neutral-500: #6b7280;
        --neutral-600: #4b5563;
        --neutral-700: #2d3748;
        --neutral-800: #1f2937;
        --neutral-900: #111827;
    }
    
    /* =====================================================================
       GLOBAL STYLES
       ===================================================================== */
    
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 14px;
        color: var(--neutral-100);
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    }
    
    /* Typography Scale */
    h1 { font-size: 2.125rem; font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; }
    h2 { font-size: 1.875rem; font-weight: 700; line-height: 1.25; letter-spacing: -0.01em; }
    h3 { font-size: 1.5rem; font-weight: 600; line-height: 1.33; }
    h4 { font-size: 1.125rem; font-weight: 600; line-height: 1.5; }
    h5 { font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    
    p { line-height: 1.6; color: var(--neutral-300); }
    
    /* =====================================================================
       PROGRESS BARS & ANIMATIONS
       ===================================================================== */
    
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, 
            var(--primary-500) 0%, 
            var(--primary-100) 50%, 
            var(--primary-500) 100%
        );
        background-size: 200% 100%;
        animation: shimmer 2s infinite linear;
    }

    /* Pulse for active status */
    @keyframes pulse-green {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    
    .status-pulse {
        width: 8px;
        height: 8px;
        background-color: var(--success-500);
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse-green 2s infinite;
    }

    /* =====================================================================
       GLOBAL COMMAND BAR
       ===================================================================== */
    
    .command-bar-container {
        background: rgba(30, 41, 59, 0.8);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(14, 165, 233, 0.2);
        padding: 0.75rem 2rem;
        position: sticky;
        top: 0;
        z-index: 999;
        margin: -4rem -4rem 2rem -4rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    /* =====================================================================
       CARDS & CONTAINERS
       ===================================================================== */
    
    .metric-card {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.6));
        border: 1px solid rgba(14, 165, 233, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        backdrop-filter: blur(8px);
    }
    
    .metric-card:hover {
        border-color: rgba(14, 165, 233, 0.4);
        box-shadow: 0 10px 30px rgba(14, 165, 233, 0.1);
        transform: translateY(-2px);
    }
    
    .metric-card .value {
        font-size: 2.25rem;
        font-weight: 800;
        background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
    }
    
    .metric-card .label {
        font-size: 0.75rem;
        color: var(--neutral-400);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.375rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .status-success { background: rgba(16, 185, 129, 0.15); color: #10b981; }
    .status-warning { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
    .status-error { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
    .status-info { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
    
    /* =====================================================================
       SIDEBAR STYLING
       ===================================================================== */
    
    .stSidebar > div:first-child {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(20, 28, 48, 0.95) 100%);
    }
    
    .stSidebar [data-testid="stSidebarNav"] {
        padding: 0;
    }
    
    .stSidebar .stMarkdown {
        border-bottom: 1px solid rgba(14, 165, 233, 0.1);
        margin-bottom: 1rem;
        padding-bottom: 1rem;
    }
    
    .stSidebar .stMarkdown h1 {
        font-size: 1.25rem;
        margin-bottom: 0;
    }
    
    .stSidebar .stMarkdown h2 {
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--neutral-400);
        margin: 1.5rem 0 0.75rem 0;
    }
    
    .sidebar-nav-item {
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        border-radius: 10px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s ease;
        border-left: 3px solid transparent;
        position: relative;
    }
    
    .sidebar-nav-item:hover {
        background: rgba(14, 165, 233, 0.1);
        border-left-color: var(--primary-500);
        padding-left: 1.25rem;
    }
    
    /* =====================================================================
       BUTTONS & INTERACTIONS
       ===================================================================== */
    
    .stButton > button {
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        transition: all 0.2s ease;
        border: none;
        background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
        color: white;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(14, 165, 233, 0.3);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* =====================================================================
       INPUT FIELDS
       ===================================================================== */
    
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(14, 165, 233, 0.2);
        border-radius: 10px;
        color: var(--neutral-100);
        padding: 0.75rem 1rem;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus {
        border-color: var(--primary-500);
        box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
        outline: none;
    }
    
    /* =====================================================================
       RADIO & CHECKBOXES
       ===================================================================== */
    
    .stRadio > div {
        gap: 0.75rem;
    }
    
    .stRadio > div > label {
        display: flex;
        align-items: center;
        padding: 0.5rem 0;
        border-radius: 8px;
        transition: background 0.2s ease;
        cursor: pointer;
    }
    
    .stRadio > div > label:hover {
        background: rgba(14, 165, 233, 0.05);
    }
    
    /* =====================================================================
       EXPANDABLE SECTIONS
       ===================================================================== */
    
    .stExpander {
        border: 1px solid rgba(14, 165, 233, 0.15);
        border-radius: 10px;
        overflow: hidden;
    }
    
    .stExpander > div:first-child {
        background: rgba(30, 41, 59, 0.4);
        padding: 1rem 1.25rem;
    }
    
    .stExpander > div:first-child:hover {
        background: rgba(30, 41, 59, 0.6);
    }
    
    /* =====================================================================
       TABLES
       ===================================================================== */
    
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
    
    [data-testid="stDataFrame"] thead {
        background: rgba(14, 165, 233, 0.1);
    }
    
    /* =====================================================================
       ACCESSIBILITY ENHANCEMENTS
       ===================================================================== */
    
    /* Focus states for keyboard navigation */
    *:focus-visible {
        outline: 2px solid var(--primary-500);
        outline-offset: 2px;
    }
    
    /* Improved contrast for text */
    .stMarkdown a {
        color: #06b6d4;
        text-decoration: none;
        font-weight: 500;
    }
    
    .stMarkdown a:hover {
        text-decoration: underline;
    }
    
    /* =====================================================================
       RESPONSIVE DESIGN
       ===================================================================== */
    
    @media (max-width: 768px) {
        .main-header {
            padding: 1.5rem 1.5rem;
        }
        
        .main-header h1 {
            font-size: 1.5rem;
        }
        
        .metric-card {
            padding: 1rem;
        }
        
        .metric-card .value {
            font-size: 1.75rem;
        }
    }
    
    /* =====================================================================
       DARK MODE SPECIFIC TWEAKS
       ===================================================================== */
    
    .stSelectbox {
        color: var(--neutral-100);
    }
    
    [role="listbox"] {
        background: var(--neutral-800) !important;
        border: 1px solid rgba(14, 165, 233, 0.2) !important;
        border-radius: 10px !important;
    }
    
    [role="option"] {
        color: var(--neutral-100) !important;
    }
    
    [role="option"]:hover {
        background: rgba(14, 165, 233, 0.2) !important;
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
    background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(3, 105, 161, 0.05));
    border-radius: 12px;
    border: 1px solid rgba(14, 165, 233, 0.2);
    margin-bottom: 1.5rem;
    text-align: center;
">
    <h1 style="margin: 0; font-size: 1.5rem; font-weight: 700;">🧠 knowledgeVault</h1>
    <p style="margin: 0.5rem 0 0; font-size: 0.85rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em;">YouTube Intelligence</p>
</div>
""", unsafe_allow_html=True)

# Service Health Status
with st.sidebar:
    cols = st.columns(2)
    with cols[0]:
        if health["database"]:
            st.success("✅ Database")
        else:
            st.error("❌ Database")
    
    with cols[1]:
        if health["ollama"]:
            st.success("✅ Ollama")
        else:
            st.warning("⚠️ Ollama")
    
    if health["errors"]:
        with st.expander("🔍 Service Details"):
            for error in health["errors"]:
                st.caption(f"⚠️ {error}")

# Categorized Navigation Structure
NAV_STRUCTURE = {
    "Research": [
        "🏠 Dashboard", 
        "🔬 Intelligence Lab",
        "🧬 Comparative Lab",
        "📜 Transcripts", 
    ],
    "Operations": [
        "🌾 Ingestion Hub", 
        "📊 Pipeline Center",
        "⚖️ Review Center", # New View planned
    ],
    "System": [
        "⚡ Performance",
        "📤 Export & Integration",
        "⚙️ Admin & Settings"
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
    st.session_state.current_page = "🏠 Dashboard"

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
        📖 <a href='#' style='color: #0ea5e9; text-decoration: none;'>Documentation</a> • 
        💡 <a href='#' style='color: #0ea5e9; text-decoration: none;'>Support</a>
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
        <span style="font-size: 1.2rem;">🔍</span>
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
        if st.button("🚀 Harvest", type="primary", use_container_width=True, key="global_harvest_btn"):
            if harvest_url:
                run_pipeline_background(harvest_url, db)
                st.toast(f"Harvest started for {harvest_url[:30]}...", icon="🚀")
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

PAGE_MAP = {
    "🏠 Dashboard": lambda: dashboard.render(db),
    "🌾 Ingestion Hub": lambda: ingestion_hub.render(db, run_pipeline_background, run_bulk_pipeline_background),
    "📊 Pipeline Center": lambda: pipeline_center.render(db, run_pipeline_background),
    "⚖️ Review Center": lambda: reject_review.render(db), # Using existing reject_review for now
    "⚡ Performance": lambda: performance_metrics.render(),
    "🔬 Intelligence Lab": lambda: intelligence_lab.render(db, vs),
    "🧬 Comparative Lab": lambda: comparative_lab.render(db, vs),
    "📜 Transcripts": lambda: transcript_viewer.render(db),
    "📤 Export & Integration": lambda: export_center.render(db),
    "⚙️ Admin & Settings": lambda: data_management.render(db, run_repair_background, get_vault_diagnostics),
}

PAGE_MAP[page]()
