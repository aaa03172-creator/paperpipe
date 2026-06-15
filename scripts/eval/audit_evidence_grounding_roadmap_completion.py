#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import build_evidence_grounding_roadmap_completion_audit_report
from src.services.path_masking import mask_local_paths_in_text


def _check_evidence_value(report, requirement_id: str, key: str) -> str:
    prefix = f"{key}="
    for check in report.checks:
        if check.requirement_id != requirement_id:
            continue
        for item in check.evidence:
            if item.startswith(prefix):
                value = item.removeprefix(prefix).strip()
                return "" if value == "-" else value
    return ""


def _stdout_value(value: object) -> str:
    return mask_local_paths_in_text(str(value))


def _frontier_human_review_queue_split_command(queue_csv_out: Path) -> str:
    split_out_dir = queue_csv_out.with_suffix("")
    manifest_out = queue_csv_out.with_name(f"{queue_csv_out.stem}_split_manifest.json")
    return (
        ".venv/bin/python scripts/eval/split_evidence_grounding_frontier_human_review_queue.py "
        f"--queue-csv {_stdout_value(queue_csv_out)} "
        f"--out-dir {_stdout_value(split_out_dir)} "
        f"--manifest-out {_stdout_value(manifest_out)}"
    )


def _stdout_count_mapping(mapping: dict[str, int]) -> str:
    return ",".join(f"{key}:{value}" for key, value in sorted(mapping.items())) or "-"


def _stdout_string_mapping(mapping: dict[str, str]) -> str:
    return ";".join(
        f"{key}:{_stdout_value(value)}" for key, value in sorted(mapping.items())
    ) or "-"


def _stdout_nested_count_mapping(mapping: dict[str, dict[str, int]]) -> str:
    return ";".join(
        f"{key}:{'|'.join(f'{field}:{count}' for field, count in sorted(value.items())) or '-'}"
        for key, value in sorted(mapping.items())
    ) or "-"


