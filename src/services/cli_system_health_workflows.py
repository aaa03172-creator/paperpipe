from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from rich.console import Console


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
    from src.config import load_config
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
