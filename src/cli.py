import typer
import os
import shutil
import logging
from pathlib import Path
from rich.console import Console
from src.config import load_config
from src.db import init_db
from src.logger import setup_logging
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

# 0. Main Entry
@app.callback()
def main():
    """PaperPipe Automation Tool"""
    pass

# 1. Environment Doctor
@app.command()
def doctor():
    """Check environment, config, and dependencies."""
    console.print("[bold blue]🩺 Checking Environment...[/bold blue]")
    
    try:
        config = load_config()
        console.print("✅ Config loaded successfully.")
        console.print(f"   - Zotero Dir: {config.paths.zotero_base_dir}")
        console.print(f"   - Log Level: {config.system.log_level}")
    except Exception as e:
        console.print(f"❌ Config Error: {e}", style="bold red")
        return

    try:
        init_db()
        console.print("✅ Database initialized (state.db).")
    except Exception as e:
        console.print(f"❌ Database Error: {e}", style="bold red")
    
    if Path("logs/paperpipe.log").exists():
        console.print("✅ Log file accessible.")
    else:
        console.print("⚠️ Log file not found yet (will be created on first log).")

    console.print("[bold green]All systems go![/bold green]")
    logger.info("Doctor check completed.")

# 2. Simple Fetch Test
@app.command()
def test_fetch():
    """Test Fetch (PubMed + ArXiv)"""
    from src.fetchers import fetch_arxiv, fetch_pubmed
    
    config = load_config()
    keywords = [config.search.slots['mechanism'].query]
    
    console.print(f"[bold cyan]🔍 Testing fetch with query: {keywords}[/bold cyan]")
    
    console.print("\n[bold]Testing ArXiv...[/bold]")
    arxiv_papers = fetch_arxiv(keywords, max_results=3)
    for p in arxiv_papers:
        console.print(f" - [ArXiv] {p.title} ({p.published})")

    console.print("\n[bold]Testing PubMed...[/bold]")
    pubmed_papers = fetch_pubmed(keywords, max_results=3)
    for p in pubmed_papers:
        console.print(f" - [PubMed] {p.title} ({p.published})")

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
    open("logs/paperpipe.log", "w").close()
    console.print("✅ Logs cleared.")

@app.command()
def reset():
    """[DANGER] Reset DB, Logs, and Obsidian Data."""
    if not typer.confirm("⚠️  Are you sure you want to delete ALL data?"):
        console.print("❌ Cancelled.")
        raise typer.Abort()

    console.print("[bold red]🗑️  Resetting all data...[/bold red]")

    # 1. DB
    db_path = Path("state.db")
    if db_path.exists():
        db_path.unlink()
        console.print("   - Deleted state.db")
    
    # 2. Logs
    log_path = Path("logs/paperpipe.log")
    if log_path.exists():
        open(log_path, "w").close()
        console.print("   - Cleared logs")

    # 3. Obsidian
    try:
        config = load_config()
        vault_path = config.paths.obsidian_vault
        
        inbox_path = vault_path / "Inbox"
        if inbox_path.exists():
            shutil.rmtree(inbox_path)
            console.print(f"   - Deleted {inbox_path}")
            
        index_all = vault_path / config.paths.index_all
        if index_all.exists():
            index_all.unlink()
            console.print(f"   - Deleted {index_all}")
            
        index_clinical = vault_path / config.paths.index_clinical
        if index_clinical.exists():
            index_clinical.unlink()
            console.print(f"   - Deleted {index_clinical}")

    except Exception as e:
        console.print(f"   ⚠️  Failed to clean Obsidian vault: {e}")

    # 4. Re-init
    init_db()
    console.print("✅ Reset complete. System is clean.")

@app.command()
def test_unpaywall(doi: str = "10.1038/s41586-020-2165-8"):
    """Test Unpaywall API link fetching"""
    from src.downloader import _fetch_oa_link
    config = load_config()
    
    console.print(f"[bold cyan]🔍 Testing Unpaywall for DOI: {doi}[/bold cyan]")
    email = config.system.unpaywall_email
    console.print(f"   - Email: {email}")
    
    link = _fetch_oa_link(doi, email)
    if link:
        console.print(f"✅ Found OA Link: {link}")
    else:
        console.print("❌ No OA Link found (or API error).")

# 6. Watch Folder Service
@app.command()
def watch(path: str = typer.Option(None, help="Folder path to watch for new PDFs")):
    """Start Watch Folder Service for auto-processing local PDFs."""
    from src.watcher import run_watcher
    
    config = load_config()
    target_path = Path(path) if path else config.paths.upload_dir
    
    if not target_path:
        console.print("[bold red]❌ No watch folder configured. Pass --path or set upload_dir in config.[/bold red]")
        return
        
    if not target_path.exists():
        console.print(f"[bold yellow]⚠️ Watch folder {target_path} does not exist. Creating it...[/bold yellow]")
        target_path.mkdir(parents=True, exist_ok=True)
        
    console.print(f"[bold green]👀 Starting Watcher on: {target_path}[/bold green]")
    console.print("   (Press Ctrl+C to stop)")
    
    try:
        run_watcher(target_path, config)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Watcher stopped by user.[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Watcher Error: {e}[/bold red]")

if __name__ == "__main__":
    app()
