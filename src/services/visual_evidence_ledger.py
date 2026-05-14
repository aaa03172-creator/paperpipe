from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from src.schemas.agent_artifacts import ClaimSet
from src.schemas.figure_captions import FigureCaptionSidecar
from src.schemas.visual_evidence import (
    VisualEvidenceLedger,
    VisualEvidenceObject,
    VisualExtractedValue,
    summarize_visual_evidence,
)
from src.skills.storage import atomic_write_text

_FIGURE_KIND_TERMS = {
    "microscopy": ("microscopy", "microscope", "micrograph", "fluorescence", "confocal"),
    "plot": ("plot", "curve", "bar chart", "graph", "scatter", "kaplan", "volcano"),
    "diagram": ("diagram", "schematic", "workflow", "overview", "model", "architecture"),
}
_TABLE_CELL_ROW_LIMIT = 5
_TABLE_CELL_COL_LIMIT = 8


def build_visual_evidence_ledger(
    *,
    paper_id: str,
    run_id: str,
    document_artifact: Any,
    figure_captions: FigureCaptionSidecar | None = None,
    resolved_claimset: ClaimSet | None = None,
    generated_at: datetime | None = None,
) -> VisualEvidenceLedger:
    entries: list[VisualEvidenceObject] = []
    entries.extend(_figure_entries(figure_captions=figure_captions, resolved_claimset=resolved_claimset))
    entries.extend(_table_entries(document_artifact=document_artifact, resolved_claimset=resolved_claimset))
    return VisualEvidenceLedger(
        paper_id=paper_id,
        run_id=run_id,
        generated_at=generated_at or datetime.now(timezone.utc),
        source_artifacts=_source_artifacts(figure_captions=figure_captions, resolved_claimset=resolved_claimset),
        entries=entries,
        metrics=summarize_visual_evidence(entries),
    )


def write_visual_evidence_ledger(ledger: VisualEvidenceLedger, artifact_dir: Path) -> Path:
    path = artifact_dir / "visual_evidence_ledger.json"
    atomic_write_text(path, ledger.model_dump_json(indent=2))
    return path


def _figure_entries(
    *,
    figure_captions: FigureCaptionSidecar | None,
    resolved_claimset: ClaimSet | None,
) -> list[VisualEvidenceObject]:
    if figure_captions is None:
        return []

    entries: list[VisualEvidenceObject] = []
    for figure in figure_captions.figures:
        page = _zero_indexed_page(getattr(figure, "page", None))
        figure_id = str(getattr(figure, "figure_id", "") or "").strip()
        if page is None or not figure_id:
            continue
        label = str(getattr(figure, "label", "") or "").strip()
        caption = str(getattr(figure, "caption", "") or "").strip() or None
        linked_claim_ids = _linked_claim_ids_for_figure(
            resolved_claimset=resolved_claimset,
            figure_id=figure_id,
            label=label,
        )
        entries.append(
            VisualEvidenceObject(
                evidence_id=f"visual_{figure_id}",
                kind=_infer_figure_kind(caption or label),
                page=page,
                figure_id=figure_id,
                caption=caption,
                status="unknown",
                failure_reason="caption_only",
                linked_claim_ids=linked_claim_ids,
                source_artifact="figure_captions.json",
                not_allowed_claims=[
                    "Do not infer visual measurements, causal effects, statistical significance, or biological mechanism from the caption alone."
                ],
            )
        )
    return entries


def _table_entries(*, document_artifact: Any, resolved_claimset: ClaimSet | None) -> list[VisualEvidenceObject]:
    entries: list[VisualEvidenceObject] = []
    tables = list(getattr(document_artifact, "tables", []) or [])
    for table in tables:
        table_id = str(_attr_or_item(table, "table_id") or "").strip()
        if not table_id:
            continue
        page = _zero_indexed_page(_attr_or_item(table, "source_page"))
        if page is None:
            continue
        caption = str(_attr_or_item(table, "caption") or "").strip() or None
        data = _table_data(table)
        extracted_values = _sample_table_values(table_id=table_id, data=data)
        linked_claim_ids = _linked_claim_ids_for_table(resolved_claimset=resolved_claimset, table_id=table_id)
        if extracted_values:
            entries.append(
                VisualEvidenceObject(
                    evidence_id=f"visual_{table_id}",
                    kind="table",
                    page=page,
                    table_id=table_id,
                    caption=caption,
                    extracted_values=extracted_values,
                    observed_text=_table_preview_lines(data),
                    allowed_claims=[f"Table {table_id} exposes parsed cell values that can be cited with table/cell grounding."],
                    not_allowed_claims=[
                        "Do not infer trend, significance, or causality from parsed table cells without matching textual/statistical support."
                    ],
                    status="partially_observed",
                    linked_claim_ids=linked_claim_ids,
                    source_artifact="document_artifact.json",
                )
            )
        else:
            entries.append(
                VisualEvidenceObject(
                    evidence_id=f"visual_{table_id}",
                    kind="table",
                    page=page,
                    table_id=table_id,
                    caption=caption,
                    status="unknown",
                    failure_reason="table_parse_failed",
                    linked_claim_ids=linked_claim_ids,
                    source_artifact="document_artifact.json",
                    not_allowed_claims=["Do not cite table-derived values because no parsed rows were available."],
                )
            )
    return entries


