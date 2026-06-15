#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_patch_template_fill_readiness_report,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether a non-canonical evidence grounding patch template has enough "
            "review context for a human fill step."
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
    parser.add_argument("--out", required=True, help="Output fill-readiness JSON path.")
    args = parser.parse_args()

    try:
        report = build_evidence_grounding_patch_template_fill_readiness_report(
            patch_template_path=Path(args.patch_template),
            out=Path(args.out),
        )
    except Exception as exc:
        print(
            f"[evidence_grounding_patch_template_fill_readiness] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(
        "[evidence_grounding_patch_template_fill_readiness] "
        f"schema={report.source_patch_template_schema_version}"
    )
    print(f"[evidence_grounding_patch_template_fill_readiness] target_count={report.target_count}")
    print(
        "[evidence_grounding_patch_template_fill_readiness] "
        f"blank_patch_field_count={report.blank_patch_field_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_readiness] "
        f"ready_for_human_fill_review={report.ready_for_human_fill_review}"
    )
    print(
        "[evidence_grounding_patch_template_fill_readiness] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    if report.warnings:
        print(
            "[evidence_grounding_patch_template_fill_readiness] "
            f"warnings={','.join(report.warnings)}"
        )
    return 0 if report.ready_for_human_fill_review else 1


if __name__ == "__main__":
    raise SystemExit(main())
