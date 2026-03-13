from pydantic import BaseModel, Field

from .agent_artifacts import (
    ClaimSet,
    DocumentArtifact,
    PaperMetadata,
    ScientificClaim,
    SourceInfo,
    StatCheckEntry,
    StatsReport,
    TableData,
    VerificationStatus,
)


class TrialExtraction(BaseModel):
    intervention: str | None = None
    sample_size: int | None = None
    outcomes: list[str] = Field(default_factory=list)


__all__ = [
    "ClaimSet",
    "DocumentArtifact",
    "PaperMetadata",
    "ScientificClaim",
    "SourceInfo",
    "StatCheckEntry",
    "StatsReport",
    "TableData",
    "TrialExtraction",
    "VerificationStatus",
]
