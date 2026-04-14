#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.eval.compare_deepread_handoff_audits import compare_deepread_handoff_audits

_DEFAULT_OUT_DIR = _REPO_ROOT / "snapshots" / "deepread_handoff_gate"
_DEFAULT_CORIC_BASELINE = (
    _REPO_ROOT / "baselines" / "deepread_handoff" / "deepread_handoff_coric_regression_20260408_backfilled"
)
_DEFAULT_MULTICASE_BASELINE = (
    _REPO_ROOT / "baselines" / "deepread_handoff" / "deepread_handoff_multicase_regression_20260408_backfilled"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _required_cases(mode: str) -> list[str]:
    normalized = str(mode or "").strip().lower()
    if normalized == "continuity":
        return ["coric"]
    if normalized == "cross-paper":
        return ["coric", "multicase"]
    raise ValueError(f"unsupported_mode={mode}")


def build_deepread_handoff_gate_summary(
    *,
    mode: str,
    case_reports: dict[str, dict[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    required_cases = _required_cases(mode)
    missing_cases = [case for case in required_cases if case not in case_reports]
    if missing_cases:
        raise ValueError(f"missing_case_reports={','.join(missing_cases)}")

    case_rows: dict[str, dict[str, Any]] = {}
    failed_cases: list[str] = []

    for case_name in required_cases:
        report = case_reports[case_name]
        decision = report.get("decision") or {}
        passed = bool(decision.get("passed"))
        failed_checks = [str(item) for item in (decision.get("failed_checks") or []) if str(item).strip()]
        regressions = [str(item) for item in (decision.get("regressions") or []) if str(item).strip()]
        baseline = report.get("baseline") or {}
        new = report.get("new") or {}
        if not passed:
            failed_cases.append(case_name)

        case_rows[case_name] = {
            "passed": passed,
            "baseline_path": baseline.get("path"),
            "baseline_run_id": baseline.get("run_id"),
            "baseline_run_count": baseline.get("run_count"),
            "new_path": new.get("path"),
            "new_run_id": new.get("run_id"),
            "new_run_count": new.get("run_count"),
            "failed_checks": failed_checks,
            "regressions": regressions,
        }

    return {
        "schema_version": "deepread_handoff_gate.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "mode": mode,
        "decision": {
            "passed": len(failed_cases) == 0,
            "required_cases": required_cases,
            "failed_cases": failed_cases,
        },
        "cases": case_rows,
    }


def run_deepread_handoff_gate(
    *,
    mode: str,
    coric_baseline: Path,
    coric_new: Path,
    multicase_baseline: Path,
    multicase_new: Path | None,
    out_dir: Path,
    run_id: str,
) -> Path:
    normalized_mode = str(mode or "").strip().lower()
    required_cases = _required_cases(normalized_mode)
    if "multicase" in required_cases and multicase_new is None:
        raise ValueError("multicase_new_required_for_cross_paper")

    run_root = out_dir / run_id
    case_reports: dict[str, dict[str, Any]] = {}

    case_reports["coric"] = compare_deepread_handoff_audits(
        baseline=coric_baseline,
        new=coric_new,
        out=run_root / "cases" / "coric" / "report.json",
    )
    if "multicase" in required_cases:
        assert multicase_new is not None
        case_reports["multicase"] = compare_deepread_handoff_audits(
            baseline=multicase_baseline,
            new=multicase_new,
            out=run_root / "cases" / "multicase" / "report.json",
        )

    summary = build_deepread_handoff_gate_summary(
        mode=normalized_mode,
        case_reports=case_reports,
        run_id=run_id,
    )
    _write_json(run_root / "summary.json", summary)
    (run_root / "summary.txt").write_text(
        "\n".join(
            [
                f"mode={summary['mode']}",
                f"passed={summary['decision']['passed']}",
                f"required_cases={','.join(summary['decision']['required_cases'])}",
                f"failed_cases={','.join(summary['decision']['failed_cases']) if summary['decision']['failed_cases'] else '-'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the bounded deep-read handoff compare gate for continuity-only or cross-paper changes."
    )
    parser.add_argument("--mode", required=True, choices=["continuity", "cross-paper"])
    parser.add_argument("--coric-new", required=True, help="Coric audit run directory or summary.json path.")
    parser.add_argument(
        "--multicase-new",
        default="",
        help="Multicase audit run directory or summary.json path. Required for cross-paper mode.",
    )
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
    parser.add_argument("--out-dir", default=str(_DEFAULT_OUT_DIR), help="Output directory for gate reports.")
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_deepread_handoff_gate(
        mode=str(args.mode),
        coric_baseline=Path(args.coric_baseline).expanduser().resolve(),
        coric_new=Path(args.coric_new).expanduser().resolve(),
        multicase_baseline=Path(args.multicase_baseline).expanduser().resolve(),
        multicase_new=Path(args.multicase_new).expanduser().resolve() if args.multicase_new else None,
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    print(f"[check_deepread_handoff_gate] out={run_root}")
    print(f"[check_deepread_handoff_gate] summary={run_root / 'summary.json'}")
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    print(f"[check_deepread_handoff_gate] passed={summary['decision']['passed']}")
    return 0 if summary["decision"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
