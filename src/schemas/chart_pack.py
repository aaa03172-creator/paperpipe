from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.artifact_brief import ArtifactBrief, ArtifactPlanReview
from src.schemas.chart_pack_handoff import ChartPackQualityGate


ChartSourceKind = Literal["stats_report", "document_table", "cloud_derived_table"]
ChartTemplateId = Literal[
    "stats_check_status_counts",
    "reported_vs_computed_p_scatter",
    "table_numeric_bar",
    "table_numeric_line",
]
ChartWarningSeverity = Literal["info", "warning", "error"]
ChartFilterOp = Literal["eq", "neq", "gt", "gte", "lt", "lte", "in"]
ChartSortDirection = Literal["asc", "desc"]
ChartTransformKind = Literal["field_mapping", "filter", "sort", "coerce_numeric"]
ChartArtifactKind = Literal["data_csv", "spec_json", "render_png", "render_svg"]
ChartValueKind = Literal["text", "numeric", "boolean"]
ChartScalar = str | int | float | bool
ChartFilterValue = ChartScalar | list[ChartScalar]
CHART_PACK_ID_PATTERN = re.compile(r"^chartpack_[A-Za-z0-9._-]+$")
CHART_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


class ChartTemplateSpec(BaseModel):
    template_id: ChartTemplateId
    label: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    supported_source_kinds: list[ChartSourceKind] = Field(default_factory=list, min_length=1)


CHART_TEMPLATE_SPECS: tuple[ChartTemplateSpec, ...] = (
    ChartTemplateSpec(
        template_id="stats_check_status_counts",
        label="Stats Check Status Counts",
        description="Count verification checks by verdict from a saved stats report.",
        supported_source_kinds=["stats_report"],
    ),
    ChartTemplateSpec(
        template_id="reported_vs_computed_p_scatter",
        label="Reported vs Computed p Scatter",
        description="Plot reported p values against computed p values when both are present.",
        supported_source_kinds=["stats_report"],
    ),
    ChartTemplateSpec(
        template_id="table_numeric_bar",
        label="Numeric Table Bar Chart",
        description="Render a bar chart from an explicitly selected numeric document table column.",
        supported_source_kinds=["document_table", "cloud_derived_table"],
    ),
    ChartTemplateSpec(
        template_id="table_numeric_line",
        label="Numeric Table Line Chart",
        description="Render a line chart from an explicitly selected numeric document table column.",
        supported_source_kinds=["document_table", "cloud_derived_table"],
    ),
)
CHART_TEMPLATE_MAP: dict[ChartTemplateId, ChartTemplateSpec] = {
    spec.template_id: spec for spec in CHART_TEMPLATE_SPECS
}


def chart_template_specs() -> list[ChartTemplateSpec]:
    return [spec.model_copy(deep=True) for spec in CHART_TEMPLATE_SPECS]


class ChartSourceRef(BaseModel):
    source_kind: ChartSourceKind
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    table_id: str | None = None
    source_label: str | None = None

    @model_validator(mode="after")
    def validate_source_ref(self):
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        if self.source_label is not None:
            self.source_label = self.source_label.strip() or None
        if self.table_id is not None:
            self.table_id = self.table_id.strip() or None

        if self.source_kind == "stats_report":
            if self.table_id is not None:
                raise ValueError("stats_report source refs must not include table_id")
            return self
        if self.source_kind in {"document_table", "cloud_derived_table"}:
            if not self.table_id:
                raise ValueError(f"{self.source_kind} source refs require table_id")
            return self
        return self


class ChartFieldMapping(BaseModel):
    target_field: str = Field(..., min_length=1)
    source_field: str = Field(..., min_length=1)
    label: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self):
        self.target_field = self.target_field.strip()
        self.source_field = self.source_field.strip()
        if self.label is not None:
            self.label = self.label.strip() or None
        return self


class ChartFilter(BaseModel):
    field: str = Field(..., min_length=1)
    op: ChartFilterOp
    value: ChartFilterValue

    @model_validator(mode="after")
    def normalize_field(self):
        self.field = self.field.strip()
        return self


class ChartSort(BaseModel):
    field: str = Field(..., min_length=1)
    direction: ChartSortDirection = "asc"

    @model_validator(mode="after")
    def normalize_field(self):
        self.field = self.field.strip()
        return self


class ChartTransform(BaseModel):
    kind: ChartTransformKind
    description: str = Field(..., min_length=1)
    field: str | None = None
    value: ChartFilterValue | None = None

    @model_validator(mode="after")
    def normalize_transform(self):
        self.description = self.description.strip()
        if self.field is not None:
            self.field = self.field.strip() or None
        return self


class ChartWarning(BaseModel):
    code: str = Field(..., min_length=1)
    severity: ChartWarningSeverity = "warning"
    message: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_warning(self):
        self.code = self.code.strip()
        self.message = self.message.strip()
        return self


class ChartArtifactRef(BaseModel):
    kind: ChartArtifactKind
    path: str = Field(..., min_length=1)
    mime_type: str | None = None

    @model_validator(mode="after")
    def validate_relative_path(self):
        normalized = self.path.strip()
        if not normalized:
            raise ValueError("ChartArtifactRef.path must be non-empty")
        if Path(normalized).is_absolute():
            raise ValueError("ChartArtifactRef.path must be pack-relative")
        self.path = normalized
        if self.mime_type is not None:
            self.mime_type = self.mime_type.strip() or None
        return self


