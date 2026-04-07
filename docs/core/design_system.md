# UI/UX Professional Design System

**knowledgeVault-YT** now features a comprehensive, enterprise-grade design system built on the ui-ux-pro-max-skill framework. This document outlines the design tokens, component library, and best practices for maintaining visual and interaction consistency.

## 🎨 Design System Overview

### Core Design Principles

1. **Professional & Trustworthy** — Clean, modern interface with scientific/analytical aesthetic
2. **Accessible** — WCAG 2.1 AA compliant with proper contrast ratios and keyboard navigation
3. **Consistent** — Unified component library ensures predictable user experience
4. **Responsive** — Works seamlessly across desktop, tablet, and mobile
5. **Performance** — Optimized rendering and minimal visual bloat

---

## 🎭 Color Palette

### Primary Colors (Cyan Blue)
- **Primary-50**: `#f0f9ff` — Lightest accent
- **Primary-100**: `#e0f2fe` — Light accent
- **Primary-500**: `#0ea5e9` — Primary action (links, buttons, focus)
- **Primary-600**: `#0284c7` — Button hover
- **Primary-700**: `#0369a1` — Button active
- **Primary-800**: `#075985` — Darker accents

### Semantic Colors
- **Success**: `#10b981` — Positive actions, completed states
- **Warning**: `#f59e0b` — Caution, review pending
- **Error**: `#ef4444` — Errors, critical alerts
- **Info**: `#3b82f6` — Informational, neutral states

### Neutral Palette (Dark Mode)
- **Neutral-50**: `#f9fafb` — Nearly white
- **Neutral-100**: `#f3f4f6` — Very light
- **Neutral-200**: `#e5e7eb` — Light
- **Neutral-300**: `#d1d5db` — Medium light
- **Neutral-400**: `#9ca3af` — Medium
- **Neutral-500**: `#6b7280` — Medium dark
- **Neutral-600**: `#4b5563` — Dark
- **Neutral-700**: `#2d3748` — Very dark
- **Neutral-800**: `#1f2937` — Nearly black
- **Neutral-900**: `#111827` — Darkest

### Usage

```python
# In CSS/Tailwind
background-color: var(--primary-500);  # Use CSS variables

# In Python/Streamlit
st.markdown(f'<span style="color: #0ea5e9;">Text</span>', unsafe_allow_html=True)
```

---

## 📐 Typography Scale

### Font Family
- **Display & Headlines**: `Inter` (sans-serif) with 300–800 weights
- **Code**: `JetBrains Mono` for technical content
- **Fallback**: System fonts (-apple-system, BlinkMacSystemFont, 'Segoe UI')

### Sizing & Weights

| Element | Size | Weight | Line Height | Letter Spacing |
|---------|------|--------|-------------|----------------|
| **H1** | 2.125rem (34px) | 700 | 1.2 | -0.02em |
| **H2** | 1.875rem (30px) | 700 | 1.25 | -0.01em |
| **H3** | 1.5rem (24px) | 600 | 1.33 | — |
| **H4** | 1.125rem (18px) | 600 | 1.5 | — |
| **Body** | 0.875/1rem (14/16px) | 400–600 | 1.6 | — |
| **Small** | 0.75rem (12px) | 500–600 | 1.5 | 0.05–0.1em |

### Usage

```python
# Proper semantic HTML in Streamlit
st.markdown("<h1>Main Heading</h1>", unsafe_allow_html=True)
st.markdown("#### Section Header", unsafe_allow_html=True)
st.caption("Supporting text — use for metadata")
```

---

## 🧩 Component Library

### 1. Page Headers

**Purpose**: Clearly identify current page and provide context.

```python
from src.ui.components import page_header

page_header(
    title="Research Console",
    subtitle="Hybrid RAG Search & Citation Export",
    icon="🔍",
    show_divider=True
)
```

**Output**:
- Large, gradient-styled header
- Optional subtitle below
- Built-in divider for separation
- Accessible contrast ratios

---

### 2. Section Headers

**Purpose**: Organize content within pages.

```python
from src.ui.components import section_header

section_header("System Overview", "📊")
section_header("Pipeline Progress", "📈")
```

---

### 3. Metric Cards & Grids

