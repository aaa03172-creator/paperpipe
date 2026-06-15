from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from backend import main as api_main
from backend.routers import evidence_grounding_scorecards as evidence_grounding_scorecards_router
from src.schemas.agent_artifacts import (
    ClaimSet,
    DocumentArtifact,
    DocumentChunk,
    EvidenceSpan,
    IndexArtifact,
    PaperMetadata,
    ScientificClaim,
    Section,
    SourceInfo,
)
from src.schemas.claim_evidence_correction import (
    ClaimEvidenceCorrectionCase,
    ClaimEvidenceCorrectionEvalCandidate,
    ClaimEvidenceCorrectionReviewedEvalFixture,
    ClaimEvidenceCorrectionLocator,
)
from src.schemas.claimset_coverage import (
    ClaimsetCoverageEvidenceSummary,
    ClaimsetCoverageMetrics,
    ClaimsetCoveragePageSummary,
    ClaimsetCoverageSidecar,
)
from src.schemas.evidence_extraction import EvidenceExtractionBundle, EvidenceExtractionMetrics
from src.schemas.evidence_grounding_scorecard import (
    EvidenceGroundingCandidateConfig,
    EvidenceGroundingInputArtifactDiagnostic,
    EvidenceGroundingMetric,
    EvidenceGroundingScorecard,
    EvidenceGroundingScorecardBuildRequest,
    EvidenceGroundingScorecardInputBackfillItemRequest,
    EvidenceGroundingScorecardInputBackfillReport,
    EvidenceGroundingStageFailureSummary,
)
from src.schemas.deepread_handoff import DeepReadAcceptanceContract, DeepReadQualityGate, DeepReadQualityGateCheck
from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGold,
    PaperUnderstandingGoldEvidenceLocator,
    PaperUnderstandingGoldFigure,
    PaperUnderstandingGoldMetadata,
    PaperUnderstandingGoldStatement,
    PaperUnderstandingGoldTable,
)
from src.schemas.reader_eval import ReaderEvalClaimEntry, ReaderEvalMetrics, ReaderEvalSidecar
from src.schemas.visual_evidence import (
    VisualEvidenceLedger,
    VisualEvidenceMetrics,
    VisualEvidenceObject,
    VisualExtractedValue,
)
from src.services.evidence_grounding_scorecard import (
    build_evidence_grounding_scorecard,
    build_evidence_grounding_scorecard_from_run_dir,
    write_evidence_grounding_scorecard,
    write_evidence_grounding_scorecard_to_path,
)
from src.services.evidence_grounding_scorecard_input_backfill import (
    build_evidence_grounding_scorecard_input_backfill_report,
    load_scorecard_input_backfill_items_from_benchmark_artifacts,
)
from src.services.claim_evidence_corrections import write_claim_evidence_reviewed_eval_fixtures_sidecar


def _reader_eval() -> ReaderEvalSidecar:
    return ReaderEvalSidecar(
        generated_at=datetime.now(timezone.utc),
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        metrics=ReaderEvalMetrics(
            claim_count=4,
            supported_claim_count=2,
            unsupported_claim_count=1,
            unknown_claim_count=2,
            evidence_span_count=5,
            grounded_span_count=3,
            unresolved_span_count=1,
            ambiguous_span_count=1,
            failed_grounding_span_count=1,
            limitation_count=2,
            grounded_limitation_count=1,
            low_overlap_claim_count=1,
        ),
        claims=[
            ReaderEvalClaimEntry(
                claim_id="c1",
                statement="Supported claim.",
                supported=True,
                unsupported=False,
                unknown=False,
                evidence_span_count=1,
                grounded_span_count=1,
            ),
            ReaderEvalClaimEntry(
                claim_id="c2",
                statement="Missing location claim.",
                supported=False,
                unsupported=False,
                unknown=True,
                unknown_reason="EVIDENCE_LOCATION_MISSING",
                evidence_span_count=1,
                unresolved_span_count=1,
            ),
        ],
    )


def _coverage(status: str = "warn") -> ClaimsetCoverageSidecar:
    return ClaimsetCoverageSidecar(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        generated_at=datetime.now(timezone.utc),
        coverage_status=status,
        metrics=ClaimsetCoverageMetrics(
            claim_count=4,
            evidence_span_count=5,
            grounded_span_count=3,
            unresolved_span_count=2,
            grounded_evidence_ratio=0.6,
            document_page_count=10,
            covered_page_count=3,
            page_coverage_ratio=0.3,
            duplicate_cluster_count=1,
            missing_topic_signal_count=2,
        ),
        page_summary=ClaimsetCoveragePageSummary(
            covered_pages=[1, 2, 3],
            missing_page_ranges=["4-10"],
            undercovered_page_ranges=["4-10"],
        ),
        evidence_summary=ClaimsetCoverageEvidenceSummary(
            total_spans=5,
            grounded_spans=3,
            unresolved_spans=2,
            grounded_ratio=0.6,
            pages_with_grounded_evidence=[1, 2],
        ),
        recommended_next_action="review",
        reason_codes=["low_page_coverage"],
    )


def _evidence_extraction() -> EvidenceExtractionBundle:
    return EvidenceExtractionBundle(
        generated_at=datetime.now(timezone.utc),
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        source_artifacts=["claimset.resolved.json"],
        metrics=EvidenceExtractionMetrics(
            record_count=4,
            claim_record_count=2,
            clinical_field_record_count=1,
            entity_record_count=1,
            evidence_backed_record_count=3,
            artifact_backed_record_count=1,
            derived_record_count=0,
            evidence_ref_count=6,
            grounded_evidence_ref_count=3,
        ),
    )


def _visual_evidence() -> VisualEvidenceLedger:
    entries = [
        VisualEvidenceObject(
            evidence_id="visual_fig_1",
            kind="figure",
            page=0,
            figure_id="fig_1",
            caption="Fig. 1. Caption-only workflow.",
            status="unknown",
            failure_reason="caption_only",
            linked_claim_ids=["c1"],
            source_artifact="figure_captions.json",
        ),
        VisualEvidenceObject(
            evidence_id="visual_table_1",
            kind="table",
            page=1,
            table_id="T1",
            status="partially_observed",
            extracted_values=[
                VisualExtractedValue(label="group", value="treated", table_id="T1", cell_id="r2c1"),
                VisualExtractedValue(label="mean", value="12.4", table_id="T1", cell_id="r2c2"),
            ],
            linked_claim_ids=["c3"],
            source_artifact="document_artifact.json",
        ),
        VisualEvidenceObject(
            evidence_id="visual_table_2",
            kind="table",
            page=2,
            table_id="T2",
            status="unknown",
            failure_reason="table_parse_failed",
            source_artifact="document_artifact.json",
        ),
    ]
    return VisualEvidenceLedger(
        paper_id="paper-1",
        run_id="run-1",
        generated_at=datetime.now(timezone.utc),
        entries=entries,
        metrics=VisualEvidenceMetrics(
            entry_count=3,
            observed_count=0,
            partially_observed_count=1,
            unknown_count=2,
            unsupported_count=0,
            linked_claim_count=2,
        ),
    )


def _visual_evidence_with_figure_table_conflict() -> VisualEvidenceLedger:
    ledger = _visual_evidence().model_copy(deep=True)
    ledger.entries.append(
        VisualEvidenceObject(
            evidence_id="visual_conflict_1",
            kind="other",
            page=3,
            figure_id="fig_2",
            table_id="T1",
            caption="Figure and table imply different treated means.",
            status="unsupported",
            failure_reason="figure_table_conflict",
            linked_claim_ids=["c3"],
            not_allowed_claims=["Do not silently choose the figure value over the table value."],
            source_artifact="visual_evidence_ledger.json",
        )
    )
    ledger.metrics = VisualEvidenceMetrics(
        entry_count=len(ledger.entries),
        observed_count=sum(1 for entry in ledger.entries if entry.status == "observed"),
        partially_observed_count=sum(1 for entry in ledger.entries if entry.status == "partially_observed"),
        unknown_count=sum(1 for entry in ledger.entries if entry.status == "unknown"),
        unsupported_count=sum(1 for entry in ledger.entries if entry.status == "unsupported"),
        linked_claim_count=len({claim_id for entry in ledger.entries for claim_id in entry.linked_claim_ids}),
    )
    return ledger


def _visual_evidence_with_ambiguous_panel() -> VisualEvidenceLedger:
    ledger = _visual_evidence().model_copy(deep=True)
    ledger.entries.append(
        VisualEvidenceObject(
            evidence_id="visual_ambiguous_panel_1",
            kind="figure",
            page=4,
            figure_id="fig_3",
            caption="Figure 3 has multiple panels with unclear claim linkage.",
            status="unknown",
            failure_reason="ambiguous_panel",
            linked_claim_ids=["c4"],
            inferred_notes=["Panel label could not be tied to the extracted claim."],
            source_artifact="visual_evidence_ledger.json",
        )
    )
    ledger.metrics = VisualEvidenceMetrics(
        entry_count=len(ledger.entries),
        observed_count=sum(1 for entry in ledger.entries if entry.status == "observed"),
        partially_observed_count=sum(1 for entry in ledger.entries if entry.status == "partially_observed"),
        unknown_count=sum(1 for entry in ledger.entries if entry.status == "unknown"),
        unsupported_count=sum(1 for entry in ledger.entries if entry.status == "unsupported"),
        linked_claim_count=len({claim_id for entry in ledger.entries for claim_id in entry.linked_claim_ids}),
    )
    return ledger


def _visual_evidence_with_not_allowed_claim() -> VisualEvidenceLedger:
    ledger = _visual_evidence().model_copy(deep=True)
    ledger.entries.append(
        VisualEvidenceObject(
            evidence_id="visual_not_allowed_1",
            kind="figure",
            page=5,
            figure_id="fig_4",
            caption="Figure 4 does not support a survival benefit claim.",
            status="unsupported",
            failure_reason="other",
            linked_claim_ids=["c1"],
            not_allowed_claims=["Treatment not improved survival."],
            source_artifact="visual_evidence_ledger.json",
        )
    )
    ledger.metrics = VisualEvidenceMetrics(
        entry_count=len(ledger.entries),
        observed_count=sum(1 for entry in ledger.entries if entry.status == "observed"),
        partially_observed_count=sum(1 for entry in ledger.entries if entry.status == "partially_observed"),
        unknown_count=sum(1 for entry in ledger.entries if entry.status == "unknown"),
        unsupported_count=sum(1 for entry in ledger.entries if entry.status == "unsupported"),
        linked_claim_count=len({claim_id for entry in ledger.entries for claim_id in entry.linked_claim_ids}),
    )
    return ledger


def _visual_evidence_with_table_value_mismatch() -> VisualEvidenceLedger:
    ledger = _visual_evidence().model_copy(deep=True)
    ledger.entries[1].extracted_values[1].value = "11.0"
    return ledger


def _visual_evidence_with_figure_observation(observed_text: str) -> VisualEvidenceLedger:
    ledger = _visual_evidence().model_copy(deep=True)
    ledger.entries.append(
        VisualEvidenceObject(
            evidence_id="visual_fig_2",
            kind="figure",
            page=2,
            figure_id="fig_2",
            caption="Figure 2 visual evidence.",
            status="observed",
            observed_text=[observed_text],
            linked_claim_ids=["c1"],
            source_artifact="visual_evidence_ledger.json",
        )
    )
    ledger.metrics = VisualEvidenceMetrics(
        entry_count=len(ledger.entries),
        observed_count=sum(1 for entry in ledger.entries if entry.status == "observed"),
        partially_observed_count=sum(1 for entry in ledger.entries if entry.status == "partially_observed"),
        unknown_count=sum(1 for entry in ledger.entries if entry.status == "unknown"),
        unsupported_count=sum(1 for entry in ledger.entries if entry.status == "unsupported"),
        linked_claim_count=len({claim_id for entry in ledger.entries for claim_id in entry.linked_claim_ids}),
    )
    return ledger


def _acceptance_contract() -> DeepReadAcceptanceContract:
    return DeepReadAcceptanceContract(
        paper_id="paper-1",
        run_id="run-1",
        expected_outputs=[
            "document_artifact.json",
            "claimset.resolved.json",
            "evidence_grounding_scorecard.json",
            "missing_downstream_artifact.json",
        ],
    )


def _quality_gate(review_ready: bool = True) -> DeepReadQualityGate:
    return DeepReadQualityGate(
        paper_id="paper-1",
        run_id="run-1",
        overall_status="pass" if review_ready else "warn",
        current_promotion_candidate=True,
        review_ready=review_ready,
        hard_fail_codes=[] if review_ready else ["MISSING_CLAIMSET_RESOLVED"],
        checks=[
            DeepReadQualityGateCheck(name="claimset_resolved", status="pass"),
            DeepReadQualityGateCheck(name="scorecard_written", status="pass"),
            DeepReadQualityGateCheck(name="review_ready", status="pass" if review_ready else "warn"),
        ],
    )


def _write_raw_deepread_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True)
    text = "Treatment improved survival in Figure 2. The study was limited by small sample size."
    document = DocumentArtifact(
        doc_id="doc-1",
        source=SourceInfo(type="pdf", ref="paper.pdf"),
        metadata=PaperMetadata(title="Example Paper", authors=["A. Researcher"], year=2026),
        sections=[
            Section(
                name="results",
                text=text,
                char_start=0,
                char_end=len(text),
                page_start=1,
                page_end=1,
            )
        ],
    )
    index = IndexArtifact(
        doc_id="doc-1",
        vector_store_id="vs-1",
        chunk_count=1,
        chunks=[
            DocumentChunk(
                chunk_id="chunk-results",
                text=text,
                section_name="results",
                page_hint=1,
            )
        ],
    )
    claimset = ClaimSet(
        doc_id="doc-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="finding",
                statement="Treatment improved survival in Figure 2.",
                evidence_spans=[
                    EvidenceSpan(
                        page=0,
                        chunk_id="chunk-results",
                        raw_text="Treatment improved survival in Figure 2.",
                        quote="Treatment improved survival",
                        rationale="The result sentence supports the claim.",
                    )
                ],
                limitations=["The study was limited by small sample size."],
                confidence=0.9,
            )
        ],
    )
    (run_dir / "document_artifact.json").write_text(document.model_dump_json(), encoding="utf-8")
    (run_dir / "index_artifact.json").write_text(index.model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.json").write_text(claimset.model_dump_json(), encoding="utf-8")


def _resolved_claimset() -> ClaimSet:
    return ClaimSet(
        doc_id="doc-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="finding",
                statement="Treatment improved survival in Figure 2.",
                evidence_spans=[
                    EvidenceSpan(
                        page=2,
                        chunk_id="chunk-results",
                        raw_text="Treatment improved survival in Figure 2.",
                        quote="Treatment improved survival",
                        rationale="The result is reported with a Figure 2 reference.",
                    )
                ],
                limitations=["The study was limited by small sample size."],
                confidence=0.9,
            ),
            ScientificClaim(
                claim_id="c2",
                type="finding",
                statement="Participants were randomized using blocked allocation.",
                evidence_spans=[
                    EvidenceSpan(
                        page=4,
                        chunk_id="chunk-methods",
                        raw_text="Participants were randomized using blocked allocation.",
                        quote="randomized using blocked allocation",
                        rationale="The methods section states the allocation procedure.",
                    )
                ],
                confidence=0.7,
            ),
            ScientificClaim(
                claim_id="c3",
                type="finding",
                statement="Table T1 reports a treated mean of 12.4.",
                evidence_spans=[
                    EvidenceSpan(
                        page=5,
                        chunk_id="chunk-table",
                        raw_text="treated mean 12.4",
                        quote="12.4",
                        rationale="The parsed table cell reports the value.",
                        table_id="T1",
                        cell_id="r2c2",
                    )
                ],
                confidence=0.8,
            ),
            ScientificClaim(
                claim_id="c4",
                type="finding",
                statement="The intervention eliminates all future relapse.",
                evidence_spans=[
                    EvidenceSpan(
                        page=8,
                        chunk_id="chunk-discussion",
                        raw_text="Future relapse was not assessed.",
                        quote="Future relapse was not assessed.",
                        rationale="This does not support the stronger statement.",
                    )
                ],
                confidence=0.4,
            ),
        ],
    )


def _resolved_claimset_with_figure_locator_mismatch() -> ClaimSet:
    claimset = _resolved_claimset().model_copy(deep=True)
    claimset.claims[0].evidence_spans[0].page = 7
    return claimset


def _resolved_claimset_with_table_locator_mismatch() -> ClaimSet:
    claimset = _resolved_claimset().model_copy(deep=True)
    claimset.claims[2].evidence_spans[0].page = 6
    claimset.claims[2].evidence_spans[0].quote = "11.0"
    claimset.claims[2].evidence_spans[0].raw_text = "treated mean 11.0"
    return claimset


def _resolved_claimset_with_direct_contradiction() -> ClaimSet:
    claimset = _resolved_claimset().model_copy(deep=True)
    claimset.claims[0].statement = "Treatment did not improve survival in Figure 2."
    return claimset


def _resolved_claimset_with_claim_evidence_direct_contradiction() -> ClaimSet:
    claimset = _resolved_claimset().model_copy(deep=True)
    claimset.claims[0].statement = "Treatment improved survival in Figure 2."
    claimset.claims[0].evidence_spans[0].quote = "Survival was not improved by treatment"
    claimset.claims[0].evidence_spans[0].raw_text = "Survival was not improved by treatment in Figure 2."
    return claimset


def _paper_understanding_gold() -> PaperUnderstandingGold:
    return PaperUnderstandingGold(
        paper_id="paper-1",
        citation=PaperUnderstandingGoldMetadata(title="Gold Paper"),
        paper_type="primary_research",
        domain_tags=["clinical"],
        important_figures=[PaperUnderstandingGoldFigure(figure_id="fig_2", label="Figure 2", page=2)],
        important_tables=[PaperUnderstandingGoldTable(table_id="T1", label="Table 1", page=5)],
        gold_claims=[
            PaperUnderstandingGoldStatement(
                statement_id="g-claim-1",
                kind="claim",
                text="Treatment improved survival.",
                evidence_refs=[
                    PaperUnderstandingGoldEvidenceLocator(
                        page=2,
                        chunk_id="chunk-results",
                        quote="Treatment improved survival",
                        figure_id="fig_2",
                    )
                ],
            )
        ],
        gold_methods=[
            PaperUnderstandingGoldStatement(
                statement_id="g-method-1",
                kind="method",
                text="Participants were randomized using blocked allocation.",
                evidence_refs=[
                    PaperUnderstandingGoldEvidenceLocator(
                        page=4,
                        chunk_id="chunk-methods",
                        quote="randomized using blocked allocation",
                    )
                ],
            )
        ],
        gold_results=[
            PaperUnderstandingGoldStatement(
                statement_id="g-result-1",
                kind="result",
                text="Table 1 reports a treated mean of 12.4.",
                evidence_refs=[
                    PaperUnderstandingGoldEvidenceLocator(
                        page=5,
                        table_id="T1",
                        cell_id="r2c2",
                        quote="12.4",
                    )
                ],
            )
        ],
        gold_limitations=[
            PaperUnderstandingGoldStatement(
                statement_id="g-limitation-1",
                kind="limitation",
                text="The study was limited by small sample size.",
                evidence_refs=[
                    PaperUnderstandingGoldEvidenceLocator(
                        page=9,
                        chunk_id="chunk-limitations",
                        quote="limited by small sample size",
                    )
                ],
            )
        ],
    )


