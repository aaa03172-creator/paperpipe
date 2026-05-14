from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.schemas.agent_artifacts import DocumentArtifact, StatsReport
from src.schemas.chart_pack import (
    ChartDataSnapshot,
    ChartDefinition,
    ChartFilter,
    ChartFilterValue,
    ChartRequest,
    ChartScalar,
    ChartSnapshotField,
    ChartSort,
    ChartSourceRef,
    ChartTemplateId,
    ChartTransform,
    ChartValueKind,
    ChartWarning,
)
from src.services.runtime_paths import artifacts_root as default_artifacts_root
from src.services.runtime_paths import preferred_artifact_paper_dir


ChartPackInput = ChartRequest | ChartDefinition
_P_APPROX_PREFIXES = ("<", ">", "≤", "≥")
_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")


@dataclass(frozen=True)
class _RawSnapshot:
    rows: tuple[dict[str, ChartScalar | None], ...]
    field_kinds: dict[str, ChartValueKind]
    warnings: tuple[ChartWarning, ...]
    source_row_count: int
    note: str | None = None


def build_chart_data_snapshot(
    chart: ChartPackInput,
    *,
    artifacts_root: Path | None = None,
) -> ChartDataSnapshot:
    artifacts_path = (artifacts_root or default_artifacts_root()).expanduser().resolve()
    raw = _load_raw_snapshot(chart.source_ref, chart.template_id, artifacts_root=artifacts_path)
    columns, rows, transforms = _apply_chart_projection(chart, raw)
    warnings = list(raw.warnings)

    if chart.template_id in {"table_numeric_bar", "table_numeric_line"}:
        if not any(column.value_kind == "numeric" for column in columns):
            warnings.append(
                ChartWarning(
                    code="no_numeric_mapped_field",
                    severity="warning",
                    message="The selected mapped fields do not include a numeric column.",
                )
            )

    if not rows:
        warnings.append(
            ChartWarning(
                code="empty_snapshot",
                severity="warning",
                message="No rows remained after field mapping, filtering, and sorting.",
            )
        )

    return ChartDataSnapshot(
        template_id=chart.template_id,
        source_ref=chart.source_ref,
        columns=columns,
        rows=rows,
        transforms=transforms,
        warnings=_dedupe_warnings(warnings),
        source_row_count=raw.source_row_count,
        note=raw.note,
    )


def _load_raw_snapshot(
    source_ref: ChartSourceRef,
    template_id: ChartTemplateId,
    *,
    artifacts_root: Path,
) -> _RawSnapshot:
    if source_ref.source_kind == "stats_report":
        report = _load_stats_report(source_ref, artifacts_root=artifacts_root)
        if template_id == "stats_check_status_counts":
            return _stats_check_status_counts_snapshot(report)
        if template_id == "reported_vs_computed_p_scatter":
            return _reported_vs_computed_p_snapshot(report)
        raise ValueError(f"Unsupported stats_report template: {template_id}")

    if source_ref.source_kind == "document_table":
        document = _load_document_artifact(source_ref, artifacts_root=artifacts_root)
        if template_id in {"table_numeric_bar", "table_numeric_line"}:
            return _document_table_snapshot(document, source_ref=source_ref)
        raise ValueError(f"Unsupported document_table template: {template_id}")

    raise ValueError(f"Unsupported source kind: {source_ref.source_kind}")