**Purpose**: Display KPIs and statistics.

```python
from src.ui.components import metric_card, metric_grid

# Single metric
metric_card(
    value=1425,
    label="Videos Processed",
    delta="+12%",
    delta_color="positive",
    icon=""
)

# Multiple metrics in grid
metrics = [
    {"value": 1425, "label": "Videos", "icon": "🎬", "delta": "+12%", "delta_color": "positive"},
    {"value": 3847, "label": "Chunks", "icon": "📦", "delta_color": "neutral"},
    {"value": 245, "label": "Guests", "icon": "👥", "delta_color": "positive"},
]
metric_grid(metrics, cols=3)
```

**Features**:
- Gradient background with hover effects
- Optional delta indicators (↑ positive, ↓ negative)
- Responsive column layout
- Semantic color coding

---

### 4. Status Badges

**Purpose**: Quick visual status indicators.

```python
from src.ui.components import status_badge, inline_status

# Inline in Markdown
st.markdown(f"Task {status_badge('success', 'Completed')}", unsafe_allow_html=True)

# Standalone
inline_status("warning", "Pending Review")
```

**Status Options**:
- `success` —  Complete, accepted, ready
- `warning` — ️ Review pending, caution needed
- `error` —  Failed, rejected
- `info` — ℹ️ Neutral state, informational

---

### 5. Informational Cards

**Purpose**: Highlight important messages with semantic styling.

```python
from src.ui.components import info_card, success_card, warning_card, error_card

info_card("Configuration", "All settings have been validated.")
success_card("Pipeline Ready", "12 scans queued and ready to process.")
warning_card("High Memory Usage", "Current processes using 78% of available RAM.")
error_card("Connection Failed", "Unable to reach Neo4j database. Retrying in 30s...")
```

**Styling**:
- Left border with semantic color
- Appropriate background tint
- Emoji icon prefix
- Readable text contrast

---

### 6. Progress Components

**Purpose**: Show pipeline progress and loading states.

```python
from src.ui.components import progress_step, loading_spinner

# Pipeline stages
progress_step(1, 5, "Discovery", status="completed")
progress_step(2, 5, "Triage", status="completed")
progress_step(3, 5, "Transcript Fetch", status="in_progress")
progress_step(4, 5, "Refinement", status="pending")
progress_step(5, 5, "Chunking & Embedding", status="pending")

# Loading state
loading_spinner("Processing your query...")
```

---

### 7. Data Display

**Purpose**: Structured presentation of tabular and key-value data.

```python
from src.ui.components import data_table, key_value_display

# Table display
data_table(dataframe, columns=["title", "channel", "processed_at"])

# Key-value pairs
key_value_display({
    "Status": "Processing",
    "Progress": "45/100",
    "ETA": "2m 30s",
    "Model": "llama3.1:8b"
})
```

---

### 8. Form Sections

**Purpose**: Organize and label form inputs.

```python
from src.ui.components import form_section

form_section("Search Parameters", "Refine your query with filters and options")
url = st.text_input("Channel or Video URL")
confidence_threshold = st.slider("Confidence Threshold", 0.0, 1.0, 0.7)
```

---

### 9. Layout Utilities

**Purpose**: Consistent spacing and column management.

```python
from src.ui.components import create_columns_equal, spacer

# Equal width columns
cols = create_columns_equal(3, gap="medium")
with cols[0]:
    st.write("Column 1")
with cols[1]:
    st.write("Column 2")
with cols[2]:
    st.write("Column 3")

# Vertical spacing
spacer("2rem")
```

---

## 🎯 Best Practices

### 1. Naming & Organization

```python
# Good: Descriptive organization
def render(db):
    page_header("Research Console", "Hybrid RAG Search", icon="🔍")
    
    with st.container():
        section_header("Search Configuration", "️")
        # Form controls here
    
    with st.container():
        section_header("Results", "📋")
        # Display results
```

### 2. Accessibility

 **DO**:
- Always include `unsafe_allow_html=True` when using styled markdown
- Use semantic HTML: `<strong>`, `<em>`, proper heading hierarchy
- Ensure 4.5:1+ contrast for text on backgrounds
- Include keyboard focus states

 **DON'T**:
