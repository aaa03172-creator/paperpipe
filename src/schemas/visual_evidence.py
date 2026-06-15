from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


VisualEvidenceKind = Literal[
    "figure",
    "table",
    "plot",
    "microscopy",
    "diagram",
    "supplementary_figure",
    "other",
]
VisualEvidenceStatus = Literal["observed", "partially_observed", "unknown", "unsupported"]
VisualEvidenceFailureReason = Literal[
    "ocr_failed",
    "vision_unavailable",
    "ambiguous_panel",
    "caption_only",
    "table_parse_failed",
    "figure_table_conflict",
    "bbox_unavailable",
    "not_reviewed",
    "other",
]


class VisualEvidenceBBox(BaseModel):
    bbox_pdf: list[float] | None = Field(
        default=None,
        description="[x0, y0, x1, y1] in PDF points, top-left origin.",
    )
    bbox_pct: dict[str, float] | None = Field(
        default=None,
        description="UI-friendly percentage bbox with left/top/width/height.",
    )

    @model_validator(mode="after")
    def validate_bbox(self):
        if self.bbox_pdf is not None:
            if len(self.bbox_pdf) != 4:
                raise ValueError("bbox_pdf must contain 4 numeric values")
            x0, y0, x1, y1 = self.bbox_pdf
            if min(x0, y0, x1, y1) < 0:
                raise ValueError("bbox_pdf values must be non-negative")
            if x0 > x1 or y0 > y1:
                raise ValueError("bbox_pdf must satisfy x0<=x1 and y0<=y1")

        if self.bbox_pct is not None:
            required = {"left", "top", "width", "height"}
            if not required.issubset(set(self.bbox_pct.keys())):
                raise ValueError("bbox_pct must include left/top/width/height")
        return self


class VisualExtractedValue(BaseModel):
    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    unit: str | None = None
    table_id: str | None = None
    cell_id: str | None = None
    row_label: str | None = None
    column_label: str | None = None

    @model_validator(mode="after")
    def validate_table_cell_pair(self):
        self.label = self.label.strip()
        self.value = self.value.strip()
        if self.unit is not None:
            self.unit = self.unit.strip() or None
        if self.table_id is not None:
            self.table_id = self.table_id.strip() or None
        if self.cell_id is not None:
            self.cell_id = self.cell_id.strip() or None
        if self.row_label is not None:
            self.row_label = self.row_label.strip() or None
        if self.column_label is not None:
            self.column_label = self.column_label.strip() or None

        if (self.table_id is None) != (self.cell_id is None):
            raise ValueError("table_id and cell_id must be provided together")
        return self


class VisualEvidenceObject(BaseModel):
    evidence_id: str = Field(..., min_length=1)
    kind: VisualEvidenceKind
    page: int = Field(..., ge=0, description="0-indexed PDF page number.")
    figure_id: str | None = None
    table_id: str | None = None
    caption: str | None = None
    bbox: VisualEvidenceBBox | None = None
    observed_elements: list[str] = Field(default_factory=list)
    observed_text: list[str] = Field(default_factory=list)
    extracted_values: list[VisualExtractedValue] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)
    not_allowed_claims: list[str] = Field(default_factory=list)
    inferred_notes: list[str] = Field(default_factory=list)
    status: VisualEvidenceStatus = "unknown"
    failure_reason: VisualEvidenceFailureReason | None = None
    linked_claim_ids: list[str] = Field(default_factory=list)
    source_artifact: str | None = None

    @model_validator(mode="after")
    def validate_visual_evidence_object(self):
        self.evidence_id = self.evidence_id.strip()
        if self.figure_id is not None:
            self.figure_id = self.figure_id.strip() or None
        if self.table_id is not None:
            self.table_id = self.table_id.strip() or None
        if self.caption is not None:
            self.caption = self.caption.strip() or None
        if self.source_artifact is not None:
            self.source_artifact = self.source_artifact.strip() or None

        self.observed_elements = _clean_list(self.observed_elements)
        self.observed_text = _clean_list(self.observed_text)
        self.allowed_claims = _clean_list(self.allowed_claims)
        self.not_allowed_claims = _clean_list(self.not_allowed_claims)
        self.inferred_notes = _clean_list(self.inferred_notes)
        self.linked_claim_ids = _clean_list(self.linked_claim_ids)

        if self.kind == "table" and not self.table_id:
            raise ValueError("table visual evidence requires table_id")
        if self.kind in {"figure", "plot", "microscopy", "diagram", "supplementary_figure"} and not self.figure_id:
            raise ValueError("figure-like visual evidence requires figure_id")
        if self.status in {"unknown", "unsupported"} and self.failure_reason is None:
            raise ValueError("unknown or unsupported visual evidence requires failure_reason")
        if self.status == "observed" and self.failure_reason is not None:
            raise ValueError("observed visual evidence must not include failure_reason")
        if self.status == "observed" and not (
            self.observed_elements or self.observed_text or self.extracted_values or self.allowed_claims
        ):
            raise ValueError("observed visual evidence requires observed content or allowed_claims")
        return self


class VisualEvidenceMetrics(BaseModel):
    entry_count: int = 0
    observed_count: int = 0
    partially_observed_count: int = 0
    unknown_count: int = 0
    unsupported_count: int = 0
    linked_claim_count: int = 0


class VisualEvidenceLedger(BaseModel):
    schema_version: Literal["visual_evidence_ledger.v1"] = "visual_evidence_ledger.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    generated_at: datetime
    source_artifacts: list[str] = Field(
        default_factory=lambda: ["document_artifact.json", "figure_captions.json", "claimset.resolved.json"]
    )
    entries: list[VisualEvidenceObject] = Field(default_factory=list)
    metrics: VisualEvidenceMetrics = Field(default_factory=VisualEvidenceMetrics)
    generation_replay_required: bool = True
    final_answer_validation_required: bool = True

    @model_validator(mode="after")
    def validate_ledger(self):
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.source_artifacts = _clean_list(self.source_artifacts)
        entry_ids = [entry.evidence_id for entry in self.entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("VisualEvidenceLedger.entries must not contain duplicate evidence_id values")
        return self


def summarize_visual_evidence(entries: list[VisualEvidenceObject]) -> VisualEvidenceMetrics:
    linked_claim_ids = {
        claim_id
        for entry in entries
        for claim_id in entry.linked_claim_ids
        if claim_id.strip()
    }
    return VisualEvidenceMetrics(
        entry_count=len(entries),
        observed_count=sum(1 for entry in entries if entry.status == "observed"),
        partially_observed_count=sum(1 for entry in entries if entry.status == "partially_observed"),
        unknown_count=sum(1 for entry in entries if entry.status == "unknown"),
        unsupported_count=sum(1 for entry in entries if entry.status == "unsupported"),
        linked_claim_count=len(linked_claim_ids),
    )


def _clean_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]
