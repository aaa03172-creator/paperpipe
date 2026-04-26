from __future__ import annotations

import csv
from io import StringIO
from math import isfinite
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


def render_chart_svg(
    chart: ChartDefinition,
    snapshot: ChartDataSnapshot,
    spec_payload: dict[str, Any],
) -> str:
    width = 720
    height = 420
    left = 72
    right = 28
    top = 56
    bottom = 68
    plot_width = width - left - right
    plot_height = height - top - bottom
    plot_left = left
    plot_top = top
    plot_bottom = top + plot_height

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{_svg_id(chart.chart_id, "title")} {_svg_id(chart.chart_id, "desc")}">',
        f"<title id=\"{_svg_id(chart.chart_id, 'title')}\">{_escape_xml(chart.title)}</title>",
        f"<desc id=\"{_svg_id(chart.chart_id, 'desc')}\">{_escape_xml(_build_svg_description(chart, snapshot))}</desc>",
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#0b1220" />',
        f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" rx="12" fill="#101a2b" stroke="#243247" />',
        f'<text x="{plot_left}" y="30" fill="#f8fafc" font-size="20" font-weight="700">{_escape_xml(chart.title)}</text>',
        (
            f'<text x="{plot_left}" y="48" fill="#94a3b8" font-size="12">{_escape_xml(chart.template_id)}'
            f" · {_escape_xml(chart.source_ref.source_kind)}</text>"
        ),
    ]

    if chart.warnings:
        warning_label = f"Warnings {len(chart.warnings)}"
        badge_width = max(96, 12 + len(warning_label) * 7)
        badge_x = width - right - badge_width
        parts.extend(
            [
                f'<rect x="{badge_x}" y="18" width="{badge_width}" height="24" rx="12" fill="#7c2d12" stroke="#fb923c" />',
                f'<text x="{badge_x + badge_width / 2:.1f}" y="34" fill="#ffedd5" font-size="12" text-anchor="middle">{_escape_xml(warning_label)}</text>',
            ]
        )

    x_field = _encoding_field(spec_payload, "x")
    y_field = _encoding_field(spec_payload, "y")

    if chart.template_id == "reported_vs_computed_p_scatter":
        parts.extend(
            _render_scatter_plot(
                snapshot=snapshot,
                x_field=x_field,
                y_field=y_field,
                left=plot_left,
                top=plot_top,
                width=plot_width,
                height=plot_height,
            )
        )
    else:
        parts.extend(
            _render_series_plot(
                chart=chart,
                snapshot=snapshot,
                x_field=x_field,
                y_field=y_field,
                left=plot_left,
                top=plot_top,
                width=plot_width,
                height=plot_height,
                bottom=plot_bottom,
            )
        )

    parts.extend(
        [
            f'<text x="{plot_left}" y="{height - 22}" fill="#64748b" font-size="11">Derived chart artifact · inspect source lineage before reuse.</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


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
    if chart_pack.artifact_brief is not None:
        lines.append(f"- Artifact brief sources: {len(chart_pack.artifact_brief.source_context.source_items)}")
    if chart_pack.artifact_brief_review is not None:
        lines.append(f"- Artifact brief review: {chart_pack.artifact_brief_review.overall_status}")
    lines.append("")

    if chart_pack.artifact_brief is not None:
        lines.extend(
            [
                "## Artifact Brief",
                "",
                f"- Artifact family: {chart_pack.artifact_brief.artifact_family}",
                f"- Goal: {chart_pack.artifact_brief.communicative_intent.goal}",
                f"- Source items: {len(chart_pack.artifact_brief.source_context.source_items)}",
                f"- Direct plan items: {sum(1 for item in chart_pack.artifact_brief.plan.items if item.support_status == 'direct')}",
                "",
            ]
        )

    if chart_pack.artifact_brief_review is not None:
        lines.extend(
            [
                "## Artifact Brief Review",
                "",
                f"- Status: {chart_pack.artifact_brief_review.overall_status}",
            ]
        )
        for reason_code in chart_pack.artifact_brief_review.reason_codes:
            lines.append(f"- Reason code: {reason_code}")
        for warning in chart_pack.artifact_brief_review.warnings:
            lines.append(f"- Warning: {warning}")
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
        if chart.render_refs:
            lines.append("- Renders: " + ", ".join(ref.path for ref in chart.render_refs))
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


def _render_series_plot(
    *,
    chart: ChartDefinition,
    snapshot: ChartDataSnapshot,
    x_field: str | None,
    y_field: str | None,
    left: int,
    top: int,
    width: int,
    height: int,
    bottom: int,
) -> list[str]:
    series = _series_points(snapshot, x_field, y_field)
    if not series:
        return _render_empty_plot(left=left, top=top, width=width, height=height)

    domain_min, domain_max = _series_domain([point[1] for point in series])

    axis_parts = _render_y_axis(
        left=left,
        top=top,
        width=width,
        height=height,
        min_value=domain_min,
        max_value=domain_max,
    )
    slot_width = width / max(len(series), 1)
    baseline_y = _scale_y(0.0, min_value=domain_min, max_value=domain_max, top=top, height=height)
    draw_parts: list[str] = []

    if chart.template_id == "table_numeric_line":
        polyline_points: list[str] = []
        for index, (label, value) in enumerate(series):
            x = left + slot_width * index + slot_width / 2
            y = _scale_y(value, min_value=domain_min, max_value=domain_max, top=top, height=height)
            polyline_points.append(f"{x:.2f},{y:.2f}")
            draw_parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="#38bdf8" stroke="#e0f2fe" stroke-width="1.5" />'
            )
            label_y = max(y - 10, top + 12) if value >= 0 else min(y + 16, bottom - 8)
            draw_parts.extend(
                [
                    f'<text x="{x:.2f}" y="{bottom + 18}" fill="#94a3b8" font-size="11" text-anchor="middle">{_escape_xml(label)}</text>',
                    f'<text x="{x:.2f}" y="{label_y:.2f}" fill="#e2e8f0" font-size="11" text-anchor="middle">{_format_number(value)}</text>',
                ]
            )
        if len(polyline_points) >= 2:
            draw_parts.insert(
                0,
                f'<polyline fill="none" stroke="#38bdf8" stroke-width="3" points="{" ".join(polyline_points)}" />',
            )
        return axis_parts + draw_parts

    for index, (label, value) in enumerate(series):
        x = left + slot_width * index + slot_width * 0.18
        bar_width = max(slot_width * 0.64, 24)
        value_y = _scale_y(value, min_value=domain_min, max_value=domain_max, top=top, height=height)
        y = min(value_y, baseline_y)
        bar_height = abs(baseline_y - value_y)
        label_y = max(y - 8, top + 12) if value >= 0 else min(y + bar_height + 14, bottom - 8)
        draw_parts.extend(
            [
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="8" fill="#38bdf8" />',
                f'<text x="{x + bar_width / 2:.2f}" y="{label_y:.2f}" fill="#e2e8f0" font-size="11" text-anchor="middle">{_format_number(value)}</text>',
                f'<text x="{x + bar_width / 2:.2f}" y="{bottom + 18}" fill="#94a3b8" font-size="11" text-anchor="middle">{_escape_xml(label)}</text>',
            ]
        )
    return axis_parts + draw_parts


def _render_scatter_plot(
    *,
    snapshot: ChartDataSnapshot,
    x_field: str | None,
    y_field: str | None,
    left: int,
    top: int,
    width: int,
    height: int,
) -> list[str]:
    points = _scatter_points(snapshot, x_field, y_field)
    if not points:
        return _render_empty_plot(left=left, top=top, width=width, height=height)

    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    domain_min = min(x_values + y_values)
    domain_max = max(x_values + y_values)
    if domain_min == domain_max:
        domain_min -= 1.0
        domain_max += 1.0
    padding = (domain_max - domain_min) * 0.08
    min_value = domain_min - padding
    max_value = domain_max + padding

    parts = _render_square_axis(
        left=left,
        top=top,
        width=width,
        height=height,
        min_value=min_value,
        max_value=max_value,
    )
    diagonal_start = _scale_xy(min_value, min_value, min_value, max_value, left, top, width, height)
    diagonal_end = _scale_xy(max_value, max_value, min_value, max_value, left, top, width, height)
    parts.append(
        f'<line x1="{diagonal_start[0]:.2f}" y1="{diagonal_start[1]:.2f}" x2="{diagonal_end[0]:.2f}" y2="{diagonal_end[1]:.2f}" stroke="#475569" stroke-width="2" stroke-dasharray="6 4" />'
    )
    for x_value, y_value in points:
        point_x, point_y = _scale_xy(x_value, y_value, min_value, max_value, left, top, width, height)
        parts.append(
            f'<circle cx="{point_x:.2f}" cy="{point_y:.2f}" r="5" fill="#38bdf8" stroke="#e0f2fe" stroke-width="1.5" />'
        )
    return parts


def _render_y_axis(
    *,
    left: int,
    top: int,
    width: int,
    height: int,
    min_value: float,
    max_value: float,
) -> list[str]:
    parts = [
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + height}" stroke="#334155" stroke-width="1.5" />',
    ]
    for tick in _tick_values(min_value, max_value, count=5):
        y = _scale_y(tick, min_value=min_value, max_value=max_value, top=top, height=height)
        parts.extend(
            [
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + width}" y2="{y:.2f}" stroke="#1e293b" stroke-width="1" />',
                f'<text x="{left - 10}" y="{y + 4:.2f}" fill="#94a3b8" font-size="11" text-anchor="end">{_format_number(tick)}</text>',
            ]
        )
    if min_value <= 0.0 <= max_value:
        zero_y = _scale_y(0.0, min_value=min_value, max_value=max_value, top=top, height=height)
        parts.append(
            f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + width}" y2="{zero_y:.2f}" stroke="#475569" stroke-width="2" />'
        )
    return parts


