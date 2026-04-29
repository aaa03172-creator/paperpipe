from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SlotClassificationRerunDriftSurface(BaseModel):
    summary_path: str
    details_path: str
    run_id: str | None = None
    generated_at: datetime | None = None
    document_count: int = 0
    mismatch_count: int = 0
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    prediction_coverage_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class SlotClassificationRerunDriftDocument(BaseModel):
    paper_id: str
    doi: str | None = None
    title: str | None = None
    gold_slot: str
    prior_predicted_slot: str | None = None
    new_predicted_slot: str | None = None
    prior_matched: bool | None = None
    new_matched: bool | None = None
    prior_prediction_status: str | None = None
    new_prediction_status: str | None = None
    changed_fields: list[str] = Field(default_factory=list)


class SlotClassificationRerunDriftMetrics(BaseModel):
    document_count: int = 0
    drift_count: int = 0
    drift_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    mismatch_status_changed_count: int = 0
    predicted_slot_changed_count: int = 0
    prediction_status_changed_count: int = 0
    missing_in_prior_count: int = 0
    missing_in_new_count: int = 0


class SlotClassificationRerunDriftSummary(BaseModel):
    schema_version: str = "slot_classification_rerun_drift.v1"
    generated_at: datetime
    run_id: str
    prior: SlotClassificationRerunDriftSurface
    new: SlotClassificationRerunDriftSurface
    metrics: SlotClassificationRerunDriftMetrics
    documents_with_drift: list[str] = Field(default_factory=list)
    documents_missing_in_prior: list[str] = Field(default_factory=list)
    documents_missing_in_new: list[str] = Field(default_factory=list)


class SlotClassificationRerunDriftDetails(BaseModel):
    schema_version: str = "slot_classification_rerun_drift_details.v1"
    generated_at: datetime
    run_id: str
    documents: list[SlotClassificationRerunDriftDocument] = Field(default_factory=list)
