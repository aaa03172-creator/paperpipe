from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TeacherReviewEvalClaimEntry(BaseModel):
    claim_id: str
    statement: str
    reviewed: bool = False
    anchor_quality_label: str | None = None
    support_label: str | None = None
    location_label: str | None = None
    keep_teacher_claim: bool | None = None
    source_page: int | None = None
    source_chunk_id: str | None = None
    bundle_outcome: str | None = None
    issue_pattern: str | None = None
    reviewer: str | None = None
    notes: str | None = None


class TeacherReviewEvalMetrics(BaseModel):
    claim_count: int = 0
    reviewed_claim_count: int = 0
    missing_review_count: int = 0
    extra_review_count: int = 0
    duplicate_review_row_count: int = 0
    direct_quote_support_count: int = 0
    adjacent_support_count: int = 0
    heading_level_support_count: int = 0
    misaligned_quote_count: int = 0
    fragmentary_claim_count: int = 0
    supported_claim_count: int = 0
    unsupported_claim_count: int = 0
    ambiguous_claim_count: int = 0
    good_location_count: int = 0
    weak_location_count: int = 0
    misleading_location_count: int = 0
    keep_teacher_claim_count: int = 0
    drop_teacher_claim_count: int = 0
    supported_claim_precision: float = 0.0


class TeacherReviewEvalSidecar(BaseModel):
    schema_version: str = "teacher_review_eval.v1"
    generated_at: datetime
    paper_id: str
    doc_id: str
    bundle_dir: str
    review_source: str
    review_jsonl_path: str | None = None
    bundle_outcome: str | None = None
    issue_patterns: list[str] = Field(default_factory=list)
    metrics: TeacherReviewEvalMetrics
    claims: list[TeacherReviewEvalClaimEntry] = Field(default_factory=list)
