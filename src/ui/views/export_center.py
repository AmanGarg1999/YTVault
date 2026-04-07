"""Export Center page for knowledgeVault-YT."""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render(db):
    """Render the Export Center page."""
    st.markdown("""
    <div class="main-header">
        <h1>Export Center</h1>
        <p>Export research data and pipeline statistics</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        from src.intelligence.export import ExportEngine
        exporter = ExportEngine(db)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Pipeline Statistics")
            if st.button("Export Stats (Markdown)"):
                content = exporter.export_pipeline_stats()
                st.download_button("Download", content, "pipeline_stats.md")
                st.markdown(content)

        with col2:
            st.markdown("### Guest Registry")
            fmt = st.selectbox("Format", ["markdown", "json", "csv"], key="guest_fmt")
            if st.button("Export Guests"):
                content = exporter.export_guests(fmt=fmt)
                ext = {"markdown": "md", "json": "json", "csv": "csv"}[fmt]
                st.download_button("Download", content, f"guests.{ext}")
                if fmt == "markdown":
                    st.markdown(content)
                else:
                    st.code(content)
        
        st.markdown("---")
        with st.expander("Obsidian Sync (Research Wiki)", expanded=True):
            st.markdown("""
            **Generate a complete research vault for Obsidian.**
            - Converts Claims, Bridges, and Clashes into linked notes.
            - Includes backlinks to Channels and Videos.
            - Uses Dataview-compatible metadata.
            """)
            
            from pathlib import Path
            default_obsidian_path = str(Path(db.db_path).parent / "obsidian_vault")
            obsidian_path = st.text_input("Output Directory", default_obsidian_path)
            
            if st.button("Sync to Obsidian Vault", type="primary"):
                try:
                    from src.utils.obsidian_exporter import ObsidianExporter
                    writer = ObsidianExporter(db, obsidian_path)
                    with st.spinner("Generating vault structure..."):
                        writer.export_all()
                    st.success(f"Vault exported successfully to: `{obsidian_path}`")
                except Exception as e:
                    st.error(f"Obsidian sync failed: {e}")
                    logger.error(f"Obsidian sync failed: {e}", exc_info=True)

    except Exception as e:
        st.error(f"Failed to load Export Center: {e}")
        logger.error(f"Export Center error: {e}", exc_info=True)