def _render_square_axis(
    *,
    left: int,
    top: int,
    width: int,
    height: int,
    min_value: float,
    max_value: float,
) -> list[str]:
    parts = [
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + height}" stroke="#334155" stroke-width="1.5" />',
        f'<line x1="{left}" y1="{top + height}" x2="{left + width}" y2="{top + height}" stroke="#334155" stroke-width="1.5" />',
    ]
    ticks = _tick_values(min_value, max_value, count=5)
    for index, tick in enumerate(ticks):
        fraction = index / 4 if len(ticks) > 1 else 0
        x = left + width * fraction
        y = top + height - height * fraction
        parts.extend(
            [
                f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + height}" stroke="#1e293b" stroke-width="1" />',
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + width}" y2="{y:.2f}" stroke="#1e293b" stroke-width="1" />',
                f'<text x="{x:.2f}" y="{top + height + 18}" fill="#94a3b8" font-size="11" text-anchor="middle">{_format_number(tick)}</text>',
                f'<text x="{left - 10}" y="{y + 4:.2f}" fill="#94a3b8" font-size="11" text-anchor="end">{_format_number(tick)}</text>',
            ]
        )
    return parts


def _render_empty_plot(*, left: int, top: int, width: int, height: int) -> list[str]:
    return [
        f'<text x="{left + width / 2:.2f}" y="{top + height / 2:.2f}" fill="#94a3b8" font-size="15" text-anchor="middle">No chartable rows available.</text>'
    ]