def _source_artifacts(*, figure_captions: FigureCaptionSidecar | None, resolved_claimset: ClaimSet | None) -> list[str]:
    artifacts = ["document_artifact.json"]
    if figure_captions is not None:
        artifacts.append("figure_captions.json")
    if resolved_claimset is not None:
        artifacts.append("claimset.resolved.json")
    return artifacts


def _zero_indexed_page(value: object) -> int | None:
    if isinstance(value, int):
        if value > 0:
            return value - 1
        if value == 0:
            return 0
    if isinstance(value, float) and value.is_integer():
        return _zero_indexed_page(int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return _zero_indexed_page(int(value.strip()))
    return None


def _infer_figure_kind(text: str) -> str:
    lowered = str(text or "").lower()
    for kind, terms in _FIGURE_KIND_TERMS.items():
        if any(term in lowered for term in terms):
            return kind
    return "figure"


def _linked_claim_ids_for_figure(*, resolved_claimset: ClaimSet | None, figure_id: str, label: str) -> list[str]:
    if resolved_claimset is None:
        return []
    needles = _figure_needles(figure_id=figure_id, label=label)
    linked: list[str] = []
    for claim in resolved_claimset.claims:
        haystack = _claim_haystack(claim)
        if any(needle and needle in haystack for needle in needles):
            linked.append(claim.claim_id)
    return linked


def _figure_needles(*, figure_id: str, label: str) -> list[str]:
    needles = {_normalize_text(figure_id), _normalize_text(label)}
    match = re.search(r"(\d+[a-z]?)", f"{figure_id} {label}", flags=re.IGNORECASE)
    if match is not None:
        number = match.group(1).lower()
        needles.update(
            {
                f"fig {number}",
                f"figure {number}",
                f"fig. {number}",
            }
        )
    return [needle for needle in needles if needle]


def _linked_claim_ids_for_table(*, resolved_claimset: ClaimSet | None, table_id: str) -> list[str]:
    if resolved_claimset is None:
        return []
    normalized_table_id = _normalize_text(table_id)
    linked: list[str] = []
    for claim in resolved_claimset.claims:
        span_table_ids = {_normalize_text(str(span.table_id or "")) for span in claim.evidence_spans}
        if normalized_table_id in span_table_ids or normalized_table_id in _claim_haystack(claim):
            linked.append(claim.claim_id)
    return linked


def _claim_haystack(claim: Any) -> str:
    parts = [str(getattr(claim, "statement", "") or "")]
    for span in list(getattr(claim, "evidence_spans", []) or []):
        parts.extend(
            [
                str(getattr(span, "raw_text", "") or ""),
                str(getattr(span, "quote", "") or ""),
                str(getattr(span, "rationale", "") or ""),
            ]
        )
    return _normalize_text("\n".join(parts))


def _normalize_text(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return " ".join(text.split())


def _attr_or_item(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _table_data(table: Any) -> list[list[str]]:
    data = _attr_or_item(table, "data") or []
    rows: list[list[str]] = []
    for row in data:
        if not isinstance(row, list):
            continue
        cells = [str(cell or "").strip() for cell in row]
        if any(cells):
            rows.append(cells)
    return rows


def _sample_table_values(*, table_id: str, data: list[list[str]]) -> list[VisualExtractedValue]:
    if not data:
        return []
    headers = [cell.strip() or f"col_{idx + 1}" for idx, cell in enumerate(data[0][:_TABLE_CELL_COL_LIMIT])]
    values: list[VisualExtractedValue] = []
    for row_idx, row in enumerate(data[1 : _TABLE_CELL_ROW_LIMIT + 1], start=2):
        row_label = row[0].strip() if row and row[0].strip() else None
        for col_idx, cell in enumerate(row[:_TABLE_CELL_COL_LIMIT], start=1):
            cell_text = str(cell or "").strip()
            if not cell_text:
                continue
            header = headers[col_idx - 1] if col_idx - 1 < len(headers) else f"col_{col_idx}"
            values.append(
                VisualExtractedValue(
                    label=header,
                    value=cell_text,
                    table_id=table_id,
                    cell_id=f"r{row_idx}c{col_idx}",
                    row_label=row_label,
                    column_label=header,
                )
            )
    return values


def _table_preview_lines(data: list[list[str]]) -> list[str]:
    return [" | ".join(row[:_TABLE_CELL_COL_LIMIT]) for row in data[: _TABLE_CELL_ROW_LIMIT + 1]]
