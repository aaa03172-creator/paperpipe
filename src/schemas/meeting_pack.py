from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.output_modes import OutputModeFamily, resolve_meeting_pack_output_mode_family
from .cloud_paper import CloudPaperPayloadClass
from .artifact_brief import ArtifactBrief, ArtifactPlanReview
from .chat import ChatLocator


MeetingPackMode = Literal[
    "journal_club",
    "literature_update",
    "project_progress_update",
    "experiment_proposal",
]
MeetingPackStatus = Literal["draft"]
MeetingPackReadiness = Literal["evidence_backed", "background_only"]
MeetingPackMarkdownSyncState = Literal["in_sync", "drifted"]
MeetingPackRegenerateStrategy = Literal["saved_request", "legacy_source_items", "unavailable"]
MeetingPackSourceType = Literal[
    "paper_slug",
    "paper_state",
    "paper_note",
    "project_note",
    "research_note",
    "screening_decision",
    "project_profile",
    "research_profile",
    "topic",
]
MeetingPackSupportType = Literal["direct", "summary", "background", "conflict"]
MeetingPackPriority = Literal["low", "medium", "high"]
MeetingPackConflictType = Literal["possible_divergence", "selection_scope"]
MeetingPackConsensusType = Literal[
    "directional_alignment",
    "majority_directional_alignment",
    "cross_focus_pattern",
    "cross_focus_majority_pattern",
]
MeetingPackRetrievalOutcome = Literal["selected", "deduped", "resolved", "loaded"]
MeetingPackCloudDerivedKind = Literal["ocr_text", "table", "figure", "figure_analysis"]


class MeetingPackSourceSelector(BaseModel):
    type: MeetingPackSourceType
    ref: str = Field(..., min_length=1)


class MeetingPackSourceItem(BaseModel):
    id: str = Field(..., min_length=1)
    type: MeetingPackSourceType
    ref: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1)
    included: bool = True


class MeetingPackRetrievalTraceEntry(BaseModel):
    order: int = Field(..., ge=1)
    selector_type: MeetingPackSourceType
    selector_ref: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    outcome: MeetingPackRetrievalOutcome
    detail: str = Field(..., min_length=1)
    source_item_id: str | None = None
    source_path: str | None = None
    matched_paper_slugs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MeetingPackEvidenceRef(BaseModel):
    id: str = Field(..., min_length=1)
    paper_slug: str
    claim_id: str | None = None
    evidence_id: str | None = None
    run_id: str | None = None
    locator: ChatLocator | None = None
    support_type: MeetingPackSupportType = "direct"
    note: str | None = None


class MeetingPackReviewArtifact(BaseModel):
    kind: Literal["visual_evidence_ledger"]
    paper_slug: str = Field(..., min_length=1)
    run_id: str | None = None
    path: str | None = None
    entry_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    partially_observed_count: int = Field(default=0, ge=0)
    replay_required: bool = True
    note: str | None = None


class MeetingPackCloudDerivedContextItem(BaseModel):
    context_id: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    kind: MeetingPackCloudDerivedKind
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    text: str | None = None
    source_page: int = Field(..., ge=1)
    source_block_id: str | None = None
    source_pdf_sha256: str = Field(..., min_length=64, max_length=64)
    payload_class: CloudPaperPayloadClass = "local_only"
    support_type: Literal["background"] = "background"
    canonical_status: Literal["derived_noncanonical"] = "derived_noncanonical"
    confidence: float | None = Field(default=None, ge=0, le=1)
    image_route: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_context_item(self):
        self.context_id = self.context_id.strip()
        self.candidate_id = self.candidate_id.strip()
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.title = self.title.strip()
        self.text = self.text.strip() or None if self.text is not None else None
        self.source_block_id = self.source_block_id.strip() or None if self.source_block_id is not None else None
        self.source_pdf_sha256 = self.source_pdf_sha256.strip().lower()
        self.image_route = self.image_route.strip() or None if self.image_route is not None else None
        if self.image_route is not None and not self.image_route.startswith("/api/cloud/papers/"):
            raise ValueError("image_route must be a same-origin cloud paper API route")
        if self.evidence_refs:
            raise ValueError("cloud-derived Meeting Pack context must not carry evidence refs")
        return self


