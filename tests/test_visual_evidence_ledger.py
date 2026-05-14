from __future__ import annotations

import json
from datetime import datetime, timezone

from src.contracts.document_artifact_v2 import ArtifactMetaV2, DocumentArtifactV2, TableV2
from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim
from src.schemas.figure_captions import FigureCaptionEntry, FigureCaptionMetrics, FigureCaptionSidecar
from src.services.visual_evidence_ledger import build_visual_evidence_ledger, write_visual_evidence_ledger


def test_build_visual_evidence_ledger_keeps_caption_only_figures_unknown() -> None:
    figure_captions = FigureCaptionSidecar(
        paper_id="paper-1",
        run_id="run-1",
        generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        metrics=FigureCaptionMetrics(figure_count=1, page_count=1),
        figures=[
            FigureCaptionEntry(
                figure_id="fig_2",
                label="Fig. 2.",
                page=3,
                section="page_3",
                caption="Representative microscopy panels after treatment.",
            )
        ],
    )
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="CLM-001",
                type="finding",
                statement="Figure 2 compares treated and control microscopy panels.",
                confidence=0.8,
                evidence_spans=[
                    EvidenceSpan(
                        page=2,
                        chunk_id="p03_c01",
                        raw_text="Fig. 2. Representative microscopy panels after treatment.",
                        quote="Fig. 2. Representative microscopy panels",
                        rationale="The figure caption names the visual comparison.",
                    )
                ],
            )
        ],
    )

    ledger = build_visual_evidence_ledger(
        paper_id="paper-1",
        run_id="run-1",
        document_artifact=DocumentArtifactV2(
            document_id="paper-1",
            meta=ArtifactMetaV2(title="T", authors=[], source_ref="paper.pdf"),
            pages=[],
            tables=[],
        ),
        figure_captions=figure_captions,
        resolved_claimset=claimset,
        generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )

    assert ledger.schema_version == "visual_evidence_ledger.v1"
    assert ledger.source_artifacts == ["document_artifact.json", "figure_captions.json", "claimset.resolved.json"]
    assert ledger.metrics.entry_count == 1
    assert ledger.metrics.unknown_count == 1
    entry = ledger.entries[0]
    assert entry.kind == "microscopy"
    assert entry.page == 2
    assert entry.figure_id == "fig_2"
    assert entry.status == "unknown"
    assert entry.failure_reason == "caption_only"
    assert entry.allowed_claims == []
    assert entry.linked_claim_ids == ["CLM-001"]
    assert entry.not_allowed_claims


def test_build_visual_evidence_ledger_samples_tables_without_interpreting_them(tmp_path) -> None:
    doc = DocumentArtifactV2(
        document_id="paper-table",
        meta=ArtifactMetaV2(title="T", authors=[], source_ref="paper.pdf"),
        pages=[],
        tables=[
            TableV2(
                table_id="T1",
                caption="Outcome measures.",
                source_page=4,
                data=[
                    ["group", "mean", "sd"],
                    ["treated", "12.4", "1.2"],
                    ["control", "10.1", "1.5"],
                ],
            )
        ],
    )
    claimset = ClaimSet(
        doc_id="paper-table",
        claims=[
            ScientificClaim(
                claim_id="CLM-T1",
                type="finding",
                statement="Table T1 reports a treated mean of 12.4 points.",
                confidence=0.8,
                evidence_spans=[
                    EvidenceSpan(
                        page=3,
                        chunk_id="unknown",
                        raw_text="treated mean 12.4",
                        quote="12.4",
                        rationale="The value is in the parsed table.",
                        table_id="T1",
                        cell_id="r2c2",
                    )
                ],
            )
        ],
    )

    ledger = build_visual_evidence_ledger(
        paper_id="paper-table",
        run_id="run-table",
        document_artifact=doc,
        resolved_claimset=claimset,
        generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    path = write_visual_evidence_ledger(ledger, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "visual_evidence_ledger.v1"
    assert ledger.metrics.partially_observed_count == 1
    assert ledger.metrics.linked_claim_count == 1
    entry = ledger.entries[0]
    assert entry.kind == "table"
    assert entry.page == 3
    assert entry.status == "partially_observed"
    assert entry.extracted_values[1].cell_id == "r2c2"
    assert entry.extracted_values[1].value == "12.4"
    assert entry.allowed_claims == ["Table T1 exposes parsed cell values that can be cited with table/cell grounding."]
    assert "significance" in entry.not_allowed_claims[0]
