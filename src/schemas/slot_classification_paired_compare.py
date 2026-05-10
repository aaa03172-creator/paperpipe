from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SlotClassificationPairedCompareSurface(BaseModel):
    summary_path: str
    run_id: str | None = None
    generated_at: datetime | None = None
    document_count: int = 0
    evaluated_count: int = 0
    mismatch_count: int = 0
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    prediction_coverage_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    documents_with_mismatch: list[str] = Field(default_factory=list)


class SlotClassificationPairedCompareInputs(BaseModel):
    default_template: SlotClassificationPairedCompareSurface
    boundary_companion: SlotClassificationPairedCompareSurface


class SlotClassificationPairedCompareThresholds(BaseModel):
    allow_default_accuracy_drop: float = Field(default=0.0, ge=0.0)
    allow_boundary_accuracy_drop: float = Field(default=0.0, ge=0.0)
    allow_default_coverage_drop: float = Field(default=0.0, ge=0.0)
    allow_boundary_coverage_drop: float = Field(default=0.0, ge=0.0)
    allow_default_mismatch_increase: int = Field(default=0, ge=0)
    allow_boundary_mismatch_increase: int = Field(default=0, ge=0)


class SlotClassificationPairedCompareCheck(BaseModel):
    name: str
    baseline: float
    new: float
    required: float
    passed: bool
    direction: str


class SlotClassificationPairedCompareDecision(BaseModel):
    passed: bool = False
    failed_checks: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    error_migration_detected: bool = False
    tradeoff_review_required: bool = False
    surfaces_with_mismatch_migration: list[str] = Field(default_factory=list)
    checks: list[SlotClassificationPairedCompareCheck] = Field(default_factory=list)
    default_template_resolved_mismatches: list[str] = Field(default_factory=list)
    default_template_new_mismatches: list[str] = Field(default_factory=list)
    boundary_companion_resolved_mismatches: list[str] = Field(default_factory=list)
    boundary_companion_new_mismatches: list[str] = Field(default_factory=list)
    decision_reason: str


class SlotClassificationPairedCompareSummary(BaseModel):
    schema_version: str = "slot_classification_paired_compare.v1"
    generated_at: datetime
    run_id: str
    baseline: SlotClassificationPairedCompareInputs
    candidate: SlotClassificationPairedCompareInputs
    thresholds: SlotClassificationPairedCompareThresholds
    decision: SlotClassificationPairedCompareDecision
