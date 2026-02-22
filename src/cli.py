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
    from src.fetch import get_fetchers
    
    config = load_config()
    keywords = [config.search.slots['mechanism'].query] # Keep it as list for logging, but fetch takes str
    query_str = keywords[0] # Simple test
    
    console.print(f"[bold cyan]🔍 Testing fetch with query: {query_str}[/bold cyan]")
    
    fetchers = get_fetchers(config)
    console.print(f"Loaded Fetchers: {[f.source_name for f in fetchers]}")
    
    for fetcher in fetchers:
        console.print(f"\n[bold]Testing {fetcher.source_name}...[/bold]")
        try:
            papers = fetcher.fetch(query_str, max_results=3)
            for p in papers:
                 console.print(f" - [{fetcher.source_name}] {p.title} ({p.published})")
        except Exception as e:
            console.print(f"[red]Error fetching from {fetcher.source_name}: {e}[/red]")

            console.print(f"[red]Error fetching from {fetcher.source_name}: {e}[/red]")

# 2.5 On-Demand Fetch
@app.command()
def fetch(
    query: str = typer.Option(..., "--query", "-q", help="Search query (e.g. 'CRISPR off-target')"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results per source"),
    save: bool = typer.Option(False, "--save", "-s", help="Save results to Obsidian/Database (Default: Dry Run)"),
):
    """[On-Demand] Search papers immediately. Default is Dry-Run (list only)."""
    from src.processor import process_on_demand_search
    
    console.print(f"[bold cyan]🚀 Fetching papers for: '{query}'[/bold cyan]")
    if save:
        console.print("[bold yellow]💾 Save Mode: ON (Will download & create notes)[/bold yellow]")
    else:
        console.print("[bold green]👀 Dry-Run Mode: List only[/bold green]")
        
    results = process_on_demand_search(query, limit, dry_run=not save)
    
    if not results:
        console.print("[bold red]❌ No results found.[/bold red]")
        return
        
    console.print(f"\n[bold]✅ Found {len(results)} papers:[/bold]")
    for idx, item in enumerate(results, 1):
        # Result can be Paper object (dry-run) or Dict (saved)
        if isinstance(item, dict):
             title = item.get('title', 'No Title')
             date = item.get('published', 'Unknown')
             source = item.get('source', 'Unknown')
             link = item.get('doi') or item.get('link')
             score_val = item.get('manual_rank_score')
        else:
             # Paper object
             title = item.title
             date = item.published
             source = item.source
             link = item.id
             score_val = item.manual_rank_score
             
        score_str = f" [bold magenta](Score: {score_val:.2f})[/bold magenta]" if score_val else ""
        console.print(f"{idx}. [{source}] {title} ({date}){score_str} - {link}")
    
    if save and results:
        console.print(f"\n[bold blue]✨ Saved {len(results)} papers to 'Inbox/OnDemand'[/bold blue]")

# 3. Process Test
# 3. Process Test
@app.command()
def process_test(force: bool = False):
    """Test Full Pipeline (Fetch -> Classify -> Tag). Use --force to ignore DB."""
    from src.processor import process_daily_slots
    
    if force:
        console.print("[bold yellow]⚠️ Running in FORCE mode: Ignoring DB duplicates.[/bold yellow]")
    
    results = process_daily_slots(ignore_db=force)
    _print_results(results)

@app.command()
def run():
    """[Production] Run Daily PaperPipe Routine."""
    from src.processor import process_daily_slots
    from src.reporting import generate_daily_report # [NEW]
    from src.config import load_config
    
    console.print("[bold green]🚀 Starting Production Run...[/bold green]")
    results = process_daily_slots(ignore_db=False)
    
    # [NEW] Generate SLA Report
    if results:
        config = load_config()
        report_path = generate_daily_report(results, config)
        if report_path:
            console.print(f"[bold blue]📊 SLA Report generated: {report_path}[/bold blue]")

    _print_results(results)

def _print_results(results):
    console.print("\n[bold green]📊 Daily Slot Report[/bold green]")
    
    if not results:
        console.print("[bold red]❌ No papers selected.[/bold red]")
        return

    for p in results:
        icon = "🏥" if p.get('trial_data') else "📝"
        console.print(f"\n{icon} [{p['slot']}] {p['title']}")
        
        one_liner = p.get('ai_one_liner') or "⚠️ No AI Summary (Fallback)"
        console.print(f"   💡 One-Liner: {one_liner}")

        if p.get('trial_data'):
            console.print("   💊 [bold cyan]Clinical Data Extracted:[/bold cyan]")
            for key, val in p['trial_data'].items():
                console.print(f"      - {key}: {val}")


# 4. Filter Test
@app.command()
def test_filter():
    """Test Title Filter Logic"""
    test_titles = [
        "Basic Science and Pathogenesis.",
        "Drug Development.",
        "Clinical Manifestations.",
        "Chapter 1: Introduction",
        "Section 5. Results",
        "Valid Paper Title About Neuroscience",
        "A very long title that should pass even if it ends with.",
        "Short title without dot"
    ]
    
    console.print("[bold]🧪 Testing Junk Title Filter Logic...[/bold]")
    
    for title in test_titles:
        title_clean = title.strip()
        word_count = len(title_clean.split())
        
        is_junk_short = (word_count <= 4 and title_clean.endswith('.'))
        junk_keywords = ["Chapter", "Section", "Part", "Index", "Preface", "Table of Contents"]
        is_junk_keyword = (word_count <= 5 and any(k in title_clean for k in junk_keywords))
        
        if is_junk_short:
            console.print(f"❌ [red]FILTERED (Short)[/red]: '{title}'")
        elif is_junk_keyword:
            console.print(f"❌ [red]FILTERED (Keyword)[/red]: '{title}'")
        else:
            console.print(f"✅ [green]PASSED[/green]: '{title}'")

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
    from src.db_utils import reconcile_approved_decisions

    dry_run = not apply
    result = reconcile_approved_decisions(dry_run=dry_run)

    mode = "DRY-RUN" if dry_run else "APPLY"
    console.print(f"[bold cyan]🔧 Reconcile Mode: {mode}[/bold cyan]")
    console.print(f"   - Candidates: {result['candidate_count']}")
    console.print(f"   - Updated: {result['updated_count']}")

    if not result["candidates"]:
        console.print("[green]✅ No reconciliation needed.[/green]")
        return

    for item in result["candidates"]:
        console.print(
            f" - {item['paper_id']}: {item['old_status']} -> APPROVED "
            f"(source={item['source']})"
        )

    if dry_run:
        console.print("[yellow]ℹ️ Re-run with --apply to persist changes.[/yellow]")

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
    from src.exporter import run_export
    
    console.print(f"[bold cyan]📤 Starting Export to Obsidian...[/bold cyan]")
    if overwrite:
        console.print("[yellow]⚠️  Overwrite Mode: ON[/yellow]")
        
    run_export(overwrite=overwrite)
    
    console.print("[bold green]✅ Export Complete.[/bold green]")


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
