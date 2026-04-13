"""Export Center page for knowledgeVault-YT."""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


from src.ui.components import page_header, section_header

def render(db):
    """Render the Export Center page."""
    page_header("Export Center", "Export research data and pipeline statistics")

    try:
        from src.intelligence.export import ExportEngine
        exporter = ExportEngine(db)

        col1, col2 = st.columns(2)

        with col1:
            section_header("Pipeline Statistics")
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
                import io
                import zipfile
                from datetime import datetime
                
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
        st.markdown("### Mission Briefings & Collaboration")
        st.caption("Export research chat sessions as formal briefings or sync intelligence missions with other investigators.")

        tab_brief, tab_sync = st.tabs(["Individual Briefings", "Collaboration Sync"])

        with tab_brief:
            sessions = db.get_chat_sessions(limit=100)
            if sessions:
                col_s1, col_s2 = st.columns([2, 1])
                with col_s1:
                    selected_session = st.selectbox(
                        "Select Research Session", 
                        sessions, 
                        format_func=lambda s: f"{s.name} ({s.created_at[:10]})",
                        key="brief_session_select"
                    )
                with col_s2:
                    brief_fmt = st.selectbox("Format", ["markdown", "json"], key="brief_fmt")
                
                if st.button("Generate Briefing", type="primary", use_container_width=True):
                    brief_content = exporter.export_chat_session(selected_session.session_id, fmt=brief_fmt)
                    ext = "md" if brief_fmt == "markdown" else "json"
                    file_name = f"briefing_{selected_session.name.replace(' ', '_').lower()}.{ext}"
                    st.download_button("Download Mission Briefing", brief_content, file_name, use_container_width=True)
                    if brief_fmt == "markdown":
                        with st.expander("Preview Briefing"):
                            st.markdown(brief_content)
            else:
                st.info("No research chat sessions found. Start a conversation in the Research Chat Hub to generate briefings.")

        with tab_sync:
            col_sync1, col_sync2 = st.columns(2)
            
            with col_sync1:
                st.markdown("#### Export Mission Package")
                if sessions:
                    sync_vids = st.multiselect(
                        "Select Missions to Sync", 
                        sessions, 
                        format_func=lambda s: s.name,
                        key="sync_session_select"
                    )
                    if st.button("Generate Mission Package (.json)", type="primary", disabled=not sync_vids, use_container_width=True):
                        pkg = exporter.export_mission_package([s.session_id for s in sync_vids])
                        st.download_button(
                            "Download Package", 
                            pkg, 
                            f"mission_package_{datetime.now().strftime('%Y%m%d')}.json",
                            use_container_width=True
                        )
                else:
                    st.caption("No missions available to sync.")

            with col_sync2:
                st.markdown("#### Import Mission Package")
                uploaded_file = st.file_uploader("Upload .json Mission Package", type=["json"])
                if uploaded_file:
                    if st.button("Execute Import", type="secondary", use_container_width=True):
                        import_data = uploaded_file.read().decode("utf-8")
                        result = exporter.import_mission_package(import_data)
                        if result["success"]:
                            st.success(f"Successfully validated Mission Package! Found {result['missions_count']} missions ready for synchronization.")
                            st.toast("Collaboration Sync: Integrity Verified.", icon="✦")
                        else:
                            st.error(f"Import Failed: {result['error']}")

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
