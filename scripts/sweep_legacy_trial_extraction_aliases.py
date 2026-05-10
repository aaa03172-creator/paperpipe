#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_legacy_trial_extraction_alias.py"
MIGRATE_SCRIPT = REPO_ROOT / "scripts" / "migrate_legacy_trial_extraction_alias.py"


def _iter_targets(base_dir: Path, *, include_current_repo: bool) -> list[Path]:
    targets: list[Path] = []
    for path in sorted(base_dir.glob("paperpipe*")):
        if not path.is_dir():
            continue
        if not include_current_repo and path.resolve() == REPO_ROOT.resolve():
            continue
        targets.append(path.resolve())
    return targets


def _run_json(command: list[str]) -> tuple[int, dict]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()
    return result.returncode, payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sweep sibling `paperpipe*` roots for deprecated legacy trial_extraction config usage."
    )
    parser.add_argument(
        "--base-dir",
        default=str(REPO_ROOT.parent),
        help="Directory containing sibling paperpipe* roots. Default: parent of the current repo.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply migration to each matching root before re-auditing it.",
    )
    parser.add_argument(
        "--include-current-repo",
        action="store_true",
        help="Include the current repo in the sweep. Default excludes it.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    targets = _iter_targets(base_dir, include_current_repo=bool(args.include_current_repo))
    summary: dict[str, object] = {
        "base_dir": str(base_dir),
        "apply": bool(args.apply),
        "include_current_repo": bool(args.include_current_repo),
        "root_count": len(targets),
        "roots": [],
    }

    final_exit = 0
    for target in targets:
        root_result: dict[str, object] = {"root": str(target)}
        if args.apply:
            migrate_code, migrate_payload = _run_json(
                [sys.executable, str(MIGRATE_SCRIPT), "--root", str(target), "--apply"]
            )
            root_result["migrate_exit_code"] = migrate_code
            root_result["migrate"] = migrate_payload
            if migrate_code not in {0, 2}:
                final_exit = max(final_exit, 1)
        audit_code, audit_payload = _run_json([sys.executable, str(CHECK_SCRIPT), "--root", str(target)])
        root_result["audit_exit_code"] = audit_code
        root_result["audit"] = audit_payload
        if audit_code != 0:
            final_exit = max(final_exit, 2)
        roots = summary["roots"]
        assert isinstance(roots, list)
        roots.append(root_result)

    print(json.dumps(summary, indent=2))
    return final_exit


if __name__ == "__main__":
    raise SystemExit(main())
