#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_patch_template_fill_task_export,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export per-field human review tasks from an evidence grounding patch-template "
            "fill-readiness report."
        )
    )
    parser.add_argument(
        "--fill-readiness",
        required=True,
        help="Path to an evidence_grounding_patch_template_fill_readiness.v1 JSON report.",
    )
    parser.add_argument("--out", required=True, help="Output fill-task export JSON path.")
    parser.add_argument("--csv-out", help="Optional reviewer-friendly CSV sidecar path.")
    parser.add_argument("--markdown-out", help="Optional reviewer-friendly Markdown packet path.")
    args = parser.parse_args()

    try:
        export = build_evidence_grounding_patch_template_fill_task_export(
            fill_readiness_path=Path(args.fill_readiness),
            out=Path(args.out),
            csv_out=Path(args.csv_out) if args.csv_out else None,
            markdown_out=Path(args.markdown_out) if args.markdown_out else None,
        )
    except Exception as exc:
        print(
            f"[evidence_grounding_patch_template_fill_task_export] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(
        "[evidence_grounding_patch_template_fill_task_export] "
        f"schema={export.source_patch_template_schema_version}"
    )
    print(f"[evidence_grounding_patch_template_fill_task_export] record_count={export.record_count}")
    print(f"[evidence_grounding_patch_template_fill_task_export] task_count={export.task_count}")
    print(
        "[evidence_grounding_patch_template_fill_task_export] "
        f"missing_suggestion_task_count={export.missing_suggestion_task_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_task_export] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    if export.task_export_csv_path:
        print(
            "[evidence_grounding_patch_template_fill_task_export] "
            f"csv={mask_local_paths_in_text(export.task_export_csv_path)}"
        )
    if export.task_export_markdown_path:
        print(
            "[evidence_grounding_patch_template_fill_task_export] "
            f"markdown={mask_local_paths_in_text(export.task_export_markdown_path)}"
        )
    if export.warnings:
        print(
            "[evidence_grounding_patch_template_fill_task_export] "
            f"warnings={','.join(export.warnings)}"
        )
    return 0 if export.task_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
