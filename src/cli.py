import typer
import os
import shutil
import logging
from pathlib import Path
from rich.console import Console
from src.config import load_config
from src.db import init_db
from src.logger import setup_logging
from src.services.deepread_note_writer import (
    build_deepread_markdown,
    build_stats_markdown,
    upsert_deepread_section,
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
            mode = getattr(llm_config, 'mode', 'cloud') 
            
            if mode in ["local", "hybrid"]:
                 console.print(f"   - LLM Mode: [bold cyan]{mode}[/bold cyan] (Ollama Active)")
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
                 console.print(f"   - LLM Mode: {mode} (Cloud Only)")
                 
        except Exception as e:
            console.print(f"   - LLM Check: ⚠️ Error checking LLM config: {e}")

    except Exception as e:
        console.print(f"❌ Config Error: {e}", style="bold red")
        return

    try:
        init_db()
        console.print("✅ Database initialized (state.db).")
    except Exception as e:
        console.print(f"❌ Database Error: {e}", style="bold red")
    
    # Check OpenAI Key
    if os.getenv("OPENAI_API_KEY"):
        console.print("✅ OpenAI API Key detected.")
    else:
        console.print("❌ OpenAI API Key missing!", style="bold red")

    if Path("logs/paperpipe.log").exists():
        console.print("✅ Log file accessible.")
    else:
        console.print("⚠️ Log file not found yet (will be created on first log).")

    console.print("[bold green]All systems go![/bold green]")
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
    _update_status(identifier, "Reading")

@app.command()
def done(
    identifier: str = typer.Argument(..., help="Paper ID, DOI, or Exact Title")
):
    """Mark a paper as 'Done'."""
    _update_status(identifier, "Done")

def _update_status(identifier: str, status: str):
    from src.obsidian import set_reading_status
    from src.db import update_paper_status
    
    config = load_config()
    console.print(f"[bold cyan]🔄 Updating status to '{status}' for: {identifier}[/bold cyan]")
    
    # 1. Update Obsidian & CSV (Source of Truth for User)
    doi = set_reading_status(identifier, status, config)
    
    if doi:
        # 2. Update DB (Backend State)
        update_paper_status(doi, status)
        console.print(f"   ✅ DB Updated (DOI: {doi})")
        console.print(f"   ✅ Obsidian Note & Index Updated")
    else:
        # Try finding by partial title if exact identification failed?
        # For now, just error.
        console.print(f"[bold red]❌ Paper not found in Index.[/bold red]")
        console.print("   (Try using exact Paper ID, DOI, or Title from 'paperpipe stats' or 'paperpipe fetch --save')")

@app.command()
def deepread(
    identifier: str = typer.Argument(..., help="Paper ID or DOI"),
    verify: bool = typer.Option(False, "--verify", help="Run strict statistical verification on claims")
):
    """
    [v3.0] Run Agentic Deep Read pipeline: Ingest -> Index -> Read.
    Appends structured analysis to the Obsidian note.
    """
    from src.config import load_config
    from src.db import get_paper_by_id
    from src.agents.ingest_agent import IngestAgent
    from src.agents.indexer_agent import IndexerAgent
    from src.agents.reader_agent import ReaderAgent
    # Lazy import for verification
    if verify:
        from src.agents.stats_agent import StatsVerificationAgent
    
    config = load_config()
    if not config.agents.enabled:
        console.print("[yellow]⚠️ Agents are disabled in config. Enable them to use this feature.[/yellow]")
        return

    console.print(f"[bold cyan]🤖 Starting Deep Read Pipeline for: {identifier}[/bold cyan]")

    # 1. Locate PDF & Note
    # Try DB first for PDF path
    try:
        paper_row = get_paper_by_id(identifier)
    except:
        paper_row = None
        
    pdf_path = None
    if paper_row and paper_row.get("local_path"):
        pdf_path = Path(paper_row["local_path"])
    
    # Fallback: Search Library
    if not pdf_path or not pdf_path.exists():
        # Quick search in Library for any PDF containing the ID
        # Limiting depth or glob scope to avoid massive search
        results = list(config.paths.library_dir.rglob(f"*{identifier}*.pdf"))
        # If ID is DOI (contains /), glob might fail or split.
        if not results and "/" in identifier:
             clean_id = identifier.replace("/", "_")
             results = list(config.paths.library_dir.rglob(f"*{clean_id}*.pdf"))
             
        if results:
             pdf_path = results[0]
    
    if not pdf_path or not pdf_path.exists():
         console.print(f"[red]❌ PDF not found for {identifier}[/red]")
         return
         
    console.print(f"   📂 PDF: {pdf_path}")
    
    # Find Note Path (reuse CSV logic)
    vault_path = config.paths.obsidian_vault
    idx_files = [config.paths.index_all, "00_Index/on_demand.csv"]
    target_note_path = None
    
    import csv
    for rel_idx in idx_files:
        p = vault_path / rel_idx
        if not p.exists(): continue
        try:
             with open(p, 'r') as f:
                 for row in csv.DictReader(f):
                     if row.get('Paper_ID') == identifier or row.get('DOI') == identifier:
                         if row.get('Note_Path'):
                             target_note_path = vault_path / row['Note_Path']
                         break
        except: pass
        if target_note_path: break
        
    if not target_note_path or not target_note_path.exists():
        console.print(f"[yellow]⚠️ Note not found. Will just print output.[/yellow]")
    else:
        console.print(f"   📝 Note: {target_note_path}")

    # 2. Pipeline Execution
    try:
        # Step A: Ingest
        console.print("[bold]1️⃣  Ingesting PDF...[/bold]")
        ingester = IngestAgent()
        doc = ingester.process_v2(str(pdf_path))
        if not doc:
            console.print("[red]❌ Ingest Agent failed to produce v2 artifact.[/red]")
            return
        console.print(f"   ✅ Extracted {len(doc.pages)} pages (v2 artifact).")

        # Step B: Index
        console.print("[bold]2️⃣  Indexing (RAG)...[/bold]")
        indexer = IndexerAgent(collection_name="paperpipe_rag")
        index_artifact = indexer.process(doc)
        console.print(f"   ✅ Indexed {index_artifact.chunk_count} chunks.")

        # Inject Feedback dynamically
        from src.agents.feedback_retriever import FeedbackRetriever
        retriever = FeedbackRetriever()
        similar_feedback = retriever.query_relevant_feedback(doc.meta.title, limit=3)
        persona_hint = None
        if similar_feedback:
             fb_lines = ["Similar feedback examples (Top-3):"]
             for idx, item in enumerate(similar_feedback, 1):
                 fb_lines.append(f"{idx}) paper_id={item['paper_id']} preview={item['preview']}")
             persona_hint = "\n".join(fb_lines)
             console.print(f"   [yellow]⚠️ Similar feedback injected: {len(similar_feedback)}[/yellow]")
             
        # Step C: Read (Claim Extraction)
        console.print("[bold]3️⃣  Deep Reading (Agentic Analysis)...[/bold]")
        reader = ReaderAgent(model_name=config.agents.main_model, persona_hint=persona_hint)
        claims_set = reader.analyze(doc)
        
        if not claims_set:
            console.print("[red]❌ Reader Agent failed to extract claims.[/red]")
            return

        console.print(f"   ✅ Extracted {len(claims_set.claims)} claims.")

        # Step D: Stats Verification (Optional)
        stats_md = ""
        if verify:
            console.print("\n[bold magenta]4️⃣  Starting Stats Verification Agent (Reflexion Loop)...[/bold magenta]")
            verifier = StatsVerificationAgent()
            with console.status("[bold magenta]   🕵️‍♀️ Verifying Claims (Docker Sandbox Active)...[/bold magenta]", spinner="dots"):
                stats_report = verifier.run(job_id=identifier.replace("/", "_"), doc=doc, claims=claims_set)
                
            console.print(f"   ✅ Verification Complete. Checks run: {len(stats_report.checks)}")
            
            stats_md = build_stats_markdown(stats_report)

        # 3. Output Formatting
        md_output = build_deepread_markdown(
            model_name=reader.model_name,
            claims_set=claims_set,
            stats_md=stats_md if verify else "",
        )
            
            # 4. Upsert (replace existing Deep Read section(s) idempotently)
        if target_note_path:
            content = target_note_path.read_text(encoding="utf-8")
            updated = upsert_deepread_section(content, md_output)
            target_note_path.write_text(updated, encoding="utf-8")
            console.print("[bold green]✨ Deep Read section upserted in note.[/bold green]")
        else:
            console.print(md_output)

    except Exception as e:
        console.print(f"[bold red]❌ Pipeline Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()

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
    [v3.0] Chat with the Strict Data Librarian to update search profiles.
    """
    try:
        from src.profiles.profile_store import load_profiles, save_profiles
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

        console.print(f"\n[bold green]✅ Selected: {selected_profile.title} ({selected_profile.id})[/bold green]")
        
        # 3. Get User Request
        if not prompt:
            prompt = typer.prompt("💬 What would you like to change?")

        # 4. Agent Generation
        agent = ProfileChatAgent()
        with console.status("[bold green]🤖 Librarian is thinking...[/bold green]"):
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
            console.print("[bold red]The Strict Librarian Refuses to Save Risky Profiles.[/bold red]")
            return

        # 8. Confirmation
        if typer.confirm("\n🚀 Apply these changes?"):
            # Update in-memory list
            for i, p in enumerate(config.profiles):
                if p.id == selected_profile.id:
                    config.profiles[i] = new_profile
                    break
            
            # Save
            save_profiles(config)
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
    from src.profiles.profile_store import load_profiles, save_profiles
    from src.profiles.patch_apply import apply_patch
    from src.profiles.risk_rules import validate_profile
    from src.agents.profile_chat_agent import ProfileChatAgent
    from src.db import get_profile_stats
    
    config = load_profiles()
    if not config.profiles:
        console.print("[yellow]⚠️ No profiles to audit.[/yellow]")
        return
        
    console.print(f"[bold]🔍 Auditing {len(config.profiles)} profiles (Last {days} days)...[/bold]")
    agent = None # Lazy load
    
    issues_found = 0
    
    for profile in config.profiles:
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
            
            if typer.confirm("   🛠️  Ask Librarian to fix this?"):
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
                    save_profiles(config)
                    console.print("   ✅ Fixed & Saved.")
                else:
                    console.print("   💨 Skipped.")
        else:
             # Healthy
             pass
             
    if issues_found == 0:
        console.print("\n[bold green]✅ All profiles healthy![/bold green]")


if __name__ == "__main__":
    app()