def _series_points(
    snapshot: ChartDataSnapshot,
    x_field: str | None,
    y_field: str | None,
) -> list[tuple[str, float]]:
    if not x_field or not y_field:
        return []
    series: list[tuple[str, float]] = []
    for row in snapshot.rows:
        label = str(row.get(x_field) or "").strip() or "n/a"
        numeric_value = _coerce_float(row.get(y_field))
        if numeric_value is None:
            continue
        series.append((label, numeric_value))
    return series


def _scatter_points(
    snapshot: ChartDataSnapshot,
    x_field: str | None,
    y_field: str | None,
) -> list[tuple[float, float]]:
    if not x_field or not y_field:
        return []
    points: list[tuple[float, float]] = []
    for row in snapshot.rows:
        x_value = _coerce_float(row.get(x_field))
        y_value = _coerce_float(row.get(y_field))
        if x_value is None or y_value is None:
            continue
        points.append((x_value, y_value))
    return points


def _series_domain(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    min_value = min(values)
    max_value = max(values)
    if min_value >= 0:
        return 0.0, max_value if max_value > 0 else 1.0
    if max_value <= 0:
        return min_value if min_value < 0 else -1.0, 0.0
    return min_value, max_value


def _scale_y(value: float, *, min_value: float, max_value: float, top: int, height: int) -> float:
    domain = max(max_value - min_value, 1e-9)
    return top + height - ((value - min_value) / domain) * height


def _scale_xy(
    x_value: float,
    y_value: float,
    min_value: float,
    max_value: float,
    left: int,
    top: int,
    width: int,
    height: int,
) -> tuple[float, float]:
    domain = max(max_value - min_value, 1e-9)
    scaled_x = left + ((x_value - min_value) / domain) * width
    scaled_y = top + height - ((y_value - min_value) / domain) * height
    return scaled_x, scaled_y


def _tick_values(min_value: float, max_value: float, *, count: int) -> list[float]:
    if count <= 1:
        return [max_value]
    step = (max_value - min_value) / (count - 1)
    return [min_value + step * index for index in range(count)]


def _encoding_field(spec_payload: dict[str, Any], axis: str) -> str | None:
    encoding = spec_payload.get("encoding")
    if not isinstance(encoding, dict):
        return None
    value = encoding.get(axis)
    if not isinstance(value, str):
        return None
    return value


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if isfinite(float(value)):
            return float(value)
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        return None
    return numeric if isfinite(numeric) else None


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _svg_id(chart_id: str, suffix: str) -> str:
    return f"{chart_id}-{suffix}".replace("_", "-")


def _build_svg_description(chart: ChartDefinition, snapshot: ChartDataSnapshot) -> str:
    return (
        f"{chart.title}. Template {chart.template_id}. "
        f"{len(snapshot.rows)} row(s) rendered from saved {chart.source_ref.source_kind} source."
    )


def _escape_xml(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
