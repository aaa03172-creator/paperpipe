from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SlotClassificationGoldsetAuditInput(BaseModel):
    goldset_csv_path: str
    predictions_jsonl_path: str | None = None
    row_count: int = 0
    rows_with_gold_slot: int = 0
    rows_with_predictions: int = 0


class SlotClassificationGoldsetAuditDocument(BaseModel):
    paper_id: str
    doi: str | None = None
    title: str | None = None
    current_slot: str | None = None
    gold_slot: str
    gold_slot_rationale: str | None = None
    input_richness: str = "title_only"
    predicted_slot: str | None = None
    matched: bool | None = None
    prediction_status: str = "missing"
    prediction_source: str = "none"
    summary_present: bool = False
    full_text_present: bool = False
    first_pass_predicted_slot: str | None = None
    final_source: str | None = None
    adjudication_triggered: bool | None = None
    adjudication_reason: str | None = None
    confidence: float | None = None


class SlotClassificationGoldsetAuditMetrics(BaseModel):
    document_count: int = 0
    evaluated_count: int = 0
    matched_count: int = 0
    mismatch_count: int = 0
    missing_prediction_count: int = 0
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    prediction_coverage_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    gold_slot_counts: dict[str, int] = Field(default_factory=dict)
    predicted_slot_counts: dict[str, int] = Field(default_factory=dict)
    confusion_counts: dict[str, int] = Field(default_factory=dict)
    per_gold_slot_accuracy: dict[str, float] = Field(default_factory=dict)
    per_gold_slot_coverage: dict[str, float] = Field(default_factory=dict)
    prediction_status_counts: dict[str, int] = Field(default_factory=dict)
    prediction_source_counts: dict[str, int] = Field(default_factory=dict)
    input_richness_counts: dict[str, int] = Field(default_factory=dict)


class SlotClassificationGoldsetAuditSummary(BaseModel):
    schema_version: str = "slot_classification_goldset_audit_summary.v3"
    generated_at: datetime
    run_id: str
    inputs: SlotClassificationGoldsetAuditInput
    metrics: SlotClassificationGoldsetAuditMetrics
    documents_with_mismatch: list[str] = Field(default_factory=list)
    documents_missing_prediction: list[str] = Field(default_factory=list)


class SlotClassificationGoldsetAuditDetails(BaseModel):
    schema_version: str = "slot_classification_goldset_audit_details.v3"
    generated_at: datetime
    run_id: str
    documents: list[SlotClassificationGoldsetAuditDocument] = Field(default_factory=list)
