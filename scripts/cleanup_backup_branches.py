from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class BackupBranch:
    name: str
    commit_date: datetime


def _run_git(args: list[str]) -> str:
    out = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return out.stdout.strip()


def _parse_git_datetime(raw: str) -> datetime:
    # git for-each-ref iso8601 yields e.g. "2026-02-24 00:26:13 +0900"
    return datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S %z")


def list_backup_branches(prefix: str) -> list[BackupBranch]:
    lines = _run_git(
        [
            "for-each-ref",
            "--format=%(refname:short)|%(committerdate:iso8601)",
            "refs/heads",
        ]
    ).splitlines()
    branches: list[BackupBranch] = []
    for line in lines:
        if not line.strip() or "|" not in line:
            continue
        name, raw_date = line.split("|", 1)
        name = name.strip()
        if not name.startswith(prefix):
            continue
        branches.append(BackupBranch(name=name, commit_date=_parse_git_datetime(raw_date)))
    return branches


def select_expired_branches(
    branches: Iterable[BackupBranch],
    *,
    retention_days: int,
    now: datetime | None = None,
    exclude_names: set[str] | None = None,
) -> list[BackupBranch]:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if retention_days < 0:
        raise ValueError("retention_days must be >= 0")

    exclude = exclude_names or set()
    cutoff = now - timedelta(days=retention_days)
    expired = []
    for branch in branches:
        if branch.name in exclude:
            continue
        if branch.commit_date < cutoff:
            expired.append(branch)
    return sorted(expired, key=lambda b: b.commit_date)


def delete_branches(names: list[str]) -> None:
    for name in names:
        # backup branches are intentionally disposable after retention window.
        _run_git(["branch", "-D", name])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cleanup local backup branches by retention policy (dry-run default)."
    )
    parser.add_argument(
        "--prefix",
        default="master_local_backup_",
        help="Backup branch prefix to manage (default: master_local_backup_).",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=14,
        help="Retention window in days (default: 14).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletion. Default is dry-run.",
    )
    parser.add_argument(
        "--max-delete",
        type=int,
        default=0,
        help="Limit number of branches to delete (0 = all expired).",
    )
    args = parser.parse_args()

    current_branch = _run_git(["branch", "--show-current"]).strip()
    branches = list_backup_branches(args.prefix)
    expired = select_expired_branches(
        branches,
        retention_days=args.retention_days,
        exclude_names={current_branch} if current_branch else set(),
    )
    if args.max_delete > 0:
        expired = expired[: args.max_delete]

    print(f"[BACKUP-CLEANUP] prefix={args.prefix}")
    print(f"[BACKUP-CLEANUP] retention_days={args.retention_days}")
    print(f"[BACKUP-CLEANUP] total_backups={len(branches)}")
    print(f"[BACKUP-CLEANUP] expired_candidates={len(expired)}")
    for b in expired:
        print(f"  - {b.name} | {b.commit_date.isoformat()}")

    if not args.apply:
        print("[BACKUP-CLEANUP] dry-run only (no changes applied)")
        return 0

    if not expired:
        print("[BACKUP-CLEANUP] nothing to delete")
        return 0

    delete_branches([b.name for b in expired])
    print(f"[BACKUP-CLEANUP] deleted={len(expired)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