def _load_stats_report(source_ref: ChartSourceRef, *, artifacts_root: Path) -> StatsReport:
    run_dir = _artifact_run_dir(source_ref, artifacts_root=artifacts_root)
    path = run_dir / "stats_report.json"
    if not path.exists():
        raise FileNotFoundError(f"stats_report.json not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StatsReport(**payload)
    except Exception as exc:
        raise ValueError(f"Failed to parse stats report {path}: {exc}") from exc


def _stats_check_status_counts_snapshot(report: StatsReport) -> _RawSnapshot:
    counts: dict[str, int] = {}
    for check in report.checks:
        verdict = str(getattr(check.verdict, "value", check.verdict))
        counts[verdict] = counts.get(verdict, 0) + 1

    warnings: list[ChartWarning] = []
    if not report.checks:
        warnings.append(
            ChartWarning(
                code="no_checks",
                severity="warning",
                message="Stats report contains no verification checks.",
            )
        )

    rows = tuple({"status": status, "count": count} for status, count in sorted(counts.items()))
    return _RawSnapshot(
        rows=rows,
        field_kinds={"status": "text", "count": "numeric"},
        warnings=tuple(warnings),
        source_row_count=len(report.checks),
        note=f"Loaded {len(report.checks)} check(s) from stats_report.json.",
    )


def _reported_vs_computed_p_snapshot(report: StatsReport) -> _RawSnapshot:
    rows: list[dict[str, ChartScalar | None]] = []
    skipped_pairs = 0
    for check in report.checks:
        reported_p = _parse_reported_p(check.reported_p)
        computed_p = check.computed_p
        if reported_p is None or computed_p is None:
            skipped_pairs += 1
            continue
        rows.append(
            {
                "reported_p": reported_p,
                "computed_p": float(computed_p),
                "check_id": check.check_id,
                "test_type": check.test_type,
            }
        )

    warnings: list[ChartWarning] = []
    if skipped_pairs:
        warnings.append(
            ChartWarning(
                code="stats_p_pairs_skipped",
                severity="warning",
                message=f"Skipped {skipped_pairs} check(s) without exact reported/computed p pairs.",
            )
        )
    if not rows:
        warnings.append(
            ChartWarning(
                code="no_chartable_pairs",
                severity="warning",
                message="No chartable reported/computed p pairs were available in the stats report.",
            )
        )

    return _RawSnapshot(
        rows=tuple(rows),
        field_kinds={
            "reported_p": "numeric",
            "computed_p": "numeric",
            "check_id": "text",
            "test_type": "text",
        },
        warnings=tuple(warnings),
        source_row_count=len(report.checks),
        note=f"Loaded {len(rows)} chartable p-value pair(s) from stats_report.json.",
    )


def _load_document_artifact(source_ref: ChartSourceRef, *, artifacts_root: Path) -> DocumentArtifact | DocumentArtifactV2:
    run_dir = _artifact_run_dir(source_ref, artifacts_root=artifacts_root)
    candidates = [
        (run_dir / "document_artifact_v2.json", "v2"),
        (run_dir / "document_artifact.json", "legacy"),
    ]
    for path, kind in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if kind == "v2":
                return DocumentArtifactV2(**payload)
            return DocumentArtifact(**payload)
        except Exception as exc:
            raise ValueError(f"Failed to parse document artifact {path}: {exc}") from exc
    raise FileNotFoundError(f"document artifact not found for paper_id={source_ref.paper_id}, run_id={source_ref.run_id}")


def _document_table_snapshot(
    document: DocumentArtifact | DocumentArtifactV2,
    *,
    source_ref: ChartSourceRef,
) -> _RawSnapshot:
    tables = list(getattr(document, "tables", []) or [])
    table = next((candidate for candidate in tables if getattr(candidate, "table_id", None) == source_ref.table_id), None)
    if table is None:
        raise FileNotFoundError(f"Table {source_ref.table_id} not found in saved document artifact")

    table_rows = list(getattr(table, "data", []) or [])
    warnings: list[ChartWarning] = []
    if not table_rows:
        warnings.append(
            ChartWarning(
                code="empty_table",
                severity="warning",
                message=f"Table {source_ref.table_id} contained no rows.",
            )
        )
        return _RawSnapshot(
            rows=tuple(),
            field_kinds={},
            warnings=tuple(warnings),
            source_row_count=0,
            note=f"Loaded empty table {source_ref.table_id}.",
        )

    headers = _normalize_headers(table_rows[0])
    body_rows = table_rows[1:]
    if not body_rows:
        warnings.append(
            ChartWarning(
                code="table_no_data_rows",
                severity="warning",
                message=f"Table {source_ref.table_id} contained headers but no data rows.",
            )
        )

    column_values: dict[str, list[str]] = {header: [] for header in headers}
    for row in body_rows:
        for index, header in enumerate(headers):
            column_values[header].append(_string_cell(row[index]) if index < len(row) else "")

    field_kinds = {header: _infer_column_kind(values) for header, values in column_values.items()}
    normalized_rows: list[dict[str, ChartScalar | None]] = []
    for row in body_rows:
        normalized_row: dict[str, ChartScalar | None] = {}
        for index, header in enumerate(headers):
            raw_value = _string_cell(row[index]) if index < len(row) else ""
            normalized_row[header] = _coerce_cell_value(raw_value, field_kinds[header])
        normalized_rows.append(normalized_row)

    if not any(kind == "numeric" for kind in field_kinds.values()):
        warnings.append(
            ChartWarning(
                code="table_no_numeric_columns",
                severity="warning",
                message=f"Table {source_ref.table_id} did not expose a fully numeric column.",
            )
        )

    return _RawSnapshot(
        rows=tuple(normalized_rows),
        field_kinds=field_kinds,
        warnings=tuple(warnings),
        source_row_count=len(body_rows),
        note=f"Loaded table {source_ref.table_id} with {len(body_rows)} data row(s).",
    )


def _apply_chart_projection(
    chart: ChartPackInput,
    raw: _RawSnapshot,
) -> tuple[list[ChartSnapshotField], list[dict[str, ChartScalar | None]], list[ChartTransform]]:
    available_fields = set(raw.field_kinds)
    transforms: list[ChartTransform] = []
    columns: list[ChartSnapshotField] = []
    for mapping in chart.field_mappings:
        if mapping.source_field not in available_fields:
            raise ValueError(f"Unknown source field for chart template: {mapping.source_field}")
        columns.append(
            ChartSnapshotField(
                field_id=mapping.target_field,
                label=mapping.label or _humanize_field_name(mapping.target_field),
                value_kind=raw.field_kinds[mapping.source_field],
                source_field=mapping.source_field,
            )
        )
        transforms.append(
            ChartTransform(
                kind="field_mapping",
                description=f"Mapped source field '{mapping.source_field}' to '{mapping.target_field}'.",
                field=mapping.target_field,
                value=mapping.source_field,
            )
        )

    mapped_rows = [
        {mapping.target_field: row.get(mapping.source_field) for mapping in chart.field_mappings}
        for row in raw.rows
    ]
    mapped_rows = _apply_filters(mapped_rows, chart.filters, transforms)
    mapped_rows = _apply_sort(mapped_rows, chart.sort, transforms)
    return columns, mapped_rows, transforms


def _apply_filters(
    rows: list[dict[str, ChartScalar | None]],
    filters: list[ChartFilter],
    transforms: list[ChartTransform],
) -> list[dict[str, ChartScalar | None]]:
    filtered_rows = list(rows)
    available_fields = set(filtered_rows[0]) if filtered_rows else {flt.field for flt in filters}
    for item in filters:
        if item.field not in available_fields:
            raise ValueError(f"Unknown filter field: {item.field}")
        filtered_rows = [row for row in filtered_rows if _row_matches_filter(row, item)]
        transforms.append(
            ChartTransform(
                kind="filter",
                description=f"Applied filter {item.field} {item.op} {item.value!r}.",
                field=item.field,
                value=item.value,
            )
        )
    return filtered_rows


def _apply_sort(
    rows: list[dict[str, ChartScalar | None]],
    sort: ChartSort | None,
    transforms: list[ChartTransform],
) -> list[dict[str, ChartScalar | None]]:
    if sort is None:
        return rows
    available_fields = set(rows[0]) if rows else {sort.field}
    if sort.field not in available_fields:
        raise ValueError(f"Unknown sort field: {sort.field}")

    non_null_rows = [row for row in rows if row.get(sort.field) is not None]
    null_rows = [row for row in rows if row.get(sort.field) is None]
    non_null_rows.sort(key=lambda row: _sortable_value(row.get(sort.field)), reverse=sort.direction == "desc")
    transforms.append(
        ChartTransform(
            kind="sort",
            description=f"Sorted by {sort.field} ({sort.direction}).",
            field=sort.field,
            value=sort.direction,
        )
    )
    return [*non_null_rows, *null_rows]


def _row_matches_filter(row: dict[str, ChartScalar | None], flt: ChartFilter) -> bool:
    current = row.get(flt.field)
    target = flt.value
    if flt.op == "eq":
        return current == target
    if flt.op == "neq":
        return current != target
    if flt.op == "in":
        values = target if isinstance(target, list) else [target]
        return current in values
    if current is None:
        return False
    left = _sortable_value(current)
    right = _sortable_value(target if not isinstance(target, list) else (target[0] if target else None))
    if right is None:
        return False
    if flt.op == "gt":
        return left > right
    if flt.op == "gte":
        return left >= right
    if flt.op == "lt":
        return left < right
    if flt.op == "lte":
        return left <= right
    raise ValueError(f"Unsupported filter op: {flt.op}")


def _artifact_run_dir(source_ref: ChartSourceRef, *, artifacts_root: Path) -> Path:
    paper_dir = preferred_artifact_paper_dir(source_ref.paper_id, root=artifacts_root)
    run_dir = paper_dir / source_ref.run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"Artifact run directory not found: {run_dir}")
    return run_dir


