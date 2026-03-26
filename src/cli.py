import typer
import os
import shutil
import logging
import socket
import subprocess
import sys
import time
import webbrowser
import json
from pathlib import Path
import requests
import yaml
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
from dotenv import load_dotenv

load_dotenv()

# [Clean API Key]
if os.getenv("OPENAI_API_KEY"):
    clean_key = os.getenv("OPENAI_API_KEY").strip().replace("\n", "").replace("\r", "")
    os.environ["OPENAI_API_KEY"] = clean_key

# Setup App & Logger
app = typer.Typer(no_args_is_help=True)
research_dna_app = typer.Typer(no_args_is_help=True)
console = Console()

# Initialize Centralized Logger
try:
    config_initial = load_config()
    log_level = config_initial.system.log_level
except Exception:
    log_level = "INFO"

logger = setup_logging(log_level=log_level)


def _emit_json(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def bootstrap_database() -> Path:
    """Initialize canonical runtime schema (papers/review_queue/jobs/run_stats)."""
    from scripts.init_db import init_db as init_core_db

    init_core_db()
    init_jobs_db()
    init_run_stats_table()
    return DB_UTILS_PATH


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _wait_for_health(base_url: str, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return False


def _terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


# 0. Main Entry
@app.callback()
def main():
    """PaperPipe Automation Tool"""
    pass


app.add_typer(research_dna_app, name="research-dna")

# 1. Environment Doctor
@app.command()
def doctor():
    """Check environment, config, and dependencies."""
    console.print("[bold blue]🩺 Checking Environment...[/bold blue]")
    llm_mode = "local"
    
    try:
        config = load_config()
        console.print("✅ Config loaded successfully.")
        console.print(f"   - Zotero Dir: {config.paths.zotero_base_dir}")
        console.print(f"   - Log Level: {config.system.log_level}")
        
        # [NEW] Check Watch Folder
        if config.paths.watch_folder:
            if config.paths.watch_folder.exists():
                console.print(f"   - Watch Folder: ✅ Found ({config.paths.watch_folder})")
            else:
                console.print(f"   - Watch Folder: ⚠️ Configured but missing ({config.paths.watch_folder})")
        else:
            console.print("   - Watch Folder: ⚪ Not configured")

        # [NEW] Check Unpaywall
        if config.system.unpaywall_email and "example.com" not in config.system.unpaywall_email:
             console.print(f"   - Unpaywall: ✅ Email configured ({config.system.unpaywall_email})")
        else:
             console.print("   - Unpaywall: ⚠️ Email missing or default")

        # [NEW] Check Bibliometrics
        if config.ranking.bibliometrics.enabled:
             console.print("   - Bibliometrics: ✅ Enabled (OpenAlex)")
        else:
             console.print("   - Bibliometrics: ⚪ Disabled")

        # [NEW] Check LLM & Ollama
        try:
            llm_config = config.llm
            
            # Helper to check mode safely
            llm_mode = getattr(llm_config, "mode", "local")
            
            if llm_mode in ["local", "hybrid"]:
                 console.print(f"   - LLM Mode: [bold cyan]{llm_mode}[/bold cyan] (Ollama Active)")
                 if hasattr(llm_config, 'local') and llm_config.local:
                     url = llm_config.local.base_url
                     try:
                         import ollama
                         # Check basic connectivity
                         client = ollama.Client(host=url)
                         try:
                             client.list()
                             console.print(f"   - Ollama: ✅ Connected ({url})")
                         except Exception as conn_err:
                             console.print(f"   - Ollama: ❌ Connection Failed ({url}) - {conn_err}", style="red")
                     except ImportError:
                         console.print("   - Ollama: ⚠️ 'ollama' package not installed.", style="yellow")
            else:
                 console.print(f"   - LLM Mode: {llm_mode} (Cloud Only)")
                 
        except Exception as e:
            console.print(f"   - LLM Check: ⚠️ Error checking LLM config: {e}")

    except Exception as e:
        console.print(f"❌ Config Error: {e}", style="bold red")
        return

    try:
        db_path = bootstrap_database()
        console.print(f"✅ Database initialized ({db_path}).")
    except Exception as e:
        console.print(f"❌ Database Error: {e}", style="bold red")
    
    # Check OpenAI Key (mode-aware)
    openai_key = os.getenv("OPENAI_API_KEY")
    if llm_mode == "cloud":
        if openai_key:
            console.print("✅ OpenAI API Key detected.")
        else:
            console.print("❌ OpenAI API Key missing! (required for cloud mode)", style="bold red")
    elif llm_mode == "hybrid":
        if openai_key:
            console.print("✅ OpenAI API Key detected. (hybrid cloud path available)")
        else:
            console.print("⚠️ OpenAI API Key missing. (hybrid cloud path disabled)", style="yellow")
    else:
        if openai_key:
            console.print("✅ OpenAI API Key detected. (optional in local mode)")
        else:
            console.print("ℹ️ OpenAI API Key not required in local mode.")

    if Path("logs/paperpipe.log").exists():
        console.print("✅ Log file accessible.")
    else:
        console.print("⚠️ Log file not found yet (will be created on first log).")

    console.print("[bold green]All systems go![/bold green]")
    logger.info("Doctor check completed.")


@app.command()
def start(
    host: str = typer.Option("127.0.0.1", "--host", help="Backend bind host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Backend bind port"),
    ui_url: str = typer.Option("", "--ui-url", help="UI URL to open. Empty means /ui."),
    health_timeout: int = typer.Option(15, "--health-timeout", min=3, max=120, help="Healthcheck timeout in seconds."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not auto-open browser."),
):
    """
    Start local backend runtime and open Lattice UI/docs.
    """
    console.print("[bold green]🚀 Starting Lattice runtime...[/bold green]")

    try:
        load_config()
        db_path = bootstrap_database()
        console.print("   - Preflight config: ✅")
        console.print(f"   - Runtime DB: ✅ ({db_path})")
    except Exception as exc:
        console.print(f"[bold red]❌ Preflight failed: {exc}[/bold red]")
        raise typer.Exit(code=1)

    if not _is_port_available(host, port):
        console.print(f"[bold red]❌ Port already in use: {host}:{port}[/bold red]")
        console.print("   Try another port: --port 8001")
        raise typer.Exit(code=1)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    try:
        proc = subprocess.Popen(cmd)
    except Exception as exc:
        console.print(f"[bold red]❌ Failed to start backend: {exc}[/bold red]")
        raise typer.Exit(code=1)

    base_url = f"http://{host}:{port}"
    if not _wait_for_health(base_url, health_timeout):
        _terminate_process(proc)
        console.print(
            f"[bold red]❌ Healthcheck timeout after {health_timeout}s: {base_url}/health[/bold red]"
        )
        raise typer.Exit(code=1)

    entry_url = ui_url.strip() or f"{base_url}/ui"
    console.print(f"   - Backend: ✅ {base_url}")
    console.print(f"   - Entry: {entry_url}")

    if not no_open:
        try:
            webbrowser.open(entry_url, new=2)
        except Exception as exc:
            console.print(f"[yellow]⚠️ Failed to open browser automatically: {exc}[/yellow]")

    console.print("   (Press Ctrl+C to stop)")

    try:
        while True:
            return_code = proc.poll()
            if return_code is None:
                time.sleep(0.5)
                continue
            if return_code == 0:
                console.print("[yellow]⚠️ Backend exited.[/yellow]")
                raise typer.Exit(code=0)
            console.print(f"[bold red]❌ Backend exited with code {return_code}[/bold red]")
            raise typer.Exit(code=return_code)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Stopping Lattice runtime...[/bold yellow]")
    finally:
        _terminate_process(proc)


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
    open("logs/paperpipe.log", "w").close()
    console.print("✅ Logs cleared.")


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

    console.print("[bold red]🗑️  Resetting all data...[/bold red]")

    # 1. DB
    db_paths = [DB_UTILS_PATH, Path("state.db")]
    seen = set()
    for db_path in db_paths:
        db_path = Path(db_path)
        if str(db_path) in seen:
            continue
        seen.add(str(db_path))
        if db_path.exists():
            db_path.unlink()
            console.print(f"   - Deleted {db_path}")
    
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
    db_path = bootstrap_database()
    console.print(f"✅ Reset complete. System is clean. ({db_path})")

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
def watch():
    """Start Watch Folder Service for auto-processing local PDFs."""
    from src.watcher import WatcherService
    from src.processor import Processor # We need a Processor class or module
    # Actually processor.py is a module with functions. 
    # The WatcherService expects an object with `process_local_pdf`.
    # Let's create a simple wrapper or just pass the module if it has the function.
    import src.processor as processor_module

    config = load_config()
    
    console.print(f"[bold green]👀 Starting Watcher Service...[/bold green]")
    console.print(f"   - Folder: {config.paths.watch_folder}")
    console.print("   (Press Ctrl+C to stop)")
    
    service = WatcherService(config)
    try:
        service.start(processor_module)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Watcher stopped by user.[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Watcher Error: {e}[/bold red]")


@app.command()
def watch_downloads():
    """Watch Downloads folder and auto-match manual-required PDFs into storage."""
    from src.downloads_watcher import DownloadsWatcherService

    config = load_config()
    watch_dir = config.paths.downloads_watch_dir
    storage_dir = config.paths.pdf_storage_dir

    console.print("[bold green]👀 Starting Downloads Watcher...[/bold green]")
    console.print(f"   - Downloads Dir: {watch_dir}")
    console.print(f"   - PDF Storage Dir: {storage_dir}")
    console.print("   (Press Ctrl+C to stop)")

    service = DownloadsWatcherService(
        downloads_watch_dir=watch_dir,
        pdf_storage_dir=storage_dir,
        title_threshold=0.90,
    )
    try:
        service.start()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Downloads watcher stopped by user.[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Downloads watcher error: {e}[/bold red]")

@app.command()
def organize(target_dir: str = "."):
    """
    Organize PDF files in a directory into the Library structure.
    Renames files to {Year}_{Author}_{ShortTitle}.pdf and moves them to Library/{Year}/.
    """
    import shutil
    import datetime
    from pathlib import Path
    from src.utils import create_paper_from_pdf, generate_filename
    from src.config import load_config
    
    config = load_config()
    target = Path(target_dir).expanduser()
    
    if not target.exists():
        console.print(f"[bold red]❌ Target directory not found: {target}[/bold red]")
        return
        
    pdfs = list(target.glob("*.pdf"))
    if not pdfs:
        console.print(f"[yellow]⚠️ No PDF files found in {target}[/yellow]")
        return
        
    console.print(f"[bold green]📦 Organizing {len(pdfs)} PDFs from: {target}[/bold green]")
    console.print(f"   -> Destination: {config.paths.library_dir}")
    
    success_count = 0
    fail_count = 0
    
    for pdf in pdfs:
        try:
            # 1. Create Paper (Extract Metadata)
            paper = create_paper_from_pdf(pdf)
            
            # 2. Generate Filename & Path
            new_name = generate_filename(paper)
            year = paper.published[:4] if paper.published and len(paper.published) >= 4 else "Unknown"
            
            year_dir = config.paths.library_dir / year
            year_dir.mkdir(parents=True, exist_ok=True)
            
            final_path = year_dir / new_name
            
            # Handle duplicates
            if final_path.exists() and final_path.resolve() != pdf.resolve():
                 # If same file content (size check for speed), skip?
                 # Better to just rename if unsure.
                 timestamp = datetime.datetime.now().strftime("%H%M%S")
                 final_path = year_dir / f"{final_path.stem}_{timestamp}{final_path.suffix}"
            
            if final_path.resolve() == pdf.resolve():
                console.print(f"   ⏭️  Already organized: {pdf.name}")
                continue
                
            shutil.move(pdf, final_path)
            console.print(f"   ✅ {pdf.name} -> {year}/{new_name}")
            success_count += 1
            
        except Exception as e:
            console.print(f"   ❌ Failed to organize {pdf.name}: {e}")
            fail_count += 1
            
    console.print(f"\n[bold]🎉 Done! Organized: {success_count}, Failed: {fail_count}[/bold]")

@app.command()
def stats():
    """
    Show statistics of papers in the library (Reading Status).
    Reads from All Indexes (Main, OnDemand, Manual).
    """
    import csv
    from collections import Counter
    from rich.table import Table
    from src.config import load_config
    
    config = load_config()
    vault_path = config.paths.obsidian_vault
    
    # Define potential indexes
    potential_indexes = [
        config.paths.index_all, # 00_Index/paper_collection.csv
        "00_Index/on_demand.csv",
        "00_Index/manual_collection.csv"
    ]
    
    status_counts = Counter()
    total = 0
    scanned_files = 0
    
    for relative_idx_path in potential_indexes:
        index_path = vault_path / relative_idx_path
        
        if not index_path.exists():
            continue
            
        scanned_files += 1
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    s = row.get('Status', 'Unknown').strip() or 'Unknown'
                    # Normalization
                    if s.lower() == 'to read': s = 'Inbox'
                    
                    status_counts[s] += 1
                    total += 1
        except Exception as e:
            console.print(f"[red]❌ Failed to read index {relative_idx_path}: {e}[/red]")

    if scanned_files == 0:
        console.print(f"[yellow]⚠️  No index files found in {vault_path}[/yellow]")
        return
        
    table = Table(title=f"📚 Library Stats (Total: {total})", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right", style="white")
    table.add_column("Percentage", justify="right", style="green")
    
    # Sort by predefined order
    order = ["Inbox", "Reading", "Done", "Unknown"]
    
    for s in order:
        if status_counts[s] > 0 or s in ["Inbox", "Reading", "Done"]: # Show zeros for main statuses
            count = status_counts[s]
            pct = (count / total * 100) if total > 0 else 0
            table.add_row(s, str(count), f"{pct:.1f}%")
            if s in status_counts: del status_counts[s]
            
    # Remaining
    for s, count in status_counts.items():
        pct = (count / total * 100) if total > 0 else 0
        table.add_row(s, str(count), f"{pct:.1f}%")
        
    console.print(table)


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
    verify: bool = typer.Option(False, "--verify", help="Run strict statistical verification on claims"),
    reader_timeout_sec: int = typer.Option(
        0,
        "--reader-timeout-sec",
        min=0,
        help="Reader step timeout seconds (0 = auto budget)",
    ),
    stats_timeout_sec: int = typer.Option(
        0,
        "--stats-timeout-sec",
        min=0,
        help="Stats verification step timeout seconds (0 = auto budget)",
    ),
    adaptive_step_timeout: bool = typer.Option(
        True,
        "--adaptive-step-timeout/--no-adaptive-step-timeout",
        help="Use page/table aware adaptive timeout budget.",
    ),
):
    """
    [v3.0] Run Agentic Deep Read pipeline: Ingest -> Index -> Read.
    Appends structured analysis to the Obsidian note.
    """
    run_deepread_workflow(
        identifier,
        verify,
        console,
        reader_timeout_sec=reader_timeout_sec,
        stats_timeout_sec=stats_timeout_sec,
        adaptive_step_timeout=adaptive_step_timeout,
    )


@app.command(name="repair-stats")
def repair_stats(
    paper_id: list[str] = typer.Option(
        [],
        "--paper-id",
        help="Target paper id (repeatable). Default uses curated 3-paper set.",
    ),
    run_id: str = typer.Option("", "--run-id", help="Optional run id override."),
    artifacts_root: str = typer.Option(
        "storage/artifacts",
        "--artifacts-root",
        help="Artifacts root directory.",
    ),
    max_checks: int = typer.Option(6, "--max-checks", min=1, help="Max checks per paper."),
    write_bootstrap_meta: bool = typer.Option(
        True,
        "--write-bootstrap-meta/--no-write-bootstrap-meta",
        help="Update bootstrap_meta flags when writing stats_report.",
    ),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--overwrite-existing",
        help="Skip runs where stats_report.json already exists.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; do not write files."),
):
    """
    Seed missing stats_report.json from claimset artifacts.
    """
    from src.services.stats_repair import (
        DEFAULT_STATS_REPAIR_PAPER_IDS,
        seed_stats_reports_from_claimset,
    )

    target_ids = paper_id if paper_id else list(DEFAULT_STATS_REPAIR_PAPER_IDS)
    results = seed_stats_reports_from_claimset(
        paper_ids=[str(pid) for pid in target_ids],
        artifacts_root=Path(artifacts_root),
        run_id=(run_id or None),
        max_checks=max_checks,
        write_bootstrap_meta=write_bootstrap_meta,
        skip_existing=skip_existing,
        dry_run=dry_run,
    )

    for item in results:
        console.print(
            f"{item.paper_id} | run={item.run_id or '-'} | {item.status} | checks={item.checks} | {item.reason}"
        )

    seeded = sum(1 for item in results if item.status == "seeded")
    planned = sum(1 for item in results if item.status == "planned")
    skipped = sum(1 for item in results if item.status == "skipped")
    console.print(f"summary: seeded={seeded}, planned={planned}, skipped={skipped}, total={len(results)}")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask the RAG agent")
):
    """
    [v3.0] Query the local RAG knowledge base (storage/rag/).
    """
    from src.config import load_config
    from src.agents.indexer_agent import IndexerAgent
    from src.agents.adapter import OllamaModelAdapter

    config = load_config()
    if not config.agents.enabled:
        console.print("[yellow]⚠️ Agents are disabled in config.[/yellow]")
        return
        
    console.print(f"[bold cyan]🤔 User: {question}[/bold cyan]")
    
    try:
        # 1. Retrieve
        indexer = IndexerAgent(collection_name="paperpipe_rag") 
        # Note: IndexerAgent initializes adapter internally too, careful with resource usage? 
        # Ollama is stateless HTTP, so it's fine.
        
        with console.status("[bold green]🔍 Searching Knowledge Base...[/bold green]"):
            docs = indexer.query(question, n_results=5)
        
        if not docs:
            console.print("[red]❌ No relevant documents found.[/red]")
            return
            
        console.print(f"   📄 Found {len(docs)} relevant chunks.")
        
        # 2. Generate
        context = "\n\n".join(docs)
        prompt = f"""
You are a helpful research assistant for the PaperPipe system.
Answer the user's question based ONLY on the provided context from scientific papers.
If the answer is not in the context, say "I cannot find the answer in the indexed papers."

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""
        
        adapter = OllamaModelAdapter(model_name=config.agents.main_model)
        
        with console.status("[bold green]🧠 Thinking...[/bold green]"):
            result = adapter.generate(prompt)
            
        console.print(f"\n[bold]🤖 Answer:[/bold]\n{result.text}\n")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()

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
    [v3.0] Chat with the profile patch assistant to update search profiles.
    """
    try:
        from src.profiles.profile_store import (
            ProfileRevisionConflictError,
            load_profiles,
            upsert_profile,
        )
        from src.profiles.profile_metadata import is_research_dna_projection_profile
        from src.profiles.patch_apply import apply_patch
        from src.profiles.risk_rules import validate_profile
        from src.agents.profile_chat_agent import ProfileChatAgent
        
        # 1. Load Profiles
        config = load_profiles()
        if not config.profiles:
            console.print("[yellow]⚠️ No profiles found. Please create one manually first in config/profiles.yaml[/yellow]")
            return

        # 2. Select Profile
        selected_profile = None
        if target_id:
            for p in config.profiles:
                if p.id == target_id:
                    selected_profile = p
                    break
        
        if not selected_profile:
            console.print("[bold cyan]📚 Select a Profile to Update:[/bold cyan]")
            for i, p in enumerate(config.profiles, 1):
                console.print(f" {i}. [bold]{p.id}[/bold] ({p.title})")
            
            choice = typer.prompt("Enter number or ID")
            try:
                # Try as index
                idx = int(choice) - 1
                if 0 <= idx < len(config.profiles):
                    selected_profile = config.profiles[idx]
            except ValueError:
                # Try as ID
                for p in config.profiles:
                    if p.id == choice.strip():
                        selected_profile = p
                        break
        
        if not selected_profile:
            console.print("[bold red]❌ Invalid profile selected.[/bold red]")
            return

        if is_research_dna_projection_profile(selected_profile):
            console.print(
                "[bold yellow]⚠️ This profile is a ResearchDNA compatibility projection and is read-only here.[/bold yellow]"
            )
            console.print("[dim]Update the source Research DNA and re-run `research-dna project-profile` instead.[/dim]")
            return

        console.print(f"\n[bold green]✅ Selected: {selected_profile.title} ({selected_profile.id})[/bold green]")
        
        # 3. Get User Request
        if not prompt:
            prompt = typer.prompt("💬 What would you like to change?")

        # 4. Agent Generation
        agent = ProfileChatAgent()
        with console.status("[bold green]🤖 Profile assistant is thinking...[/bold green]"):
            patch_request = agent.generate_patch(selected_profile, prompt)
            
        # 5. Dry Run & Validation
        try:
            new_profile = apply_patch(selected_profile, patch_request)
            risk_errors = validate_profile(new_profile)
        except Exception as e:
            console.print(f"[bold red]❌ Patch Application Failed:[/bold red] {e}")
            return

        # 6. Show Diff
        console.print("\n[bold]📝 Proposed Changes:[/bold]")
        
        # Simple Diff Display
        import difflib
        old_json = selected_profile.model_dump_json(indent=2)
        new_json = new_profile.model_dump_json(indent=2)
        
        diff = difflib.unified_diff(
            old_json.splitlines(), 
            new_json.splitlines(), 
            lineterm="",
            fromfile="Current",
            tofile="Proposed"
        )
        
        has_changes = False
        for line in diff:
            has_changes = True
            if line.startswith('+') and not line.startswith('+++'):
                console.print(line, style="green")
            elif line.startswith('-') and not line.startswith('---'):
                console.print(line, style="red")
            else:
                console.print(line, style="dim")
                
        if not has_changes:
            console.print("[yellow]⚠️ No changes proposed (Agent likely rejected request or request was trivial).[/yellow]")
            return

        # 7. Show Risks
        if risk_errors:
            console.print("\n[bold red]🚫 RISK VIOLATIONS DETECTED:[/bold red]")
            for err in risk_errors:
                console.print(f" - {err}")
            console.print("[bold red]The profile assistant refuses to save risky profiles.[/bold red]")
            return

        # 8. Confirmation
        if typer.confirm("\n🚀 Apply these changes?"):
            # Update in-memory list
            for i, p in enumerate(config.profiles):
                if p.id == selected_profile.id:
                    config.profiles[i] = new_profile
                    break
            
            # Save
            try:
                upsert_profile(new_profile, expected_revision=selected_profile.revision)
            except ProfileRevisionConflictError as exc:
                console.print("[bold red]❌ Profile changed on disk while you were editing it.[/bold red]")
                console.print(f"[dim]{exc}[/dim]")
                console.print("[dim]Reload the profile and retry so you review the latest diff first.[/dim]")
                return
            console.print("[bold green]✅ Profile Updated & Saved![/bold green]")
        else:
            console.print("[yellow]❌ Changes discarded.[/yellow]")

    except Exception as e:
         console.print(f"[bold red]❌ Error: {e}[/bold red]")
         import traceback
         traceback.print_exc()

@app.command(name="audit")
def profiles_audit(
    days: int = typer.Option(7, help="Lookback window in days")
):
    """
    [v3.0] Audit profiles for performance issues (limit hits) & Auto-Fix.
    """
    from src.profiles.profile_store import (
        ProfileRevisionConflictError,
        load_profiles,
        upsert_profile,
    )
    from src.profiles.profile_metadata import is_research_dna_projection_profile
    from src.profiles.patch_apply import apply_patch
    from src.profiles.risk_rules import validate_profile
    from src.agents.profile_chat_agent import ProfileChatAgent
    from src.db_utils import get_profile_stats
    
    config = load_profiles()
    if not config.profiles:
        console.print("[yellow]⚠️ No profiles to audit.[/yellow]")
        return
        
    console.print(f"[bold]🔍 Auditing {len(config.profiles)} profiles (Last {days} days)...[/bold]")
    agent = None # Lazy load
    
    issues_found = 0
    
    for profile in config.profiles:
        if is_research_dna_projection_profile(profile):
            console.print(f"[dim]Skipping ResearchDNA projection profile: {profile.id}[/dim]")
            continue
        stats = get_profile_stats(profile.id, days=days)
        if not stats:
            continue
            
        total_runs = len(stats)
        limit_hits = sum(1 for s in stats if s['limit_hit'])
        hit_ratio = limit_hits / total_runs
        avg_items = sum(s['items_fetched'] for s in stats) / total_runs
        
        # Threshold: > 50% runs hit limit
        if hit_ratio > 0.5:
            issues_found += 1
            console.print(f"\n[bold red]🚨 ISSUE: {profile.title} ({profile.id})[/bold red]")
            console.print(f"   - Limit Hit Rate: {hit_ratio:.1%} ({limit_hits}/{total_runs} runs)")
            console.print(f"   - Avg Fetched: {avg_items:.1f} (Limit: {profile.limits.max_results_per_run})")
            
            if typer.confirm("   🛠️  Ask profile assistant to fix this?"):
                if not agent: agent = ProfileChatAgent()
                
                with console.status("   🤖 Generating Fix..."):
                    patch = agent.suggest_audit_fix(profile, hit_ratio, days)
                    
                # Dry Run
                try:
                    new_profile = apply_patch(profile, patch)
                    validate_profile(new_profile) # Ignore return, just check assumption
                except Exception as e:
                    console.print(f"[red]   ❌ Fix generation failed: {e}[/red]")
                    continue
                    
                # Show Diff
                console.print("\n   [bold]Proposed Fix:[/bold]")
                import difflib
                old_json = profile.model_dump_json(indent=2)
                new_json = new_profile.model_dump_json(indent=2)
                diff = difflib.unified_diff(
                    old_json.splitlines(), new_json.splitlines(), lineterm="", fromfile="Current", tofile="Fix"
                )
                for line in diff:
                     color = "green" if line.startswith('+') else "red" if line.startswith('-') else "dim"
                     if not line.startswith('---') and not line.startswith('+++'):
                         console.print(f"   {line}", style=color)
                         
                if typer.confirm("   🚀 Apply Fix?"):
                    # Apply
                    for i, p in enumerate(config.profiles):
                        if p.id == profile.id:
                            config.profiles[i] = new_profile
                            break
                    try:
                        upsert_profile(new_profile, expected_revision=profile.revision)
                    except ProfileRevisionConflictError as exc:
                        console.print("   [red]❌ Fix not saved because the profile changed on disk.[/red]")
                        console.print(f"   [dim]{exc}[/dim]")
                        console.print("   [dim]Reload and rerun audit before applying another fix.[/dim]")
                        continue
                    console.print("   ✅ Fixed & Saved.")
                else:
                    console.print("   💨 Skipped.")
        else:
             # Healthy
             pass
             
    if issues_found == 0:
        console.print("\n[bold green]✅ All profiles healthy![/bold green]")


@research_dna_app.command("create")
def research_dna_create(
    topic: str = typer.Argument(..., help="Research topic"),
    intent: str = typer.Option(..., "--intent", help="explore | systematic_review | update"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why this DNA is being created"),
    dna_id: str | None = typer.Option(None, "--dna-id", help="Optional explicit DNA ID"),
    title: str | None = typer.Option(None, "--title", help="Optional explicit title"),
    recommended_db: list[str] = typer.Option(None, "--recommended-db", help="Recommended database"),
    available_db: list[str] = typer.Option(None, "--available-db", help="Available database"),
):
    from src.profiles.research_dna_service import create_research_dna

    dna = create_research_dna(
        topic=topic,
        intent=intent,  # type: ignore[arg-type]
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
        dna_id=dna_id,
        title=title,
        recommended_databases=recommended_db or [],
        available_databases=available_db or [],
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("show")
def research_dna_show(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
):
    from src.profiles.research_dna_store import load_research_dna

    dna = load_research_dna(dna_id)
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("approve-pilot")
def research_dna_approve_pilot(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the pilot is approved"),
):
    from src.profiles.research_dna_service import approve_pilot

    dna = approve_pilot(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("update")
def research_dna_update(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    patch_file: Path = typer.Option(..., "--patch-file", exists=True, help="ResearchDNAUpdate JSON/YAML file"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the DNA is being updated"),
):
    from src.profiles.research_dna_schema import ResearchDNAUpdate
    from src.profiles.research_dna_service import update_research_dna

    payload = yaml.safe_load(patch_file.read_text(encoding="utf-8"))
    patch = ResearchDNAUpdate(**payload)
    dna = update_research_dna(
        dna_id,
        patch=patch,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("interview")
def research_dna_interview(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    round: str = typer.Option(..., "--round", help="researcher | librarian"),
    question_id: str = typer.Option(..., "--question-id", help="Stable question ID"),
    question: str = typer.Option(..., "--question", help="Interview question text"),
    answer: str = typer.Option(..., "--answer", help="Interview answer text"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
):
    from src.profiles.research_dna_service import log_interview_response

    dna, interview = log_interview_response(
        dna_id,
        round=round,  # type: ignore[arg-type]
        question_id=question_id,
        question=question,
        answer=answer,
        actor_type="human_cli",
        actor_id=actor_id,
    )
    _emit_json(
        {
            "dna": dna.model_dump(mode="json", exclude_none=True),
            "interview": interview.model_dump(mode="json", exclude_none=True),
        }
    )


@research_dna_app.command("refine")
def research_dna_refine(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    query_version_file: Path = typer.Option(..., "--query-version-file", exists=True, help="QueryVersion JSON/YAML file"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the query is refined"),
):
    from src.profiles.research_dna_schema import QueryVersion
    from src.profiles.research_dna_service import refine_query_version

    payload = yaml.safe_load(query_version_file.read_text(encoding="utf-8"))
    query_version = QueryVersion(**payload)
    dna = refine_query_version(
        dna_id,
        query_version=query_version,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("pilot")
def research_dna_run_pilot(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional explicit pilot run ID"),
):
    from src.profiles.research_dna_service import run_pilot

    pilot_run = run_pilot(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        run_id=run_id,
    )
    _emit_json(pilot_run.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("screening")
def research_dna_submit_screening(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    candidate_id: str = typer.Option(..., "--candidate-id", help="Screening candidate ID"),
    decision: str = typer.Option(..., "--decision", help="include | exclude | unclear"),
    reason_code: str = typer.Option(..., "--reason-code", help="Structured reason code"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    note: str | None = typer.Option(None, "--note", help="Optional screening note"),
):
    from src.profiles.research_dna_service import submit_screening_decision

    dna = submit_screening_decision(
        dna_id,
        run_id=run_id,
        candidate_id=candidate_id,
        decision=decision,  # type: ignore[arg-type]
        reason_code=reason_code,  # type: ignore[arg-type]
        note=note,
        actor_type="human_cli",
        actor_id=actor_id,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("lock")
def research_dna_lock(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the DNA is being locked"),
):
    from src.profiles.research_dna_service import lock_research_dna

    dna = lock_research_dna(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("unlock")
def research_dna_unlock(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the DNA is being unlocked"),
):
    from src.profiles.research_dna_service import unlock_research_dna

    dna = unlock_research_dna(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("project-profile")
def research_dna_project_profile(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the projection is being materialized"),
    query_version: str | None = typer.Option(None, "--query-version", help="Optional explicit query version"),
    database: str | None = typer.Option(None, "--database", help="Optional explicit database key"),
):
    from src.profiles.research_dna_projection import sync_research_dna_profile

    projection = sync_research_dna_profile(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
        query_version_name=query_version,
        database=database,
    )
    _emit_json(projection.model_dump(mode="json", exclude_none=True))


def entrypoint():
    app()


if __name__ == "__main__":
    entrypoint()
