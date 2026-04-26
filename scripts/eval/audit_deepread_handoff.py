#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _normalize_status(value: Any, *, missing: str = "missing") -> str:
    normalized = str(value or "").strip().lower()
    return normalized or missing


def _normalize_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    codes: list[str] = []
    for item in value:
        code = str(item or "").strip()
        if code:
            codes.append(code)
    return codes


def _quality_gate_check_status(quality_gate: dict[str, Any], name: str) -> str:
    checks = quality_gate.get("checks")
    if not isinstance(checks, list):
        return "missing"
    for item in checks:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip() != name:
            continue
        return _normalize_status(item.get("status"))
    return "missing"


def _find_run_dirs(runs_root: Path) -> list[Path]:
    run_dirs: list[Path] = []
    for path in sorted(runs_root.rglob("quality_gate.json")):
        run_dirs.append(path.parent)
    return run_dirs


def _remap_repo_root_candidate(path: Path, *, repo_root: Path) -> Path:
    repo_root = repo_root.expanduser().resolve()
    if path.exists():
        return path.resolve()

    candidates: list[Path] = []
    parts = list(path.parts)
    repo_name = repo_root.name
    repo_indexes = [index for index, part in enumerate(parts) if part == repo_name]
    for index in reversed(repo_indexes):
        suffix = parts[index + 1 :]
        if suffix:
            candidates.append(repo_root.joinpath(*suffix))

    for anchor in ("storage", "snapshots", "goldset", "baselines"):
        if anchor in parts:
            index = parts.index(anchor)
            suffix = parts[index:]
            if suffix:
                candidates.append(repo_root.joinpath(*suffix))

    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)

    for candidate in unique_candidates:
        if candidate.exists():
            return candidate.resolve()
    if unique_candidates:
        return unique_candidates[0]
    return path.resolve()


def _resolve_manifest_run_dir(raw_run_dir: str, *, manifest_path: Path, repo_root: Path) -> Path:
    candidate = Path(raw_run_dir).expanduser()
    if not candidate.is_absolute():
        return (manifest_path.parent / candidate).resolve()
    return _remap_repo_root_candidate(candidate.resolve(), repo_root=repo_root)


def load_manifest_run_dirs(manifest_path: Path, *, repo_root: Path | None = None) -> list[Path]:
    repo_root = (repo_root or REPO_ROOT).expanduser().resolve()
    payload = _load_json(manifest_path)
    if str(payload.get("schema_version") or "") != "deepread_handoff_manifest.v1":
        raise RuntimeError(f"unsupported_manifest_schema={manifest_path}")
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise RuntimeError(f"manifest_runs_missing={manifest_path}")

    run_dirs: list[Path] = []
    for index, item in enumerate(runs):
        if not isinstance(item, dict):
            raise RuntimeError(f"manifest_run_invalid={manifest_path} index={index}")
        raw_run_dir = str(item.get("run_dir") or "").strip()
        if not raw_run_dir:
            raise RuntimeError(f"manifest_run_dir_missing={manifest_path} index={index}")
        run_dirs.append(_resolve_manifest_run_dir(raw_run_dir, manifest_path=manifest_path, repo_root=repo_root))
    return run_dirs


def _collect_run_row(run_dir: Path) -> dict[str, Any]:
    quality_gate = _load_json(run_dir / "quality_gate.json")
    context_manifest_path = run_dir / "context_manifest.json"
    context_manifest = _load_json(context_manifest_path) if context_manifest_path.exists() else {}

    step_summary = quality_gate.get("step_stability_summary")
    if not isinstance(step_summary, dict):
        step_summary = {}
    recovery_summary = quality_gate.get("failure_recovery_summary")
    if not isinstance(recovery_summary, dict):
        recovery_summary = {}
    goal_summary = context_manifest.get("goal_drift_summary")
    if not isinstance(goal_summary, dict):
        goal_summary = {}

    paper_id = str(quality_gate.get("paper_id") or context_manifest.get("paper_id") or "").strip()
    run_id = str(quality_gate.get("run_id") or context_manifest.get("run_id") or run_dir.name).strip()
    overall_status = _normalize_status(quality_gate.get("overall_status"), missing="unknown")
    step_status = _normalize_status(step_summary.get("status"))
    recovery_status = _normalize_status(recovery_summary.get("status"))
    goal_status = _normalize_status(goal_summary.get("status"))
    section_navigation_status = _quality_gate_check_status(quality_gate, "section_navigation_signal")

    return {
        "paper_id": paper_id or None,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "overall_status": overall_status,
        "current_promotion_candidate": bool(quality_gate.get("current_promotion_candidate")),
        "review_ready": bool(quality_gate.get("review_ready")),
        "quality_gate_reason_codes": _normalize_codes(quality_gate.get("reason_codes")),
        "quality_gate_hard_fail_codes": _normalize_codes(quality_gate.get("hard_fail_codes")),
        "step_stability_status": step_status,
        "step_stability_reason_codes": _normalize_codes(step_summary.get("reason_codes")),
        "failure_recovery_status": recovery_status,
        "failure_recovery_reason_codes": _normalize_codes(recovery_summary.get("reason_codes")),
        "goal_drift_status": goal_status,
        "goal_drift_reason_codes": _normalize_codes(goal_summary.get("reason_codes")),
        "section_navigation_signal_status": section_navigation_status,
        "context_manifest_present": context_manifest_path.exists(),
    }


