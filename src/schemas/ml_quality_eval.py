from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.schemas.ml_training_examples import PayloadClass


MLQualityEvalTask = Literal[
    "evidence_reranking",
    "extraction_normalization",
    "correction_calibration",
    "reader_extractor_lora",
]
MLQualityEvalLayer = Literal["review_gate_artifact"]
MLQualityCanonicalStatus = Literal["non_canonical"]
MLQualityMetricDirection = Literal["higher_is_better", "lower_is_better"]
MLQualityPromotionRecommendation = Literal["promote", "hold", "reject"]


class _StrictMLQualityEvalModel(BaseModel):
    model_config = {"extra": "forbid"}


class MLQualityMetricSpec(_StrictMLQualityEvalModel):
    metric_id: str = Field(..., min_length=1)
    direction: MLQualityMetricDirection
    min_relative_improvement: float = Field(default=0.0, ge=0.0)
    max_allowed_regression: float = Field(default=0.0, ge=0.0)
    hard_fail_on_regression: bool = False

    @model_validator(mode="after")
    def normalize_metric_spec(self):
        self.metric_id = self.metric_id.strip()
        if not self.metric_id:
            raise ValueError("metric_id is required")
        return self


class MLQualityEvalManifest(_StrictMLQualityEvalModel):
    schema_version: Literal["ml_quality_eval_manifest.v1"] = "ml_quality_eval_manifest.v1"
    layer: MLQualityEvalLayer = "review_gate_artifact"
    canonical_status: MLQualityCanonicalStatus = "non_canonical"
    eval_id: str = Field(..., min_length=1)
    task: MLQualityEvalTask
    payload_class: PayloadClass = "local_only"
    fixed_manifest_ref: str = Field(..., min_length=1)
    case_ids: list[str] = Field(..., min_length=1)
    primary_metric_id: str = Field(..., min_length=1)
    metric_specs: list[MLQualityMetricSpec] = Field(..., min_length=1)
    safety_metric_ids: list[str] = Field(default_factory=list)
    created_at: datetime

    @field_validator("case_ids", "safety_metric_ids", mode="before")
    @classmethod
    def reject_none_lists(cls, value):
        if value is None:
            return []
        return value

    @model_validator(mode="after")
    def normalize_manifest(self):
        self.eval_id = self.eval_id.strip()
        self.fixed_manifest_ref = self.fixed_manifest_ref.strip()
        self.primary_metric_id = self.primary_metric_id.strip()
        self.case_ids = _dedupe_required_strings(self.case_ids, field_name="case_ids")
        self.safety_metric_ids = _dedupe_required_strings(self.safety_metric_ids, field_name="safety_metric_ids")
        metric_ids = [spec.metric_id for spec in self.metric_specs]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("metric_specs must not contain duplicate metric_id values")
        if self.primary_metric_id not in metric_ids:
            raise ValueError("primary_metric_id must be declared in metric_specs")
        missing_safety_ids = [metric_id for metric_id in self.safety_metric_ids if metric_id not in metric_ids]
        if missing_safety_ids:
            raise ValueError("safety_metric_ids must be declared in metric_specs")
        if not self.eval_id:
            raise ValueError("eval_id is required")
        if not self.fixed_manifest_ref:
            raise ValueError("fixed_manifest_ref is required")
        return self


class MLQualityMetricResult(_StrictMLQualityEvalModel):
    metric_id: str = Field(..., min_length=1)
    baseline_value: float
    candidate_value: float
    absolute_delta: float
    relative_delta: float | None = None
    passed: bool
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_metric_result(self):
        self.metric_id = self.metric_id.strip()
        self.reason_codes = _dedupe_required_strings(self.reason_codes, field_name="reason_codes")
        return self


class MLQualityEvalReport(_StrictMLQualityEvalModel):
    schema_version: Literal["ml_quality_eval_report.v1"] = "ml_quality_eval_report.v1"
    layer: MLQualityEvalLayer = "review_gate_artifact"
    canonical_status: MLQualityCanonicalStatus = "non_canonical"
    eval_id: str = Field(..., min_length=1)
    task: MLQualityEvalTask
    payload_class: PayloadClass
    fixed_manifest_ref: str = Field(..., min_length=1)
    baseline_run_ref: str = Field(..., min_length=1)
    candidate_run_ref: str = Field(..., min_length=1)
    case_count: int = Field(..., ge=1)
    metric_results: list[MLQualityMetricResult] = Field(..., min_length=1)
    primary_metric_id: str = Field(..., min_length=1)
    promotion_recommendation: MLQualityPromotionRecommendation
    reason_codes: list[str] = Field(default_factory=list)
    generated_at: datetime

    @model_validator(mode="after")
    def normalize_report(self):
        self.eval_id = self.eval_id.strip()
        self.fixed_manifest_ref = self.fixed_manifest_ref.strip()
        self.baseline_run_ref = self.baseline_run_ref.strip()
        self.candidate_run_ref = self.candidate_run_ref.strip()
        self.primary_metric_id = self.primary_metric_id.strip()
        self.reason_codes = _dedupe_required_strings(self.reason_codes, field_name="reason_codes")
        metric_ids = [result.metric_id for result in self.metric_results]
        if self.primary_metric_id not in metric_ids:
            raise ValueError("primary_metric_id must be present in metric_results")
        return self


def _dedupe_required_strings(values: list[str], *, field_name: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value or "").strip()
        if not value:
            raise ValueError(f"{field_name} entries must be non-empty")
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
