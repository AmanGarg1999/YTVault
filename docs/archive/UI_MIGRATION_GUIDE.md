# UI Migration Guide — Updating Pages to Professional Design System

This guide provides step-by-step instructions for migrating existing pages to the new professional UI/UX design system.

## Quick Start

### 1. Import UI Components

Add this to the top of your page module:

```python
from src.ui.components import (
    page_header,
    section_header,
    metric_grid,
    info_card,
    success_card,
    warning_card,
    error_card,
    status_badge,
    key_value_display,
    progress_step,
    loading_spinner,
    create_columns_equal,
    spacer,
)
```

### 2. Update Page Header

**Before**:
```python
st.markdown("""
<div class="main-header">
    <h1>🔍 Research Console</h1>
    <p>Hybrid RAG Search & Citation Export</p>
</div>
""", unsafe_allow_html=True)
```

**After**:
```python
page_header(
    title="Research Console",
    subtitle="Hybrid RAG Search & Citation Export",
    icon="🔍"
)
```

### 3. Add Section Headers

**Before**:
```python
st.markdown("### 🔍 Search Parameters")
```

**After**:
```python
section_header("Search Parameters", "️")
```

### 4. Replace Metrics

**Before**:
```python
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Videos", 1425)
with col2:
    st.metric("Chunks", 3847)
with col3:
    st.metric("Guests", 245)
```

**After**:
```python
metrics = [
    {"value": 1425, "label": "Videos", "icon": "🎬", "delta": "+12%", "delta_color": "positive"},
    {"value": 3847, "label": "Chunks", "icon": "📦"},
    {"value": 245, "label": "Guests", "icon": "👥"},
]
metric_grid(metrics, cols=3)
```

### 5. Replace Info/Alert Messages

**Before**:
```python
st.info("Processing complete!")
st.warning("High memory usage detected")
st.error("Connection failed")
```

**After**:
```python
info_card("Processing Complete", "All 45 videos have been indexed successfully.")
warning_card("High Memory Usage", "Current process using 78% of available RAM.")
error_card("Connection Failed", "Unable to reach Neo4j. Retrying in 30s...")
```

---

## Migration Patterns by Page Type

### Pattern 1: Dashboard/Analytics Page

```python
from src.ui.components import (
    page_header, section_header, metric_grid, 
    info_card, warning_card, spacer
)

def render(db):
    # Main header
    page_header("Analytics Dashboard", "View system metrics and performance", icon="📊")
    
    # Key metrics section
    section_header("System Overview", "📈")
    metrics = [
        {"value": db.count_videos(), "label": "Videos", "icon": "🎬"},
        {"value": db.count_chunks(), "label": "Chunks", "icon": "📦"},
    ]
    metric_grid(metrics, cols=2)
    spacer()
    
    # Status section
    st.divider()
    section_header("Status", "🔄")
    if db.is_healthy():
        info_card("System Healthy", "All services operational")
    else:
        warning_card("Degraded Mode", "One or more services unavailable")
```

### Pattern 2: Form/Input Page

```python
from src.ui.components import page_header, form_section, section_header

def render(db):
    page_header("Harvest Manager", "Configure and manage content ingestion", icon="🌾")
    
    # Configuration section
    form_section("Harvest Configuration", "Set parameters for automated discovery")
    url = st.text_input("YouTube Channel/Playlist URL")
    confidence = st.slider("Confidence Threshold", 0.0, 1.0, 0.7)
    
    # Advanced options
    with st.expander("️ Advanced Options"):
        max_workers = st.number_input("Max Workers", 1, 10, 3)
        skip_embeds = st.checkbox("Skip Embedding Generation")
    
    # Action
    if st.button("🚀 Start Harvest", use_container_width=True):
        process_harvest(url, confidence, max_workers, skip_embeds)
```

### Pattern 3: Monitor/Status Page

```python
from src.ui.components import (
    page_header, section_header, progress_step, 
    key_value_display, spacer
)

def render(db):
    page_header("Pipeline Monitor", "Real-time pipeline progress tracking", icon="📊")
    
    section_header("Current Scan", "🔄")
    scan = db.get_active_scan()
    
    if scan:
        # Progress tracking
        progress_step(1, 5, "Discovery", "completed")
        progress_step(2, 5, "Triage", "completed")
        progress_step(3, 5, "Transcript Fetch", "in_progress")
        progress_step(4, 5, "Refinement", "pending")
        progress_step(5, 5, "Indexing", "pending")
        
        spacer()
        st.divider()
        
        # Details
        section_header("Scan Details", "📋")
        key_value_display({
            "Scan ID": scan.scan_id,
            "Status": scan.status,
            "Progress": f"{scan.processed}/{scan.total} ({scan.percent:.0f}%)",
            "ETA": scan.eta_str,
        })
    else:
        info_card("No Active Scans", "All harvest operations are idle.")
```

### Pattern 4: Data Display/List Page

```python
from src.ui.components import (
    page_header, section_header, status_badge, 
    data_table, spacer
)

def render(db):
    page_header("Transcript Viewer", "Browse and search video transcripts", icon="📄")
    
    # Filter section
    section_header("Filters", "🔍")
    col1, col2 = st.columns(2)
    with col1:
        channel = st.multiselect("Channels", db.get_channels())
    with col2:
        status_filter = st.selectbox("Status", ["All", "Processed", "Pending"])
    
    spacer()
    st.divider()
    
    # Results section
    section_header("Transcripts", "📋")
    results = db.search_transcripts(channel=channel, status=status_filter)
    
    if results:
        data_table(results, columns=["title", "channel", "word_count", "created_at"])
    else:
        info_card("No Results", "Adjust filters to find more transcripts.")
```

