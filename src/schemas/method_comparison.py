from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
