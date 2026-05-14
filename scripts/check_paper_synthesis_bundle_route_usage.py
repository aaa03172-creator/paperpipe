#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BUNDLE_ROUTE_PATTERNS = (
    re.compile(r"/paper-syntheses/\{synthesis_id\}(?!/)"),
    re.compile(r"/paper-syntheses/\$\{[^}]+\}(?!/)"),
    re.compile(r"/paper-syntheses/papersynth_[A-Za-z0-9._-]+(?:$|[\s\"'`)},\]])"),
    re.compile(r"/paper-syntheses/papersynth_missing(?:$|[\s\"'`)},\]])"),
)

ALLOWED = {
    "backend/routers/paper_syntheses.py",
    "docs/PAPER_SYNTHESIS.md",
    "docs/UX_REVIEW_REPORT_workbench-persona-profile-split.md",
    "scripts/check_paper_synthesis_bundle_route_usage.py",
    "scripts/check_paper_synthesis_bundle_route_removal_readiness.py",
    "tests/test_no_new_paper_synthesis_bundle_route_usage.py",
    "tests/test_paper_synthesis_bundle_route_scripts.py",
    "tests/test_paper_syntheses_api.py",
}

SKIP_PREFIXES = (
    ".codex/",
    "build/",
    "docs/reports/",
    "storage/",
    "frontend/.e2e-backend-runtime/",
    "tests/fixtures/",
    "__pycache__/",
)

TEXT_SUFFIXES = {".py", ".md", ".ts", ".tsx", ".yaml", ".yml"}


def _should_skip(rel_path: str, *, include_generated: bool) -> bool:
    if include_generated:
        return rel_path.startswith("__pycache__/")
    return any(rel_path.startswith(prefix) for prefix in SKIP_PREFIXES)


def _scan_root(root: Path, *, include_generated: bool) -> tuple[list[str], list[str]]:
    offenders: list[str] = []
    allowlisted_surfaces: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if _should_skip(rel, include_generated=include_generated):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not any(pattern.search(text) for pattern in BUNDLE_ROUTE_PATTERNS):
            continue
        if rel in ALLOWED:
            allowlisted_surfaces.append(rel)
            continue
        offenders.append(rel)

    return sorted(set(offenders)), sorted(set(allowlisted_surfaces))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the repo for bare `/paper-syntheses/{synthesis_id}` compatibility-route usage outside "
            "the bounded allowlist."
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
    offenders, allowlisted_surfaces = _scan_root(root, include_generated=args.include_generated)
    summary = {
        "root": str(root),
        "offender_count": len(offenders),
        "offenders": offenders,
        "allowlisted_surface_count": len(allowlisted_surfaces),
        "allowlisted_surfaces": allowlisted_surfaces,
        "include_generated": bool(args.include_generated),
    }
    print(json.dumps(summary, indent=2))
    return 0 if not offenders else 2


if __name__ == "__main__":
    raise SystemExit(main())
