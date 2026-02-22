from __future__ import annotations

from rich.console import Console


def test_fetch_workflow(console: Console) -> None:
    """Test Fetch (Provider Pattern)"""
    from src.config import load_config
    from src.fetch import get_fetchers

    config = load_config()
    keywords = [config.search.slots["mechanism"].query]
    query_str = keywords[0]

    console.print(f"[bold cyan]🔍 Testing fetch with query: {query_str}[/bold cyan]")

    fetchers = get_fetchers(config)
    console.print(f"Loaded Fetchers: {[f.source_name for f in fetchers]}")

    for fetcher in fetchers:
        console.print(f"\n[bold]Testing {fetcher.source_name}...[/bold]")
        try:
            papers = fetcher.fetch(query_str, max_results=3)
            for paper in papers:
                console.print(f" - [{fetcher.source_name}] {paper.title} ({paper.published})")
        except Exception as exc:
            console.print(f"[red]Error fetching from {fetcher.source_name}: {exc}[/red]")
            console.print(f"[red]Error fetching from {fetcher.source_name}: {exc}[/red]")


def fetch_workflow(query: str, limit: int, save: bool, console: Console) -> None:
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
        if isinstance(item, dict):
            title = item.get("title", "No Title")
            date = item.get("published", "Unknown")
            source = item.get("source", "Unknown")
            link = item.get("doi") or item.get("link")
            score_val = item.get("manual_rank_score")
        else:
            title = item.title
            date = item.published
            source = item.source
            link = item.id
            score_val = item.manual_rank_score

        score_str = f" [bold magenta](Score: {score_val:.2f})[/bold magenta]" if score_val else ""
        console.print(f"{idx}. [{source}] {title} ({date}){score_str} - {link}")

    if save and results:
        console.print(f"\n[bold blue]✨ Saved {len(results)} papers to 'Inbox/OnDemand'[/bold blue]")


def _print_slot_results(results, console: Console) -> None:
    console.print("\n[bold green]📊 Daily Slot Report[/bold green]")

    if not results:
        console.print("[bold red]❌ No papers selected.[/bold red]")
        return

    for paper in results:
        icon = "🏥" if paper.get("trial_data") else "📝"
        console.print(f"\n{icon} [{paper['slot']}] {paper['title']}")

        one_liner = paper.get("ai_one_liner") or "⚠️ No AI Summary (Fallback)"
        console.print(f"   💡 One-Liner: {one_liner}")

        if paper.get("trial_data"):
            console.print("   💊 [bold cyan]Clinical Data Extracted:[/bold cyan]")
            for key, val in paper["trial_data"].items():
                console.print(f"      - {key}: {val}")


def process_test_workflow(force: bool, console: Console) -> None:
    """Test Full Pipeline (Fetch -> Classify -> Tag). Use --force to ignore DB."""
    from src.processor import process_daily_slots

    if force:
        console.print("[bold yellow]⚠️ Running in FORCE mode: Ignoring DB duplicates.[/bold yellow]")

    results = process_daily_slots(ignore_db=force)
    _print_slot_results(results, console)


def run_daily_workflow(console: Console) -> None:
    """[Production] Run Daily PaperPipe Routine."""
    from src.config import load_config
    from src.processor import process_daily_slots
    from src.reporting import generate_daily_report

    console.print("[bold green]🚀 Starting Production Run...[/bold green]")
    results = process_daily_slots(ignore_db=False)

    if results:
        config = load_config()
        report_path = generate_daily_report(results, config)
        if report_path:
            console.print(f"[bold blue]📊 SLA Report generated: {report_path}[/bold blue]")

    _print_slot_results(results, console)


def test_filter_workflow(console: Console) -> None:
    """Test Title Filter Logic"""
    test_titles = [
        "Basic Science and Pathogenesis.",
        "Drug Development.",
        "Clinical Manifestations.",
        "Chapter 1: Introduction",
        "Section 5. Results",
        "Valid Paper Title About Neuroscience",
        "A very long title that should pass even if it ends with.",
        "Short title without dot",
    ]

    console.print("[bold]🧪 Testing Junk Title Filter Logic...[/bold]")

    for title in test_titles:
        title_clean = title.strip()
        word_count = len(title_clean.split())

        is_junk_short = word_count <= 4 and title_clean.endswith(".")
        junk_keywords = ["Chapter", "Section", "Part", "Index", "Preface", "Table of Contents"]
        is_junk_keyword = word_count <= 5 and any(keyword in title_clean for keyword in junk_keywords)

        if is_junk_short:
            console.print(f"❌ [red]FILTERED (Short)[/red]: '{title}'")
        elif is_junk_keyword:
            console.print(f"❌ [red]FILTERED (Keyword)[/red]: '{title}'")
        else:
            console.print(f"✅ [green]PASSED[/green]: '{title}'")


def reconcile_workflow(apply: bool, console: Console) -> None:
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


def export_workflow(overwrite: bool, console: Console) -> None:
    from src.exporter import run_export

    console.print(f"[bold cyan]📤 Starting Export to Obsidian...[/bold cyan]")
    if overwrite:
        console.print("[yellow]⚠️  Overwrite Mode: ON[/yellow]")

    run_export(overwrite=overwrite)

    console.print("[bold green]✅ Export Complete.[/bold green]")