def run_audit(
    *,
    run_dirs: list[Path],
    out_dir: Path,
    run_id: str,
    manifest_paths: list[Path] | None = None,
) -> Path:
    resolved_run_dirs = [path.expanduser().resolve() for path in run_dirs]
    resolved_manifest_paths = [path.expanduser().resolve() for path in (manifest_paths or [])]
    rows = [_collect_run_row(path) for path in resolved_run_dirs]

    overall_counts: Counter[str] = Counter()
    step_counts: Counter[str] = Counter()
    recovery_counts: Counter[str] = Counter()
    goal_counts: Counter[str] = Counter()
    section_navigation_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    hard_fail_counts: Counter[str] = Counter()

    for row in rows:
        overall_counts[row["overall_status"]] += 1
        step_counts[row["step_stability_status"]] += 1
        recovery_counts[row["failure_recovery_status"]] += 1
        goal_counts[row["goal_drift_status"]] += 1
        section_navigation_counts[row["section_navigation_signal_status"]] += 1
        for code in row["quality_gate_reason_codes"]:
            reason_counts[code] += 1
        for code in row["quality_gate_hard_fail_codes"]:
            hard_fail_counts[code] += 1
        for code in row["step_stability_reason_codes"]:
            reason_counts[code] += 1
        for code in row["failure_recovery_reason_codes"]:
            reason_counts[code] += 1
        for code in row["goal_drift_reason_codes"]:
            reason_counts[code] += 1

    run_root = out_dir / run_id
    summary = {
        "schema_version": "deepread_handoff_audit.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "inputs": {
            "manifest_count": len(resolved_manifest_paths),
            "manifests": [str(path) for path in resolved_manifest_paths],
            "run_dir_count": len(resolved_run_dirs),
            "run_dirs": [str(path) for path in resolved_run_dirs],
        },
        "run_count": len(rows),
        "overall_status_counts": {key: int(value) for key, value in sorted(overall_counts.items())},
        "step_stability_status_counts": {key: int(value) for key, value in sorted(step_counts.items())},
        "failure_recovery_status_counts": {key: int(value) for key, value in sorted(recovery_counts.items())},
        "goal_drift_status_counts": {key: int(value) for key, value in sorted(goal_counts.items())},
        "section_navigation_signal_status_counts": {
            key: int(value) for key, value in sorted(section_navigation_counts.items())
        },
        "review_ready_count": sum(1 for row in rows if row["review_ready"]),
        "promotion_candidate_count": sum(1 for row in rows if row["current_promotion_candidate"]),
        "context_manifest_missing_count": sum(1 for row in rows if not row["context_manifest_present"]),
        "runs_with_goal_drift_warn": [row["run_id"] for row in rows if row["goal_drift_status"] == "warn"],
        "runs_with_section_navigation_signal_warn_or_fail": [
            row["run_id"] for row in rows if row["section_navigation_signal_status"] in {"warn", "fail"}
        ],
        "runs_with_step_stability_warn_or_fail": [
            row["run_id"] for row in rows if row["step_stability_status"] in {"warn", "fail"}
        ],
        "runs_with_failure_recovery_warn_or_fail": [
            row["run_id"] for row in rows if row["failure_recovery_status"] in {"warn", "fail"}
        ],
        "reason_code_counts": {key: int(value) for key, value in sorted(reason_counts.items())},
        "hard_fail_code_counts": {key: int(value) for key, value in sorted(hard_fail_counts.items())},
    }
    details = {
        "schema_version": "deepread_handoff_audit_details.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "runs": rows,
    }
    _write_json(run_root / "summary.json", summary)
    _write_json(run_root / "details.json", details)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate deep-read handoff quality and context summaries across saved run directories.")
    parser.add_argument("--manifest", action="append", default=[], help="Manifest listing saved deep-read run directories. Repeat as needed.")
    parser.add_argument("--runs-root", default="", help="Optional root directory to scan recursively for quality_gate.json files.")
    parser.add_argument("--run-dir", action="append", default=[], help="Explicit deep-read artifact run directory. Repeat as needed.")
    parser.add_argument("--out-dir", required=True, help="Directory to write audit outputs into.")
    parser.add_argument("--run-id", default="", help="Optional audit run id. Defaults to a UTC timestamp.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    manifest_paths: list[Path] = [Path(item).expanduser().resolve() for item in args.manifest if str(item).strip()]
    run_dirs: list[Path] = [Path(item).expanduser().resolve() for item in args.run_dir if str(item).strip()]
    for manifest_path in manifest_paths:
        run_dirs.extend(load_manifest_run_dirs(manifest_path))
    if args.runs_root:
        run_dirs.extend(_find_run_dirs(Path(args.runs_root).expanduser().resolve()))
    unique_run_dirs: list[Path] = []
    seen: set[Path] = set()
    for path in run_dirs:
        if path in seen:
            continue
        seen.add(path)
        unique_run_dirs.append(path)
    if not unique_run_dirs:
        raise SystemExit("no_run_dirs_provided")

    run_id = args.run_id.strip() or f"deepread_handoff_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_root = run_audit(
        run_dirs=unique_run_dirs,
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        manifest_paths=manifest_paths,
    )
    print(f"[audit_deepread_handoff] out={run_root}")
    print(f"[audit_deepread_handoff] summary={run_root / 'summary.json'}")


if __name__ == "__main__":
    main()