def _parse_reported_p(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("p", "").replace("=", "").replace("P", "").strip()
    if text.startswith(_P_APPROX_PREFIXES):
        return None
    if not _NUMERIC_RE.match(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_headers(header_row: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: dict[str, int] = {}
    for index, raw in enumerate(header_row):
        text = _string_cell(raw)
        text = text or f"column_{index + 1}"
        count = seen.get(text, 0)
        seen[text] = count + 1
        if count:
            text = f"{text}_{count + 1}"
        normalized.append(text)
    return normalized


def _infer_column_kind(values: list[str]) -> ChartValueKind:
    non_empty = [value for value in values if value.strip()]
    if not non_empty:
        return "text"
    if all(value.lower() in {"true", "false"} for value in non_empty):
        return "boolean"
    if all(_looks_numeric(value) for value in non_empty):
        return "numeric"
    return "text"


def _coerce_cell_value(value: str, kind: ChartValueKind) -> ChartScalar | None:
    text = value.strip()
    if not text:
        return None
    if kind == "numeric":
        parsed = float(text)
        return int(parsed) if parsed.is_integer() else parsed
    if kind == "boolean":
        return text.lower() == "true"
    return text


def _looks_numeric(value: str) -> bool:
    return bool(_NUMERIC_RE.match(value.strip()))


def _sortable_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if _looks_numeric(text):
        return float(text)
    return text.lower()


def _string_cell(value: Any) -> str:
    return str(value or "").strip()


def _humanize_field_name(name: str) -> str:
    parts = [part for part in re.split(r"[_\s]+", name.strip()) if part]
    if not parts:
        return name
    return " ".join(part.capitalize() for part in parts)


def _dedupe_warnings(warnings: list[ChartWarning]) -> list[ChartWarning]:
    deduped: list[ChartWarning] = []
    seen: set[tuple[str, str, str]] = set()
    for warning in warnings:
        key = (warning.code, warning.severity, warning.message)
        if key not in seen:
            deduped.append(warning)
            seen.add(key)
    return deduped
