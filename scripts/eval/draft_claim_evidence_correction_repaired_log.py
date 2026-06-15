#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.claim_evidence_corrections import (  # noqa: E402
    build_claim_evidence_correction_repaired_log_draft,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a filled claim/evidence correction repair patch template and write a "
            "non-canonical repaired correction JSONL draft."
        )
    )
    parser.add_argument("--patch-template", required=True)
    parser.add_argument("--out-log", required=True, help="Output JSONL path for repaired correction records.")
    parser.add_argument("--summary-out", help="Optional output path for the repaired-log draft summary JSON.")
    args = parser.parse_args()

    try:
        draft = build_claim_evidence_correction_repaired_log_draft(
            patch_template_path=Path(args.patch_template),
            out_log_path=Path(args.out_log),
            summary_out=Path(args.summary_out) if args.summary_out else None,
        )
    except Exception as exc:
        print(
            f"[claim_evidence_correction_repaired_log_draft] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1
    print(f"[claim_evidence_correction_repaired_log_draft] record_count={draft.record_count}")
    print(f"[claim_evidence_correction_repaired_log_draft] repaired_record_count={draft.repaired_record_count}")
    print(
        "[claim_evidence_correction_repaired_log_draft] "
        f"repaired_log_path={mask_local_paths_in_text(draft.repaired_log_path or '-')}"
    )
    if args.summary_out:
        print(
            "[claim_evidence_correction_repaired_log_draft] "
            f"summary_out={mask_local_paths_in_text(str(Path(args.summary_out).expanduser().resolve()))}"
        )
    if draft.warnings:
        print(f"[claim_evidence_correction_repaired_log_draft] warnings={','.join(draft.warnings)}")
    return 0 if draft.record_count == draft.repaired_record_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
