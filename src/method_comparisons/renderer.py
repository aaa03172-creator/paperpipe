from __future__ import annotations

import csv
from io import StringIO

from src.schemas.chat import ChatEvidenceRef
from src.schemas.method_comparison import ComparisonCell, MethodComparison


def render_method_comparison_csv(comparison: MethodComparison) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    header = ["paper_id", "paper_slug", "citekey", "title"]
    for column in comparison.columns:
        header.extend(
            [
                column.field_id,
                f"{column.field_id}__status",
                f"{column.field_id}__refs",
            ]
        )
    writer.writerow(header)

    for row in comparison.rows:
        cell_map = {cell.field_id: cell for cell in row.cells}
        record = [row.paper_id, row.paper_slug or "", row.citekey or "", row.title]
        for column in comparison.columns:
            cell = cell_map.get(column.field_id)
            if cell is None:
                record.extend(["", "missing", ""])
                continue
            record.extend(
                [
                    _render_csv_value(cell),
                    cell.status,
                    "; ".join(_format_ref_token(ref) for ref in cell.evidence_refs),
                ]
            )
        writer.writerow(record)
    return buffer.getvalue()


def render_method_comparison_markdown(comparison: MethodComparison) -> str:
    lines: list[str] = []
    lines.append(f"# {comparison.title}")
    lines.append("")
    lines.append(f"- Comparison ID: {comparison.comparison_id}")
    lines.append(f"- Layer: {comparison.layer}")
    lines.append(f"- Canonical status: {comparison.canonical_status}")
    lines.append(f"- Readiness: {comparison.readiness}")
    lines.append(f"- Freshness: {comparison.freshness}")
    lines.append(f"- Created at: {comparison.created_at.isoformat()}")
    if comparison.generated_at is not None:
        lines.append(f"- Generated at: {comparison.generated_at.isoformat()}")
    lines.append(f"- Papers: {len(comparison.paper_ids)}")
    lines.append(f"- Fields: {', '.join(column.field_id for column in comparison.columns)}")
    lines.append(f"- Source priority: {', '.join(comparison.source_summary.source_priority)}")
    if comparison.warnings:
        lines.append(f"- Warnings: {' | '.join(comparison.warnings)}")
    lines.append("")

    lines.append("## Comparison")
    header = ["Paper", *[column.label for column in comparison.columns]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in comparison.rows:
        cell_map = {cell.field_id: cell for cell in row.cells}
        rendered_cells = [_render_row_label(row.paper_id, row.title)]
        for column in comparison.columns:
            cell = cell_map.get(column.field_id)
            rendered_cells.append(_render_markdown_cell(cell))
        lines.append("| " + " | ".join(rendered_cells) + " |")
    lines.append("")

    lines.append("## Evidence Trace")
    for row in comparison.rows:
        lines.append(f"### {_render_row_label(row.paper_id, row.title)}")
        cell_map = {cell.field_id: cell for cell in row.cells}
        for column in comparison.columns:
            cell = cell_map.get(column.field_id)
            if cell is None:
                lines.append(f"- {column.label}: missing")
                continue
            status = f"[{cell.status}]"
            if cell.status == "missing":
                note = f" - {cell.note}" if cell.note else ""
                lines.append(f"- {column.label}: {status}{note}")
                continue
            value = _render_csv_value(cell)
            note = f" - {cell.note}" if cell.note else ""
            lines.append(f"- {column.label}: {value} {status}{note}")
            for ref in cell.evidence_refs:
                lines.append(f"  - {_format_ref_line(ref)}")
        lines.append("")

    lines.extend(
        [
            "## Promotion guardrail",
            "",
            "- This comparison is a derived user-facing artifact, not canonical scientific truth.",
            "- Promoted biomedical answers must jump back to upstream claim/evidence/source data before reuse.",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _render_markdown_cell(cell: ComparisonCell | None) -> str:
    if cell is None or cell.status == "missing":
        return "missing"
    value = _render_csv_value(cell)
    return f"{value} ({cell.status})"


def _render_csv_value(cell: ComparisonCell) -> str:
    if cell.value is None:
        return ""
    return str(cell.value)


def _render_row_label(paper_id: str, title: str) -> str:
    return f"{title} (`{paper_id}`)"


def _format_ref_token(ref: ChatEvidenceRef) -> str:
    parts = [ref.paper_slug]
    if ref.claim_id:
        parts.append(ref.claim_id)
    if ref.evidence_id:
        parts.append(ref.evidence_id)
    locator_bits: list[str] = []
    if ref.locator and ref.locator.page is not None:
        locator_bits.append(f"p{ref.locator.page}")
    if ref.locator and ref.locator.section:
        locator_bits.append(ref.locator.section)
    token = ":".join(parts)
    if locator_bits:
        token += "@" + ",".join(locator_bits)
    return token


def _format_ref_line(ref: ChatEvidenceRef) -> str:
    parts = [ref.paper_slug]
    if ref.claim_id:
        parts.append(f"claim_id={ref.claim_id}")
    if ref.evidence_id:
        parts.append(f"evidence_id={ref.evidence_id}")
    if ref.run_id:
        parts.append(f"run_id={ref.run_id}")
    if ref.locator and ref.locator.page is not None:
        parts.append(f"page={ref.locator.page}")
    if ref.locator and ref.locator.section:
        parts.append(f"section={ref.locator.section}")
    return ", ".join(parts)
