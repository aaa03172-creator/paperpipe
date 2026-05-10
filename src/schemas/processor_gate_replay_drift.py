from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProcessorGateReplayDriftInput(BaseModel):
    db_path: str | None = None
    paper_id_migration_plan_path: str | None = None
    precanonical_db_path: str | None = None
    feedback_log_path: str | None = None
    row_count: int = 0
    high_threshold: float
    low_threshold: float


class ProcessorGateReplayDriftDocument(BaseModel):
    paper_id: str
    title: str | None = None
    precanonical_paper_id: str | None = None
    precanonical_created_at: str | None = None
    precanonical_updated_at: str | None = None
    precanonical_status: str | None = None
    precanonical_gate_decision: str | None = None
    precanonical_gate_reason: str | None = None
    precanonical_gate_reason_category: str | None = None
    precanonical_confidence: float | None = None
    identity_migration_hint: str | None = None
    feedback_log_paper_id: str | None = None
    feedback_log_avg_confidence: float | None = None
    feedback_log_gate_decision_hint: str | None = None
    feedback_log_timestamp: str | None = None
    feedback_log_timestamp_relation: str | None = None
    feedback_log_to_precanonical_update_relation: str | None = None
    feedback_log_import_hint: str | None = None
    fixture_classification_reason: str | None = None
    local_provenance_hint: str | None = None
    historical_rewrite_hint: str | None = None
    current_status: str | None = None
    current_gate_decision: str | None = None
    current_gate_reason: str | None = None
    current_gate_reason_category: str | None = None
    current_producer: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    timestamp_relation: str | None = None
    replay_status: str | None = None
    replay_gate_decision: str | None = None
    eligible_for_apply: bool = False
    skip_reason: str | None = None
    probable_drift_cause: str | None = None
    historical_path_hint: str | None = None
    confidence: float | None = None
    confidence_band: str | None = None
    has_evidence_text: bool = False
    evidence_source: str = "none"
    soft_tags_count: int = 0
    hard_tags_present: bool = False


class ProcessorGateReplayDriftMetrics(BaseModel):
    candidate_count: int = 0
    promotable_count: int = 0
    drift_count: int = 0
    drift_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    skip_reason_counts: dict[str, int] = Field(default_factory=dict)
    current_gate_decision_counts: dict[str, int] = Field(default_factory=dict)
    replay_gate_decision_counts: dict[str, int] = Field(default_factory=dict)
    decision_transition_counts: dict[str, int] = Field(default_factory=dict)
    gate_reason_category_counts: dict[str, int] = Field(default_factory=dict)
    timestamp_relation_counts: dict[str, int] = Field(default_factory=dict)
    probable_drift_cause_counts: dict[str, int] = Field(default_factory=dict)
    historical_path_hint_counts: dict[str, int] = Field(default_factory=dict)
    identity_migration_hint_counts: dict[str, int] = Field(default_factory=dict)
    feedback_log_import_hint_counts: dict[str, int] = Field(default_factory=dict)
    feedback_log_timestamp_relation_counts: dict[str, int] = Field(default_factory=dict)
    feedback_log_to_precanonical_update_relation_counts: dict[str, int] = Field(default_factory=dict)
    local_provenance_hint_counts: dict[str, int] = Field(default_factory=dict)
    historical_rewrite_hint_counts: dict[str, int] = Field(default_factory=dict)
    confidence_value_counts: dict[str, int] = Field(default_factory=dict)
    confidence_band_counts: dict[str, int] = Field(default_factory=dict)
    evidence_source_counts: dict[str, int] = Field(default_factory=dict)


class ProcessorGateReplayDriftSummary(BaseModel):
    schema_version: str = "processor_gate_replay_drift_summary.v5"
    generated_at: datetime
    run_id: str
    inputs: ProcessorGateReplayDriftInput
    metrics: ProcessorGateReplayDriftMetrics
    documents_with_drift: list[str] = Field(default_factory=list)


class ProcessorGateReplayDriftDetails(BaseModel):
    schema_version: str = "processor_gate_replay_drift_details.v5"
    generated_at: datetime
    run_id: str
    documents: list[ProcessorGateReplayDriftDocument] = Field(default_factory=list)
