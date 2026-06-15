#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.evidence_grounding_benchmark import (
    build_evidence_grounding_roadmap_completion_audit_report_from_comparison_suite_package,
)
from src.services.path_masking import mask_local_paths_in_text
from src.schemas.paper_understanding_gold import PaperUnderstandingGoldReleaseManifestBuildItem


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
        ("roadmap_blocker_count", len(report.blockers)),
        ("roadmap_blocker_ids", _stdout_id_list(report.blockers)),
        ("roadmap_blocker_reason_counts", _stdout_count_mapping(report.frontier_blocker_reason_counts)),
        (
            "roadmap_blocker_next_action_kind_counts_by_requirement",
            _stdout_nested_count_mapping(report.next_action_kind_counts_by_requirement),
        ),
        (
            "roadmap_blocker_next_action_kind_counts",
            _stdout_count_mapping(report.next_action_kind_counts),
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
            _stdout_nested_ids_mapping(report.frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement),
        ),
        (
            "roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_field",
            _stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_missing_suggestion_task_ids_by_field),
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
        ("roadmap_blocker_ready_to_run_unique_next_action_count", report.ready_to_run_unique_next_action_count),
        (
            "roadmap_blocker_placeholder_command_unique_next_action_count",
            report.placeholder_command_unique_next_action_count,
        ),
        (
            "roadmap_blocker_prerequisite_gated_next_action_count",
            report.prerequisite_gated_next_action_count,
        ),
        ("roadmap_blocker_blocked_without_next_action_count", report.blocked_without_next_action_count),
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


def _print_structured_correction_diagnostics(report, *, prefix: str) -> None:
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
        ("source_invalid_record_repair_targets", "structured_correction_repair_targets"),
        ("source_invalid_record_missing_replay_fields", "structured_correction_missing_replay_fields"),
        (
            "source_invalid_record_available_replay_context",
            "structured_correction_available_replay_context",
        ),
        ("source_invalid_record_details", "structured_correction_invalid_details"),
    ):
        value = _check_evidence_value(report, "structured_correction_log", evidence_key)
        if value:
            print(f"[{prefix}] {output_key}={_stdout_value(value)}")


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
    fallback_by_suffix = {
        "fill_review_missing_suggestion_count_by_field": report.human_review_open_csv_missing_suggestion_counts_by_requirement,
        "fill_review_available_context_count_by_field": report.human_review_open_csv_available_context_counts_by_requirement,
        "fill_review_available_context_keys_by_field": report.human_review_open_csv_available_context_keys_by_requirement,
        "fill_review_available_context_values_by_field": report.human_review_open_csv_available_context_values_by_requirement,
        "fill_review_missing_context_count_by_field": report.human_review_open_csv_missing_context_counts_by_requirement,
    }
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
                continue
            if output_suffix in fallback_by_suffix:
                fallback_value = fallback_by_suffix[output_suffix].get(requirement_id, {})
                if isinstance(fallback_value, dict):
                    if all(isinstance(item, int) for item in fallback_value.values()):
                        value_text = _stdout_count_mapping(fallback_value)
                    else:
                        value_text = _stdout_ids_by_kind_mapping(fallback_value)
                else:
                    value_text = _stdout_value(fallback_value)
                print(f"[{prefix}] {output_prefix}_{output_suffix}={value_text}")


