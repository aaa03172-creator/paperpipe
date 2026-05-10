#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db_utils import get_db_path
from src.services.intake_override_audit import (
    INTAKE_OVERRIDE_AUDIT_CALIBRATION_TARGET_RUNS,
    build_intake_override_audit_viewer_command,
    build_intake_override_threshold_review_viewer_command,
    build_intake_override_audit,
    default_intake_override_audits_root,
    load_audit_rows_from_db,
    load_audit_rows_from_jsonl,
    write_intake_override_audit,
)
from scripts.eval.recommend_intake_override_threshold_review import (
    run_intake_override_threshold_review,
)
from src.services.runtime_readiness import (
    LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
    LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
)


def _repo_local_viewer_hint() -> str:
    if os.name == "nt":
        return r".venv\Scripts\paperpipe.exe show-intake-override-audit <run_dir>"
    return ".venv/bin/paperpipe show-intake-override-audit <run_dir>"


def _repo_local_threshold_review_viewer_hint() -> str:
    if os.name == "nt":
        return r".venv\Scripts\paperpipe.exe show-intake-override-threshold-review <run_dir>"
    return ".venv/bin/paperpipe show-intake-override-threshold-review <run_dir>"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit persisted intake_override_log coverage and disagreement metrics.",
        epilog=(
            "Writes summary.json, details.json, and audit.md into the run directory. "
            "For a repo-local CLI view, run: "
            f"{_repo_local_viewer_hint()} "
            "If you also pass --emit-threshold-review, inspect the review artifact with: "
            f"{_repo_local_threshold_review_viewer_hint()} "
            "Threshold-review sidecars emitted here default to provenance=operator but latest_eligible=false, "
            "so they do not replace the operator-facing 'latest threshold review' unless you also pass "
            "--threshold-review-latest-eligible."
        ),
    )
    parser.add_argument("--db-path", default="", help="Optional PaperPipe runtime DB path. Defaults to current runtime DB.")
    parser.add_argument("--rows-jsonl", default="", help="Optional JSONL export of paper-like rows.")
    parser.add_argument(
        "--out-dir",
        default=str(default_intake_override_audits_root()),
        help="Directory to write audit artifacts into.",
    )
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument(
        "--emit-threshold-review",
        action="store_true",
        help="Also write a bounded threshold-review summary for the audit root after generating this audit run.",
    )
    parser.add_argument(
        "--threshold-review-provenance-kind",
        choices=("operator", "synthetic"),
        default="operator",
        help="Explicit provenance for emitted threshold review artifacts.",
    )
    parser.add_argument(
        "--threshold-review-latest-eligible",
        action="store_true",
        help="Allow the emitted threshold review artifact to participate in operator-facing latest selection.",
    )
    return parser


def run_audit(
    *,
    db_path: Path | None,
    rows_jsonl_path: Path | None,
    out_dir: Path,
    run_id: str,
) -> Path:
    if db_path is not None and rows_jsonl_path is not None:
        raise ValueError("choose either db_path or rows_jsonl_path, not both")

    if rows_jsonl_path is not None:
        rows = load_audit_rows_from_jsonl(rows_jsonl_path)
        summary, details = build_intake_override_audit(
            rows=rows,
            run_id=run_id,
            source="rows_jsonl",
            rows_jsonl_path=rows_jsonl_path,
        )
    else:
        resolved_db_path = db_path or get_db_path()
        rows = load_audit_rows_from_db(resolved_db_path)
        summary, details = build_intake_override_audit(
            rows=rows,
            run_id=run_id,
            source="runtime_db",
            db_path=resolved_db_path,
        )
    return write_intake_override_audit(summary=summary, details=details, out_dir=out_dir)


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    run_id = args.run_id.strip() or f"intake_override_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    db_path = Path(args.db_path).expanduser().resolve() if args.db_path.strip() else None
    rows_jsonl_path = Path(args.rows_jsonl).expanduser().resolve() if args.rows_jsonl.strip() else None
    out_dir = Path(args.out_dir).expanduser().resolve()
    run_root = run_audit(
        db_path=db_path,
        rows_jsonl_path=rows_jsonl_path,
        out_dir=out_dir,
        run_id=run_id,
    )
    payload = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "details_path": str(run_root / "details.json"),
        "markdown_path": str(run_root / "audit.md"),
        "viewer_command": build_intake_override_audit_viewer_command(
            run_root,
            repo_root=ROOT,
            python_executable=Path(sys.executable),
        ),
    }
    if bool(args.emit_threshold_review):
        threshold_review_run_id = f"{run_id}__threshold_review"
        threshold_review_root = run_intake_override_threshold_review(
            audit_root=out_dir,
            out_dir=ROOT / "snapshots" / "intake_override_threshold_review",
            run_id=threshold_review_run_id,
            warn_threshold=LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
            min_audited_docs=LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
            calibration_target_runs=INTAKE_OVERRIDE_AUDIT_CALIBRATION_TARGET_RUNS,
            provenance_kind=str(args.threshold_review_provenance_kind),
            latest_eligible=bool(args.threshold_review_latest_eligible),
        )
        payload.update(
            {
                "threshold_review_run_root": str(threshold_review_root),
                "threshold_review_summary_path": str(threshold_review_root / "summary.json"),
                "threshold_review_viewer_command": build_intake_override_threshold_review_viewer_command(
                    threshold_review_root,
                    repo_root=ROOT,
                    python_executable=Path(sys.executable),
                ),
            }
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
