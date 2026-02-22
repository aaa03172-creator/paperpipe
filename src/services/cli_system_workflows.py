from __future__ import annotations

import csv
import datetime
import shutil
from collections import Counter
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.table import Table


def doctor_workflow(console: Console, bootstrap_database: Callable[[], Path]) -> None:
    console.print("[bold blue]🩺 Checking Environment...[/bold blue]")

    try:
        from src.config import load_config

        config = load_config()
        console.print("✅ Config loaded successfully.")
        console.print(f"   - Zotero Dir: {config.paths.zotero_base_dir}")
        console.print(f"   - Log Level: {config.system.log_level}")

        if config.paths.watch_folder:
            if config.paths.watch_folder.exists():
                console.print(f"   - Watch Folder: ✅ Found ({config.paths.watch_folder})")
            else:
                console.print(
                    f"   - Watch Folder: ⚠️ Configured but missing ({config.paths.watch_folder})"
                )
        else:
            console.print("   - Watch Folder: ⚪ Not configured")

        if config.system.unpaywall_email and "example.com" not in config.system.unpaywall_email:
            console.print(f"   - Unpaywall: ✅ Email configured ({config.system.unpaywall_email})")
        else:
            console.print("   - Unpaywall: ⚠️ Email missing or default")

        if config.ranking.bibliometrics.enabled:
            console.print("   - Bibliometrics: ✅ Enabled (OpenAlex)")
        else:
            console.print("   - Bibliometrics: ⚪ Disabled")

        try:
            llm_config = config.llm
            mode = getattr(llm_config, "mode", "cloud")
            if mode in ["local", "hybrid"]:
                console.print(f"   - LLM Mode: [bold cyan]{mode}[/bold cyan] (Ollama Active)")
                if hasattr(llm_config, "local") and llm_config.local:
                    url = llm_config.local.base_url
                    try:
                        import ollama

                        client = ollama.Client(host=url)
                        try:
                            client.list()
                            console.print(f"   - Ollama: ✅ Connected ({url})")
                        except Exception as conn_err:
                            console.print(
                                f"   - Ollama: ❌ Connection Failed ({url}) - {conn_err}",
                                style="red",
                            )
                    except ImportError:
                        console.print("   - Ollama: ⚠️ 'ollama' package not installed.", style="yellow")
            else:
                console.print(f"   - LLM Mode: {mode} (Cloud Only)")
        except Exception as exc:
            console.print(f"   - LLM Check: ⚠️ Error checking LLM config: {exc}")
    except Exception as exc:
        console.print(f"❌ Config Error: {exc}", style="bold red")
        return

    try:
        db_path = bootstrap_database()
        console.print(f"✅ Database initialized ({db_path}).")
    except Exception as exc:
        console.print(f"❌ Database Error: {exc}", style="bold red")

    import os

    if os.getenv("OPENAI_API_KEY"):
        console.print("✅ OpenAI API Key detected.")
    else:
        console.print("❌ OpenAI API Key missing!", style="bold red")

    if Path("logs/paperpipe.log").exists():
        console.print("✅ Log file accessible.")
    else:
        console.print("⚠️ Log file not found yet (will be created on first log).")

    console.print("[bold green]All systems go![/bold green]")


def clear_logs_workflow(console: Console) -> None:
    open("logs/paperpipe.log", "w").close()
    console.print("✅ Logs cleared.")


def reset_workflow(console: Console, bootstrap_database: Callable[[], Path], db_paths: list[Path]) -> None:
    console.print("[bold red]🗑️  Resetting all data...[/bold red]")

    seen = set()
    for db_path in db_paths:
        db_path = Path(db_path)
        if str(db_path) in seen:
            continue
        seen.add(str(db_path))
        if db_path.exists():
            db_path.unlink()
            console.print(f"   - Deleted {db_path}")

    log_path = Path("logs/paperpipe.log")
    if log_path.exists():
        open(log_path, "w").close()
        console.print("   - Cleared logs")

    try:
        from src.config import load_config

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
    except Exception as exc:
        console.print(f"   ⚠️  Failed to clean Obsidian vault: {exc}")

    db_path = bootstrap_database()
    console.print(f"✅ Reset complete. System is clean. ({db_path})")


