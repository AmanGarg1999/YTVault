"""
UI Helper Components — Intelligence Core Design System (Nebula-Glassmorphism)

Provides reusable, high-performance components for headers, metrics, status badges, 
and data displays. Optimized for research-grade intelligence platforms.
"""

import streamlit as st
import json
import re
from typing import Optional, Dict, Any, List

# ===========================================================================
# HEADER COMPONENTS
# ===========================================================================

def page_header(
    title: str,
    subtitle: Optional[str] = None,
    show_divider: bool = True
) -> None:
    """
    Render a high-end page header with consistent typography and spacing.
    """
    st.markdown(f"""
<div style="margin-bottom: 2.5rem; position: relative;">
<h1 style="color: white; margin-bottom: 0.25rem; font-family: 'Outfit', sans-serif; letter-spacing: -0.04em; font-weight: 800;">{title}</h1>
{f'<p style="color: var(--text-muted); font-size: 1rem; max-width: 850px; font-weight: 500;">{subtitle}</p>' if subtitle else ''}
<div style="position: absolute; bottom: -1rem; left: 0; width: 60px; height: 4px; background: linear-gradient(90deg, var(--primary-glow), transparent); border-radius: 2px;"></div>
</div>
""", unsafe_allow_html=True)
    
    if show_divider:
        spacer("2rem")


def section_header(title: str, icon: Optional[str] = None) -> None:
    """
    Render a section header with optional icon and accent.
    """
    icon_html = f"<span style='color: var(--accent-glow); margin-right: 0.5rem;'>{icon}</span>" if icon else ""
    st.markdown(f"""
<div style="display: flex; align-items: center; margin: 1.5rem 0 1rem 0;">
<h3 style="margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.15rem; font-weight: 700; color: #cbd5e1;">{icon_html}{title}</h3>
</div>
""", unsafe_allow_html=True)


# ===========================================================================
# METRIC & VISUALIZATION COMPONENTS
# ===========================================================================

def metric_card(
    value: Any,
    label: str,
    delta: Optional[str] = None,
    delta_color: str = "neutral",
    glow: bool = False
) -> None:
    """
    Render a glassmorphic metric card.
    
    Args:
        value: Main value (str or int)
        label: Descriptor
        delta: Optional change text
        delta_color: positive, negative, info
        glow: If True, adds a subtle persistent glow
    """
    delta_html = ""
    if delta:
        color_map = {
            "positive": "#10b981",
            "negative": "#ef4444",
            "info": "#22d3ee",
            "neutral": "#64748b"
        }
        delta_color_hex = color_map.get(delta_color, "#64748b")
        delta_html = f'<div style="color: {delta_color_hex}; font-size: 0.8rem; margin-top: 0.25rem; font-weight: 700;">{delta}</div>'
    
    glow_style = "box-shadow: 0 0 20px rgba(99, 102, 241, 0.15); border-color: rgba(99, 102, 241, 0.3);" if glow else ""
    
    st.markdown(f"""
<div class="metric-card" style="{glow_style}">
<div class="label">{label}</div>
<div class="value">{value}</div>
{delta_html}
</div>
""", unsafe_allow_html=True)


def radial_health_chart(percentage: int, label: str, description: str = "") -> None:
    """
    Render a radial progress chart using custom SVG/CSS for 'Vault Health'.
    """
    # Color based on percentage
    color = "#10b981" if percentage > 80 else ("#f59e0b" if percentage > 50 else "#ef4444")
    
    st.markdown(f"""
<div class="metric-card" style="display: flex; align-items: center; gap: 1.5rem;">
<div style="position: relative; width: 80px; height: 80px;">
<svg viewBox="0 0 36 36" style="width: 100%; height: 100%; transform: rotate(-90deg);">
<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="3" />
<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="{percentage}, 100" />
</svg>
<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-family: 'Outfit', sans-serif; font-weight: 800; font-size: 1.2rem; color: white;">{percentage}%</div>
</div>
<div>
<div class="label" style="margin-bottom: 0.25rem;">{label}</div>
<div style="font-size: 0.85rem; color: var(--text-muted);">{description}</div>
</div>
</div>
""", unsafe_allow_html=True)


