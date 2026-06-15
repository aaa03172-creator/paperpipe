#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.path_masking import mask_local_paths_in_text  # noqa: E402
from src.skills.storage import atomic_write_text  # noqa: E402


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required: {path}")
    return payload


def _command_arg(command: str, name: str) -> str | None:
    parts = shlex.split(command)
    for index, part in enumerate(parts):
        if part == name and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith(f"{name}="):
            return part.split("=", 1)[1]
    return None


def _source_for_requirement(manifest: dict, requirement_id: str) -> dict:
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("split_manifest_sources_list_required")
    matches: list[dict] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        requirement_ids = source.get("requirement_ids")
        if not isinstance(requirement_ids, list):
            continue
        if requirement_id in {str(value) for value in requirement_ids}:
            matches.append(source)
    if len(matches) != 1:
        raise ValueError(f"split_manifest_requirement_source_count_must_be_one: {requirement_id}")
    return matches[0]


def _source_string(source: dict, key: str) -> str | None:
    value = source.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _require_derived_input(inputs: dict[str, str | None], key: str, source_label: str) -> str:
    value = inputs.get(key)
    if not value:
        raise ValueError(f"split_manifest_missing_{source_label}")
    return value


def derive_inputs_from_split_manifest(
    *,
    split_manifest_path: str,
    requirement_id: str,
) -> dict[str, str]:
    manifest = _read_json(Path(split_manifest_path))
    source = _source_for_requirement(manifest, requirement_id)
    command = _source_string(source, "fill_review_audit_command_hint") or ""
    if not command:
        raise ValueError("split_manifest_missing_fill_review_audit_command_hint")

    inputs: dict[str, str | None] = {
        "fill_review_status_path": _command_arg(command, "--out"),
        "reviewed_csv_path": _command_arg(command, "--reviewed-csv")
        or _source_string(source, "reviewed_csv_path"),
        "open_records_csv_path": _command_arg(command, "--open-record-csv-out"),
        "task_export_path": _command_arg(command, "--task-export")
        or _source_string(source, "source_task_export_path"),
    }
    return {
        "fill_review_status_path": _require_derived_input(
            inputs, "fill_review_status_path", "fill_review_status"
        ),
        "reviewed_csv_path": _require_derived_input(inputs, "reviewed_csv_path", "reviewed_csv"),
        "open_records_csv_path": _require_derived_input(
            inputs, "open_records_csv_path", "open_records_csv"
        ),
        "task_export_path": _require_derived_input(inputs, "task_export_path", "task_export"),
    }


def _read_open_records_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{str(key): str(value or "") for key, value in row.items()} for row in reader]
    if not reader.fieldnames:
        raise ValueError(f"open_records_csv_missing_header: {path}")
    required = {"record_ref", "open_field_names", "filled_patch_fields"}
    missing = sorted(required.difference(reader.fieldnames))
    if missing:
        raise ValueError(f"open_records_csv_missing_columns: {','.join(missing)}")
    return rows


def _require_existing_file(path: str, label: str) -> None:
    if not Path(path).is_file():
        raise ValueError(f"{label}_missing: {path}")


def _related_review_output_path(status_path: str, suffix: str) -> str:
    path = Path(status_path)
    marker = ".fill_review_status.json"
    if path.name.endswith(marker):
        return str(path.with_name(f"{path.name[: -len(marker)]}{suffix}"))
    return str(path.with_suffix(suffix))


def _task_export_markdown_path(task_export_path: str) -> str:
    return str(Path(task_export_path).with_suffix(".md"))


