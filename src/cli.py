import typer
import os
from pathlib import Path
from rich.console import Console
from src.config import load_config
from src.db_utils import (
    init_db as init_jobs_db,
    init_run_stats_table,
    DB_PATH as DB_UTILS_PATH,
)
from src.logger import setup_logging
from src.services.cli_workflows import (
    run_deepread_workflow,
    update_reading_status_workflow,
)
from src.services.profile_cli_workflows import (
    run_profiles_audit_workflow,
    run_profiles_chat_workflow,
)
from src.services.rag_cli_workflows import ask_question_workflow
from src.services.cli_system_workflows import (
    clear_logs_workflow,
    doctor_workflow,
    organize_workflow,
    reset_workflow,
    stats_workflow,
    test_unpaywall_workflow,
    watch_downloads_workflow,
    watch_workflow,
)
from src.services.cli_command_workflows import (
    export_workflow,
    fetch_workflow,
    process_test_workflow,
    reconcile_workflow,
    run_daily_workflow,
    test_fetch_workflow,
    test_filter_workflow,
)
from dotenv import load_dotenv

load_dotenv()

# [Clean API Key]
if os.getenv("OPENAI_API_KEY"):
    clean_key = os.getenv("OPENAI_API_KEY").strip().replace("\n", "").replace("\r", "")
    os.environ["OPENAI_API_KEY"] = clean_key

# Setup App & Logger
app = typer.Typer(no_args_is_help=True)
console = Console()

# Initialize Centralized Logger
try:
    config_initial = load_config()
    log_level = config_initial.system.log_level
except Exception:
    log_level = "INFO"

logger = setup_logging(log_level=log_level)


def bootstrap_database() -> Path:
    """Initialize canonical runtime schema (papers/review_queue/jobs/run_stats)."""
    from scripts.init_db import init_db as init_core_db

    init_core_db()
    init_jobs_db()
    init_run_stats_table()
    return DB_UTILS_PATH


# 0. Main Entry
@app.callback()
def main():
    """PaperPipe Automation Tool"""
    pass

# 1. Environment Doctor
@app.command()
def doctor():
    """Check environment, config, and dependencies."""
    doctor_workflow(console, bootstrap_database)
    logger.info("Doctor check completed.")


# 2. Simple Fetch Test
@app.command()
def test_fetch():
    """Test Fetch (Provider Pattern)"""
    test_fetch_workflow(console)

# 2.5 On-Demand Fetch
@app.command()
def fetch(
    query: str = typer.Option(..., "--query", "-q", help="Search query (e.g. 'CRISPR off-target')"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results per source"),
    save: bool = typer.Option(False, "--save", "-s", help="Save results to Obsidian/Database (Default: Dry Run)"),
):
    """[On-Demand] Search papers immediately. Default is Dry-Run (list only)."""
    fetch_workflow(query=query, limit=limit, save=save, console=console)

# 3. Process Test
# 3. Process Test
@app.command()
def process_test(force: bool = False):
    """Test Full Pipeline (Fetch -> Classify -> Tag). Use --force to ignore DB."""
    process_test_workflow(force=force, console=console)

@app.command()
def run():
    """[Production] Run Daily PaperPipe Routine."""
    run_daily_workflow(console)


# 4. Filter Test
@app.command()
def test_filter():
    """Test Title Filter Logic"""
    test_filter_workflow(console)

@app.command()
def clear_logs():
    """Clear log file"""
    clear_logs_workflow(console)


@app.command()
def reconcile(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply updates. Default is dry-run (no DB writes).",
    )
):
    """
    Reconcile paper statuses from approved decisions.
    """
    reconcile_workflow(apply=apply, console=console)

@app.command()
def reset():
    """[DANGER] Reset DB, Logs, and Obsidian Data."""
    if not typer.confirm("⚠️  Are you sure you want to delete ALL data?"):
        console.print("❌ Cancelled.")
        raise typer.Abort()
    reset_workflow(console, bootstrap_database, [DB_UTILS_PATH, Path("state.db")])

@app.command()
def test_unpaywall(doi: str = "10.1038/s41586-020-2165-8"):
    """Test Unpaywall API link fetching"""
    test_unpaywall_workflow(doi, console)

# 6. Watch Folder Service
@app.command()
def watch():
    """Start Watch Folder Service for auto-processing local PDFs."""
    watch_workflow(console)


@app.command()
def watch_downloads():
    """Watch Downloads folder and auto-match manual-required PDFs into storage."""
    watch_downloads_workflow(console)

@app.command()
def organize(target_dir: str = "."):
    """
    Organize PDF files in a directory into the Library structure.
    Renames files to {Year}_{Author}_{ShortTitle}.pdf and moves them to Library/{Year}/.
    """
    organize_workflow(target_dir, console)

@app.command()
def stats():
    """
    Show statistics of papers in the library (Reading Status).
    Reads from All Indexes (Main, OnDemand, Manual).
    """
    stats_workflow(console)


@app.command()
def read(
    identifier: str = typer.Argument(..., help="Paper ID, DOI, or Exact Title")
):
    """Mark a paper as 'Reading'."""
    update_reading_status_workflow(identifier, "Reading", console)

@app.command()
def done(
    identifier: str = typer.Argument(..., help="Paper ID, DOI, or Exact Title")
):
    """Mark a paper as 'Done'."""
    update_reading_status_workflow(identifier, "Done", console)

@app.command()
def deepread(
    identifier: str = typer.Argument(..., help="Paper ID or DOI"),
    verify: bool = typer.Option(False, "--verify", help="Run strict statistical verification on claims")
):
    """
    [v3.0] Run Agentic Deep Read pipeline: Ingest -> Index -> Read.
    Appends structured analysis to the Obsidian note.
    """
    run_deepread_workflow(identifier, verify, console)

@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask the RAG agent")
):
    """
    [v3.0] Query the local RAG knowledge base (storage/rag/).
    """
    ask_question_workflow(question, console)

# 7. Export Manager (Phase 2)
@app.command()
def export(
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="Overwrite existing files in Obsidian"),
):
    """
    [Phase 2] Export APPROVED/INDEXED papers to Obsidian Vault.
    Generates Markdown files with Frontmatter and Analysis.
    """
    export_workflow(overwrite=overwrite, console=console)


# 8. Profile Management (Milestone 4)
@app.command(name="profiles")
def profiles_chat(
    target_id: str = typer.Argument(None, help="Target Profile ID (optional, will ask if missing)"),
    prompt: str = typer.Argument(None, help="Natural language request (optional, will ask if missing)")
):
    """
    [v3.0] Chat with the Strict Data Librarian to update search profiles.
    """
    run_profiles_chat_workflow(target_id, prompt, console)

@app.command(name="audit")
def profiles_audit(
    days: int = typer.Option(7, help="Lookback window in days")
):
    """
    [v3.0] Audit profiles for performance issues (limit hits) & Auto-Fix.
    """
    run_profiles_audit_workflow(days, console)


if __name__ == "__main__":
    app()
