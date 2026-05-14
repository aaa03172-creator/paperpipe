from __future__ import annotations

import argparse
import os
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
    classify_title_scope,
)
from src.services.deepread_handoff_gate_scope import classify_deepread_handoff_gate_scope


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
    if report.has_mixed_scope:
        if report.allowed_doc_files:
            lines.append(f"[PR-SCOPE] allowed_docs_with_code={', '.join(report.allowed_doc_files)}")
        if report.blocked_doc_files:
            lines.append(f"[PR-SCOPE] blocked_docs_with_code={', '.join(report.blocked_doc_files)}")
    return "\n".join(lines)


def _format_title_scope(report) -> str:
    lines: list[str] = []
    lines.append(f"[PR-TITLE-SCOPE] policy={report.policy}")
    if report.violating_files:
        lines.append(f"[PR-TITLE-SCOPE] violating_files={', '.join(report.violating_files)}")
    return "\n".join(lines)


def _format_deepread_handoff_gate_scope(files: list[str]) -> str:
    report = classify_deepread_handoff_gate_scope(files)
    lines: list[str] = []
    lines.append(f"[DEEPREAD-HANDOFF-GATE] mode={report.mode}")
    lines.append(f"[DEEPREAD-HANDOFF-GATE] reason={report.reason}")
    if report.relevant_files:
        lines.append(f"[DEEPREAD-HANDOFF-GATE] relevant_files={', '.join(report.relevant_files)}")
    if report.continuity_files:
        lines.append(f"[DEEPREAD-HANDOFF-GATE] continuity_files={', '.join(report.continuity_files)}")
    if report.cross_paper_files:
        lines.append(f"[DEEPREAD-HANDOFF-GATE] cross_paper_files={', '.join(report.cross_paper_files)}")
    if report.ignored_doc_files:
        lines.append(f"[DEEPREAD-HANDOFF-GATE] ignored_doc_files={', '.join(report.ignored_doc_files)}")
    if report.mode == "continuity":
        lines.append(
            "[DEEPREAD-HANDOFF-GATE] next=python3 scripts/eval/run_recommended_deepread_handoff_gate.py --against-ref <ref> --coric-new <audit_dir> --run-id <run_id>"
        )
    elif report.mode == "cross-paper":
        lines.append(
            "[DEEPREAD-HANDOFF-GATE] next=python3 scripts/eval/run_recommended_deepread_handoff_gate.py --against-ref <ref> --coric-new <coric_audit_dir> --multicase-new <multicase_audit_dir> --run-id <run_id>"
        )
    return "\n".join(lines)


def _deepread_handoff_gate_next_command(report) -> str | None:
    if report.mode == "continuity":
        return (
            "python3 scripts/eval/run_recommended_deepread_handoff_gate.py "
            "--against-ref <ref> --coric-new <audit_dir> --run-id <run_id>"
        )
    if report.mode == "cross-paper":
        return (
            "python3 scripts/eval/run_recommended_deepread_handoff_gate.py "
            "--against-ref <ref> --coric-new <coric_audit_dir> "
            "--multicase-new <multicase_audit_dir> --run-id <run_id>"
        )
    return None


def _deepread_handoff_gate_annotation_line(files: list[str]) -> str | None:
    report = classify_deepread_handoff_gate_scope(files)
    if report.mode == "not_applicable":
        return None
    next_command = _deepread_handoff_gate_next_command(report)
    message = f"mode={report.mode}; reason={report.reason}"
    if next_command:
        message += f"; next={next_command}"
    return f"::notice title=DeepRead Handoff Gate::{message}"


def _write_deepread_handoff_gate_summary(files: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path:
        return

    report = classify_deepread_handoff_gate_scope(files)
    next_command = _deepread_handoff_gate_next_command(report)
    lines: list[str] = [
        "## DeepRead Handoff Gate Advisory",
        "",
        f"- mode: `{report.mode}`",
        f"- reason: {report.reason}",
    ]
    if report.relevant_files:
        lines.append(f"- relevant files: `{', '.join(report.relevant_files)}`")
    if next_command:
        lines.append(f"- next: `{next_command}`")
    elif report.mode == "not_applicable":
        lines.append("- next: no deep-read handoff gate needed for this diff")
    summary_file = Path(summary_path).expanduser()
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with summary_file.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _emit_deepread_handoff_gate_annotation(files: list[str]) -> None:
    if not os.environ.get("GITHUB_ACTIONS", "").strip():
        return
    annotation = _deepread_handoff_gate_annotation_line(files)
    if annotation:
        print(annotation)


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
    parser.add_argument(
        "--title",
        default="",
        help="Optional PR title for title-scope policy checks (docs*/test* prefixes).",
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
    elif report.is_allowed:
        print("[PR-SCOPE] PASS: mixed scope allowed by docs-with-code allowlist")
    else:
        print("[PR-SCOPE] FAIL: mixed code/docs scope with blocked doc files")
        return 2

    title_report = classify_title_scope(args.title, files, allowed_docs_with_code=allowed_docs)
    print(_format_title_scope(title_report))
    if not title_report.is_allowed:
        print(f"[PR-TITLE-SCOPE] FAIL: {title_report.message}")
        return 2

    print("[PR-TITLE-SCOPE] PASS")
    print(_format_deepread_handoff_gate_scope(files))
    _write_deepread_handoff_gate_summary(files)
    _emit_deepread_handoff_gate_annotation(files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