---

## Common Component Replacements

### Replace st.success() / st.info() / st.warning() / st.error()

```python
# Old way
st.success("Operation completed")
st.info("This is informational")
st.warning("Use caution")
st.error("Something went wrong")

# New way
success_card("Operation Completed", "All 45 videos processed successfully.")
info_card("Information", "This is informational content.")
warning_card("Caution Required", "Use caution with the following action.")
error_card("Error Occurred", "Something went wrong: [details]")
```

### Replace Multiple st.metric() Calls

```python
# Old way
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Videos", 1425)
with c2:
    st.metric("Chunks", 3847)
with c3:
    st.metric("Guests", 245)
with c4:
    st.metric("Topics", 892)

# New way
metric_grid([
    {"value": 1425, "label": "Videos", "icon": "🎬"},
    {"value": 3847, "label": "Chunks", "icon": "📦"},
    {"value": 245, "label": "Guests", "icon": "👥"},
    {"value": 892, "label": "Topics", "icon": "🏷️"},
], cols=4)
```

### Replace Status/Badge Indicators

```python
# Old way
st.markdown(f"Status: **COMPLETED**")
st.markdown(f"Confidence: **87%**")

# New way
st.markdown(f"Status: {status_badge('success', 'Completed')}", unsafe_allow_html=True)
st.markdown(f"Confidence: {status_badge('info', '87%')}", unsafe_allow_html=True)
```

### Replace Simple Columns Layout

```python
# Old way
col1, col2, col3 = st.columns(3)
with col1:
    st.write("Content 1")
with col2:
    st.write("Content 2")
with col3:
    st.write("Content 3")

# New way
cols = create_columns_equal(3, gap="medium")
with cols[0]:
    st.write("Content 1")
with cols[1]:
    st.write("Content 2")
with cols[2]:
    st.write("Content 3")
```

---

## Migration Priority Order

Update pages in this order for best results:

1. **Priority 1 (Main Pages)** - Most visible, high impact
   - `dashboard.py` ( Already done)
   - `research.py` (Search/RAG interface)
   - `pipeline_monitor.py` (Status tracking)

2. **Priority 2 (Management Pages)** - Frequently used
   - `harvest.py` (Content ingestion)
   - `pipeline_control.py` (Pipeline management)
   - `data_management.py` (Data operations)

3. **Priority 3 (Supporting Pages)** - Lower frequency
   - `ambiguity.py` (Review queue)
   - `guest_intel.py` (Guest profiles)
   - `explorer.py` (Graph visualization)
   - `export_center.py` (Data export)
   - `logs_monitor.py` (Event logging)
   - `reject_review.py` (Rejection handling)
   - `transcript_viewer.py` (Transcript display)

---

## Testing Your Migrations

### Checklist

- [ ] Page imports UI components successfully
- [ ] Page header renders with icon and subtitle
- [ ] Section headers use consistent formatting
- [ ] Metrics display with proper delta indicators
- [ ] Status messages use semantic colors
- [ ] Forms have proper section organization
- [ ] Error messages include helpful context
- [ ] All links have proper contrast (WCAG AA)
- [ ] Keyboard navigation works (Tab, Enter, etc.)
- [ ] Responsive layout works on mobile sizes

### Local Testing

```bash
# Start the app locally
streamlit run src/ui/app.py

# Verify page loads without errors
# Check sidebar navigation
# Click through pages and verify styling
# Test form inputs
# Check error handling
```

---

## Troubleshooting

### Issue: Component import fails
**Solution**: Ensure `src/ui/components/__init__.py` exports all components

```python
from src.ui.components import page_header  # Should work
```

### Issue: Styling doesn't apply
**Solution**: Always use `unsafe_allow_html=True` for markdown with HTML/CSS

```python
# Wrong
st.markdown(response_html)

# Correct
st.markdown(response_html, unsafe_allow_html=True)
```

### Issue: Colors look wrong
**Solution**: Check if CSS variables are properly imported (`src/ui/app.py`)

### Issue: Layout shifts on scroll
**Solution**: Use consistent column gaps and avoid nested responsive containers

```python
# Better
cols = create_columns_equal(3, gap="medium")

# Avoid
st.columns(3)  # Default no-gap behavior
```

---

## Advanced: Creating Custom Components

If you need a page-specific component:

```python
# In pages/your_page.py
def custom_status_display(status, message):
    """Custom component for this page."""
    from src.ui.components import status_badge
    st.markdown(f"""
    <div style="
        background: rgba(30, 41, 59, 0.6);
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    ">
        {status_badge(status, message)}
    </div>
    """, unsafe_allow_html=True)
```

Then PR it to `src/ui/components/ui_helpers.py` if it's reusable!

---

## Questions?

Refer to:
- **Component API**: See `docs/UI_UX_DESIGN_SYSTEM.md`
- **Source Code**: `src/ui/components/ui_helpers.py`
- **Example**: `src/ui/pages/dashboard.py` (fully migrated)

---

**Last Updated**: April 2026
