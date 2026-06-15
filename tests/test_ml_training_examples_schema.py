from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.ml_training_examples import (
    CorrectionReviewExample,
    EvidenceRerankExample,
    TrainingExample,
    TrainingInputRef,
    TrainingSourceSpan,
)
from src.schemas.claim_evidence_correction import ClaimEvidenceCorrectionCase, ClaimEvidenceCorrectionLocator
from src.services.ml_training_examples import (
    build_correction_review_example_from_case,
    write_run_ml_training_examples_sidecar,
)


def _now() -> datetime:
    return datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _span(span_id: str = "span-positive") -> TrainingSourceSpan:
    return TrainingSourceSpan(
        span_id=span_id,
        source_ref="document_artifact.json#/pages/0/blocks/0/lines/0",
        page_index=0,
        block_id="block-001",
        line_id="line-001",
        char_start=10,
        char_end=42,
        text_hash="sha256:abc123",
    )


def _input_ref() -> TrainingInputRef:
    return TrainingInputRef(
        artifact_path="claimset.json",
        artifact_kind="claimset",
        excerpt_ref="claimset.json#/claims/0",
        excerpt_hash="sha256:def456",
    )


def test_training_example_requires_source_trace_and_reviewed_output_separation() -> None:
    example = TrainingExample(
        example_id="train_example_001",
        paper_id="paper-001",
        run_id="run-001",
        artifact_id="claimset-001",
        task_type="extraction",
        payload_class="local_only",
        input_ref=_input_ref(),
        source_spans=[_span()],
        candidate_output={"claim": "Treatment improves survival."},
        reviewed_output={"claim": "Treatment was associated with improved survival in this cohort."},
        review_status="accepted",
        failure_taxonomy=[" overclaim ", "overclaim", ""],
        reviewer_notes=" Keep cohort qualifier. ",
        created_at=_now(),
    )

    assert example.schema_version == "training_example.v1"
    assert example.layer == "review_gate_artifact"
    assert example.canonical_status == "non_canonical"
    assert example.payload_class == "local_only"
    assert example.failure_taxonomy == ["overclaim", "overclaim"]
    assert example.reviewer_notes == "Keep cohort qualifier."


def test_training_example_rejects_reviewed_record_without_reviewed_output() -> None:
    with pytest.raises(ValidationError):
        TrainingExample(
            example_id="train_example_002",
            paper_id="paper-001",
            run_id="run-001",
            artifact_id="claimset-001",
            task_type="extraction",
            payload_class="local_only",
            input_ref=_input_ref(),
            source_spans=[_span()],
            candidate_output={"claim": "Treatment improves survival."},
            reviewed_output={},
            review_status="accepted",
            created_at=_now(),
        )


def test_training_input_ref_rejects_absolute_or_parent_paths() -> None:
    with pytest.raises(ValidationError):
        TrainingInputRef(artifact_path="/tmp/claimset.json", artifact_kind="claimset")

    with pytest.raises(ValidationError):
        TrainingInputRef(artifact_path="../claimset.json", artifact_kind="claimset")


def test_evidence_rerank_example_validates_positive_and_negative_spans() -> None:
    example = EvidenceRerankExample(
        example_id="rerank_example_001",
        paper_id="paper-001",
        run_id="run-001",
        claim_id="claim-001",
        claim_text="Treatment was associated with improved survival.",
        payload_class="local_only",
        positive_span_ids=["span-positive"],
        hard_negative_span_ids=["span-negative"],
        candidate_span_pool_ref="candidate_spans.json",
        ranking_source="hybrid",
        source_spans=[_span("span-positive"), _span("span-negative")],
        adjudication_status="reviewed",
        created_at=_now(),
    )

    assert example.schema_version == "evidence_rerank_example.v1"
    assert example.positive_span_ids == ["span-positive"]

    with pytest.raises(ValidationError):
        EvidenceRerankExample(
            example_id="rerank_example_002",
            paper_id="paper-001",
            run_id="run-001",
            claim_id="claim-001",
            claim_text="Treatment was associated with improved survival.",
            payload_class="local_only",
            positive_span_ids=["span-positive"],
            hard_negative_span_ids=["span-positive"],
            candidate_span_pool_ref="candidate_spans.json",
            ranking_source="hybrid",
            source_spans=[_span("span-positive")],
            adjudication_status="reviewed",
            created_at=_now(),
        )


