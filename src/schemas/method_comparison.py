from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .cloud_paper import CloudPaperPayloadClass
from .chat import ChatEvidenceRef


MethodComparisonFieldId = Literal[
    "intervention",
    "comparator",
    "duration_or_timepoint",
    "primary_readout",
    "sample_size",
]
MethodComparisonValueKind = Literal["text", "numeric", "duration", "categorical"]
MethodComparisonCellStatus = Literal["explicit", "inferred", "missing", "conflict"]
MethodComparisonReadiness = Literal["evidence_backed", "background_only", "mixed"]
MethodComparisonFreshness = Literal["current", "stale", "unknown"]
MethodComparisonCloudDerivedKind = Literal["ocr_text", "table"]


class MethodComparisonFieldSpec(BaseModel):
    field_id: MethodComparisonFieldId
    label: str = Field(..., min_length=1)
    value_kind: MethodComparisonValueKind
    description: str = Field(..., min_length=1)


METHOD_COMPARISON_FIELD_SPECS: tuple[MethodComparisonFieldSpec, ...] = (
    MethodComparisonFieldSpec(
        field_id="intervention",
        label="Intervention",
        value_kind="text",
        description="Primary intervention or exposure being tested.",
    ),
    MethodComparisonFieldSpec(
        field_id="comparator",
        label="Comparator",
        value_kind="text",
        description="Comparator, control, placebo, or baseline condition.",
    ),
    MethodComparisonFieldSpec(
        field_id="duration_or_timepoint",
        label="Duration / Timepoint",
        value_kind="duration",
        description="Treatment duration, follow-up window, or key measurement timepoint.",
    ),
    MethodComparisonFieldSpec(
        field_id="primary_readout",
        label="Primary Readout",
        value_kind="categorical",
        description="Primary endpoint, assay, or outcome readout emphasized by the study.",
    ),
    MethodComparisonFieldSpec(
        field_id="sample_size",
        label="Sample Size",
        value_kind="numeric",
        description="Reported sample size or count tied to the compared method lane.",
    ),
)
METHOD_COMPARISON_FIELD_MAP: dict[MethodComparisonFieldId, MethodComparisonFieldSpec] = {
    spec.field_id: spec for spec in METHOD_COMPARISON_FIELD_SPECS
}


def method_comparison_field_specs() -> list[MethodComparisonFieldSpec]:
    return [spec.model_copy(deep=True) for spec in METHOD_COMPARISON_FIELD_SPECS]


def build_method_comparison_columns(
    field_ids: list[MethodComparisonFieldId],
) -> list["ComparisonColumn"]:
    return [
        ComparisonColumn(
            field_id=field_id,
            label=METHOD_COMPARISON_FIELD_MAP[field_id].label,
            value_kind=METHOD_COMPARISON_FIELD_MAP[field_id].value_kind,
        )
        for field_id in field_ids
    ]


class MethodComparisonRequest(BaseModel):
    comparison_id: str | None = None
    title: str | None = None
    paper_ids: list[str] = Field(default_factory=list, min_length=1)
    field_ids: list[MethodComparisonFieldId] = Field(default_factory=list, min_length=1)
    notes: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_lists(self):
        self.paper_ids = _dedupe_non_empty_strings(self.paper_ids, field_name="paper_ids")
        self.field_ids = _dedupe_field_ids(self.field_ids)
        return self


