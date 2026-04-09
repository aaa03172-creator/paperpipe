#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.eval.check_deepread_handoff_gate import run_deepread_handoff_gate
from scripts.eval.recommend_deepread_handoff_gate_mode import resolve_changed_files
from src.services.deepread_handoff_gate_scope import classify_deepread_handoff_gate_scope

_DEFAULT_OUT_DIR = REPO_ROOT / "snapshots" / "deepread_handoff_gate_runs"
_DEFAULT_CORIC_BASELINE = (
    REPO_ROOT / "baselines" / "deepread_handoff" / "deepread_handoff_coric_regression_20260408_backfilled"
)
_DEFAULT_MULTICASE_BASELINE = (
    REPO_ROOT / "baselines" / "deepread_handoff" / "deepread_handoff_multicase_regression_20260408_backfilled"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_recommended_deepread_handoff_gate(
    *,
    changed_files: list[str],
    coric_new: Path | None,
    multicase_new: Path | None,
    coric_baseline: Path,
    multicase_baseline: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    recommendation = classify_deepread_handoff_gate_scope(changed_files)
    run_root = out_dir / run_id

    summary: dict[str, Any] = {
        "schema_version": "deepread_handoff_gate_run.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "recommendation": {
            "mode": recommendation.mode,
            "reason": recommendation.reason,
            "relevant_files": recommendation.relevant_files,
            "continuity_files": recommendation.continuity_files,
            "cross_paper_files": recommendation.cross_paper_files,
            "ignored_doc_files": recommendation.ignored_doc_files,
        },
        "gate": {
            "attempted": False,
            "passed": None,
            "path": None,
            "mode": None,
        },
    }

    if recommendation.mode == "not_applicable":
        _write_json(run_root / "summary.json", summary)
        return run_root

    if coric_new is None:
        raise ValueError("coric_new_required_when_gate_mode_applies")
    if recommendation.mode == "cross-paper" and multicase_new is None:
        raise ValueError("multicase_new_required_for_cross_paper")

    gate_root = run_deepread_handoff_gate(
        mode=recommendation.mode,
        coric_baseline=coric_baseline,
        coric_new=coric_new,
        multicase_baseline=multicase_baseline,
        multicase_new=multicase_new,
        out_dir=run_root / "gate",
        run_id="gate",
    )
    gate_summary = json.loads((gate_root / "summary.json").read_text(encoding="utf-8"))
    summary["gate"] = {
        "attempted": True,
        "passed": bool((gate_summary.get("decision") or {}).get("passed")),
        "path": str(gate_root / "summary.json"),
        "mode": recommendation.mode,
    }
    _write_json(run_root / "summary.json", summary)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recommend the deep-read handoff gate mode from changed files and, when applicable, run that gate in one step."
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
    parser.add_argument("--coric-new", default="", help="Coric audit run directory or summary.json path.")
    parser.add_argument("--multicase-new", default="", help="Multicase audit run directory or summary.json path.")
    parser.add_argument(
        "--coric-baseline",
        default=str(_DEFAULT_CORIC_BASELINE),
        help="Coric baseline directory or summary.json path.",
    )
    parser.add_argument(
        "--multicase-baseline",
        default=str(_DEFAULT_MULTICASE_BASELINE),
        help="Multicase baseline directory or summary.json path.",
    )
    parser.add_argument("--out-dir", default=str(_DEFAULT_OUT_DIR), help="Output directory for combined recommendation+gate reports.")
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        changed_files = resolve_changed_files(
            files=list(args.files) if args.files else None,
            base=args.base,
            head=args.head,
            against_ref=args.against_ref,
        )
    except ValueError as exc:
        parser.error(str(exc))

    run_root = run_recommended_deepread_handoff_gate(
        changed_files=changed_files,
        coric_new=Path(args.coric_new).expanduser().resolve() if args.coric_new else None,
        multicase_new=Path(args.multicase_new).expanduser().resolve() if args.multicase_new else None,
        coric_baseline=Path(args.coric_baseline).expanduser().resolve(),
        multicase_baseline=Path(args.multicase_baseline).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    print(f"[run_recommended_deepread_handoff_gate] out={run_root}")
    print(f"[run_recommended_deepread_handoff_gate] mode={summary['recommendation']['mode']}")
    print(f"[run_recommended_deepread_handoff_gate] gate_attempted={summary['gate']['attempted']}")
    print(f"[run_recommended_deepread_handoff_gate] gate_passed={summary['gate']['passed']}")
    return 0 if summary["gate"]["attempted"] is not True or summary["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