def _reviewer_value_hint_counts_by_requirement(
    *,
    missing_value_counts: dict[str, dict[str, int]],
    missing_suggestion_counts: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    values: dict[str, dict[str, int]] = {}
    for requirement_id, counts_by_field in missing_value_counts.items():
        missing_suggestions = missing_suggestion_counts.get(requirement_id, {})
        for field_name, count in counts_by_field.items():
            hint_count = count - missing_suggestions.get(field_name, 0)
            if hint_count > 0:
                values.setdefault(requirement_id, {})[field_name] = hint_count
    return values


def _reviewer_value_hint_counts_by_field(
    *,
    missing_value_counts: dict[str, int],
    missing_suggestion_counts: dict[str, int],
) -> dict[str, int]:
    values: dict[str, int] = {}
    for field_name, count in missing_value_counts.items():
        hint_count = count - missing_suggestion_counts.get(field_name, 0)
        if hint_count > 0:
            values[field_name] = hint_count
    return values


def _stdout_nested_ids_mapping(mapping: dict[str, dict[str, list[str]]]) -> str:
    return ";".join(
        f"{key}:{'|'.join(f'{field}:{','.join(_stdout_value(item) for item in values) or '-'}' for field, values in sorted(value.items())) or '-'}"
        for key, value in sorted(mapping.items())
    ) or "-"


def _stdout_path_count_mapping(mapping: dict[str, list[str]]) -> str:
    return ",".join(f"{key}:{len(value)}" for key, value in sorted(mapping.items())) or "-"


def _frontier_human_review_source_metadata_by_open_csv_path(report) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for check in report.checks:
        values: dict[str, str] = {}
        for item in check.evidence:
            key, separator, value = str(item).partition("=")
            if not separator:
                continue
            values[key.strip()] = value.strip()
        for key, open_csv_path in values.items():
            if not key.endswith("_fill_review_status_open_csv_path") or open_csv_path in {"", "-"}:
                continue
            prefix = key.removesuffix("_open_csv_path")
            path_prefix = prefix.removesuffix("_fill_review_status")
            metadata[open_csv_path] = {
                "source_fill_review_status_path": values.get(
                    path_prefix + "_fill_review_status_path",
                    "",
                ),
                "source_task_export_path": values.get(
                    prefix + "_source_task_export_path",
                    values.get(path_prefix + "_fill_task_export_path", ""),
                ),
                "source_reviewed_csv_path": values.get(
                    prefix + "_reviewed_csv_path",
                    "",
                ),
            }
    return metadata


def _write_frontier_human_review_queue_csv(report, out: Path) -> int:
    base_fields = [
        "task_id",
        "record_ref",
        "field_name",
        "suggested_value",
        "available_context_keys",
        "available_context_values",
        "filled_patch_fields",
        "review_required",
        "reviewer_value",
        "reviewer_value_hint",
        "reviewer_evidence_hint",
        "reviewer_evidence",
        "reviewer_notes",
        "review_status",
        "review_findings",
        "has_reviewer_value",
        "has_reviewer_evidence",
    ]
    rows: list[dict[str, str]] = []
    observed_fields: set[str] = set()
    source_metadata_by_open_csv_path = _frontier_human_review_source_metadata_by_open_csv_path(report)
    summaries_by_requirement = {
        summary.requirement_id: summary for summary in report.frontier_next_action_summaries
    }
    for requirement_id, raw_paths in sorted(
        report.frontier_human_review_open_csv_paths_by_requirement.items()
    ):
        for raw_path in raw_paths:
            source_path = Path(raw_path)
            if not source_path.exists():
                summary = summaries_by_requirement.get(requirement_id)
                task_ids = summary.human_review_open_task_ids if summary is not None else []
                for source_row_number, task_id in enumerate(task_ids, start=1):
                    record_ref, _, field_name = task_id.rpartition(":")
                    rows.append(
                        {
                            "requirement_id": requirement_id,
                            "source_open_csv_path": str(source_path),
                            "source_open_csv_row_number": str(source_row_number),
                            "source_open_csv_missing": "true",
                            **source_metadata_by_open_csv_path.get(str(source_path), {}),
                            "task_id": task_id,
                            "record_ref": record_ref,
                            "field_name": field_name,
                        }
                    )
                continue
            with source_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for source_row_number, row in enumerate(reader, start=1):
                    observed_fields.update(str(field) for field in row)
                    rows.append(
                        {
                            "requirement_id": requirement_id,
                            "source_open_csv_path": str(source_path),
                            "source_open_csv_row_number": str(source_row_number),
                            "source_open_csv_missing": "false",
                            **source_metadata_by_open_csv_path.get(str(source_path), {}),
                            **{str(key): str(value or "") for key, value in row.items()},
                        }
                    )
    fieldnames = [
        "requirement_id",
        "source_open_csv_path",
        "source_open_csv_row_number",
        "source_open_csv_missing",
        "source_fill_review_status_path",
        "source_task_export_path",
        "source_reviewed_csv_path",
        *base_fields,
        *sorted(observed_fields - set(base_fields)),
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _markdown_bullets(values: list[str]) -> list[str]:
    if not values:
        return ["- -"]
    return [f"- `{_stdout_value(value)}`" for value in values]


def _markdown_sample_bullets(values: list[str], *, limit: int = 5) -> list[str]:
    if not values:
        return ["- -"]
    sample = values[:limit]
    bullets = [f"- `{_stdout_value(value)}`" for value in sample]
    if len(values) > limit:
        bullets.append(f"- `...{len(values) - limit}_more`")
    return bullets


def _frontier_human_review_queue_guide_requirement_ids(report) -> list[str]:
    split_requirement_ids = (
        set(report.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement)
        | set(
            report.frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement
        )
        | set(
            report.frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement
        )
    )
    if split_requirement_ids:
        return sorted(split_requirement_ids)
    return sorted(
        requirement_id
        for requirement_id, row_count in report.frontier_human_review_open_csv_row_counts_by_requirement.items()
        if row_count > 0
    )


def _write_frontier_human_review_queue_guide(
    report,
    out: Path,
    *,
    queue_csv_out: Path | None = None,
) -> int:
    requirement_ids = _frontier_human_review_queue_guide_requirement_ids(report)
    frontier_summaries_by_requirement = {
        summary.requirement_id: summary for summary in report.frontier_next_action_summaries
    }
    reviewer_value_hint_counts_by_requirement = _reviewer_value_hint_counts_by_requirement(
        missing_value_counts=report.frontier_human_review_open_csv_missing_value_counts_by_requirement,
        missing_suggestion_counts=report.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement,
    )
    lines = [
        "# Evidence Grounding Frontier Human Review Queue",
        "",
        "This is a non-canonical reviewer handoff generated from the roadmap completion audit.",
        "",
        f"- Roadmap complete: `{str(report.roadmap_complete).lower()}`",
        f"- Pass count: `{report.pass_count}`",
        f"- Fail count: `{report.fail_count}`",
        f"- Combined open rows: `{report.human_review_open_csv_row_count}`",
        f"- Unblocked frontier actions: `{report.frontier_unblocked_next_action_count}`",
    ]
    if queue_csv_out is not None:
        lines.append(f"- Combined queue CSV: `{_stdout_value(queue_csv_out)}`")
        lines.append(
            f"- Split command: `{_frontier_human_review_queue_split_command(queue_csv_out)}`"
        )
    lines.extend(
        [
            "",
            (
                "Reviewer columns to complete: `reviewer_value` for every open row, "
                "plus `reviewer_evidence` when `reviewer_evidence_hint` is blank."
            ),
            "Optional columns: `reviewer_notes`, `review_status`, and `review_findings`.",
            "",
        ]
    )
    if not requirement_ids:
        lines.extend(["No unblocked human-review split requirements are currently present.", ""])
    for requirement_id in requirement_ids:
        summary = frontier_summaries_by_requirement.get(requirement_id)
        next_action_kinds = (
            report.frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement.get(
                requirement_id,
                [],
            )
            or ([summary.kind] if summary is not None else [])
        )
        blocker_reasons = (
            report.frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement.get(
                requirement_id,
                [],
            )
            or (summary.blocker_reasons if summary is not None else [])
        )
        missing_value_task_ids = (
            report.frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement.get(
                requirement_id,
                [],
            )
            or (summary.human_review_open_task_ids if summary is not None else [])
        )
        missing_value_count = (
            report.frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement.get(
                requirement_id,
                0,
            )
            or len(missing_value_task_ids)
        )
        missing_value_counts_by_field = (
            report.frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement.get(
                requirement_id,
                {},
            )
            or report.frontier_human_review_open_csv_missing_value_counts_by_requirement.get(requirement_id, {})
        )
        reviewer_value_hint_counts_by_field = (
            report.frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement.get(
                requirement_id,
                {},
            )
            or reviewer_value_hint_counts_by_requirement.get(requirement_id, {})
        )
        reviewer_evidence_hint_counts_by_field = (
            report.frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement.get(
                requirement_id,
                {},
            )
            or report.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement.get(
                requirement_id,
                {},
            )
        )
        fill_review_audit_commands = (
            report.frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement.get(
                requirement_id,
                [],
            )
            or report.human_review_command_hints_by_requirement.get(requirement_id, [])
        )
        lines.extend(
            [
                f"## {requirement_id}",
                "",
                f"- Open rows: `{report.frontier_human_review_open_csv_row_counts_by_requirement.get(requirement_id, 0)}`",
                (
                    "- Current next action kinds: "
                    f"`{_stdout_ids_by_kind_mapping({requirement_id: next_action_kinds})}`"
                ),
                (
                    "- Current blocker reasons: "
                    f"`{_stdout_ids_by_kind_mapping({requirement_id: blocker_reasons})}`"
                ),
                (
                    "- Missing value task IDs: "
                    f"`{missing_value_count}`"
                ),
                (
                    "- Missing evidence task IDs: "
                    f"`{report.frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement.get(requirement_id, 0)}`"
                ),
                (
                    "- Missing value counts by field: "
                    f"`{_stdout_nested_count_mapping({requirement_id: missing_value_counts_by_field})}`"
                ),
                (
                    "- Missing evidence counts by field: "
                    f"`{_stdout_nested_count_mapping({requirement_id: report.frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement.get(requirement_id, {})})}`"
                ),
                (
                    "- Reviewer value hint counts by field: "
                    f"`{_stdout_nested_count_mapping({requirement_id: reviewer_value_hint_counts_by_field})}`"
                ),
                (
                    "- Reviewer evidence hint counts by field: "
                    f"`{_stdout_nested_count_mapping({requirement_id: reviewer_evidence_hint_counts_by_field})}`"
                ),
                "",
                "Missing value task ID sample:",
                *_markdown_sample_bullets(missing_value_task_ids),
                "",
                "Missing evidence task ID sample:",
                *_markdown_sample_bullets(
                    report.frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement.get(
                        requirement_id,
                        [],
                    )
                ),
                "",
                "Open CSV paths:",
                *_markdown_bullets(
                    report.frontier_human_review_open_csv_paths_by_requirement.get(requirement_id, [])
                ),
                "",
                "Reviewed CSV paths:",
                *_markdown_bullets(
                    report.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement.get(
                        requirement_id,
                        [],
                    )
                ),
                "",
                "Fill-review audit commands:",
                *_markdown_bullets(fill_review_audit_commands),
                "",
                "Fill-task apply commands:",
                *_markdown_bullets(
                    report.frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement.get(
                        requirement_id,
                        [],
                    )
                ),
                "",
            ]
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return len(requirement_ids)


def _stdout_ids_by_kind_mapping(mapping: dict[str, list[str]]) -> str:
    return ";".join(
        f"{key}:{'|'.join(_stdout_value(item) for item in value) or '-'}"
        for key, value in sorted(mapping.items())
    ) or "-"


def _stdout_id_list(values: list[str]) -> str:
    return ",".join(_stdout_value(value) for value in values) or "-"


def _stdout_next_action_diagnostic_fields(item) -> str:
    return (
        f" kind={item.kind}"
        f" has_command_hint={item.has_command_hint}"
        f" has_unresolved_command_placeholder={item.has_unresolved_command_placeholder}"
        f" blocker_reasons={_stdout_id_list(item.blocker_reasons)}"
        f" blocked_by_requirement_ids={_stdout_id_list(item.blocked_by_requirement_ids)}"
        f" unresolved_command_placeholders={_stdout_id_list(item.unresolved_command_placeholders)}"
        f" missing_metric_inputs={_stdout_id_list(item.missing_metric_inputs)}"
        f" human_review_open_task_id_count={len(item.human_review_open_task_ids)}"
    )


def _print_action_queue_counts(report, *, prefix: str) -> None:
    for key, value in (
        ("action_queue_next_action_count", report.next_action_count),
        ("action_queue_human_review_next_action_count", report.human_review_next_action_count),
        ("action_queue_human_review_unique_next_action_count", report.human_review_unique_next_action_count),
        ("action_queue_ready_to_run_next_action_count", report.ready_to_run_next_action_count),
        ("action_queue_ready_to_run_unique_next_action_count", report.ready_to_run_unique_next_action_count),
        ("action_queue_placeholder_command_next_action_count", report.placeholder_command_next_action_count),
        (
            "action_queue_placeholder_command_unique_next_action_count",
            report.placeholder_command_unique_next_action_count,
        ),
        ("action_queue_blocked_without_next_action_count", report.blocked_without_next_action_count),
    ):
        print(f"[{prefix}] {key}={value}")


def _print_blocker_summary(report, *, prefix: str) -> None:
    reviewer_value_hint_counts_by_requirement = _reviewer_value_hint_counts_by_requirement(
        missing_value_counts=report.frontier_human_review_open_csv_missing_value_counts_by_requirement,
        missing_suggestion_counts=report.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement,
    )
    reviewer_value_hint_counts_by_field = _reviewer_value_hint_counts_by_field(
        missing_value_counts=report.frontier_human_review_open_csv_missing_value_counts_by_field,
        missing_suggestion_counts=report.frontier_human_review_open_csv_missing_suggestion_counts_by_field,
    )
    for key, value in (
        ("roadmap_blocker_count", report.roadmap_blocker_count),
        ("roadmap_blocker_ids", _stdout_id_list(report.roadmap_blocker_ids)),
        ("roadmap_blocker_reason_counts", _stdout_count_mapping(report.roadmap_blocker_reason_counts)),
        (
            "roadmap_blocker_next_action_kind_counts_by_requirement",
            _stdout_nested_count_mapping(report.roadmap_blocker_next_action_kind_counts_by_requirement),
        ),
        (
            "roadmap_blocker_next_action_kind_counts",
            _stdout_count_mapping(report.roadmap_blocker_next_action_kind_counts),
        ),
        (
            "roadmap_blocker_missing_metric_inputs_by_requirement",
            _stdout_ids_by_kind_mapping(report.frontier_missing_metric_inputs_by_requirement),
        ),
        (
            "roadmap_blocker_missing_metric_input_counts_by_metric",
            _stdout_count_mapping(report.frontier_missing_metric_input_counts_by_metric),
        ),
        (
            "roadmap_blocker_human_review_open_task_counts_by_requirement",
            _stdout_path_count_mapping(report.frontier_human_review_open_task_ids_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_row_counts_by_requirement",
            _stdout_count_mapping(report.frontier_human_review_open_csv_row_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_field_names_by_requirement",
            _stdout_ids_by_kind_mapping(report.frontier_human_review_open_field_names_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_value_counts_by_field",
            _stdout_count_mapping(report.frontier_human_review_open_csv_missing_value_counts_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_suggestion_counts_by_requirement",
            _stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_suggestion_counts_by_field",
            _stdout_count_mapping(report.frontier_human_review_open_csv_missing_suggestion_counts_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_requirement",
            _stdout_nested_ids_mapping(
                report.roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_requirement
            ),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_field",
            _stdout_ids_by_kind_mapping(
                report.roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_field
            ),
        ),
        (
            "roadmap_blocker_human_review_open_csv_suggested_value_counts_by_requirement",
            _stdout_nested_count_mapping(report.frontier_human_review_open_csv_suggested_value_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_suggested_value_counts_by_field",
            _stdout_count_mapping(report.frontier_human_review_open_csv_suggested_value_counts_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_record_filled_patch_field_counts_by_requirement",
            _stdout_nested_count_mapping(report.frontier_human_review_open_record_filled_patch_field_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_record_filled_patch_field_counts_by_field",
            _stdout_count_mapping(report.frontier_human_review_open_record_filled_patch_field_counts_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_available_context_counts_by_requirement",
            _stdout_nested_count_mapping(report.frontier_human_review_open_csv_available_context_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_available_context_counts_by_field",
            _stdout_count_mapping(report.frontier_human_review_open_csv_available_context_counts_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_available_context_values_by_requirement",
            _stdout_nested_ids_mapping(report.frontier_human_review_open_csv_available_context_values_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_available_context_values_by_field",
            _stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_available_context_values_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_context_counts_by_requirement",
            _stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_context_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_context_counts_by_field",
            _stdout_count_mapping(report.frontier_human_review_open_csv_missing_context_counts_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_context_task_ids_by_requirement",
            _stdout_nested_ids_mapping(report.frontier_human_review_open_csv_missing_context_task_ids_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_context_task_ids_by_field",
            _stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_missing_context_task_ids_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_reviewer_value_hint_counts_by_requirement",
            _stdout_nested_count_mapping(reviewer_value_hint_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_reviewer_value_hint_counts_by_field",
            _stdout_count_mapping(reviewer_value_hint_counts_by_field),
        ),
        (
            "roadmap_blocker_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement",
            _stdout_nested_count_mapping(report.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_reviewer_evidence_hint_counts_by_field",
            _stdout_count_mapping(report.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field),
        ),
        (
            "roadmap_blocker_ready_to_run_unique_next_action_count",
            report.roadmap_blocker_ready_to_run_unique_next_action_count,
        ),
        (
            "roadmap_blocker_placeholder_command_unique_next_action_count",
            report.roadmap_blocker_placeholder_command_unique_next_action_count,
        ),
        (
            "roadmap_blocker_prerequisite_gated_next_action_count",
            report.roadmap_blocker_prerequisite_gated_next_action_count,
        ),
        (
            "roadmap_blocker_blocked_without_next_action_count",
            report.roadmap_blocker_blocked_without_next_action_count,
        ),
    ):
        print(f"[{prefix}] {key}={value}")


def _print_placeholder_summary(report, *, prefix: str) -> None:
    for key, value in (
        ("placeholder_summary_unique_action_count", report.placeholder_command_unique_next_action_count),
        (
            "placeholder_summary_unresolved_placeholder_counts",
            _stdout_count_mapping(report.placeholder_command_unresolved_placeholder_counts_by_placeholder),
        ),
        (
            "placeholder_summary_unresolved_placeholders_by_requirement",
            _stdout_ids_by_kind_mapping(report.placeholder_command_unresolved_placeholders_by_requirement),
        ),
        (
            "placeholder_summary_frontier_unresolved_placeholder_count",
            report.frontier_unresolved_command_placeholder_count,
        ),
        (
            "placeholder_summary_frontier_unresolved_placeholder_counts",
            _stdout_count_mapping(report.frontier_unresolved_command_placeholder_counts_by_placeholder),
        ),
        (
            "placeholder_summary_frontier_unresolved_placeholders_by_requirement",
            _stdout_ids_by_kind_mapping(report.frontier_unresolved_command_placeholders_by_requirement),
        ),
        ("placeholder_summary_ready_to_run_unique_next_action_count", report.ready_to_run_unique_next_action_count),
    ):
        print(f"[{prefix}] {key}={value}")


def _stdout_frontier_summary_mapping(summaries) -> str:
    return ";".join(
        (
            f"{item.requirement_id}:{item.kind}:"
            f"placeholders={','.join(item.unresolved_command_placeholders) or '-'}:"
            f"missing_metrics={','.join(item.missing_metric_inputs) or '-'}:"
            f"open_csv_rows={item.human_review_open_csv_row_count}:"
            "missing_fields="
            f"{','.join(f'{key}:{value}' for key, value in sorted(item.human_review_open_csv_missing_value_counts_by_field.items())) or '-'}:"
            f"open_csv_paths={len(item.human_review_open_csv_paths)}:"
            f"open_task_ids={len(item.human_review_open_task_ids)}:"
            f"blockers={','.join(item.blocker_reasons) or '-'}:"
            f"blocked_by={','.join(item.blocked_by_requirement_ids) or '-'}"
        )
        for item in summaries
    ) or "-"


def _print_threshold_package_diagnostics(report, *, prefix: str) -> None:
    for evidence_key, output_key in (
        ("not_ready_splits", "threshold_package_not_ready_splits"),
        ("package_run_readiness_fail_count", "threshold_package_run_readiness_fail_count"),
        ("baseline_goldset_missing_papers_by_split", "threshold_package_baseline_missing_papers_by_split"),
        ("candidate_goldset_missing_papers_by_split", "threshold_package_candidate_missing_papers_by_split"),
        ("baseline_scorecard_not_ready_candidate_ids", "threshold_package_baseline_scorecard_not_ready_ids"),
        ("candidate_scorecard_not_ready_candidate_ids", "threshold_package_candidate_scorecard_not_ready_ids"),
        ("baseline_scorecard_fail_candidate_ids", "threshold_package_baseline_scorecard_fail_ids"),
        ("candidate_scorecard_fail_candidate_ids", "threshold_package_candidate_scorecard_fail_ids"),
        ("baseline_scorecard_fail_reason_codes", "threshold_package_baseline_scorecard_fail_reason_codes"),
        ("candidate_scorecard_fail_reason_codes", "threshold_package_candidate_scorecard_fail_reason_codes"),
        ("baseline_scorecard_fail_proxy_metrics", "threshold_package_baseline_scorecard_fail_proxy_metrics"),
        ("candidate_scorecard_fail_proxy_metrics", "threshold_package_candidate_scorecard_fail_proxy_metrics"),
    ):
        value = _check_evidence_value(report, "fixed_goldset_threshold_adoption_package_ready", evidence_key)
        if value:
            print(f"[{prefix}] {output_key}={_stdout_value(value)}")


def _print_p0_metric_diagnostics(report, *, prefix: str) -> None:
    for evidence_key, output_key, requirement_id in (
        ("available_p0_metrics", "p0_available_metrics", "p0_metrics_reported"),
        ("missing_p0_metrics", "p0_missing_metrics", "p0_metrics_reported"),
        (
            "available_p0_calibration_metrics",
            "threshold_p0_available_calibration_metrics",
            "production_threshold_adoption_reviewed",
        ),
        (
            "adopted_p0_threshold_metrics",
            "threshold_p0_adopted_metrics",
            "production_threshold_adoption_reviewed",
        ),
        (
            "missing_p0_calibration_metrics",
            "threshold_p0_missing_calibration_metrics",
            "production_threshold_adoption_reviewed",
        ),
        (
            "missing_p0_adoption_metrics",
            "threshold_p0_missing_adoption_metrics",
            "production_threshold_adoption_reviewed",
        ),
        (
            "production_threshold_ready",
            "threshold_production_ready",
            "production_threshold_adoption_reviewed",
        ),
    ):
        value = _check_evidence_value(report, requirement_id, evidence_key)
        if value:
            print(f"[{prefix}] {output_key}={_stdout_value(value)}")


def _print_fill_review_suggestion_diagnostics(report, *, prefix: str) -> None:
    for requirement_id, evidence_prefix, output_prefix in (
        (
            "candidate_configuration_lineage",
            "candidate_lineage_patch_template",
            "candidate_lineage",
        ),
        (
            "structured_correction_log",
            "claim_evidence_correction_repair_patch_template",
            "claim_evidence_correction_repair",
        ),
    ):
        for evidence_suffix, output_suffix in (
            (
                "fill_review_status_suggested_value_count_by_field",
                "fill_review_suggested_value_count_by_field",
            ),
            (
                "fill_review_status_missing_suggestion_count_by_field",
                "fill_review_missing_suggestion_count_by_field",
            ),
            (
                "fill_review_status_available_context_count_by_field",
                "fill_review_available_context_count_by_field",
            ),
            (
                "fill_review_status_available_context_keys_by_field",
                "fill_review_available_context_keys_by_field",
            ),
            (
                "fill_review_status_available_context_values_by_field",
                "fill_review_available_context_values_by_field",
            ),
            (
                "fill_review_status_missing_context_count_by_field",
                "fill_review_missing_context_count_by_field",
            ),
        ):
            value = _check_evidence_value(
                report,
                requirement_id,
                f"{evidence_prefix}_{evidence_suffix}",
            )
            if value:
                print(f"[{prefix}] {output_prefix}_{output_suffix}={_stdout_value(value)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether current evidence-grounding artifacts prove the roadmap Definition of Done. "
            "This produces a non-canonical review artifact and fails closed when required evidence is missing."
        )
    )
    parser.add_argument("--out", required=True, help="Output roadmap completion audit JSON path")
    parser.add_argument("--audit-id", default="evidence-grounding-roadmap-completion-audit")
    parser.add_argument("--scorecard", help="Optional standalone evidence_grounding_scorecard.v1 JSON path")
    parser.add_argument(
        "--comparison-suite",
        help=(
            "Optional evidence_grounding_fixed_goldset_comparison_suite.v1 JSON path. "
            "Baseline/candidate/comparison/readiness report paths are resolved relative to this file unless explicit paths override them."
        ),
    )
    parser.add_argument("--baseline-benchmark-report", help="Baseline benchmark report JSON path")
    parser.add_argument("--candidate-benchmark-report", help="Candidate benchmark report JSON path")
    parser.add_argument("--comparison-report", help="Scorecard/benchmark comparison report JSON path")
    parser.add_argument("--run-readiness-report", help="Fixed-goldset run-readiness report JSON path")
    parser.add_argument("--threshold-calibration-report", help="Threshold calibration report JSON path")
    parser.add_argument("--threshold-adoption-review", help="Threshold adoption review JSON path")
    parser.add_argument("--threshold-adoption-package", help="Threshold adoption package JSON path")
    parser.add_argument("--contract-readiness-report", help="Contract readiness review JSON path")
    parser.add_argument("--gold-release-package", help="Paper-understanding gold release package JSON path")
    parser.add_argument("--gold-release-readiness-report", help="Paper-understanding gold release-readiness JSON path")
    parser.add_argument(
        "--additional-artifact",
        action="append",
        default=[],
        help=(
            "Additional non-canonical review/contract artifact path to consider during completion audit; "
            "for example p0_overstatement_review_packet.json, p0_overstatement_review_summary.json, "
            "active_review_readiness.json, or active_reviewer_handoff_refresh.json. "
            "May be repeated."
        ),
    )
    parser.add_argument(
        "--correction-log",
        help=(
            "Claim/evidence correction evidence path: raw ClaimEvidenceCorrectionCase JSONL "
            "or claim_evidence_eval_candidate_export.v1 JSON review artifact"
        ),
    )
    parser.add_argument("--goldset-root", help="Optional current workspace goldset root to inventory")
    parser.add_argument("--run-root", help="Optional current workspace run/artifact root to inventory")
    parser.add_argument("--required-ready-gold-count", type=int, default=1)
    parser.add_argument("--required-ready-run-count", type=int, default=1)
    parser.add_argument(
        "--inventory-required-artifact",
        action="append",
        dest="inventory_required_artifacts",
        help="Required run artifact for workspace inventory checks; may be repeated.",
    )
    parser.add_argument(
        "--print-next-actions",
        action="store_true",
        help="Print the roadmap-completion next-action queue to stdout after the summary.",
    )
    parser.add_argument(
        "--print-human-review-actions",
        action="store_true",
        help="Print the unique human-review next-action queue to stdout after the summary.",
    )
    parser.add_argument(
        "--print-ready-to-run-actions",
        action="store_true",
        help="Print the unique ready-to-run next-action queue to stdout after the summary.",
    )
    parser.add_argument(
        "--print-placeholder-command-actions",
        action="store_true",
        help="Print the unique placeholder-command next-action queue to stdout after the summary.",
    )
    parser.add_argument(
        "--print-all-action-queues",
        action="store_true",
        help=(
            "Print the full next-action queue plus the unique human-review, ready-to-run, "
            "and placeholder-command action queues."
        ),
    )
    parser.add_argument(
        "--print-action-queue-counts",
        action="store_true",
        help="Print compact action queue counts without requiring verbose action rows.",
    )
    parser.add_argument(
        "--print-blocker-summary",
        action="store_true",
        help="Print compact blocker, missing metric, and human-review task summaries.",
    )
    parser.add_argument(
        "--print-placeholder-summary",
        action="store_true",
        help="Print compact unresolved command-placeholder summaries without verbose action rows.",
    )
    parser.add_argument(
        "--print-frontier-actions",
        action="store_true",
        help="Print only the first next action for each currently failed roadmap requirement.",
    )
    parser.add_argument(
        "--print-unblocked-frontier-actions",
        action="store_true",
        help=(
            "Print only frontier next actions that are not blocked by another failed "
            "roadmap requirement."
        ),
    )
    parser.add_argument(
        "--next-action-limit",
        type=int,
        default=0,
        help="Maximum next actions to print when --print-next-actions is set. Use 0 for all actions.",
    )
    parser.add_argument(
        "--unique-action-limit",
        type=int,
        default=10,
        help=(
            "Maximum unique actions to print for --print-ready-to-run-actions and "
            "--print-placeholder-command-actions. Use 0 for all actions."
        ),
    )
    parser.add_argument(
        "--human-review-action-limit",
        type=int,
        default=0,
        help="Maximum human-review actions to print when --print-human-review-actions is set. Use 0 for all actions.",
    )
    parser.add_argument(
        "--frontier-action-limit",
        type=int,
        default=0,
        help=(
            "Maximum frontier actions to print when --print-frontier-actions or "
            "--print-unblocked-frontier-actions is set. Use 0 for all actions."
        ),
    )
    parser.add_argument(
        "--frontier-human-review-queue-csv-out",
        help=(
            "Optional CSV path that combines the current frontier human-review open CSV rows "
            "with requirement/source columns for reviewer handoff."
        ),
    )
    parser.add_argument(
        "--frontier-human-review-queue-guide-out",
        help=(
            "Optional Markdown path that summarizes the current unblocked frontier "
            "human-review split requirements, counts, reviewed CSV paths, and next commands."
        ),
    )
    args = parser.parse_args()

    report = build_evidence_grounding_roadmap_completion_audit_report(
        audit_id=args.audit_id,
        scorecard_path=Path(args.scorecard) if args.scorecard else None,
        comparison_suite_path=Path(args.comparison_suite) if args.comparison_suite else None,
        baseline_benchmark_report_path=Path(args.baseline_benchmark_report) if args.baseline_benchmark_report else None,
        candidate_benchmark_report_path=(
            Path(args.candidate_benchmark_report) if args.candidate_benchmark_report else None
        ),
        comparison_report_path=Path(args.comparison_report) if args.comparison_report else None,
        run_readiness_report_path=Path(args.run_readiness_report) if args.run_readiness_report else None,
        threshold_calibration_report_path=(
            Path(args.threshold_calibration_report) if args.threshold_calibration_report else None
        ),
        threshold_adoption_review_path=Path(args.threshold_adoption_review) if args.threshold_adoption_review else None,
        threshold_adoption_package_path=(
            Path(args.threshold_adoption_package) if args.threshold_adoption_package else None
        ),
        contract_readiness_report_path=Path(args.contract_readiness_report) if args.contract_readiness_report else None,
        gold_release_package_path=Path(args.gold_release_package) if args.gold_release_package else None,
        gold_release_readiness_report_path=(
            Path(args.gold_release_readiness_report) if args.gold_release_readiness_report else None
        ),
        correction_log_path=Path(args.correction_log) if args.correction_log else None,
        additional_artifact_paths=(
            [Path(path).expanduser().resolve() for path in args.additional_artifact]
            if args.additional_artifact
            else None
        ),
        goldset_root=Path(args.goldset_root) if args.goldset_root else None,
        run_root=Path(args.run_root) if args.run_root else None,
        required_ready_gold_count=args.required_ready_gold_count,
        required_ready_run_count=args.required_ready_run_count,
        inventory_required_artifacts=args.inventory_required_artifacts,
        out=Path(args.out).expanduser().resolve(),
    )
    queue_csv_out = None
    if args.frontier_human_review_queue_csv_out:
        queue_csv_out = Path(args.frontier_human_review_queue_csv_out).expanduser().resolve()
        queue_row_count = _write_frontier_human_review_queue_csv(report, queue_csv_out)
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_human_review_queue_csv={_stdout_value(queue_csv_out)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_human_review_queue_row_count={queue_row_count}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_human_review_queue_split_command={_frontier_human_review_queue_split_command(queue_csv_out)}"
        )
    if args.frontier_human_review_queue_guide_out:
        queue_guide_out = Path(args.frontier_human_review_queue_guide_out).expanduser().resolve()
        guide_requirement_count = _write_frontier_human_review_queue_guide(
            report,
            queue_guide_out,
            queue_csv_out=queue_csv_out,
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_human_review_queue_guide={_stdout_value(queue_guide_out)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_human_review_queue_guide_requirement_count={guide_requirement_count}"
        )
    print(f"[evidence_grounding_roadmap_completion] audit_id={report.audit_id}")
    print(f"[evidence_grounding_roadmap_completion] pass_count={report.pass_count}")
    print(f"[evidence_grounding_roadmap_completion] fail_count={report.fail_count}")
    print(f"[evidence_grounding_roadmap_completion] roadmap_complete={report.roadmap_complete}")
    print(
        "[evidence_grounding_roadmap_completion] "
        f"additional_artifact_count={report.additional_artifact_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"additional_artifact_paths={_stdout_id_list(report.additional_artifact_paths)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"active_review_readiness_path={_stdout_value(report.active_review_readiness_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_ready_for_downstream_review_steps="
        f"{report.active_review_readiness_ready_for_downstream_review_steps}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"active_review_readiness_blocker_count={report.active_review_readiness_blocker_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_structured_reviewed_csv_path="
        f"{_stdout_value(report.active_review_readiness_structured_reviewed_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_structured_open_csv_path="
        f"{_stdout_value(report.active_review_readiness_structured_open_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_p0_source_reviewed_csv_path="
        f"{_stdout_value(report.active_review_readiness_p0_source_reviewed_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_p0_open_issue_csv_path="
        f"{_stdout_value(report.active_review_readiness_p0_open_issue_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_structured_missing_value_count="
        f"{report.active_review_readiness_structured_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_p0_missing_decision_count="
        f"{report.active_review_readiness_p0_missing_decision_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_structured_open_review_cell_count="
        f"{report.active_review_readiness_structured_open_review_cell_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_p0_open_decision_count="
        f"{report.active_review_readiness_p0_open_decision_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_p0_open_paper_count="
        f"{report.active_review_readiness_p0_open_paper_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_structured_expected_paper_reading="
        f"{report.active_review_readiness_structured_expected_paper_reading}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_p0_expected_paper_reading="
        f"{report.active_review_readiness_p0_expected_paper_reading}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_work_item_count="
        f"{report.active_review_readiness_reviewer_work_item_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_work_item_ids="
        f"{_stdout_id_list([item.item_id for item in report.active_review_readiness_reviewer_work_items])}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_work_item_ids_by_blocked_requirement="
        f"{_stdout_ids_by_kind_mapping(report.active_review_readiness_reviewer_work_item_ids_by_blocked_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_open_item_counts_by_blocked_requirement="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_item_counts_by_blocked_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_open_item_counts_by_work_item_id="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_item_counts_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_expected_paper_reading_by_work_item_id="
        f"{_stdout_string_mapping(report.active_review_readiness_reviewer_expected_paper_reading_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_primary_review_sources_by_work_item_id="
        f"{_stdout_string_mapping(report.active_review_readiness_reviewer_primary_review_sources_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_verification_command_hints_by_work_item_id="
        f"{_stdout_string_mapping(report.active_review_readiness_reviewer_verification_command_hints_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_review_readiness_brief_audit_all_passed="
        f"{report.active_review_readiness_brief_audit_all_passed}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_path="
        f"{_stdout_value(report.active_reviewer_handoff_refresh_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_brief_audit_all_passed="
        f"{report.active_reviewer_handoff_refresh_brief_audit_all_passed}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_brief_audit_pass_count="
        f"{report.active_reviewer_handoff_refresh_brief_audit_pass_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_brief_audit_fail_count="
        f"{report.active_reviewer_handoff_refresh_brief_audit_fail_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_structured_open_csv_row_count="
        f"{report.active_reviewer_handoff_refresh_structured_open_csv_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_p0_open_issue_row_count="
        f"{report.active_reviewer_handoff_refresh_p0_open_issue_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_p0_open_paper_count="
        f"{report.active_reviewer_handoff_refresh_p0_open_paper_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_ready_for_downstream_review_steps="
        f"{report.active_reviewer_handoff_refresh_ready_for_downstream_review_steps}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "active_reviewer_handoff_refresh_readiness_blocker_count="
        f"{report.active_reviewer_handoff_refresh_readiness_blocker_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "claim_evidence_eval_review_queue_records_dir="
        f"{_stdout_value(report.claim_evidence_eval_review_queue_records_dir or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "claim_evidence_eval_review_queue_records_dir_exists="
        f"{report.claim_evidence_eval_review_queue_records_dir_exists}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "claim_evidence_eval_review_queue_pending_count="
        f"{report.claim_evidence_eval_review_queue_pending_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "claim_evidence_eval_review_queue_total_count="
        f"{report.claim_evidence_eval_review_queue_total_count}"
    )
    print(f"[evidence_grounding_roadmap_completion] next_action_count={report.next_action_count}")
    print(
        "[evidence_grounding_roadmap_completion] "
        f"human_review_next_action_count={report.human_review_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"human_review_unique_next_action_count={report.human_review_unique_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"human_review_open_csv_row_count={report.human_review_open_csv_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"human_review_open_record_count={report.human_review_open_record_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_paths="
        f"{','.join(_stdout_value(path) for path in report.human_review_open_csv_paths) or '-'}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_csv_paths="
        f"{','.join(_stdout_value(path) for path in report.human_review_open_record_csv_paths) or '-'}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_path_counts_by_requirement="
        f"{_stdout_path_count_mapping(report.human_review_open_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_csv_path_counts_by_requirement="
        f"{_stdout_path_count_mapping(report.human_review_open_record_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_record_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_row_counts_by_requirement="
        f"{_stdout_count_mapping(report.human_review_open_csv_row_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_counts_by_requirement="
        f"{_stdout_count_mapping(report.human_review_open_record_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_refs_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_record_refs_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_field_names_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_field_names_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_field_names_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_field_names_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_task_ids_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_task_ids_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_value_count="
        f"{report.human_review_open_csv_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_missing_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_value_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_missing_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_suggestion_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_missing_suggestion_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_suggestion_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_missing_suggestion_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_suggestion_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_missing_suggestion_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_suggestion_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_missing_suggestion_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_suggested_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_suggested_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_suggested_value_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_suggested_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_filled_patch_field_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_record_filled_patch_field_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_filled_patch_field_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_record_filled_patch_field_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_record_filled_patch_fields_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_record_filled_patch_fields_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_reviewer_value_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(_reviewer_value_hint_counts_by_requirement(missing_value_counts=report.human_review_open_csv_missing_value_counts_by_requirement, missing_suggestion_counts=report.human_review_open_csv_missing_suggestion_counts_by_requirement))}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_reviewer_value_hint_counts_by_field="
        f"{_stdout_count_mapping(_reviewer_value_hint_counts_by_field(missing_value_counts=report.human_review_open_csv_missing_value_counts_by_field, missing_suggestion_counts=report.human_review_open_csv_missing_suggestion_counts_by_field))}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_reviewer_evidence_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_reviewer_evidence_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_reviewer_evidence_hint_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_reviewer_evidence_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_available_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_available_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_available_context_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_available_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_missing_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_context_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_missing_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_context_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_missing_context_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_missing_context_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_missing_context_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_available_context_keys_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_available_context_keys_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_available_context_keys_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_available_context_keys_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_available_context_values_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_available_context_values_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_csv_available_context_values_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_available_context_values_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "human_review_open_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_task_ids_by_field)}"
    )
    phase_counts = ",".join(
        f"{phase}:{count}" for phase, count in sorted(report.next_action_phase_counts.items())
    )
    print(f"[evidence_grounding_roadmap_completion] next_action_phase_counts={phase_counts or '-'}")
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_counts_by_requirement="
        f"{_stdout_count_mapping(report.next_action_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_unresolved_command_placeholders_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_unresolved_command_placeholders_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_unresolved_command_placeholder_counts_by_requirement="
        f"{_stdout_count_mapping(report.next_action_unresolved_command_placeholder_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_unresolved_command_placeholder_counts_by_placeholder="
        f"{_stdout_count_mapping(report.next_action_unresolved_command_placeholder_counts_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_kind_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.next_action_kind_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocked_by_requirement_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_blocked_by_requirement_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocked_by_requirement_counts="
        f"{_stdout_count_mapping(report.next_action_blocked_by_requirement_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocked_by_requirement_unique_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_blocked_by_requirement_unique_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocked_by_requirement_unique_counts="
        f"{_stdout_count_mapping(report.next_action_blocked_by_requirement_unique_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocker_reasons_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_blocker_reasons_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocker_reason_counts="
        f"{_stdout_count_mapping(report.next_action_blocker_reason_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocker_reason_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.next_action_blocker_reason_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "next_action_blocker_reason_counts_by_phase="
        f"{_stdout_nested_count_mapping(report.next_action_blocker_reason_counts_by_phase)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"next_action_ids_by_phase={_stdout_ids_by_kind_mapping(report.next_action_ids_by_phase)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"next_action_ids_by_kind={_stdout_ids_by_kind_mapping(report.next_action_ids_by_kind)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"next_action_kind_counts={_stdout_count_mapping(report.next_action_kind_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"frontier_next_action_count={report.frontier_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"frontier_human_review_next_action_count={report.frontier_human_review_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"frontier_ready_to_run_next_action_count={report.frontier_ready_to_run_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_placeholder_command_next_action_count="
        f"{report.frontier_placeholder_command_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_next_action_ids_by_kind="
        f"{_stdout_ids_by_kind_mapping(report.frontier_next_action_ids_by_kind)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_next_action_count="
        f"{report.frontier_unblocked_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_next_action_ids_by_kind="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_next_action_ids_by_kind)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_action_text_by_requirement="
        f"{_stdout_string_mapping(report.frontier_action_text_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_command_hints_by_requirement="
        f"{_stdout_string_mapping(report.frontier_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_next_action_summaries="
        f"{_stdout_frontier_summary_mapping(report.frontier_next_action_summaries)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unresolved_command_placeholder_count="
        f"{report.frontier_unresolved_command_placeholder_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unresolved_command_placeholders_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unresolved_command_placeholders_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unresolved_command_placeholder_counts_by_placeholder="
        f"{_stdout_count_mapping(report.frontier_unresolved_command_placeholder_counts_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"frontier_missing_metric_input_count={report.frontier_missing_metric_input_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_missing_metric_inputs_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_missing_metric_inputs_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_missing_metric_input_counts_by_metric="
        f"{_stdout_count_mapping(report.frontier_missing_metric_input_counts_by_metric)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_row_counts_by_requirement="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_row_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_field_names_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_field_names_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_value_count="
        f"{report.frontier_human_review_open_csv_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_value_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_missing_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_suggestion_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_suggestion_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_missing_suggestion_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_suggestion_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_missing_suggestion_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_suggested_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_suggested_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_suggested_value_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_suggested_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_record_filled_patch_field_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_record_filled_patch_field_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_record_filled_patch_field_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_record_filled_patch_field_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_record_filled_patch_fields_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_record_filled_patch_fields_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_reviewer_value_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(_reviewer_value_hint_counts_by_requirement(missing_value_counts=report.frontier_human_review_open_csv_missing_value_counts_by_requirement, missing_suggestion_counts=report.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement))}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_reviewer_value_hint_counts_by_field="
        f"{_stdout_count_mapping(_reviewer_value_hint_counts_by_field(missing_value_counts=report.frontier_human_review_open_csv_missing_value_counts_by_field, missing_suggestion_counts=report.frontier_human_review_open_csv_missing_suggestion_counts_by_field))}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_available_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_available_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_available_context_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_available_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_context_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_missing_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_context_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_missing_context_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_missing_context_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_missing_context_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_available_context_keys_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_available_context_keys_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_available_context_keys_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_available_context_keys_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_available_context_values_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_available_context_values_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_csv_available_context_values_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_available_context_values_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_open_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_manifest_path="
        f"{_stdout_value(report.frontier_human_review_queue_split_manifest_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_source_csv_count="
        f"{report.frontier_human_review_queue_split_source_csv_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_review_row_count="
        f"{report.frontier_human_review_queue_split_merged_review_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_reviewed_value_count="
        f"{report.frontier_human_review_queue_split_merged_reviewed_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_missing_value_count="
        f"{report.frontier_human_review_queue_split_merged_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_reviewed_evidence_count="
        f"{report.frontier_human_review_queue_split_merged_reviewed_evidence_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_missing_evidence_count="
        f"{report.frontier_human_review_queue_split_merged_missing_evidence_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_reviewer_value_hint_count="
        f"{report.frontier_human_review_queue_split_reviewer_value_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_reviewer_evidence_hint_count="
        f"{report.frontier_human_review_queue_split_reviewer_evidence_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_reviewer_value_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_reviewer_value_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_with_hint_count="
        f"{report.frontier_human_review_queue_split_missing_value_with_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_without_hint_count="
        f"{report.frontier_human_review_queue_split_missing_value_without_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_with_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_missing_value_with_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_without_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_missing_value_without_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_ready_source_count="
        f"{report.frontier_human_review_queue_split_ready_source_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_blocked_source_count="
        f"{report.frontier_human_review_queue_split_blocked_source_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_ready_reviewed_csv_paths="
        f"{_stdout_id_list(report.frontier_human_review_queue_split_ready_reviewed_csv_paths)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_blocked_reviewed_csv_paths="
        f"{_stdout_id_list(report.frontier_human_review_queue_split_blocked_reviewed_csv_paths)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_ready_fill_review_audit_command_hints="
        f"{_stdout_id_list(report.frontier_human_review_queue_split_ready_fill_review_audit_command_hints)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_blocked_fill_review_audit_command_hints="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_blocked_fill_review_audit_command_hints)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_blocked_fill_task_apply_command_hints="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_blocked_fill_task_apply_command_hints)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_reviewer_value_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_reviewer_value_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_with_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_value_with_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_without_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_value_without_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement="
        f"{_stdout_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement="
        f"{_stdout_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_blocker_reasons_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_blocker_reasons_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_blocker_reason_counts="
        f"{_stdout_count_mapping(report.frontier_blocker_reason_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_blocked_by_requirement_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_blocked_by_requirement_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_blocked_by_requirement_counts="
        f"{_stdout_count_mapping(report.frontier_blocked_by_requirement_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_blocked_by_requirement_unique_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_blocked_by_requirement_unique_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "frontier_blocked_by_requirement_unique_counts="
        f"{_stdout_count_mapping(report.frontier_blocked_by_requirement_unique_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"ready_to_run_next_action_count={report.ready_to_run_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"ready_to_run_unique_next_action_count={report.ready_to_run_unique_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"placeholder_command_next_action_count={report.placeholder_command_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"placeholder_command_unique_next_action_count={report.placeholder_command_unique_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"prerequisite_gated_next_action_count={report.prerequisite_gated_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "prerequisite_gated_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.prerequisite_gated_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "prerequisite_gated_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.prerequisite_gated_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"placeholder_command_next_action_ids={','.join(report.placeholder_command_next_action_ids) or '-'}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "placeholder_command_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.placeholder_command_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "placeholder_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.placeholder_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "placeholder_command_unresolved_placeholders_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.placeholder_command_unresolved_placeholders_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "placeholder_command_unresolved_placeholder_counts_by_requirement="
        f"{_stdout_count_mapping(report.placeholder_command_unresolved_placeholder_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "placeholder_command_unresolved_placeholder_counts_by_placeholder="
        f"{_stdout_count_mapping(report.placeholder_command_unresolved_placeholder_counts_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        "placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder="
        f"{_stdout_string_mapping(report.placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"blocked_without_next_action_count={report.blocked_without_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion] "
        f"blocked_without_next_action_ids={','.join(report.blocked_without_next_action_ids) or '-'}"
    )
    print(f"[evidence_grounding_roadmap_completion] out={_stdout_value(Path(args.out).expanduser().resolve())}")
    if args.print_action_queue_counts or args.print_all_action_queues:
        _print_action_queue_counts(report, prefix="evidence_grounding_roadmap_completion")
    if args.print_blocker_summary:
        _print_blocker_summary(report, prefix="evidence_grounding_roadmap_completion")
    if args.print_placeholder_summary:
        _print_placeholder_summary(report, prefix="evidence_grounding_roadmap_completion")
    if args.print_frontier_actions:
        frontier_action_limit = max(0, args.frontier_action_limit)
        actions = report.frontier_next_actions[:frontier_action_limit] if frontier_action_limit else report.frontier_next_actions
        omitted_count = max(0, len(report.frontier_next_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_action_total_count={len(report.frontier_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"frontier_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            human_review = f" requires_human_review={item.requires_human_review}"
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion] "
                f"frontier_action.{index} requirement_id={item.requirement_id}{phase}{human_review}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
    if args.print_unblocked_frontier_actions:
        frontier_action_limit = max(0, args.frontier_action_limit)
        unblocked_frontier_actions = [
            action for action in report.frontier_next_actions if not action.blocked_by_requirement_ids
        ]
        actions = (
            unblocked_frontier_actions[:frontier_action_limit]
            if frontier_action_limit
            else unblocked_frontier_actions
        )
        omitted_count = max(0, len(unblocked_frontier_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion] "
            f"unblocked_frontier_action_total_count={len(unblocked_frontier_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"unblocked_frontier_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"unblocked_frontier_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            human_review = f" requires_human_review={item.requires_human_review}"
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion] "
                f"unblocked_frontier_action.{index} requirement_id={item.requirement_id}{phase}{human_review}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
    if args.print_next_actions or args.print_all_action_queues:
        action_limit = max(0, args.next_action_limit)
        actions = report.next_actions[:action_limit] if action_limit else report.next_actions
        omitted_count = max(0, len(report.next_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion] "
            f"next_action_total_count={len(report.next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"next_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"next_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            human_review = f" requires_human_review={item.requires_human_review}"
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion] "
                f"next_action.{index} requirement_id={item.requirement_id}{phase}{human_review}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
        for evidence_key, output_key in (
            ("source_record_count", "structured_correction_source_record_count"),
            ("source_valid_record_count", "structured_correction_source_valid_record_count"),
            ("replayable_candidate_count", "structured_correction_replayable_candidate_count"),
            (
                "source_nonreplayable_valid_record_count",
                "structured_correction_source_nonreplayable_valid_record_count",
            ),
            ("source_invalid_record_count", "structured_correction_source_invalid_record_count"),
            ("repair_target_count", "structured_correction_repair_target_count"),
            ("source_reason_code_counts", "structured_correction_source_reason_code_counts"),
        ):
            value = _check_evidence_value(report, "structured_correction_log", evidence_key)
            if value:
                print(f"[evidence_grounding_roadmap_completion] {output_key}={_stdout_value(value)}")
        correction_repair_targets = _check_evidence_value(
            report,
            "structured_correction_log",
            "source_invalid_record_repair_targets",
        )
        if correction_repair_targets:
            print(
                "[evidence_grounding_roadmap_completion] "
                f"structured_correction_repair_targets={_stdout_value(correction_repair_targets)}"
            )
        correction_missing_replay_fields = _check_evidence_value(
            report,
            "structured_correction_log",
            "source_invalid_record_missing_replay_fields",
        )
        if correction_missing_replay_fields:
            print(
                "[evidence_grounding_roadmap_completion] "
                f"structured_correction_missing_replay_fields={_stdout_value(correction_missing_replay_fields)}"
            )
        correction_available_replay_context = _check_evidence_value(
            report,
            "structured_correction_log",
            "source_invalid_record_available_replay_context",
        )
        if correction_available_replay_context:
            print(
                "[evidence_grounding_roadmap_completion] "
                "structured_correction_available_replay_context="
                f"{_stdout_value(correction_available_replay_context)}"
            )
        correction_invalid_details = _check_evidence_value(
            report,
            "structured_correction_log",
            "source_invalid_record_details",
        )
        if correction_invalid_details:
            print(
                "[evidence_grounding_roadmap_completion] "
                f"structured_correction_invalid_details={_stdout_value(correction_invalid_details)}"
            )
        _print_p0_metric_diagnostics(report, prefix="evidence_grounding_roadmap_completion")
        _print_threshold_package_diagnostics(report, prefix="evidence_grounding_roadmap_completion")
        _print_fill_review_suggestion_diagnostics(
            report,
            prefix="evidence_grounding_roadmap_completion",
        )
        handoff_template_path_count = _check_evidence_value(
            report,
            "workspace_evidence_inventory_ready",
            "gold_reviewer_handoff_patch_template_path_count",
        )
        if handoff_template_path_count:
            print(
                "[evidence_grounding_roadmap_completion] "
                f"gold_reviewer_handoff_patch_template_path_count={handoff_template_path_count}"
            )
        handoff_template_paths = _check_evidence_value(
            report,
            "workspace_evidence_inventory_ready",
            "gold_reviewer_handoff_patch_template_paths_sample",
        )
        if handoff_template_paths:
            print(
                "[evidence_grounding_roadmap_completion] "
                f"gold_reviewer_handoff_patch_template_paths_sample={_stdout_value(handoff_template_paths)}"
            )
    if args.print_human_review_actions or args.print_all_action_queues:
        human_review_action_limit = max(0, args.human_review_action_limit)
        actions = (
            report.human_review_unique_next_actions[:human_review_action_limit]
            if human_review_action_limit
            else report.human_review_unique_next_actions
        )
        omitted_count = max(0, len(report.human_review_unique_next_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion] "
            f"human_review_action_total_count={len(report.human_review_unique_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"human_review_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"human_review_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion] "
                f"human_review_action.{index} requirement_id={item.requirement_id}{phase}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
    if args.print_ready_to_run_actions or args.print_all_action_queues:
        unique_action_limit = max(0, args.unique_action_limit)
        actions = (
            report.ready_to_run_unique_next_actions[:unique_action_limit]
            if unique_action_limit
            else report.ready_to_run_unique_next_actions
        )
        omitted_count = max(0, len(report.ready_to_run_unique_next_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion] "
            f"ready_to_run_action_total_count={len(report.ready_to_run_unique_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"ready_to_run_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"ready_to_run_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion] "
                f"ready_to_run_action.{index} requirement_id={item.requirement_id}{phase}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
    if args.print_placeholder_command_actions or args.print_all_action_queues:
        unique_action_limit = max(0, args.unique_action_limit)
        actions = (
            report.placeholder_command_unique_next_actions[:unique_action_limit]
            if unique_action_limit
            else report.placeholder_command_unique_next_actions
        )
        omitted_count = max(0, len(report.placeholder_command_unique_next_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion] "
            f"placeholder_command_action_total_count={len(report.placeholder_command_unique_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"placeholder_command_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion] "
            f"placeholder_command_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion] "
                f"placeholder_command_action.{index} requirement_id={item.requirement_id}{phase}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
    return 0 if report.roadmap_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