class MethodComparisonCloudDerivedContextItem(BaseModel):
    context_id: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    kind: MethodComparisonCloudDerivedKind
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    text: str | None = None
    source_page: int = Field(..., ge=1)
    source_block_id: str | None = None
    source_pdf_sha256: str = Field(..., min_length=64, max_length=64)
    payload_class: CloudPaperPayloadClass = "local_only"
    readiness: Literal["background_only"] = "background_only"
    canonical_status: Literal["derived_noncanonical"] = "derived_noncanonical"
    comparison_cell_status: Literal["missing"] = "missing"
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[ChatEvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_context_item(self):
        self.context_id = self.context_id.strip()
        self.candidate_id = self.candidate_id.strip()
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.title = self.title.strip()
        self.text = self.text.strip() or None if self.text is not None else None
        self.source_block_id = self.source_block_id.strip() or None if self.source_block_id is not None else None
        self.source_pdf_sha256 = self.source_pdf_sha256.strip().lower()
        if self.evidence_refs:
            raise ValueError("cloud-derived Method Comparison context must not carry evidence refs")
        return self


class MethodComparisonCloudDerivedContext(BaseModel):
    schema_version: Literal["method_comparison_cloud_derived_context.v1"] = "method_comparison_cloud_derived_context.v1"
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    source_pdf_sha256: str = Field(..., min_length=64, max_length=64)
    readiness: Literal["background_only"] = "background_only"
    payload_class: CloudPaperPayloadClass = "local_only"
    items: list[MethodComparisonCloudDerivedContextItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_context(self):
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.source_pdf_sha256 = self.source_pdf_sha256.strip().lower()
        for item in self.items:
            if item.paper_id != self.paper_id:
                raise ValueError("item.paper_id must match context paper_id")
            if item.run_id != self.run_id:
                raise ValueError("item.run_id must match context run_id")
            if item.source_pdf_sha256 != self.source_pdf_sha256:
                raise ValueError("item source checksum must match context source_pdf_sha256")
        return self


class ComparisonColumn(BaseModel):
    field_id: MethodComparisonFieldId
    label: str = Field(..., min_length=1)
    value_kind: MethodComparisonValueKind


class ComparisonCell(BaseModel):
    field_id: MethodComparisonFieldId
    value: str | int | float | None = None
    normalized_value: str | int | float | None = None
    status: MethodComparisonCellStatus = "missing"
    note: str | None = None
    evidence_refs: list[ChatEvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_payload(self):
        has_value = self.value not in (None, "")
        if self.status == "missing":
            self.value = None
            self.normalized_value = None
            self.evidence_refs = []
            return self
        if not has_value:
            raise ValueError("ComparisonCell requires value when status is not missing")
        return self


class ComparisonRow(BaseModel):
    paper_id: str = Field(..., min_length=1)
    paper_slug: str | None = None
    citekey: str | None = None
    title: str = Field(..., min_length=1)
    cells: list[ComparisonCell] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_field_ids(self):
        seen: set[str] = set()
        for cell in self.cells:
            if cell.field_id in seen:
                raise ValueError(f"Duplicate field_id in ComparisonRow: {cell.field_id}")
            seen.add(cell.field_id)
        return self


class ComparisonSourceSummary(BaseModel):
    source_priority: list[str] = Field(
        default_factory=lambda: [
            "claimset.resolved.json",
            "document_artifact",
            "paper_note_state",
        ]
    )
    note: str | None = None
    source_paper_count: int = 0
    note_backed_paper_count: int = 0
    operator_override_count: int = 0


class MethodComparison(BaseModel):
    comparison_id: str = Field(..., pattern=r"^methodcmp_[A-Za-z0-9._-]+$")
    title: str = Field(..., min_length=1)
    created_at: datetime
    generated_at: datetime | None = None
    layer: Literal["user_facing_artifact"] = "user_facing_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    readiness: MethodComparisonReadiness = "background_only"
    freshness: MethodComparisonFreshness = "unknown"
    paper_ids: list[str] = Field(default_factory=list, min_length=1)
    columns: list[ComparisonColumn] = Field(default_factory=list, min_length=1)
    rows: list[ComparisonRow] = Field(default_factory=list)
    source_summary: ComparisonSourceSummary = Field(default_factory=ComparisonSourceSummary)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_identity_lists(self):
        self.paper_ids = _dedupe_non_empty_strings(self.paper_ids, field_name="paper_ids")
        return self


class MethodComparisonResponse(BaseModel):
    comparison: MethodComparison
    csv_text: str
    markdown: str


class MethodComparisonListItem(BaseModel):
    comparison_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    created_at: datetime
    generated_at: datetime | None = None
    paper_count: int = Field(default=0, ge=0)
    field_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)


class MethodComparisonListResponse(BaseModel):
    items: list[MethodComparisonListItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


def _dedupe_non_empty_strings(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            raise ValueError(f"{field_name} entries must be non-empty")
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


def _dedupe_field_ids(values: list[MethodComparisonFieldId]) -> list[MethodComparisonFieldId]:
    normalized: list[MethodComparisonFieldId] = []
    seen: set[str] = set()
    for field_id in values:
        if field_id not in seen:
            normalized.append(field_id)
            seen.add(field_id)
    return normalized
