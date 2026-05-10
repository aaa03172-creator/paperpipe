#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.legacy_trial_extraction_constants import LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE


LEGACY_KEY_PATTERN = re.compile(r"(?m)^(\s*)trial_extraction(\s*:)")
CONFIG_SUFFIXES = {".yaml", ".yml"}
SKIP_PREFIXES = (
    ".codex/",
    "storage/",
    "frontend/.e2e-backend-runtime/",
    "tests/fixtures/",
    "__pycache__/",
)


def _should_skip(rel_path: str, *, include_generated: bool) -> bool:
    if include_generated:
        return False
    return any(rel_path.startswith(prefix) for prefix in SKIP_PREFIXES)


def _is_historical_snapshot_config(rel_path: str) -> bool:
    return rel_path.startswith("storage/artifacts/") and rel_path.endswith("/snapshots/config.yaml")


def _rewrite_text(text: str) -> tuple[str, int]:
    return LEGACY_KEY_PATTERN.subn(r"\1specialty_trial_extraction\2", text)


def _migrate_root(
    root: Path,
    *,
    include_generated: bool,
    include_historical_snapshots: bool,
    apply_changes: bool,
) -> tuple[list[str], list[str]]:
    rewritten: list[str] = []
    preserved_historical_snapshots: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in CONFIG_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if _should_skip(rel, include_generated=include_generated):
            continue
        original = path.read_text(encoding="utf-8", errors="ignore")
        updated, replacements = _rewrite_text(original)
        if replacements <= 0:
            continue
        if _is_historical_snapshot_config(rel) and not include_historical_snapshots:
            preserved_historical_snapshots.append(rel)
            continue
        if apply_changes:
            path.write_text(updated, encoding="utf-8")
        rewritten.append(rel)
    return sorted(rewritten), sorted(preserved_historical_snapshots)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite deprecated `trial_extraction` YAML keys to `specialty_trial_extraction` "
            f"before the scheduled removal date ({LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE})."
        )
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to scan. Default: current working directory.",
    )
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="Include generated/runtime directories such as storage/ and frontend/.e2e-backend-runtime/.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the key rewrite in place. Default is dry-run.",
    )
    parser.add_argument(
        "--include-historical-snapshots",
        action="store_true",
        help=(
            "Also rewrite historical storage snapshot configs under storage/artifacts/**/snapshots/. "
            "Default behavior preserves them."
        ),
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    rewritten, preserved_historical_snapshots = _migrate_root(
        root,
        include_generated=args.include_generated,
        include_historical_snapshots=bool(args.include_historical_snapshots),
        apply_changes=bool(args.apply),
    )
    summary = {
        "root": str(root),
        "removal_date": LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE,
        "mode": "apply" if args.apply else "dry_run",
        "rewritten_count": len(rewritten),
        "rewritten_files": rewritten,
        "preserved_historical_snapshot_count": len(preserved_historical_snapshots),
        "preserved_historical_snapshots": preserved_historical_snapshots,
        "include_generated": bool(args.include_generated),
        "include_historical_snapshots": bool(args.include_historical_snapshots),
    }
    print(json.dumps(summary, indent=2))
    if rewritten and not args.apply:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
