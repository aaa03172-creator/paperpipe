from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class GateDecision(str, Enum):
    APPROVED = "APPROVED"
    PENDING_REVIEW = "PENDING_REVIEW"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"


class ReasonCode(str, Enum):
    CONFIDENCE_LOW = "CONFIDENCE_LOW"
    CONFIDENCE_MID = "CONFIDENCE_MID"
    SCHEMA_PARSE_FAIL = "SCHEMA_PARSE_FAIL"
    SCHEMA_VALIDATION_FAIL = "SCHEMA_VALIDATION_FAIL"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"


class ConfidenceComponents(BaseModel):
    self: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    judge: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    evidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    hard_fields: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class EvidenceSnippet(BaseModel):
    snippet: str
    location: Literal["abstract", "methods", "results", "discussion", "unknown"] = "unknown"
    supports: str


class GateResult(BaseModel):
    decision: GateDecision
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    confidence_total: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_components: ConfidenceComponents = Field(default_factory=ConfidenceComponents)
    missing_fields: List[str] = Field(default_factory=list)
    evidence_snippets: List[EvidenceSnippet] = Field(default_factory=list)
