from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from src.schemas.chart_pack import ChartDataSnapshot, ChartDefinition, ChartPack


def render_chart_snapshot_csv(snapshot: ChartDataSnapshot) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    header = [column.field_id for column in snapshot.columns]
    writer.writerow(header)
    for row in snapshot.rows:
        writer.writerow([_render_cell(row.get(column.field_id)) for column in snapshot.columns])
    return buffer.getvalue()


def render_chart_spec(chart: ChartDefinition, snapshot: ChartDataSnapshot) -> dict[str, Any]:
    column_ids = [column.field_id for column in snapshot.columns]
    numeric_columns = [column.field_id for column in snapshot.columns if column.value_kind == "numeric"]
    text_columns = [column.field_id for column in snapshot.columns if column.value_kind == "text"]

    spec: dict[str, Any] = {
        "chart_id": chart.chart_id,
        "title": chart.title,
        "template_id": chart.template_id,
        "source_ref": chart.source_ref.model_dump(mode="json", exclude_none=True),
        "columns": [
            {
                "field_id": column.field_id,
                "label": column.label,
                "value_kind": column.value_kind,
                "source_field": column.source_field,
            }
            for column in snapshot.columns
        ],
        "row_count": len(snapshot.rows),
        "warnings": [warning.model_dump(mode="json", exclude_none=True) for warning in snapshot.warnings],
    }

    if chart.template_id == "stats_check_status_counts":
        spec.update(
            {
                "mark": "bar",
                "encoding": {"x": "status", "y": "value"},
            }
        )
        return spec

    if chart.template_id == "reported_vs_computed_p_scatter":
        spec.update(
            {
                "mark": "point",
                "encoding": {"x": "reported_p", "y": "computed_p"},
            }
        )
        return spec

    if chart.template_id in {"table_numeric_bar", "table_numeric_line"}:
        if numeric_columns:
            y_field = numeric_columns[0]
        else:
            y_field = column_ids[-1] if column_ids else None
        x_candidates = [field_id for field_id in text_columns if field_id != y_field]
        x_field = x_candidates[0] if x_candidates else (column_ids[0] if column_ids else None)
        spec.update(
            {
                "mark": "bar" if chart.template_id == "table_numeric_bar" else "line",
                "encoding": {"x": x_field, "y": y_field},
            }
        )
        return spec

    raise ValueError(f"Unsupported chart template: {chart.template_id}")


def render_chart_pack_markdown(
    chart_pack: ChartPack,
    snapshots: dict[str, ChartDataSnapshot],
) -> str:
    lines: list[str] = []
    lines.append(f"# {chart_pack.title}")
    lines.append("")
    lines.append(f"- Chart Pack ID: {chart_pack.chart_pack_id}")
    lines.append(f"- Created at: {chart_pack.created_at.isoformat()}")
    if chart_pack.generated_at is not None:
        lines.append(f"- Generated at: {chart_pack.generated_at.isoformat()}")
    lines.append(f"- Charts: {len(chart_pack.charts)}")
    if chart_pack.render_env is not None:
        lines.append(f"- Render env: {chart_pack.render_env.engine} {chart_pack.render_env.version}")
    if chart_pack.caution_notes:
        lines.append(f"- Caution notes: {' | '.join(chart_pack.caution_notes)}")
    if chart_pack.warnings:
        lines.append(
            "- Pack warnings: "
            + " | ".join(f"[{warning.code}] {warning.message}" for warning in chart_pack.warnings)
        )
    lines.append("")

    lines.append("## Charts")
    for chart in chart_pack.charts:
        snapshot = snapshots.get(chart.chart_id)
        lines.append(f"### {chart.title}")
        lines.append(f"- Chart ID: {chart.chart_id}")
        lines.append(f"- Template: {chart.template_id}")
        lines.append(
            "- Source: "
            + f"{chart.source_ref.source_kind} "
            + f"({chart.source_ref.paper_id} / {chart.source_ref.run_id}"
            + (f" / {chart.source_ref.table_id}" if chart.source_ref.table_id else "")
            + ")"
        )
        if chart.data_snapshot_ref is not None:
            lines.append(f"- Data snapshot: {chart.data_snapshot_ref.path}")
        if chart.spec_ref is not None:
            lines.append(f"- Spec: {chart.spec_ref.path}")
        if chart.warnings:
            lines.append(
                "- Warnings: "
                + " | ".join(f"[{warning.code}] {warning.message}" for warning in chart.warnings)
            )
        if chart.transforms:
            lines.append("- Transforms:")
            for transform in chart.transforms:
                lines.append(f"  - {transform.kind}: {transform.description}")
        if snapshot is not None:
            lines.append(
                "- Snapshot: "
                + f"{len(snapshot.rows)} row(s), columns="
                + ", ".join(column.field_id for column in snapshot.columns)
            )
            if snapshot.note:
                lines.append(f"- Snapshot note: {snapshot.note}")
            lines.append("")
            lines.extend(_render_markdown_table(snapshot))
        else:
            lines.append("- Snapshot: unavailable")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _render_markdown_table(snapshot: ChartDataSnapshot) -> list[str]:
    if not snapshot.columns:
        return ["No columns available."]

    header = [column.label for column in snapshot.columns]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    preview_rows = snapshot.rows[:5]
    for row in preview_rows:
        lines.append(
            "| "
            + " | ".join(_markdown_cell(row.get(column.field_id)) for column in snapshot.columns)
            + " |"
        )
    if len(snapshot.rows) > len(preview_rows):
        lines.append(f"_Preview limited to first {len(preview_rows)} row(s) of {len(snapshot.rows)}._")
    return lines


def _markdown_cell(value: Any) -> str:
    text = _render_cell(value)
    return text if text else ""


def _render_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
