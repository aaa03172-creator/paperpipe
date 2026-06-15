#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_active_review_readiness_report,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


def build_active_review_readiness_report(
    *,
    structured_fill_review_status_path: str,
    p0_summary_path: str,
    active_brief_audit_path: str | None = None,
) -> dict:
    return build_evidence_grounding_active_review_readiness_report(
        structured_fill_review_status_path=Path(structured_fill_review_status_path),
        p0_summary_path=Path(p0_summary_path),
        active_brief_audit_path=Path(active_brief_audit_path) if active_brief_audit_path else None,
    ).model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Combine active structured-correction and P0 review readiness into one non-canonical "
            "review-gate report without filling reviewer-owned values or decisions."
        )
    )
    parser.add_argument("--structured-fill-review-status", required=True)
    parser.add_argument("--p0-summary", required=True)
    parser.add_argument("--active-brief-audit")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        report = build_active_review_readiness_report(
            structured_fill_review_status_path=args.structured_fill_review_status,
            p0_summary_path=args.p0_summary,
            active_brief_audit_path=args.active_brief_audit,
        )
        atomic_write_text(Path(args.out).expanduser().resolve(), json.dumps(report, indent=2) + "\n")
    except Exception as exc:
        print(
            f"[active_review_readiness] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    reviewer_verification_command_hints_by_work_item_id = {
        str(item["item_id"]): mask_local_paths_in_text(str(item["verification_command_hint"]))
        for item in report.get("reviewer_work_items", [])
        if item.get("verification_command_hint")
    }
    print(
        "[active_review_readiness] "
        f"ready_for_downstream_review_steps={str(report['ready_for_downstream_review_steps']).lower()} "
        f"blocker_count={report['blocker_count']} "
        "structured_reviewed_csv="
        f"{mask_local_paths_in_text(str(report['structured_correction'].get('reviewed_csv_path') or '-'))} "
        "structured_open_csv="
        f"{mask_local_paths_in_text(str(report['structured_correction'].get('open_csv_path') or '-'))} "
        "p0_reviewed_csv="
        f"{mask_local_paths_in_text(str(report['p0_overstatement'].get('source_reviewed_csv_path') or '-'))} "
        "p0_open_issue_csv="
        f"{mask_local_paths_in_text(str(report['p0_overstatement'].get('open_issue_csv_path') or '-'))} "
        f"structured_open_review_cell_count={report.get('structured_open_review_cell_count')} "
        f"p0_open_decision_count={report.get('p0_open_decision_count')} "
        f"p0_open_paper_count={report.get('p0_open_paper_count')} "
        f"structured_expected_paper_reading={report.get('structured_expected_paper_reading')} "
        f"p0_expected_paper_reading={report.get('p0_expected_paper_reading')} "
        f"reviewer_work_item_count={report.get('reviewer_work_item_count')} "
        "reviewer_open_item_counts_by_expected_paper_reading="
        f"{report.get('reviewer_open_item_counts_by_expected_paper_reading') or {}} "
        "reviewer_open_paper_counts_by_expected_paper_reading="
        f"{report.get('reviewer_open_paper_counts_by_expected_paper_reading') or {}} "
        "reviewer_verification_command_hints_by_work_item_id="
        f"{reviewer_verification_command_hints_by_work_item_id} "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    return 0 if report["ready_for_downstream_review_steps"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
