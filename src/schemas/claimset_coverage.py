from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ClaimsetCoverageStatus = Literal["pass", "warn", "fail"]


class ClaimsetCoverageMetrics(BaseModel):
    claim_count: int = 0
    evidence_span_count: int = 0
    grounded_span_count: int = 0
    unresolved_span_count: int = 0
    grounded_evidence_ratio: float = 0.0
    document_page_count: int = 0
    covered_page_count: int = 0
    page_coverage_ratio: float = 0.0
    unique_section_count: int = 0
    duplicate_cluster_count: int = 0
    missing_topic_signal_count: int = 0


class ClaimsetCoveragePageSummary(BaseModel):
    covered_pages: list[int] = Field(default_factory=list)
    missing_page_ranges: list[str] = Field(default_factory=list)
    undercovered_page_ranges: list[str] = Field(default_factory=list)


class ClaimsetCoverageTopicSignal(BaseModel):
    key: str
    label: str
    keywords: list[str] = Field(default_factory=list)
    present_in_document: bool = False
    covered_by_claimset: bool = False
    evidence_pages: list[int] = Field(default_factory=list)


class ClaimsetCoverageDuplicateWarning(BaseModel):
    claim_ids: list[str] = Field(default_factory=list)
    similarity: float = 0.0
    reason: str


class ClaimsetCoverageEvidenceSummary(BaseModel):
    total_spans: int = 0
    grounded_spans: int = 0
    unresolved_spans: int = 0
    grounded_ratio: float = 0.0
    pages_with_grounded_evidence: list[int] = Field(default_factory=list)


class ClaimsetCoverageSidecar(BaseModel):
    schema_version: Literal["claimset_coverage.v1"] = "claimset_coverage.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    paper_id: str
    doc_id: str
    run_id: str
    source_artifacts: list[str] = Field(default_factory=list)
    generated_at: datetime
    coverage_status: ClaimsetCoverageStatus
    metrics: ClaimsetCoverageMetrics
    page_summary: ClaimsetCoveragePageSummary
    topic_signals: list[ClaimsetCoverageTopicSignal] = Field(default_factory=list)
    duplicate_warnings: list[ClaimsetCoverageDuplicateWarning] = Field(default_factory=list)
    evidence_summary: ClaimsetCoverageEvidenceSummary
    recommended_next_action: str
    reason_codes: list[str] = Field(default_factory=list)
