"""Export Center page for knowledgeVault-YT."""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(db):
    """Render the Export Center page."""
    st.markdown("""
    <div class="main-header">
        <h1>📤 Export Center</h1>
        <p>Export research data and pipeline statistics</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        from src.intelligence.export import ExportEngine
        exporter = ExportEngine(db)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Pipeline Statistics")
            if st.button("📊 Export Stats (Markdown)"):
                content = exporter.export_pipeline_stats()
                st.download_button("Download", content, "pipeline_stats.md")
                st.markdown(content)

        with col2:
            st.markdown("### Guest Registry")
            fmt = st.selectbox("Format", ["markdown", "json", "csv"], key="guest_fmt")
            if st.button("👤 Export Guests"):
                content = exporter.export_guests(fmt=fmt)
                ext = {"markdown": "md", "json": "json", "csv": "csv"}[fmt]
                st.download_button("Download", content, f"guests.{ext}")
                if fmt == "markdown":
                    st.markdown(content)
                else:
                    st.code(content)
    except Exception as e:
        st.error(f"Failed to load Export Center: {e}")
        logger.error(f"Export Center error: {e}", exc_info=True)
