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
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ensure_data_dirs, get_settings
from src.storage.sqlite_store import SQLiteStore

# Page modules
from src.ui.views import (
    intelligence_center, intelligence_studio, ops_dashboard,
    research_chat, transcript_viewer, reject_review,
    blueprint_center, export_center, data_management,
    performance_metrics
)
from src.ingestion.discovery import validate_target_availability

from src.ui.components.ui_helpers import action_confirmation_dialog, failure_confirmation_dialog

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="KnowledgeVault Intelligence",
    layout="wide",
    initial_sidebar_state="auto",
)

# ---------------------------------------------------------------------------
# Custom CSS - Professional Design System (UI/UX Pro Max)
# ---------------------------------------------------------------------------

def inject_custom_css():
    theme = st.session_state.get("theme", "dark")
    
    # Dynamic Theme Variables
    theme_vars = f"""
    :root {{
        --bg-deep: {"#030712" if theme == "dark" else "#f8fafc"};
        --bg-nebula: {"radial-gradient(circle at 0% 0%, #0f172a 0%, #030712 50%, #020617 100%)" if theme == "dark" else "radial-gradient(circle at 0% 0%, #f1f5f9 0%, #f8fafc 100%)"};
        
        --primary-glow: {"#6366f1" if theme == "dark" else "#4f46e1"};
        --primary-active: {"#4f46e1" if theme == "dark" else "#3730a3"};
        --accent-glow: {"#22d3ee" if theme == "dark" else "#0891b2"};
        
        --glass-bg: {"rgba(15, 23, 42, 0.4)" if theme == "dark" else "rgba(255, 255, 255, 0.7)"};
        --glass-border: {"rgba(255, 255, 255, 0.05)" if theme == "dark" else "rgba(0, 0, 0, 0.08)"};
        --glass-active: {"rgba(99, 102, 241, 0.1)" if theme == "dark" else "rgba(79, 70, 225, 0.05)"};
        
        --success-glow: {"#10b981" if theme == "dark" else "#059669"};
        --warning-glow: {"#f59e0b" if theme == "dark" else "#d97706"};
        --error-glow: {"#ef4444" if theme == "dark" else "#dc2626"};
        
        --text-stellar: {"#f8fafc" if theme == "dark" else "#0f172a"};
        --text-muted: {"#64748b" if theme == "dark" else "#475569"};
        --text-contrast: {"#ffffff" if theme == "dark" else "#f8fafc"};
        --nav-text: {"#ffffff" if theme == "dark" else "#1e293b"};
        --nav-shadow: {"0 1px 3px rgba(0,0,0,0.8)" if theme == "dark" else "none"};
    }}
    """
    
    # Static Global Styles
    st.markdown(f"<style>{theme_vars}</style>", unsafe_allow_html=True)
    
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* =====================================================================
       GLOBAL STYLES & TYPOGRAPHY
       ===================================================================== */
    
    .stApp {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 15px;
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

    /* Responsive Typography */
    @media (max-width: 768px) {
        h1 { font-size: 1.75rem !important; }
        h2 { font-size: 1.5rem !important; }
        h3 { font-size: 1.25rem !important; }
        p { font-size: 0.9rem !important; }
        .stApp { font-size: 13px !important; }
    }
    
    /* =====================================================================
       ENHANCED COMPONENTS - GLASSMORPHISM
       ===================================================================== */
    
    .metric-card, [data-testid="stVerticalBlockBordered"] {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 20px !important;
        padding: 1.75rem !important;
        transition: all 0.3s ease !important;
    }
    
    .metric-card:hover, [data-testid="stVerticalBlockBordered"]:hover {
        background: var(--glass-active) !important;
        border-color: var(--primary-glow) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.25) !important;
    }

    @media (max-width: 768px) {
        .metric-card, .glass-card {
            padding: 1.25rem !important;
            border-radius: 12px !important;
        }
        .metric-card:hover, .glass-card:hover {
            transform: translateY(-2px) !important;
        }

        /* Video Card Mobile Fix */
        .video-card-flex {
            flex-direction: column !important;
            gap: 1rem !important;
        }
        .video-thumbnail {
            width: 100% !important;
            max-width: none !important;
        }
        .video-thumbnail img {
            width: 100% !important;
        }
        .video-title {
            font-size: 1.1rem !important;
        }
        .video-meta {
            flex-wrap: wrap !important;
            gap: 0.5rem 1rem !important;
        }
        .meta-sep {
            display: none !important;
        }

        /* Radial Chart Mobile Fix */
        .radial-chart-container {
            flex-direction: column !important;
            text-align: center !important;
            gap: 1rem !important;
        }
        .radial-chart-info {
            padding-left: 0 !important;
            min-width: unset !important;
        }
        
        /* Dashboard Grid Stacking */
        [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
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
        line-height: 1.2;
    }
    
    .metric-card .label, .glass-card .label {
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
    .stButton > button:not([kind="secondary"]):not([kind="tertiary"]), 
    .stButton > button:not([kind="secondary"]):not([kind="tertiary"]) div p, 
    .stButton > button:not([kind="secondary"]):not([kind="tertiary"]) p {
        border-radius: 14px;
        background: linear-gradient(135deg, var(--primary-glow) 0%, var(--primary-active) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: var(--text-contrast) !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        font-weight: 700 !important;
        font-size: 1rem;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        text-transform: none;
        letter-spacing: 0.02em;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        white-space: normal !important;
        height: auto !important;
        min-height: 44px;
        padding: 0.75rem 1.25rem !important;
        line-height: 1.4 !important;
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
        background: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        backdrop-filter: blur(12px) !important;
        color: var(--text-stellar) !important;
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
        background: var(--bg-deep);
    }
    ::-webkit-scrollbar-thumb {
        background: var(--glass-border);
        border: 2px solid var(--bg-deep);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
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

    /* Sidebar Navigation Button Contrast Fix */
    div[data-testid="stSidebar"] button, 
    div[data-testid="stSidebar"] button div p,
    div[data-testid="stSidebar"] button p {
        color: var(--nav-text) !important;
        font-weight: 600 !important;
        text-shadow: var(--nav-shadow) !important;
    }

    div[data-testid="stSidebar"] button[kind="primary"],
    div[data-testid="stSidebar"] button[kind="primary"] div p {
        background-color: var(--primary-glow) !important;
        color: var(--text-contrast) !important;
        font-weight: 700 !important;
        border: 1px solid rgba(255, 255, 254, 0.2) !important;
    }

    div[data-testid="stSidebar"] button[kind="secondary"],
    div[data-testid="stSidebar"] button[kind="secondary"] div p {
        background-color: var(--glass-bg) !important;
        color: rgba(255, 255, 255, 0.8) !important;
        border: 1px solid var(--glass-border) !important;
    }
    
    /* Chat Message Legibility Fix for Light Theme */
    [data-testid="stChatMessage"] {
        background-color: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
    }
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {
        color: var(--text-stellar) !important;
        font-weight: 500 !important;
    }
    
    /* Secondary Button Contrast in Sidebar */
    div[data-testid="stSidebar"] button[kind="secondary"] {
        background-color: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        color: var(--text-stellar) !important;
        font-weight: 600 !important;
        transition: all 0.2s ease;
    }
    div[data-testid="stSidebar"] button[kind="secondary"]:hover {
        background-color: var(--glass-active) !important;
        border-color: var(--primary-glow) !important;
        color: var(--primary-glow) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    }

    /* =====================================================================
       RESEARCH CHAL HUB - MESSAGING STYLES
       ===================================================================== */
    
    /* Standardize Chat Messages */
    div[data-testid="stChatMessage"] {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        color: white !important;
        font-weight: 700 !important;
        box-shadow: 0 0 15px rgba(99, 102, 241, 0.3);
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

    /* Fixed Aesthetic - Handling Header/Footer Visibility */
    footer {visibility: hidden; height: 10px;}
    
    /* Responsive Header: Show on mobile for sidebar expansion, hide on desktop for immersion */
    header {
        visibility: visible !important; 
        background: rgba(15, 23, 42, 0.1) !important;
        backdrop-filter: blur(8px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    @media (min-width: 1024px) {
        header { 
            visibility: visible !important; 
            height: 3rem !important; 
        }
    }
    
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
    /* =====================================================================
       MOBILE RESPONSIVENESS
       ===================================================================== */
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem !important;
        }
        div[data-testid="stSidebar"] {
            width: 80vw !important;
        }
        .metric-card {
            margin-bottom: 1rem !important;
        }
        h1 { font-size: 2rem !important; }
        h2 { font-size: 1.5rem !important; }
    }

    @keyframes pulse-live {
        0% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(34, 211, 238, 0); }
        100% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0); }
    }
    .live-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #22d3ee;
        border-radius: 50%;
        margin-right: 8px;
        vertical-align: middle;
        animation: pulse-live 2s infinite;
    }
</style>
<script>
    (function() {
        const navItems = [
            "Intelligence Center", "Intelligence Studio", "Research Chat",
            "Operations Dashboard", "Triage Center", "Transcripts",
            "Settings"
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

inject_custom_css()


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
        "graph_engine": False,
        "errors": []
    }
    
    settings = get_settings()

    # Check Database
    try:
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
        ollama_host = settings["ollama"]["host"]
        resp = requests.get(f"{ollama_host}/api/tags", timeout=3)
        if resp.status_code == 200:
            health_status["ollama"] = True
    except Exception as e:
        health_status["errors"].append(f"Ollama: Service unavailable")

    # Check Vector Store (ChromaDB)
    try:
        vs_internal = init_vs()
        if vs_internal and vs_internal.is_ready():
            health_status["vector_store"] = True
    except Exception as e:
        health_status["errors"].append(f"Vector Store: {str(e)[:50]}")

    # Check Graph Engine (Neo4j)
    try:
        from neo4j import GraphDatabase
        cfg = settings["neo4j"]
        driver = GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
        with driver.session() as session:
            session.run("MATCH (n) RETURN count(n) LIMIT 1")
        driver.close()
        health_status["graph_engine"] = True
    except Exception as e:
        health_status["errors"].append(f"Graph Engine: {str(e)[:50]}")

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
# First-Run Onboarding Modal
# ---------------------------------------------------------------------------

@st.dialog("Welcome to KnowledgeVault Intelligence")
def render_onboarding_modal():
    st.markdown("""
    ### ✦ Your Research Intelligence Journey Starts Here
    
    KnowledgeVault transforms fragmented video tutorials into a structured, searchable knowledge graph. 
    Follow these steps to initialize your vault:
    
    1. **Harvest Content**: Paste a YouTube channel or playlist URL in the **Intelligence Center**.
    2. **Triage Intel**: Filter out noise and approve high-fidelity content in the **Review Center**.
    3. **Deep Synthesis**: Use the **Intelligence Studio** to find thematic bridges across your vault.
    4. **Execute Blueprints**: Access actionable procedural steps in the **Execution OS**.
    
    ---
    **System Status**: 🟢 Engine Ready • 🟢 Storage Connected
    
    *Need help? Click the 'Documentation' link in the sidebar footer at any time.*
    """)
    if st.button("GET STARTED", type="primary", use_container_width=True):
        st.session_state.onboarding_complete = True
        st.rerun()

if "onboarding_complete" not in st.session_state:
    # Check if we have any data yet - if empty vault, show onboarding
    try:
        count = db.conn.execute("SELECT COUNT(*) as cnt FROM videos").fetchone()["cnt"]
        if count == 0:
            render_onboarding_modal()
    except Exception as e:
        logger.warning(f"Onboarding check failed: {e}")
        pass


# ---------------------------------------------------------------------------
# Sidebar Navigation - Enhanced with Professional Branding
# ---------------------------------------------------------------------------

# Sidebar Header with Branding
_current_theme = st.session_state.get("theme", "dark")
st.sidebar.markdown(f"""
<div style="padding: 1.5rem; background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(34, 211, 238, 0.05)); border-radius: 16px; border: 1px solid rgba(99, 102, 241, 0.2); margin-bottom: 2rem; text-align: left; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
    <h1 style="margin: 0; font-size: 1.5rem; font-weight: 800; color: {"#ffffff" if _current_theme == "dark" else "#1e293b"}; letter-spacing: -0.03em;">KnowledgeVault</h1>
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
            "Intelligence Center", 
            "Intelligence Studio",
            "Research Chat",
        ],
        "Operations": [
            "Operations Dashboard",
            "Triage Center",
            "Transcripts", 
        ],
        "System": [
            "Blueprint Center",
            "Export & Integration",
            "Settings",
            "Performance"
        ]
    }

    # Flatten for programmatic check
    nav_options = []
    for category, items in NAV_STRUCTURE.items():
        nav_options.extend(items)

    # Support programmatic navigation - MUST BE ABOVE SIDEBAR RENDERING
    if "navigate" in st.session_state:
        target_page = st.session_state.pop("navigate")
        if target_page in nav_options:
            st.session_state.current_page = target_page
        elif target_page == "Transcripts": # Alias handling
            st.session_state.current_page = "Transcripts"

    selected_page = st.session_state.get("current_page", "Intelligence Center")
    
    for category, items in NAV_STRUCTURE.items():
        st.markdown(f"<p style='font-size:0.75rem; color:#475569; font-weight:800; margin-top:2rem; margin-bottom:0.5rem;'>{category.upper()}</p>", unsafe_allow_html=True)
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


# Support programmatic navigation (backup check if session state set outside sidebar block)
if "navigate" in st.session_state:
    target_page = st.session_state.pop("navigate")
    if target_page in nav_options:
        st.session_state.current_page = target_page

page = st.session_state.get("current_page", "Intelligence Center")


# Sidebar Footer - Active Scans Tray & Help
st.sidebar.markdown("---")
with st.sidebar:
    active_scans = db.get_active_scans()
    
    # Live Monitor Control
    col_m1, col_m2 = st.columns([1.2, 1])
    with col_m1:
        live_mon = st.toggle("Live Monitor", value=st.session_state.get("live_mon", False), help="Auto-refresh when tasks are active.")
        st.session_state.live_mon = live_mon
    with col_m2:
        if live_mon:
            st.caption(f"⏱ {datetime.now().strftime('%H:%M:%S')}")

    st.markdown("<p style='font-size:0.75rem; color:#475569; font-weight:800; margin-top:0.5rem; margin-bottom:0.5rem;'>SYSTEM PIPELINE MONITOR</p>", unsafe_allow_html=True)
    if active_scans:
        label = f"⚙️ {len(active_scans)} ACTIVE HARVESTS"
        with st.expander(label, expanded=True):
            st.markdown("<span class='live-dot'></span> **Live Pipeline Trace Active**", unsafe_allow_html=True)
            for scan in active_scans[:5]:
                progress = (scan.total_processed / max(scan.total_discovered, 1))
                safe_progress = max(0.0, min(1.0, progress))
                display_name = getattr(scan, 'channel_name', None) or f"Scan {scan.scan_id[-4:]}"
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

# Global Command Bar removed - now integrated into Intelligence Center
st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

PAGE_MAP = {
    "Intelligence Center": lambda: intelligence_center.render(db, vs, run_pipeline_background),
    "Intelligence Studio": lambda: intelligence_studio.render(db, vs, run_repair_background),
    "Research Chat": lambda: research_chat.render_research_chat(db, vs),
    "Operations Dashboard": lambda: ops_dashboard.render(db, run_pipeline_background, run_bulk_pipeline_background, run_repair_background, get_vault_diagnostics),
    "Triage Center": lambda: reject_review.render(db),
    "Transcripts": lambda: transcript_viewer.render(db),
    "Blueprint Center": lambda: blueprint_center.render(db),
    "Export & Integration": lambda: export_center.render(db),
    "Settings": lambda: data_management.render(db, run_repair_background, get_vault_diagnostics),
    "Performance": lambda: performance_metrics.render(db),
}

PAGE_MAP[page]()
# Reload trigger for Live Monitor
if st.session_state.get("live_mon") and active_scans:
    time.sleep(10) # Revert to 10s to prevent UI thrashing
    st.rerun()