def metric_grid(metrics: List[Dict[str, Any]], cols: int = 4) -> None:
    """
    Render multiple metrics in a responsive grid.
    """
    columns = st.columns(cols)
    for idx, metric in enumerate(metrics):
        with columns[idx % cols]:
            if "percentage" in metric:
                radial_health_chart(
                    metric["percentage"], 
                    metric["label"], 
                    metric.get("description", "")
                )
            else:
                metric_card(
                    metric["value"],
                    metric["label"],
                    metric.get("delta"),
                    metric.get("delta_color", "neutral"),
                    glow=metric.get("glow", False)
                )


# ===========================================================================
# STATUS & BADGE COMPONENTS
# ===========================================================================

def status_badge(status: str, text: str = "") -> str:
    """
    Generate HTML for a premium Nebula status badge.
    """
    colors = {
        "success": ("#10b981", "rgba(16, 185, 129, 0.1)"),
        "warning": ("#f59e0b", "rgba(245, 158, 11, 0.1)"),
        "error": ("#ef4444", "rgba(239, 68, 68, 0.1)"),
        "info": ("#22d3ee", "rgba(34, 211, 238, 0.1)"),
        "primary": ("#6366f1", "rgba(99, 102, 241, 0.1)")
    }
    
    color, bg = colors.get(status.lower(), colors["info"])
    
    return f'''
<span style="display: inline-block; padding: 0.3rem 0.8rem; border-radius: 8px; font-size: 0.65rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; background: {bg}; color: {color}; border: 1px solid {color}44; backdrop-filter: blur(4px);">{text or status.upper()}</span>
'''


def inline_status(status: str, text: str = "") -> None:
    """Render status badge inline."""
    st.markdown(status_badge(status, text), unsafe_allow_html=True)


# ===========================================================================
# CARD & CONTAINER COMPONENTS
# ===========================================================================

def glass_card(title: Optional[str] = None, border_accent: Optional[str] = None):
    """
    Create a context manager for a glassmorphic container.
    """
    accent_style = f"border-left: 4px solid {border_accent};" if border_accent else ""
    st.markdown(f"""
<div style="background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 16px; padding: 1.5rem; margin: 1rem 0; {accent_style}">
""", unsafe_allow_html=True)
    if title:
        st.markdown(f"<strong style='color: white; display: block; margin-bottom: 1rem; font-size: 1.1rem;'>{title}</strong>", unsafe_allow_html=True)
    
    # Usage: 
    # with glass_card("Title"): 
    #     st.write("Content")
    return st.container()


def info_card(title: str, content: str) -> None:
    st.markdown(f"""
<div style="background: rgba(34, 211, 238, 0.05); border-left: 4px solid var(--accent-glow); border-radius: 12px; padding: 1.25rem; margin: 1rem 0;">
<strong style="color: var(--accent-glow); display: block; margin-bottom: 0.25rem; font-weight: 700;">{title}</strong>
<span style="color: var(--text-muted); font-size: 0.95rem;">{content}</span>
</div>
""", unsafe_allow_html=True)

def success_card(title: str, content: str) -> None:
    st.markdown(f"""
<div style="background: rgba(16, 185, 129, 0.05); border-left: 4px solid var(--success-glow); border-radius: 12px; padding: 1.25rem; margin: 1rem 0;">
<strong style="color: var(--success-glow); display: block; margin-bottom: 0.25rem; font-weight: 700;">{title}</strong>
<span style="color: var(--text-muted); font-size: 0.95rem;">{content}</span>
</div>
""", unsafe_allow_html=True)

def warning_card(title: str, content: str) -> None:
    st.markdown(f"""
<div style="background: rgba(245, 158, 11, 0.05); border-left: 4px solid var(--warning-glow); border-radius: 12px; padding: 1.25rem; margin: 1rem 0;">
<strong style="color: var(--warning-glow); display: block; margin-bottom: 0.25rem; font-weight: 700;">{title}</strong>
<span style="color: var(--text-muted); font-size: 0.95rem;">{content}</span>
</div>
""", unsafe_allow_html=True)


# ===========================================================================
# VIDEO & RESEARCH COMPONENTS
# ===========================================================================

def strip_html(text: str) -> str:
    """Helper to strip HTML tags and LLM artifacts."""
    if not text: return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    if text.strip().startswith('{') and text.strip().endswith('}'):
        try:
            import json
            parsed = json.loads(text)
            return parsed.get("reason", parsed.get("summary", text))
        except: pass
    return text.strip()


