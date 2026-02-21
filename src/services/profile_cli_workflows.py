from __future__ import annotations

import difflib
from typing import Optional

import typer
from rich.console import Console

from src.agents.profile_chat_agent import ProfileChatAgent
from src.db_utils import get_profile_stats
from src.profiles.patch_apply import apply_patch
from src.profiles.profile_store import load_profiles, save_profiles
from src.profiles.risk_rules import validate_profile


def _select_profile(config, target_id: Optional[str], console: Console):
    selected_profile = None
    if target_id:
        for profile in config.profiles:
            if profile.id == target_id:
                selected_profile = profile
                break

    if selected_profile:
        return selected_profile

    console.print("[bold cyan]📚 Select a Profile to Update:[/bold cyan]")
    for index, profile in enumerate(config.profiles, 1):
        console.print(f" {index}. [bold]{profile.id}[/bold] ({profile.title})")

    choice = typer.prompt("Enter number or ID")
    try:
        choice_index = int(choice) - 1
        if 0 <= choice_index < len(config.profiles):
            return config.profiles[choice_index]
    except ValueError:
        pass

    for profile in config.profiles:
        if profile.id == choice.strip():
            return profile
    return None


def run_profiles_chat_workflow(target_id: Optional[str], prompt: Optional[str], console: Console) -> None:
    config = load_profiles()
    if not config.profiles:
        console.print(
            "[yellow]⚠️ No profiles found. Please create one manually first in config/profiles.yaml[/yellow]"
        )
        return

    selected_profile = _select_profile(config, target_id, console)
    if not selected_profile:
        console.print("[bold red]❌ Invalid profile selected.[/bold red]")
        return

    console.print(
        f"\n[bold green]✅ Selected: {selected_profile.title} ({selected_profile.id})[/bold green]"
    )

    if not prompt:
        prompt = typer.prompt("💬 What would you like to change?")

    agent = ProfileChatAgent()
    with console.status("[bold green]🤖 Librarian is thinking...[/bold green]"):
        patch_request = agent.generate_patch(selected_profile, prompt)

    try:
        new_profile = apply_patch(selected_profile, patch_request)
        risk_errors = validate_profile(new_profile)
    except Exception as exc:
        console.print(f"[bold red]❌ Patch Application Failed:[/bold red] {exc}")
        return

    console.print("\n[bold]📝 Proposed Changes:[/bold]")
    old_json = selected_profile.model_dump_json(indent=2)
    new_json = new_profile.model_dump_json(indent=2)
    diff = difflib.unified_diff(
        old_json.splitlines(),
        new_json.splitlines(),
        lineterm="",
        fromfile="Current",
        tofile="Proposed",
    )

    has_changes = False
    for line in diff:
        has_changes = True
        if line.startswith("+") and not line.startswith("+++"):
            console.print(line, style="green")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(line, style="red")
        else:
            console.print(line, style="dim")

    if not has_changes:
        console.print(
            "[yellow]⚠️ No changes proposed (Agent likely rejected request or request was trivial).[/yellow]"
        )
        return

    if risk_errors:
        console.print("\n[bold red]🚫 RISK VIOLATIONS DETECTED:[/bold red]")
        for error in risk_errors:
            console.print(f" - {error}")
        console.print("[bold red]The Strict Librarian Refuses to Save Risky Profiles.[/bold red]")
        return

    if not typer.confirm("\n🚀 Apply these changes?"):
        console.print("[yellow]❌ Changes discarded.[/yellow]")
        return

    for index, profile in enumerate(config.profiles):
        if profile.id == selected_profile.id:
            config.profiles[index] = new_profile
            break
    save_profiles(config)
    console.print("[bold green]✅ Profile Updated & Saved![/bold green]")


def run_profiles_audit_workflow(days: int, console: Console) -> None:
    config = load_profiles()
    if not config.profiles:
        console.print("[yellow]⚠️ No profiles to audit.[/yellow]")
        return

    console.print(f"[bold]🔍 Auditing {len(config.profiles)} profiles (Last {days} days)...[/bold]")
    agent = None
    issues_found = 0

    for profile in config.profiles:
        stats = get_profile_stats(profile.id, days=days)
        if not stats:
            continue

        total_runs = len(stats)
        limit_hits = sum(1 for sample in stats if sample["limit_hit"])
        hit_ratio = limit_hits / total_runs
        avg_items = sum(sample["items_fetched"] for sample in stats) / total_runs

        if hit_ratio <= 0.5:
            continue

        issues_found += 1
        console.print(f"\n[bold red]🚨 ISSUE: {profile.title} ({profile.id})[/bold red]")
        console.print(f"   - Limit Hit Rate: {hit_ratio:.1%} ({limit_hits}/{total_runs} runs)")
        console.print(
            f"   - Avg Fetched: {avg_items:.1f} (Limit: {profile.limits.max_results_per_run})"
        )

        if not typer.confirm("   🛠️  Ask Librarian to fix this?"):
            continue

        if not agent:
            agent = ProfileChatAgent()
        with console.status("   🤖 Generating Fix..."):
            patch = agent.suggest_audit_fix(profile, hit_ratio, days)

        try:
            new_profile = apply_patch(profile, patch)
            validate_profile(new_profile)
        except Exception as exc:
            console.print(f"[red]   ❌ Fix generation failed: {exc}[/red]")
            continue

        console.print("\n   [bold]Proposed Fix:[/bold]")
        old_json = profile.model_dump_json(indent=2)
        new_json = new_profile.model_dump_json(indent=2)
        diff = difflib.unified_diff(
            old_json.splitlines(),
            new_json.splitlines(),
            lineterm="",
            fromfile="Current",
            tofile="Fix",
        )
        for line in diff:
            color = "green" if line.startswith("+") else "red" if line.startswith("-") else "dim"
            if not line.startswith("---") and not line.startswith("+++"):
                console.print(f"   {line}", style=color)

        if not typer.confirm("   🚀 Apply Fix?"):
            console.print("   💨 Skipped.")
            continue

        for index, existing in enumerate(config.profiles):
            if existing.id == profile.id:
                config.profiles[index] = new_profile
                break
        save_profiles(config)
        console.print("   ✅ Fixed & Saved.")

    if issues_found == 0:
        console.print("\n[bold green]✅ All profiles healthy![/bold green]")
