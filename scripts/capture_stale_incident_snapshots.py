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


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def _set_db_path_override(db_path: Path | None) -> None:
    if db_path is None:
        return
    os.environ["PAPERPIPE_DB_PATH"] = str(db_path.expanduser().resolve())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture bounded local support artifacts for currently stale-running jobs. "
            "This does not reclaim, requeue, or mutate canonical job status."
        )
    )
    parser.add_argument("--db-path", type=Path, default=None, help="Optional PAPERPIPE_DB_PATH override.")
    parser.add_argument(
        "--stale-after-seconds",
        type=_positive_int,
        default=900,
        help="Minimum heartbeat/started age required before a running job is captured.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=50,
        help="Maximum stale candidates to capture and maximum incident summaries to return.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List stale candidates without writing incident snapshots or job events.",
    )
    args = parser.parse_args(argv)
    _set_db_path_override(args.db_path)

    import src.db_utils as db_utils
    from src.services.stale_jobs import (
        capture_stale_running_incident_snapshot,
        collect_stale_jobs,
        collect_stale_running_incidents,
    )

    db_path = db_utils.get_db_path()
    stale_payload = collect_stale_jobs(
        db_path,
        stale_after_seconds=args.stale_after_seconds,
        limit=args.limit,
    )
    candidates: list[dict[str, Any]] = list(stale_payload.get("stale_jobs") or [])
    captured: list[dict[str, Any]] = []
    if not args.dry_run:
        for candidate in candidates:
            job_id = str(candidate.get("job_id") or "").strip()
            if not job_id:
                continue
            captured.append(
                capture_stale_running_incident_snapshot(
                    db_path,
                    job_id=job_id,
                    stale_after_seconds=args.stale_after_seconds,
                )
            )

    incidents_payload = collect_stale_running_incidents(limit=args.limit)
    result = {
        "db_path": str(db_path),
        "dry_run": bool(args.dry_run),
        "stale_after_seconds": int(args.stale_after_seconds),
        "stale_candidates_total": int(stale_payload.get("stale_candidates_total") or 0),
        "captured_total": len([item for item in captured if item.get("outcome") == "captured"]),
        "captured": captured,
        "incidents_total": int(incidents_payload.get("incidents_total") or 0),
        "returned_incidents": incidents_payload.get("incidents") or [],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
