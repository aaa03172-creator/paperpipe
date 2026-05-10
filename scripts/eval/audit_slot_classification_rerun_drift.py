#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.slot_classification_rerun_drift import (
    build_slot_classification_rerun_drift,
    load_slot_classification_audit_run,
    write_slot_classification_rerun_drift,
)


def run_audit(
    *,
    prior_run_path: Path,
    new_run_path: Path,
    out_dir: Path,
    run_id: str,
) -> Path:
    prior_summary_path, prior_details_path, prior_summary, prior_details = load_slot_classification_audit_run(prior_run_path)
    new_summary_path, new_details_path, new_summary, new_details = load_slot_classification_audit_run(new_run_path)
    summary, details = build_slot_classification_rerun_drift(
        prior_summary=prior_summary,
        prior_summary_path=prior_summary_path,
        prior_details=prior_details,
        prior_details_path=prior_details_path,
        new_summary=new_summary,
        new_summary_path=new_summary_path,
        new_details=new_details,
        new_details_path=new_details_path,
        run_id=run_id,
    )
    return write_slot_classification_rerun_drift(summary=summary, details=details, out_dir=out_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit rerun drift between two slot-classification audit runs over the same benchmark surface."
    )
    parser.add_argument("--prior-run", required=True, help="Prior audit run directory or summary.json path.")
    parser.add_argument("--new-run", required=True, help="New audit run directory or summary.json path.")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "slot_classification_rerun_drift"),
        help="Output directory for rerun-drift artifacts.",
    )
    parser.add_argument("--run-id", required=True, help="Rerun-drift run identifier.")
    args = parser.parse_args()

    run_root = run_audit(
        prior_run_path=Path(args.prior_run).expanduser(),
        new_run_path=Path(args.new_run).expanduser(),
        out_dir=Path(args.out_dir).expanduser(),
        run_id=args.run_id,
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "details_path": str(run_root / "details.json"),
        "markdown_path": str(run_root / "audit.md"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
