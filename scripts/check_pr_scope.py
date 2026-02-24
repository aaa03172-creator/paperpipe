from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# Allow direct script execution: `python3 scripts/check_pr_scope.py`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.pr_scope_guard import (
    DEFAULT_ALLOWED_DOCS_WITH_CODE,
    ScopeReport,
    classify_scope,
)


def _run_git(args: list[str]) -> str:
    out = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return out.stdout.strip()


def _diff_files(base: str, head: str) -> list[str]:
    diff = _run_git(["diff", "--name-only", f"{base}...{head}"])
    return [line.strip() for line in diff.splitlines() if line.strip()]


def _format_scope(report: ScopeReport) -> str:
    lines: list[str] = []
    lines.append(f"[PR-SCOPE] doc_files={len(report.doc_files)} code_files={len(report.code_files)}")
    if report.doc_files:
        lines.append(f"[PR-SCOPE] docs={', '.join(report.doc_files)}")
    if report.code_files:
        lines.append(f"[PR-SCOPE] code={', '.join(report.code_files)}")
    if report.allowed_doc_files:
        lines.append(f"[PR-SCOPE] allowed_docs_with_code={', '.join(report.allowed_doc_files)}")
    if report.blocked_doc_files:
        lines.append(f"[PR-SCOPE] blocked_docs_with_code={', '.join(report.blocked_doc_files)}")
    return "\n".join(lines)


def _parse_allowed_docs(raw_values: Iterable[str] | None) -> set[str]:
    if not raw_values:
        return set(DEFAULT_ALLOWED_DOCS_WITH_CODE)
    return {value.strip().replace("\\", "/") for value in raw_values if value.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR scope guard: block mixed code+docs PRs except explicitly allowed docs sync files."
    )
    parser.add_argument("--base", help="Base commit/ref for diff mode.")
    parser.add_argument("--head", help="Head commit/ref for diff mode.")
    parser.add_argument(
        "--files",
        nargs="*",
        help="Explicit changed files. If provided, base/head diff is ignored.",
    )
    parser.add_argument(
        "--allow-doc-with-code",
        action="append",
        dest="allowed_docs",
        help=(
            "Doc file allowed to appear with code changes. "
            "Repeat for multiple files. Default: docs/Pending_PR_Queue.md"
        ),
    )
    args = parser.parse_args()

    allowed_docs = _parse_allowed_docs(args.allowed_docs)

    if args.files:
        files = args.files
    else:
        if not args.base or not args.head:
            parser.error("Provide --files OR both --base and --head.")
        files = _diff_files(args.base, args.head)

    report = classify_scope(files, allowed_docs_with_code=allowed_docs)
    print(_format_scope(report))

    if not report.has_mixed_scope:
        print("[PR-SCOPE] PASS: single-scope change set")
        return 0

    if report.is_allowed:
        print("[PR-SCOPE] PASS: mixed scope allowed by docs-with-code allowlist")
        return 0

    print("[PR-SCOPE] FAIL: mixed code/docs scope with blocked doc files")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
