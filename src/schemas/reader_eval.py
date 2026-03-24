from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReaderEvalClaimEntry(BaseModel):
    claim_id: str
    statement: str
    supported: bool
    unsupported: bool
    unknown: bool
    unknown_reason: str | None = None
    heuristic_backfill: bool = False
    evidence_span_count: int = 0
    grounded_span_count: int = 0
    unresolved_span_count: int = 0
    ambiguous_span_count: int = 0
    failed_grounding_span_count: int = 0
    grounding_resolutions: list[str] = Field(default_factory=list)
    limitation_count: int = 0
    grounded_limitation_count: int = 0
    statement_evidence_overlap_ratio: float = 0.0
    low_statement_evidence_overlap: bool = False


class ReaderEvalMetrics(BaseModel):
    claim_count: int = 0
    supported_claim_count: int = 0
    unsupported_claim_count: int = 0
    unknown_claim_count: int = 0
    heuristic_backfill_claim_count: int = 0
    evidence_span_count: int = 0
    grounded_span_count: int = 0
    unresolved_span_count: int = 0
    ambiguous_span_count: int = 0
    failed_grounding_span_count: int = 0
    limitation_count: int = 0
    grounded_limitation_count: int = 0
    low_overlap_claim_count: int = 0


class ReaderEvalSidecar(BaseModel):
    schema_version: str = "reader_eval.v1"
    generated_at: datetime
    paper_id: str
    doc_id: str
    run_id: str
    metrics: ReaderEvalMetrics
    claims: list[ReaderEvalClaimEntry] = Field(default_factory=list)