def video_card(
    video: Any,
    show_thumbnail: bool = True,
    show_actions: bool = True,
    key_prefix: str = "vid"
) -> Any:
    """
    Render a professional video card with high visual hierarchy.
    """
    with st.container(border=False):
        # We render the main information as a single HTML block to prevent tag leakage
        clean_title = strip_html(video.title)
        dur_min = video.duration_seconds // 60
        dur_sec = video.duration_seconds % 60
        
        status = getattr(video, 'triage_status', 'PENDING')
        status_color = "info"
        if status == "ACCEPTED": status_color = "success"
        elif status == "REJECTED": status_color = "error"
        elif status == "PENDING_REVIEW": status_color = "warning"
        
        badge_html = status_badge(status_color, status)
        confidence = getattr(video, 'triage_confidence', 0)
        views = getattr(video, 'view_count', 0)

        st.markdown(f"""
<div style="background: rgba(15, 23, 42, 0.3); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 1.25rem; margin-bottom: 0.75rem;"><div style="display: flex; gap: 1.5rem; align-items: flex-start;">
{f'<div style="width: 140px; flex-shrink: 0;"><img src="https://img.youtube.com/vi/{video.video_id}/mqdefault.jpg" style="width: 100%; border-radius: 8px;"></div>' if show_thumbnail else ''}
<div style="flex-grow: 1;">
<p style="font-size: 1.1rem; font-weight: 700; color: white; margin: 0; line-height: 1.4;">{clean_title}</p>
<div style="display: flex; gap: 1rem; align-items: center; margin-top: 0.75rem; font-size: 0.75rem; color: #94a3b8; font-weight: 600;">
{badge_html}<span>{dur_min}:{dur_sec:02d}</span><span>{views:,} VIEWS</span><span style="color: #6366f1;">{confidence:.0%} CONFIDENCE</span>
</div></div></div></div>
""", unsafe_allow_html=True)
        
        if show_actions:
            cols = st.columns([1, 1, 1, 1])
            return cols
            
    return None


# ===========================================================================
# INTERACTION: SIDE-CAR PANEL
# ===========================================================================

def side_car_layout():
    """
    Initialize a side-car layout. Returns two columns (main, side).
    """
    if "side_car_active" not in st.session_state:
        st.session_state.side_car_active = False
    
    if st.session_state.side_car_active:
        return st.columns([1.8, 1])
    else:
        return st.columns([1])[0], None


def render_side_car(title: str, content_func, close_key: str = "close_side"):
    """
    Render the content of the side-car panel.
    """
    st.markdown(f"""
<div style="background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(20px); border: 1px solid var(--primary-glow); border-radius: 20px; padding: 2rem; height: 100%; box-shadow: -10px 0 50px rgba(0,0,0,0.5);">
<h2 style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; margin-top: 0;">{title}</h2>
<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.1); margin: 1.5rem 0;">
""", unsafe_allow_html=True)
    
    content_func()
    
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("Close Panel", key=close_key, use_container_width=True):
        st.session_state.side_car_active = False
        st.session_state.active_video_id = None
        st.rerun()


# ===========================================================================
# PROGRESS & LOADING COMPONENTS
# ===========================================================================

def loading_spinner(text: str = "Processing...") -> None:
    """Render a premium loading spinner with Nebula styling."""
    st.markdown(f"""
    <div style="text-align: center; padding: 3rem;">
        <div style="
            display: inline-block;
            width: 48px;
            height: 48px;
            border: 3px solid rgba(99, 102, 241, 0.1);
            border-top-color: var(--primary-glow);
            border-radius: 50%;
            animation: spin 1s cubic-bezier(0.4, 0, 0.2, 1) infinite;
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.2);
        "></div>
        <p style="margin-top: 1.5rem; color: var(--text-muted); font-weight: 500; letter-spacing: 0.05em;">{text.upper()}</p>
    </div>
    <style>
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
    """, unsafe_allow_html=True)


