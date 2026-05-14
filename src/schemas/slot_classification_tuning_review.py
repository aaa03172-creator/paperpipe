from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SlotClassificationTuningReviewInputs(BaseModel):
    paired_compare_summary_path: str | None = None
    default_rerun_drift_summary_path: str | None = None
    boundary_rerun_drift_summary_path: str | None = None
    max_default_rerun_drift_rate: float = Field(default=0.0, ge=0.0)
    max_boundary_rerun_drift_rate: float = Field(default=0.0, ge=0.0)


class SlotClassificationTuningReviewAction(BaseModel):
    order: int
    action: str
    target: str | None = None
    blocking: bool = False
    summary: str
    evidence: str | None = None


class SlotClassificationTuningReviewDecision(BaseModel):
    recommended_action: str
    review_ready: bool = False
    decision_reason: str
    next_step: str
    latest_compare_run_id: str | None = None
    paired_compare_status: str = "missing"
    default_rerun_status: str = "missing"
    boundary_rerun_status: str = "missing"
    prompt_change_ready: bool = False
    prompt_change_status: str
    prompt_change_blocker: str
    tuning_targets: list[str] = Field(default_factory=list)
    tuning_actions: list[dict[str, str]] = Field(default_factory=list)
    action_plan: list[SlotClassificationTuningReviewAction] = Field(default_factory=list)
    tuning_recommendations: list[str] = Field(default_factory=list)


class SlotClassificationTuningReviewSummary(BaseModel):
    schema_version: str = "slot_classification_tuning_review.v1"
    generated_at: datetime
    run_id: str
    advisory_only: bool = True
    inputs: SlotClassificationTuningReviewInputs
    decision: SlotClassificationTuningReviewDecision
    signal_summary: dict[str, object] = Field(default_factory=dict)