def test_correction_review_example_requires_minimal_correction_for_correctable_labels() -> None:
    example = CorrectionReviewExample(
        example_id="correction_example_001",
        paper_id="paper-001",
        run_id="run-001",
        claim_id="claim-001",
        claim_text="Treatment improves survival.",
        evidence_text_ref="document_artifact.json#/pages/0/blocks/0/lines/0",
        payload_class="local_only",
        observed_issue="overclaim",
        expected_label="overclaim",
        minimal_correction="Treatment was associated with improved survival in this cohort.",
        must_preserve_terms=["survival", "cohort"],
        must_not_infer=["causality"],
        source_spans=[_span()],
        review_status="accepted",
        created_at=_now(),
    )

    assert example.schema_version == "correction_review_example.v1"
    assert example.minimal_correction == "Treatment was associated with improved survival in this cohort."

    with pytest.raises(ValidationError):
        CorrectionReviewExample(
            example_id="correction_example_002",
            paper_id="paper-001",
            run_id="run-001",
            claim_id="claim-001",
            claim_text="Treatment improves survival.",
            evidence_text_ref="document_artifact.json#/pages/0/blocks/0/lines/0",
            payload_class="local_only",
            observed_issue="overclaim",
            expected_label="overclaim",
            source_spans=[_span()],
            review_status="accepted",
            created_at=_now(),
        )


def test_training_examples_sidecar_writer_writes_jsonl_under_artifact_dir(tmp_path) -> None:
    example = CorrectionReviewExample(
        example_id="correction_example_003",
        paper_id="paper-001",
        run_id="run-001",
        claim_id="claim-001",
        claim_text="Treatment improves survival.",
        evidence_text_ref="document_artifact.json#/pages/0/blocks/0/lines/0",
        payload_class="local_only",
        observed_issue="overclaim",
        expected_label="overclaim",
        minimal_correction="Treatment was associated with improved survival in this cohort.",
        source_spans=[_span()],
        review_status="accepted",
        created_at=_now(),
    )

    out = write_run_ml_training_examples_sidecar(tmp_path / "run-artifacts", [example])

    assert out.name == "ml_training_examples.jsonl"
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert rows == [example.model_dump(mode="json")]
    assert rows[0]["canonical_status"] == "non_canonical"
    assert rows[0]["payload_class"] == "local_only"


def test_correction_case_converter_preserves_source_trace_and_payload_class() -> None:
    correction = ClaimEvidenceCorrectionCase(
        correction_id="corr-001",
        paper_id="paper-001",
        run_id="run-001",
        claim_id="claim-001",
        field_path="claims.0.text",
        before_claim_text="Treatment improves survival.",
        after_claim_text="Treatment was associated with improved survival in this cohort.",
        before_evidence_refs=[
            ClaimEvidenceCorrectionLocator(page=0, chunk_id="chunk-001", char_start=10, char_end=42)
        ],
        after_evidence_refs=[
            ClaimEvidenceCorrectionLocator(
                page=0,
                chunk_id="chunk-002",
                char_start=50,
                char_end=120,
                section="Results",
                quote="associated with improved survival",
            )
        ],
        reason_codes=["OVERSTATED_RESULT"],
        reviewer_id="reviewer-001",
        parser_version="parser.v1",
        llm_provider="ollama",
        llm_model="qwen3.5:4b",
        llm_model_version="qwen3.5:4b",
        prompt_version="reader.v1",
        reader_profile_version="default.v1",
        created_at=_now(),
        accepted_for_eval=True,
    )

    example = build_correction_review_example_from_case(correction)

    assert example.schema_version == "correction_review_example.v1"
    assert example.example_id == "correction_review:corr-001"
    assert example.payload_class == "local_only"
    assert example.review_status == "accepted"
    assert example.expected_label == "overclaim"
    assert example.minimal_correction == "Treatment was associated with improved survival in this cohort."
    assert example.evidence_text_ref == "document_artifact.json#page=0&chunk_id=chunk-002&section=Results"
    assert example.source_spans[0].span_id == "corr-001:evidence:1"
    assert example.source_spans[0].page_index == 0
    assert example.source_spans[0].block_id == "chunk-002"
