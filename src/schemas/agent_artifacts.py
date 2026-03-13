from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    INCONSISTENT = "inconsistent"
    UNVERIFIABLE = "unverifiable"


class SourceInfo(BaseModel):
    type: str
    ref: str


class PaperMetadata(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    year: int = 0
    journal: str = "Unknown"
    doi: Optional[str] = None
    pmid: Optional[str] = None


class Section(BaseModel):
    name: str
    text: str
    char_start: int = 0
    char_end: int = 0


class TableData(BaseModel):
    table_id: str
    caption: str
    data: List[List[str]] = Field(default_factory=list)
    source_page: int


class DocumentArtifact(BaseModel):
    doc_id: str
    source: SourceInfo
    metadata: PaperMetadata
    sections: List[Section] = Field(default_factory=list)
    tables: List[TableData] = Field(default_factory=list)


class ScientificClaim(BaseModel):
    claim_id: str
    type: str
    statement: str
    confidence: float = 0.0
    evidence_spans: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class ClaimSet(BaseModel):
    doc_id: str
    claims: List[ScientificClaim] = Field(default_factory=list)


class StatCheckEntry(BaseModel):
    check_id: str
    hypothesis: Optional[str] = None
    test_type: str
    method: str
    reported_p: Optional[str] = None
    computed_p: Optional[float] = None
    code: str
    outputs: str
    verdict: VerificationStatus
    notes: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)


class StatsReport(BaseModel):
    doc_id: str
    run_id: str
    checks: List[StatCheckEntry] = Field(default_factory=list)