def test_unpaywall_workflow(doi: str, console: Console) -> None:
    from src.downloader import _fetch_oa_link
    from src.config import load_config

    config = load_config()

    console.print(f"[bold cyan]🔍 Testing Unpaywall for DOI: {doi}[/bold cyan]")
    email = config.system.unpaywall_email
    console.print(f"   - Email: {email}")

    link = _fetch_oa_link(doi, email)
    if link:
        console.print(f"✅ Found OA Link: {link}")
    else:
        console.print("❌ No OA Link found (or API error).")


def watch_workflow(console: Console) -> None:
    from src.watcher import WatcherService
    import src.processor as processor_module
    from src.config import load_config

    config = load_config()

    console.print("[bold green]👀 Starting Watcher Service...[/bold green]")
    console.print(f"   - Folder: {config.paths.watch_folder}")
    console.print("   (Press Ctrl+C to stop)")

    service = WatcherService(config)
    try:
        service.start(processor_module)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Watcher stopped by user.[/bold yellow]")
    except Exception as exc:
        console.print(f"[bold red]❌ Watcher Error: {exc}[/bold red]")


def watch_downloads_workflow(console: Console) -> None:
    from src.downloads_watcher import DownloadsWatcherService
    from src.config import load_config

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
    except Exception as exc:
        console.print(f"[bold red]❌ Downloads watcher error: {exc}[/bold red]")


def organize_workflow(target_dir: str, console: Console) -> None:
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
            paper = create_paper_from_pdf(pdf)
            new_name = generate_filename(paper)
            year = (
                paper.published[:4]
                if paper.published and len(paper.published) >= 4
                else "Unknown"
            )

            year_dir = config.paths.library_dir / year
            year_dir.mkdir(parents=True, exist_ok=True)

            final_path = year_dir / new_name
            if final_path.exists() and final_path.resolve() != pdf.resolve():
                timestamp = datetime.datetime.now().strftime("%H%M%S")
                final_path = year_dir / f"{final_path.stem}_{timestamp}{final_path.suffix}"

            if final_path.resolve() == pdf.resolve():
                console.print(f"   ⏭️  Already organized: {pdf.name}")
                continue

            shutil.move(pdf, final_path)
            console.print(f"   ✅ {pdf.name} -> {year}/{new_name}")
            success_count += 1
        except Exception as exc:
            console.print(f"   ❌ Failed to organize {pdf.name}: {exc}")
            fail_count += 1

    console.print(f"\n[bold]🎉 Done! Organized: {success_count}, Failed: {fail_count}[/bold]")


def stats_workflow(console: Console) -> None:
    from src.config import load_config

    config = load_config()
    vault_path = config.paths.obsidian_vault

    potential_indexes = [
        config.paths.index_all,
        "00_Index/on_demand.csv",
        "00_Index/manual_collection.csv",
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
            with open(index_path, "r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    status = row.get("Status", "Unknown").strip() or "Unknown"
                    if status.lower() == "to read":
                        status = "Inbox"
                    status_counts[status] += 1
                    total += 1
        except Exception as exc:
            console.print(f"[red]❌ Failed to read index {relative_idx_path}: {exc}[/red]")

    if scanned_files == 0:
        console.print(f"[yellow]⚠️  No index files found in {vault_path}[/yellow]")
        return

    table = Table(title=f"📚 Library Stats (Total: {total})", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right", style="white")
    table.add_column("Percentage", justify="right", style="green")

    order = ["Inbox", "Reading", "Done", "Unknown"]
    for status in order:
        if status_counts[status] > 0 or status in ["Inbox", "Reading", "Done"]:
            count = status_counts[status]
            pct = (count / total * 100) if total > 0 else 0
            table.add_row(status, str(count), f"{pct:.1f}%")
            if status in status_counts:
                del status_counts[status]

    for status, count in status_counts.items():
        pct = (count / total * 100) if total > 0 else 0
        table.add_row(status, str(count), f"{pct:.1f}%")

    console.print(table)
