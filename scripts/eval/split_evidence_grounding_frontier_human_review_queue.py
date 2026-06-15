#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.evidence_grounding_benchmark import (  # noqa: E402
    EvidenceGroundingFrontierHumanReviewQueueSplitReport,
    EvidenceGroundingFrontierHumanReviewQueueSplitSource,
)
from src.services.path_masking import mask_local_paths_in_text  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


QUEUE_SOURCE_COLUMNS = {
    "requirement_id",
    "source_open_csv_path",
    "source_open_csv_row_number",
    "source_open_csv_missing",
}
REVIEW_COLUMNS_TO_MERGE = (
    "reviewer_value",
    "reviewer_evidence",
    "reviewer_notes",
)
REVIEW_CONTEXT_COLUMNS_TO_REFRESH = (
    "suggested_value",
    "available_context_keys",
    "available_context_values",
    "filled_patch_fields",
    "review_required",
    "reviewer_value_hint",
    "reviewer_evidence_hint",
)
ANNOTATION_COLUMNS = (
    "review_status",
    "review_findings",
    "has_reviewer_value",
    "has_reviewer_evidence",
)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [{str(key): str(value or "") for key, value in row.items()} for row in reader]
    if not fieldnames:
        raise ValueError(f"csv_missing_header: {path}")
    return fieldnames, rows


