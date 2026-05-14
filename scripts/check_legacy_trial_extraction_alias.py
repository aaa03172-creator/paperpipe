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


LEGACY_KEY_PATTERN = re.compile(r"(?m)^\s*trial_extraction\s*:")
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


def _scan_root(root: Path, *, include_generated: bool) -> tuple[list[str], list[str]]:
    offenders: list[str] = []
    preserved_historical_snapshots: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in CONFIG_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if _should_skip(rel, include_generated=include_generated):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not LEGACY_KEY_PATTERN.search(text):
            continue
        if _is_historical_snapshot_config(rel):
            preserved_historical_snapshots.append(rel)
            continue
        offenders.append(rel)
    return sorted(offenders), sorted(preserved_historical_snapshots)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit YAML configs for deprecated `trial_extraction` usage before the "
            f"scheduled removal date ({LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE})."
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
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    offenders, preserved_historical_snapshots = _scan_root(root, include_generated=args.include_generated)
    summary = {
        "root": str(root),
        "removal_date": LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE,
        "offender_count": len(offenders),
        "offenders": offenders,
        "preserved_historical_snapshot_count": len(preserved_historical_snapshots),
        "preserved_historical_snapshots": preserved_historical_snapshots,
        "include_generated": bool(args.include_generated),
    }
    print(json.dumps(summary, indent=2))
    return 0 if not offenders else 2


if __name__ == "__main__":
    raise SystemExit(main())
