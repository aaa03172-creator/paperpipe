from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


EvidenceExtractionRecordType = Literal["claim", "clinical_field", "entity", "relation"]
EvidenceExtractionRecordStatus = Literal["evidence_backed", "artifact_backed", "derived"]


class EvidenceExtractionLocator(BaseModel):
    page: int | None = None
    chunk_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    section: str | None = None
    table_id: str | None = None
    cell_id: str | None = None
    bbox_pdf: list[float] | None = None
    bbox_pct: dict[str, float] | None = None


class EvidenceExtractionRef(BaseModel):
    claim_id: str | None = None
    quote: str | None = None
    rationale: str | None = None
    grounded: bool | None = None
    resolution: str | None = None
    locator: EvidenceExtractionLocator | None = None


class EvidenceExtractionRecord(BaseModel):
    record_id: str
    record_type: EvidenceExtractionRecordType
    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    normalized_value: str | int | float | None = None
    source_artifact: str = Field(..., min_length=1)
    field_path: str | None = None
    claim_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: EvidenceExtractionRecordStatus = "derived"
    tags: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceExtractionRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence_status(self):
        if self.status == "evidence_backed" and not self.evidence_refs:
            raise ValueError("Evidence-backed extraction records require evidence_refs")
        return self


class EvidenceExtractionMetrics(BaseModel):
    record_count: int = 0
    claim_record_count: int = 0
    clinical_field_record_count: int = 0
    entity_record_count: int = 0
    relation_record_count: int = 0
    evidence_backed_record_count: int = 0
    artifact_backed_record_count: int = 0
    derived_record_count: int = 0
    evidence_ref_count: int = 0
    grounded_evidence_ref_count: int = 0


class EvidenceExtractionBundle(BaseModel):
    schema_version: str = "evidence_extraction.v1"
    workflow: Literal["deep_read"] = "deep_read"
    generated_at: datetime
    paper_id: str
    doc_id: str
    run_id: str
    source_artifacts: list[str] = Field(default_factory=list)
    records: list[EvidenceExtractionRecord] = Field(default_factory=list)
    metrics: EvidenceExtractionMetrics = Field(default_factory=EvidenceExtractionMetrics)
    warnings: list[str] = Field(default_factory=list)
