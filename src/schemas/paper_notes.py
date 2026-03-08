from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class PaperNoteDetailResponse(BaseModel):
    note: PaperNoteIndexItem
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body_markdown: str
    related: list[PaperNoteRelatedItem] = Field(default_factory=list)
    references: list[PaperNoteReferenceLink] = Field(default_factory=list)
