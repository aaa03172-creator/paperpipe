from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


PRIVACY_PREFLIGHT_SCHEMA_VERSION = "privacy_preflight.v1"
PRIVACY_PREFLIGHT_ROLLBACK_FLAG = "LATTICE_PRIVACY_PREFLIGHT_MODE"

PrivacyPreflightMode = Literal["off", "report_only", "block_on_review"]
PrivacyPreflightStatus = Literal["disabled", "pass", "review_required", "blocked"]
PrivacyPreflightSeverity = Literal["info", "low", "medium", "high", "critical"]
PrivacyPreflightAction = Literal["none", "preserve", "redact", "manual_review", "block"]
PrivacyPreflightPayloadClass = Literal["local_only", "lab_allowed", "external_allowed"]
PrivacyPreflightFindingKind = Literal[
    "detector_span",
    "deterministic_span",
    "preserve_conflict",
    "false_negative_risk",
    "manual_review",
    "unexpected_prediction",
    "policy_note",
]


class PrivacyPreflightRuntimeConfig(BaseModel):
    schema_version: str = PRIVACY_PREFLIGHT_SCHEMA_VERSION
    mode: PrivacyPreflightMode = "off"
    rollback_flag: str = PRIVACY_PREFLIGHT_ROLLBACK_FLAG
    default_status_when_off: Literal["disabled"] = "disabled"
    mutation_allowed: bool = False


class PrivacyPreflightFinding(BaseModel):
    finding_id: str
    kind: PrivacyPreflightFindingKind
    severity: PrivacyPreflightSeverity
    action: PrivacyPreflightAction
    message: str
    label: str | None = None
    source_surface: str | None = None
    detector: str | None = None
    reason: str | None = None
    text_preview: str | None = None
    start: int | None = None
    end: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PrivacyPreflightManualReviewItem(BaseModel):
    review_id: str
    severity: PrivacyPreflightSeverity
    reason: str
    message: str
    source_surface: str | None = None
    finding_ids: list[str] = Field(default_factory=list)
    recommended_action: PrivacyPreflightAction = "manual_review"


class PrivacyPreflightSummary(BaseModel):
    detector_spans: int = 0
    deterministic_spans: int = 0
    preserve_conflicts: int = 0
    false_negative_risks: int = 0
    unexpected_predictions: int = 0
    manual_review_records: int = 0
    manual_review_reasons: int = 0


class PrivacyPreflightResponse(BaseModel):
    schema_version: str = PRIVACY_PREFLIGHT_SCHEMA_VERSION
    mode: PrivacyPreflightMode = "off"
    status: PrivacyPreflightStatus = "disabled"
    rollback_flag: str = PRIVACY_PREFLIGHT_ROLLBACK_FLAG
    payload_class: PrivacyPreflightPayloadClass = "local_only"
    scope: str = "external_inference_payload"
    redaction_applied: bool = False
    mutation_applied: bool = False
    findings: list[PrivacyPreflightFinding] = Field(default_factory=list)
    manual_review: list[PrivacyPreflightManualReviewItem] = Field(default_factory=list)
    summary: PrivacyPreflightSummary = Field(default_factory=PrivacyPreflightSummary)
    input_refs: list[str] = Field(default_factory=list)
    source_surfaces: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
