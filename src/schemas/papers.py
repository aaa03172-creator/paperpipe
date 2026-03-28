from __future__ import annotations

from pydantic import BaseModel
from typing import Literal

from .paper_notes import PaperNoteOpsSummary


PaperIssueState = Literal["flagged", "clear", "unavailable"]


class PaperSummaryResponse(BaseModel):
    paper_id: str
    title: str
    authors: str | None = None
    year: int | None = None
    pdf_exists: bool = False
    pdf_path: str | None = None
    pdf_status: str | None = None
    status: str | None = None
    issues: int | None = None
    issues_label: str | None = None
    issues_state: PaperIssueState | None = None
    latest_job_id: str | None = None
    latest_run_id: str | None = None
    updated_at: str | None = None
    is_escalated: bool = False
    escalation_reason: str | None = None
    escalation_final_route: str | None = None
    escalation_in_biomedical_scope: bool | None = None
    escalation_reason_codes: list[str] = []
    ops_summary: PaperNoteOpsSummary | None = None


class PaperDetailResponse(PaperSummaryResponse):
    abstract: str | None = None
