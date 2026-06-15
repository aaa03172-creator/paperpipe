from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.ml_training_examples import PayloadClass, TrainingSourceSpan


EvidenceRerankLayer = Literal["review_gate_artifact"]
EvidenceRerankCanonicalStatus = Literal["non_canonical"]


class _StrictEvidenceRerankModel(BaseModel):
    model_config = {"extra": "forbid"}


class EvidenceRerankCandidateSpan(_StrictEvidenceRerankModel):
    span_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    source_span: TrainingSourceSpan
    original_rank: int = Field(..., ge=1)
    heuristic_score: float = 0.0
    is_positive: bool = False
    is_hard_negative: bool = False

    @model_validator(mode="after")
    def normalize_candidate_span(self):
        self.span_id = self.span_id.strip()
        self.text = self.text.strip()
        if not self.span_id:
            raise ValueError("span_id is required")
        if not self.text:
            raise ValueError("text is required")
        if self.is_positive and self.is_hard_negative:
            raise ValueError("candidate span cannot be both positive and hard negative")
        if self.span_id != self.source_span.span_id:
            raise ValueError("span_id must match source_span.span_id")
        return self


class EvidenceRerankCandidatePool(_StrictEvidenceRerankModel):
    schema_version: Literal["evidence_rerank_candidate_pool.v1"] = "evidence_rerank_candidate_pool.v1"
    layer: EvidenceRerankLayer = "review_gate_artifact"
    canonical_status: EvidenceRerankCanonicalStatus = "non_canonical"
    example_id: str = Field(..., min_length=1)
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    claim_id: str = Field(..., min_length=1)
    claim_text: str = Field(..., min_length=1)
    payload_class: PayloadClass
    candidates: list[EvidenceRerankCandidateSpan] = Field(..., min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def normalize_candidate_pool(self):
        self.example_id = self.example_id.strip()
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.claim_id = self.claim_id.strip()
        self.claim_text = self.claim_text.strip()
        span_ids = [candidate.span_id for candidate in self.candidates]
        if len(span_ids) != len(set(span_ids)):
            raise ValueError("candidate span_id values must be unique")
        if not any(candidate.is_positive for candidate in self.candidates):
            raise ValueError("candidate pool requires at least one positive span")
        return self


class EvidenceRerankPilotReport(_StrictEvidenceRerankModel):
    schema_version: Literal["evidence_rerank_pilot_report.v1"] = "evidence_rerank_pilot_report.v1"
    layer: EvidenceRerankLayer = "review_gate_artifact"
    canonical_status: EvidenceRerankCanonicalStatus = "non_canonical"
    evaluated_at: datetime
    payload_class: PayloadClass
    example_count: int = Field(..., ge=1)
    candidate_count: int = Field(..., ge=1)
    original_top_1_hit_rate: float = Field(..., ge=0.0, le=1.0)
    reranked_top_1_hit_rate: float = Field(..., ge=0.0, le=1.0)
    original_mrr: float = Field(..., ge=0.0, le=1.0)
    reranked_mrr: float = Field(..., ge=0.0, le=1.0)
    hard_negative_top_1_rate: float = Field(..., ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.warnings = [warning.strip() for warning in self.warnings if warning.strip()]
        return self
