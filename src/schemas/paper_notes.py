from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from .skills import ReadingAssistBlockKind, SkillActionInfo, StructuredPaperState


class PaperNoteOpsSummary(BaseModel):
    state: Literal["healthy", "action_needed"]
    label: str
    reason: str
    recommended_action: Literal["none", "repair_stats", "open_workbench"] = "none"
    latest_run_id: str | None = None
    has_claimset: bool = False
    has_stats_report: bool = False
    stats_check_count: int = 0


PaperNoteOperatorTriageLabel = Literal[
    "revisit",
    "needs_verification",
    "experiment_relevant",
]

PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER: tuple[PaperNoteOperatorTriageLabel, ...] = (
    "revisit",
    "needs_verification",
    "experiment_relevant",
)


class PaperNoteOperatorState(BaseModel):
    note_slug: str = Field(..., min_length=1)
    paper_id: str = Field(..., min_length=1)
    layer: Literal["raw_memory"] = "raw_memory"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    paper_note_text: str | None = Field(default=None, max_length=4000)
    starred: bool = False
    triage_labels: list[PaperNoteOperatorTriageLabel] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_operator_state(self):
        self.note_slug = self.note_slug.strip()
        self.paper_id = self.paper_id.strip()
        if not self.note_slug:
            raise ValueError("PaperNoteOperatorState.note_slug must not be blank")
        if not self.paper_id:
            raise ValueError("PaperNoteOperatorState.paper_id must not be blank")
        if self.paper_note_text is not None:
            normalized_text = self.paper_note_text.strip()
            self.paper_note_text = normalized_text or None
        ordered_labels: list[PaperNoteOperatorTriageLabel] = []
        seen_labels: set[PaperNoteOperatorTriageLabel] = set()
        allowed_labels = set(PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER)
        for label in PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER:
            if label in self.triage_labels and label not in seen_labels:
                ordered_labels.append(label)
                seen_labels.add(label)
        for label in self.triage_labels:
            if label in seen_labels or label not in allowed_labels:
                continue
            ordered_labels.append(label)
            seen_labels.add(label)
        self.triage_labels = ordered_labels
        return self


class PaperNoteOperatorStateUpdateRequest(BaseModel):
    paper_note_text: str | None = Field(default=None, max_length=4000)
    starred: bool = False
    triage_labels: list[PaperNoteOperatorTriageLabel] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_update_request(self):
        if self.paper_note_text is not None:
            normalized_text = self.paper_note_text.strip()
            self.paper_note_text = normalized_text or None
        ordered_labels: list[PaperNoteOperatorTriageLabel] = []
        seen_labels: set[PaperNoteOperatorTriageLabel] = set()
        allowed_labels = set(PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER)
        for label in PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER:
            if label in self.triage_labels and label not in seen_labels:
                ordered_labels.append(label)
                seen_labels.add(label)
        for label in self.triage_labels:
            if label in seen_labels or label not in allowed_labels:
                continue
            ordered_labels.append(label)
            seen_labels.add(label)
        self.triage_labels = ordered_labels
        return self


