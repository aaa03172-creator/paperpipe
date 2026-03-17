from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .skills import SkillActionInfo, StructuredPaperState


class PaperNoteOpsSummary(BaseModel):
    state: Literal["healthy", "action_needed"]
    label: str
    reason: str
    recommended_action: Literal["none", "repair_stats", "open_workbench"] = "none"
    latest_run_id: str | None = None
    has_claimset: bool = False
    has_stats_report: bool = False
    stats_check_count: int = 0


class PaperNoteIndexItem(BaseModel):
    slug: str
    title: str
    note_path: str
    id: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    date_processed: str | None = None
    confidence: float | None = None
    status: str | None = None
    doi: str | None = None
    zotero_link: str | None = None
    updated_at: str | None = None


class PaperNoteListResponse(BaseModel):
    generated_at: str
    index_path: str
    total: int
    page: int = 1
    page_size: int = 30
    total_pages: int = 1
    available_tags: list[str] = Field(default_factory=list)
    available_statuses: list[str] = Field(default_factory=list)
    items: list[PaperNoteIndexItem] = Field(default_factory=list)


class PaperNoteRelatedItem(BaseModel):
    slug: str
    title: str
    shared_tags: list[str] = Field(default_factory=list)


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

class PaperNoteDetailResponse(BaseModel):
    note: PaperNoteIndexItem
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body_markdown: str
    related: list[PaperNoteRelatedItem] = Field(default_factory=list)
    references: list[PaperNoteReferenceLink] = Field(default_factory=list)
    context_trace: PaperNoteContextTrace | None = None
    structured_state: StructuredPaperState | None = None
    available_actions: list[SkillActionInfo] = Field(default_factory=list)


class PaperNoteStructuredStateLookupResponse(BaseModel):
    paper_id: str
    slug: str
    note_path: str
    structured_state: StructuredPaperState | None = None
