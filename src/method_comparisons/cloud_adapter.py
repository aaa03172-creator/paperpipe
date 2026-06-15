from __future__ import annotations

from src.schemas.cloud_paper import CloudPaperDownstreamAdapterResponse
from src.schemas.method_comparison import (
    MethodComparisonCloudDerivedContext,
    MethodComparisonCloudDerivedContextItem,
)


def build_method_comparison_cloud_derived_context(
    adapter_response: CloudPaperDownstreamAdapterResponse,
) -> MethodComparisonCloudDerivedContext:
    items: list[MethodComparisonCloudDerivedContextItem] = []
    for candidate in adapter_response.candidates:
        if candidate.kind not in {"ocr_text", "table"}:
            continue
        if "method_comparison" not in candidate.allowed_lanes:
            continue
        items.append(
            MethodComparisonCloudDerivedContextItem(
                context_id=f"methodctx_{len(items) + 1:02d}",
                candidate_id=candidate.candidate_id,
                kind=candidate.kind,
                paper_id=candidate.paper_id,
                run_id=candidate.run_id,
                title=candidate.title,
                text=_candidate_context_text(candidate.kind, candidate.text, candidate.table_columns, candidate.table_rows),
                source_page=candidate.source.page,
                source_block_id=candidate.source.block_id,
                source_pdf_sha256=candidate.source.source_pdf_sha256,
                payload_class=candidate.payload_class,
                readiness="background_only",
                canonical_status=candidate.canonical_status,
                comparison_cell_status="missing",
                confidence=candidate.confidence,
                evidence_refs=[],
            )
        )

    return MethodComparisonCloudDerivedContext(
        paper_id=adapter_response.paper_id,
        run_id=adapter_response.run_id,
        source_pdf_sha256=adapter_response.source_pdf_sha256,
        readiness="background_only",
        payload_class=adapter_response.payload_class,
        items=items,
        warnings=[warning.message for warning in adapter_response.warnings],
    )


def _candidate_context_text(
    kind: str,
    text: str | None,
    table_columns: list[str],
    table_rows: list[list[str]],
) -> str | None:
    if kind != "table":
        return text
    if not table_rows:
        return text
    header = " | ".join(table_columns) if table_columns else ""
    rendered_rows = [" | ".join(row) for row in table_rows[:3]]
    parts = [part for part in [text, header, *rendered_rows] if part]
    return "\n".join(parts) or None
