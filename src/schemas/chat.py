from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatLocator(BaseModel):
    page: int | None = None
    span: list[int] = Field(default_factory=list)
    section: str | None = None
    chunk_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox_pdf: list[float] | None = None
    bbox_pct: dict[str, float] | None = None
    table_id: str | None = None
    cell_id: str | None = None
    source: str | None = None


class ChatEvidenceRef(BaseModel):
    paper_slug: str
    claim_id: str | None = None
    evidence_id: str | None = None
    run_id: str | None = None
    locator: ChatLocator | None = None


class ChatSuggestedAction(BaseModel):
    action: str
    reason: str


class ChatResponse(BaseModel):
    answer: str
    evidence_refs: list[ChatEvidenceRef] = Field(default_factory=list)
    suggested_actions: list[ChatSuggestedAction] = Field(default_factory=list)


class ChatRequest(BaseModel):
    paper_slug: str | None = None
    message: str = Field(..., min_length=1)
    focus: str | None = None


class ChatStubResponse(BaseModel):
    error_code: Literal["CHAT_NOT_IMPLEMENTED"] = "CHAT_NOT_IMPLEMENTED"
    chat_enabled: bool = False
    message: str
    external_calls: bool = False
