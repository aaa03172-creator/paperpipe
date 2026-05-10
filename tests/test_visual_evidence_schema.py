from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.visual_evidence import (
    VisualEvidenceLedger,
    VisualEvidenceObject,
    summarize_visual_evidence,
)


def test_visual_evidence_ledger_preserves_review_gate_boundary() -> None:
    entries = [
        VisualEvidenceObject(
            evidence_id="ve_fig_2",
            kind="figure",
            page=3,
            figure_id="fig_2",
            caption="Fig. 2. Representative microscopy panels after treatment.",
            observed_elements=["treated panel has visibly fewer labeled cells than control"],
            allowed_claims=["Figure 2 visually compares treated and control microscopy panels."],
            not_allowed_claims=["Treatment reduces cell count unless quantified elsewhere."],
            inferred_notes=["Possible reduction requires quantified table or text support."],
            status="observed",
            linked_claim_ids=["CLM-001"],
            source_artifact="figure_captions.json",
        )
    ]
    ledger = VisualEvidenceLedger(
        paper_id="paper-001",
        run_id="run-001",
        generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        entries=entries,
        metrics=summarize_visual_evidence(entries),
    )

    assert ledger.schema_version == "visual_evidence_ledger.v1"
    assert ledger.layer == "review_gate_artifact"
    assert ledger.canonical_status == "non_canonical"
    assert ledger.generation_replay_required is True
    assert ledger.final_answer_validation_required is True
    assert ledger.metrics.entry_count == 1
    assert ledger.metrics.observed_count == 1
    assert ledger.entries[0].observed_elements
    assert ledger.entries[0].inferred_notes


def test_unknown_visual_evidence_requires_explicit_failure_reason() -> None:
    with pytest.raises(ValidationError, match="requires failure_reason"):
        VisualEvidenceObject(
            evidence_id="ve_fig_unknown",
            kind="figure",
            page=1,
            figure_id="fig_1",
            status="unknown",
        )

    evidence = VisualEvidenceObject(
        evidence_id="ve_fig_unknown",
        kind="figure",
        page=1,
        figure_id="fig_1",
        status="unknown",
        failure_reason="vision_unavailable",
        caption="Fig. 1. Workflow diagram.",
    )
    assert evidence.failure_reason == "vision_unavailable"
    assert evidence.allowed_claims == []


def test_visual_evidence_keeps_table_cell_grounding_explicit() -> None:
    evidence = VisualEvidenceObject(
        evidence_id="ve_table_1",
        kind="table",
        page=4,
        table_id="T1",
        caption="Table 1. Outcome measures.",
        extracted_values=[
            {
                "label": "primary outcome",
                "value": "12.4",
                "unit": "points",
                "table_id": "T1",
                "cell_id": "r2c3",
                "row_label": "treated",
                "column_label": "mean",
            }
        ],
        allowed_claims=["Table 1 reports a treated mean of 12.4 points."],
        status="observed",
    )

    assert evidence.extracted_values[0].table_id == "T1"
    assert evidence.extracted_values[0].cell_id == "r2c3"

    with pytest.raises(ValidationError, match="table_id and cell_id"):
        VisualEvidenceObject(
            evidence_id="ve_table_bad_cell",
            kind="table",
            page=4,
            table_id="T1",
            extracted_values=[{"label": "primary outcome", "value": "12.4", "table_id": "T1"}],
            status="observed",
        )


def test_visual_evidence_rejects_missing_kind_specific_identifiers_and_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="figure-like visual evidence requires figure_id"):
        VisualEvidenceObject(
            evidence_id="ve_missing_figure",
            kind="figure",
            page=0,
            observed_elements=["panel labels are visible"],
            status="observed",
        )

    with pytest.raises(ValidationError, match="table visual evidence requires table_id"):
        VisualEvidenceObject(
            evidence_id="ve_missing_table",
            kind="table",
            page=0,
            extracted_values=[{"label": "n", "value": "20"}],
            status="observed",
        )

    entry = VisualEvidenceObject(
        evidence_id="ve_dup",
        kind="figure",
        page=0,
        figure_id="fig_1",
        observed_elements=["diagram contains two branches"],
        status="observed",
    )
    with pytest.raises(ValidationError, match="duplicate evidence_id"):
        VisualEvidenceLedger(
            paper_id="paper-001",
            run_id="run-001",
            generated_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
            entries=[entry, entry],
        )
