from __future__ import annotations

import csv
import datetime
import shutil
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table


def watch_workflow(console: Console) -> None:
    from src.config import load_config
    from src.watcher import WatcherService
    import src.processor as processor_module

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
    from src.config import load_config
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
    except Exception as exc:
        console.print(f"[bold red]❌ Downloads watcher error: {exc}[/bold red]")


def organize_workflow(target_dir: str, console: Console) -> None:
    from src.config import load_config
    from src.utils import create_paper_from_pdf, generate_filename

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