def _print_handoff_template_paths(report, *, prefix: str) -> None:
    count = _check_evidence_value(
        report,
        "workspace_evidence_inventory_ready",
        "gold_reviewer_handoff_patch_template_path_count",
    )
    if count:
        print(f"[{prefix}] gold_reviewer_handoff_patch_template_path_count={count}")
    value = _check_evidence_value(
        report,
        "workspace_evidence_inventory_ready",
        "gold_reviewer_handoff_patch_template_paths_sample",
    )
    if value:
        print(f"[{prefix}] gold_reviewer_handoff_patch_template_paths_sample={_stdout_value(value)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build threshold adoption, contract readiness, and final roadmap completion audit artifacts "
            "from one fixed-goldset comparison suite. All outputs remain non-canonical review artifacts."
        )
    )
    parser.add_argument("--comparison-suite", required=True)
    parser.add_argument("--threshold-calibration-out", required=True)
    parser.add_argument("--threshold-checked-comparison-out", required=True)
    parser.add_argument("--threshold-adoption-out", required=True)
    parser.add_argument("--contract-compatibility-out", required=True)
    parser.add_argument("--contract-readiness-out", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--audit-id", default="evidence-grounding-roadmap-completion-audit")
    parser.add_argument("--calibration-id", default="evidence-grounding-threshold-calibration")
    parser.add_argument("--adoption-id", default="evidence-grounding-threshold-adoption-review")
    parser.add_argument("--calibration-metric", action="append", default=None)
    parser.add_argument("--calibration-metric-preset", choices=("p0-gold", "explicit"), default="p0-gold")
    parser.add_argument("--include-baseline-report", action="store_true")
    parser.add_argument("--exclude-candidate-report", action="store_true")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--gate-metric", action="append", default=None)
    parser.add_argument("--gate-preset", choices=("all-comparable", "p0-gold"), default="p0-gold")
    parser.add_argument("--threshold-metric", action="append", default=None, metavar="NAME=VALUE")
    parser.add_argument("--required-metric", action="append", default=None)
    parser.add_argument("--threshold-reviewer-approval-reference")
    parser.add_argument("--allow-production-threshold-ready", action="store_true")
    parser.add_argument("--compatibility-id", default="evidence-grounding-contract-compatibility")
    parser.add_argument("--readiness-id", default="evidence-grounding-contract-readiness")
    parser.add_argument("--skip-embedded-scorecards", action="store_true")
    parser.add_argument("--migration-plan")
    parser.add_argument("--backfill-plan")
    parser.add_argument("--public-contract-doc")
    parser.add_argument("--contract-reviewer-approval-reference")
    parser.add_argument("--allow-external-contract-ready", action="store_true")
    parser.add_argument(
        "--additional-artifact",
        action="append",
        default=None,
        help=(
            "Additional review/contract artifact to include in generated contract compatibility "
            "and roadmap completion, for example p0_overstatement_review_packet.json or "
            "p0_overstatement_review_summary.json, active_review_readiness.json, or "
            "active_reviewer_handoff_refresh.json. May be repeated."
        ),
    )
    parser.add_argument("--gold-release-goldset-id")
    parser.add_argument("--gold-release-split-plan")
    parser.add_argument(
        "--gold-release-staged-split-manifest",
        action="append",
        default=None,
        help="Staged split build spec as split=NAME,staging=PATH,out=PATH. May be repeated for seed/eval/holdout.",
    )
    parser.add_argument("--gold-release-package-out")
    parser.add_argument("--gold-release-package")
    parser.add_argument("--gold-release-readiness-report")
    parser.add_argument("--gold-release-readiness-out")
    parser.add_argument("--gold-release-manifest", action="append", default=None)
    parser.add_argument("--gold-release-required-split", action="append", default=None)
    parser.add_argument("--gold-release-min-ready-per-split", type=int, default=1)
    parser.add_argument("--gold-release-allow-multiple-goldset-ids", action="store_true")
    parser.add_argument(
        "--correction-log",
        help=(
            "Claim/evidence correction evidence path: raw ClaimEvidenceCorrectionCase JSONL "
            "or claim_evidence_eval_candidate_export.v1 JSON review artifact"
        ),
    )
    parser.add_argument("--goldset-root")
    parser.add_argument("--run-root")
    parser.add_argument("--required-ready-gold-count", type=int, default=1)
    parser.add_argument("--required-ready-run-count", type=int, default=1)
    parser.add_argument("--inventory-required-artifact", action="append", dest="inventory_required_artifacts")
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
    include_candidate_report = not args.exclude_candidate_report
    if not args.include_baseline_report and not include_candidate_report:
        parser.error("at least one suite benchmark report must be selected for calibration")

    report = build_evidence_grounding_roadmap_completion_audit_report_from_comparison_suite_package(
        comparison_suite_path=Path(args.comparison_suite),
        threshold_calibration_report_out=Path(args.threshold_calibration_out),
        threshold_checked_comparison_report_out=Path(args.threshold_checked_comparison_out),
        threshold_adoption_review_out=Path(args.threshold_adoption_out),
        contract_compatibility_report_out=Path(args.contract_compatibility_out),
        contract_readiness_report_out=Path(args.contract_readiness_out),
        out=Path(args.out).expanduser().resolve(),
        audit_id=args.audit_id,
        calibration_id=args.calibration_id,
        calibration_metric_names=args.calibration_metric,
        calibration_metric_preset=args.calibration_metric_preset.replace("-", "_"),
        include_baseline_report=args.include_baseline_report,
        include_candidate_report=include_candidate_report,
        tolerance=args.tolerance,
        gate_metric_names=args.gate_metric,
        gate_preset=args.gate_preset.replace("-", "_"),
        threshold_metric_values=_parse_threshold_metrics(args.threshold_metric),
        adoption_id=args.adoption_id,
        required_metric_names=args.required_metric,
        threshold_reviewer_approval_reference=args.threshold_reviewer_approval_reference,
        allow_production_threshold_ready=args.allow_production_threshold_ready,
        compatibility_id=args.compatibility_id,
        readiness_id=args.readiness_id,
        include_embedded_scorecards=not args.skip_embedded_scorecards,
        migration_plan_path=Path(args.migration_plan) if args.migration_plan else None,
        backfill_plan_path=Path(args.backfill_plan) if args.backfill_plan else None,
        public_contract_doc_path=Path(args.public_contract_doc) if args.public_contract_doc else None,
        contract_reviewer_approval_reference=args.contract_reviewer_approval_reference,
        allow_external_contract_ready=args.allow_external_contract_ready,
        additional_artifact_paths=(
            [Path(path).expanduser().resolve() for path in args.additional_artifact]
            if args.additional_artifact
            else None
        ),
        gold_release_goldset_id=args.gold_release_goldset_id,
        gold_release_staged_split_manifests=(
            [_parse_gold_release_staged_split_manifest(raw) for raw in args.gold_release_staged_split_manifest]
            if args.gold_release_staged_split_manifest
            else None
        ),
        gold_release_split_plan_path=Path(args.gold_release_split_plan) if args.gold_release_split_plan else None,
        gold_release_package_out=Path(args.gold_release_package_out) if args.gold_release_package_out else None,
        gold_release_package_path=Path(args.gold_release_package) if args.gold_release_package else None,
        gold_release_manifest_paths=[Path(path) for path in args.gold_release_manifest] if args.gold_release_manifest else None,
        gold_release_readiness_report_out=(
            Path(args.gold_release_readiness_out) if args.gold_release_readiness_out else None
        ),
        gold_release_readiness_report_path=(
            Path(args.gold_release_readiness_report) if args.gold_release_readiness_report else None
        ),
        gold_release_required_splits=args.gold_release_required_split,
        gold_release_min_ready_per_split=args.gold_release_min_ready_per_split,
        gold_release_require_single_goldset_id=not args.gold_release_allow_multiple_goldset_ids,
        correction_log_path=Path(args.correction_log) if args.correction_log else None,
        goldset_root=Path(args.goldset_root) if args.goldset_root else None,
        run_root=Path(args.run_root) if args.run_root else None,
        required_ready_gold_count=args.required_ready_gold_count,
        required_ready_run_count=args.required_ready_run_count,
        inventory_required_artifacts=args.inventory_required_artifacts,
    )
    queue_csv_out = None
    if args.frontier_human_review_queue_csv_out:
        queue_csv_out = Path(args.frontier_human_review_queue_csv_out).expanduser().resolve()
        queue_row_count = _write_frontier_human_review_queue_csv(report, queue_csv_out)
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"frontier_human_review_queue_csv={_stdout_value(queue_csv_out)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"frontier_human_review_queue_row_count={queue_row_count}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
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
            "[evidence_grounding_roadmap_completion_package] "
            f"frontier_human_review_queue_guide={_stdout_value(queue_guide_out)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"frontier_human_review_queue_guide_requirement_count={guide_requirement_count}"
        )
    print(f"[evidence_grounding_roadmap_completion_package] audit_id={report.audit_id}")
    print(f"[evidence_grounding_roadmap_completion_package] pass_count={report.pass_count}")
    print(f"[evidence_grounding_roadmap_completion_package] fail_count={report.fail_count}")
    print(f"[evidence_grounding_roadmap_completion_package] roadmap_complete={report.roadmap_complete}")
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"additional_artifact_count={report.additional_artifact_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"additional_artifact_paths={_stdout_id_list(report.additional_artifact_paths)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"active_review_readiness_path={_stdout_value(report.active_review_readiness_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_ready_for_downstream_review_steps="
        f"{report.active_review_readiness_ready_for_downstream_review_steps}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"active_review_readiness_blocker_count={report.active_review_readiness_blocker_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_structured_reviewed_csv_path="
        f"{_stdout_value(report.active_review_readiness_structured_reviewed_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_structured_open_csv_path="
        f"{_stdout_value(report.active_review_readiness_structured_open_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_p0_source_reviewed_csv_path="
        f"{_stdout_value(report.active_review_readiness_p0_source_reviewed_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_p0_open_issue_csv_path="
        f"{_stdout_value(report.active_review_readiness_p0_open_issue_csv_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_structured_missing_value_count="
        f"{report.active_review_readiness_structured_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_p0_missing_decision_count="
        f"{report.active_review_readiness_p0_missing_decision_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_structured_open_review_cell_count="
        f"{report.active_review_readiness_structured_open_review_cell_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_p0_open_decision_count="
        f"{report.active_review_readiness_p0_open_decision_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_p0_open_paper_count="
        f"{report.active_review_readiness_p0_open_paper_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_structured_expected_paper_reading="
        f"{report.active_review_readiness_structured_expected_paper_reading}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_p0_expected_paper_reading="
        f"{report.active_review_readiness_p0_expected_paper_reading}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_work_item_count="
        f"{report.active_review_readiness_reviewer_work_item_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_work_item_ids="
        f"{_stdout_id_list([item.item_id for item in report.active_review_readiness_reviewer_work_items])}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_work_item_ids_by_blocked_requirement="
        f"{_stdout_ids_by_kind_mapping(report.active_review_readiness_reviewer_work_item_ids_by_blocked_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_open_item_counts_by_blocked_requirement="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_item_counts_by_blocked_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_open_item_counts_by_work_item_id="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_item_counts_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_expected_paper_reading_by_work_item_id="
        f"{_stdout_string_mapping(report.active_review_readiness_reviewer_expected_paper_reading_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_primary_review_sources_by_work_item_id="
        f"{_stdout_string_mapping(report.active_review_readiness_reviewer_primary_review_sources_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_verification_command_hints_by_work_item_id="
        f"{_stdout_string_mapping(report.active_review_readiness_reviewer_verification_command_hints_by_work_item_id)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading="
        f"{_stdout_count_mapping(report.active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_review_readiness_brief_audit_all_passed="
        f"{report.active_review_readiness_brief_audit_all_passed}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_path="
        f"{_stdout_value(report.active_reviewer_handoff_refresh_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_brief_audit_all_passed="
        f"{report.active_reviewer_handoff_refresh_brief_audit_all_passed}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_brief_audit_pass_count="
        f"{report.active_reviewer_handoff_refresh_brief_audit_pass_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_brief_audit_fail_count="
        f"{report.active_reviewer_handoff_refresh_brief_audit_fail_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_structured_open_csv_row_count="
        f"{report.active_reviewer_handoff_refresh_structured_open_csv_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_p0_open_issue_row_count="
        f"{report.active_reviewer_handoff_refresh_p0_open_issue_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_p0_open_paper_count="
        f"{report.active_reviewer_handoff_refresh_p0_open_paper_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_ready_for_downstream_review_steps="
        f"{report.active_reviewer_handoff_refresh_ready_for_downstream_review_steps}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "active_reviewer_handoff_refresh_readiness_blocker_count="
        f"{report.active_reviewer_handoff_refresh_readiness_blocker_count}"
    )
    print(f"[evidence_grounding_roadmap_completion_package] next_action_count={report.next_action_count}")
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"human_review_next_action_count={report.human_review_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"human_review_unique_next_action_count={report.human_review_unique_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"human_review_open_csv_row_count={report.human_review_open_csv_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"human_review_open_record_count={report.human_review_open_record_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_paths="
        f"{','.join(_stdout_value(path) for path in report.human_review_open_csv_paths) or '-'}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_csv_paths="
        f"{','.join(_stdout_value(path) for path in report.human_review_open_record_csv_paths) or '-'}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_path_counts_by_requirement="
        f"{_stdout_path_count_mapping(report.human_review_open_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_csv_path_counts_by_requirement="
        f"{_stdout_path_count_mapping(report.human_review_open_record_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_record_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_row_counts_by_requirement="
        f"{_stdout_count_mapping(report.human_review_open_csv_row_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_counts_by_requirement="
        f"{_stdout_count_mapping(report.human_review_open_record_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_refs_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_record_refs_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_field_names_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_field_names_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_field_names_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_field_names_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_task_ids_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_task_ids_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_value_count="
        f"{report.human_review_open_csv_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_missing_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_value_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_missing_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_suggestion_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_missing_suggestion_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_suggestion_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_missing_suggestion_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_suggestion_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_missing_suggestion_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_suggestion_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_missing_suggestion_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_suggested_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_suggested_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_suggested_value_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_suggested_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_filled_patch_field_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_record_filled_patch_field_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_filled_patch_field_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_record_filled_patch_field_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_record_filled_patch_fields_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_record_filled_patch_fields_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_reviewer_value_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(_reviewer_value_hint_counts_by_requirement(missing_value_counts=report.human_review_open_csv_missing_value_counts_by_requirement, missing_suggestion_counts=report.human_review_open_csv_missing_suggestion_counts_by_requirement))}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_reviewer_value_hint_counts_by_field="
        f"{_stdout_count_mapping(_reviewer_value_hint_counts_by_field(missing_value_counts=report.human_review_open_csv_missing_value_counts_by_field, missing_suggestion_counts=report.human_review_open_csv_missing_suggestion_counts_by_field))}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_reviewer_evidence_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_reviewer_evidence_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_reviewer_evidence_hint_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_reviewer_evidence_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_available_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_available_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_available_context_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_available_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.human_review_open_csv_missing_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_context_counts_by_field="
        f"{_stdout_count_mapping(report.human_review_open_csv_missing_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_context_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_missing_context_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_missing_context_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_missing_context_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_available_context_keys_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_available_context_keys_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_available_context_keys_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_available_context_keys_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_available_context_values_by_requirement="
        f"{_stdout_nested_ids_mapping(report.human_review_open_csv_available_context_values_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_csv_available_context_values_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_csv_available_context_values_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "human_review_open_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.human_review_open_task_ids_by_field)}"
    )
    phase_counts = ",".join(
        f"{phase}:{count}" for phase, count in sorted(report.next_action_phase_counts.items())
    )
    print(f"[evidence_grounding_roadmap_completion_package] next_action_phase_counts={phase_counts or '-'}")
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_counts_by_requirement="
        f"{_stdout_count_mapping(report.next_action_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_unresolved_command_placeholders_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_unresolved_command_placeholders_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_unresolved_command_placeholder_counts_by_requirement="
        f"{_stdout_count_mapping(report.next_action_unresolved_command_placeholder_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_unresolved_command_placeholder_counts_by_placeholder="
        f"{_stdout_count_mapping(report.next_action_unresolved_command_placeholder_counts_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_kind_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.next_action_kind_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocked_by_requirement_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_blocked_by_requirement_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocked_by_requirement_counts="
        f"{_stdout_count_mapping(report.next_action_blocked_by_requirement_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocked_by_requirement_unique_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_blocked_by_requirement_unique_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocked_by_requirement_unique_counts="
        f"{_stdout_count_mapping(report.next_action_blocked_by_requirement_unique_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocker_reasons_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.next_action_blocker_reasons_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocker_reason_counts="
        f"{_stdout_count_mapping(report.next_action_blocker_reason_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocker_reason_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.next_action_blocker_reason_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "next_action_blocker_reason_counts_by_phase="
        f"{_stdout_nested_count_mapping(report.next_action_blocker_reason_counts_by_phase)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"next_action_ids_by_phase={_stdout_ids_by_kind_mapping(report.next_action_ids_by_phase)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"next_action_ids_by_kind={_stdout_ids_by_kind_mapping(report.next_action_ids_by_kind)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"next_action_kind_counts={_stdout_count_mapping(report.next_action_kind_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"frontier_next_action_count={report.frontier_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"frontier_human_review_next_action_count={report.frontier_human_review_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"frontier_ready_to_run_next_action_count={report.frontier_ready_to_run_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_placeholder_command_next_action_count="
        f"{report.frontier_placeholder_command_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_next_action_ids_by_kind="
        f"{_stdout_ids_by_kind_mapping(report.frontier_next_action_ids_by_kind)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_next_action_count="
        f"{report.frontier_unblocked_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_next_action_ids_by_kind="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_next_action_ids_by_kind)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_action_text_by_requirement="
        f"{_stdout_string_mapping(report.frontier_action_text_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_command_hints_by_requirement="
        f"{_stdout_string_mapping(report.frontier_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_next_action_summaries="
        f"{_stdout_frontier_summary_mapping(report.frontier_next_action_summaries)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unresolved_command_placeholder_count="
        f"{report.frontier_unresolved_command_placeholder_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unresolved_command_placeholders_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unresolved_command_placeholders_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unresolved_command_placeholder_counts_by_placeholder="
        f"{_stdout_count_mapping(report.frontier_unresolved_command_placeholder_counts_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"frontier_missing_metric_input_count={report.frontier_missing_metric_input_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_missing_metric_inputs_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_missing_metric_inputs_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_missing_metric_input_counts_by_metric="
        f"{_stdout_count_mapping(report.frontier_missing_metric_input_counts_by_metric)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_row_counts_by_requirement="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_row_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_field_names_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_field_names_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_value_count="
        f"{report.frontier_human_review_open_csv_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_value_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_missing_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_suggestion_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_suggestion_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_missing_suggestion_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_suggestion_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_missing_suggestion_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_suggested_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_suggested_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_suggested_value_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_suggested_value_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_record_filled_patch_field_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_record_filled_patch_field_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_record_filled_patch_field_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_record_filled_patch_field_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_record_filled_patch_fields_by_record_ref_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_record_filled_patch_fields_by_record_ref_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_reviewer_value_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(_reviewer_value_hint_counts_by_requirement(missing_value_counts=report.frontier_human_review_open_csv_missing_value_counts_by_requirement, missing_suggestion_counts=report.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement))}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_reviewer_value_hint_counts_by_field="
        f"{_stdout_count_mapping(_reviewer_value_hint_counts_by_field(missing_value_counts=report.frontier_human_review_open_csv_missing_value_counts_by_field, missing_suggestion_counts=report.frontier_human_review_open_csv_missing_suggestion_counts_by_field))}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_available_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_available_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_available_context_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_available_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_context_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_open_csv_missing_context_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_context_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_open_csv_missing_context_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_context_task_ids_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_missing_context_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_missing_context_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_missing_context_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_available_context_keys_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_available_context_keys_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_available_context_keys_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_available_context_keys_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_available_context_values_by_requirement="
        f"{_stdout_nested_ids_mapping(report.frontier_human_review_open_csv_available_context_values_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_csv_available_context_values_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_csv_available_context_values_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_open_task_ids_by_field="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_open_task_ids_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_manifest_path="
        f"{_stdout_value(report.frontier_human_review_queue_split_manifest_path or '-')}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_source_csv_count="
        f"{report.frontier_human_review_queue_split_source_csv_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_review_row_count="
        f"{report.frontier_human_review_queue_split_merged_review_row_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_reviewed_value_count="
        f"{report.frontier_human_review_queue_split_merged_reviewed_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_missing_value_count="
        f"{report.frontier_human_review_queue_split_merged_missing_value_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_reviewed_evidence_count="
        f"{report.frontier_human_review_queue_split_merged_reviewed_evidence_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_missing_evidence_count="
        f"{report.frontier_human_review_queue_split_merged_missing_evidence_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_reviewer_value_hint_count="
        f"{report.frontier_human_review_queue_split_reviewer_value_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_reviewer_evidence_hint_count="
        f"{report.frontier_human_review_queue_split_reviewer_evidence_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_reviewer_value_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_reviewer_value_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_with_hint_count="
        f"{report.frontier_human_review_queue_split_missing_value_with_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_without_hint_count="
        f"{report.frontier_human_review_queue_split_missing_value_without_hint_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_with_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_missing_value_with_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_without_hint_counts_by_field="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_missing_value_without_hint_counts_by_field)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_ready_source_count="
        f"{report.frontier_human_review_queue_split_ready_source_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_blocked_source_count="
        f"{report.frontier_human_review_queue_split_blocked_source_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_ready_reviewed_csv_paths="
        f"{_stdout_id_list(report.frontier_human_review_queue_split_ready_reviewed_csv_paths)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_blocked_reviewed_csv_paths="
        f"{_stdout_id_list(report.frontier_human_review_queue_split_blocked_reviewed_csv_paths)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_ready_fill_review_audit_command_hints="
        f"{_stdout_id_list(report.frontier_human_review_queue_split_ready_fill_review_audit_command_hints)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_blocked_fill_review_audit_command_hints="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_blocked_fill_review_audit_command_hints)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_blocked_fill_task_apply_command_hints="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_blocked_fill_task_apply_command_hints)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path="
        f"{_stdout_string_mapping(report.frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path="
        f"{_stdout_count_mapping(report.frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_reviewer_value_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_reviewer_value_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_with_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_value_with_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_without_hint_counts_by_reviewed_csv_path="
        f"{_stdout_nested_count_mapping(report.frontier_human_review_queue_split_missing_value_without_hint_counts_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path="
        f"{_stdout_ids_by_kind_mapping(report.frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement="
        f"{_stdout_nested_count_mapping(report.frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement="
        f"{_stdout_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement="
        f"{_stdout_count_mapping(report.frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_blocker_reasons_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_blocker_reasons_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_blocker_reason_counts="
        f"{_stdout_count_mapping(report.frontier_blocker_reason_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_blocked_by_requirement_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_blocked_by_requirement_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_blocked_by_requirement_counts="
        f"{_stdout_count_mapping(report.frontier_blocked_by_requirement_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_blocked_by_requirement_unique_ids_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.frontier_blocked_by_requirement_unique_ids_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "frontier_blocked_by_requirement_unique_counts="
        f"{_stdout_count_mapping(report.frontier_blocked_by_requirement_unique_counts)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"ready_to_run_next_action_count={report.ready_to_run_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"ready_to_run_unique_next_action_count={report.ready_to_run_unique_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"placeholder_command_next_action_count={report.placeholder_command_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"placeholder_command_unique_next_action_count={report.placeholder_command_unique_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"prerequisite_gated_next_action_count={report.prerequisite_gated_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "prerequisite_gated_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.prerequisite_gated_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "prerequisite_gated_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.prerequisite_gated_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"placeholder_command_next_action_ids={','.join(report.placeholder_command_next_action_ids) or '-'}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "placeholder_command_action_texts_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.placeholder_command_action_texts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "placeholder_command_hints_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.placeholder_command_hints_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "placeholder_command_unresolved_placeholders_by_requirement="
        f"{_stdout_ids_by_kind_mapping(report.placeholder_command_unresolved_placeholders_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "placeholder_command_unresolved_placeholder_counts_by_requirement="
        f"{_stdout_count_mapping(report.placeholder_command_unresolved_placeholder_counts_by_requirement)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "placeholder_command_unresolved_placeholder_counts_by_placeholder="
        f"{_stdout_count_mapping(report.placeholder_command_unresolved_placeholder_counts_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        "placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder="
        f"{_stdout_string_mapping(report.placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder)}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"blocked_without_next_action_count={report.blocked_without_next_action_count}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"blocked_without_next_action_ids={','.join(report.blocked_without_next_action_ids) or '-'}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"threshold_calibration_out={_stdout_value(Path(args.threshold_calibration_out).resolve())}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"threshold_checked_comparison_out={_stdout_value(Path(args.threshold_checked_comparison_out).resolve())}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"threshold_adoption_out={_stdout_value(Path(args.threshold_adoption_out).resolve())}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"contract_compatibility_out={_stdout_value(Path(args.contract_compatibility_out).resolve())}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"contract_readiness_out={_stdout_value(Path(args.contract_readiness_out).resolve())}"
    )
    print(
        "[evidence_grounding_roadmap_completion_package] "
        f"out={_stdout_value(Path(args.out).expanduser().resolve())}"
    )
    if args.print_action_queue_counts or args.print_all_action_queues:
        _print_action_queue_counts(report, prefix="evidence_grounding_roadmap_completion_package")
    if args.print_blocker_summary:
        _print_blocker_summary(report, prefix="evidence_grounding_roadmap_completion_package")
    if args.print_placeholder_summary:
        _print_placeholder_summary(report, prefix="evidence_grounding_roadmap_completion_package")
    if args.print_frontier_actions:
        frontier_action_limit = max(0, args.frontier_action_limit)
        actions = report.frontier_next_actions[:frontier_action_limit] if frontier_action_limit else report.frontier_next_actions
        omitted_count = max(0, len(report.frontier_next_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"frontier_action_total_count={len(report.frontier_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"frontier_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"frontier_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            human_review = f" requires_human_review={item.requires_human_review}"
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion_package] "
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
            "[evidence_grounding_roadmap_completion_package] "
            f"unblocked_frontier_action_total_count={len(unblocked_frontier_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"unblocked_frontier_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"unblocked_frontier_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            human_review = f" requires_human_review={item.requires_human_review}"
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion_package] "
                f"unblocked_frontier_action.{index} requirement_id={item.requirement_id}{phase}{human_review}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
    if args.print_next_actions or args.print_all_action_queues:
        action_limit = max(0, args.next_action_limit)
        actions = report.next_actions[:action_limit] if action_limit else report.next_actions
        omitted_count = max(0, len(report.next_actions) - len(actions))
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"next_action_total_count={len(report.next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"next_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"next_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            human_review = f" requires_human_review={item.requires_human_review}"
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion_package] "
                f"next_action.{index} requirement_id={item.requirement_id}{phase}{human_review}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
        _print_structured_correction_diagnostics(
            report,
            prefix="evidence_grounding_roadmap_completion_package",
        )
        _print_p0_metric_diagnostics(
            report,
            prefix="evidence_grounding_roadmap_completion_package",
        )
        _print_threshold_package_diagnostics(
            report,
            prefix="evidence_grounding_roadmap_completion_package",
        )
        _print_fill_review_suggestion_diagnostics(
            report,
            prefix="evidence_grounding_roadmap_completion_package",
        )
        _print_handoff_template_paths(
            report,
            prefix="evidence_grounding_roadmap_completion_package",
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
            "[evidence_grounding_roadmap_completion_package] "
            f"human_review_action_total_count={len(report.human_review_unique_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"human_review_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"human_review_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion_package] "
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
            "[evidence_grounding_roadmap_completion_package] "
            f"ready_to_run_action_total_count={len(report.ready_to_run_unique_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"ready_to_run_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"ready_to_run_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion_package] "
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
            "[evidence_grounding_roadmap_completion_package] "
            f"placeholder_command_action_total_count={len(report.placeholder_command_unique_next_actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"placeholder_command_action_printed_count={len(actions)}"
        )
        print(
            "[evidence_grounding_roadmap_completion_package] "
            f"placeholder_command_action_omitted_count={omitted_count}"
        )
        for index, item in enumerate(actions, start=1):
            phase = f" phase={item.phase}" if item.phase else ""
            command_hint = f" command_hint={item.command_hint}" if item.command_hint else ""
            diagnostics = _stdout_next_action_diagnostic_fields(item)
            print(
                "[evidence_grounding_roadmap_completion_package] "
                f"placeholder_command_action.{index} requirement_id={item.requirement_id}{phase}"
                f"{diagnostics} action={_stdout_value(item.action)}{_stdout_value(command_hint)}"
            )
    return 0 if report.roadmap_complete else 1


def _parse_threshold_metrics(raw_values: list[str] | None) -> dict[str, float] | None:
    if not raw_values:
        return None
    parsed: dict[str, float] = {}
    for raw_value in raw_values:
        if "=" not in raw_value:
            raise ValueError(f"--threshold-metric must use NAME=VALUE: {raw_value!r}")
        name, value = raw_value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"--threshold-metric requires a metric name: {raw_value!r}")
        parsed[name] = float(value.strip())
    return parsed


def _parse_gold_release_staged_split_manifest(raw: str) -> PaperUnderstandingGoldReleaseManifestBuildItem:
    values: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            raise ValueError(f"--gold-release-staged-split-manifest item must use key=value: {item!r}")
        key, value = item.split("=", 1)
        key = key.strip().lower().replace("-", "_")
        value = value.strip()
        if key == "split":
            values["goldset_split"] = value
        elif key in {"staging", "staging_manifest", "staging_manifest_path"}:
            values["staging_manifest_path"] = value
        elif key in {"out", "manifest_out"}:
            values["manifest_out"] = value
        else:
            raise ValueError(f"unsupported --gold-release-staged-split-manifest key={key!r}")
    return PaperUnderstandingGoldReleaseManifestBuildItem.model_validate(values)


if __name__ == "__main__":
    raise SystemExit(main())
