#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (  # noqa: E402
    build_evidence_grounding_patch_template_fill_review_status_report,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


def _format_count_map(counts: dict[str, int]) -> str:
    return ",".join(f"{key}:{counts[key]}" for key in sorted(counts)) or "-"


def _format_string_list_map(values: dict[str, list[str]]) -> str:
    return ",".join(
        f"{key}:{'|'.join(values[key])}" for key in sorted(values) if values[key]
    ) or "-"


def _fallback_review_row(*, fieldnames: list[str], item) -> dict[str, str]:
    row = {field: "" for field in fieldnames}
    available_context_values = _format_context_values(item.available_context_values)
    row_updates = {
        "task_id": item.task_id,
        "record_ref": item.record_ref,
        "field_name": item.field_name,
        "suggested_value": item.suggested_value or "",
        "available_context_keys": ",".join(item.available_context_keys),
        "available_context_values": available_context_values,
        "filled_patch_fields": ",".join(item.filled_patch_fields),
        "reviewer_value_hint": item.suggested_value or "",
        "reviewer_evidence_hint": available_context_values,
    }
    for key, value in row_updates.items():
        if key in row:
            row[key] = value
    return row


def _fill_blank_review_support_columns(row: dict[str, str], item) -> dict[str, str]:
    if not str(row.get("suggested_value") or "").strip():
        row["suggested_value"] = item.suggested_value or ""
    if not str(row.get("available_context_keys") or "").strip():
        row["available_context_keys"] = ";".join(item.available_context_keys)
    if not str(row.get("available_context_values") or "").strip():
        row["available_context_values"] = _format_context_values(item.available_context_values)
    if not str(row.get("filled_patch_fields") or "").strip():
        row["filled_patch_fields"] = ";".join(item.filled_patch_fields)
    if not str(row.get("reviewer_value_hint") or "").strip():
        row["reviewer_value_hint"] = item.suggested_value or ""
    if not str(row.get("reviewer_evidence_hint") or "").strip():
        row["reviewer_evidence_hint"] = _format_context_values(item.available_context_values)
    return row


