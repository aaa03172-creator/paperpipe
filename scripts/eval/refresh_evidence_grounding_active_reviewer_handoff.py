#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.eval.audit_evidence_grounding_active_reviewer_briefs import (  # noqa: E402
    build_active_reviewer_brief_audit,
)
from scripts.eval.export_evidence_grounding_active_reviewer_brief import (  # noqa: E402
    derive_inputs_from_split_manifest,
    render_active_reviewer_brief,
)
from scripts.eval.export_p0_overstatement_active_reviewer_brief import (  # noqa: E402
    render_p0_active_reviewer_brief,
)
from src.schemas.evidence_grounding_benchmark import (  # noqa: E402
    EvidenceGroundingActiveReviewerHandoffRefreshReport,
)
from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_active_review_readiness_report,
    build_evidence_grounding_p0_overstatement_review_summary,
    write_evidence_grounding_p0_overstatement_review_summary,
    write_evidence_grounding_p0_overstatement_review_summary_open_issue_csv,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


def refresh_active_reviewer_handoff(
    *,
    roadmap_audit: str,
    split_manifest: str,
    structured_brief_out: str,
    p0_packet: str,
    p0_reviewed_csv: str,
    p0_open_issue_csv: str,
    p0_summary_out: str,
    p0_brief_out: str,
    brief_audit_out: str,
    active_review_readiness_out: str | None,
    generated_date: str,
    requirement_id: str,
) -> dict:
    structured_inputs = derive_inputs_from_split_manifest(
        split_manifest_path=split_manifest,
        requirement_id=requirement_id,
    )
    structured_markdown = render_active_reviewer_brief(
        audit_path=roadmap_audit,
        fill_review_status_path=structured_inputs["fill_review_status_path"],
        reviewed_csv_path=structured_inputs["reviewed_csv_path"],
        open_records_csv_path=structured_inputs["open_records_csv_path"],
        task_export_path=structured_inputs["task_export_path"],
        generated_date=generated_date,
    )
    atomic_write_text(Path(structured_brief_out).expanduser().resolve(), structured_markdown)

    p0_summary = build_evidence_grounding_p0_overstatement_review_summary(
        packet_path=Path(p0_packet),
        reviewed_csv_path=Path(p0_reviewed_csv),
    )
    write_evidence_grounding_p0_overstatement_review_summary_open_issue_csv(
        p0_summary,
        Path(p0_open_issue_csv),
    )
    write_evidence_grounding_p0_overstatement_review_summary(p0_summary, Path(p0_summary_out))

    p0_markdown = render_p0_active_reviewer_brief(
        packet_path=p0_packet,
        reviewed_csv_path=p0_reviewed_csv,
        open_issue_csv_path=p0_open_issue_csv,
        summary_out_path=p0_summary_out,
        generated_date=generated_date,
    )
    atomic_write_text(Path(p0_brief_out).expanduser().resolve(), p0_markdown)

    audit = build_active_reviewer_brief_audit(
        structured_brief=structured_brief_out,
        structured_fill_review_status=structured_inputs["fill_review_status_path"],
        structured_open_records_csv=structured_inputs["open_records_csv_path"],
        p0_brief=p0_brief_out,
        p0_open_issue_csv=p0_open_issue_csv,
    )
    atomic_write_text(Path(brief_audit_out).expanduser().resolve(), json.dumps(audit, indent=2) + "\n")

    readiness = None
    if active_review_readiness_out:
        readiness_report = build_evidence_grounding_active_review_readiness_report(
            structured_fill_review_status_path=Path(structured_inputs["fill_review_status_path"]),
            p0_summary_path=Path(p0_summary_out),
            active_brief_audit_path=Path(brief_audit_out),
            out=Path(active_review_readiness_out),
        )
        readiness = readiness_report.model_dump(mode="json")

    report = EvidenceGroundingActiveReviewerHandoffRefreshReport(
        structured_brief_path=structured_brief_out,
        structured_reviewed_csv_path=structured_inputs["reviewed_csv_path"],
        structured_fill_review_status_path=structured_inputs["fill_review_status_path"],
        structured_open_records_csv_path=structured_inputs["open_records_csv_path"],
        p0_brief_path=p0_brief_out,
        p0_reviewed_csv_path=p0_reviewed_csv,
        p0_open_issue_csv_path=p0_open_issue_csv,
        brief_audit_path=brief_audit_out,
        brief_audit_all_passed=audit["all_passed"],
        brief_audit_pass_count=audit["pass_count"],
        brief_audit_fail_count=audit["fail_count"],
        brief_audit_counts=audit.get("counts", {}),
        active_review_readiness_path=active_review_readiness_out,
        active_review_ready_for_downstream_review_steps=(
            readiness["ready_for_downstream_review_steps"] if readiness is not None else None
        ),
        active_review_readiness_blocker_count=(
            readiness["blocker_count"] if readiness is not None else None
        ),
    )
    return report.model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the current active reviewer handoff briefs and freshness audit "
            "without filling reviewer-owned values or decisions."
        )
    )
    parser.add_argument("--roadmap-audit", required=True)
    parser.add_argument("--split-manifest", required=True)
    parser.add_argument("--structured-brief-out", required=True)
    parser.add_argument("--p0-packet", required=True)
    parser.add_argument("--p0-reviewed-csv", required=True)
    parser.add_argument("--p0-open-issue-csv", required=True)
    parser.add_argument("--p0-summary-out", required=True)
    parser.add_argument("--p0-brief-out", required=True)
    parser.add_argument("--brief-audit-out", required=True)
    parser.add_argument(
        "--active-review-readiness-out",
        help="Optional combined active review readiness JSON output path.",
    )
    parser.add_argument("--out", required=True, help="Refresh summary JSON output path.")
    parser.add_argument("--generated-date", default="2026-05-31")
    parser.add_argument("--requirement-id", default="structured_correction_log")
    args = parser.parse_args()

    try:
        refresh = refresh_active_reviewer_handoff(
            roadmap_audit=args.roadmap_audit,
            split_manifest=args.split_manifest,
            structured_brief_out=args.structured_brief_out,
            p0_packet=args.p0_packet,
            p0_reviewed_csv=args.p0_reviewed_csv,
            p0_open_issue_csv=args.p0_open_issue_csv,
            p0_summary_out=args.p0_summary_out,
            p0_brief_out=args.p0_brief_out,
            brief_audit_out=args.brief_audit_out,
            active_review_readiness_out=args.active_review_readiness_out,
            generated_date=args.generated_date,
            requirement_id=args.requirement_id,
        )
        atomic_write_text(Path(args.out).expanduser().resolve(), json.dumps(refresh, indent=2) + "\n")
    except Exception as exc:
        print(
            f"[active_reviewer_handoff_refresh] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(
        "[active_reviewer_handoff_refresh] "
        f"audit_all_passed={str(refresh['brief_audit_all_passed']).lower()} "
        f"audit_fail_count={refresh['brief_audit_fail_count']} "
        f"readiness_blocker_count={refresh['active_review_readiness_blocker_count']} "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    return 0 if refresh["brief_audit_all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