class PaperNoteIndexItem(BaseModel):
    slug: str
    title: str
    note_path: str
    structured_state_present: bool = False
    reading_assist_available: bool = False
    reading_assist_locales: list[str] = Field(default_factory=list)
    id: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    date_processed: str | None = None
    confidence: float | None = None
    status: str | None = None
    doi: str | None = None
    zotero_link: str | None = None
    updated_at: str | None = None
    pp_signals: dict[str, Any] = Field(default_factory=dict)
    claim_tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    mesh: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    ops_summary: PaperNoteOpsSummary | None = None
    starred: bool = False
    has_operator_note: bool = False
    triage_labels: list[PaperNoteOperatorTriageLabel] = Field(default_factory=list)
    _runtime_source_metadata_loaded: bool = PrivateAttr(default=False)
    _runtime_source_url: str | None = PrivateAttr(default=None)
    _runtime_pdf_url: str | None = PrivateAttr(default=None)
    _runtime_pdf_path: str | None = PrivateAttr(default=None)
    _runtime_local_pdf_path: str | None = PrivateAttr(default=None)
    _runtime_structured_path: str | None = PrivateAttr(default=None)
    _runtime_identity_sets_loaded: bool = PrivateAttr(default=False)
    _runtime_identity_raw_variants: frozenset[str] = PrivateAttr(default_factory=frozenset)
    _runtime_identity_normalized_variants: frozenset[str] = PrivateAttr(default_factory=frozenset)
    _runtime_listing_candidate_loaded: bool = PrivateAttr(default=False)
    _runtime_listing_candidate_paper_id: str | None = PrivateAttr(default=None)
    _runtime_listing_candidate_title: str | None = PrivateAttr(default=None)
    _runtime_listing_candidate_sort_updated_at: str | None = PrivateAttr(default=None)
    _runtime_listing_candidate_is_fixture: bool = PrivateAttr(default=False)
    _runtime_fixture_preview_loaded: bool = PrivateAttr(default=False)
    _runtime_fixture_preview_is_fixture: bool = PrivateAttr(default=False)
    _runtime_ops_candidate_group_loaded: bool = PrivateAttr(default=False)
    _runtime_ops_candidate_group_key: tuple[str, ...] = PrivateAttr(default_factory=tuple)

    @staticmethod
    def _normalize_runtime_source_value(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def set_runtime_source_metadata(
        self,
        *,
        source_url: Any = None,
        pdf_url: Any = None,
        pdf_path: Any = None,
        local_pdf_path: Any = None,
        structured_path: Any = None,
    ) -> None:
        self._runtime_source_metadata_loaded = True
        self._runtime_source_url = self._normalize_runtime_source_value(source_url)
        self._runtime_pdf_url = self._normalize_runtime_source_value(pdf_url)
        self._runtime_pdf_path = self._normalize_runtime_source_value(pdf_path)
        self._runtime_local_pdf_path = self._normalize_runtime_source_value(local_pdf_path)
        self._runtime_structured_path = self._normalize_runtime_source_value(structured_path)

    def load_runtime_source_metadata(self, payload: dict[str, Any] | None) -> None:
        metadata = payload if isinstance(payload, dict) else {}
        self.set_runtime_source_metadata(
            source_url=metadata.get("source_url"),
            pdf_url=metadata.get("pdf_url"),
            pdf_path=metadata.get("pdf_path"),
            local_pdf_path=metadata.get("local_pdf_path"),
            structured_path=metadata.get("structured_path"),
        )

    def export_runtime_source_metadata(self) -> dict[str, Any]:
        return {
            "source_url": self._runtime_source_url,
            "pdf_url": self._runtime_pdf_url,
            "pdf_path": self._runtime_pdf_path,
            "local_pdf_path": self._runtime_local_pdf_path,
            "structured_path": self._runtime_structured_path,
        }

    def has_runtime_source_metadata(self) -> bool:
        return self._runtime_source_metadata_loaded

    def build_runtime_source_frontmatter(self) -> dict[str, Any]:
        frontmatter: dict[str, Any] = {}
        if self.id:
            frontmatter["id"] = self.id
        if self.doi:
            frontmatter["doi"] = self.doi
        if self._runtime_source_url:
            frontmatter["url"] = self._runtime_source_url
        if self._runtime_pdf_url:
            frontmatter["pdf_url"] = self._runtime_pdf_url
        if self._runtime_pdf_path:
            frontmatter["pdf_path"] = self._runtime_pdf_path
        if self._runtime_local_pdf_path:
            frontmatter["local_pdf_path"] = self._runtime_local_pdf_path
        if self._runtime_structured_path:
            frontmatter["pp"] = {"structured_path": self._runtime_structured_path}
        return frontmatter

    def get_runtime_identity_sets(self) -> tuple[frozenset[str], frozenset[str]] | None:
        if not self._runtime_identity_sets_loaded:
            return None
        return self._runtime_identity_raw_variants, self._runtime_identity_normalized_variants

    def set_runtime_identity_sets(
        self,
        *,
        raw_variants: Any,
        normalized_variants: Any,
    ) -> None:
        self._runtime_identity_sets_loaded = True
        self._runtime_identity_raw_variants = frozenset(
            str(value).strip() for value in raw_variants or [] if str(value).strip()
        )
        self._runtime_identity_normalized_variants = frozenset(
            str(value).strip() for value in normalized_variants or [] if str(value).strip()
        )

    def get_runtime_listing_candidate_metadata(self) -> tuple[str, str, str | None, bool] | None:
        if not self._runtime_listing_candidate_loaded:
            return None
        paper_id = str(self._runtime_listing_candidate_paper_id or "").strip()
        title = str(self._runtime_listing_candidate_title or "").strip()
        if not paper_id or not title:
            return None
        return (
            paper_id,
            title,
            self._runtime_listing_candidate_sort_updated_at,
            self._runtime_listing_candidate_is_fixture,
        )

    def set_runtime_listing_candidate_metadata(
        self,
        *,
        paper_id: Any,
        title: Any,
        sort_updated_at: Any,
        is_fixture: bool,
    ) -> None:
        normalized_paper_id = str(paper_id or "").strip()
        normalized_title = str(title or "").strip()
        self._runtime_listing_candidate_loaded = bool(normalized_paper_id and normalized_title)
        self._runtime_listing_candidate_paper_id = normalized_paper_id or None
        self._runtime_listing_candidate_title = normalized_title or None
        self._runtime_listing_candidate_sort_updated_at = (
            str(sort_updated_at).strip() if sort_updated_at is not None and str(sort_updated_at).strip() else None
        )
        self._runtime_listing_candidate_is_fixture = bool(is_fixture)

    def get_runtime_fixture_preview_is_fixture(self) -> bool | None:
        if not self._runtime_fixture_preview_loaded:
            return None
        return self._runtime_fixture_preview_is_fixture

    def set_runtime_fixture_preview_is_fixture(self, is_fixture: bool) -> None:
        self._runtime_fixture_preview_loaded = True
        self._runtime_fixture_preview_is_fixture = bool(is_fixture)

    def get_runtime_ops_candidate_group_key(self) -> tuple[str, ...] | None:
        if not self._runtime_ops_candidate_group_loaded:
            return None
        return tuple(str(value).strip() for value in self._runtime_ops_candidate_group_key if str(value).strip())

    def set_runtime_ops_candidate_group_key(self, candidate_group_key: Any) -> None:
        self._runtime_ops_candidate_group_loaded = True
        self._runtime_ops_candidate_group_key = tuple(
            str(value).strip() for value in candidate_group_key or () if str(value).strip()
        )


class PaperNoteListResponse(BaseModel):
    generated_at: str
    index_path: str
    total: int
    page: int = 1
    page_size: int = 30
    total_pages: int = 1
    available_tags: list[str] = Field(default_factory=list)
    available_statuses: list[str] = Field(default_factory=list)
    available_reading_assist_note_count: int = 0
    available_reading_assist_locales: list[str] = Field(default_factory=list)
    items: list[PaperNoteIndexItem] = Field(default_factory=list)


def _default_home_marker_triage_counts() -> dict[PaperNoteOperatorTriageLabel, int]:
    return {label: 0 for label in PAPER_NOTE_OPERATOR_TRIAGE_LABEL_ORDER}


class PaperNotesHomeMarkerSummary(BaseModel):
    marked_papers: int = 0
    note_backed_papers: int = 0
    starred: int = 0
    triage_counts: dict[PaperNoteOperatorTriageLabel, int] = Field(default_factory=_default_home_marker_triage_counts)


class PaperNotesHomeContextResponse(BaseModel):
    saved_notes: int = 0
    structured_notes: int = 0
    latest_note_updated_at: str | None = None
    note_context_limited: bool = False
    note_slug_by_paper_id: dict[str, str] = Field(default_factory=dict)
    marker_summary: PaperNotesHomeMarkerSummary = Field(default_factory=PaperNotesHomeMarkerSummary)


class PaperNoteRelatedItem(BaseModel):
    slug: str
    title: str
    shared_tags: list[str] = Field(default_factory=list)
    shared_signals: list[str] = Field(default_factory=list)


class PaperNoteReferenceLink(BaseModel):
    label: str
    url: str
    source: Literal["pdf", "doi", "zotero", "external"] = "external"


PaperNoteContextTraceOutcome = Literal["loaded", "filtered", "resolved", "derived", "missing"]


class PaperNoteContextTraceEntry(BaseModel):
    order: int = Field(..., ge=1)
    action: str = Field(..., min_length=1)
    outcome: PaperNoteContextTraceOutcome
    detail: str = Field(..., min_length=1)
    source_path: str | None = None
    matched_slugs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaperNoteContextTraceSummary(BaseModel):
    entry_count: int = Field(default=0, ge=0)
    source_path_count: int = Field(default=0, ge=0)
    related_count: int = Field(default=0, ge=0)
    reference_count: int = Field(default=0, ge=0)
    action_counts: dict[str, int] = Field(default_factory=dict)
    outcome_counts: dict[str, int] = Field(default_factory=dict)
    source_paths: list[str] = Field(default_factory=list)
    related_slugs: list[str] = Field(default_factory=list)
    reference_sources: list[str] = Field(default_factory=list)


class PaperNoteContextTrace(BaseModel):
    available: bool = False
    summary: PaperNoteContextTraceSummary = Field(default_factory=PaperNoteContextTraceSummary)
    trace: list[PaperNoteContextTraceEntry] = Field(default_factory=list)


class PaperNoteReadingAssistBlock(BaseModel):
    kind: ReadingAssistBlockKind
    label: str
    canonical_text: str | None = None
    translated_text: str
    source_field: str
    source_heading: str | None = None
    source_locale: str = "en"
    translator: str | None = None
    model: str | None = None
    version: str | None = None


class PaperNoteReadingAssist(BaseModel):
    locale: str
    canonical_locale: str = "en"
    machine_translated: bool = True
    partial: bool = True
    blocks: list[PaperNoteReadingAssistBlock] = Field(default_factory=list)


class PaperNoteSectionNavigatorItem(BaseModel):
    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    outline_id: str | None = None
    outline_order: int | None = Field(default=None, ge=0)
    claim_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    representative_claim_id: str | None = None
    representative_evidence_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    matched_to_outline: bool = False


class PaperNoteDetailResponse(BaseModel):
    note: PaperNoteIndexItem
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body_markdown: str
    related: list[PaperNoteRelatedItem] = Field(default_factory=list)
    references: list[PaperNoteReferenceLink] = Field(default_factory=list)
    context_trace: PaperNoteContextTrace | None = None
    structured_state: StructuredPaperState | None = None
    section_navigator: list[PaperNoteSectionNavigatorItem] = Field(default_factory=list)
    reading_assist: PaperNoteReadingAssist | None = None
    operator_state: PaperNoteOperatorState
    available_actions: list[SkillActionInfo] = Field(default_factory=list)


class PaperNoteStructuredStateLookupResponse(BaseModel):
    paper_id: str
    slug: str
    note_path: str
    note: PaperNoteIndexItem | None = None
    pdf_url: str | None = None
    doi_url: str | None = None
    structured_state: StructuredPaperState | None = None
    operator_state: PaperNoteOperatorState | None = None


class PaperNoteImportResponse(BaseModel):
    paper_id: str
    slug: str
    title: str
    note_path: str
    pdf_url: str