def _paper_understanding_gold_with_overstatement_label() -> PaperUnderstandingGold:
    gold = _paper_understanding_gold()
    gold.gold_claims[0].review_failure_codes = ["OVERSTATED_RESULT"]
    return gold


def _paper_understanding_gold_with_contradiction_label() -> PaperUnderstandingGold:
    gold = _paper_understanding_gold()
    gold.gold_claims[0].review_failure_codes = ["CONTRADICTED_RESULT"]
    return gold


def _paper_understanding_gold_with_gap() -> PaperUnderstandingGold:
    gold = _paper_understanding_gold()
    gold.gold_gaps = [
        PaperUnderstandingGoldStatement(
            statement_id="g-gap-1",
            kind="gap",
            text="Future relapse was not assessed.",
            evidence_refs=[
                PaperUnderstandingGoldEvidenceLocator(
                    page=8,
                    chunk_id="chunk-discussion",
                    quote="Future relapse was not assessed.",
                )
            ],
        )
    ]
    return gold


def _paper_understanding_gold_with_metadata() -> PaperUnderstandingGold:
    gold = _paper_understanding_gold()
    gold.citation = PaperUnderstandingGoldMetadata(
        doi="10.1000/gold",
        pmid="12345",
        title="Gold Paper",
        authors=["Ada Lovelace", "Grace Hopper"],
        year=2024,
    )
    return gold


def _paper_understanding_gold_with_sections() -> PaperUnderstandingGold:
    gold = _paper_understanding_gold()
    gold.gold_claims[0].evidence_refs[0].section = "Results"
    gold.gold_methods[0].evidence_refs[0].section = "Methods"
    gold.gold_results[0].evidence_refs[0].section = "Results"
    gold.gold_limitations[0].evidence_refs[0].section = "Discussion"
    return gold


def _document_artifact_with_metadata(**overrides: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "doi": "https://doi.org/10.1000/gold",
        "pmid": "12345",
        "title": "Gold Paper",
        "authors": ["Ada Lovelace", "Other Author"],
        "year": 2024,
    }
    metadata.update(overrides)
    return {
        "document_id": "doc-1",
        "meta": metadata,
        "pages": [],
        "tables": [],
        "schema_version": "2.0",
    }


def _document_artifact_with_sections() -> dict[str, object]:
    document = _document_artifact_with_metadata()
    document["sections"] = [
        {
            "name": "Methods",
            "text": "Participants were randomized using blocked allocation.",
            "char_start": 0,
            "char_end": 56,
            "page_start": 4,
            "page_end": 4,
        },
        {
            "name": "Results",
            "text": "Treatment improved survival. Table 1 reports a treated mean of 12.4.",
            "char_start": 57,
            "char_end": 126,
            "page_start": 2,
            "page_end": 5,
        },
        {
            "name": "Discussion",
            "text": "The study was limited by small sample size.",
            "char_start": 127,
            "char_end": 171,
            "page_start": 9,
            "page_end": 9,
        },
    ]
    return document


def _reviewed_eval_fixture(
    *,
    paper_id: str = "paper-1",
    run_id: str = "run-1",
    claim_id: str = "c1",
    source_correction_id: str = "correction-reviewed-c1",
) -> ClaimEvidenceCorrectionReviewedEvalFixture:
    return ClaimEvidenceCorrectionReviewedEvalFixture(
        source_decision_id=f"decision-{source_correction_id}",
        intake_id=f"intake-{source_correction_id}",
        reviewed_at=datetime.now(timezone.utc),
        reviewer_id="reviewer-1",
        review_notes="claim and locator verified",
        source_candidate=ClaimEvidenceCorrectionEvalCandidate(
            source_correction_id=source_correction_id,
            source_feedback_id=f"feedback-{source_correction_id}",
            paper_id=paper_id,
            run_id=run_id,
            claim_id=claim_id,
            field_path="claims[0]",
            before_claim_text="Treatment proves broad benefit.",
            after_claim_text="Treatment improved survival.",
            before_evidence_refs=[
                ClaimEvidenceCorrectionLocator(page=2, chunk_id="chunk-results", quote="Treatment improved survival")
            ],
            after_evidence_refs=[
                ClaimEvidenceCorrectionLocator(page=2, chunk_id="chunk-results", quote="Treatment improved survival")
            ],
            reason_codes=["OVERSTATED_RESULT"],
            reviewer_id="reviewer-1",
            feedback_export_status="linked",
        ),
    )


def _correction_case(
    *,
    correction_id: str,
    claim_id: str,
    accepted_for_eval: bool,
    feedback_export_status: str = "not_applicable",
    related_feedback_id: str | None = None,
    paper_id: str = "paper-1",
    run_id: str = "run-1",
) -> ClaimEvidenceCorrectionCase:
    lineage = (
        {
            "parser_version": "parser-v2",
            "llm_provider": "local",
            "llm_model": "reader-model",
            "llm_model_version": "reader-model-2026-05-22",
            "prompt_version": "grounding-prompt-v2",
            "reader_profile_version": "reader-profile-v2",
        }
        if accepted_for_eval
        else {}
    )
    return ClaimEvidenceCorrectionCase(
        correction_id=correction_id,
        paper_id=paper_id,
        run_id=run_id,
        claim_id=claim_id,
        field_path=f"claims[{claim_id}]",
        before_claim_text="Treatment proves broad benefit.",
        after_claim_text="Treatment improved survival.",
        before_evidence_refs=[
            ClaimEvidenceCorrectionLocator(page=2, chunk_id="chunk-results", quote="Treatment improved survival")
        ],
        after_evidence_refs=[
            ClaimEvidenceCorrectionLocator(page=2, chunk_id="chunk-results", quote="Treatment improved survival")
        ],
        reason_codes=["OVERSTATED_RESULT"],
        reviewer_id="reviewer-1",
        accepted_for_eval=accepted_for_eval,
        related_feedback_id=related_feedback_id,
        feedback_export_status=feedback_export_status,  # type: ignore[arg-type]
        **lineage,
    )


def test_build_evidence_grounding_scorecard_separates_proxy_from_gold_metrics():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    )

    assert scorecard.schema_version == "evidence_grounding_scorecard.v1"
    assert scorecard.layer == "review_gate_artifact"
    assert scorecard.canonical_status == "non_canonical"
    assert scorecard.readiness_status == "warn"
    assert scorecard.source_artifacts == [
        "reader_eval.json",
        "claimset_coverage.json",
        "evidence_extraction_bundle.json",
        "visual_evidence_ledger.json",
    ]
    assert [
        (diagnostic.artifact, diagnostic.status, diagnostic.core_scorecard_input)
        for diagnostic in scorecard.input_artifact_diagnostics
    ] == [
        ("reader_eval.json", "loaded", True),
        ("claimset_coverage.json", "loaded", True),
        ("evidence_extraction_bundle.json", "loaded", True),
        ("visual_evidence_ledger.json", "loaded", True),
    ]
    assert scorecard.input_artifact_summary.source_artifact_count == 4
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 4
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4


def test_scorecard_readiness_warns_when_p0_gold_metrics_missing() -> None:
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(status="pass"),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        paper_understanding_gold=None,
    )

    assert scorecard.readiness_status == "warn"
    assert "missing_p0_gold_metrics" in scorecard.reason_codes


def test_scorecard_readiness_warns_when_accepted_corrections_are_not_replayable() -> None:
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(status="pass"),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        correction_cases=[
            _correction_case(
                correction_id="correction-unlinked",
                claim_id="c1",
                accepted_for_eval=True,
                feedback_export_status="pending",
                related_feedback_id=None,
            )
        ],
    )

    assert scorecard.readiness_status == "warn"
    assert "accepted_corrections_not_replayable" in scorecard.reason_codes
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 0

    proxy = scorecard.runtime_proxy_metrics
    assert proxy.input_artifact_coverage_rate.value == 1.0
    assert proxy.missing_input_artifact_count.value == 0
    assert proxy.malformed_input_artifact_count.value == 0
    assert proxy.claim_count.value == 4
    assert proxy.evidence_span_count.value == 5
    assert proxy.grounded_evidence_ratio.value == 0.6
    assert proxy.unresolved_grounding_rate.value == 0.2
    assert proxy.unsupported_claim_rate_proxy.value == 0.25
    assert proxy.unknown_claim_rate_proxy.value == 0.5
    assert proxy.low_overlap_claim_rate.value == 0.25
    assert proxy.missing_location_claim_count.value == 1
    assert proxy.grounded_limitation_rate_proxy.value == 0.5
    assert proxy.page_coverage_ratio.value == 0.3
    assert proxy.missing_topic_signal_count.value == 2
    assert proxy.duplicate_cluster_count.value == 1
    assert proxy.evidence_extraction_record_count.value == 4
    assert proxy.evidence_backed_extraction_rate.value == 0.75
    assert proxy.grounded_extraction_ref_rate.value == 0.5
    assert proxy.visual_evidence_entry_count.value == 3
    assert proxy.visual_evidence_claim_link_rate.value == 0.6667
    assert proxy.visual_evidence_unknown_rate.value == 0.6667
    assert proxy.visual_evidence_unsupported_rate.value == 0.0
    assert proxy.caption_only_figure_count.value == 1
    assert proxy.table_parse_failure_count.value == 1
    assert proxy.table_cell_value_count.value == 2
    assert proxy.figure_table_conflict_count.value == 0
    assert scorecard.failure_counts_by_code == {
        "FIGURE_CAPTION_MISLINKED": 1,
        "MISSING_CLAIM": 2,
        "TABLE_PARSE_FAILED": 1,
        "UNSUPPORTED_CLAIM": 1,
        "WEAK_OR_AMBIGUOUS_EVIDENCE": 1,
        "WRONG_LOCATOR": 1,
    }
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert stage_summary["extractor"].failure_count == 2
    assert stage_summary["grounding_checker"].failure_count == 4
    assert stage_summary["parser"].failure_count == 1
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["unknown"].runtime_proxy_metrics["input_artifact_coverage_rate"].value == 1.0
    assert stage_metrics["unknown"].runtime_proxy_metrics["missing_input_artifact_count"].value == 0
    assert stage_metrics["unknown"].runtime_proxy_metrics["malformed_input_artifact_count"].value == 0
    assert stage_metrics["extractor"].runtime_proxy_metrics["claim_count"].value == 4
    assert stage_metrics["extractor"].runtime_proxy_metrics["missing_topic_signal_count"].value == 2
    assert stage_metrics["grounding_checker"].runtime_proxy_metrics["grounded_evidence_ratio"].value == 0.6
    assert stage_metrics["grounding_checker"].runtime_proxy_metrics["missing_location_claim_count"].value == 1
    assert stage_metrics["parser"].runtime_proxy_metrics["table_parse_failure_count"].value == 1
    assert "classifier" not in stage_metrics

    gold = scorecard.gold_scored_metrics
    assert gold.claim_precision.status == "not_available"
    assert gold.claim_precision.value is None
    assert gold.limitation_recall.status == "not_available"
    assert gold.figure_reference_precision.status == "not_available"
    assert gold.table_reference_precision.status == "not_available"
    assert "gold_labels_missing" in scorecard.reason_codes
    assert any("gold labels" in warning for warning in scorecard.warnings)


def test_build_evidence_grounding_scorecard_carries_candidate_lineage():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        candidate_config=EvidenceGroundingCandidateConfig(
            parser_version=" parser-v2 ",
            llm_provider="local",
            llm_model="reader-model",
            llm_model_version="reader-model-2026-05-22",
            prompt_version="grounding-prompt-v2",
            reader_profile_version="reader-profile-v2",
        ),
    )

    assert scorecard.candidate_config is not None
    assert scorecard.candidate_config.parser_version == "parser-v2"
    assert scorecard.candidate_config.llm_model_version == "reader-model-2026-05-22"


def test_build_evidence_grounding_scorecard_counts_figure_table_conflict_proxy():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence_with_figure_table_conflict(),
    )

    assert scorecard.runtime_proxy_metrics.figure_table_conflict_count.value == 1
    assert scorecard.failure_counts_by_code["FIGURE_TABLE_CONFLICT_MISSED"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert stage_summary["consistency_checker"].failure_codes == ["FIGURE_TABLE_CONFLICT_MISSED"]
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["consistency_checker"].runtime_proxy_metrics["figure_table_conflict_count"].value == 1


def test_build_evidence_grounding_scorecard_counts_ambiguous_visual_panel_proxy():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence_with_ambiguous_panel(),
    )

    assert scorecard.runtime_proxy_metrics.ambiguous_visual_panel_count.value == 1
    assert scorecard.failure_counts_by_code["WEAK_OR_AMBIGUOUS_EVIDENCE"] == 2
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "WEAK_OR_AMBIGUOUS_EVIDENCE" in stage_summary["grounding_checker"].failure_codes
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["grounding_checker"].runtime_proxy_metrics["ambiguous_visual_panel_count"].value == 1


def test_build_evidence_grounding_scorecard_counts_visual_not_allowed_claim_proxy():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence_with_not_allowed_claim(),
    )

    assert scorecard.runtime_proxy_metrics.visual_not_allowed_claim_count.value == 1
    assert scorecard.failure_counts_by_code["OVERSTATED_RESULT"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "OVERSTATED_RESULT" in stage_summary["consistency_checker"].failure_codes
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["consistency_checker"].runtime_proxy_metrics["visual_not_allowed_claim_count"].value == 1


def test_build_evidence_grounding_scorecard_counts_visual_direct_contradiction_proxy():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence_with_not_allowed_claim(),
        resolved_claimset=_resolved_claimset(),
    )

    assert scorecard.runtime_proxy_metrics.visual_direct_contradiction_count.value == 1
    assert scorecard.failure_counts_by_code["CONTRADICTED_RESULT"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "CONTRADICTED_RESULT" in stage_summary["consistency_checker"].failure_codes
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["consistency_checker"].runtime_proxy_metrics["visual_direct_contradiction_count"].value == 1


def test_build_evidence_grounding_scorecard_reports_downstream_traceability_proxy(tmp_path):
    for filename in [
        "document_artifact.json",
        "claimset.resolved.json",
        "evidence_grounding_scorecard.json",
    ]:
        (tmp_path / filename).write_text("{}", encoding="utf-8")

    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        deepread_acceptance_contract=_acceptance_contract(),
        deepread_quality_gate=_quality_gate(review_ready=False),
        artifact_dir=tmp_path,
    )

    proxy = scorecard.runtime_proxy_metrics
    assert "acceptance_contract.json" in scorecard.source_artifacts
    assert "quality_gate.json" in scorecard.source_artifacts
    assert proxy.downstream_traceability_rate.value == 0.6667
    assert proxy.handoff_review_ready.value == 0
    assert proxy.handoff_check_pass_rate.value == 0.6667
    assert proxy.handoff_hard_fail_count.value == 1
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["formatter"].runtime_proxy_metrics["downstream_traceability_rate"].value == 0.6667
    assert stage_metrics["formatter"].runtime_proxy_metrics["handoff_check_pass_rate"].value == 0.6667
    assert stage_metrics["formatter"].runtime_proxy_metrics["handoff_hard_fail_count"].value == 1


def test_downstream_traceability_is_not_available_when_contract_only_expects_scorecard_output(tmp_path):
    (tmp_path / "evidence_grounding_scorecard.json").write_text("{}", encoding="utf-8")
    contract = DeepReadAcceptanceContract(
        paper_id="paper-1",
        run_id="run-1",
        expected_outputs=["evidence_grounding_scorecard.json"],
    )

    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        deepread_acceptance_contract=contract,
        artifact_dir=tmp_path,
    )

    metric = scorecard.runtime_proxy_metrics.downstream_traceability_rate
    assert metric.status == "not_available"
    assert metric.value is None
    assert metric.source == "acceptance_contract.expected_outputs + run_dir"
    assert "No non-scorecard expected outputs" in (metric.detail or "")
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert "formatter" not in stage_metrics


def test_build_evidence_grounding_scorecard_reports_correction_loop_proxy_metrics():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        correction_cases=[
            _correction_case(
                correction_id="corr-linked",
                claim_id="c1",
                accepted_for_eval=True,
                feedback_export_status="linked",
                related_feedback_id="feedback-1",
            ),
            _correction_case(
                correction_id="corr-pending",
                claim_id="c2",
                accepted_for_eval=True,
                feedback_export_status="pending",
            ),
            _correction_case(
                correction_id="corr-review-only",
                claim_id="c3",
                accepted_for_eval=False,
            ),
            _correction_case(
                correction_id="corr-other-run",
                claim_id="c4",
                accepted_for_eval=True,
                run_id="run-other",
            ),
        ],
        reviewed_eval_fixtures=[_reviewed_eval_fixture()],
    )

    proxy = scorecard.runtime_proxy_metrics
    assert proxy.review_burden_per_paper.value == 3
    assert proxy.accepted_correction_rate.value == 0.6667
    assert proxy.correction_reuse_candidate_rate.value == 0.6667
    assert proxy.correction_feedback_link_rate.value == 0.5
    assert proxy.reviewed_eval_fixture_count.value == 1
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["grounding_checker"].runtime_proxy_metrics["review_burden_per_paper"].value == 3
    assert stage_metrics["grounding_checker"].runtime_proxy_metrics["correction_feedback_link_rate"].value == 0.5


