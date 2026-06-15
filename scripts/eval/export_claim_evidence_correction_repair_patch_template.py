#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.claim_evidence_corrections import (  # noqa: E402
    build_claim_evidence_correction_repair_patch_template,
    write_claim_evidence_correction_repair_patch_template,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a non-canonical patch template from a claim/evidence correction repair plan."
        )
    )
    parser.add_argument("--repair-plan", required=True, help="claim_evidence_correction_repair_plan.v1 path.")
    parser.add_argument("--out", required=True, help="Output JSON path for the patch template.")
    args = parser.parse_args()

    template = build_claim_evidence_correction_repair_patch_template(
        repair_plan_path=Path(args.repair_plan)
    )
    out = write_claim_evidence_correction_repair_patch_template(template, Path(args.out))
    print(f"[claim_evidence_correction_repair_patch_template] target_count={template.target_count}")
    print(
        "[claim_evidence_correction_repair_patch_template] "
        f"source_correction_log_path={mask_local_paths_in_text(template.source_correction_log_path)}"
    )
    print(f"[claim_evidence_correction_repair_patch_template] out={mask_local_paths_in_text(str(out))}")
    if template.warnings:
        print(
            "[claim_evidence_correction_repair_patch_template] "
            f"warnings={','.join(template.warnings)}"
        )
    return 0 if template.target_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