class MeetingPackCloudDerivedContext(BaseModel):
    schema_version: Literal["meeting_pack_cloud_derived_context.v1"] = "meeting_pack_cloud_derived_context.v1"
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    source_pdf_sha256: str = Field(..., min_length=64, max_length=64)
    readiness: Literal["background_only"] = "background_only"
    payload_class: CloudPaperPayloadClass = "local_only"
    items: list[MeetingPackCloudDerivedContextItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_context(self):
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.source_pdf_sha256 = self.source_pdf_sha256.strip().lower()
        for item in self.items:
            if item.paper_id != self.paper_id:
                raise ValueError("item.paper_id must match context paper_id")
            if item.run_id != self.run_id:
                raise ValueError("item.run_id must match context run_id")
            if item.source_pdf_sha256 != self.source_pdf_sha256:
                raise ValueError("item source checksum must match context source_pdf_sha256")
        return self


class MeetingPackKeyPoint(BaseModel):
    label: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    uncertainty_note: str | None = None


class MeetingPackConflict(BaseModel):
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    conflict_type: MeetingPackConflictType = "possible_divergence"
    source_item_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class MeetingPackConsensus(BaseModel):
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    consensus_type: MeetingPackConsensusType = "directional_alignment"
    source_item_ids: list[str] = Field(default_factory=list)
    outlier_source_item_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class MeetingPackOnePageSummary(BaseModel):
    overview: str = ""
    key_points: list[MeetingPackKeyPoint] = Field(default_factory=list)
    consensus_points: list[MeetingPackConsensus] = Field(default_factory=list)
    conflicts: list[MeetingPackConflict] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class MeetingPackFigureCandidate(BaseModel):
    label: str = Field(..., min_length=1)
    source_item_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class MeetingPackSlide(BaseModel):
    slide_title: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    bullets: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    optional_figure_candidates: list[MeetingPackFigureCandidate] = Field(default_factory=list)
    caution_notes: list[str] = Field(default_factory=list)


class MeetingPackSpeakerNote(BaseModel):
    slide_index: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class MeetingPackQuestion(BaseModel):
    question: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class MeetingPackExpectedQuestion(BaseModel):
    question: str = Field(..., min_length=1)
    suggested_response: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class MeetingPackNextStep(BaseModel):
    action: str = Field(..., min_length=1)
    why: str = Field(..., min_length=1)
    priority: MeetingPackPriority = "medium"
    evidence_refs: list[str] = Field(default_factory=list)


class MeetingPackRequestSnapshot(BaseModel):
    mode: MeetingPackMode
    title: str | None = None
    source_items: list[MeetingPackSourceSelector] = Field(default_factory=list, min_length=1)
    max_slides: int = Field(default=6, ge=5, le=8)


class MeetingPackMarkdownSync(BaseModel):
    status: MeetingPackMarkdownSyncState = "in_sync"
    stored_markdown_sha1: str = Field(..., min_length=1)
    rendered_markdown_sha1: str = Field(..., min_length=1)
    note: str | None = None


class MeetingPackValidation(BaseModel):
    pack_id: str = Field(..., min_length=1)
    readiness: MeetingPackReadiness
    markdown_sync: MeetingPackMarkdownSync
    can_regenerate: bool = False
    regenerate_strategy: MeetingPackRegenerateStrategy = "unavailable"
    warnings: list[str] = Field(default_factory=list)


class MeetingPackListItem(BaseModel):
    pack_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    mode: MeetingPackMode
    output_mode_family: OutputModeFamily | None = None
    created_at: datetime
    readiness: MeetingPackReadiness
    source_count: int = Field(default=0, ge=0)
    slide_count: int = Field(default=0, ge=0)
    trace_entry_count: int = Field(default=0, ge=0)
    primary_source_title: str | None = None
    has_generation_request: bool = False
    regenerated_from_pack_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_output_mode_family(cls, value: Any) -> Any:
        if isinstance(value, dict):
            payload = dict(value)
            payload["output_mode_family"] = resolve_meeting_pack_output_mode_family(
                payload["mode"],
                explicit_family=payload.get("output_mode_family"),
            )
            return payload
        return value


class MeetingPackRetrievalTraceSummary(BaseModel):
    entry_count: int = Field(default=0, ge=0)
    selector_count: int = Field(default=0, ge=0)
    matched_paper_count: int = Field(default=0, ge=0)
    source_path_count: int = Field(default=0, ge=0)
    action_counts: dict[str, int] = Field(default_factory=dict)
    outcome_counts: dict[str, int] = Field(default_factory=dict)
    matched_paper_slugs: list[str] = Field(default_factory=list)
    source_paths: list[str] = Field(default_factory=list)


class MeetingPack(BaseModel):
    id: str = Field(..., pattern=r"^meetingpack_[A-Za-z0-9._-]+$")
    mode: MeetingPackMode
    output_mode_family: OutputModeFamily | None = None
    title: str = Field(..., min_length=1)
    created_at: datetime
    layer: Literal["user_facing_artifact"] = "user_facing_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    status: MeetingPackStatus = "draft"
    readiness: MeetingPackReadiness = "evidence_backed"
    generation_request: MeetingPackRequestSnapshot | None = None
    regenerated_from_pack_id: str | None = None
    source_items: list[MeetingPackSourceItem] = Field(default_factory=list)
    retrieval_trace: list[MeetingPackRetrievalTraceEntry] = Field(default_factory=list)
    one_page_summary: MeetingPackOnePageSummary = Field(default_factory=MeetingPackOnePageSummary)
    slides: list[MeetingPackSlide] = Field(default_factory=list)
    speaker_notes: list[MeetingPackSpeakerNote] = Field(default_factory=list)
    discussion_questions: list[MeetingPackQuestion] = Field(default_factory=list)
    expected_questions: list[MeetingPackExpectedQuestion] = Field(default_factory=list)
    next_steps: list[MeetingPackNextStep] = Field(default_factory=list)
    evidence_refs: list[MeetingPackEvidenceRef] = Field(default_factory=list)
    review_artifacts: list[MeetingPackReviewArtifact] = Field(default_factory=list)
    artifact_brief: ArtifactBrief | None = None
    artifact_brief_review: ArtifactPlanReview | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_output_mode_family(cls, value: Any) -> Any:
        if isinstance(value, dict):
            payload = dict(value)
            payload["output_mode_family"] = resolve_meeting_pack_output_mode_family(
                payload["mode"],
                explicit_family=payload.get("output_mode_family"),
            )
            return payload
        return value


class MeetingPackGenerateRequest(MeetingPackRequestSnapshot):
    pass


class MeetingPackResponse(BaseModel):
    pack: MeetingPack
    markdown: str | None = None
    markdown_sync: MeetingPackMarkdownSync | None = None


class MeetingPackValidationResponse(BaseModel):
    validation: MeetingPackValidation


class MeetingPackTraceResponse(BaseModel):
    pack_id: str = Field(..., min_length=1)
    available: bool = False
    summary: MeetingPackRetrievalTraceSummary = Field(default_factory=MeetingPackRetrievalTraceSummary)
    trace: list[MeetingPackRetrievalTraceEntry] = Field(default_factory=list)


class MeetingPackListResponse(BaseModel):
    generated_at: datetime
    total: int = Field(default=0, ge=0)
    items: list[MeetingPackListItem] = Field(default_factory=list)
