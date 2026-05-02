#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.deepread_handoff_gate_scope import classify_deepread_handoff_gate_scope


def _run_git(args: list[str]) -> str:
    out = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return out.stdout.strip()


def _diff_files(base: str, head: str) -> list[str]:
    diff = _run_git(["diff", "--name-only", f"{base}...{head}"])
    return [line.strip() for line in diff.splitlines() if line.strip()]


def _merge_base(base_ref: str, head_ref: str) -> str:
    return _run_git(["merge-base", base_ref, head_ref]).strip()


def resolve_changed_files(
    *,
    files: list[str] | None,
    base: str | None,
    head: str | None,
    against_ref: str | None,
) -> list[str]:
    if files:
        return files

    normalized_head = str(head or "HEAD").strip() or "HEAD"
    if against_ref:
        merge_base = _merge_base(str(against_ref).strip(), normalized_head)
        return _diff_files(merge_base, normalized_head)

    if base and head:
        return _diff_files(str(base).strip(), str(head).strip())

    raise ValueError("Provide --files OR both --base and --head OR --against-ref.")


def _to_payload(report) -> dict[str, Any]:
    return {
        "mode": report.mode,
        "reason": report.reason,
        "relevant_files": report.relevant_files,
        "continuity_files": report.continuity_files,
        "cross_paper_files": report.cross_paper_files,
        "ignored_doc_files": report.ignored_doc_files,
    }


def _compact_report_text(report) -> str:
    parts = [f"mode={report.mode}"]
    if report.relevant_files:
        parts.append(f"relevant={len(report.relevant_files)}")
    if report.continuity_files:
        parts.append(f"continuity={len(report.continuity_files)}")
    if report.cross_paper_files:
        parts.append(f"cross_paper={len(report.cross_paper_files)}")
    if report.ignored_doc_files:
        parts.append(f"ignored_docs={len(report.ignored_doc_files)}")
    return " ".join(parts)


def _print_report(report) -> None:
    print(f"[DEEPREAD-HANDOFF-GATE] mode={report.mode}")
    print(f"[DEEPREAD-HANDOFF-GATE] reason={report.reason}")
    if report.relevant_files:
        print(f"[DEEPREAD-HANDOFF-GATE] relevant_files={', '.join(report.relevant_files)}")
    if report.continuity_files:
        print(f"[DEEPREAD-HANDOFF-GATE] continuity_files={', '.join(report.continuity_files)}")
    if report.cross_paper_files:
        print(f"[DEEPREAD-HANDOFF-GATE] cross_paper_files={', '.join(report.cross_paper_files)}")
    if report.ignored_doc_files:
        print(f"[DEEPREAD-HANDOFF-GATE] ignored_doc_files={', '.join(report.ignored_doc_files)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recommend whether the deep-read handoff lane needs no gate, a coric continuity gate, or a coric+multicase cross-paper gate."
    )
    parser.add_argument("--base", help="Base commit/ref for diff mode.")
    parser.add_argument("--head", help="Head commit/ref for diff mode.")
    parser.add_argument(
        "--against-ref",
        help="Diff the current or specified head against the merge-base with this integration ref (for example origin/main).",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Explicit changed files. If provided, base/head diff is ignored.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of line output.")
    args = parser.parse_args()

    try:
        files = resolve_changed_files(
            files=list(args.files) if args.files else None,
            base=args.base,
            head=args.head,
            against_ref=args.against_ref,
        )
    except ValueError as exc:
        parser.error(str(exc))

    report = classify_deepread_handoff_gate_scope(files)
    if args.json:
        print(
            "[recommend_deepread_handoff_gate_mode] " + _compact_report_text(report),
            file=sys.stderr,
        )
        print(json.dumps(_to_payload(report), ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
