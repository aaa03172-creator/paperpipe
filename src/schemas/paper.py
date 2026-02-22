from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from src.schemas.downloader import DownloadAttempt


class PaperStatus(str, Enum):
    """
    Canonical status terms shared across gate decisions and DB status.
    """

    APPROVED = "APPROVED"
    PENDING_REVIEW = "PENDING_REVIEW"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"
    INDEXED = "INDEXED"
    AUTO_APPROVED = "APPROVED"


class ReadingStatus(str, Enum):
    """
    User-facing reading status for workflow management.
    """

    INBOX = "Inbox"
    READING = "Reading"
    DONE = "Done"


class Paper(BaseModel):
    """논문 정보를 담는 표준 스키마"""

    id: str = Field(description="Unique ID (DOI or timestamp based)")
    title: str
    authors: List[str]
    published: str
    source: str = Field(description="Source of the paper (Pubmed, ArXiv, etc)")
    summary: str
    link: str

    processing_status: PaperStatus = Field(
        default=PaperStatus.PENDING_REVIEW,
        description="Current processing status based on confidence.",
    )
    is_retracted: bool = Field(default=False, description="True if the paper has been retracted")
    retraction_details: Optional[str] = Field(None, description="Details about retraction or correction")
    is_escalated: bool = Field(default=False, description="True if auto-approved via escalation judge")
    escalation_reason: Optional[str] = Field(None, description="Reason for escalation approval")
    relevance_analysis: Optional[Dict[str, str]] = None
    citation_count: Optional[int] = Field(None, description="Total citations from OpenAlex")
    impact_factor: Optional[float] = Field(None, description="Journal Impact Factor proxy (SJR)")
    journal_tier: Optional[str] = Field(None, description="Q1/Q2/Q3/Q4 or similar ranking")
    reading_status: ReadingStatus = Field(
        default=ReadingStatus.INBOX,
        description="User workflow status (Inbox, Reading, Done)",
    )
    manual_rank_score: Optional[float] = Field(None, description="Final calculated rank score")
    download_attempts: List[DownloadAttempt] = Field(
        default_factory=list,
        description="PDF download attempts across providers",
    )

    doi: Optional[str] = Field(default=None, description="DOI of the paper")
    pdf_link: Optional[str] = Field(default=None, description="Direct PDF URL")
    full_text: Optional[str] = None
    local_pdf_path: Optional[Path] = None

    @field_validator("processing_status", mode="before")
    @classmethod
    def normalize_processing_status(cls, v):
        """Accept legacy labels and normalize to canonical enum values."""
        if isinstance(v, PaperStatus):
            return v
        if isinstance(v, str):
            key = v.strip().upper().replace("-", "_").replace(" ", "_")
            legacy_map = {
                "AUTO_APPROVED": "APPROVED",
                "AUTOAPPROVED": "APPROVED",
                "APPROVED": "APPROVED",
                "PENDING_REVIEW": "PENDING_REVIEW",
                "PENDING": "PENDING_REVIEW",
                "QUARANTINED": "QUARANTINED",
                "FAILED": "FAILED",
                "INDEXED": "INDEXED",
            }
            if key in legacy_map:
                return PaperStatus(legacy_map[key])
        return v
