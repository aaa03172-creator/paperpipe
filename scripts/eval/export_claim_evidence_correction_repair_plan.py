#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.claim_evidence_corrections import (  # noqa: E402
    build_claim_evidence_correction_repair_plan,
    write_claim_evidence_correction_repair_plan,
)
from src.services.runtime_paths import claim_evidence_correction_log_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a non-canonical repair plan for invalid claim/evidence correction records."
    )
    parser.add_argument(
        "--log-path",
        default="",
        help="Optional claim_evidence_corrections.jsonl path. Defaults to PaperPipe runtime storage.",
    )
    parser.add_argument("--out", required=True, help="Output repair-plan JSON path.")
    parser.add_argument("--diagnostic-limit", type=int, default=100)
    args = parser.parse_args()

    if args.diagnostic_limit < 1:
        raise SystemExit("--diagnostic-limit must be >= 1")

    log_path = Path(args.log_path).expanduser().resolve() if args.log_path else claim_evidence_correction_log_path()
    plan = build_claim_evidence_correction_repair_plan(
        log_path=log_path,
        diagnostic_limit=args.diagnostic_limit,
    )
    out = write_claim_evidence_correction_repair_plan(plan, Path(args.out))

    print(f"[claim_evidence_correction_repair_plan] source_record_count={plan.source_record_count}")
    print(f"[claim_evidence_correction_repair_plan] source_invalid_record_count={plan.source_invalid_record_count}")
    print(f"[claim_evidence_correction_repair_plan] repair_target_count={plan.repair_target_count}")
    if plan.targets:
        repair_targets = []
        missing_fields = []
        reason_codes = []
        available_context = []
        for target in plan.targets:
            parts = []
            if target.source_correction_id:
                parts.append(f"correction_id={target.source_correction_id}")
            if target.paper_id:
                parts.append(f"paper_id={target.paper_id}")
            if target.run_id:
                parts.append(f"run_id={target.run_id}")
            if target.claim_id:
                parts.append(f"claim_id={target.claim_id}")
            if parts:
                repair_targets.append(f"line_{target.line_number}:{','.join(parts)}")
            if target.missing_replay_fields:
                missing_fields.append(
                    f"line_{target.line_number}:{','.join(target.missing_replay_fields)}"
                )
            if target.reason_codes:
                reason_codes.append(f"line_{target.line_number}:{','.join(target.reason_codes)}")
            if target.available_replay_context:
                context_parts = [
                    f"{key}={value}" for key, value in target.available_replay_context.items()
                ]
                available_context.append(f"line_{target.line_number}:{','.join(context_parts)}")
        if repair_targets:
            print(
                "[claim_evidence_correction_repair_plan] repair_targets="
                f"{';'.join(repair_targets)}"
            )
        if missing_fields:
            print(
                "[claim_evidence_correction_repair_plan] missing_replay_fields="
                f"{';'.join(missing_fields)}"
            )
        if reason_codes:
            print(
                "[claim_evidence_correction_repair_plan] reason_codes="
                f"{';'.join(reason_codes)}"
            )
        if available_context:
            print(
                "[claim_evidence_correction_repair_plan] available_replay_context="
                f"{';'.join(available_context)}"
            )
    print(f"[claim_evidence_correction_repair_plan] out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
