#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_patch_template_prefill_from_suggestions,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy non-canonical suggested lineage values into a patch template while "
            "leaving unresolved fields blank for human review."
        )
    )
    parser.add_argument(
        "--patch-template",
        required=True,
        help=(
            "Path to evidence_grounding_candidate_lineage_patch_template.v1 or "
            "claim_evidence_correction_repair_patch_template.v1 JSON."
        ),
    )
    parser.add_argument("--out", required=True, help="Output partial prefilled patch template JSON path.")
    args = parser.parse_args()

    try:
        template = build_evidence_grounding_patch_template_prefill_from_suggestions(
            patch_template_path=Path(args.patch_template),
            out=Path(args.out),
        )
    except Exception as exc:
        print(
            f"[evidence_grounding_patch_template_prefill] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    prefilled_field_count = 0
    remaining_blank_field_count = 0
    for record in template.records:
        for value in record.patch_fields.values():
            if str(value or "").strip():
                prefilled_field_count += 1
            else:
                remaining_blank_field_count += 1

    print(f"[evidence_grounding_patch_template_prefill] schema={template.schema_version}")
    print(f"[evidence_grounding_patch_template_prefill] target_count={template.target_count}")
    print(f"[evidence_grounding_patch_template_prefill] prefilled_field_count={prefilled_field_count}")
    print(f"[evidence_grounding_patch_template_prefill] remaining_blank_field_count={remaining_blank_field_count}")
    print(
        "[evidence_grounding_patch_template_prefill] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    if template.warnings:
        print(f"[evidence_grounding_patch_template_prefill] warnings={','.join(template.warnings)}")
    return 0 if prefilled_field_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