- Nest focus-related styles excessively
- Use color alone to convey information
- Create interactive elements without keyboard support
- Ignore WCAG 2.1 guidelines

### 3. Responsive Design

Use Streamlit's native `st.columns()` and responsive breakpoints:

```python
# Mobile-friendly
if 'col_count' not in st.session_state:
    st.session_state.col_count = 3  # Default for desktop

cols = st.columns(st.session_state.col_count)
# Columns will wrap on narrow screens
```

### 4. Error Handling

Always provide context and recovery paths:

```python
try:
    result = complex_operation()
except Exception as e:
    error_card("Operation Failed", f"Could not complete: {str(e)[:100]}")
    with st.expander("🔍 Debug Details"):
        st.code(traceback.format_exc())
```

### 5. Consistent Emoji Usage

| Icon | Context | Usage |
|------|---------|-------|
| 🧠 | Branding | App name, primary identity |
| 📊 | Metrics | Dashboards, analytics, numbers |
| 📋 | Lists | Queues, pending items, forms |
| 🔍 | Search | Query, lookup, research |
|  | Success | Completed, accepted, ready |
| ️ | Warning | Caution, pending, needs attention |
|  | Error | Failed, rejected, error |
| 🔄 | Loading | Processing, in-progress |
| 📈 | Progress | Growth, improvement, trending |
| 🎯 | Actions | CTA buttons, focus areas |

---

## 📦 Updating Existing Pages

### Migration Example

**Before (Basic Styling)**:
```python
st.markdown("### 📊 Metrics")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Videos", 1425)
with col2:
    st.metric("Chunks", 3847)
with col3:
    st.metric("Guests", 245)
```

**After (Professional Design System)**:
```python
from src.ui.components import section_header, metric_grid

section_header("Metrics", "📊")
metrics = [
    {"value": 1425, "label": "Videos", "icon": "🎬", "delta": "+12%", "delta_color": "positive"},
    {"value": 3847, "label": "Chunks", "icon": "📦"},
    {"value": 245, "label": "Guests", "icon": "👥"},
]
metric_grid(metrics, cols=3)
```

---

## 🎨 Customization

### Adding Custom Colors

Edit the CSS variables in `src/ui/app.py`:

```css
:root {
    --primary-500: #0ea5e9;  /* Change primary color */
    --success-500: #10b981;  /* Change success color */
}
```

### Modifying Component Styles

Override in `src/ui/components/ui_helpers.py`:

```python
def metric_card(...):
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #custom-color-1, #custom-color-2);
        ...
    ">
    """, unsafe_allow_html=True)
```

---

## 📖 Component API Reference

### All Available Components

```python
from src.ui.components import (
    # Headers
    page_header,
    section_header,
    
    # Metrics
    metric_card,
    metric_grid,
    
    # Status
    status_badge,
    inline_status,
    
    # Cards
    info_card,
    success_card,
    warning_card,
    error_card,
    
    # Progress
    progress_step,
    loading_spinner,
    
    # Data
    data_table,
    key_value_display,
    
    # Forms
    form_section,
    
    # Utilities
    create_columns_equal,
    spacer,
)
```

---

## 🚀 Performance Tips

1. **Use `@st.cache_resource` for expensive UI computations**
2. **Lazy-load components in expanders for complex content**
3. **Minimize HTML/markdown rendering complexity**
4. **Batch component updates when possible**

---

## 🤝 Contributing

When adding new UI components:

1. Create in `src/ui/components/ui_helpers.py`
2. Export in `src/ui/components/__init__.py`
3. Document with docstrings and usage examples
4. Test accessibility with keyboard navigation
5. Verify color contrast ratios (WCAG 2.1 AA)
6. Update this documentation

---

## 📚 Resources

- **Streamlit Docs**: https://docs.streamlit.io
- **WCAG 2.1 Guidelines**: https://www.w3.org/WAI/WCAG21/quickref/
- **Inter Font**: https://rsms.me/inter/
- **Color Playground**: https://www.tailwindcss.com/resources/tailwindcss-cheat-sheet

---

**Last Updated**: April 2026  
**Design System Version**: 1.0 (ui-ux-pro-max-skill)  
**Status**: Production Ready 