def test_build_evidence_grounding_scorecard_scores_gold_metrics_when_gold_and_claimset_are_attached():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold(),
    )

    gold = scorecard.gold_scored_metrics
    assert "gold_metrics_scored" in scorecard.reason_codes
    assert "gold_labels_missing" not in scorecard.reason_codes
    assert "claimset.resolved.json" in scorecard.source_artifacts
    assert "paper_understanding_gold.json" in scorecard.source_artifacts
    assert gold.claim_precision.status == "available"
    assert gold.claim_precision.value == 0.5
    assert gold.claim_recall.value == 1.0
    assert gold.unsupported_claim_rate.value == 0.5
    assert gold.evidence_support_precision.value == 0.75
    assert gold.locator_precision.value == 0.75
    assert gold.limitation_recall.value == 1.0
    assert gold.gap_recall.status == "not_available"
    assert gold.method_result_confusion_rate.value == 0.5
    assert gold.figure_reference_precision.value == 1.0
    assert gold.table_reference_precision.value == 1.0
    assert gold.table_cell_locator_precision.value == 1.0
    assert gold.table_cell_value_accuracy.value == 1.0
    assert gold.figure_caption_link_accuracy.value == 1.0
    assert gold.figure_visual_text_accuracy.status == "not_available"
    assert gold.metadata_match_rate.status == "not_available"
    assert gold.parser_section_accuracy.status == "not_available"
    assert gold.overstatement_rate.status == "not_available"
    assert scorecard.failure_counts_by_code == {
        "FIGURE_CAPTION_MISLINKED": 1,
        "METHOD_AS_RESULT": 1,
        "TABLE_PARSE_FAILED": 1,
        "UNSUPPORTED_CLAIM": 2,
        "WEAK_OR_AMBIGUOUS_EVIDENCE": 1,
        "WRONG_EVIDENCE": 1,
        "WRONG_LOCATOR": 1,
    }
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert stage_summary["classifier"].failure_codes == ["METHOD_AS_RESULT"]
    assert "consistency_checker" not in stage_summary
    assert stage_summary["grounding_checker"].failure_count == 6
    assert "extractor" not in stage_summary
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["extractor"].gold_scored_metrics["claim_recall"].value == 1.0
    assert stage_metrics["classifier"].gold_scored_metrics["method_result_confusion_rate"].value == 0.5
    assert stage_metrics["consistency_checker"].gold_scored_metrics["limitation_recall"].value == 1.0
    assert stage_metrics["grounding_checker"].gold_scored_metrics["evidence_support_precision"].value == 0.75
    assert stage_metrics["grounding_checker"].gold_scored_metrics["locator_precision"].value == 0.75
    assert stage_metrics["parser"].gold_scored_metrics["table_cell_value_accuracy"].value == 1.0


def test_build_evidence_grounding_scorecard_refuses_mismatched_gold_identity():
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})

    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=mismatched_gold,
    )

    assert scorecard.readiness_status == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in scorecard.reason_codes
    assert "gold_metrics_scored" not in scorecard.reason_codes
    assert "gold_labels_missing" not in scorecard.reason_codes
    assert "paper_understanding_gold.json" not in scorecard.source_artifacts
    assert scorecard.gold_scored_metrics.claim_precision.status == "not_available"
    assert scorecard.gold_scored_metrics.claim_precision.value is None
    assert any(
        "paper_understanding_gold paper_id mismatch: expected paper-1, got paper-2" in warning
        for warning in scorecard.warnings
    )


def test_build_evidence_grounding_scorecard_rejects_without_core_inputs():
    with pytest.raises(ValueError, match="at least one loadable core scorecard sidecar"):
        build_evidence_grounding_scorecard(
            paper_id="paper-1",
            doc_id="doc-1",
            run_id="run-1",
        )


def test_build_evidence_grounding_scorecard_rejects_spoofed_loaded_core_diagnostics_without_core_inputs():
    with pytest.raises(ValueError, match="at least one loadable core scorecard sidecar"):
        build_evidence_grounding_scorecard(
            paper_id="paper-1",
            doc_id="doc-1",
            run_id="run-1",
            input_artifact_diagnostics=[
                EvidenceGroundingInputArtifactDiagnostic(
                    artifact="reader_eval.json",
                    status="loaded",
                    core_scorecard_input=True,
                )
            ],
        )


def test_build_evidence_grounding_scorecard_reconciles_core_diagnostics_with_actual_inputs():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        input_artifact_diagnostics=[
            EvidenceGroundingInputArtifactDiagnostic(
                artifact="reader_eval.json",
                status="missing",
                core_scorecard_input=True,
            ),
            EvidenceGroundingInputArtifactDiagnostic(
                artifact="candidate_config.json",
                status="loaded",
                core_scorecard_input=False,
            ),
        ],
    )

    diagnostics = {diagnostic.artifact: diagnostic for diagnostic in scorecard.input_artifact_diagnostics}
    assert diagnostics["reader_eval.json"].status == "loaded"
    assert diagnostics["candidate_config.json"].status == "loaded"
    assert scorecard.runtime_proxy_metrics.input_artifact_coverage_rate.value == 0.25
    assert scorecard.runtime_proxy_metrics.missing_input_artifact_count.value == 3


def test_build_evidence_grounding_scorecard_scores_metadata_match_when_gold_and_document_are_attached():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold_with_metadata(),
        document_artifact=_document_artifact_with_metadata(),
    )

    assert "document_artifact.json" in scorecard.source_artifacts
    assert scorecard.gold_scored_metrics.metadata_match_rate.status == "available"
    assert scorecard.gold_scored_metrics.metadata_match_rate.value == 1.0
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["metadata_resolver"].gold_scored_metrics["metadata_match_rate"].value == 1.0
    assert "DOI_MISMATCH" not in scorecard.failure_counts_by_code
    assert "METADATA_MISMATCH" not in scorecard.failure_counts_by_code


def test_build_evidence_grounding_scorecard_counts_metadata_mismatch_when_document_identity_differs():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold_with_metadata(),
        document_artifact=_document_artifact_with_metadata(doi="10.9999/wrong", title="Wrong Paper"),
    )

    assert scorecard.gold_scored_metrics.metadata_match_rate.status == "available"
    assert scorecard.gold_scored_metrics.metadata_match_rate.value == 0.6
    assert scorecard.failure_counts_by_code["DOI_MISMATCH"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert stage_summary["metadata_resolver"].failure_codes == ["DOI_MISMATCH"]


def test_build_evidence_grounding_scorecard_scores_parser_section_accuracy_when_gold_sections_are_attached():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold_with_sections(),
        document_artifact=_document_artifact_with_sections(),
    )

    assert scorecard.gold_scored_metrics.parser_section_accuracy.status == "available"
    assert scorecard.gold_scored_metrics.parser_section_accuracy.value == 1.0
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["parser"].gold_scored_metrics["parser_section_accuracy"].value == 1.0


def test_build_evidence_grounding_scorecard_scores_parser_section_mismatch():
    document = _document_artifact_with_sections()
    document["sections"][1]["text"] = "A different result section without the gold evidence quote."

    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold_with_sections(),
        document_artifact=document,
    )

    assert scorecard.gold_scored_metrics.parser_section_accuracy.status == "available"
    assert scorecard.gold_scored_metrics.parser_section_accuracy.value == 0.5


def test_build_evidence_grounding_scorecard_requires_figure_locator_context_when_gold_has_page_or_quote():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        resolved_claimset=_resolved_claimset_with_figure_locator_mismatch(),
        paper_understanding_gold=_paper_understanding_gold(),
    )

    assert scorecard.gold_scored_metrics.figure_reference_precision.value == 0.0
    assert scorecard.gold_scored_metrics.figure_caption_link_accuracy.value == 0.0
    assert scorecard.failure_counts_by_code["FIGURE_CAPTION_MISLINKED"] == 1


def test_build_evidence_grounding_scorecard_requires_table_locator_context_when_gold_has_page_or_quote():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        resolved_claimset=_resolved_claimset_with_table_locator_mismatch(),
        paper_understanding_gold=_paper_understanding_gold(),
    )

    assert scorecard.gold_scored_metrics.table_reference_precision.value == 0.0
    assert scorecard.gold_scored_metrics.table_cell_locator_precision.value == 0.0


def test_build_evidence_grounding_scorecard_scores_table_cell_value_accuracy_from_visual_evidence():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence_with_table_value_mismatch(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold(),
    )

    assert scorecard.gold_scored_metrics.table_cell_locator_precision.value == 1.0
    assert scorecard.gold_scored_metrics.table_cell_value_accuracy.value == 0.0
    assert scorecard.failure_counts_by_code["TABLE_VALUE_MISMATCH"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "TABLE_VALUE_MISMATCH" in stage_summary["parser"].failure_codes
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["parser"].gold_scored_metrics["table_cell_value_accuracy"].value == 0.0


def test_build_evidence_grounding_scorecard_scores_figure_visual_text_accuracy_from_visual_evidence():
    matching = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence_with_figure_observation("Treatment improved survival in the plotted group."),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold(),
    )

    assert matching.gold_scored_metrics.figure_visual_text_accuracy.value == 1.0
    assert "FIGURE_VISUAL_MISMATCH" not in matching.failure_counts_by_code

    mismatching = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence_with_figure_observation("No survival improvement was visible."),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold(),
    )

    assert mismatching.gold_scored_metrics.figure_visual_text_accuracy.value == 0.0
    assert mismatching.failure_counts_by_code["FIGURE_VISUAL_MISMATCH"] == 1
    stage_summary = {summary.stage: summary for summary in mismatching.stage_failure_summary}
    assert "FIGURE_VISUAL_MISMATCH" in stage_summary["grounding_checker"].failure_codes
    stage_metrics = {summary.stage: summary for summary in mismatching.stage_metric_summary}
    assert stage_metrics["grounding_checker"].gold_scored_metrics["figure_visual_text_accuracy"].value == 0.0


def test_build_evidence_grounding_scorecard_scores_overstatement_when_review_label_exists():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold_with_overstatement_label(),
    )

    assert scorecard.gold_scored_metrics.overstatement_rate.status == "available"
    assert scorecard.gold_scored_metrics.overstatement_rate.value == 0.25
    assert scorecard.failure_counts_by_code["OVERSTATED_RESULT"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "OVERSTATED_RESULT" in stage_summary["consistency_checker"].failure_codes


def test_build_evidence_grounding_scorecard_scores_contradiction_when_review_label_exists():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold_with_contradiction_label(),
    )

    assert scorecard.gold_scored_metrics.contradiction_rate.status == "available"
    assert scorecard.gold_scored_metrics.contradiction_rate.value == 0.25
    assert scorecard.failure_counts_by_code["CONTRADICTED_RESULT"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "CONTRADICTED_RESULT" in stage_summary["consistency_checker"].failure_codes
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["consistency_checker"].gold_scored_metrics["contradiction_rate"].value == 0.25


def test_build_evidence_grounding_scorecard_detects_direct_text_polarity_contradiction():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset_with_direct_contradiction(),
        paper_understanding_gold=_paper_understanding_gold(),
    )

    assert scorecard.gold_scored_metrics.contradiction_rate.status == "available"
    assert scorecard.gold_scored_metrics.contradiction_rate.value == 1.0
    assert "direct_text_polarity" in (scorecard.gold_scored_metrics.contradiction_rate.source or "")
    assert scorecard.failure_counts_by_code["CONTRADICTED_RESULT"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "CONTRADICTED_RESULT" in stage_summary["consistency_checker"].failure_codes


def test_build_evidence_grounding_scorecard_counts_claim_evidence_direct_contradiction_proxy():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset_with_claim_evidence_direct_contradiction(),
    )

    metric = scorecard.runtime_proxy_metrics.claim_evidence_direct_contradiction_count
    assert metric.status == "available"
    assert metric.value == 1
    assert "claimset.resolved.json" in (metric.source or "")
    assert scorecard.failure_counts_by_code["CONTRADICTED_RESULT"] == 1
    stage_summary = {summary.stage: summary for summary in scorecard.stage_failure_summary}
    assert "CONTRADICTED_RESULT" in stage_summary["consistency_checker"].failure_codes
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["consistency_checker"].runtime_proxy_metrics[
        "claim_evidence_direct_contradiction_count"
    ].value == 1


def test_build_evidence_grounding_scorecard_scores_gap_recall_when_gold_gaps_are_attached():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold_with_gap(),
    )

    assert scorecard.gold_scored_metrics.gap_recall.status == "available"
    assert scorecard.gold_scored_metrics.gap_recall.value == 1.0
    stage_metrics = {summary.stage: summary for summary in scorecard.stage_metric_summary}
    assert stage_metrics["consistency_checker"].gold_scored_metrics["gap_recall"].value == 1.0
    assert "GAP_MISSED" not in scorecard.failure_counts_by_code


def test_build_evidence_grounding_scorecard_scores_reviewed_eval_fixtures_when_gold_is_absent():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        reviewed_eval_fixtures=[_reviewed_eval_fixture()],
    )

    assert "reviewed_eval_fixture_metrics_scored" in scorecard.reason_codes
    assert "gold_labels_missing" not in scorecard.reason_codes
    assert "claim_evidence_reviewed_eval_fixtures.json" in scorecard.source_artifacts
    assert "paper_understanding_gold.json" not in scorecard.source_artifacts
    assert any("non-canonical reviewed claim/evidence correction fixtures" in warning for warning in scorecard.warnings)
    assert scorecard.gold_scored_metrics.claim_precision.status == "available"
    assert scorecard.gold_scored_metrics.claim_precision.value == 0.25
    assert scorecard.gold_scored_metrics.claim_recall.value == 1.0
    assert scorecard.gold_scored_metrics.evidence_support_precision.value == 0.25
    assert scorecard.gold_scored_metrics.locator_precision.value == 0.25
    assert scorecard.gold_scored_metrics.overstatement_rate.status == "available"
    assert scorecard.gold_scored_metrics.overstatement_rate.value == 0.25
    assert scorecard.failure_counts_by_code["OVERSTATED_RESULT"] == 1
    assert scorecard.input_artifact_summary.source_artifact_count == 6
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 4
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 0


def test_build_evidence_grounding_scorecard_uses_reviewed_eval_consistency_labels_with_gold():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        paper_understanding_gold=_paper_understanding_gold(),
        reviewed_eval_fixtures=[_reviewed_eval_fixture()],
    )

    assert "gold_metrics_scored" in scorecard.reason_codes
    assert "reviewed_eval_fixture_consistency_metrics_scored" in scorecard.reason_codes
    assert "paper_understanding_gold.json" in scorecard.source_artifacts
    assert "claim_evidence_reviewed_eval_fixtures.json" in scorecard.source_artifacts
    assert scorecard.gold_scored_metrics.claim_precision.value == 0.5
    assert scorecard.gold_scored_metrics.overstatement_rate.status == "available"
    assert scorecard.gold_scored_metrics.overstatement_rate.value == 0.25
    assert "claim_evidence_reviewed_eval_fixtures.json" in scorecard.gold_scored_metrics.overstatement_rate.source
    assert scorecard.failure_counts_by_code["OVERSTATED_RESULT"] == 1
    assert any("non-canonical reviewed claim/evidence correction fixtures" in warning for warning in scorecard.warnings)
    assert scorecard.input_artifact_summary.source_artifact_count == 7
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 4
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 0


def test_build_evidence_grounding_scorecard_skips_reviewed_eval_fixtures_outside_run_scope():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        reviewed_eval_fixtures=[
            _reviewed_eval_fixture(),
            _reviewed_eval_fixture(
                paper_id="paper-2",
                run_id="run-2",
                claim_id="c-other",
                source_correction_id="correction-reviewed-other",
            ),
        ],
    )

    assert scorecard.readiness_status == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in scorecard.reason_codes
    assert "reviewed_eval_fixture_metrics_scored" in scorecard.reason_codes
    assert scorecard.runtime_proxy_metrics.reviewed_eval_fixture_count.value == 1
    assert scorecard.gold_scored_metrics.claim_precision.value == 0.25
    assert any(
        "reviewed eval fixtures skipped outside run scope: 1; expected paper_id=paper-1,run_id=run-1" in warning
        for warning in scorecard.warnings
    )
    assert scorecard.input_artifact_summary.source_artifact_count == 6
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 4
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 0


def test_build_evidence_grounding_scorecard_does_not_score_only_out_of_scope_reviewed_eval_fixtures():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
        resolved_claimset=_resolved_claimset(),
        reviewed_eval_fixtures=[
            _reviewed_eval_fixture(
                paper_id="paper-2",
                run_id="run-2",
                claim_id="c-other",
                source_correction_id="correction-reviewed-other",
            )
        ],
    )

    assert scorecard.readiness_status == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in scorecard.reason_codes
    assert "reviewed_eval_fixture_metrics_scored" not in scorecard.reason_codes
    assert "claim_evidence_reviewed_eval_fixtures.json" not in scorecard.source_artifacts
    assert scorecard.runtime_proxy_metrics.reviewed_eval_fixture_count.status == "not_available"
    assert scorecard.gold_scored_metrics.claim_precision.status == "not_available"
    assert scorecard.input_artifact_summary.source_artifact_count == 5
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 4
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 0


def test_scorecard_uses_available_proxy_metrics_when_coverage_is_missing():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=None,
    )

    assert scorecard.readiness_status == "warn"
    assert scorecard.source_artifacts == ["reader_eval.json"]
    assert "claimset_coverage_missing" in scorecard.reason_codes
    assert "evidence_extraction_bundle_missing" in scorecard.reason_codes
    assert "visual_evidence_ledger_missing" in scorecard.reason_codes
    assert scorecard.runtime_proxy_metrics.input_artifact_coverage_rate.value == 0.25
    assert scorecard.runtime_proxy_metrics.missing_input_artifact_count.value == 3
    assert scorecard.runtime_proxy_metrics.malformed_input_artifact_count.value == 0
    assert [
        (diagnostic.artifact, diagnostic.status)
        for diagnostic in scorecard.input_artifact_diagnostics
    ] == [
        ("reader_eval.json", "loaded"),
        ("claimset_coverage.json", "missing"),
        ("evidence_extraction_bundle.json", "missing"),
        ("visual_evidence_ledger.json", "missing"),
    ]
    assert scorecard.input_artifact_summary.source_artifact_count == 1
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 4
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 1
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 3
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 0
    assert scorecard.runtime_proxy_metrics.claim_count.status == "available"
    assert scorecard.runtime_proxy_metrics.page_coverage_ratio.status == "not_available"
    assert scorecard.runtime_proxy_metrics.evidence_extraction_record_count.status == "not_available"
    assert scorecard.gold_scored_metrics.locator_precision.status == "not_available"


def test_scorecard_rejects_stale_input_artifact_summary():
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    )
    payload = scorecard.model_dump(mode="json")
    payload["input_artifact_summary"]["source_artifact_count"] = 99

    with pytest.raises(ValidationError, match="input_artifact_summary"):
        EvidenceGroundingScorecard.model_validate(payload)


