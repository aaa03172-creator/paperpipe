from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.agent_artifacts import ClaimSet


ClaimsetCoverageFocusStatus = Literal["generated", "skipped", "error"]


class ClaimsetCoverageFocusTarget(BaseModel):
    key: str
    label: str
    keywords: list[str] = Field(default_factory=list)
    page_ranges: list[str] = Field(default_factory=list)


class ClaimsetCoverageFocusMetrics(BaseModel):
    target_count: int = 0
    generated_claim_count: int = 0
    evidence_span_count: int = 0
    grounded_span_count: int = 0
    unresolved_span_count: int = 0


class ClaimsetCoverageFocusSidecar(BaseModel):
    schema_version: Literal["claimset_coverage_focus.v1"] = "claimset_coverage_focus.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    paper_id: str
    doc_id: str
    run_id: str
    source_artifacts: list[str] = Field(default_factory=list)
    generated_at: datetime
    focus_status: ClaimsetCoverageFocusStatus
    reason: str | None = None
    targets: list[ClaimsetCoverageFocusTarget] = Field(default_factory=list)
    metrics: ClaimsetCoverageFocusMetrics
    candidate_claimset: ClaimSet
    recommended_next_action: str
