from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


PayloadClass = Literal["local_only", "lab_allowed", "external_allowed"]
TrainingTaskType = Literal[
    "extraction",
    "evidence_linking",
    "correction",
    "slot_classification",
    "reader_quality",
]
TrainingReviewStatus = Literal["draft", "reviewed", "accepted", "rejected"]
TrainingArtifactLayer = Literal["review_gate_artifact"]
TrainingCanonicalStatus = Literal["non_canonical"]
EvidenceRankingSource = Literal[
    "keyword",
    "semantic",
    "title_reference",
    "table_figure_anchor",
    "graph_sidecar",
    "hybrid",
]
CorrectionIssueLabel = Literal[
    "supported",
    "weak",
    "unsupported",
    "overclaim",
    "numeric_mismatch",
    "location_missing",
    "uncertainty_missing",
]


class _StrictTrainingExampleModel(BaseModel):
    model_config = {"extra": "forbid"}


def _strip_required(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} is required")
    return stripped


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class TrainingSourceSpan(_StrictTrainingExampleModel):
    span_id: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    page_index: int | None = Field(default=None, ge=0)
    block_id: str | None = None
    line_id: str | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    text_hash: str | None = None

    @model_validator(mode="after")
    def normalize_and_validate_span(self):
        self.span_id = _strip_required(self.span_id, field_name="span_id")
        self.source_ref = _strip_required(self.source_ref, field_name="source_ref")
        self.block_id = _strip_optional(self.block_id)
        self.line_id = _strip_optional(self.line_id)
        self.text_hash = _strip_optional(self.text_hash)
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be provided together")
        if self.char_start is not None and self.char_end is not None and self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class TrainingInputRef(_StrictTrainingExampleModel):
    artifact_path: str = Field(..., min_length=1)
    artifact_kind: str = Field(..., min_length=1)
    excerpt_ref: str | None = None
    excerpt_hash: str | None = None

    @model_validator(mode="after")
    def normalize_ref(self):
        self.artifact_path = _strip_required(self.artifact_path, field_name="artifact_path")
        if self.artifact_path.startswith("/") or ".." in self.artifact_path.split("/"):
            raise ValueError("artifact_path must be artifact-relative")
        self.artifact_kind = _strip_required(self.artifact_kind, field_name="artifact_kind")
        self.excerpt_ref = _strip_optional(self.excerpt_ref)
        self.excerpt_hash = _strip_optional(self.excerpt_hash)
        return self


class TrainingExample(_StrictTrainingExampleModel):
    schema_version: Literal["training_example.v1"] = "training_example.v1"
    layer: TrainingArtifactLayer = "review_gate_artifact"
    canonical_status: TrainingCanonicalStatus = "non_canonical"
    example_id: str = Field(..., min_length=1)
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    artifact_id: str = Field(..., min_length=1)
    task_type: TrainingTaskType
    payload_class: PayloadClass
    input_ref: TrainingInputRef
    source_spans: list[TrainingSourceSpan] = Field(..., min_length=1)
    candidate_output: dict[str, Any] = Field(default_factory=dict)
    reviewed_output: dict[str, Any] = Field(default_factory=dict)
    review_status: TrainingReviewStatus
    failure_taxonomy: list[str] = Field(default_factory=list)
    reviewer_notes: str | None = None
    created_at: datetime

    @field_validator("failure_taxonomy", mode="before")
    @classmethod
    def normalize_failure_taxonomy(cls, value):
        if value is None:
            return []
        return value

    @model_validator(mode="after")
    def normalize_and_validate_example(self):
        self.example_id = _strip_required(self.example_id, field_name="example_id")
        self.paper_id = _strip_required(self.paper_id, field_name="paper_id")
        self.run_id = _strip_required(self.run_id, field_name="run_id")
        self.artifact_id = _strip_required(self.artifact_id, field_name="artifact_id")
        self.reviewer_notes = _strip_optional(self.reviewer_notes)
        self.failure_taxonomy = [
            item.strip()
            for item in self.failure_taxonomy
            if isinstance(item, str) and item.strip()
        ]
        if self.review_status in {"reviewed", "accepted", "rejected"} and not self.reviewed_output:
            raise ValueError("reviewed examples require reviewed_output")
        if self.candidate_output == self.reviewed_output and self.review_status in {"reviewed", "accepted"}:
            raise ValueError("reviewed output must be distinct from candidate output when accepted or reviewed")
        return self