def test_scorecard_warns_when_non_reader_core_inputs_are_missing():
    clean_reader = _reader_eval().model_copy(
        update={
            "metrics": ReaderEvalMetrics(
                claim_count=2,
                supported_claim_count=2,
                unsupported_claim_count=0,
                unknown_claim_count=0,
                evidence_span_count=2,
                grounded_span_count=2,
                unresolved_span_count=0,
                ambiguous_span_count=0,
                failed_grounding_span_count=0,
                limitation_count=1,
                grounded_limitation_count=1,
                low_overlap_claim_count=0,
            ),
            "claims": [],
        }
    )
    clean_coverage = _coverage(status="pass").model_copy(
        update={
            "metrics": ClaimsetCoverageMetrics(
                claim_count=2,
                evidence_span_count=2,
                grounded_span_count=2,
                unresolved_span_count=0,
                grounded_evidence_ratio=1.0,
                document_page_count=2,
                covered_page_count=2,
                page_coverage_ratio=1.0,
                duplicate_cluster_count=0,
                missing_topic_signal_count=0,
            ),
            "recommended_next_action": "none",
            "reason_codes": [],
        }
    )

    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=clean_reader,
        claimset_coverage=clean_coverage,
    )

    assert scorecard.readiness_status == "warn"
    assert scorecard.recommended_next_action == "review_proxy_warnings_before_promotion"
    assert "evidence_extraction_bundle_missing" in scorecard.reason_codes
    assert "visual_evidence_ledger_missing" in scorecard.reason_codes
    assert scorecard.runtime_proxy_metrics.input_artifact_coverage_rate.value == 0.5
    assert scorecard.runtime_proxy_metrics.missing_input_artifact_count.value == 2


