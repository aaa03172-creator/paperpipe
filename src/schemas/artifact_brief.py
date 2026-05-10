from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.output_modes import OutputModeFamily


ArtifactContextRole = Literal["canonical", "context_only"]
ArtifactLayer = Literal[
    "raw_source",
    "raw_memory",
    "compiled_knowledge",
    "canonical_structured_state",
    "review_gate_artifact",
    "user_facing_artifact",
]
ArtifactPlanItemKind = Literal[
    "overview",
    "chart",
    "key_point",
    "slide",
    "speaker_note",
    "discussion_question",
    "expected_question",
    "next_step",
]
ArtifactSupportStatus = Literal["direct", "context_only", "background_only"]
ArtifactPlanReviewStatus = Literal["pass", "warn"]


class ArtifactSourceContextItem(BaseModel):
    source_item_id: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    ref: str = Field(..., min_length=1)
    title: str | None = None
    role: ArtifactContextRole
    layer: ArtifactLayer
    note: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self):
        self.source_item_id = self.source_item_id.strip()
        self.source_type = self.source_type.strip()
        self.ref = self.ref.strip()
        if self.title is not None:
            self.title = self.title.strip() or None
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ArtifactTraceSummary(BaseModel):
    selector_count: int = Field(default=0, ge=0)
    retrieval_trace_entry_count: int = Field(default=0, ge=0)
    source_path_count: int = Field(default=0, ge=0)
    matched_paper_count: int = Field(default=0, ge=0)


class SourceContextManifest(BaseModel):
    source_items: list[ArtifactSourceContextItem] = Field(default_factory=list)
    allowed_evidence_refs: list[str] = Field(default_factory=list)
    trace_summary: ArtifactTraceSummary = Field(default_factory=ArtifactTraceSummary)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_lists(self):
        self.allowed_evidence_refs = _dedupe_non_empty_strings(self.allowed_evidence_refs)
        self.warnings = _dedupe_non_empty_strings(self.warnings)
        return self


class ArtifactCommunicativeIntent(BaseModel):
    artifact_family: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    audience: str = Field(..., min_length=1)
    output_mode_family: OutputModeFamily | None = None
    mode: str | None = None
    constraints: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_not_infer: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.artifact_family = self.artifact_family.strip()
        self.goal = self.goal.strip()
        self.audience = self.audience.strip()
        if self.mode is not None:
            self.mode = self.mode.strip() or None
        self.constraints = _dedupe_non_empty_strings(self.constraints)
        self.must_include = _dedupe_non_empty_strings(self.must_include)
        self.must_not_infer = _dedupe_non_empty_strings(self.must_not_infer)
        return self


class ArtifactPlanItem(BaseModel):
    item_id: str = Field(..., min_length=1)
    kind: ArtifactPlanItemKind
    label: str = Field(..., min_length=1)
    support_status: ArtifactSupportStatus = "background_only"
    requires_evidence: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    source_item_ids: list[str] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self):
        self.item_id = self.item_id.strip()
        self.label = self.label.strip()
        self.evidence_refs = _dedupe_non_empty_strings(self.evidence_refs)
        self.source_item_ids = _dedupe_non_empty_strings(self.source_item_ids)
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ArtifactPlan(BaseModel):
    artifact_family: str = Field(..., min_length=1)
    items: list[ArtifactPlanItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_family(self):
        self.artifact_family = self.artifact_family.strip()
        return self


class ArtifactPlanReview(BaseModel):
    overall_status: ArtifactPlanReviewStatus = "pass"
    warnings: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    direct_supported_item_count: int = Field(default=0, ge=0)
    evidence_required_item_count: int = Field(default=0, ge=0)
    missing_direct_support_item_ids: list[str] = Field(default_factory=list)
    context_only_source_item_ids: list[str] = Field(default_factory=list)
    context_only_item_ids: list[str] = Field(default_factory=list)
    background_only_item_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_lists(self):
        self.warnings = _dedupe_non_empty_strings(self.warnings)
        self.reason_codes = _dedupe_non_empty_strings(self.reason_codes)
        self.missing_direct_support_item_ids = _dedupe_non_empty_strings(self.missing_direct_support_item_ids)
        self.context_only_source_item_ids = _dedupe_non_empty_strings(self.context_only_source_item_ids)
        self.context_only_item_ids = _dedupe_non_empty_strings(self.context_only_item_ids)
        self.background_only_item_ids = _dedupe_non_empty_strings(self.background_only_item_ids)
        return self


class ArtifactBrief(BaseModel):
    schema_version: str = "artifact_brief.v1"
    artifact_family: str = Field(..., min_length=1)
    source_context: SourceContextManifest
    communicative_intent: ArtifactCommunicativeIntent
    plan: ArtifactPlan

    @model_validator(mode="after")
    def normalize_family(self):
        self.artifact_family = self.artifact_family.strip()
        return self


def _dedupe_non_empty_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
