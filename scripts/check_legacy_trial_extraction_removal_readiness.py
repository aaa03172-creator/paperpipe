#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_legacy_trial_extraction_alias.py"
SWEEP_SCRIPT = REPO_ROOT / "scripts" / "sweep_legacy_trial_extraction_aliases.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.legacy_trial_extraction_constants import LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE


def _run_json(command: list[str]) -> tuple[int, dict]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        payload = {"stdout_parse_error": str(exc), "raw_stdout": result.stdout}
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()
    return result.returncode, payload


def _today_iso(override: str | None) -> str:
    if override:
        return date.fromisoformat(override).isoformat()
    return date.today().isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether active surfaces are clean enough to remove the legacy trial_extraction alias."
    )
    parser.add_argument(
        "--current-root",
        default=str(REPO_ROOT),
        help="Root directory of the current repo to audit. Default: this repo.",
    )
    parser.add_argument(
        "--base-dir",
        default=str(REPO_ROOT.parent),
        help="Directory containing sibling paperpipe* roots. Default: parent of the current repo.",
    )
    parser.add_argument(
        "--today",
        help="Override today's date in YYYY-MM-DD format for deterministic checks.",
    )
    args = parser.parse_args()

    current_root = Path(args.current_root).expanduser().resolve()
    base_dir = Path(args.base_dir).expanduser().resolve()
    today_iso = _today_iso(args.today)
    removal_window_open = today_iso >= LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE

    current_code, current_payload = _run_json(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(current_root)]
    )
    generated_code, generated_payload = _run_json(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(current_root), "--include-generated"]
    )
    sibling_code, sibling_payload = _run_json(
        [sys.executable, str(SWEEP_SCRIPT), "--base-dir", str(base_dir)]
    )

    sibling_blocker_roots: list[str] = []
    sibling_roots = sibling_payload.get("roots")
    if isinstance(sibling_roots, list):
        for item in sibling_roots:
            if not isinstance(item, dict):
                continue
            audit = item.get("audit")
            if not isinstance(audit, dict):
                continue
            if int(audit.get("offender_count") or 0) > 0:
                sibling_blocker_roots.append(str(item.get("root") or ""))

    active_surface_ready = (
        current_code == 0
        and generated_code == 0
        and sibling_code == 0
        and int(current_payload.get("offender_count") or 0) == 0
        and int(generated_payload.get("offender_count") or 0) == 0
        and not sibling_blocker_roots
    )

    summary = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "today": today_iso,
        "removal_date": LEGACY_TRIAL_EXTRACTION_ALIAS_REMOVAL_DATE,
        "removal_window_open": removal_window_open,
        "active_surface_ready": active_surface_ready,
        "ready_to_remove_alias_now": active_surface_ready and removal_window_open,
        "current_root": str(current_root),
        "base_dir": str(base_dir),
        "current_repo": {
            "exit_code": current_code,
            **current_payload,
        },
        "current_repo_include_generated": {
            "exit_code": generated_code,
            **generated_payload,
        },
        "sibling_sweep": {
            "exit_code": sibling_code,
            **sibling_payload,
        },
        "sibling_blocker_roots": sibling_blocker_roots,
    }
    print(json.dumps(summary, indent=2))
    return 0 if active_surface_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