def test_scorecard_from_run_dir_warns_on_malformed_sidecar(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text("{not-json", encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(_paper_understanding_gold().model_dump_json(), encoding="utf-8")
    (run_dir / "acceptance_contract.json").write_text(_acceptance_contract().model_dump_json(), encoding="utf-8")
    (run_dir / "quality_gate.json").write_text(_quality_gate().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_corrections.jsonl").write_text(
        "\n".join(
            [
                _correction_case(
                    correction_id="corr-linked",
                    claim_id="c1",
                    accepted_for_eval=True,
                    feedback_export_status="linked",
                    related_feedback_id="feedback-1",
                ).model_dump_json(),
                _correction_case(
                    correction_id="corr-review-only",
                    claim_id="c2",
                    accepted_for_eval=False,
                ).model_dump_json(),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "document_artifact.json").write_text("{}", encoding="utf-8")
    (run_dir / "evidence_grounding_scorecard.json").write_text("{}", encoding="utf-8")

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert scorecard.paper_id == "paper-1"
    assert scorecard.doc_id == "doc-1"
    assert scorecard.run_id == "run-1"
    assert scorecard.readiness_status == "warn"
    assert "reader_eval_missing" in scorecard.reason_codes
    assert any("reader_eval.json could not be loaded" in warning for warning in scorecard.warnings)
    diagnostics = {diagnostic.artifact: diagnostic for diagnostic in scorecard.input_artifact_diagnostics}
    assert diagnostics["reader_eval.json"].status == "load_failed"
    assert diagnostics["reader_eval.json"].core_scorecard_input is True
    assert diagnostics["reader_eval.json"].detail == "JSONDecodeError"
    assert diagnostics["claimset_coverage.json"].status == "loaded"
    assert diagnostics["claim_evidence_corrections.jsonl"].status == "loaded"
    assert diagnostics["document_artifact.json"].status == "loaded"
    assert scorecard.runtime_proxy_metrics.malformed_input_artifact_count.value == 1
    assert scorecard.runtime_proxy_metrics.claim_count.value == 4
    assert scorecard.runtime_proxy_metrics.grounded_evidence_ratio.value == 0.6
    assert scorecard.runtime_proxy_metrics.evidence_extraction_record_count.value == 4
    assert scorecard.runtime_proxy_metrics.grounded_extraction_ref_rate.value == 0.5
    assert scorecard.runtime_proxy_metrics.caption_only_figure_count.value == 1
    assert scorecard.runtime_proxy_metrics.downstream_traceability_rate.value == 0.6667
    assert scorecard.runtime_proxy_metrics.handoff_review_ready.value == 1
    assert scorecard.runtime_proxy_metrics.review_burden_per_paper.value == 2
    assert scorecard.runtime_proxy_metrics.correction_reuse_candidate_rate.value == 0.5
    assert scorecard.gold_scored_metrics.claim_precision.value == 0.5


def test_scorecard_from_run_dir_refuses_mismatched_run_local_gold(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(mismatched_gold.model_dump_json(), encoding="utf-8")

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert scorecard.readiness_status == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in scorecard.reason_codes
    assert "gold_metrics_scored" not in scorecard.reason_codes
    assert "paper_understanding_gold.json" not in scorecard.source_artifacts
    assert scorecard.gold_scored_metrics.claim_precision.status == "not_available"


def test_scorecard_from_run_dir_treats_malformed_run_local_gold_as_unavailable_eval_source(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text("{not-json", encoding="utf-8")

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert scorecard.readiness_status == "warn"
    assert "gold_labels_missing" in scorecard.reason_codes
    assert "gold_metrics_scored" not in scorecard.reason_codes
    assert "paper_understanding_gold.json" not in scorecard.source_artifacts
    assert scorecard.gold_scored_metrics.claim_precision.status == "not_available"
    assert any("paper_understanding_gold.json could not be loaded" in warning for warning in scorecard.warnings)
    diagnostics = {diagnostic.artifact: diagnostic for diagnostic in scorecard.input_artifact_diagnostics}
    assert diagnostics["paper_understanding_gold.json"].status == "load_failed"
    assert diagnostics["paper_understanding_gold.json"].core_scorecard_input is False
    assert diagnostics["paper_understanding_gold.json"].detail == "JSONDecodeError"


def test_scorecard_from_run_dir_warns_on_input_sidecar_identity_mismatch(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    clean_reader = _reader_eval().model_copy(
        update={
            "metrics": ReaderEvalMetrics(
                claim_count=2,
                supported_claim_count=2,
                unsupported_claim_count=0,
                unknown_claim_count=0,
                evidence_span_count=2,
                grounded_span_count=2,
                unresolved_span_count=0,
                ambiguous_span_count=0,
                failed_grounding_span_count=0,
                limitation_count=1,
                grounded_limitation_count=1,
                low_overlap_claim_count=0,
            ),
            "claims": [],
        }
    )
    clean_coverage = _coverage(status="pass").model_copy(
        update={
            "metrics": ClaimsetCoverageMetrics(
                claim_count=2,
                evidence_span_count=2,
                grounded_span_count=2,
                unresolved_span_count=0,
                grounded_evidence_ratio=1.0,
                document_page_count=2,
                covered_page_count=2,
                page_coverage_ratio=1.0,
                duplicate_cluster_count=0,
                missing_topic_signal_count=0,
            ),
            "recommended_next_action": "none",
            "reason_codes": [],
            "paper_id": "paper-2",
            "run_id": "run-2",
            "doc_id": "doc-2",
        }
    )

    (run_dir / "reader_eval.json").write_text(clean_reader.model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(clean_coverage.model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert scorecard.paper_id == "paper-1"
    assert scorecard.readiness_status == "fail"
    assert "input_paper_id_mismatch" in scorecard.reason_codes
    assert "input_run_id_mismatch" in scorecard.reason_codes
    assert "input_doc_id_mismatch" in scorecard.reason_codes
    assert any("input sidecar paper_id mismatch: paper-1,paper-2" == warning for warning in scorecard.warnings)
    assert any("input sidecar run_id mismatch: run-1,run-2" == warning for warning in scorecard.warnings)
    assert any("input sidecar doc_id mismatch: doc-1,doc-2" == warning for warning in scorecard.warnings)
    assert any(
        "input sidecar paper_id mismatch sources: "
        "reader_eval.json=paper-1;claimset_coverage.json=paper-2;"
        "evidence_extraction_bundle.json=paper-1;visual_evidence_ledger.json=paper-1"
        == warning
        for warning in scorecard.warnings
    )
    assert any(
        "input sidecar run_id mismatch sources: "
        "reader_eval.json=run-1;claimset_coverage.json=run-2;"
        "evidence_extraction_bundle.json=run-1;visual_evidence_ledger.json=run-1"
        == warning
        for warning in scorecard.warnings
    )
    assert any(
        "input sidecar doc_id mismatch sources: "
        "reader_eval.json=doc-1;claimset_coverage.json=doc-2;evidence_extraction_bundle.json=doc-1"
        == warning
        for warning in scorecard.warnings
    )


def test_scorecard_from_run_dir_loads_reviewed_eval_fixture_sidecar_when_gold_is_absent(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps({"fixtures": [_reviewed_eval_fixture().model_dump(mode="json")]}),
        encoding="utf-8",
    )

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert "reviewed_eval_fixture_metrics_scored" in scorecard.reason_codes
    assert "claim_evidence_reviewed_eval_fixtures.json" in scorecard.source_artifacts
    assert scorecard.gold_scored_metrics.claim_precision.value == 0.25
    assert scorecard.gold_scored_metrics.overstatement_rate.value == 0.25
    assert scorecard.input_artifact_summary.source_artifact_count == 6
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 6
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 2


def test_scorecard_from_run_dir_treats_malformed_reviewed_eval_fixtures_as_unavailable_eval_source(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text("{not-json", encoding="utf-8")

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert "gold_labels_missing" in scorecard.reason_codes
    assert "reviewed_eval_fixture_metrics_scored" not in scorecard.reason_codes
    assert "claim_evidence_reviewed_eval_fixtures.json" not in scorecard.source_artifacts
    assert scorecard.gold_scored_metrics.claim_precision.status == "not_available"
    assert scorecard.runtime_proxy_metrics.reviewed_eval_fixture_count.status == "not_available"
    assert any(
        "claim_evidence_reviewed_eval_fixtures.json could not be loaded" in warning
        for warning in scorecard.warnings
    )
    diagnostics = {diagnostic.artifact: diagnostic for diagnostic in scorecard.input_artifact_diagnostics}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"].status == "load_failed"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"].core_scorecard_input is False
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"].detail == "JSONDecodeError"
    assert scorecard.input_artifact_summary.source_artifact_count == 5
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 6
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 2


def test_scorecard_from_run_dir_uses_reviewed_eval_fixture_sidecar_with_gold(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps({"fixtures": [_reviewed_eval_fixture().model_dump(mode="json")]}),
        encoding="utf-8",
    )

    scorecard = build_evidence_grounding_scorecard_from_run_dir(
        run_dir,
        paper_understanding_gold=_paper_understanding_gold(),
    )

    assert "gold_metrics_scored" in scorecard.reason_codes
    assert "reviewed_eval_fixture_consistency_metrics_scored" in scorecard.reason_codes
    assert scorecard.gold_scored_metrics.claim_precision.value == 0.5
    assert scorecard.gold_scored_metrics.overstatement_rate.value == 0.25
    assert scorecard.input_artifact_summary.source_artifact_count == 7
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 6
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 2


def test_scorecard_from_run_dir_loads_candidate_config_sidecar(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": " parser-sidecar-v2 ",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-sidecar-2026-05-22",
                "prompt_version": "grounding-prompt-sidecar-v2",
                "reader_profile_version": "reader-profile-sidecar-v2",
            }
        ),
        encoding="utf-8",
    )

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert scorecard.candidate_config is not None
    assert scorecard.candidate_config.parser_version == "parser-sidecar-v2"
    assert scorecard.candidate_config.has_complete_replay_lineage() is True
    assert "candidate_config.json" in scorecard.source_artifacts
    diagnostics = {diagnostic.artifact: diagnostic for diagnostic in scorecard.input_artifact_diagnostics}
    assert diagnostics["candidate_config.json"].status == "loaded"
    assert diagnostics["candidate_config.json"].core_scorecard_input is False
    assert scorecard.input_artifact_summary.source_artifact_count == 5
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 5
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 1


def test_scorecard_from_run_dir_warns_on_malformed_candidate_config_sidecar(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-sidecar-v2",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )

    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert scorecard.candidate_config is None
    assert "candidate_config.json" not in scorecard.source_artifacts
    assert any("candidate_config.json could not be loaded" in warning for warning in scorecard.warnings)
    diagnostics = {diagnostic.artifact: diagnostic for diagnostic in scorecard.input_artifact_diagnostics}
    assert diagnostics["candidate_config.json"].status == "load_failed"
    assert diagnostics["candidate_config.json"].core_scorecard_input is False
    assert diagnostics["candidate_config.json"].detail == "ValidationError"
    assert scorecard.input_artifact_summary.source_artifact_count == 4
    assert scorecard.input_artifact_summary.input_artifact_diagnostic_count == 5
    assert scorecard.input_artifact_summary.core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.loaded_core_input_artifact_count == 4
    assert scorecard.input_artifact_summary.missing_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.load_failed_core_input_artifact_count == 0
    assert scorecard.input_artifact_summary.non_core_input_artifact_count == 1


def test_scorecard_from_run_dir_rejects_missing_run_directory(tmp_path):
    run_dir = tmp_path / "paper-1" / "missing-run"

    with pytest.raises(ValueError, match="run_dir must be an existing directory"):
        build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert not run_dir.exists()


def test_scorecard_from_run_dir_rejects_empty_run_directory(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-empty"
    run_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="at least one loadable core scorecard sidecar"):
        build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_scorecard_input_backfill_copies_run_and_derives_core_sidecars(tmp_path):
    from src.services.evidence_grounding_benchmark import build_evidence_grounding_contract_compatibility_report

    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "scorecard_runs"
    report_out = tmp_path / "backfill_report.json"
    _write_raw_deepread_run(source_run)

    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=[
            EvidenceGroundingScorecardInputBackfillItemRequest(
                paper_id="paper-1",
                source_run_dir=str(source_run),
            )
        ],
        out_run_root=out_root,
        out=report_out,
    )

    target_run = out_root / "paper-1"
    assert report.schema_version == "evidence_grounding_scorecard_input_backfill.v1"
    assert report.canonical_status == "non_canonical"
    assert report.item_count == 1
    assert report.pass_count == 1
    assert report.fail_count == 0
    assert report.items[0].status == "pass"
    assert report.items[0].output_run_dir == str(target_run.resolve())
    assert set(report.items[0].generated_artifacts) >= {
        "claimset.resolved.json",
        "reader_eval.json",
        "claimset_coverage.json",
        "evidence_extraction_bundle.json",
        "visual_evidence_ledger.json",
        "evidence_grounding_scorecard.json",
    }
    assert report.items[0].scorecard_readiness_metrics["grounded_evidence_ratio"].status == "available"
    assert report.items[0].scorecard_readiness_metrics["page_coverage_ratio"].status == "available"
    assert report.items[0].scorecard_readiness_metrics["missing_topic_signal_count"].status == "available"
    assert not (source_run / "reader_eval.json").exists()
    assert (target_run / "reader_eval.json").exists()
    assert (target_run / "evidence_grounding_scorecard.json").exists()
    written = EvidenceGroundingScorecardInputBackfillReport.model_validate_json(
        report_out.read_text(encoding="utf-8")
    )
    assert written.pass_count == 1
    assert written.items[0].scorecard_readiness_metrics["grounded_evidence_ratio"].value is not None
    compatibility = build_evidence_grounding_contract_compatibility_report(artifact_paths=[report_out])
    assert compatibility.fail_count == 0


def test_scorecard_input_backfill_reports_repair_targets_without_evidence_text(tmp_path):
    from src.services.evidence_grounding_benchmark import build_evidence_grounding_contract_compatibility_report

    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "scorecard_runs_with_repair_targets"
    report_out = tmp_path / "backfill_report.json"
    _write_raw_deepread_run(source_run)
    claimset = ClaimSet.model_validate_json((source_run / "claimset.json").read_text(encoding="utf-8"))
    claimset.claims[0].evidence_spans[0].quote = "This exact evidence text is absent from the source."
    claimset.claims[0].evidence_spans[0].raw_text = "This exact evidence text is absent from the source."
    (source_run / "claimset.json").write_text(claimset.model_dump_json(), encoding="utf-8")

    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=[
            EvidenceGroundingScorecardInputBackfillItemRequest(
                paper_id="paper-1",
                source_run_dir=str(source_run),
            )
        ],
        out_run_root=out_root,
        out=report_out,
    )

    assert report.items[0].status == "pass"
    assert report.items[0].scorecard_readiness_status == "fail"
    assert report.items[0].scorecard_repair_targets
    target = report.items[0].scorecard_repair_targets[0]
    assert target.claim_id == "c1"
    assert target.span_index == 0
    assert target.resolution == "FAILED_MATCH"
    assert target.has_raw_text is True
    assert target.raw_text_char_count > 0
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    target_payload = payload["items"][0]["scorecard_repair_targets"][0]
    assert target_payload["claim_id"] == "c1"
    assert "This exact evidence text" not in json.dumps(target_payload)
    scorecard_payload = json.loads((out_root / "paper-1" / "evidence_grounding_scorecard.json").read_text(encoding="utf-8"))
    scorecard_target_payload = scorecard_payload["repair_targets"][0]
    assert scorecard_target_payload["claim_id"] == "c1"
    assert scorecard_target_payload["resolution"] == "FAILED_MATCH"
    assert "This exact evidence text" not in json.dumps(scorecard_target_payload)
    compatibility = build_evidence_grounding_contract_compatibility_report(artifact_paths=[report_out])
    detail = ";".join(
        finding
        for item in compatibility.items
        for finding in item.findings
    )
    assert "repair_targets=c1#0:FAILED_MATCH" in detail
    assert "This exact evidence text" not in detail


def test_scorecard_input_backfill_packages_reviewed_eval_fixtures_before_scorecard(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "scorecard_runs_with_reviewed_fixtures"
    reviewed_dir = tmp_path / "goldset" / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    reviewed_dir.mkdir(parents=True)
    _write_raw_deepread_run(source_run)
    (reviewed_dir / "intake-reviewed-c1.json").write_text(
        _reviewed_eval_fixture().model_dump_json(),
        encoding="utf-8",
    )

    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=[
            EvidenceGroundingScorecardInputBackfillItemRequest(
                paper_id="paper-1",
                source_run_dir=str(source_run),
            )
        ],
        out_run_root=out_root,
        reviewed_fixtures_dir=reviewed_dir,
    )

    target_run = out_root / "paper-1"
    scorecard_payload = json.loads((target_run / "evidence_grounding_scorecard.json").read_text(encoding="utf-8"))
    assert report.pass_count == 1
    assert report.reviewed_fixtures_dir == str(reviewed_dir.resolve())
    assert report.items[0].reviewed_eval_fixture_count == 1
    assert "claim_evidence_reviewed_eval_fixtures.json" in report.items[0].generated_artifacts
    assert (target_run / "claim_evidence_reviewed_eval_fixtures.json").exists()
    assert "claim_evidence_reviewed_eval_fixtures.json" in scorecard_payload["source_artifacts"]
    assert scorecard_payload["gold_scored_metrics"]["overstatement_rate"]["status"] == "available"


def test_scorecard_input_backfill_requires_reviewed_eval_fixtures_when_requested(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "scorecard_runs_missing_reviewed_fixtures"
    reviewed_dir = tmp_path / "goldset" / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    reviewed_dir.mkdir(parents=True)
    _write_raw_deepread_run(source_run)

    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=[
            EvidenceGroundingScorecardInputBackfillItemRequest(
                paper_id="paper-1",
                source_run_dir=str(source_run),
            )
        ],
        out_run_root=out_root,
        reviewed_fixtures_dir=reviewed_dir,
        require_reviewed_fixtures=True,
    )

    assert report.pass_count == 0
    assert report.fail_count == 1
    assert "scorecard_input_backfill_failures_present" in report.warnings
    assert "reviewed_fixtures_required_but_missing" in (report.items[0].error or "")
    assert not (out_root / "paper-1").exists()


def test_scorecard_input_backfill_derives_gold_path_from_benchmark_manifest_metadata(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    manifest_dir = tmp_path / "manifests"
    gold_path = tmp_path / "gold" / "paper-1.json"
    out_root = tmp_path / "scorecard_runs_from_manifest_gold"
    run_dir_map_out = tmp_path / "scorecard_runs_from_manifest_gold_run_dir_map.json"
    manifest_dir.mkdir()
    gold_path.parent.mkdir()
    _write_raw_deepread_run(source_run)
    gold_path.write_text(_paper_understanding_gold_with_overstatement_label().model_dump_json(), encoding="utf-8")
    manifest_path = manifest_dir / "benchmark_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "evidence_grounding_benchmark_manifest.v1",
                "benchmark_id": "manifest-gold-backfill",
                "items": [
                    {
                        "candidate_id": "candidate-paper-1",
                        "paper_id": "paper-1",
                        "run_dir": "../source/paper-1/run-1",
                        "metadata": {"source_gold_path": "../gold/paper-1.json"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    items = load_scorecard_input_backfill_items_from_benchmark_artifacts(
        benchmark_manifest_paths=[manifest_path]
    )
    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=items,
        out_run_root=out_root,
        run_dir_map_out=run_dir_map_out,
    )

    target_run = out_root / "candidate-paper-1"
    run_dir_map = json.loads(run_dir_map_out.read_text(encoding="utf-8"))
    scorecard_payload = json.loads((target_run / "evidence_grounding_scorecard.json").read_text(encoding="utf-8"))
    assert items[0].paper_understanding_gold_path == str(gold_path.resolve())
    assert report.run_dir_map_path == str(run_dir_map_out.resolve())
    assert run_dir_map == {"paper-1": str(target_run.resolve())}
    assert report.pass_count == 1
    assert "paper_understanding_gold.json" in report.items[0].generated_artifacts
    assert (target_run / "paper_understanding_gold.json").exists()
    assert "paper_understanding_gold.json" in scorecard_payload["source_artifacts"]
    assert "gold_labels_missing" not in scorecard_payload["reason_codes"]
    assert scorecard_payload["gold_scored_metrics"]["overstatement_rate"]["status"] == "available"
    assert report.items[0].scorecard_readiness_metrics["grounded_evidence_ratio"].status == "available"


def test_scorecard_input_backfill_removes_partial_output_when_generation_fails(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "scorecard_runs_failed"
    report_out = tmp_path / "failed_backfill_report.json"
    _write_raw_deepread_run(source_run)
    (source_run / "index_artifact.json").unlink()

    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=[
            EvidenceGroundingScorecardInputBackfillItemRequest(
                paper_id="paper-1",
                source_run_dir=str(source_run),
            )
        ],
        out_run_root=out_root,
        out=report_out,
    )

    target_run = out_root / "paper-1"
    assert report.fail_count == 1
    assert report.items[0].status == "fail"
    assert "index_artifact.json" in (report.items[0].error or "")
    assert "scorecard_input_backfill_failures_present" in report.warnings
    assert not target_run.exists()
    written = EvidenceGroundingScorecardInputBackfillReport.model_validate_json(
        report_out.read_text(encoding="utf-8")
    )
    assert written.fail_count == 1
    assert not target_run.exists()


def test_scorecard_input_backfill_removes_partial_output_when_copy_fails(tmp_path, monkeypatch):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "scorecard_runs_copy_failed"
    _write_raw_deepread_run(source_run)

    def fail_after_partial_copy(source, destination, *args, **kwargs):
        destination = Path(destination)
        destination.mkdir(parents=True)
        (destination / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("simulated copy failure")

    monkeypatch.setattr(
        "src.services.evidence_grounding_scorecard_input_backfill.shutil.copytree",
        fail_after_partial_copy,
    )

    report = build_evidence_grounding_scorecard_input_backfill_report(
        items=[
            EvidenceGroundingScorecardInputBackfillItemRequest(
                paper_id="paper-1",
                source_run_dir=str(source_run),
            )
        ],
        out_run_root=out_root,
    )

    target_run = out_root / "paper-1"
    assert report.fail_count == 1
    assert report.items[0].status == "fail"
    assert "simulated copy failure" in (report.items[0].error or "")
    assert "scorecard_input_backfill_failures_present" in report.warnings
    assert not target_run.exists()


def test_scorecard_input_backfill_api_writes_noncanonical_report(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "api_scorecard_runs"
    report_out = tmp_path / "api_backfill_report.json"
    _write_raw_deepread_run(source_run)
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "items": [{"paper_id": "paper-1", "source_run_dir": str(source_run)}],
            "out_run_root": str(out_root),
            "out": str(report_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard_input_backfill.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["pass_count"] == 1
    assert str(tmp_path) not in response.text
    assert (out_root / "paper-1" / "evidence_extraction_bundle.json").exists()
    assert report_out.exists()
    written = json.loads(report_out.read_text(encoding="utf-8"))
    assert written["items"][0]["source_run_dir"] == str(source_run.resolve())


def test_scorecard_input_backfill_api_reports_repair_targets_without_evidence_text(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "api_scorecard_runs_with_repair_targets"
    report_out = tmp_path / "api_backfill_repair_targets_report.json"
    missing_text = "This exact evidence text is absent from the source."
    _write_raw_deepread_run(source_run)
    claimset = ClaimSet.model_validate_json((source_run / "claimset.json").read_text(encoding="utf-8"))
    claimset.claims[0].evidence_spans[0].quote = missing_text
    claimset.claims[0].evidence_spans[0].raw_text = missing_text
    (source_run / "claimset.json").write_text(claimset.model_dump_json(), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "items": [{"paper_id": "paper-1", "source_run_dir": str(source_run)}],
            "out_run_root": str(out_root),
            "out": str(report_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pass_count"] == 1
    assert payload["scorecard_fail_count"] == 1
    target_payload = payload["items"][0]["scorecard_repair_targets"][0]
    assert target_payload["claim_id"] == "c1"
    assert target_payload["span_index"] == 0
    assert target_payload["resolution"] == "FAILED_MATCH"
    assert target_payload["has_raw_text"] is True
    assert target_payload["raw_text_char_count"] == len(missing_text)
    assert missing_text not in response.text
    assert str(tmp_path) not in response.text
    written_report = json.loads(report_out.read_text(encoding="utf-8"))
    assert missing_text not in json.dumps(written_report["items"][0]["scorecard_repair_targets"])
    written_scorecard = json.loads(
        (out_root / "paper-1" / "evidence_grounding_scorecard.json").read_text(encoding="utf-8")
    )
    assert written_scorecard["repair_targets"][0]["claim_id"] == "c1"
    assert missing_text not in json.dumps(written_scorecard["repair_targets"])


def test_scorecard_input_backfill_api_masks_failed_item_and_removes_partial_output(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "api_scorecard_runs_failed"
    report_out = tmp_path / "api_failed_backfill_report.json"
    _write_raw_deepread_run(source_run)
    (source_run / "index_artifact.json").unlink()
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "items": [{"paper_id": "paper-1", "source_run_dir": str(source_run)}],
            "out_run_root": str(out_root),
            "out": str(report_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard_input_backfill.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["pass_count"] == 0
    assert payload["fail_count"] == 1
    assert payload["items"][0]["status"] == "fail"
    assert payload["items"][0]["source_run_dir"] == ".../run-1"
    assert payload["items"][0]["output_run_dir"] == ".../paper-1"
    assert "index_artifact.json" in payload["items"][0]["error"]
    assert str(tmp_path) not in response.text
    assert not (out_root / "paper-1").exists()
    assert report_out.exists()
    written = json.loads(report_out.read_text(encoding="utf-8"))
    assert written["fail_count"] == 1
    assert written["items"][0]["source_run_dir"] == str(source_run.resolve())


def test_scorecard_input_backfill_api_derives_items_from_benchmark_manifest(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    manifest_path = manifest_dir / "benchmark_manifest.json"
    out_root = tmp_path / "api_scorecard_runs_from_manifest"
    report_out = tmp_path / "api_manifest_backfill_report.json"
    run_dir_map_out = tmp_path / "api_manifest_backfill_run_dir_map.json"
    _write_raw_deepread_run(source_run)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "evidence_grounding_benchmark_manifest.v1",
                "benchmark_id": "api-manifest-backfill",
                "items": [
                    {
                        "candidate_id": "candidate-paper-1",
                        "paper_id": "paper-1",
                        "run_dir": "../source/paper-1/run-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "benchmark_manifest_paths": [str(manifest_path)],
            "out_run_root": str(out_root),
            "out": str(report_out),
            "run_dir_map_out": str(run_dir_map_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard_input_backfill.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["pass_count"] == 1
    assert payload["run_dir_map_path"] == ".../api_manifest_backfill_run_dir_map.json"
    assert str(tmp_path) not in response.text
    assert payload["items"][0]["source_run_dir"] == ".../run-1"
    assert payload["items"][0]["output_run_dir"] == ".../candidate-paper-1"
    assert (out_root / "candidate-paper-1" / "evidence_extraction_bundle.json").exists()
    assert not (source_run / "evidence_extraction_bundle.json").exists()
    assert report_out.exists()
    written = json.loads(report_out.read_text(encoding="utf-8"))
    assert written["items"][0]["source_run_dir"] == str(source_run.resolve())
    assert written["items"][0]["output_run_dir"] == str((out_root / "candidate-paper-1").resolve())
    run_dir_map = json.loads(run_dir_map_out.read_text(encoding="utf-8"))
    assert run_dir_map == {"paper-1": str((out_root / "candidate-paper-1").resolve())}


def test_scorecard_input_backfill_api_derives_items_from_benchmark_manifest_package(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    manifest_dir = tmp_path / "manifests"
    package_dir = tmp_path / "packages"
    manifest_dir.mkdir()
    package_dir.mkdir()
    manifest_path = manifest_dir / "benchmark_manifest.json"
    package_path = package_dir / "benchmark_manifest_package.json"
    out_root = tmp_path / "api_scorecard_runs_from_manifest_package"
    report_out = tmp_path / "api_manifest_package_backfill_report.json"
    _write_raw_deepread_run(source_run)
    manifest_payload = {
        "schema_version": "evidence_grounding_benchmark_manifest.v1",
        "benchmark_id": "api-manifest-package-backfill",
        "items": [
            {
                "candidate_id": "candidate-paper-1",
                "paper_id": "paper-1",
                "run_dir": "../source/paper-1/run-1",
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    readiness_payload = {
        "schema_version": "paper_understanding_gold_release_readiness.v1",
        "layer": "review_gate_artifact",
        "canonical_status": "non_canonical",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_id": "gold-release-readiness",
        "required_splits": ["eval"],
        "min_ready_per_split": 1,
        "manifest_count": 1,
        "goldset_ids": ["goldset-1"],
        "item_count": 1,
        "ready_count": 1,
        "invalid_count": 0,
        "missing_splits": [],
        "underfilled_splits": [],
        "duplicate_paper_ids": [],
        "split_summaries": [
            {
                "manifest_path": "eval.json",
                "goldset_id": "goldset-1",
                "goldset_split": "eval",
                "item_count": 1,
                "ready_count": 1,
                "warn_count": 0,
                "fail_count": 0,
                "invalid_count": 0,
                "paper_ids": ["paper-1"],
                "status": "pass",
            }
        ],
        "blockers": [],
        "release_ready": True,
        "warnings": [],
    }
    package_path.write_text(
        json.dumps(
            {
                "schema_version": "evidence_grounding_benchmark_manifest_package.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "package_id": "api-manifest-package-backfill",
                "release_package_path": "release_package.json",
                "release_package": {
                    "schema_version": "paper_understanding_gold_release_package.v1",
                    "layer": "review_gate_artifact",
                    "canonical_status": "non_canonical",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "package_id": "gold-release-package",
                    "goldset_id": "goldset-1",
                    "source_split_manifests": [],
                    "manifest_paths": ["eval.json"],
                    "release_readiness_report_path": "release_readiness.json",
                    "release_readiness": readiness_payload,
                },
                "run_root": str((tmp_path / "source").resolve()),
                "run_dir_template": "{paper_id}",
                "out_dir": str(manifest_dir.resolve()),
                "benchmark_manifest_paths": [str(manifest_path.resolve())],
                "benchmark_manifests": [manifest_payload],
                "manifest_count": 1,
                "item_count": 1,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "benchmark_manifest_package_paths": [str(package_path)],
            "out_run_root": str(out_root),
            "out": str(report_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard_input_backfill.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["pass_count"] == 1
    assert str(tmp_path) not in response.text
    assert payload["items"][0]["source_run_dir"] == ".../run-1"
    assert payload["items"][0]["output_run_dir"] == ".../candidate-paper-1"
    assert (out_root / "candidate-paper-1" / "evidence_grounding_scorecard.json").exists()
    assert report_out.exists()
    written = json.loads(report_out.read_text(encoding="utf-8"))
    assert written["items"][0]["source_run_dir"] == str(source_run.resolve())
    assert written["items"][0]["output_run_dir"] == str((out_root / "candidate-paper-1").resolve())


def test_scorecard_input_backfill_api_resolves_embedded_package_runs_from_out_dir(tmp_path):
    source_run = tmp_path / "manifest-root" / "source" / "paper-1" / "run-1"
    manifest_dir = tmp_path / "manifest-root" / "manifests"
    package_dir = tmp_path / "package-root" / "packages"
    manifest_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)
    package_path = package_dir / "benchmark_manifest_package.json"
    out_root = tmp_path / "api_scorecard_runs_from_embedded_manifest_package"
    _write_raw_deepread_run(source_run)
    package_path.write_text(
        json.dumps(
            {
                "schema_version": "evidence_grounding_benchmark_manifest_package.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "package_id": "api-embedded-manifest-package-backfill",
                "release_package_path": "release_package.json",
                "release_package": {
                    "schema_version": "paper_understanding_gold_release_package.v1",
                    "layer": "review_gate_artifact",
                    "canonical_status": "non_canonical",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "package_id": "gold-release-package",
                    "goldset_id": "goldset-1",
                    "release_readiness_report_path": "release_readiness.json",
                    "release_readiness": {
                        "schema_version": "paper_understanding_gold_release_readiness.v1",
                        "layer": "review_gate_artifact",
                        "canonical_status": "non_canonical",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "readiness_id": "gold-release-readiness",
                        "manifest_count": 1,
                        "item_count": 1,
                        "ready_count": 1,
                        "invalid_count": 0,
                        "release_ready": True,
                    },
                },
                "run_root": str((tmp_path / "manifest-root" / "source").resolve()),
                "run_dir_template": "{paper_id}",
                "out_dir": str(manifest_dir.resolve()),
                "benchmark_manifest_paths": [],
                "benchmark_manifests": [
                    {
                        "schema_version": "evidence_grounding_benchmark_manifest.v1",
                        "benchmark_id": "api-embedded-manifest-package-backfill",
                        "items": [
                            {
                                "candidate_id": "candidate-paper-1",
                                "paper_id": "paper-1",
                                "run_dir": "../source/paper-1/run-1",
                            }
                        ],
                    }
                ],
                "manifest_count": 1,
                "item_count": 1,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "benchmark_manifest_package_paths": [str(package_path)],
            "out_run_root": str(out_root),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pass_count"] == 1
    assert payload["fail_count"] == 0
    assert str(tmp_path) not in response.text
    assert payload["items"][0]["source_run_dir"] == ".../run-1"
    assert (out_root / "candidate-paper-1" / "evidence_grounding_scorecard.json").exists()


def test_scorecard_input_backfill_api_rejects_missing_reviewed_fixture_dir(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "api_scorecard_runs_missing_reviewed"
    _write_raw_deepread_run(source_run)
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "items": [{"paper_id": "paper-1", "source_run_dir": str(source_run)}],
            "out_run_root": str(out_root),
            "reviewed_fixtures_dir": str(tmp_path / "missing-reviewed"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fail_count"] == 1
    assert "reviewed_fixtures_dir_not_found" in payload["items"][0]["error"]
    assert str(tmp_path) not in response.text


def test_scorecard_input_backfill_api_requires_reviewed_fixtures_when_requested(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "api_scorecard_runs_without_reviewed_fixtures"
    reviewed_dir = tmp_path / "reviewed"
    reviewed_dir.mkdir()
    _write_raw_deepread_run(source_run)
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/input-backfill",
        json={
            "items": [{"paper_id": "paper-1", "source_run_dir": str(source_run)}],
            "out_run_root": str(out_root),
            "reviewed_fixtures_dir": str(reviewed_dir),
            "require_reviewed_fixtures": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pass_count"] == 0
    assert payload["fail_count"] == 1
    assert "reviewed_fixtures_required_but_missing" in payload["items"][0]["error"]
    assert str(tmp_path) not in response.text


def test_evidence_grounding_scorecard_build_api_writes_scorecard_with_external_gold(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "paper-1.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text(_paper_understanding_gold_with_gap().model_dump_json(), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "paper_understanding_gold_path": str(gold_path),
            "out": str(out),
            "candidate_config": {
                "parser_version": "parser-api-v2",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-api-2026-05-22",
                "prompt_version": "grounding-prompt-api-v2",
                "reader_profile_version": "reader-profile-api-v2",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["paper_id"] == "paper-1"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "available"
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.5
    assert payload["gold_scored_metrics"]["gap_recall"]["status"] == "available"
    assert payload["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    assert payload["candidate_config"]["parser_version"] == "parser-api-v2"
    assert payload["candidate_config"]["llm_model_version"] == "reader-model-api-2026-05-22"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 5,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 1,
    }
    assert ".../paper-1.json" in payload["source_artifacts"]
    assert str(tmp_path) not in json.dumps(payload)
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["reason_codes"].count("gold_metrics_scored") == 1
    assert written["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]
    stage_metrics = {summary["stage"]: summary for summary in written["stage_metric_summary"]}
    assert stage_metrics["consistency_checker"]["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    assert "GAP_MISSED" not in written["failure_counts_by_code"]
    assert written["candidate_config"]["prompt_version"] == "grounding-prompt-api-v2"
    assert str(gold_path.resolve()) in written["source_artifacts"]


def test_evidence_grounding_scorecard_build_api_masks_all_response_strings(
    tmp_path,
    monkeypatch,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    private_path = tmp_path / "private" / "source.json"
    scorecard_payload = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    ).model_dump(mode="json")
    scorecard_payload.pop("input_artifact_summary", None)
    scorecard_payload["source_artifacts"] = [str(private_path)]
    scorecard_payload["warnings"] = [f"review private source at {private_path}"]
    scorecard_payload["recommended_next_action"] = f"inspect {private_path}"
    scorecard = EvidenceGroundingScorecard.model_validate(scorecard_payload)

    def fake_build_scorecard_from_run_dir(*args, **kwargs):
        return scorecard

    monkeypatch.setattr(
        evidence_grounding_scorecards_router,
        "build_evidence_grounding_scorecard_from_run_dir",
        fake_build_scorecard_from_run_dir,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert str(tmp_path) not in response.text
    assert ".../source.json" in response.text
    payload = response.json()
    assert payload["source_artifacts"] == [".../source.json"]
    assert payload["warnings"] == ["review private source at .../source.json"]
    assert payload["recommended_next_action"] == "inspect .../source.json"


def test_evidence_grounding_scorecard_build_api_defaults_to_run_dir_noncanonical_output(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 1.0
    assert payload["runtime_proxy_metrics"]["missing_input_artifact_count"]["value"] == 0
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 5,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 1,
    }
    assert {
        diagnostic["artifact"]
        for diagnostic in payload["input_artifact_diagnostics"]
        if diagnostic["core_scorecard_input"] is True
    } == {
        "reader_eval.json",
        "claimset_coverage.json",
        "evidence_extraction_bundle.json",
        "visual_evidence_ledger.json",
    }
    assert written["schema_version"] == payload["schema_version"]
    assert written["canonical_status"] == payload["canonical_status"]
    assert written["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 1.0


def test_scorecard_only_router_builds_default_noncanonical_output(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    app = FastAPI()
    app.include_router(evidence_grounding_scorecards_router.router)
    client = TestClient(app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["source_artifacts"] == ["reader_eval.json"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"


def test_main_app_scorecard_build_route_uses_scorecard_only_router():
    routes = [
        route
        for route in api_main.app.routes
        if getattr(route, "path", None) == "/evidence-grounding/scorecards/build"
    ]

    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == "backend.routers.evidence_grounding_scorecards"


def test_scorecard_only_router_exposes_only_scorecard_build_route():
    routes = [
        route
        for route in evidence_grounding_scorecards_router.router.routes
        if hasattr(route, "methods")
    ]

    assert [(route.path, sorted(route.methods)) for route in routes] == [
        ("/evidence-grounding/scorecards/build", ["POST"])
    ]


def test_evidence_grounding_scorecard_build_api_can_preview_without_writing(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 1.0
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_external_gold_without_writing(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "paper-1.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text(_paper_understanding_gold_with_gap().model_dump_json(), encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "paper_understanding_gold_path": str(gold_path),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "available"
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.5
    assert "gold_metrics_scored" in payload["reason_codes"]
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 5,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 1,
    }
    assert ".../paper-1.json" in payload["source_artifacts"]
    assert str(tmp_path) not in response.text
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_run_local_gold_without_writing(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(
        _paper_understanding_gold().model_dump_json(),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "available"
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.5
    assert "gold_metrics_scored" in payload["reason_codes"]
    assert "paper_understanding_gold.json" in payload["source_artifacts"]
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["paper_understanding_gold.json"]["status"] == "loaded"
    assert diagnostics["paper_understanding_gold.json"]["core_scorecard_input"] is False
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_run_local_gold_gap_recall_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(
        _paper_understanding_gold_with_gap().model_dump_json(),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["gap_recall"]["status"] == "available"
    assert payload["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    stage_metrics = {summary["stage"]: summary for summary in payload["stage_metric_summary"]}
    assert stage_metrics["consistency_checker"]["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    assert "gold_metrics_scored" in payload["reason_codes"]
    assert "GAP_MISSED" not in payload["failure_counts_by_code"]
    assert "paper_understanding_gold.json" in payload["source_artifacts"]
    assert str(tmp_path) not in response.text
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_mismatched_run_local_gold_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(
        mismatched_gold.model_dump_json(),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_malformed_run_local_gold_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("paper_understanding_gold.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["paper_understanding_gold.json"]["status"] == "load_failed"
    assert diagnostics["paper_understanding_gold.json"]["core_scorecard_input"] is False
    assert diagnostics["paper_understanding_gold.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_reviewed_eval_fixtures_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps({"fixtures": [_reviewed_eval_fixture().model_dump(mode="json")]}),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "reviewed_eval_fixture_metrics_scored" in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["value"] == 1
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.25
    assert payload["gold_scored_metrics"]["overstatement_rate"]["value"] == 0.25
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_malformed_reviewed_eval_fixtures_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert any(
        "claim_evidence_reviewed_eval_fixtures.json could not be loaded" in warning
        for warning in payload["warnings"]
    )
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "load_failed"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_out_of_scope_reviewed_eval_fixtures_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json")
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_mixed_scope_reviewed_eval_fixtures_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture().model_dump(mode="json"),
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json"),
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["value"] == 1
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.25
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_previews_mismatched_external_gold_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "paper-2.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text(mismatched_gold.model_dump_json(), encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "paper_understanding_gold_path": str(gold_path),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert ".../paper-2.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert str(tmp_path) not in response.text
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_preview_with_malformed_candidate_config_does_not_write(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-api-sidecar-v2",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"] is None
    assert "candidate_config.json" not in payload["source_artifacts"]
    assert any("candidate_config.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "load_failed"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert diagnostics["candidate_config.json"]["detail"] == "ValidationError"
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_preview_loads_run_local_candidate_config_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": " parser-api-sidecar-v2 ",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-api-sidecar-2026-05-22",
                "prompt_version": "grounding-prompt-api-sidecar-v2",
                "reader_profile_version": "reader-profile-api-sidecar-v2",
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"]["parser_version"] == "parser-api-sidecar-v2"
    assert payload["candidate_config"]["llm_model_version"] == "reader-model-api-sidecar-2026-05-22"
    assert payload["candidate_config"]["prompt_version"] == "grounding-prompt-api-sidecar-v2"
    assert "candidate_config.json" in payload["source_artifacts"]
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "loaded"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_rejects_missing_run_directory_without_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "missing-run"
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "run_dir must be an existing directory" in detail
    assert ".../missing-run" in detail
    assert str(tmp_path) not in detail
    assert not run_dir.exists()


def test_evidence_grounding_scorecard_build_api_rejects_missing_run_directory_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "missing-run"
    out = tmp_path / "exports" / "evidence_grounding_scorecard.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir), "out": str(out), "write": False},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "run_dir must be an existing directory" in detail
    assert ".../missing-run" in detail
    assert str(tmp_path) not in detail
    assert not run_dir.exists()
    assert not out.exists()
    assert not out.parent.exists()


def test_evidence_grounding_scorecard_build_api_rejects_empty_run_directory_without_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-empty"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "at least one loadable core scorecard sidecar" in detail
    assert ".../run-empty" in detail
    assert str(tmp_path) not in detail
    assert not out.exists()


def test_evidence_grounding_scorecard_build_api_rejects_empty_run_directory_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-empty"
    out = tmp_path / "exports" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir), "out": str(out), "write": False},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "at least one loadable core scorecard sidecar" in detail
    assert ".../run-empty" in detail
    assert str(tmp_path) not in detail
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert list(run_dir.iterdir()) == []


def test_evidence_grounding_scorecard_build_api_reports_malformed_core_sidecar_without_mutating_sources(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text("{not-json", encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["readiness_status"] == "warn"
    assert "reader_eval.json" not in payload["source_artifacts"]
    assert "reader_eval_missing" in payload["reason_codes"]
    assert any("reader_eval.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["reader_eval.json"]["status"] == "load_failed"
    assert diagnostics["reader_eval.json"]["core_scorecard_input"] is True
    assert diagnostics["reader_eval.json"]["detail"] == "JSONDecodeError"
    assert payload["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 0.75
    assert payload["runtime_proxy_metrics"]["missing_input_artifact_count"]["value"] == 1
    assert payload["runtime_proxy_metrics"]["malformed_input_artifact_count"]["value"] == 1
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 4,
        "input_artifact_diagnostic_count": 5,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 3,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 1,
        "non_core_input_artifact_count": 1,
    }
    assert written["input_artifact_diagnostics"] == payload["input_artifact_diagnostics"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]
    assert written["runtime_proxy_metrics"]["malformed_input_artifact_count"]["value"] == 1


def test_evidence_grounding_scorecard_build_api_previews_malformed_core_sidecar_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text("{not-json", encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["readiness_status"] == "warn"
    assert "reader_eval.json" not in payload["source_artifacts"]
    assert "reader_eval_missing" in payload["reason_codes"]
    assert any("reader_eval.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["reader_eval.json"]["status"] == "load_failed"
    assert diagnostics["reader_eval.json"]["core_scorecard_input"] is True
    assert diagnostics["reader_eval.json"]["detail"] == "JSONDecodeError"
    assert payload["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 0.75
    assert payload["runtime_proxy_metrics"]["missing_input_artifact_count"]["value"] == 1
    assert payload["runtime_proxy_metrics"]["malformed_input_artifact_count"]["value"] == 1
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 4,
        "input_artifact_diagnostic_count": 5,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 3,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 1,
        "non_core_input_artifact_count": 1,
    }
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_warns_on_malformed_run_local_candidate_config(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-api-sidecar-v2",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"] is None
    assert "candidate_config.json" not in payload["source_artifacts"]
    assert any("candidate_config.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "load_failed"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert diagnostics["candidate_config.json"]["detail"] == "ValidationError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert written["candidate_config"] is None
    assert "candidate_config.json" not in written["source_artifacts"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]


def test_evidence_grounding_scorecard_build_api_loads_run_local_candidate_config_sidecar(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": " parser-api-sidecar-v2 ",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-api-sidecar-2026-05-22",
                "prompt_version": "grounding-prompt-api-sidecar-v2",
                "reader_profile_version": "reader-profile-api-sidecar-v2",
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"]["parser_version"] == "parser-api-sidecar-v2"
    assert payload["candidate_config"]["llm_model_version"] == "reader-model-api-sidecar-2026-05-22"
    assert payload["candidate_config"]["prompt_version"] == "grounding-prompt-api-sidecar-v2"
    assert "candidate_config.json" in payload["source_artifacts"]
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "loaded"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]
    assert written["candidate_config"] == payload["candidate_config"]
    assert "candidate_config.json" in written["source_artifacts"]


def test_evidence_grounding_scorecard_build_api_refuses_mismatched_run_local_gold(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(mismatched_gold.model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert written["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in written["reason_codes"]
    assert "paper_understanding_gold.json" not in written["source_artifacts"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]


def test_evidence_grounding_scorecard_build_api_treats_malformed_run_local_gold_as_unavailable_eval_source(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("paper_understanding_gold.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["paper_understanding_gold.json"]["status"] == "load_failed"
    assert diagnostics["paper_understanding_gold.json"]["core_scorecard_input"] is False
    assert diagnostics["paper_understanding_gold.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert written["input_artifact_diagnostics"] == payload["input_artifact_diagnostics"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]
    assert "paper_understanding_gold.json" not in written["source_artifacts"]


def test_evidence_grounding_scorecard_build_api_treats_malformed_reviewed_eval_fixtures_as_unavailable_eval_source(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert any(
        "claim_evidence_reviewed_eval_fixtures.json could not be loaded" in warning
        for warning in payload["warnings"]
    )
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "load_failed"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert written["input_artifact_diagnostics"] == payload["input_artifact_diagnostics"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in written["source_artifacts"]


def test_evidence_grounding_scorecard_build_api_does_not_score_out_of_scope_run_local_reviewed_eval_fixtures(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json")
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert written["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in written["reason_codes"]
    assert written["input_artifact_diagnostics"] == payload["input_artifact_diagnostics"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in written["source_artifacts"]


def test_evidence_grounding_scorecard_build_api_scores_only_in_scope_run_local_reviewed_eval_fixtures(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture().model_dump(mode="json"),
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json"),
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={"run_dir": str(run_dir)},
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["value"] == 1
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.25
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert written["reason_codes"] == payload["reason_codes"]
    assert written["input_artifact_diagnostics"] == payload["input_artifact_diagnostics"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]
    assert "claim_evidence_reviewed_eval_fixtures.json" in written["source_artifacts"]


def test_evidence_grounding_scorecard_build_api_explicit_candidate_config_overrides_run_local_sidecar(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "stale-sidecar-parser",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "candidate_config": {
                "parser_version": "parser-api-v2",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-api-2026-05-22",
                "prompt_version": "grounding-prompt-api-v2",
                "reader_profile_version": "reader-profile-api-v2",
            },
        },
    )

    assert response.status_code == 200
    assert out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = response.json()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"]["parser_version"] == "parser-api-v2"
    assert payload["candidate_config"]["llm_model_version"] == "reader-model-api-2026-05-22"
    assert "candidate_config.json" not in payload["source_artifacts"]
    assert not any("candidate_config.json could not be loaded" in warning for warning in payload["warnings"])
    assert all(
        diagnostic["artifact"] != "candidate_config.json"
        for diagnostic in payload["input_artifact_diagnostics"]
    )
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 5,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 1,
    }
    assert written["candidate_config"]["prompt_version"] == "grounding-prompt-api-v2"
    assert "candidate_config.json" not in written["source_artifacts"]
    assert written["input_artifact_summary"] == payload["input_artifact_summary"]


def test_build_evidence_grounding_scorecard_cli_writes_noncanonical_scorecard_with_sources(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "paper-1.json"
    candidate_config_path = tmp_path / "candidate_config.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text(_paper_understanding_gold_with_gap().model_dump_json(), encoding="utf-8")
    candidate_config_path.write_text(
        json.dumps(
            {
                "parser_version": "parser-cli-v2",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-cli-2026-05-22",
                "prompt_version": "grounding-prompt-cli-v2",
                "reader_profile_version": "reader-profile-cli-v2",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--paper-understanding-gold",
            str(gold_path),
            "--candidate-config",
            str(candidate_config_path),
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "available"
    assert payload["gold_scored_metrics"]["gap_recall"]["status"] == "available"
    assert payload["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    stage_metrics = {summary["stage"]: summary for summary in payload["stage_metric_summary"]}
    assert stage_metrics["consistency_checker"]["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    assert "GAP_MISSED" not in payload["failure_counts_by_code"]
    assert payload["candidate_config"]["parser_version"] == "parser-cli-v2"
    assert str(gold_path.resolve()) in payload["source_artifacts"]
    assert str(candidate_config_path.resolve()) in payload["source_artifacts"]


def test_build_evidence_grounding_scorecard_cli_explicit_candidate_config_overrides_run_local_sidecar(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    candidate_config_path = tmp_path / "candidate_config.json"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "stale-sidecar-parser",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    candidate_config_path.write_text(
        json.dumps(
            {
                "parser_version": "parser-cli-v2",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-cli-2026-05-22",
                "prompt_version": "grounding-prompt-cli-v2",
                "reader_profile_version": "reader-profile-cli-v2",
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--candidate-config",
            str(candidate_config_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stdout
    assert "source_artifact_count:6" in result.stdout
    assert "input_artifact_diagnostic_count:5" in result.stdout
    assert "loaded_core_input_artifact_count:4" in result.stdout
    assert "non_core_input_artifact_count:1" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["candidate_config"]["parser_version"] == "parser-cli-v2"
    assert payload["candidate_config"]["prompt_version"] == "grounding-prompt-cli-v2"
    assert str(candidate_config_path.resolve()) in payload["source_artifacts"]
    assert "candidate_config.json" not in payload["source_artifacts"]
    assert not any("candidate_config.json could not be loaded" in warning for warning in payload["warnings"])
    assert all(
        diagnostic["artifact"] != "candidate_config.json"
        for diagnostic in payload["input_artifact_diagnostics"]
    )
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 5,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 1,
    }


def test_build_evidence_grounding_scorecard_cli_loads_run_local_candidate_config_sidecar(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": " parser-sidecar-v2 ",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-sidecar-2026-05-22",
                "prompt_version": "grounding-prompt-sidecar-v2",
                "reader_profile_version": "reader-profile-sidecar-v2",
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"]["parser_version"] == "parser-sidecar-v2"
    assert payload["candidate_config"]["llm_model_version"] == "reader-model-sidecar-2026-05-22"
    assert payload["candidate_config"]["prompt_version"] == "grounding-prompt-sidecar-v2"
    assert "candidate_config.json" in payload["source_artifacts"]
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "loaded"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_build_evidence_grounding_scorecard_cli_can_preview_without_writing(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stdout
    assert "source_artifact_count:4" in result.stdout
    assert "input_artifact_diagnostic_count:4" in result.stdout
    assert "loaded_core_input_artifact_count:4" in result.stdout
    assert "non_core_input_artifact_count:0" in result.stdout
    assert "[evidence_grounding_scorecard] write=false" in result.stdout
    assert "[evidence_grounding_scorecard] out=-" in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_preview_with_malformed_candidate_config_does_not_write(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-sidecar-v2",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert "[evidence_grounding_scorecard] write=false" in result.stdout
    assert "[evidence_grounding_scorecard] out=-" in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_masked_json_preview(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "paper-1.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text(_paper_understanding_gold().model_dump_json(), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--paper-understanding-gold",
            str(gold_path),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:6" in result.stderr
    assert "input_artifact_diagnostic_count:5" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "non_core_input_artifact_count:1" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "available"
    assert payload["input_artifact_summary"]["source_artifact_count"] == 6
    assert payload["input_artifact_summary"]["input_artifact_diagnostic_count"] == 5
    assert payload["input_artifact_summary"]["non_core_input_artifact_count"] == 1
    assert ".../paper-1.json" in payload["source_artifacts"]
    assert str(tmp_path) not in result.stdout
    assert not out.exists()


def test_build_evidence_grounding_scorecard_cli_prints_run_local_gold_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(
        _paper_understanding_gold().model_dump_json(),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:6" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "available"
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.5
    assert "gold_metrics_scored" in payload["reason_codes"]
    assert "paper_understanding_gold.json" in payload["source_artifacts"]
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["paper_understanding_gold.json"]["status"] == "loaded"
    assert diagnostics["paper_understanding_gold.json"]["core_scorecard_input"] is False
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_run_local_gold_gap_recall_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(
        _paper_understanding_gold_with_gap().model_dump_json(),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:6" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "load_failed_core_input_artifact_count:0" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["gold_scored_metrics"]["gap_recall"]["status"] == "available"
    assert payload["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    stage_metrics = {summary["stage"]: summary for summary in payload["stage_metric_summary"]}
    assert stage_metrics["consistency_checker"]["gold_scored_metrics"]["gap_recall"]["value"] == 1.0
    assert "gold_metrics_scored" in payload["reason_codes"]
    assert "GAP_MISSED" not in payload["failure_counts_by_code"]
    assert "paper_understanding_gold.json" in payload["source_artifacts"]
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_mismatched_run_local_gold_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(
        mismatched_gold.model_dump_json(),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=fail" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:5" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_malformed_run_local_gold_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:5" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("paper_understanding_gold.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["paper_understanding_gold.json"]["status"] == "load_failed"
    assert diagnostics["paper_understanding_gold.json"]["core_scorecard_input"] is False
    assert diagnostics["paper_understanding_gold.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_reviewed_eval_fixtures_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps({"fixtures": [_reviewed_eval_fixture().model_dump(mode="json")]}),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:6" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "reviewed_eval_fixture_metrics_scored" in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["value"] == 1
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.25
    assert payload["gold_scored_metrics"]["overstatement_rate"]["value"] == 0.25
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_malformed_reviewed_eval_fixtures_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert any(
        "claim_evidence_reviewed_eval_fixtures.json could not be loaded" in warning
        for warning in payload["warnings"]
    )
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "load_failed"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_out_of_scope_reviewed_eval_fixtures_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json")
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=fail" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:5" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_mixed_scope_reviewed_eval_fixtures_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture().model_dump(mode="json"),
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json"),
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=fail" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:6" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["value"] == 1
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.25
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_mismatched_external_gold_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "paper-2.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text(mismatched_gold.model_dump_json(), encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--paper-understanding-gold",
            str(gold_path),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=fail" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert ".../paper-2.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_prints_malformed_candidate_config_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-sidecar-v2",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stderr
    assert "source_artifact_count:5" in result.stderr
    assert "input_artifact_diagnostic_count:6" in result.stderr
    assert "loaded_core_input_artifact_count:4" in result.stderr
    assert "load_failed_core_input_artifact_count:0" in result.stderr
    assert "non_core_input_artifact_count:2" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"] is None
    assert "candidate_config.json" not in payload["source_artifacts"]
    assert any("candidate_config.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "load_failed"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert diagnostics["candidate_config.json"]["detail"] == "ValidationError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_build_evidence_grounding_scorecard_cli_prints_candidate_config_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": " parser-sidecar-v2 ",
                "llm_provider": "local",
                "llm_model": "reader-model",
                "llm_model_version": "reader-model-sidecar-2026-05-22",
                "prompt_version": "grounding-prompt-sidecar-v2",
                "reader_profile_version": "reader-profile-sidecar-v2",
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"]["parser_version"] == "parser-sidecar-v2"
    assert payload["candidate_config"]["llm_model_version"] == "reader-model-sidecar-2026-05-22"
    assert payload["candidate_config"]["prompt_version"] == "grounding-prompt-sidecar-v2"
    assert "candidate_config.json" in payload["source_artifacts"]
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "loaded"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_scorecard_input_backfill_cli_writes_copied_run_root(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "cli_scorecard_runs"
    report_out = tmp_path / "cli_backfill_report.json"
    _write_raw_deepread_run(source_run)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/backfill_evidence_grounding_scorecard_inputs.py",
            "--item",
            json.dumps({"paper_id": "paper-1", "source_run_dir": str(source_run)}),
            "--out-run-root",
            str(out_root),
            "--out",
            str(report_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard_input_backfill] pass_count=1" in result.stdout
    assert "[evidence_grounding_scorecard_input_backfill] fail_count=0" in result.stdout
    assert ".../cli_scorecard_runs" in result.stdout
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard_input_backfill.v1"
    assert payload["items"][0]["status"] == "pass"
    assert (out_root / "paper-1" / "claimset.resolved.json").exists()
    assert not (source_run / "claimset.resolved.json").exists()


def test_scorecard_input_backfill_cli_fails_when_generated_scorecard_fails_readiness(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "cli_scorecard_runs_failed_scorecard"
    report_out = tmp_path / "cli_backfill_failed_scorecard_report.json"
    _write_raw_deepread_run(source_run)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (source_run / "paper_understanding_gold.json").write_text(
        mismatched_gold.model_dump_json(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/backfill_evidence_grounding_scorecard_inputs.py",
            "--item",
            json.dumps({"paper_id": "paper-1", "source_run_dir": str(source_run)}),
            "--out-run-root",
            str(out_root),
            "--out",
            str(report_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[evidence_grounding_scorecard_input_backfill] pass_count=1" in result.stdout
    assert "[evidence_grounding_scorecard_input_backfill] fail_count=0" in result.stdout
    assert "scorecard_readiness=pass=0 warn=0 fail=1" in result.stdout
    assert (
        "scorecard_failures=paper_id=paper-1,"
        "output_name=paper-1,"
        "reason_codes=paper_understanding_gold_paper_id_mismatch"
    ) in result.stdout
    assert "metrics=grounded_evidence_ratio:" in result.stdout
    assert "page_coverage_ratio:" in result.stdout
    assert "missing_topic_signal_count:" in result.stdout
    assert str(tmp_path) not in result.stdout
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["warnings"] == ["scorecard_input_backfill_scorecard_failures_present"]
    assert payload["items"][0]["status"] == "pass"
    assert payload["items"][0]["scorecard_readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["items"][0]["scorecard_reason_codes"]
    assert (out_root / "paper-1" / "evidence_grounding_scorecard.json").exists()
    assert not (source_run / "evidence_grounding_scorecard.json").exists()


def test_scorecard_input_backfill_cli_derives_items_from_benchmark_manifest(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    manifest_path = manifest_dir / "benchmark_manifest.json"
    out_root = tmp_path / "cli_scorecard_runs_from_manifest"
    report_out = tmp_path / "cli_manifest_backfill_report.json"
    run_dir_map_out = tmp_path / "cli_manifest_backfill_run_dir_map.json"
    _write_raw_deepread_run(source_run)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "evidence_grounding_benchmark_manifest.v1",
                "benchmark_id": "manifest-backfill",
                "items": [
                    {
                        "candidate_id": "candidate-paper-1",
                        "paper_id": "paper-1",
                        "run_id": "run-from-manifest",
                        "run_dir": "../source/paper-1/run-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/backfill_evidence_grounding_scorecard_inputs.py",
            "--benchmark-manifest",
            str(manifest_path),
            "--out-run-root",
            str(out_root),
            "--out",
            str(report_out),
            "--run-dir-map-out",
            str(run_dir_map_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard_input_backfill] pass_count=1" in result.stdout
    assert ".../cli_manifest_backfill_run_dir_map.json" in result.stdout
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["run_dir_map_path"] == str(run_dir_map_out.resolve())
    assert payload["items"][0]["paper_id"] == "paper-1"
    assert payload["items"][0]["source_run_dir"] == str(source_run.resolve())
    assert payload["items"][0]["output_run_dir"] == str((out_root / "candidate-paper-1").resolve())
    run_dir_map = json.loads(run_dir_map_out.read_text(encoding="utf-8"))
    assert run_dir_map == {"paper-1": str((out_root / "candidate-paper-1").resolve())}
    assert (out_root / "candidate-paper-1" / "evidence_grounding_scorecard.json").exists()
    assert not (source_run / "evidence_grounding_scorecard.json").exists()


def test_scorecard_input_backfill_cli_derives_embedded_package_items_from_manifest_paths(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    manifest_dir = tmp_path / "manifests"
    package_dir = tmp_path / "packages"
    manifest_dir.mkdir()
    package_dir.mkdir()
    manifest_path = manifest_dir / "benchmark_manifest.json"
    package_path = package_dir / "benchmark_manifest_package.json"
    out_root = tmp_path / "cli_scorecard_runs_from_manifest_package"
    report_out = tmp_path / "cli_manifest_package_backfill_report.json"
    _write_raw_deepread_run(source_run)
    manifest_payload = {
        "schema_version": "evidence_grounding_benchmark_manifest.v1",
        "benchmark_id": "manifest-package-backfill",
        "items": [
            {
                "candidate_id": "candidate-paper-1",
                "paper_id": "paper-1",
                "run_dir": "../source/paper-1/run-1",
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    readiness_payload = {
        "schema_version": "paper_understanding_gold_release_readiness.v1",
        "layer": "review_gate_artifact",
        "canonical_status": "non_canonical",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_id": "gold-release-readiness",
        "required_splits": ["eval"],
        "min_ready_per_split": 1,
        "manifest_count": 1,
        "goldset_ids": ["goldset-1"],
        "item_count": 1,
        "ready_count": 1,
        "invalid_count": 0,
        "missing_splits": [],
        "underfilled_splits": [],
        "duplicate_paper_ids": [],
        "split_summaries": [
            {
                "manifest_path": "eval.json",
                "goldset_id": "goldset-1",
                "goldset_split": "eval",
                "item_count": 1,
                "ready_count": 1,
                "warn_count": 0,
                "fail_count": 0,
                "invalid_count": 0,
                "paper_ids": ["paper-1"],
                "status": "pass",
            }
        ],
        "blockers": [],
        "release_ready": True,
        "warnings": [],
    }
    package_path.write_text(
        json.dumps(
            {
                "schema_version": "evidence_grounding_benchmark_manifest_package.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "package_id": "manifest-package-backfill",
                "release_package_path": "release_package.json",
                "release_package": {
                    "schema_version": "paper_understanding_gold_release_package.v1",
                    "layer": "review_gate_artifact",
                    "canonical_status": "non_canonical",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "package_id": "gold-release-package",
                    "goldset_id": "goldset-1",
                    "source_split_manifests": [],
                    "manifest_paths": ["eval.json"],
                    "release_readiness_report_path": "release_readiness.json",
                    "release_readiness": readiness_payload,
                },
                "run_root": str((tmp_path / "source").resolve()),
                "run_dir_template": "{paper_id}",
                "out_dir": str(manifest_dir.resolve()),
                "benchmark_manifest_paths": [str(manifest_path.resolve())],
                "benchmark_manifests": [manifest_payload],
                "manifest_count": 1,
                "item_count": 1,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/backfill_evidence_grounding_scorecard_inputs.py",
            "--benchmark-manifest-package",
            str(package_path),
            "--out-run-root",
            str(out_root),
            "--out",
            str(report_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["pass_count"] == 1
    assert payload["items"][0]["source_run_dir"] == str(source_run.resolve())
    assert (out_root / "candidate-paper-1" / "evidence_grounding_scorecard.json").exists()


def test_scorecard_input_backfill_cli_packages_reviewed_eval_fixtures(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "cli_scorecard_runs_with_reviewed_fixtures"
    report_out = tmp_path / "cli_backfill_reviewed_report.json"
    reviewed_dir = tmp_path / "goldset" / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    reviewed_dir.mkdir(parents=True)
    _write_raw_deepread_run(source_run)
    (reviewed_dir / "intake-reviewed-c1.json").write_text(
        _reviewed_eval_fixture().model_dump_json(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/backfill_evidence_grounding_scorecard_inputs.py",
            "--item",
            json.dumps({"paper_id": "paper-1", "source_run_dir": str(source_run)}),
            "--out-run-root",
            str(out_root),
            "--out",
            str(report_out),
            "--reviewed-fixtures-dir",
            str(reviewed_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard_input_backfill] pass_count=1" in result.stdout
    assert "reviewed_fixtures_dir=.../reviewed" in result.stdout
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["items"][0]["reviewed_eval_fixture_count"] == 1
    assert "claim_evidence_reviewed_eval_fixtures.json" in payload["items"][0]["generated_artifacts"]
    assert (out_root / "paper-1" / "claim_evidence_reviewed_eval_fixtures.json").exists()


def test_scorecard_input_backfill_cli_requires_reviewed_fixtures_when_requested(tmp_path):
    source_run = tmp_path / "source" / "paper-1" / "run-1"
    out_root = tmp_path / "cli_scorecard_runs_without_reviewed_fixtures"
    report_out = tmp_path / "cli_backfill_missing_reviewed_report.json"
    reviewed_dir = tmp_path / "goldset" / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    reviewed_dir.mkdir(parents=True)
    _write_raw_deepread_run(source_run)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/backfill_evidence_grounding_scorecard_inputs.py",
            "--item",
            json.dumps({"paper_id": "paper-1", "source_run_dir": str(source_run)}),
            "--out-run-root",
            str(out_root),
            "--out",
            str(report_out),
            "--reviewed-fixtures-dir",
            str(reviewed_dir),
            "--require-reviewed-fixtures",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[evidence_grounding_scorecard_input_backfill] fail_count=1" in result.stdout
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    assert "reviewed_fixtures_required_but_missing" in payload["items"][0]["error"]
    assert not (out_root / "paper-1").exists()


def test_build_evidence_grounding_scorecard_cli_defaults_to_run_dir_without_mutating_sources(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] out=.../evidence_grounding_scorecard.json" in result.stdout
    assert str(tmp_path) not in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 1.0
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"


def test_build_evidence_grounding_scorecard_cli_rejects_missing_run_directory_without_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "missing-run"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "run_dir must be an existing directory" in result.stderr
    assert ".../missing-run" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not run_dir.exists()


def test_build_evidence_grounding_scorecard_cli_rejects_missing_run_directory_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "missing-run"
    out = tmp_path / "exports" / "evidence_grounding_scorecard.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "run_dir must be an existing directory" in result.stderr
    assert ".../missing-run" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not run_dir.exists()
    assert not out.exists()
    assert not out.parent.exists()


def test_build_evidence_grounding_scorecard_cli_rejects_empty_run_directory_without_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-empty"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "at least one loadable core scorecard sidecar" in result.stderr
    assert ".../run-empty" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not out.exists()


def test_build_evidence_grounding_scorecard_cli_rejects_empty_run_directory_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-empty"
    out = tmp_path / "exports" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "at least one loadable core scorecard sidecar" in result.stderr
    assert ".../run-empty" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert list(run_dir.iterdir()) == []


def test_build_evidence_grounding_scorecard_cli_reports_malformed_core_sidecar_without_mutating_sources(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text("{not-json", encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stdout
    assert "source_artifact_count:4" in result.stdout
    assert "input_artifact_diagnostic_count:5" in result.stdout
    assert "loaded_core_input_artifact_count:3" in result.stdout
    assert "load_failed_core_input_artifact_count:1" in result.stdout
    assert "non_core_input_artifact_count:1" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "reader_eval.json" not in payload["source_artifacts"]
    assert "reader_eval_missing" in payload["reason_codes"]
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["reader_eval.json"]["status"] == "load_failed"
    assert diagnostics["reader_eval.json"]["core_scorecard_input"] is True
    assert diagnostics["reader_eval.json"]["detail"] == "JSONDecodeError"
    assert payload["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 0.75
    assert payload["runtime_proxy_metrics"]["missing_input_artifact_count"]["value"] == 1
    assert payload["runtime_proxy_metrics"]["malformed_input_artifact_count"]["value"] == 1


def test_build_evidence_grounding_scorecard_cli_prints_malformed_core_sidecar_preview_without_writing(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text("{not-json", encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stderr
    assert "[evidence_grounding_scorecard] write=false" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "reader_eval.json" not in payload["source_artifacts"]
    assert "reader_eval_missing" in payload["reason_codes"]
    assert any("reader_eval.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["reader_eval.json"]["status"] == "load_failed"
    assert diagnostics["reader_eval.json"]["core_scorecard_input"] is True
    assert diagnostics["reader_eval.json"]["detail"] == "JSONDecodeError"
    assert payload["runtime_proxy_metrics"]["input_artifact_coverage_rate"]["value"] == 0.75
    assert payload["runtime_proxy_metrics"]["missing_input_artifact_count"]["value"] == 1
    assert payload["runtime_proxy_metrics"]["malformed_input_artifact_count"]["value"] == 1
    assert payload["input_artifact_summary"]["loaded_core_input_artifact_count"] == 3
    assert payload["input_artifact_summary"]["load_failed_core_input_artifact_count"] == 1
    assert str(tmp_path) not in result.stdout
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_warns_on_malformed_run_local_candidate_config(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "candidate_config.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-sidecar-v2",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_config"] is None
    assert "candidate_config.json" not in payload["source_artifacts"]
    assert any("candidate_config.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["candidate_config.json"]["status"] == "load_failed"
    assert diagnostics["candidate_config.json"]["core_scorecard_input"] is False
    assert diagnostics["candidate_config.json"]["detail"] == "ValidationError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_build_evidence_grounding_scorecard_cli_refuses_mismatched_run_local_gold(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text(mismatched_gold.model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=fail" in result.stdout
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stdout
    assert "source_artifact_count:5" in result.stdout
    assert "input_artifact_diagnostic_count:6" in result.stdout
    assert "loaded_core_input_artifact_count:4" in result.stdout
    assert "non_core_input_artifact_count:2" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_build_evidence_grounding_scorecard_cli_treats_malformed_run_local_gold_as_unavailable_eval_source(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "paper_understanding_gold.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert "paper_understanding_gold.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("paper_understanding_gold.json could not be loaded" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["paper_understanding_gold.json"]["status"] == "load_failed"
    assert diagnostics["paper_understanding_gold.json"]["core_scorecard_input"] is False
    assert diagnostics["paper_understanding_gold.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_build_evidence_grounding_scorecard_cli_treats_malformed_reviewed_eval_fixtures_as_unavailable_eval_source(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text("{not-json", encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=warn" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "evidence_grounding_scorecard.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert "gold_labels_missing" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert any(
        "claim_evidence_reviewed_eval_fixtures.json could not be loaded" in warning
        for warning in payload["warnings"]
    )
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "load_failed"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["detail"] == "JSONDecodeError"
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_build_evidence_grounding_scorecard_cli_does_not_score_out_of_scope_run_local_reviewed_eval_fixtures(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json")
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=fail" in result.stdout
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stdout
    assert "source_artifact_count:5" in result.stdout
    assert "input_artifact_diagnostic_count:6" in result.stdout
    assert "loaded_core_input_artifact_count:4" in result.stdout
    assert "non_core_input_artifact_count:2" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" not in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" not in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["status"] == "not_available"
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 5,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_build_evidence_grounding_scorecard_cli_scores_only_in_scope_run_local_reviewed_eval_fixtures(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    (run_dir / "claim_evidence_reviewed_eval_fixtures.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    _reviewed_eval_fixture().model_dump(mode="json"),
                    _reviewed_eval_fixture(
                        paper_id="paper-2",
                        run_id="run-2",
                        claim_id="c-other",
                        source_correction_id="correction-reviewed-other",
                    ).model_dump(mode="json"),
                ]
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[evidence_grounding_scorecard] readiness_status=fail" in result.stdout
    assert "[evidence_grounding_scorecard] input_artifact_summary=" in result.stdout
    assert "source_artifact_count:6" in result.stdout
    assert "input_artifact_diagnostic_count:6" in result.stdout
    assert "loaded_core_input_artifact_count:4" in result.stdout
    assert "non_core_input_artifact_count:2" in result.stdout
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["readiness_status"] == "fail"
    assert "reviewed_eval_fixture_scope_mismatch" in payload["reason_codes"]
    assert "reviewed_eval_fixture_metrics_scored" in payload["reason_codes"]
    assert "claim_evidence_reviewed_eval_fixtures.json" in payload["source_artifacts"]
    assert payload["runtime_proxy_metrics"]["reviewed_eval_fixture_count"]["value"] == 1
    assert payload["gold_scored_metrics"]["claim_precision"]["value"] == 0.25
    assert any("reviewed eval fixtures skipped outside run scope: 1" in warning for warning in payload["warnings"])
    diagnostics = {diagnostic["artifact"]: diagnostic for diagnostic in payload["input_artifact_diagnostics"]}
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["status"] == "loaded"
    assert diagnostics["claim_evidence_reviewed_eval_fixtures.json"]["core_scorecard_input"] is False
    assert payload["input_artifact_summary"] == {
        "source_artifact_count": 6,
        "input_artifact_diagnostic_count": 6,
        "core_input_artifact_count": 4,
        "loaded_core_input_artifact_count": 4,
        "missing_core_input_artifact_count": 0,
        "load_failed_core_input_artifact_count": 0,
        "non_core_input_artifact_count": 2,
    }


def test_evidence_grounding_scorecard_build_api_rejects_invalid_external_gold_without_partial_write(tmp_path, caplog):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "invalid_gold.json"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text("{", encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)
    caplog.set_level(logging.WARNING, logger="paperpipe.backend")

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "paper_understanding_gold_path": str(gold_path),
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "paper_understanding_gold_path is invalid" in detail
    assert ".../invalid_gold.json" in detail
    assert str(tmp_path) not in detail
    assert "paper_understanding_gold_path is invalid" in caplog.text
    assert ".../invalid_gold.json" in caplog.text
    assert str(tmp_path) not in caplog.text
    assert not out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars


def test_evidence_grounding_scorecard_build_api_preview_rejects_invalid_external_gold_without_partial_write(
    tmp_path,
    caplog,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "invalid_gold.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text("{", encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}
    client = TestClient(api_main.app)
    caplog.set_level(logging.WARNING, logger="paperpipe.backend")

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "paper_understanding_gold_path": str(gold_path),
            "out": str(out),
            "write": False,
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "paper_understanding_gold_path is invalid" in detail
    assert ".../invalid_gold.json" in detail
    assert str(tmp_path) not in detail
    assert "paper_understanding_gold_path is invalid" in caplog.text
    assert ".../invalid_gold.json" in caplog.text
    assert str(tmp_path) not in caplog.text
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_evidence_grounding_scorecard_build_api_rejects_source_sidecar_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "reader_eval.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "scorecard output path would overwrite a run source artifact" in detail
    assert ".../reader_eval.json" in detail
    assert str(tmp_path) not in detail
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_evidence_grounding_scorecard_build_api_rejects_directory_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecard-output-dir"
    run_dir.mkdir(parents=True)
    out.mkdir()
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "scorecard output path must be a file path, not a directory" in detail
    assert ".../scorecard-output-dir" in detail
    assert str(tmp_path) not in detail
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert list(out.iterdir()) == []
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_evidence_grounding_scorecard_build_api_rejects_nested_run_dir_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "nested" / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "scorecard output path inside a run directory must be the top-level" in detail
    assert "evidence_grounding_scorecard.json" in detail
    assert str(tmp_path) not in detail
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert not out.exists()
    assert not out.parent.exists()
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_evidence_grounding_scorecard_build_api_rejects_non_scorecard_run_dir_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "scorecard-copy.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "out": str(out),
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "scorecard output path inside a run directory must be evidence_grounding_scorecard.json" in detail
    assert ".../scorecard-copy.json" in detail
    assert str(tmp_path) not in detail
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert not out.exists()
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_evidence_grounding_scorecard_build_api_rejects_unknown_request_fields_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "mutate_canonical_state": True,
        },
    )

    assert response.status_code == 422
    assert any(
        item["loc"][-1] == "mutate_canonical_state"
        and item["type"] == "extra_forbidden"
        for item in response.json()["detail"]
    )
    assert not out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars


def test_evidence_grounding_scorecard_build_api_rejects_unknown_candidate_config_fields_without_partial_write(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "candidate_config": {
                "parser_version": "parser-api-v2",
                "mutate_canonical_state": True,
            },
        },
    )

    assert response.status_code == 422
    assert any(
        item["loc"][-2:] == ["candidate_config", "mutate_canonical_state"]
        and item["type"] == "extra_forbidden"
        for item in response.json()["detail"]
    )
    assert not out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars


def test_build_evidence_grounding_scorecard_cli_rejects_invalid_external_gold_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "invalid_gold.json"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text("{", encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--paper-understanding-gold",
            str(gold_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "paper_understanding_gold path is invalid" in result.stderr
    assert ".../invalid_gold.json" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars


def test_build_evidence_grounding_scorecard_cli_preview_rejects_invalid_external_gold_without_partial_write(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "invalid_gold.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    default_out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text("{", encoding="utf-8")
    source_sidecars = {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--paper-understanding-gold",
            str(gold_path),
            "--out",
            str(out),
            "--no-write",
            "--print-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "paper_understanding_gold path is invalid" in result.stderr
    assert ".../invalid_gold.json" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not out.exists()
    assert not out.parent.exists()
    assert not default_out.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in run_dir.iterdir()} == source_sidecars


def test_build_evidence_grounding_scorecard_cli_rejects_source_sidecar_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "reader_eval.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "scorecard output path would overwrite a run source artifact" in result.stderr
    assert ".../reader_eval.json" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_build_evidence_grounding_scorecard_cli_rejects_directory_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = tmp_path / "scorecard-output-dir"
    run_dir.mkdir(parents=True)
    out.mkdir()
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "scorecard output path must be a file path, not a directory" in result.stderr
    assert ".../scorecard-output-dir" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert list(out.iterdir()) == []
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_build_evidence_grounding_scorecard_cli_rejects_nested_run_dir_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "nested" / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "scorecard output path inside a run directory must be the top-level" in result.stderr
    assert "evidence_grounding_scorecard.json" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert not out.exists()
    assert not out.parent.exists()
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_build_evidence_grounding_scorecard_cli_rejects_non_scorecard_run_dir_out_without_partial_write(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    out = run_dir / "scorecard-copy.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "scorecard output path inside a run directory must be evidence_grounding_scorecard.json" in result.stderr
    assert ".../scorecard-copy.json" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars
    assert not out.exists()
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_build_evidence_grounding_scorecard_cli_rejects_unknown_candidate_config_fields_without_partial_write(
    tmp_path,
):
    run_dir = tmp_path / "paper-1" / "run-1"
    candidate_config_path = tmp_path / "candidate_config.json"
    out = run_dir / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    candidate_config_path.write_text(
        json.dumps(
            {
                "parser_version": "parser-cli-v2",
                "mutate_canonical_state": True,
            }
        ),
        encoding="utf-8",
    )
    source_sidecars = {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval/build_evidence_grounding_scorecard.py",
            "--run-dir",
            str(run_dir),
            "--candidate-config",
            str(candidate_config_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("[evidence_grounding_scorecard] error=")
    assert "Extra inputs are not permitted" in result.stderr
    assert "mutate_canonical_state" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not out.exists()
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.name != "evidence_grounding_scorecard.json"
    } == source_sidecars


def test_evidence_grounding_scorecard_build_api_refuses_mismatched_external_gold(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    gold_path = tmp_path / "gold" / "paper-2.json"
    out = tmp_path / "scorecards" / "evidence_grounding_scorecard.json"
    run_dir.mkdir(parents=True)
    gold_path.parent.mkdir(parents=True)
    mismatched_gold = _paper_understanding_gold().model_copy(update={"paper_id": "paper-2"})
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")
    gold_path.write_text(mismatched_gold.model_dump_json(), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/evidence-grounding/scorecards/build",
        json={
            "run_dir": str(run_dir),
            "paper_understanding_gold_path": str(gold_path),
            "out": str(out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in payload["reason_codes"]
    assert "gold_metrics_scored" not in payload["reason_codes"]
    assert str(gold_path.resolve()) not in payload["source_artifacts"]
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["readiness_status"] == "fail"
    assert "paper_understanding_gold_paper_id_mismatch" in written["reason_codes"]


def test_packaged_reviewed_eval_fixture_sidecar_feeds_scorecard_metrics(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    reviewed_dir = tmp_path / "goldset" / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    run_dir.mkdir(parents=True)
    reviewed_dir.mkdir(parents=True)
    (reviewed_dir / "intake-reviewed-c1.json").write_text(_reviewed_eval_fixture().model_dump_json(), encoding="utf-8")
    (run_dir / "reader_eval.json").write_text(_reader_eval().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset_coverage.json").write_text(_coverage().model_dump_json(), encoding="utf-8")
    (run_dir / "evidence_extraction_bundle.json").write_text(_evidence_extraction().model_dump_json(), encoding="utf-8")
    (run_dir / "visual_evidence_ledger.json").write_text(_visual_evidence().model_dump_json(), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(_resolved_claimset().model_dump_json(), encoding="utf-8")

    sidecar_path, fixture_count = write_claim_evidence_reviewed_eval_fixtures_sidecar(
        reviewed_dir=reviewed_dir,
        run_dir=run_dir,
        paper_id="paper-1",
        run_id="run-1",
    )
    scorecard = build_evidence_grounding_scorecard_from_run_dir(run_dir)

    assert sidecar_path.name == "claim_evidence_reviewed_eval_fixtures.json"
    assert fixture_count == 1
    assert "reviewed_eval_fixture_metrics_scored" in scorecard.reason_codes
    assert scorecard.gold_scored_metrics.claim_precision.value == 0.25
    assert scorecard.gold_scored_metrics.overstatement_rate.value == 0.25


def test_write_evidence_grounding_scorecard(tmp_path):
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(status="pass"),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    )

    path = write_evidence_grounding_scorecard(scorecard, tmp_path)

    assert path.name == "evidence_grounding_scorecard.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["canonical_status"] == "non_canonical"
    assert payload["runtime_proxy_metrics"]["claim_count"]["value"] == 4
    assert payload["runtime_proxy_metrics"]["evidence_backed_extraction_rate"]["value"] == 0.75
    assert payload["runtime_proxy_metrics"]["table_cell_value_count"]["value"] == 2
    assert payload["stage_metric_summary"]
    assert any(item["stage"] == "grounding_checker" for item in payload["stage_metric_summary"])
    assert payload["failure_counts_by_code"]["TABLE_PARSE_FAILED"] == 1
    assert any(item["stage"] == "parser" for item in payload["stage_failure_summary"])
    assert payload["gold_scored_metrics"]["claim_precision"]["status"] == "not_available"


def test_write_evidence_grounding_scorecard_rejects_missing_artifact_directory(tmp_path):
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(status="pass"),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    )
    artifact_dir = tmp_path / "missing-run"

    with pytest.raises(ValueError, match="artifact_dir must be an existing directory"):
        write_evidence_grounding_scorecard(scorecard, artifact_dir)

    assert not artifact_dir.exists()


def test_write_evidence_grounding_scorecard_to_path_rejects_nested_run_dir_output(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(status="pass"),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    )
    out = run_dir / "nested" / "evidence_grounding_scorecard.json"

    with pytest.raises(ValueError, match="inside a run directory must be the top-level"):
        write_evidence_grounding_scorecard_to_path(scorecard, out, run_dir=run_dir)

    assert not out.exists()
    assert not out.parent.exists()


def test_write_evidence_grounding_scorecard_to_path_rejects_non_scorecard_run_dir_output(tmp_path):
    run_dir = tmp_path / "paper-1" / "run-1"
    run_dir.mkdir(parents=True)
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(status="pass"),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    )
    out = run_dir / "scorecard-copy.json"

    with pytest.raises(ValueError, match="must be evidence_grounding_scorecard.json"):
        write_evidence_grounding_scorecard_to_path(scorecard, out, run_dir=run_dir)

    assert not out.exists()
    assert not (run_dir / "evidence_grounding_scorecard.json").exists()


def test_write_evidence_grounding_scorecard_to_path_rejects_missing_run_dir(tmp_path):
    run_dir = tmp_path / "paper-1" / "missing-run"
    scorecard = build_evidence_grounding_scorecard(
        paper_id="paper-1",
        doc_id="doc-1",
        run_id="run-1",
        reader_eval=_reader_eval(),
        claimset_coverage=_coverage(status="pass"),
        evidence_extraction_bundle=_evidence_extraction(),
        visual_evidence_ledger=_visual_evidence(),
    )
    out = run_dir / "evidence_grounding_scorecard.json"

    with pytest.raises(ValueError, match="run_dir must be an existing directory"):
        write_evidence_grounding_scorecard_to_path(scorecard, out, run_dir=run_dir)

    assert not out.exists()
    assert not run_dir.exists()


def test_metric_validation_prevents_fake_not_available_values():
    with pytest.raises(ValidationError):
        EvidenceGroundingMetric(value=0.0, status="not_available")


def test_metric_validation_rejects_boolean_available_values():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingMetric(value=True, status="available")

    assert "metric value must be numeric, not a boolean" in str(excinfo.value)


def test_metric_validation_rejects_string_available_values():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingMetric(value="0.5", status="available")

    assert "metric value must be a JSON number, not a string" in str(excinfo.value)


def test_metric_validation_rejects_non_finite_available_values():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingMetric(value=float("nan"), status="available")

    assert "metric value must be finite" in str(excinfo.value)


def test_scorecard_schema_rejects_unknown_top_level_fields():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingScorecard(
            generated_at=datetime.now(timezone.utc),
            paper_id="paper-1",
            doc_id="doc-1",
            run_id="run-1",
            readiness_status="warn",
            recommended_next_action="Review scorecard.",
            contract_drift_field="must not be ignored",
        )

    assert "Extra inputs are not permitted" in str(excinfo.value)


def test_scorecard_metric_schema_rejects_unknown_fields():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingMetric(
            value=1.0,
            status="available",
            hidden_denominator=2,
        )

    assert "Extra inputs are not permitted" in str(excinfo.value)


def test_scorecard_build_request_rejects_unknown_fields():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingScorecardBuildRequest(
            run_dir="runs/paper-1/run-1",
            mutate_canonical_state=True,
        )

    assert "Extra inputs are not permitted" in str(excinfo.value)


def test_scorecard_schema_rejects_blank_identity_fields():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingScorecard(
            generated_at=datetime.now(timezone.utc),
            paper_id=" ",
            doc_id="doc-1",
            run_id="run-1",
            readiness_status="warn",
            recommended_next_action="Review scorecard.",
        )

    assert "paper_id is required" in str(excinfo.value)


def test_scorecard_schema_rejects_blank_recommended_next_action():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingScorecard(
            generated_at=datetime.now(timezone.utc),
            paper_id="paper-1",
            doc_id="doc-1",
            run_id="run-1",
            readiness_status="warn",
            recommended_next_action=" ",
        )

    assert "recommended_next_action is required" in str(excinfo.value)


def test_scorecard_schema_rejects_unknown_failure_codes():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingScorecard(
            generated_at=datetime.now(timezone.utc),
            paper_id="paper-1",
            doc_id="doc-1",
            run_id="run-1",
            readiness_status="fail",
            failure_counts_by_code={"NOT_A_PRODUCT_FAILURE_CODE": 1},
            recommended_next_action="Review unknown failure code.",
        )

    assert "unknown evidence grounding failure code" in str(excinfo.value)


def test_scorecard_schema_rejects_negative_failure_counts():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingScorecard(
            generated_at=datetime.now(timezone.utc),
            paper_id="paper-1",
            doc_id="doc-1",
            run_id="run-1",
            readiness_status="fail",
            failure_counts_by_code={"WRONG_LOCATOR": -1},
            recommended_next_action="Review negative failure count.",
        )

    assert "failure_counts_by_code values must be non-negative" in str(excinfo.value)


def test_scorecard_schema_rejects_boolean_failure_counts():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingScorecard(
            generated_at=datetime.now(timezone.utc),
            paper_id="paper-1",
            doc_id="doc-1",
            run_id="run-1",
            readiness_status="fail",
            failure_counts_by_code={"WRONG_LOCATOR": True},
            recommended_next_action="Review boolean failure count.",
        )

    assert "failure_counts_by_code values must be integer counts, not booleans" in str(excinfo.value)


def test_stage_failure_summary_rejects_negative_failure_count():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingStageFailureSummary(
            stage="grounding_checker",
            failure_count=-1,
            failure_codes=["WRONG_LOCATOR"],
        )

    assert "Input should be greater than or equal to 0" in str(excinfo.value)


def test_stage_failure_summary_rejects_boolean_failure_count():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingStageFailureSummary(
            stage="grounding_checker",
            failure_count=True,
            failure_codes=["WRONG_LOCATOR"],
        )

    assert "failure_count must be an integer count, not a boolean" in str(excinfo.value)


def test_stage_failure_summary_rejects_unknown_failure_codes():
    with pytest.raises(ValidationError) as excinfo:
        EvidenceGroundingStageFailureSummary(
            stage="unknown",
            failure_count=1,
            failure_codes=["NOT_A_PRODUCT_FAILURE_CODE"],
        )

    assert "NOT_A_PRODUCT_FAILURE_CODE" in str(excinfo.value)
