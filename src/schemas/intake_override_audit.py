from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IntakeOverrideAuditInput(BaseModel):
    source: str
    db_path: str | None = None
    rows_jsonl_path: str | None = None
    row_count: int = 0


class IntakeOverrideAuditDocument(BaseModel):
    paper_id: str
    title: str | None = None
    producer: str | None = None
    is_test_fixture: bool = False
    fixture_reason: str | None = None
    has_feedback_json: bool = False
    has_intake_override_log: bool = False
    parse_error: str | None = None
    analysis_available: bool | None = None
    llm_tagging_used: bool | None = None
    llm_slot_classification_used: bool | None = None
    llm_tagging_adjudication_used: bool | None = None
    llm_tagging_adjudication_reason: str | None = None
    llm_slot_adjudication_used: bool | None = None
    llm_slot_adjudication_reason: str | None = None
    triage_override: bool | None = None
    input_slot: str | None = None
    stored_slot: str | None = None
    slot_changed: bool | None = None
    input_tags: list[str] = Field(default_factory=list)
    stored_tags: list[str] = Field(default_factory=list)
    tags_changed: bool | None = None
    processing_status: str | None = None
    issues_state: str | None = None
    confidence: float | None = None
    has_selection_context: bool = False
    selection_method: str | None = None
    selection_selected_rank: int | None = None
    selection_candidate_count: int | None = None
    selection_score: float | None = None
    selection_skipped_processed_count: int = 0


class IntakeOverrideAuditMetrics(BaseModel):
    document_count: int = 0
    test_fixture_document_count: int = 0
    non_fixture_document_count: int = 0
    audited_document_count: int = 0
    has_feedback_json_count: int = 0
    no_feedback_json_count: int = 0
    test_fixture_no_feedback_json_count: int = 0
    non_fixture_no_feedback_json_count: int = 0
    missing_intake_override_log_count: int = 0
    invalid_feedback_json_count: int = 0
    invalid_intake_override_log_count: int = 0
    triage_override_count: int = 0
    slot_disagreement_count: int = 0
    tag_disagreement_count: int = 0
    analysis_unavailable_count: int = 0
    issues_state_unavailable_count: int = 0
    selection_context_count: int = 0
    selection_fallback_count: int = 0
    llm_slot_classification_used_count: int = 0
    llm_tagging_used_count: int = 0
    llm_slot_adjudication_used_count: int = 0
    llm_tagging_adjudication_used_count: int = 0
    triage_override_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    slot_disagreement_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    tag_disagreement_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    analysis_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    issues_state_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    selection_context_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    selection_fallback_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    llm_slot_adjudication_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    llm_tagging_adjudication_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    producer_counts: dict[str, int] = Field(default_factory=dict)
    processing_status_counts: dict[str, int] = Field(default_factory=dict)


class IntakeOverrideProducerMetrics(BaseModel):
    producer: str
    metrics: IntakeOverrideAuditMetrics


class IntakeOverrideAuditSummary(BaseModel):
    schema_version: str = "intake_override_audit_summary.v1"
    generated_at: datetime
    run_id: str
    inputs: IntakeOverrideAuditInput
    metrics: IntakeOverrideAuditMetrics
    producer_metrics: list[IntakeOverrideProducerMetrics] = Field(default_factory=list)
    documents_with_slot_disagreement: list[str] = Field(default_factory=list)
    documents_with_tag_disagreement: list[str] = Field(default_factory=list)
    documents_with_missing_log: list[str] = Field(default_factory=list)
    documents_with_missing_log_non_fixture: list[str] = Field(default_factory=list)
    documents_with_invalid_log: list[str] = Field(default_factory=list)
    documents_with_selection_context: list[str] = Field(default_factory=list)
    documents_with_selection_fallback: list[str] = Field(default_factory=list)


class IntakeOverrideAuditDetails(BaseModel):
    schema_version: str = "intake_override_audit_details.v1"
    generated_at: datetime
    run_id: str
    documents: list[IntakeOverrideAuditDocument] = Field(default_factory=list)