class ChartRenderEnv(BaseModel):
    engine: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_render_env(self):
        self.engine = self.engine.strip()
        self.version = self.version.strip()
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class ChartSnapshotField(BaseModel):
    field_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    value_kind: ChartValueKind = "text"
    source_field: str | None = None

    @model_validator(mode="after")
    def normalize_field(self):
        self.field_id = self.field_id.strip()
        self.label = self.label.strip()
        if self.source_field is not None:
            self.source_field = self.source_field.strip() or None
        return self


class ChartDataSnapshot(BaseModel):
    template_id: ChartTemplateId
    source_ref: ChartSourceRef
    columns: list[ChartSnapshotField] = Field(default_factory=list, min_length=1)
    rows: list[dict[str, ChartScalar | None]] = Field(default_factory=list)
    transforms: list[ChartTransform] = Field(default_factory=list)
    warnings: list[ChartWarning] = Field(default_factory=list)
    source_row_count: int = Field(default=0, ge=0)
    note: str | None = None

    @model_validator(mode="after")
    def normalize_note(self):
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ChartRequest(BaseModel):
    chart_id: str | None = None
    title: str | None = None
    template_id: ChartTemplateId
    source_ref: ChartSourceRef
    field_mappings: list[ChartFieldMapping] = Field(default_factory=list, min_length=1)
    filters: list[ChartFilter] = Field(default_factory=list)
    sort: ChartSort | None = None

    @model_validator(mode="after")
    def normalize_chart_request(self):
        if self.chart_id is not None:
            self.chart_id = _normalize_chart_id(self.chart_id)
        if self.title is not None:
            self.title = self.title.strip() or None
        return self


class ChartDefinition(BaseModel):
    chart_id: str = Field(..., pattern=CHART_ID_PATTERN.pattern)
    title: str = Field(..., min_length=1)
    template_id: ChartTemplateId
    source_ref: ChartSourceRef
    field_mappings: list[ChartFieldMapping] = Field(default_factory=list, min_length=1)
    filters: list[ChartFilter] = Field(default_factory=list)
    sort: ChartSort | None = None
    transforms: list[ChartTransform] = Field(default_factory=list)
    warnings: list[ChartWarning] = Field(default_factory=list)
    data_snapshot_ref: ChartArtifactRef | None = None
    spec_ref: ChartArtifactRef | None = None
    render_refs: list[ChartArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_artifact_refs(self):
        self.chart_id = _normalize_chart_id(self.chart_id) or ""
        self.title = self.title.strip()
        if self.data_snapshot_ref is not None and self.data_snapshot_ref.kind != "data_csv":
            raise ValueError("data_snapshot_ref must use kind=data_csv")
        if self.spec_ref is not None and self.spec_ref.kind != "spec_json":
            raise ValueError("spec_ref must use kind=spec_json")
        for ref in self.render_refs:
            if ref.kind not in {"render_png", "render_svg"}:
                raise ValueError("render_refs must use render_png or render_svg")
        return self


class ChartPackRequest(BaseModel):
    chart_pack_id: str | None = None
    title: str | None = None
    charts: list[ChartRequest] = Field(default_factory=list, min_length=1)
    notes: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        if self.chart_pack_id is not None:
            self.chart_pack_id = self.chart_pack_id.strip() or None
        if self.title is not None:
            self.title = self.title.strip() or None
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class ChartPack(BaseModel):
    chart_pack_id: str = Field(..., pattern=CHART_PACK_ID_PATTERN.pattern)
    title: str = Field(..., min_length=1)
    created_at: datetime
    generated_at: datetime | None = None
    charts: list[ChartDefinition] = Field(default_factory=list, min_length=1)
    source_items: list[ChartSourceRef] = Field(default_factory=list)
    generation_request: ChartPackRequest | None = None
    render_env: ChartRenderEnv | None = None
    caution_notes: list[str] = Field(default_factory=list)
    warnings: list[ChartWarning] = Field(default_factory=list)
    artifact_brief: ArtifactBrief | None = None
    artifact_brief_review: ArtifactPlanReview | None = None

    @model_validator(mode="after")
    def validate_chart_pack(self):
        self.title = self.title.strip()
        self.caution_notes = _dedupe_non_empty_strings(self.caution_notes, field_name="caution_notes")
        seen_chart_ids: set[str] = set()
        for chart in self.charts:
            if chart.chart_id in seen_chart_ids:
                raise ValueError(f"Duplicate chart_id in ChartPack: {chart.chart_id}")
            seen_chart_ids.add(chart.chart_id)
        return self


class ChartPackSummary(BaseModel):
    chart_pack_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    created_at: datetime
    generated_at: datetime | None = None
    chart_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)


class ChartPackResponse(BaseModel):
    chart_pack: ChartPack
    markdown: str
    data_snapshots: dict[str, str] = Field(default_factory=dict)
    specs: dict[str, Any] = Field(default_factory=dict)
    quality_gate: ChartPackQualityGate | None = None


class ChartPackListResponse(BaseModel):
    items: list[ChartPackSummary] = Field(default_factory=list)
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


def _normalize_chart_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not CHART_ID_PATTERN.fullmatch(text):
        raise ValueError("chart_id must be a single safe path segment")
    return text
