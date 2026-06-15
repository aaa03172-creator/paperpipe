#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_patch_template_from_fill_task_reviews,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply reviewer-filled evidence grounding fill-task CSV values to a non-canonical "
            "patch template."
        )
    )
    parser.add_argument(
        "--task-export",
        required=True,
        help="Path to an evidence_grounding_patch_template_fill_task_export.v1 JSON artifact.",
    )
    parser.add_argument(
        "--reviewed-csv",
        required=True,
        help="Reviewer-filled CSV sidecar with reviewer_value and reviewer_evidence columns.",
    )
    parser.add_argument(
        "--patch-template",
        help="Optional source patch template override. Defaults to the path recorded in --task-export.",
    )
    parser.add_argument("--out", required=True, help="Output patched template JSON path.")
    parser.add_argument(
        "--allow-missing-review-evidence",
        action="store_true",
        help="Allow reviewer_value cells without reviewer_evidence. Default requires evidence.",
    )
    parser.add_argument(
        "--use-reviewer-evidence-hints",
        action="store_true",
        help=(
            "When reviewer_evidence is blank, treat reviewer_evidence_hint as evidence. "
            "Default requires the reviewer_evidence column itself."
        ),
    )
    args = parser.parse_args()

    try:
        template = build_evidence_grounding_patch_template_from_fill_task_reviews(
            task_export_path=Path(args.task_export),
            reviewed_csv_path=Path(args.reviewed_csv),
            patch_template_path=Path(args.patch_template) if args.patch_template else None,
            out=Path(args.out),
            require_review_evidence=not args.allow_missing_review_evidence,
            use_review_evidence_hints=args.use_reviewer_evidence_hints,
        )
    except Exception as exc:
        print(
            f"[evidence_grounding_patch_template_fill_task_reviews] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    filled_field_count = 0
    remaining_blank_field_count = 0
    for record in template.records:
        for value in record.patch_fields.values():
            if str(value or "").strip():
                filled_field_count += 1
            else:
                remaining_blank_field_count += 1

    print(f"[evidence_grounding_patch_template_fill_task_reviews] schema={template.schema_version}")
    print(f"[evidence_grounding_patch_template_fill_task_reviews] target_count={template.target_count}")
    print(f"[evidence_grounding_patch_template_fill_task_reviews] filled_field_count={filled_field_count}")
    print(
        "[evidence_grounding_patch_template_fill_task_reviews] "
        f"remaining_blank_field_count={remaining_blank_field_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_task_reviews] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    if template.warnings:
        print(
            "[evidence_grounding_patch_template_fill_task_reviews] "
            f"warnings={','.join(template.warnings)}"
        )
    return 0 if remaining_blank_field_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