class EvidenceRerankExample(_StrictTrainingExampleModel):
    schema_version: Literal["evidence_rerank_example.v1"] = "evidence_rerank_example.v1"
    layer: TrainingArtifactLayer = "review_gate_artifact"
    canonical_status: TrainingCanonicalStatus = "non_canonical"
    example_id: str = Field(..., min_length=1)
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    claim_id: str = Field(..., min_length=1)
    claim_text: str = Field(..., min_length=1)
    payload_class: PayloadClass
    positive_span_ids: list[str] = Field(..., min_length=1)
    hard_negative_span_ids: list[str] = Field(default_factory=list)
    candidate_span_pool_ref: str = Field(..., min_length=1)
    ranking_source: EvidenceRankingSource
    source_spans: list[TrainingSourceSpan] = Field(..., min_length=1)
    adjudication_status: TrainingReviewStatus
    created_at: datetime

    @model_validator(mode="after")
    def normalize_and_validate_rerank(self):
        self.example_id = _strip_required(self.example_id, field_name="example_id")
        self.paper_id = _strip_required(self.paper_id, field_name="paper_id")
        self.run_id = _strip_required(self.run_id, field_name="run_id")
        self.claim_id = _strip_required(self.claim_id, field_name="claim_id")
        self.claim_text = _strip_required(self.claim_text, field_name="claim_text")
        self.positive_span_ids = [_strip_required(item, field_name="positive_span_id") for item in self.positive_span_ids]
        self.hard_negative_span_ids = [
            _strip_required(item, field_name="hard_negative_span_id")
            for item in self.hard_negative_span_ids
        ]
        overlap = set(self.positive_span_ids).intersection(self.hard_negative_span_ids)
        if overlap:
            raise ValueError("positive_span_ids and hard_negative_span_ids must not overlap")
        available_span_ids = {span.span_id for span in self.source_spans}
        missing_positive_ids = [span_id for span_id in self.positive_span_ids if span_id not in available_span_ids]
        if missing_positive_ids:
            raise ValueError("positive_span_ids must reference source_spans")
        self.candidate_span_pool_ref = _strip_required(
            self.candidate_span_pool_ref,
            field_name="candidate_span_pool_ref",
        )
        return self


class CorrectionReviewExample(_StrictTrainingExampleModel):
    schema_version: Literal["correction_review_example.v1"] = "correction_review_example.v1"
    layer: TrainingArtifactLayer = "review_gate_artifact"
    canonical_status: TrainingCanonicalStatus = "non_canonical"
    example_id: str = Field(..., min_length=1)
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    claim_id: str = Field(..., min_length=1)
    claim_text: str = Field(..., min_length=1)
    evidence_text_ref: str = Field(..., min_length=1)
    payload_class: PayloadClass
    observed_issue: CorrectionIssueLabel
    expected_label: CorrectionIssueLabel
    minimal_correction: str | None = None
    must_preserve_terms: list[str] = Field(default_factory=list)
    must_not_infer: list[str] = Field(default_factory=list)
    source_spans: list[TrainingSourceSpan] = Field(..., min_length=1)
    review_status: TrainingReviewStatus
    created_at: datetime

    @model_validator(mode="after")
    def normalize_and_validate_correction(self):
        self.example_id = _strip_required(self.example_id, field_name="example_id")
        self.paper_id = _strip_required(self.paper_id, field_name="paper_id")
        self.run_id = _strip_required(self.run_id, field_name="run_id")
        self.claim_id = _strip_required(self.claim_id, field_name="claim_id")
        self.claim_text = _strip_required(self.claim_text, field_name="claim_text")
        self.evidence_text_ref = _strip_required(self.evidence_text_ref, field_name="evidence_text_ref")
        self.minimal_correction = _strip_optional(self.minimal_correction)
        self.must_preserve_terms = [
            item.strip()
            for item in self.must_preserve_terms
            if isinstance(item, str) and item.strip()
        ]
        self.must_not_infer = [
            item.strip()
            for item in self.must_not_infer
            if isinstance(item, str) and item.strip()
        ]
        if self.expected_label in {"overclaim", "numeric_mismatch", "uncertainty_missing"} and not self.minimal_correction:
            raise ValueError("correctable labels require minimal_correction")
        return self


MLTrainingRecord = TrainingExample | EvidenceRerankExample | CorrectionReviewExample
