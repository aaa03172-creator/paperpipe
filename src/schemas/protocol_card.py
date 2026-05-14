from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .chat import ChatEvidenceRef


ProtocolSourceKind = Literal["paper_derived", "internal_adaptation", "mixed"]
ProtocolValidationStatus = Literal[
    "unreviewed",
    "draft",
    "reviewed",
    "verified_by_user",
    "deprecated",
]
ProtocolVersionStatus = Literal["draft", "active", "deprecated"]


class ProtocolVersion(BaseModel):
    version_id: str = Field(..., pattern=r"^protver_[A-Za-z0-9._-]+$")
    protocol_id: str = Field(..., pattern=r"^protocol_[A-Za-z0-9._-]+$")
    version_number: int = Field(..., ge=1)
    key_steps_summary: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    critical_conditions: list[str] = Field(default_factory=list)
    readouts: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    content_snapshot: str = Field(..., min_length=1)
    change_reason: str | None = None
    status: ProtocolVersionStatus = "draft"
    created_by: str = Field(..., min_length=1)
    created_at: datetime
    source_refs: list[ChatEvidenceRef] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def normalize_version(self):
        self.version_id = self.version_id.strip()
        self.protocol_id = self.protocol_id.strip()
        self.key_steps_summary = _dedupe_non_empty_strings(
            self.key_steps_summary,
            field_name="key_steps_summary",
        )
        self.materials = _dedupe_non_empty_strings(self.materials, field_name="materials")
        self.equipment = _dedupe_non_empty_strings(self.equipment, field_name="equipment")
        self.critical_conditions = _dedupe_non_empty_strings(
            self.critical_conditions,
            field_name="critical_conditions",
        )
        self.readouts = _dedupe_non_empty_strings(self.readouts, field_name="readouts")
        self.cautions = _dedupe_non_empty_strings(self.cautions, field_name="cautions")
        self.content_snapshot = self.content_snapshot.strip()
        self.created_by = self.created_by.strip()
        if self.change_reason is not None:
            self.change_reason = self.change_reason.strip() or None
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ProtocolVersionSummary(BaseModel):
    version_id: str = Field(..., pattern=r"^protver_[A-Za-z0-9._-]+$")
    version_number: int = Field(..., ge=1)
    status: ProtocolVersionStatus = "draft"
    created_at: datetime
    change_reason: str | None = None
    source_ref_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize_summary(self):
        self.version_id = self.version_id.strip()
        if self.change_reason is not None:
            self.change_reason = self.change_reason.strip() or None
        return self


class ProtocolCard(BaseModel):
    protocol_id: str = Field(..., pattern=r"^protocol_[A-Za-z0-9._-]+$")
    title: str = Field(..., min_length=1)
    purpose: str | None = None
    context: str | None = None
    source_kind: ProtocolSourceKind
    linked_paper_ids: list[str] = Field(default_factory=list)
    linked_note_slugs: list[str] = Field(default_factory=list)
    current_version_id: str | None = None
    validation_status: ProtocolValidationStatus = "unreviewed"
    created_at: datetime
    updated_at: datetime
    version_summaries: list[ProtocolVersionSummary] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_card(self):
        self.protocol_id = self.protocol_id.strip()
        self.title = self.title.strip()
        if self.purpose is not None:
            self.purpose = self.purpose.strip() or None
        if self.context is not None:
            self.context = self.context.strip() or None
        self.linked_paper_ids = _dedupe_non_empty_strings(
            self.linked_paper_ids,
            field_name="linked_paper_ids",
        )
        self.linked_note_slugs = _dedupe_non_empty_strings(
            self.linked_note_slugs,
            field_name="linked_note_slugs",
        )
        if self.current_version_id is not None:
            self.current_version_id = self.current_version_id.strip() or None

        seen_ids: set[str] = set()
        seen_numbers: set[int] = set()
        for summary in self.version_summaries:
            if summary.version_id in seen_ids:
                raise ValueError(
                    f"ProtocolCard.version_summaries must not contain duplicate version_id values: {summary.version_id}"
                )
            if summary.version_number in seen_numbers:
                raise ValueError(
                    "ProtocolCard.version_summaries must not contain duplicate version_number values"
                )
            seen_ids.add(summary.version_id)
            seen_numbers.add(summary.version_number)
        if self.current_version_id is not None and self.current_version_id not in seen_ids:
            raise ValueError("ProtocolCard.current_version_id must reference a version in version_summaries")
        return self


class ProtocolCardSummary(BaseModel):
    protocol_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    source_kind: ProtocolSourceKind
    validation_status: ProtocolValidationStatus
    updated_at: datetime
    version_count: int = Field(default=0, ge=0)
    current_version_id: str | None = None
    linked_paper_count: int = Field(default=0, ge=0)
    linked_note_count: int = Field(default=0, ge=0)


