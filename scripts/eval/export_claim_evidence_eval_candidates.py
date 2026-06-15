#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.claim_evidence_correction import ClaimEvidenceCorrectionFeedbackExportStatus
from src.services.claim_evidence_corrections import (
    build_claim_evidence_eval_candidate_export,
    claim_evidence_eval_candidate_export_replayability_findings,
    load_claim_evidence_corrections_with_diagnostics,
    write_claim_evidence_eval_candidate_export,
)
from src.services.runtime_paths import claim_evidence_correction_log_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export accepted claim/evidence corrections as non-canonical eval candidates."
    )
    parser.add_argument(
        "--log-path",
        default="",
        help="Optional claim_evidence_corrections.jsonl path. Defaults to PaperPipe runtime storage.",
    )
    parser.add_argument("--out", required=True, help="Output JSON or JSONL path.")
    parser.add_argument("--jsonl", action="store_true", help="Write one candidate per JSONL line instead of an export JSON.")
    parser.add_argument("--paper-id", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--claim-id", default=None)
    parser.add_argument("--reason-code", default=None)
    parser.add_argument(
        "--require-replayable",
        action="store_true",
        help="Exit nonzero when the export cannot satisfy roadmap correction-evidence replayability.",
    )
    parser.add_argument(
        "--feedback-export-status",
        choices=["not_applicable", "pending", "linked"],
        default=None,
    )
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    log_path = Path(args.log_path).expanduser().resolve() if args.log_path else claim_evidence_correction_log_path()
    (
        corrections,
        source_record_count,
        source_invalid_record_count,
        source_invalid_record_diagnostics,
    ) = load_claim_evidence_corrections_with_diagnostics(log_path=log_path)
    feedback_export_status: ClaimEvidenceCorrectionFeedbackExportStatus | None = args.feedback_export_status
    export = build_claim_evidence_eval_candidate_export(
        corrections,
        paper_id=args.paper_id,
        run_id=args.run_id,
        claim_id=args.claim_id,
        reason_code=args.reason_code,
        feedback_export_status=feedback_export_status,
        limit=args.limit,
        source_correction_log_path=str(log_path),
        source_record_count=source_record_count,
        source_invalid_record_count=source_invalid_record_count,
        source_invalid_record_diagnostics=source_invalid_record_diagnostics,
    )
    out = write_claim_evidence_eval_candidate_export(
        export,
        Path(args.out).expanduser().resolve(),
        jsonl=args.jsonl,
    )

    print(f"[claim_evidence_eval_candidates] candidate_count={export.candidate_count}")
    if export.source_correction_log_path:
        print(f"[claim_evidence_eval_candidates] source_correction_log_path={export.source_correction_log_path}")
    print(f"[claim_evidence_eval_candidates] source_record_count={export.source_record_count}")
    print(f"[claim_evidence_eval_candidates] source_invalid_record_count={export.source_invalid_record_count}")
    print(f"[claim_evidence_eval_candidates] skipped_not_accepted_count={export.skipped_not_accepted_count}")
    print(f"[claim_evidence_eval_candidates] skipped_filter_count={export.skipped_filter_count}")
    print(f"[claim_evidence_eval_candidates] skipped_limit_count={export.skipped_limit_count}")
    if export.source_invalid_record_diagnostics:
        diagnostic_lines = ",".join(str(item.line_number) for item in export.source_invalid_record_diagnostics)
        print(f"[claim_evidence_eval_candidates] source_invalid_record_lines={diagnostic_lines}")
        missing_replay_fields = [
            f"{line_key}:{','.join(fields)}"
            for line_key, fields in export.source_invalid_record_missing_replay_fields_by_line.items()
            if fields
        ]
        if missing_replay_fields:
            print(
                "[claim_evidence_eval_candidates] source_invalid_record_missing_replay_fields="
                f"{';'.join(missing_replay_fields)}"
            )
        repair_targets = []
        for line_key, target in export.source_invalid_record_repair_targets_by_line.items():
            parts = [
                f"{key.removeprefix('source_')}={target[key]}"
                for key in ("source_correction_id", "paper_id", "run_id", "claim_id")
                if target.get(key)
            ]
            if parts:
                repair_targets.append(f"{line_key}:{','.join(parts)}")
        if repair_targets:
            print(
                "[claim_evidence_eval_candidates] source_invalid_record_repair_targets="
                f"{';'.join(repair_targets)}"
            )
    replayability_findings = claim_evidence_eval_candidate_export_replayability_findings(export)
    if args.require_replayable:
        if replayability_findings:
            print("[claim_evidence_eval_candidates] replayable_evidence=false")
            print(f"[claim_evidence_eval_candidates] blocking_findings={','.join(replayability_findings)}")
        else:
            print("[claim_evidence_eval_candidates] replayable_evidence=true")
    print(f"[claim_evidence_eval_candidates] out={out}")
    return 1 if args.require_replayable and replayability_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
