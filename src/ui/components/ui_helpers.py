"""
UI Helper Components — Professional UI/UX patterns for consistent styling

Provides reusable components for headers, metrics, status badges, cards,
and data displays across all Streamlit pages.
"""

import streamlit as st
from typing import Optional, Dict, Any, List

# ===========================================================================
# HEADER COMPONENTS
# ===========================================================================

def page_header(
    title: str,
    subtitle: Optional[str] = None,
    icon: str = "🧠",
    show_divider: bool = True
) -> None:
    """
    Render a professional page header with optional subtitle.
    
    Args:
        title: Main heading text
        subtitle: Optional subheading
        icon: Leading emoji/icon
        show_divider: Whether to show divider after header
    
    Example:
        page_header("Research Console", "Hybrid RAG Search & Chat", icon="🔍")
    """
    st.markdown(f"""
    <div class="main-header">
        <h1>{icon} {title}</h1>
        {f'<p>{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)
    
    if show_divider:
        st.divider()


def section_header(title: str, icon: str = "📌") -> None:
    """
    Render a section header within a page.
    
    Args:
        title: Section heading
        icon: Leading emoji/icon
    """
    st.markdown(f"### {icon} {title}")


# ===========================================================================
# METRIC DISPLAY COMPONENTS
# ===========================================================================

def metric_card(
    value: Any,
    label: str,
    delta: Optional[str] = None,
    delta_color: str = "neutral",
    icon: str = "📊"
) -> None:
    """
    Render a single metric card with optional delta.
    
    Args:
        value: Main metric value
        label: Metric label
        delta: Optional change indicator (e.g., "+5.2%", "-2")
        delta_color: "positive", "negative", "neutral"
        icon: Leading emoji
    
    Example:
        metric_card(1425, "Videos Processed", "+12%", "positive", "✅")
    """
    delta_html = ""
    if delta:
        color_map = {
            "positive": "#10b981",
            "negative": "#ef4444",
            "neutral": "#6b7280"
        }
        delta_color_hex = color_map.get(delta_color, "#6b7280")
        delta_html = f'<div style="color: {delta_color_hex}; font-size: 0.85rem; margin-top: 0.25rem;">{delta}</div>'
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="label">{icon} {label}</div>
        <div class="value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def metric_grid(metrics: List[Dict[str, Any]], cols: int = 4) -> None:
    """
    Render multiple metrics in a responsive grid.
    
    Args:
        metrics: List of dicts with keys: value, label, delta (optional), delta_color, icon
        cols: Number of columns (responsive)
    
    Example:
        metrics = [
            {"value": 1425, "label": "Videos", "delta": "+12%", "delta_color": "positive", "icon": "✅"},
            {"value": 3847, "label": "Chunks", "icon": "📦"},
        ]
        metric_grid(metrics, cols=3)
    """
    columns = st.columns(cols)
    for idx, metric in enumerate(metrics):
        with columns[idx % cols]:
            metric_card(
                metric["value"],
                metric["label"],
                metric.get("delta"),
                metric.get("delta_color", "neutral"),
                metric.get("icon", "📊")
            )


# ===========================================================================
# STATUS & BADGE COMPONENTS
# ===========================================================================

def status_badge(status: str, text: str = "") -> str:
    """
    Generate HTML for a premium status badge.
    
    Args:
        status: "success", "warning", "error", "info", "primary"
        text: Badge label
    """
    status_classes = {
        "success": "status-success",
        "warning": "status-warning",
        "error": "status-error",
        "info": "status-info",
        "primary": "status-info" # Defaulting to info color for primary
    }
    class_name = status_classes.get(status.lower(), "status-info")
    
    # Adding a subtle glow effect in the style for premium feel
    return f'<span class="status-badge {class_name}" style="box-shadow: 0 2px 8px rgba(0,0,0,0.2);">{text or status.upper()}</span>'


def inline_status(status: str, text: str = "") -> None:
    """
    Render a status badge inline with current content.
    
    Args:
        status: "success", "warning", "error", "info"
        text: Badge label
    
    Example:
        inline_status("success", "Ready")
    """
    st.markdown(status_badge(status, text), unsafe_allow_html=True)


# ===========================================================================
# CARD COMPONENTS
# ===========================================================================

def info_card(title: str, content: str, icon: str = "ℹ️") -> None:
    """
    Render an informational card.
    
    Args:
        title: Card title
        content: Card content (markdown supported)
        icon: Leading emoji
    """
    st.markdown(f"""
    <div style="
        background: rgba(30, 41, 59, 0.6);
        border-left: 4px solid #0ea5e9;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    ">
        <strong style="color: #0ea5e9;">{icon} {title}</strong><br>
        <span style="color: #cbd5e1; font-size: 0.9rem;">{content}</span>
    </div>
    """, unsafe_allow_html=True)


def success_card(title: str, content: str) -> None:
    """Render a success card."""
    st.markdown(f"""
    <div style="
        background: rgba(16, 185, 129, 0.1);
        border-left: 4px solid #10b981;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    ">
        <strong style="color: #10b981;">✅ {title}</strong><br>
        <span style="color: #cbd5e1; font-size: 0.9rem;">{content}</span>
    </div>
    """, unsafe_allow_html=True)


def warning_card(title: str, content: str) -> None:
    """Render a warning card."""
    st.markdown(f"""
    <div style="
        background: rgba(245, 158, 11, 0.1);
        border-left: 4px solid #f59e0b;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    ">
        <strong style="color: #f59e0b;">⚠️ {title}</strong><br>
        <span style="color: #cbd5e1; font-size: 0.9rem;">{content}</span>
    </div>
    """, unsafe_allow_html=True)


def error_card(title: str, content: str) -> None:
    """Render an error card."""
    st.markdown(f"""
    <div style="
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    ">
        <strong style="color: #ef4444;">❌ {title}</strong><br>
        <span style="color: #cbd5e1; font-size: 0.9rem;">{content}</span>
    </div>
    """, unsafe_allow_html=True)


def video_card(
    video: Any,
    show_thumbnail: bool = True,
    show_actions: bool = True,
    key_prefix: str = "vid"
) -> Any:
    """
    Render a premium video card. Returns action columns if show_actions is True.
    """
    with st.container(border=True):
        col_img, col_info = st.columns([1, 3]) if show_thumbnail else (None, st.container())
        
        if show_thumbnail and col_img:
            with col_img:
                st.image(f"https://img.youtube.com/vi/{video.video_id}/mqdefault.jpg", use_container_width=True)
        
        with col_info:
            st.markdown(f"**{video.title}**")
            
            dur_min = video.duration_seconds // 60
            dur_sec = video.duration_seconds % 60
            
            status = getattr(video, 'triage_status', 'PENDING')
            status_color = "info"
            if status == "ACCEPTED": status_color = "success"
            elif status == "REJECTED": status_color = "error"
            elif status == "PENDING_REVIEW": status_color = "warning"
            
            badge_html = status_badge(status_color, status)
            
            st.markdown(f"""
            <div style="display: flex; gap: 0.75rem; align-items: center; margin-top: 0.25rem; font-size: 0.85rem; color: #888;">
                {badge_html}
                <span>⏱️ {dur_min}m {dur_sec}s</span>
                <span>👁️ {getattr(video, 'view_count', 0):,}</span>
                <span>🎯 {getattr(video, 'triage_confidence', 0):.0%}</span>
            </div>
            """, unsafe_allow_html=True)
            
            if hasattr(video, 'triage_reason') and video.triage_reason:
                st.caption(f"Reason: {video.triage_reason}")
            
            if show_actions:
                st.markdown("<br>", unsafe_allow_html=True)
                return st.columns([1, 1, 1, 1])
    return None


# ===========================================================================
# PROGRESS & LOADING COMPONENTS
# ===========================================================================

def progress_step(
    step: int,
    total: int,
    label: str,
    status: str = "in_progress"
) -> None:
    """
    Render a step in a progress pipeline.
    
    Args:
        step: Current step number
        total: Total steps
        label: Step label
        status: "pending", "in_progress", "completed", "error"
    """
    progress_percent = (step / total) * 100
    status_icon = {
        "pending": "⭕",
        "in_progress": "🔄",
        "completed": "✅",
        "error": "❌"
    }.get(status, "⭕")
    
    st.markdown(f"""
    <div style="margin: 0.75rem 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <span style="font-weight: 500;">{status_icon} {label}</span>
            <span style="font-size: 0.85rem; color: #888;">{step}/{total}</span>
        </div>
        <div style="
            width: 100%;
            height: 6px;
            background: rgba(30, 41, 59, 0.8);
            border-radius: 3px;
            overflow: hidden;
        ">
            <div style="
                width: {progress_percent}%;
                height: 100%;
                background: linear-gradient(90deg, #0ea5e9, #06b6d4);
                transition: width 0.3s ease;
            "></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def loading_spinner(text: str = "Processing...") -> None:
    """Render a loading spinner with text."""
    st.markdown(f"""
    <div style="text-align: center; padding: 2rem;">
        <div style="
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 3px solid rgba(14, 165, 233, 0.2);
            border-top-color: #0ea5e9;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        "></div>
        <p style="margin-top: 1rem; color: #888;">{text}</p>
    </div>
    <style>
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
    </style>
    """, unsafe_allow_html=True)


# ===========================================================================
# DATA DISPLAY COMPONENTS
# ===========================================================================

def data_table(
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    show_index: bool = False
) -> None:
    """
    Render a styled data table.
    
    Args:
        data: List of dictionaries or DataFrame
        columns: Column names to display
        show_index: Whether to show row index
    """
    import pandas as pd
    df = pd.DataFrame(data) if isinstance(data, list) else data
    
    if columns:
        df = df[columns]
    
    st.dataframe(df, use_container_width=True, hide_index=not show_index)


def key_value_display(items: Dict[str, Any]) -> None:
    """
    Render a key-value display panel.
    
    Args:
        items: Dictionary of key-value pairs to display
    
    Example:
        key_value_display({
            "Status": "Processing",
            "Progress": "45/100",
            "ETA": "2m 30s"
        })
    """
    html = '<div style="display: grid; grid-template-columns: auto 1fr; gap: 1rem;">'
    for key, value in items.items():
        html += f'''
        <div style="font-weight: 600; color: #0ea5e9;">{key}:</div>
        <div style="color: #cbd5e1;">{value}</div>
        '''
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ===========================================================================
# FORM COMPONENTS
# ===========================================================================

def form_section(title: str, help_text: str = "") -> None:
    """
    Render a visually distinct form section header.
    
    Args:
        title: Section title
        help_text: Optional help text
    """
    st.markdown(f"""
    <div style="
        padding: 1rem;
        background: rgba(14, 165, 233, 0.05);
        border-left: 4px solid #0ea5e9;
        border-radius: 8px;
        margin: 1.5rem 0 1rem 0;
    ">
        <strong style="font-size: 1.1rem; color: #0ea5e9;">📝 {title}</strong>
        {f'<p style="margin: 0.5rem 0 0; color: #888; font-size: 0.9rem;">{help_text}</p>' if help_text else ''}
    </div>
    """, unsafe_allow_html=True)


# ===========================================================================
# UTILITIES
# ===========================================================================

def create_columns_equal(count: int, gap: str = "small"):
    """
    Create equal-width columns with consistent spacing.
    
    Args:
        count: Number of columns
        gap: "small", "medium", "large"
    
    Returns:
        List of column containers
    
    Example:
        cols = create_columns_equal(3)
        with cols[0]:
            st.write("Column 1")
    """
    return st.columns(count, gap=gap)


def spacer(height: str = "1rem") -> None:
    """Add vertical spacing."""
    st.markdown(f'<div style="height: {height};"></div>', unsafe_allow_html=True)