class ProtocolVersionRequest(BaseModel):
    version_id: str | None = None
    version_number: int = Field(..., ge=1)
    key_steps_summary: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    critical_conditions: list[str] = Field(default_factory=list)
    readouts: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    content_snapshot: str = Field(..., min_length=1)
    change_reason: str | None = None
    status: ProtocolVersionStatus = "draft"
    created_by: str = Field(..., min_length=1)
    created_at: datetime | None = None
    source_refs: list[ChatEvidenceRef] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def normalize_version_request(self):
        if self.version_id is not None:
            self.version_id = self.version_id.strip() or None
        self.key_steps_summary = _dedupe_non_empty_strings(
            self.key_steps_summary,
            field_name="key_steps_summary",
        )
        self.materials = _dedupe_non_empty_strings(self.materials, field_name="materials")
        self.equipment = _dedupe_non_empty_strings(self.equipment, field_name="equipment")
        self.critical_conditions = _dedupe_non_empty_strings(
            self.critical_conditions,
            field_name="critical_conditions",
        )
        self.readouts = _dedupe_non_empty_strings(self.readouts, field_name="readouts")
        self.cautions = _dedupe_non_empty_strings(self.cautions, field_name="cautions")
        self.content_snapshot = self.content_snapshot.strip()
        self.created_by = self.created_by.strip()
        if self.change_reason is not None:
            self.change_reason = self.change_reason.strip() or None
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ProtocolCardRequest(BaseModel):
    protocol_id: str | None = None
    title: str = Field(..., min_length=1)
    purpose: str | None = None
    context: str | None = None
    source_kind: ProtocolSourceKind
    linked_paper_ids: list[str] = Field(default_factory=list)
    linked_note_slugs: list[str] = Field(default_factory=list)
    current_version_id: str | None = None
    validation_status: ProtocolValidationStatus = "unreviewed"
    versions: list[ProtocolVersionRequest] = Field(default_factory=list, min_length=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        if self.protocol_id is not None:
            self.protocol_id = self.protocol_id.strip() or None
        self.title = self.title.strip()
        if self.purpose is not None:
            self.purpose = self.purpose.strip() or None
        if self.context is not None:
            self.context = self.context.strip() or None
        self.linked_paper_ids = _dedupe_non_empty_strings(
            self.linked_paper_ids,
            field_name="linked_paper_ids",
        )
        self.linked_note_slugs = _dedupe_non_empty_strings(
            self.linked_note_slugs,
            field_name="linked_note_slugs",
        )
        if self.current_version_id is not None:
            self.current_version_id = self.current_version_id.strip() or None
        return self


class ProtocolCardDraftRequest(BaseModel):
    note_slug: str = Field(..., min_length=1)
    paper_id: str | None = None
    run_id: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.note_slug = self.note_slug.strip()
        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.run_id is not None:
            self.run_id = self.run_id.strip() or None
        return self


class ProtocolDraftWarning(BaseModel):
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_warning(self):
        self.code = self.code.strip()
        self.message = self.message.strip()
        return self


class ProtocolDraftSourceSummary(BaseModel):
    note_slug: str = Field(..., min_length=1)
    paper_id: str | None = None
    note_path: str | None = None
    structured_state_path: str | None = None
    run_id: str | None = None
    claim_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    used_note_body: bool = False
    used_structured_state: bool = False
    used_claimset: bool = False

    @model_validator(mode="after")
    def normalize_summary(self):
        self.note_slug = self.note_slug.strip()
        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.note_path is not None:
            self.note_path = self.note_path.strip() or None
        if self.structured_state_path is not None:
            self.structured_state_path = self.structured_state_path.strip() or None
        if self.run_id is not None:
            self.run_id = self.run_id.strip() or None
        return self


class ProtocolCardDraftResponse(BaseModel):
    draft: ProtocolCardRequest
    source_summary: ProtocolDraftSourceSummary
    warnings: list[ProtocolDraftWarning] = Field(default_factory=list)


class ProtocolCardResponse(BaseModel):
    protocol_card: ProtocolCard
    versions: list[ProtocolVersion] = Field(default_factory=list)
    markdown: str


class ProtocolCardListResponse(BaseModel):
    items: list[ProtocolCardSummary] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class ProtocolVersionListResponse(BaseModel):
    items: list[ProtocolVersion] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


def summarize_protocol_card(protocol_card: ProtocolCard) -> ProtocolCardSummary:
    return ProtocolCardSummary(
        protocol_id=protocol_card.protocol_id,
        title=protocol_card.title,
        source_kind=protocol_card.source_kind,
        validation_status=protocol_card.validation_status,
        updated_at=protocol_card.updated_at,
        version_count=len(protocol_card.version_summaries),
        current_version_id=protocol_card.current_version_id,
        linked_paper_count=len(protocol_card.linked_paper_ids),
        linked_note_count=len(protocol_card.linked_note_slugs),
    )


def build_protocol_version_summary(protocol_version: ProtocolVersion) -> ProtocolVersionSummary:
    return ProtocolVersionSummary(
        version_id=protocol_version.version_id,
        version_number=protocol_version.version_number,
        status=protocol_version.status,
        created_at=protocol_version.created_at,
        change_reason=protocol_version.change_reason,
        source_ref_count=len(protocol_version.source_refs),
    )


def _dedupe_non_empty_strings(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            raise ValueError(f"{field_name} entries must be non-empty")
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized
