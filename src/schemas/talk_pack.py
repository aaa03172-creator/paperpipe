from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.chat import ChatEvidenceRef


TalkPackMode = Literal[
    "journal_club",
    "lab_meeting",
    "seminar",
    "grand_rounds",
    "coursework_presentation",
]
TalkPackStyleProfile = Literal["paperpipe_baseline", "paperpipe_editorial"]
TalkPackStatus = Literal["draft"]
TalkPackArtifactFamily = Literal["talk_pack"]
TalkPackCanonicalStatus = Literal["non_canonical"]
TalkPackLayer = Literal["user_facing_artifact"]
TalkPackOutputKind = Literal[
    "slide_manifest",
    "key_numbers",
    "speaker_script",
    "qa_pack",
    "quick_review",
    "deck_pptx",
]
TalkPackOutputStatus = Literal["generated", "skipped", "blocked"]
TalkPackReviewArtifactKind = Literal["presentation_review", "style_lint"]
TalkPackReviewArtifactRole = Literal["review_only"]
TalkPackOwnerKind = Literal[
    "paper_state",
    "run_artifact",
    "derived_manifest",
    "review_gate_artifact",
    "context_artifact",
]
TalkPackSlideKind = Literal["main", "backup"]
TalkPackSpeakerPriority = Literal["must_say", "nice_to_say", "skip_if_short_on_time"]
TalkPackVisualLayout = Literal["pair_equal", "primary_supporting", "main_plus_inset"]


class TalkPackSupportingArtifactRef(BaseModel):
    artifact_family: str = Field(..., min_length=1)
    ref: str = Field(..., min_length=1)
    role: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.artifact_family = self.artifact_family.strip()
        self.ref = self.ref.strip()
        if self.role is not None:
            self.role = self.role.strip() or None
        return self


class TalkPackRequestSnapshot(BaseModel):
    paper_slug: str = Field(..., min_length=1)
    title: str | None = None
    talk_mode: TalkPackMode
    audience_profile: str = Field(..., min_length=1)
    duration_minutes: int = Field(..., ge=1, le=180)
    context: str | None = None
    selected_exports: list[TalkPackOutputKind] = Field(default_factory=list, min_length=1)
    optional_extensions: list[str] = Field(default_factory=list)
    supporting_artifact_refs: list[TalkPackSupportingArtifactRef] = Field(default_factory=list)
    style_profile: TalkPackStyleProfile = "paperpipe_baseline"
    template_attachment_refs: list[str] = Field(default_factory=list)
    max_slides: int | None = Field(default=None, ge=1, le=100)
    auto_include_dependencies: bool = True

    @model_validator(mode="after")
    def normalize_values(self):
        self.paper_slug = self.paper_slug.strip()
        self.audience_profile = self.audience_profile.strip()
        if self.title is not None:
            self.title = self.title.strip() or None
        if self.context is not None:
            self.context = self.context.strip() or None
        self.selected_exports = _dedupe_output_kinds(self.selected_exports)
        self.optional_extensions = _dedupe_non_empty_strings(
            self.optional_extensions,
            field_name="optional_extensions",
        )
        self.supporting_artifact_refs = _dedupe_supporting_refs(self.supporting_artifact_refs)
        self.template_attachment_refs = _dedupe_non_empty_strings(
            self.template_attachment_refs,
            field_name="template_attachment_refs",
        )
        return self


class TalkPackUpstreamOwnerRef(BaseModel):
    owner_kind: TalkPackOwnerKind
    ref: str = Field(..., min_length=1)
    role: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.ref = self.ref.strip()
        if self.role is not None:
            self.role = self.role.strip() or None
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class TalkPackOutputMember(BaseModel):
    kind: TalkPackOutputKind
    path: str = Field(..., min_length=1)
    required: bool = False
    status: TalkPackOutputStatus = "generated"

    @model_validator(mode="after")
    def normalize_values(self):
        self.path = _normalize_artifact_member_path(
            self.path,
            field_name="TalkPackOutputMember.path",
        )
        return self


class TalkPackReviewArtifact(BaseModel):
    kind: TalkPackReviewArtifactKind
    path: str = Field(..., min_length=1)
    role: TalkPackReviewArtifactRole = "review_only"

    @model_validator(mode="after")
    def normalize_values(self):
        self.path = _normalize_artifact_member_path(
            self.path,
            field_name="TalkPackReviewArtifact.path",
        )
        return self


class TalkPackSlideManifestSlide(BaseModel):
    slide_id: str = Field(..., min_length=1)
    order: int = Field(..., ge=1)
    slide_kind: TalkPackSlideKind = "main"
    section: str | None = None
    title: str = Field(..., min_length=1)
    primary_message: str = Field(..., min_length=1)
    speaker_priority: TalkPackSpeakerPriority | None = None
    time_budget_seconds: int | None = Field(default=None, ge=1, le=3600)
    claim_refs: list[str] = Field(default_factory=list)
    key_number_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[ChatEvidenceRef] = Field(default_factory=list)
    source_artifact_refs: list[str] = Field(default_factory=list)
    visual_refs: list[str] = Field(default_factory=list)
    visual_layout: TalkPackVisualLayout | None = None
    visual_labels: list[str] = Field(default_factory=list)
    notes_focus: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_values(self):
        self.slide_id = self.slide_id.strip()
        if self.section is not None:
            self.section = self.section.strip() or None
        self.title = self.title.strip()
        self.primary_message = self.primary_message.strip()
        self.claim_refs = _dedupe_non_empty_strings(self.claim_refs, field_name="claim_refs")
        self.key_number_refs = _dedupe_non_empty_strings(
            self.key_number_refs,
            field_name="key_number_refs",
        )
        self.source_artifact_refs = _dedupe_non_empty_strings(
            self.source_artifact_refs,
            field_name="source_artifact_refs",
        )
        self.visual_refs = _dedupe_non_empty_strings(self.visual_refs, field_name="visual_refs")
        self.visual_labels = _normalize_non_empty_strings_preserve_order(
            self.visual_labels,
            field_name="visual_labels",
        )
        if len(self.visual_labels) > len(self.visual_refs):
            raise ValueError("visual_labels must not outnumber visual_refs for a slide")
        self.notes_focus = _dedupe_non_empty_strings(self.notes_focus, field_name="notes_focus")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings")
        return self


class TalkPackSlideManifest(BaseModel):
    schema_version: str | None = None
    workflow: str | None = None
    talk_pack_id: str = Field(..., min_length=1)
    paper_slug: str = Field(..., min_length=1)
    generated_at: datetime | None = None
    talk_mode: TalkPackMode | None = None
    audience_profile: str | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=180)
    max_slides: int | None = Field(default=None, ge=1, le=100)
    style_profile: TalkPackStyleProfile | None = None
    template_attachment_refs: list[str] = Field(default_factory=list)
    slides: list[TalkPackSlideManifestSlide] = Field(default_factory=list, min_length=1)

    @model_validator(mode="after")
    def normalize_values(self):
        self.talk_pack_id = self.talk_pack_id.strip()
        self.paper_slug = self.paper_slug.strip()
        if self.schema_version is not None:
            self.schema_version = self.schema_version.strip() or None
        if self.workflow is not None:
            self.workflow = self.workflow.strip() or None
        if self.audience_profile is not None:
            self.audience_profile = self.audience_profile.strip() or None
        self.template_attachment_refs = _dedupe_non_empty_strings(
            self.template_attachment_refs,
            field_name="template_attachment_refs",
        )
        seen_slide_ids: set[str] = set()
        seen_orders: set[int] = set()
        for slide in self.slides:
            if slide.slide_id in seen_slide_ids:
                raise ValueError(
                    "TalkPackSlideManifest.slides must not contain duplicate slide_id values: "
                    f"{slide.slide_id}"
                )
            if slide.order in seen_orders:
                raise ValueError(
                    "TalkPackSlideManifest.slides must not contain duplicate order values: "
                    f"{slide.order}"
                )
            seen_slide_ids.add(slide.slide_id)
            seen_orders.add(slide.order)
        return self


class TalkPack(BaseModel):
    talk_pack_id: str = Field(..., pattern=r"^talkpack_[A-Za-z0-9._-]+$")
    paper_slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    created_at: datetime
    updated_at: datetime
    artifact_family: TalkPackArtifactFamily = "talk_pack"
    layer: TalkPackLayer = "user_facing_artifact"
    canonical_status: TalkPackCanonicalStatus = "non_canonical"
    status: TalkPackStatus = "draft"
    talk_mode: TalkPackMode
    audience_profile: str = Field(..., min_length=1)
    duration_minutes: int = Field(..., ge=1, le=180)
    style_profile: TalkPackStyleProfile = "paperpipe_baseline"
    template_attachment_refs: list[str] = Field(default_factory=list)
    generation_request: TalkPackRequestSnapshot
    regenerated_from_talk_pack_id: str | None = None
    upstream_owners: list[TalkPackUpstreamOwnerRef] = Field(default_factory=list, min_length=1)
    selected_outputs: list[TalkPackOutputKind] = Field(default_factory=list, min_length=1)
    required_outputs: list[TalkPackOutputKind] = Field(default_factory=list, min_length=1)
    output_members: list[TalkPackOutputMember] = Field(default_factory=list)
    review_artifacts: list[TalkPackReviewArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_values(self):
        self.paper_slug = self.paper_slug.strip()
        self.title = self.title.strip()
        self.audience_profile = self.audience_profile.strip()
        self.template_attachment_refs = _dedupe_non_empty_strings(
            self.template_attachment_refs,
            field_name="template_attachment_refs",
        )
        if self.regenerated_from_talk_pack_id is not None:
            self.regenerated_from_talk_pack_id = self.regenerated_from_talk_pack_id.strip() or None
        self.selected_outputs = _dedupe_output_kinds(self.selected_outputs)
        self.required_outputs = _dedupe_output_kinds(self.required_outputs)
        self.upstream_owners = _dedupe_owner_refs(self.upstream_owners)
        self.output_members = _dedupe_output_members(self.output_members)
        self.review_artifacts = _dedupe_review_artifacts(self.review_artifacts)
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings")
        self.uncertainty_notes = _dedupe_non_empty_strings(
            self.uncertainty_notes,
            field_name="uncertainty_notes",
        )
        request_field_pairs = [
            ("paper_slug", self.paper_slug, self.generation_request.paper_slug),
            ("talk_mode", self.talk_mode, self.generation_request.talk_mode),
            (
                "audience_profile",
                self.audience_profile,
                self.generation_request.audience_profile,
            ),
            (
                "duration_minutes",
                self.duration_minutes,
                self.generation_request.duration_minutes,
            ),
            ("style_profile", self.style_profile, self.generation_request.style_profile),
        ]
        mismatched_request_fields = [
            field_name
            for field_name, owner_value, request_value in request_field_pairs
            if owner_value != request_value
        ]
        if self.selected_outputs != self.generation_request.selected_exports:
            mismatched_request_fields.append("selected_outputs")
        if self.template_attachment_refs != self.generation_request.template_attachment_refs:
            mismatched_request_fields.append("template_attachment_refs")
        if mismatched_request_fields:
            raise ValueError(
                "TalkPack must preserve the saved generation_request intent for: "
                + ", ".join(mismatched_request_fields)
            )
        missing_required = [kind for kind in self.selected_outputs if kind not in self.required_outputs]
        if missing_required:
            raise ValueError(
                "TalkPack.required_outputs must include all selected_outputs: "
                + ", ".join(missing_required)
            )
        output_member_kinds = [member.kind for member in self.output_members]
        missing_output_members = [
            kind for kind in self.required_outputs if kind not in output_member_kinds
        ]
        if missing_output_members:
            raise ValueError(
                "TalkPack.output_members must include every required_output with explicit status: "
                + ", ".join(missing_output_members)
            )
        unexpected_output_members = [
            kind for kind in output_member_kinds if kind not in self.required_outputs
        ]
        if unexpected_output_members:
            raise ValueError(
                "TalkPack.output_members must not include kinds outside required_outputs: "
                + ", ".join(unexpected_output_members)
            )
        return self


class TalkPackGenerateRequest(TalkPackRequestSnapshot):
    pass


class TalkPackResponse(BaseModel):
    pack: TalkPack


class TalkPackListItem(BaseModel):
    talk_pack_id: str = Field(..., min_length=1)
    paper_slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    updated_at: datetime
    artifact_family: TalkPackArtifactFamily = "talk_pack"
    canonical_status: TalkPackCanonicalStatus = "non_canonical"
    talk_mode: TalkPackMode
    selected_output_count: int = Field(default=0, ge=0)
    generated_output_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    has_generation_request: bool = True
    regenerated_from_talk_pack_id: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.talk_pack_id = self.talk_pack_id.strip()
        self.paper_slug = self.paper_slug.strip()
        self.title = self.title.strip()
        if self.regenerated_from_talk_pack_id is not None:
            self.regenerated_from_talk_pack_id = self.regenerated_from_talk_pack_id.strip() or None
        return self


class TalkPackListResponse(BaseModel):
    items: list[TalkPackListItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


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


def _normalize_non_empty_strings_preserve_order(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            raise ValueError(f"{field_name} entries must be non-empty")
        normalized.append(text)
    return normalized


def _normalize_artifact_member_path(path: str, *, field_name: str) -> str:
    raw = str(path or "").strip()
    pure = PurePosixPath(raw)
    if (
        not raw
        or "\\" in raw
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in raw.split("/"))
    ):
        raise ValueError(f"{field_name} is invalid: {path}")
    return pure.as_posix()


def _dedupe_output_kinds(values: list[TalkPackOutputKind]) -> list[TalkPackOutputKind]:
    normalized: list[TalkPackOutputKind] = []
    seen: set[str] = set()
    for item in values:
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def _dedupe_supporting_refs(values: list[TalkPackSupportingArtifactRef]) -> list[TalkPackSupportingArtifactRef]:
    normalized: list[TalkPackSupportingArtifactRef] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in values:
        key = (item.artifact_family, item.ref, item.role)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _dedupe_owner_refs(values: list[TalkPackUpstreamOwnerRef]) -> list[TalkPackUpstreamOwnerRef]:
    normalized: list[TalkPackUpstreamOwnerRef] = []
    seen: set[tuple[str, str, str | None, str | None]] = set()
    for item in values:
        key = (item.owner_kind, item.ref, item.role, item.note)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _dedupe_output_members(values: list[TalkPackOutputMember]) -> list[TalkPackOutputMember]:
    normalized: list[TalkPackOutputMember] = []
    seen: set[str] = set()
    for item in values:
        if item.kind in seen:
            raise ValueError(f"TalkPack.output_members must not contain duplicate kind values: {item.kind}")
        seen.add(item.kind)
        normalized.append(item)
    return normalized


def _dedupe_review_artifacts(values: list[TalkPackReviewArtifact]) -> list[TalkPackReviewArtifact]:
    normalized: list[TalkPackReviewArtifact] = []
    seen: set[str] = set()
    for item in values:
        if item.kind in seen:
            raise ValueError(
                f"TalkPack.review_artifacts must not contain duplicate kind values: {item.kind}"
            )
        seen.add(item.kind)
        normalized.append(item)
    return normalized