def _split_list_cell(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _format_inline_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "-"


def _compact_cell_text(value: str, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = f"{text[: max(0, limit - 3)].rstrip()}..."
    return text.replace("|", "\\|")


def _context_preview(record: dict[str, str]) -> str:
    hint = str(record.get("reviewer_evidence_hint") or "").strip()
    context_values = str(record.get("available_context_values") or "").strip()
    if hint:
        return _compact_cell_text(hint)
    if context_values:
        return _compact_cell_text(context_values)
    return "no context/evidence hint recorded"


def _require_int(payload: dict, key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key}_int_required")
    return value


def _active_reviewer_lanes(audit: dict) -> list[str]:
    counts = audit.get("frontier_human_review_open_csv_row_counts_by_requirement")
    if not isinstance(counts, dict):
        counts = audit.get("human_review_open_csv_row_counts_by_requirement")
    if not isinstance(counts, dict):
        return []
    lanes = [
        str(requirement_id)
        for requirement_id, count in counts.items()
        if isinstance(count, int) and count > 0
    ]
    return sorted(lanes)


def render_active_reviewer_brief(
    *,
    audit_path: str,
    fill_review_status_path: str,
    reviewed_csv_path: str,
    open_records_csv_path: str,
    task_export_path: str,
    generated_date: str,
) -> str:
    _require_existing_file(reviewed_csv_path, "reviewed_csv")
    _require_existing_file(task_export_path, "task_export")
    audit = _read_json(Path(audit_path))
    status = _read_json(Path(fill_review_status_path))
    open_records = _read_open_records_csv(Path(open_records_csv_path))

    audit_open_rows = _require_int(audit, "human_review_open_csv_row_count")
    audit_open_records = _require_int(audit, "human_review_open_record_count")
    status_open_rows = _require_int(status, "open_csv_row_count")
    status_open_records = _require_int(status, "open_record_count")
    status_missing_evidence = _require_int(status, "missing_evidence_count")
    status_missing_values = _require_int(status, "missing_value_count")

    if len(open_records) != status_open_records:
        raise ValueError("open_records_csv_row_count_mismatch")
    if status_open_rows != audit_open_rows:
        raise ValueError("status_open_csv_row_count_must_match_audit")
    if status_open_records != audit_open_records:
        raise ValueError("status_open_record_count_must_match_audit")
    active_lanes = _active_reviewer_lanes(audit)
    if active_lanes and active_lanes != ["structured_correction_log"]:
        raise ValueError(f"unsupported_active_reviewer_lanes: {','.join(active_lanes)}")
    active_lane = active_lanes[0] if active_lanes else "structured_correction_log"

    rows: list[str] = [
        "# Frontier Active Reviewer Brief",
        "",
        f"Generated: {generated_date}",
        "Layer: working handoff, non-canonical",
        "",
        (
            "This brief lists only the current recommended-path reviewer work. It does not provide "
            "reviewer-owned values, approve evidence, or replace the reviewed CSV."
        ),
        "",
        "## Current Status",
        "",
        f"- Latest audit: `{audit_path}`",
        (
            "- Roadmap status: "
            f"`roadmap_complete={str(audit.get('roadmap_complete')).lower()}`, "
            f"`pass_count={audit.get('pass_count')}`, `fail_count={audit.get('fail_count')}`"
        ),
        f"- Active reviewer lane: `{active_lane}`",
        f"- Open records: `{status_open_records}`",
        f"- Open cells: `{status_open_rows}`",
        f"- Missing reviewer values: `{status_missing_values}`",
        f"- Missing evidence count: `{status_missing_evidence}`",
        "- Context/evidence hints: present in the open-records CSV when listed there, but support only",
        f"- Full context packet: `{_task_export_markdown_path(task_export_path)}`",
        "",
        "## Review Scope",
        "",
        "- Current open structured-correction fields are provenance/config metadata, not paper-content judgments.",
        "- Expected paper reading: `no`, unless the context packet is insufficient or contradictory.",
        "- Primary review sources: full context packet, reviewed CSV, and open-records CSV.",
        "",
        "## File To Edit",
        "",
        "Edit this reviewed CSV:",
        "",
        f"`{reviewed_csv_path}`",
        "",
        "Use this open-records CSV for a grouped view of the active records:",
        "",
        f"`{open_records_csv_path}`",
        "",
        "## What To Fill",
        "",
        "Open the full context packet first, then edit the reviewed CSV.",
        "",
        (
            "For each row in the reviewed CSV, fill `reviewer_value`. `reviewer_evidence` can reuse "
            "the row evidence hint only if the reviewer accepts that hint as sufficient."
        ),
        "",
        (
            "Do not fill by inference from this brief. The available context is support material, "
            "not an approved mapping."
        ),
        "",
        "| Record | Fill these fields | Already filled | Evidence/context status | Evidence/context preview |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in open_records:
        record_ref = record["record_ref"].strip()
        open_fields = _split_list_cell(record.get("open_field_names", ""))
        filled_fields = _split_list_cell(record.get("filled_patch_fields", ""))
        context_status = (
            "context/evidence hint present"
            if str(record.get("reviewer_evidence_hint") or record.get("available_context_values") or "").strip()
            else "no context/evidence hint recorded"
        )
        rows.append(
            "| "
            f"`{record_ref}` | "
            f"{_format_inline_list(open_fields)} | "
            f"{_format_inline_list(filled_fields)} | "
            f"{context_status} | "
            f"{_context_preview(record)} |"
        )

    rows.extend(
        [
            "",
            "## Recheck Command",
            "",
            "Run this after reviewer values are entered:",
            "",
            "```bash",
            ".venv/bin/python scripts/eval/audit_evidence_grounding_patch_template_fill_task_reviews.py \\",
            f"  --task-export {task_export_path} \\",
            f"  --reviewed-csv {reviewed_csv_path} \\",
            f"  --out {fill_review_status_path} \\",
            f"  --annotated-csv-out {_related_review_output_path(fill_review_status_path, '.annotated.csv')} \\",
            f"  --open-csv-out {_related_review_output_path(fill_review_status_path, '.open.csv')} \\",
            f"  --open-record-csv-out {open_records_csv_path} \\",
            "  --use-reviewer-evidence-hints",
            "```",
            "",
            "## Not In This Brief",
            "",
            "- Historical A-mode candidate-lineage rows are not part of the current recommended-path frontier.",
            "- P0 overstatement decisions still require separate reviewer judgment in the P0 packet.",
            "- External contract readiness still requires an explicit approval reference and opt-in.",
        ]
    )
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a compact non-canonical reviewer brief for the current Evidence Grounding "
            "frontier without filling reviewer-owned values."
        )
    )
    parser.add_argument("--audit", required=True, help="Roadmap completion audit JSON.")
    parser.add_argument(
        "--split-manifest",
        help=(
            "Optional frontier split manifest. When provided, missing review input paths are "
            "derived from the matching source's fill-review command hint."
        ),
    )
    parser.add_argument(
        "--requirement-id",
        default="structured_correction_log",
        help="Requirement id to select from --split-manifest.",
    )
    parser.add_argument("--fill-review-status", help="Fill-review status JSON.")
    parser.add_argument("--reviewed-csv", help="Reviewed CSV the reviewer should edit.")
    parser.add_argument("--open-records-csv", help="Open-records CSV for grouped review.")
    parser.add_argument("--task-export", help="Patch-template fill task export JSON.")
    parser.add_argument("--out", required=True, help="Markdown brief output path.")
    parser.add_argument("--generated-date", default="2026-05-31", help="Date string to print in the brief.")
    args = parser.parse_args()

    try:
        derived_inputs: dict[str, str] = {}
        if args.split_manifest:
            derived_inputs = derive_inputs_from_split_manifest(
                split_manifest_path=args.split_manifest,
                requirement_id=args.requirement_id,
            )
        fill_review_status_path = args.fill_review_status or derived_inputs.get(
            "fill_review_status_path"
        )
        reviewed_csv_path = args.reviewed_csv or derived_inputs.get("reviewed_csv_path")
        open_records_csv_path = args.open_records_csv or derived_inputs.get("open_records_csv_path")
        task_export_path = args.task_export or derived_inputs.get("task_export_path")
        required_inputs = {
            "fill_review_status": fill_review_status_path,
            "reviewed_csv": reviewed_csv_path,
            "open_records_csv": open_records_csv_path,
            "task_export": task_export_path,
        }
        missing = [label for label, value in required_inputs.items() if not value]
        if missing:
            raise ValueError(f"required_inputs_missing: {','.join(missing)}")
        markdown = render_active_reviewer_brief(
            audit_path=args.audit,
            fill_review_status_path=str(fill_review_status_path),
            reviewed_csv_path=str(reviewed_csv_path),
            open_records_csv_path=str(open_records_csv_path),
            task_export_path=str(task_export_path),
            generated_date=args.generated_date,
        )
        atomic_write_text(Path(args.out).expanduser().resolve(), markdown)
    except Exception as exc:
        print(
            f"[evidence_grounding_active_reviewer_brief] error={mask_local_paths_in_text(str(exc))}",
            file=sys.stderr,
        )
        return 1

    print(
        "[evidence_grounding_active_reviewer_brief] "
        f"out={mask_local_paths_in_text(str(Path(args.out).expanduser().resolve()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
