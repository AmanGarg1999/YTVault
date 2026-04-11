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

        st.markdown("---")
        st.markdown("### Bulk Research Packages")
        st.info("Export high-fidelity intelligence packages (transcripts, summaries, and claims) for multiple videos at once.")
        
        # 1. Selection
        all_accepted = db.get_videos_by_status("ACCEPTED", limit=1000)
        selected_vids = st.multiselect(
            "Select Videos for Export", 
            all_accepted, 
            format_func=lambda v: f"{v.title[:60]}...",
            key="bulk_exp_select"
        )
        
        col_fmt, col_exec = st.columns([1, 1])
        with col_fmt:
            bulk_fmt = st.radio("Output Format", ["markdown", "json"], horizontal=True, key="bulk_fmt")
        
        with col_exec:
            if st.button("Generate Bulk ZIP", type="primary", use_container_width=True, disabled=not selected_vids):
                # We'll simulate a zip or just offer them one by one if zip is too heavy for simple streamlit
                # Better: offer a combined Markdown file
                import io
                import zipfile
                
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for v in selected_vids:
                        content = exporter.export_video_package(v.video_id, fmt=bulk_fmt)
                        ext = "md" if bulk_fmt == "markdown" else "json"
                        zip_file.writestr(f"{v.video_id}.{ext}", content)
                
                st.download_button(
                    "Download Research Vault (.zip)",
                    buf.getvalue(),
                    f"vault_export_{datetime.now().strftime('%Y%m%d')}.zip",
                    "application/zip"
                )
        
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