@st.dialog("Intelligence Core Action")
def action_confirmation_dialog(title: str, message: str, icon: str = "✦"):
    """
    Render a high-end action confirmation dialog.
    """
    st.markdown(f"""
    <div style="text-align: center; padding: 1rem 0;">
        <div style="font-size: 3rem; margin-bottom: 1rem; color: var(--primary-glow);">{icon}</div>
        <h3 style="color: white; margin-bottom: 0.5rem; font-family: 'Outfit', sans-serif;">{title}</h3>
        <p style="color: var(--text-muted); font-size: 1rem; margin-bottom: 2rem;">{message}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Acknowledge & Continue", type="primary", use_container_width=True, key="dialog_close_btn"):
        st.rerun()


@st.dialog("System Alert: Operation Interrupted")
def failure_confirmation_dialog(title: str, error_message: str, retry_callback: Any = None, queue_callback: Any = None):
    """
    Render a high-end failure dialog with Retry and Queue options.
    """
    st.markdown(f"""
    <div style="text-align: center; padding: 1rem 0;">
        <div style="font-size: 3rem; margin-bottom: 1rem; color: var(--error-glow);">⚠️</div>
        <h3 style="color: white; margin-bottom: 0.5rem; font-family: 'Outfit', sans-serif;">{title}</h3>
        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 2rem; background: rgba(239, 68, 68, 0.08); padding: 1rem; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.2); font-family: 'JetBrains Mono', monospace; text-align: left; max-height: 200px; overflow-y: auto;">{error_message}</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Retry Now", type="primary", use_container_width=True, key="fail_retry_btn"):
            if retry_callback: retry_callback()
            st.rerun()
    with col2:
        if st.button("Add to Queue", use_container_width=True, key="fail_queue_btn"):
            if queue_callback: queue_callback()
            st.rerun()
    with col3:
        if st.button("Dismiss", use_container_width=True, key="fail_dismiss_btn"):
            st.rerun()


# ===========================================================================
# DATA DISPLAY COMPONENTS
# ===========================================================================

def data_table(
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    show_index: bool = False
) -> None:
    """Render a styled data table with glassmorphic accents."""
    import pandas as pd
    df = pd.DataFrame(data) if isinstance(data, list) else data
    if columns:
        df = df[columns]
    st.dataframe(df, use_container_width=True, hide_index=not show_index)


def key_value_display(items: Dict[str, Any]) -> None:
    """Render a high-contrast key-value display panel."""
    html = '<div style="display: grid; grid-template-columns: auto 1fr; gap: 1rem; background: rgba(15, 23, 42, 0.4); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05);">'
    for key, value in items.items():
        html += f'''
        <div style="font-weight: 800; color: var(--primary-glow); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;">{key}</div>
        <div style="color: #cbd5e1; font-size: 0.95rem;">{value}</div>
        '''
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ===========================================================================
# UTILITIES
# ===========================================================================

def spacer(height: str = "1rem") -> None:
    st.markdown(f'<div style="height: {height};"></div>', unsafe_allow_html=True)


def tts_button(text: str, label: str = "Audio Intel", key: Optional[str] = None) -> None:
    """Enhanced TTS button with nebula styling."""
    import json
    safe_text = json.dumps(text.replace("\n", " "))
    button_uuid = key or f"tts_{hash(text) % 10**8}"
    
    js_code = f"""
    <style>
        .tts-btn {{
            background: rgba(99, 102, 241, 0.1);
            color: var(--primary-glow);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 8px;
            padding: 10px 18px;
            font-size: 0.8rem;
            font-weight: 800;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            display: inline-flex;
            align-items: center;
            gap: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}
        .tts-btn:hover {{
            background: rgba(99, 102, 241, 0.25);
            border-color: var(--primary-glow);
            box-shadow: 0 0 25px rgba(99, 102, 241, 0.4);
            transform: translateY(-2px);
            filter: brightness(1.1);
        }}
        .tts-btn:active {{
            transform: translateY(1px) scale(0.97);
            box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3);
            filter: brightness(0.9);
        }}
    </style>
    <button id="btn-{button_uuid}" class="tts-btn" onclick="toggleSpeech()">
        <span>{label}</span>
    </button>
    <script>
    var synth = window.speechSynthesis;
    var isSpeaking = false;
    function toggleSpeech() {{
        const btn = document.getElementById('btn-{button_uuid}');
        if (isSpeaking) {{
            synth.cancel(); isSpeaking = false;
            btn.innerHTML = '<span>{label}</span>';
        }} else {{
            synth.cancel();
            const utt = new SpeechSynthesisUtterance({safe_text});
            utt.onend = () => {{ isSpeaking = false; btn.innerHTML = '<span>{label}</span>'; }};
            synth.speak(utt); isSpeaking = true;
            btn.innerHTML = '<span>Stop</span>';
        }}
    }}
    </script>
    """
    st.components.v1.html(js_code, height=60)