def _write_annotated_review_csv(
    *,
    reviewed_csv_path: Path,
    out: Path,
    report,
    open_only: bool = False,
) -> None:
    item_by_task_id = {item.task_id: item for item in report.items}
    with reviewed_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        original_fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not original_fieldnames:
        original_fieldnames = [
            "task_id",
            "record_ref",
            "field_name",
            "reviewer_value",
            "reviewer_evidence_hint",
            "reviewer_evidence",
        ]
    annotation_fieldnames = [
        "reviewer_value_hint",
        "reviewer_evidence_hint",
        "review_status",
        "review_findings",
        "has_reviewer_value",
        "has_reviewer_evidence",
    ]
    fieldnames = original_fieldnames + [
        field for field in annotation_fieldnames if field not in original_fieldnames
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    written_task_ids: set[str] = set()
    for row in rows:
        item = item_by_task_id.get(str(row.get("task_id") or "").strip())
        if open_only and item is not None and item.status != "fail":
            continue
        annotated = dict(row)
        if item is not None:
            written_task_ids.add(item.task_id)
            annotated = _fill_blank_review_support_columns(annotated, item)
            annotated.update(
                {
                    "review_status": item.status,
                    "review_findings": ";".join(item.findings),
                    "has_reviewer_value": str(item.has_reviewer_value).lower(),
                    "has_reviewer_evidence": str(item.has_reviewer_evidence).lower(),
                }
            )
        writer.writerow(annotated)
    for item in report.items:
        if item.task_id in written_task_ids:
            continue
        if open_only and item.status != "fail":
            continue
        annotated = _fallback_review_row(fieldnames=fieldnames, item=item)
        annotated.update(
            {
                "review_status": item.status,
                "review_findings": ";".join(item.findings),
                "has_reviewer_value": str(item.has_reviewer_value).lower(),
                "has_reviewer_evidence": str(item.has_reviewer_evidence).lower(),
            }
        )
        writer.writerow(annotated)
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(out, output.getvalue())


def _format_context_values(values: dict[str, str]) -> str:
    return ";".join(f"{key}={value}" for key, value in sorted(values.items()))


def _write_open_record_review_csv(*, out: Path, report) -> None:
    fieldnames = [
        "record_ref",
        "open_field_names",
        "open_task_ids",
        "suggested_values",
        "available_context_keys",
        "available_context_values",
        "reviewer_evidence_hint",
        "filled_patch_fields",
        "review_findings",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record_ref in report.open_record_refs:
        items = [
            item
            for item in report.items
            if item.record_ref == record_ref and item.status == "fail"
        ]
        suggested_values = {
            item.field_name: item.suggested_value
            for item in items
            if item.suggested_value
        }
        available_context_values: dict[str, str] = {}
        available_context_keys: set[str] = set()
        filled_patch_fields: set[str] = set()
        review_findings: set[str] = set()
        for item in items:
            available_context_values.update(item.available_context_values)
            available_context_keys.update(item.available_context_keys)
            filled_patch_fields.update(item.filled_patch_fields)
            review_findings.update(item.findings)
        writer.writerow(
            {
                "record_ref": record_ref,
                "open_field_names": ";".join(
                    report.open_field_names_by_record_ref.get(record_ref, [])
                ),
                "open_task_ids": ";".join(
                    report.open_task_ids_by_record_ref.get(record_ref, [])
                ),
                "suggested_values": _format_context_values(suggested_values),
                "available_context_keys": ";".join(sorted(available_context_keys)),
                "available_context_values": _format_context_values(available_context_values),
                "reviewer_evidence_hint": _format_context_values(available_context_values),
                "filled_patch_fields": ";".join(sorted(filled_patch_fields)),
                "review_findings": ";".join(sorted(review_findings)),
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(out, output.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit reviewer-filled evidence grounding fill-task CSV completeness before apply."
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
    parser.add_argument("--out", required=True, help="Output fill-review status JSON path.")
    parser.add_argument(
        "--annotated-csv-out",
        help="Optional CSV copy with review_status/review_findings columns appended.",
    )
    parser.add_argument(
        "--open-csv-out",
        help="Optional CSV copy containing only rows that still fail review-status checks.",
    )
    parser.add_argument(
        "--open-record-csv-out",
        help="Optional CSV grouped by record_ref for records with open review tasks.",
    )
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
        annotated_csv_out = (
            Path(args.annotated_csv_out).expanduser().resolve()
            if args.annotated_csv_out
            else None
        )
        open_csv_out = (
            Path(args.open_csv_out).expanduser().resolve()
            if args.open_csv_out
            else None
        )
        open_record_csv_out = (
            Path(args.open_record_csv_out).expanduser().resolve()
            if args.open_record_csv_out
            else None
        )
        report = build_evidence_grounding_patch_template_fill_review_status_report(
            task_export_path=Path(args.task_export),
            reviewed_csv_path=Path(args.reviewed_csv),
            annotated_csv_path=annotated_csv_out,
            open_csv_path=open_csv_out,
            open_record_csv_path=open_record_csv_out,
            require_review_evidence=not args.allow_missing_review_evidence,
            use_review_evidence_hints=args.use_reviewer_evidence_hints,
        )
        if annotated_csv_out is not None:
            _write_annotated_review_csv(
                reviewed_csv_path=Path(args.reviewed_csv).expanduser().resolve(),
                out=annotated_csv_out,
                report=report,
            )
        if open_csv_out is not None:
            _write_annotated_review_csv(
                reviewed_csv_path=Path(args.reviewed_csv).expanduser().resolve(),
                out=open_csv_out,
                report=report,
                open_only=True,
            )
        if open_record_csv_out is not None:
            _write_open_record_review_csv(
                out=open_record_csv_out,
                report=report,
            )
        atomic_write_text(
            Path(args.out).expanduser().resolve(),
            report.model_dump_json(indent=2),
        )
    except Exception as exc:
        print(
            f"[evidence_grounding_patch_template_fill_review_status] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(f"[evidence_grounding_patch_template_fill_review_status] task_count={report.task_count}")
    print(f"[evidence_grounding_patch_template_fill_review_status] pass_count={report.pass_count}")
    print(f"[evidence_grounding_patch_template_fill_review_status] fail_count={report.fail_count}")
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"open_csv_row_count={report.open_csv_row_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"reviewed_value_count={report.reviewed_value_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"missing_value_count={report.missing_value_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"missing_evidence_count={report.missing_evidence_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"missing_value_count_by_field={_format_count_map(report.missing_value_count_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"missing_evidence_count_by_field={_format_count_map(report.missing_evidence_count_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"suggested_value_count_by_field={_format_count_map(report.suggested_value_count_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"missing_suggestion_count_by_field={_format_count_map(report.missing_suggestion_count_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        "missing_suggestion_task_ids_by_field="
        f"{_format_string_list_map(report.missing_suggestion_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"available_context_count_by_field={_format_count_map(report.available_context_count_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"available_context_keys_by_field={_format_string_list_map(report.available_context_keys_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"available_context_values_by_field={_format_string_list_map(report.available_context_values_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"missing_context_count_by_field={_format_count_map(report.missing_context_count_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"missing_context_task_ids_by_field={_format_string_list_map(report.missing_context_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"fail_count_by_field={_format_count_map(report.fail_count_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"open_record_count={report.open_record_count}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"open_record_refs={','.join(report.open_record_refs) or '-'}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"open_field_names_by_record_ref={_format_string_list_map(report.open_field_names_by_record_ref)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"open_task_ids={','.join(report.open_task_ids) or '-'}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"open_task_ids_by_field={_format_string_list_map(report.open_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"open_task_ids_by_record_ref={_format_string_list_map(report.open_task_ids_by_record_ref)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        "open_record_filled_patch_field_counts_by_field="
        f"{_format_count_map(report.open_record_filled_patch_field_counts_by_field)}"
    )
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        "open_record_filled_patch_fields_by_record_ref="
        f"{_format_string_list_map(report.open_record_filled_patch_fields_by_record_ref)}"
    )
    print(f"[evidence_grounding_patch_template_fill_review_status] ready_for_apply={report.ready_for_apply}")
    print(
        "[evidence_grounding_patch_template_fill_review_status] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    if report.warnings:
        print(
            "[evidence_grounding_patch_template_fill_review_status] "
            f"warnings={','.join(report.warnings)}"
        )
    if annotated_csv_out is not None:
        print(
            "[evidence_grounding_patch_template_fill_review_status] "
            f"annotated_csv={mask_local_paths_in_text(str(annotated_csv_out))}"
        )
    if open_csv_out is not None:
        print(
            "[evidence_grounding_patch_template_fill_review_status] "
            f"open_csv={mask_local_paths_in_text(str(open_csv_out))}"
        )
    if open_record_csv_out is not None:
        print(
            "[evidence_grounding_patch_template_fill_review_status] "
            f"open_record_csv={mask_local_paths_in_text(str(open_record_csv_out))}"
        )
    return 0 if report.ready_for_apply else 1


if __name__ == "__main__":
    raise SystemExit(main())
