from __future__ import annotations

import re

from src.schemas.chart_pack import (
    ChartDataSnapshot,
    ChartScalar,
    ChartSnapshotField,
    ChartSourceRef,
    ChartTemplateId,
    ChartValueKind,
    ChartWarning,
)
from src.schemas.cloud_paper import CloudPaperDownstreamAdapterResponse


_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")


def build_cloud_derived_table_chart_snapshot(
    adapter_response: CloudPaperDownstreamAdapterResponse,
    *,
    table_id: str,
    template_id: ChartTemplateId,
) -> ChartDataSnapshot:
    if template_id not in {"table_numeric_bar", "table_numeric_line"}:
        raise ValueError(f"Unsupported cloud-derived table template: {template_id}")

    table_candidate = next(
        (
            candidate
            for candidate in adapter_response.candidates
            if candidate.kind == "table"
            and candidate.candidate_id == table_id
            and "chart_pack" in candidate.allowed_lanes
        ),
        None,
    )
    if table_candidate is None:
        raise FileNotFoundError(f"cloud-derived table candidate not found: {table_id}")

    headers = list(table_candidate.table_columns)
    if not headers:
        headers = [f"column_{index + 1}" for index in range(max((len(row) for row in table_candidate.table_rows), default=0))]

    column_values: dict[str, list[str]] = {header: [] for header in headers}
    rows: list[dict[str, ChartScalar | None]] = []
    for source_row in table_candidate.table_rows:
        row: dict[str, ChartScalar | None] = {}
        for index, header in enumerate(headers):
            raw_value = str(source_row[index]).strip() if index < len(source_row) else ""
            column_values[header].append(raw_value)
            row[header] = _coerce_chart_cell(raw_value)
        rows.append(row)

    columns = [
        ChartSnapshotField(
            field_id=header,
            label=header,
            value_kind=_infer_column_kind(column_values[header]),
            source_field=header,
        )
        for header in headers
    ]
    warnings = [
        ChartWarning(
            code="cloud_derived_noncanonical",
            severity="warning",
            message="This chart snapshot is derived from server-side table reconstruction, not canonical structured evidence.",
        )
    ]
    if not any(column.value_kind == "numeric" for column in columns):
        warnings.append(
            ChartWarning(
                code="no_numeric_mapped_field",
                severity="warning",
                message="The cloud-derived table did not contain an inferred numeric column.",
            )
        )

    return ChartDataSnapshot(
        template_id=template_id,
        source_ref=ChartSourceRef(
            source_kind="cloud_derived_table",
            paper_id=adapter_response.paper_id,
            run_id=adapter_response.run_id,
            table_id=table_candidate.candidate_id,
            source_label=table_candidate.title,
        ),
        columns=columns,
        rows=rows,
        transforms=[],
        warnings=warnings,
        source_row_count=len(rows),
        note=(
            "Cloud-derived table snapshot; "
            f"source_pdf_sha256={adapter_response.source_pdf_sha256}; "
            f"candidate_id={table_candidate.candidate_id}; "
            "canonical_status=derived_noncanonical."
        ),
    )


def _infer_column_kind(values: list[str]) -> ChartValueKind:
    non_empty = [value for value in values if value]
    if non_empty and all(_NUMERIC_RE.match(value) for value in non_empty):
        return "numeric"
    lowered = {value.lower() for value in non_empty}
    if lowered and lowered <= {"true", "false", "yes", "no"}:
        return "boolean"
    return "text"


def _coerce_chart_cell(value: str) -> ChartScalar | None:
    if not value:
        return None
    if _NUMERIC_RE.match(value):
        number = float(value)
        if number.is_integer():
            return int(number)
        return number
    lowered = value.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    return value
