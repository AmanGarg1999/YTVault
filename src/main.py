import logging
import logging.handlers
import sys
from pathlib import Path

import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ensure_data_dirs, get_settings, DATA_DIR


def setup_logging(level: str = "INFO"):
    """Configure structured logging with console and file output."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create handlers
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
        datefmt="%H:%M:%S",
    ))

    handlers = [console_handler]

    # Add file handler (create data dir first)
    try:
        ensure_data_dirs()
        log_file = DATA_DIR / "kvault.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3,
        )
        file_handler.setLevel(logging.DEBUG)  # Always capture debug to file
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
        ))
        handlers.append(file_handler)
    except Exception:
        pass  # Don't fail startup if log file can't be created

    logging.basicConfig(level=log_level, handlers=handlers)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose):
    """knowledgeVault-YT — Local-first Research Intelligence System."""
    setup_logging("DEBUG" if verbose else "INFO")
    ensure_data_dirs()


@cli.command()
@click.argument("url")
def harvest(url):
    """Start a new harvest from a YouTube URL.

    URL can be a video, playlist, or channel URL.

    Examples:
        kvault harvest "https://youtube.com/@lexfridman"
        kvault harvest "https://youtube.com/watch?v=xxxxx"
        kvault harvest "https://youtube.com/playlist?list=xxxxx"
    """
    click.echo(f"🚀 Starting harvest: {url}")

    # Pre-flight: check Ollama availability
    from src.utils.health import require_ollama
    settings = get_settings()
    if not require_ollama(settings):
        click.echo("⚠️  Ollama is not running. LLM features will be unavailable.", err=True)
        if not click.confirm("Continue anyway (rule-based triage only)?"):
            return

    from src.pipeline.orchestrator import PipelineOrchestrator
    pipeline = PipelineOrchestrator()
    pipeline.set_callbacks(
        on_status=lambda msg: click.echo(f"  ├─ {msg}")
    )

    try:
        scan_id = pipeline.run(url)
        click.echo(f"✅ Harvest complete! Scan ID: {scan_id}")
    except Exception as e:
        click.echo(f"❌ Harvest failed: {e}", err=True)
        sys.exit(1)
    finally:
        pipeline.close()


@cli.command()
@click.argument("scan_id")
def resume(scan_id):
    """Resume an interrupted scan.

    Example:
        kvault resume abc12345
    """
    from src.pipeline.orchestrator import PipelineOrchestrator

    click.echo(f"🔄 Resuming scan: {scan_id}")
    pipeline = PipelineOrchestrator()
    pipeline.set_callbacks(
        on_status=lambda msg: click.echo(f"  ├─ {msg}")
    )

    try:
        pipeline.resume(scan_id)
        click.echo("✅ Resume complete!")
    except Exception as e:
        click.echo(f"❌ Resume failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("question")
@click.option("--format", "-f", "fmt", default="markdown",
              type=click.Choice(["markdown", "json", "csv"]),
              help="Output format")
def query(question, fmt):
    """Ask a research question across your knowledge vault.

    Example:
        kvault query "What did Naval Ravikant say about wealth creation?"
    """
    from src.intelligence.export import ExportEngine
    from src.intelligence.rag_engine import RAGEngine
    from src.storage.sqlite_store import SQLiteStore
    from src.storage.vector_store import VectorStore

    settings = get_settings()
    db = SQLiteStore(settings["sqlite"]["path"])
    vs = VectorStore()
    rag = RAGEngine(db, vs)
    exporter = ExportEngine(db)

    click.echo(f"🔍 Searching vault: {question}\n")
    response = rag.query(question)

    output = exporter.export_rag_response(response, fmt=fmt)
    click.echo(output)


@cli.command()
def stats():
    """Show pipeline statistics."""
    settings = get_settings()
    from src.storage.sqlite_store import SQLiteStore

    db = SQLiteStore(settings["sqlite"]["path"])
    pipeline_stats = db.get_pipeline_stats()

    click.echo("📊 knowledgeVault-YT Pipeline Statistics")
    click.echo("=" * 45)
    click.echo(f"  Channels:          {pipeline_stats.get('total_channels', 0)}")
    click.echo(f"  Total Videos:      {pipeline_stats.get('total_videos', 0)}")
    click.echo(f"  ├─ Accepted:       {pipeline_stats.get('accepted', 0)}")
    click.echo(f"  ├─ Rejected:       {pipeline_stats.get('rejected', 0)}")
    click.echo(f"  ├─ Pending Review: {pipeline_stats.get('pending_review', 0)}")
    click.echo(f"  Indexed Chunks:    {pipeline_stats.get('total_chunks', 0)}")
    click.echo(f"  Guests Identified: {pipeline_stats.get('total_guests', 0)}")


@cli.command()
def ui():
    """Launch the Streamlit Command Center UI."""
    import subprocess

    ui_path = Path(__file__).parent / "ui" / "app.py"
    click.echo("🖥️  Launching Command Center...")
    subprocess.run(
        ["streamlit", "run", str(ui_path),
         "--server.port", "8501",
         "--server.headless", "true"],
    )


@cli.command()
def scans():
    """List all scan checkpoints."""
    settings = get_settings()
    from src.storage.sqlite_store import SQLiteStore

    db = SQLiteStore(settings["sqlite"]["path"])
    active = db.get_active_scans()
    all_scans = db.conn.execute(
        "SELECT * FROM scan_checkpoints ORDER BY started_at DESC"
    ).fetchall()

    if not all_scans:
        click.echo("No scans found.")
        return

    click.echo("📋 Scan History")
    click.echo("=" * 70)
    for scan in all_scans:
        status_icon = {"IN_PROGRESS": "🔄", "COMPLETED": "✅", "FAILED": "❌"}.get(
            scan["status"], "❓"
        )
        click.echo(
            f"  {status_icon} {scan['scan_id']} │ {scan['scan_type']:8s} │ "
            f"{scan['total_processed']}/{scan['total_discovered']} │ "
            f"{scan['source_url'][:50]}"
        )


@cli.command()
def taxonomy():
    """Build hierarchical topic taxonomy from the knowledge graph."""
    from src.storage.graph_store import GraphStore
    from src.intelligence.taxonomy_builder import TaxonomyBuilder

    click.echo("🌳 Building topic taxonomy...")
    try:
        graph = GraphStore()
        builder = TaxonomyBuilder(graph)
        created = builder.build_taxonomy()
        graph.close()
        click.echo(f"✅ Taxonomy built: {created} SUBTOPIC_OF relationships created")
    except Exception as e:
        click.echo(f"❌ Taxonomy build failed: {e}", err=True)


@cli.command()
def health():
    """Check status of all external services."""
    from src.utils.health import check_all_services

    settings = get_settings()
    click.echo("🏥 Service Health Check")
    click.echo("=" * 45)

    results = check_all_services(settings)
    all_ok = True
    for name, status in results.items():
        icon = "✅" if status.available else "❌"
        click.echo(f"  {icon} {status.name}: {status.detail}")
        if not status.available:
            all_ok = False

    if all_ok:
        click.echo("\n✅ All services healthy!")
    else:
        click.echo("\n⚠️  Some services unavailable. Check logs for details.")


if __name__ == "__main__":
    cli()
