#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def _set_db_path_override(db_path: Path | None) -> None:
    if db_path is None:
        return
    os.environ["PAPERPIPE_DB_PATH"] = str(db_path.expanduser().resolve())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _latest_timestamp(incidents: list[dict[str, Any]]) -> str | None:
    for incident in incidents:
        captured_at = str(incident.get("captured_at") or "").strip()
        if captured_at:
            return captured_at
        file_mtime = str(incident.get("file_mtime") or "").strip()
        if file_mtime:
            return file_mtime
    return None


def _build_decision(
    *,
    incidents_total: int,
    parse_error_total: int,
    stale_candidate_incidents_total: int,
    unique_jobs_total: int,
    current_stale_candidates_total: int,
    min_incidents: int,
    min_unique_jobs: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    if incidents_total <= 0:
        blockers.append("no_stale_incident_snapshots")
    if stale_candidate_incidents_total < min_incidents:
        blockers.append("insufficient_stale_candidate_incidents")
    if unique_jobs_total < min_unique_jobs:
        blockers.append("insufficient_unique_jobs")
    if parse_error_total > 0:
        blockers.append("incident_snapshot_parse_errors_present")
    if current_stale_candidates_total > 0:
        blockers.append("current_stale_candidates_still_need_manual_review")

    if incidents_total <= 0:
        recommendation = "hold_no_incidents"
        next_step = "capture real stale-running snapshots before revisiting auto-reclaim"
    elif blockers:
        recommendation = "hold_insufficient_evidence"
        next_step = "collect more clean incident examples and manually review current candidates"
    else:
        recommendation = "manual_review_ready"
        next_step = "perform human false-positive review before any auto-reclaim RFC"

    return {
        "auto_reclaim_ready": False,
        "recommendation": recommendation,
        "blockers": blockers,
        "next_step": next_step,
        "reason": (
            "Automatic reclaim remains disabled; this gate only determines whether accumulated "
            "incident evidence is ready for human review."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize stale-running incident evidence and decide whether the evidence is ready "
            "for human false-positive review. This never enables or runs auto-reclaim."
        )
    )
    parser.add_argument("--db-path", type=Path, default=None, help="Optional PAPERPIPE_DB_PATH override.")
    parser.add_argument(
        "--stale-after-seconds",
        type=_positive_int,
        default=900,
        help="Threshold used to count current stale-running candidates.",
    )
    parser.add_argument("--limit", type=_positive_int, default=500, help="Maximum incident summaries to inspect.")
    parser.add_argument(
        "--min-incidents",
        type=_non_negative_int,
        default=3,
        help="Minimum clean stale-candidate snapshots before manual review is considered ready.",
    )
    parser.add_argument(
        "--min-unique-jobs",
        type=_non_negative_int,
        default=3,
        help="Minimum unique jobs represented by clean stale-candidate snapshots.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report path.")
    args = parser.parse_args(argv)
    _set_db_path_override(args.db_path)

    import src.db_utils as db_utils
    from src.services.stale_jobs import collect_stale_jobs, collect_stale_running_incidents

    db_path = db_utils.get_db_path()
    stale_payload = collect_stale_jobs(
        db_path,
        stale_after_seconds=args.stale_after_seconds,
        limit=args.limit,
    )
    incident_payload = collect_stale_running_incidents(limit=args.limit)
    incidents: list[dict[str, Any]] = list(incident_payload.get("incidents") or [])
    clean_incidents = [incident for incident in incidents if not bool(incident.get("parse_error"))]
    stale_candidate_incidents = [
        incident for incident in clean_incidents if bool(incident.get("is_stale_candidate"))
    ]
    unique_jobs = {
        str(incident.get("job_id") or "").strip()
        for incident in stale_candidate_incidents
        if str(incident.get("job_id") or "").strip()
    }
    parse_error_total = sum(1 for incident in incidents if bool(incident.get("parse_error")))
    current_stale_candidates_total = int(stale_payload.get("stale_candidates_total") or 0)

    decision = _build_decision(
        incidents_total=int(incident_payload.get("incidents_total") or 0),
        parse_error_total=parse_error_total,
        stale_candidate_incidents_total=len(stale_candidate_incidents),
        unique_jobs_total=len(unique_jobs),
        current_stale_candidates_total=current_stale_candidates_total,
        min_incidents=int(args.min_incidents),
        min_unique_jobs=int(args.min_unique_jobs),
    )
    report = {
        "schema_version": "stale_reclaim_readiness.v1",
        "db_path": str(db_path),
        "incidents_root": incident_payload.get("incidents_root"),
        "thresholds": {
            "stale_after_seconds": int(args.stale_after_seconds),
            "min_incidents": int(args.min_incidents),
            "min_unique_jobs": int(args.min_unique_jobs),
        },
        "inputs": {
            "current_stale_candidates_total": current_stale_candidates_total,
            "incidents_total": int(incident_payload.get("incidents_total") or 0),
            "returned_incidents_total": len(incidents),
            "clean_incidents_total": len(clean_incidents),
            "parse_error_total": parse_error_total,
            "stale_candidate_incidents_total": len(stale_candidate_incidents),
            "unique_jobs_total": len(unique_jobs),
            "latest_incident_at": _latest_timestamp(incidents),
        },
        "decision": decision,
    }
    if args.output is not None:
        _write_json(args.output.expanduser().resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
