from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.ml_training_examples import PayloadClass


ExtractionNormalizationLayer = Literal["review_gate_artifact"]
ExtractionNormalizationCanonicalStatus = Literal["non_canonical"]


class _StrictExtractionNormalizationModel(BaseModel):
    model_config = {"extra": "forbid"}


class ExtractionNormalizationFieldResult(_StrictExtractionNormalizationModel):
    field_path: str = Field(..., min_length=1)
    candidate_value_json: str | None = None
    reviewed_value_json: str = Field(..., min_length=1)
    matched: bool
    missing_candidate: bool = False

    @model_validator(mode="after")
    def normalize_field_result(self):
        self.field_path = self.field_path.strip()
        self.candidate_value_json = _strip_optional(self.candidate_value_json)
        self.reviewed_value_json = self.reviewed_value_json.strip()
        if not self.field_path:
            raise ValueError("field_path is required")
        if not self.reviewed_value_json:
            raise ValueError("reviewed_value_json is required")
        if self.missing_candidate and self.candidate_value_json is not None:
            raise ValueError("missing candidate fields must not include candidate_value_json")
        if self.matched and self.missing_candidate:
            raise ValueError("missing candidate fields cannot be matched")
        return self


class ExtractionNormalizationCase(_StrictExtractionNormalizationModel):
    schema_version: Literal["extraction_normalization_case.v1"] = "extraction_normalization_case.v1"
    layer: ExtractionNormalizationLayer = "review_gate_artifact"
    canonical_status: ExtractionNormalizationCanonicalStatus = "non_canonical"
    example_id: str = Field(..., min_length=1)
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    artifact_id: str = Field(..., min_length=1)
    payload_class: PayloadClass
    reviewed_field_count: int = Field(..., ge=1)
    matched_reviewed_field_count: int = Field(..., ge=0)
    missing_reviewed_field_count: int = Field(..., ge=0)
    extra_candidate_field_count: int = Field(..., ge=0)
    field_exact_match_rate: float = Field(..., ge=0.0, le=1.0)
    field_coverage_rate: float = Field(..., ge=0.0, le=1.0)
    source_trace_coverage_rate: float = Field(..., ge=0.0, le=1.0)
    field_results: list[ExtractionNormalizationFieldResult] = Field(..., min_length=1)
    extra_candidate_field_paths: list[str] = Field(default_factory=list)
    evaluated_at: datetime

    @model_validator(mode="after")
    def normalize_case(self):
        self.example_id = self.example_id.strip()
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.artifact_id = self.artifact_id.strip()
        self.extra_candidate_field_paths = _dedupe_paths(self.extra_candidate_field_paths)
        field_paths = [field.field_path for field in self.field_results]
        if len(field_paths) != len(set(field_paths)):
            raise ValueError("field_results must not contain duplicate field_path values")
        if self.reviewed_field_count != len(self.field_results):
            raise ValueError("reviewed_field_count must match field_results length")
        if self.matched_reviewed_field_count > self.reviewed_field_count:
            raise ValueError("matched_reviewed_field_count cannot exceed reviewed_field_count")
        if self.missing_reviewed_field_count > self.reviewed_field_count:
            raise ValueError("missing_reviewed_field_count cannot exceed reviewed_field_count")
        if self.extra_candidate_field_count != len(self.extra_candidate_field_paths):
            raise ValueError("extra_candidate_field_count must match extra_candidate_field_paths length")
        return self


class ExtractionNormalizationPilotReport(_StrictExtractionNormalizationModel):
    schema_version: Literal["extraction_normalization_pilot_report.v1"] = (
        "extraction_normalization_pilot_report.v1"
    )
    layer: ExtractionNormalizationLayer = "review_gate_artifact"
    canonical_status: ExtractionNormalizationCanonicalStatus = "non_canonical"
    evaluated_at: datetime
    payload_class: PayloadClass
    case_count: int = Field(..., ge=1)
    reviewed_field_count: int = Field(..., ge=1)
    field_exact_match_rate: float = Field(..., ge=0.0, le=1.0)
    field_coverage_rate: float = Field(..., ge=0.0, le=1.0)
    source_trace_coverage_rate: float = Field(..., ge=0.0, le=1.0)
    extra_candidate_field_count: int = Field(..., ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.warnings = [warning.strip() for warning in self.warnings if warning.strip()]
        return self


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _dedupe_paths(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            raise ValueError("field paths must be non-empty")
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