def _render_csv(fieldnames: list[str], rows: list[dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def _safe_output_name(source_path: Path, used_names: set[str]) -> str:
    stem = source_path.stem
    if stem.endswith(".reviewed.open"):
        stem = stem[: -len(".reviewed.open")]
    stem = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in stem)
    name = f"{stem or 'reviewed_source'}.reviewed.csv"
    if name not in used_names:
        used_names.add(name)
        return name
    suffix = 2
    while True:
        candidate = f"{stem or 'reviewed_source'}.{suffix}.reviewed.csv"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        suffix += 1


def _single_non_empty_value(rows: list[dict[str, str]], key: str) -> str | None:
    values = {
        str(row.get(key) or "").strip()
        for row in rows
        if str(row.get(key) or "").strip()
    }
    if len(values) == 1:
        return next(iter(values))
    return None


def _review_status_related_output_path(status_path: Path, suffix: str) -> Path:
    status_name = status_path.name
    marker = ".fill_review_status.json"
    if status_name.endswith(marker):
        return status_path.with_name(f"{status_name[: -len(marker)]}{suffix}")
    return status_path.with_suffix(suffix)


def _fill_review_audit_command_hint(
    *,
    task_export_path: str | None,
    reviewed_csv_path: Path,
    fill_review_status_path: str | None = None,
) -> str:
    task_export = task_export_path or "<source_task_export.json>"
    status_path = Path(fill_review_status_path) if fill_review_status_path else reviewed_csv_path.with_suffix(".fill_review_status.json")
    annotated_csv_path = _review_status_related_output_path(status_path, ".annotated.csv")
    open_csv_path = _review_status_related_output_path(status_path, ".open.csv")
    open_record_csv_path = _review_status_related_output_path(status_path, ".open_records.csv")
    return (
        ".venv/bin/python scripts/eval/audit_evidence_grounding_patch_template_fill_task_reviews.py "
        f"--task-export {task_export} "
        f"--reviewed-csv {reviewed_csv_path} "
        f"--out {status_path} "
        f"--annotated-csv-out {annotated_csv_path} "
        f"--open-csv-out {open_csv_path} "
        f"--open-record-csv-out {open_record_csv_path} "
        "--use-reviewer-evidence-hints"
    )


def _fill_task_apply_command_hint(*, task_export_path: str | None, reviewed_csv_path: Path) -> str:
    task_export = task_export_path or "<source_task_export.json>"
    return (
        ".venv/bin/python scripts/eval/apply_evidence_grounding_patch_template_fill_task_reviews.py "
        f"--task-export {task_export} "
        f"--reviewed-csv {reviewed_csv_path} "
        f"--out {reviewed_csv_path.with_suffix('.filled_patch_template.json')}"
    )


def _review_value_counts(rows: list[dict[str, str]]) -> tuple[int, int, int, int]:
    reviewed_value_count = sum(1 for row in rows if str(row.get("reviewer_value") or "").strip())
    reviewed_evidence_count = sum(1 for row in rows if _has_review_evidence(row))
    row_count = len(rows)
    return (
        reviewed_value_count,
        row_count - reviewed_value_count,
        reviewed_evidence_count,
        row_count - reviewed_evidence_count,
    )


def _has_review_evidence(row: dict[str, str]) -> bool:
    return bool(
        str(row.get("reviewer_evidence") or "").strip()
        or str(row.get("reviewer_evidence_hint") or "").strip()
    )


def _missing_review_column(row: dict[str, str], column_name: str) -> bool:
    if column_name == "reviewer_evidence":
        return not _has_review_evidence(row)
    return not str(row.get(column_name) or "").strip()


def _review_findings(row: dict[str, str]) -> list[str]:
    findings: list[str] = []
    if not str(row.get("reviewer_value") or "").strip():
        findings.append("fill_task_review_value_missing")
    if not _has_review_evidence(row):
        findings.append("fill_task_review_evidence_missing")
    return findings


def _annotate_review_row(row: dict[str, str]) -> None:
    findings = _review_findings(row)
    row["review_status"] = "pass" if not findings else "fail"
    row["review_findings"] = ";".join(findings)
    row["has_reviewer_value"] = str(
        bool(str(row.get("reviewer_value") or "").strip())
    ).lower()
    row["has_reviewer_evidence"] = str(_has_review_evidence(row)).lower()


def _fill_review_blocker_reasons(*, row_count: int, missing_value_count: int, missing_evidence_count: int) -> list[str]:
    reasons: list[str] = []
    if row_count == 0:
        reasons.append("no_review_rows")
    if missing_value_count > 0:
        reasons.append("missing_reviewer_value")
    if missing_evidence_count > 0:
        reasons.append("missing_reviewer_evidence")
    return reasons


def _missing_review_task_ids(rows: list[dict[str, str]], column_name: str) -> list[str]:
    return sorted(
        str(row.get("task_id") or "").strip()
        for row in rows
        if str(row.get("task_id") or "").strip()
        and _missing_review_column(row, column_name)
    )


def _missing_review_counts_by_field(rows: list[dict[str, str]], column_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if not _missing_review_column(row, column_name):
            continue
        field_name = str(row.get("field_name") or "").strip()
        if field_name:
            counts[field_name] = counts.get(field_name, 0) + 1
    return dict(sorted(counts.items()))


def _review_hint_count(rows: list[dict[str, str]], column_name: str) -> int:
    return sum(1 for row in rows if str(row.get(column_name) or "").strip())


def _review_hint_counts_by_field(rows: list[dict[str, str]], column_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if not str(row.get(column_name) or "").strip():
            continue
        field_name = str(row.get("field_name") or "").strip()
        if field_name:
            counts[field_name] = counts.get(field_name, 0) + 1
    return dict(sorted(counts.items()))


def _missing_value_hint_split_counts(rows: list[dict[str, str]]) -> tuple[int, int]:
    with_hint = 0
    without_hint = 0
    for row in rows:
        if str(row.get("reviewer_value") or "").strip():
            continue
        if str(row.get("reviewer_value_hint") or "").strip():
            with_hint += 1
        else:
            without_hint += 1
    return with_hint, without_hint


def _missing_value_hint_split_counts_by_field(rows: list[dict[str, str]], *, with_hint: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if str(row.get("reviewer_value") or "").strip():
            continue
        has_hint = bool(str(row.get("reviewer_value_hint") or "").strip())
        if has_hint != with_hint:
            continue
        field_name = str(row.get("field_name") or "").strip()
        if field_name:
            counts[field_name] = counts.get(field_name, 0) + 1
    return dict(sorted(counts.items()))


def _merge_count_maps(sources: list[EvidenceGroundingFrontierHumanReviewQueueSplitSource], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        for key, count in getattr(source, field_name).items():
            counts[key] = counts.get(key, 0) + count
    return dict(sorted(counts.items()))


def split_frontier_human_review_queue(
    *,
    queue_csv_path: Path,
    out_dir: Path,
) -> EvidenceGroundingFrontierHumanReviewQueueSplitReport:
    queue_csv_path = queue_csv_path.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    queue_fieldnames, queue_rows = _read_csv(queue_csv_path)
    missing_queue_columns = sorted((QUEUE_SOURCE_COLUMNS | {"task_id", "record_ref", "field_name"}) - set(queue_fieldnames))
    if missing_queue_columns:
        raise ValueError("frontier_human_review_queue_missing_columns: " + ",".join(missing_queue_columns))

    rows_by_source: dict[Path, list[dict[str, str]]] = {}
    seen_queue_refs: set[tuple[Path, str]] = set()
    for line_number, row in enumerate(queue_rows, start=2):
        source_missing = str(row.get("source_open_csv_missing") or "").strip().lower()
        if source_missing == "true":
            raise ValueError(f"frontier_human_review_queue_source_missing: line_{line_number}")
        source_path_text = str(row.get("source_open_csv_path") or "").strip()
        task_id = str(row.get("task_id") or "").strip()
        if not source_path_text:
            raise ValueError(f"frontier_human_review_queue_source_path_missing: line_{line_number}")
        if not task_id:
            raise ValueError(f"frontier_human_review_queue_task_id_missing: line_{line_number}")
        source_path = Path(source_path_text).expanduser().resolve()
        queue_ref = (source_path, task_id)
        if queue_ref in seen_queue_refs:
            raise ValueError(f"frontier_human_review_queue_duplicate_task: line_{line_number}:{task_id}")
        seen_queue_refs.add(queue_ref)
        rows_by_source.setdefault(source_path, []).append(row)

    sources: list[EvidenceGroundingFrontierHumanReviewQueueSplitSource] = []
    used_names: set[str] = set()
    for source_path, source_queue_rows in sorted(rows_by_source.items(), key=lambda item: str(item[0])):
        if not source_path.exists():
            raise ValueError(f"frontier_human_review_queue_source_not_found: {source_path}")
        source_fieldnames, source_rows = _read_csv(source_path)
        source_required = {"task_id", "record_ref", "field_name"}
        missing_source_columns = sorted(source_required - set(source_fieldnames))
        if missing_source_columns:
            raise ValueError(
                f"frontier_human_review_source_csv_missing_columns: {source_path}:"
                + ",".join(missing_source_columns)
            )
        output_fieldnames = source_fieldnames + [
            field for field in REVIEW_COLUMNS_TO_MERGE if field not in source_fieldnames
        ] + [
            field for field in ANNOTATION_COLUMNS if field not in source_fieldnames
        ]
        source_rows_by_task_id = {
            str(row.get("task_id") or "").strip(): row
            for row in source_rows
            if str(row.get("task_id") or "").strip()
        }
        updated_rows = [dict(row) for row in source_rows]
        updated_rows_by_task_id = {
            str(row.get("task_id") or "").strip(): row
            for row in updated_rows
            if str(row.get("task_id") or "").strip()
        }
        for queue_row in source_queue_rows:
            task_id = str(queue_row.get("task_id") or "").strip()
            source_row = source_rows_by_task_id.get(task_id)
            if source_row is None:
                raise ValueError(f"frontier_human_review_queue_unknown_source_task: {source_path}:{task_id}")
            for key in ("record_ref", "field_name"):
                if str(queue_row.get(key) or "").strip() != str(source_row.get(key) or "").strip():
                    raise ValueError(f"frontier_human_review_queue_source_row_mismatch: {source_path}:{task_id}")
            updated_row = updated_rows_by_task_id[task_id]
            for context_column in REVIEW_CONTEXT_COLUMNS_TO_REFRESH:
                if str(queue_row.get(context_column) or "").strip():
                    updated_row[context_column] = str(queue_row.get(context_column) or "")
            for review_column in REVIEW_COLUMNS_TO_MERGE:
                if review_column in queue_row:
                    updated_row[review_column] = str(queue_row.get(review_column) or "")
            _annotate_review_row(updated_row)
        output_path = out_dir / _safe_output_name(source_path, used_names)
        atomic_write_text(output_path, _render_csv(output_fieldnames, updated_rows))
        source_task_export_path = _single_non_empty_value(
            source_queue_rows,
            "source_task_export_path",
        )
        source_fill_review_status_path = _single_non_empty_value(
            source_queue_rows,
            "source_fill_review_status_path",
        )
        (
            reviewed_value_count,
            missing_value_count,
            reviewed_evidence_count,
            missing_evidence_count,
        ) = _review_value_counts(source_queue_rows)
        missing_value_with_hint_count, missing_value_without_hint_count = (
            _missing_value_hint_split_counts(source_queue_rows)
        )
        blocker_reasons = _fill_review_blocker_reasons(
            row_count=len(source_queue_rows),
            missing_value_count=missing_value_count,
            missing_evidence_count=missing_evidence_count,
        )
        sources.append(
            EvidenceGroundingFrontierHumanReviewQueueSplitSource(
                source_open_csv_path=str(source_path),
                reviewed_csv_path=str(output_path),
                source_fill_review_status_path=source_fill_review_status_path,
                source_task_export_path=_single_non_empty_value(
                    source_queue_rows,
                    "source_task_export_path",
                ),
                source_reviewed_csv_path=_single_non_empty_value(
                    source_queue_rows,
                    "source_reviewed_csv_path",
                ),
                fill_review_audit_command_hint=_fill_review_audit_command_hint(
                    task_export_path=source_task_export_path,
                    reviewed_csv_path=output_path,
                ),
                fill_task_apply_command_hint=_fill_task_apply_command_hint(
                    task_export_path=source_task_export_path,
                    reviewed_csv_path=output_path,
                ),
                requirement_ids=sorted(
                    {
                        str(row.get("requirement_id") or "").strip()
                        for row in source_queue_rows
                        if str(row.get("requirement_id") or "").strip()
                    }
                ),
                source_row_count=len(source_rows),
                merged_review_row_count=len(source_queue_rows),
                merged_reviewed_value_count=reviewed_value_count,
                merged_missing_value_count=missing_value_count,
                merged_reviewed_evidence_count=reviewed_evidence_count,
                merged_missing_evidence_count=missing_evidence_count,
                merged_reviewer_value_hint_count=_review_hint_count(
                    source_queue_rows,
                    "reviewer_value_hint",
                ),
                merged_reviewer_evidence_hint_count=_review_hint_count(
                    source_queue_rows,
                    "reviewer_evidence_hint",
                ),
                merged_missing_value_with_hint_count=missing_value_with_hint_count,
                merged_missing_value_without_hint_count=missing_value_without_hint_count,
                merged_missing_value_task_ids=_missing_review_task_ids(
                    source_queue_rows,
                    "reviewer_value",
                ),
                merged_missing_evidence_task_ids=_missing_review_task_ids(
                    source_queue_rows,
                    "reviewer_evidence",
                ),
                merged_missing_value_counts_by_field=_missing_review_counts_by_field(
                    source_queue_rows,
                    "reviewer_value",
                ),
                merged_missing_evidence_counts_by_field=_missing_review_counts_by_field(
                    source_queue_rows,
                    "reviewer_evidence",
                ),
                merged_reviewer_value_hint_counts_by_field=_review_hint_counts_by_field(
                    source_queue_rows,
                    "reviewer_value_hint",
                ),
                merged_reviewer_evidence_hint_counts_by_field=_review_hint_counts_by_field(
                    source_queue_rows,
                    "reviewer_evidence_hint",
                ),
                merged_missing_value_with_hint_counts_by_field=_missing_value_hint_split_counts_by_field(
                    source_queue_rows,
                    with_hint=True,
                ),
                merged_missing_value_without_hint_counts_by_field=_missing_value_hint_split_counts_by_field(
                    source_queue_rows,
                    with_hint=False,
                ),
                fill_review_blocker_reasons=blocker_reasons,
                next_action_kind=(
                    "complete_human_review"
                    if blocker_reasons
                    else "run_fill_review_audit"
                ),
                next_action_command_hint=(
                    None
                    if blocker_reasons
                    else _fill_review_audit_command_hint(
                        task_export_path=source_task_export_path,
                        reviewed_csv_path=output_path,
                    )
                ),
                ready_for_fill_review_audit=not blocker_reasons,
            )
        )
    return EvidenceGroundingFrontierHumanReviewQueueSplitReport(
        generated_at=datetime.now(timezone.utc),
        queue_csv_path=str(queue_csv_path),
        out_dir=str(out_dir),
        source_csv_count=len(sources),
        merged_review_row_count=sum(source.merged_review_row_count for source in sources),
        merged_reviewed_value_count=sum(source.merged_reviewed_value_count for source in sources),
        merged_missing_value_count=sum(source.merged_missing_value_count for source in sources),
        merged_reviewed_evidence_count=sum(source.merged_reviewed_evidence_count for source in sources),
        merged_missing_evidence_count=sum(source.merged_missing_evidence_count for source in sources),
        merged_reviewer_value_hint_count=sum(source.merged_reviewer_value_hint_count for source in sources),
        merged_reviewer_evidence_hint_count=sum(source.merged_reviewer_evidence_hint_count for source in sources),
        merged_missing_value_with_hint_count=sum(source.merged_missing_value_with_hint_count for source in sources),
        merged_missing_value_without_hint_count=sum(source.merged_missing_value_without_hint_count for source in sources),
        merged_missing_value_counts_by_field=_merge_count_maps(
            sources,
            "merged_missing_value_counts_by_field",
        ),
        merged_missing_evidence_counts_by_field=_merge_count_maps(
            sources,
            "merged_missing_evidence_counts_by_field",
        ),
        merged_reviewer_value_hint_counts_by_field=_merge_count_maps(
            sources,
            "merged_reviewer_value_hint_counts_by_field",
        ),
        merged_reviewer_evidence_hint_counts_by_field=_merge_count_maps(
            sources,
            "merged_reviewer_evidence_hint_counts_by_field",
        ),
        merged_missing_value_with_hint_counts_by_field=_merge_count_maps(
            sources,
            "merged_missing_value_with_hint_counts_by_field",
        ),
        merged_missing_value_without_hint_counts_by_field=_merge_count_maps(
            sources,
            "merged_missing_value_without_hint_counts_by_field",
        ),
        ready_source_count=sum(1 for source in sources if source.ready_for_fill_review_audit),
        blocked_source_count=sum(1 for source in sources if not source.ready_for_fill_review_audit),
        ready_reviewed_csv_paths=[
            source.reviewed_csv_path
            for source in sources
            if source.ready_for_fill_review_audit
        ],
        blocked_reviewed_csv_paths=[
            source.reviewed_csv_path
            for source in sources
            if not source.ready_for_fill_review_audit
        ],
        blocked_source_reasons_by_reviewed_csv_path={
            source.reviewed_csv_path: source.fill_review_blocker_reasons
            for source in sources
            if not source.ready_for_fill_review_audit
        },
        ready_fill_review_audit_command_hints=[
            str(source.next_action_command_hint)
            for source in sources
            if (
                source.ready_for_fill_review_audit
                and source.next_action_kind == "run_fill_review_audit"
                and source.next_action_command_hint
            )
        ],
        sources=sources,
        warnings=[] if sources else ["frontier_human_review_queue_split_no_source_rows"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Split a reviewed frontier human-review queue CSV back into per-source reviewed CSV "
            "copies for the fill-task apply/audit CLIs."
        )
    )
    parser.add_argument(
        "--queue-csv",
        required=True,
        help="Reviewed CSV created from --frontier-human-review-queue-csv-out.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory where per-source reviewed CSV copies will be written.",
    )
    parser.add_argument(
        "--manifest-out",
        help="Optional evidence_grounding_frontier_human_review_queue_split.v1 JSON report path.",
    )
    args = parser.parse_args()

    try:
        report = split_frontier_human_review_queue(
            queue_csv_path=Path(args.queue_csv),
            out_dir=Path(args.out_dir),
        )
        if args.manifest_out:
            atomic_write_text(
                Path(args.manifest_out).expanduser().resolve(),
                report.model_dump_json(indent=2),
            )
    except Exception as exc:
        print(
            f"[evidence_grounding_frontier_human_review_queue_split] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"source_csv_count={report.source_csv_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_review_row_count={report.merged_review_row_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_reviewed_value_count={report.merged_reviewed_value_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_missing_value_count={report.merged_missing_value_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_reviewed_evidence_count={report.merged_reviewed_evidence_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_missing_evidence_count={report.merged_missing_evidence_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_reviewer_value_hint_count={report.merged_reviewer_value_hint_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_reviewer_evidence_hint_count={report.merged_reviewer_evidence_hint_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_missing_value_with_hint_count={report.merged_missing_value_with_hint_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"merged_missing_value_without_hint_count={report.merged_missing_value_without_hint_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"ready_source_count={report.ready_source_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        f"blocked_source_count={report.blocked_source_count}"
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        "merged_missing_value_counts_by_field="
        + (",".join(f"{key}:{value}" for key, value in report.merged_missing_value_counts_by_field.items()) or "-")
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        "merged_missing_evidence_counts_by_field="
        + (",".join(f"{key}:{value}" for key, value in report.merged_missing_evidence_counts_by_field.items()) or "-")
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        "merged_reviewer_value_hint_counts_by_field="
        + (",".join(f"{key}:{value}" for key, value in report.merged_reviewer_value_hint_counts_by_field.items()) or "-")
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        "merged_reviewer_evidence_hint_counts_by_field="
        + (",".join(f"{key}:{value}" for key, value in report.merged_reviewer_evidence_hint_counts_by_field.items()) or "-")
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        "merged_missing_value_with_hint_counts_by_field="
        + (",".join(f"{key}:{value}" for key, value in report.merged_missing_value_with_hint_counts_by_field.items()) or "-")
    )
    print(
        "[evidence_grounding_frontier_human_review_queue_split] "
        "merged_missing_value_without_hint_counts_by_field="
        + (",".join(f"{key}:{value}" for key, value in report.merged_missing_value_without_hint_counts_by_field.items()) or "-")
    )
    for index, source in enumerate(report.sources, start=1):
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"reviewed_csv.{index}={mask_local_paths_in_text(source.reviewed_csv_path)};"
            f"row_count={source.merged_review_row_count}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"ready_for_fill_review_audit.{index}={source.ready_for_fill_review_audit}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"fill_review_blocker_reasons.{index}={','.join(source.fill_review_blocker_reasons) or '-'}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"next_action_kind.{index}={source.next_action_kind}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"missing_value_task_ids.{index}={','.join(source.merged_missing_value_task_ids) or '-'}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"missing_evidence_task_ids.{index}={','.join(source.merged_missing_evidence_task_ids) or '-'}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"reviewer_value_hint_count.{index}={source.merged_reviewer_value_hint_count}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"reviewer_evidence_hint_count.{index}={source.merged_reviewer_evidence_hint_count}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"missing_value_with_hint_count.{index}={source.merged_missing_value_with_hint_count}"
        )
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"missing_value_without_hint_count.{index}={source.merged_missing_value_without_hint_count}"
        )
        if source.fill_review_audit_command_hint:
            print(
                "[evidence_grounding_frontier_human_review_queue_split] "
                f"fill_review_audit_command.{index}={mask_local_paths_in_text(source.fill_review_audit_command_hint)}"
            )
        if source.fill_task_apply_command_hint:
            print(
                "[evidence_grounding_frontier_human_review_queue_split] "
                f"fill_task_apply_command.{index}={mask_local_paths_in_text(source.fill_task_apply_command_hint)}"
            )
    for index, command_hint in enumerate(report.ready_fill_review_audit_command_hints, start=1):
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"ready_fill_review_audit_command.{index}={mask_local_paths_in_text(command_hint)}"
        )
    if args.manifest_out:
        print(
            "[evidence_grounding_frontier_human_review_queue_split] "
            f"manifest={mask_local_paths_in_text(str(Path(args.manifest_out).expanduser().resolve()))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
