from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.ml_training_examples import CorrectionIssueLabel, PayloadClass


CorrectionCalibrationLayer = Literal["review_gate_artifact"]
CorrectionCalibrationCanonicalStatus = Literal["non_canonical"]


class _StrictCorrectionCalibrationModel(BaseModel):
    model_config = {"extra": "forbid"}


class CorrectionCalibrationCase(_StrictCorrectionCalibrationModel):
    schema_version: Literal["correction_calibration_case.v1"] = "correction_calibration_case.v1"
    layer: CorrectionCalibrationLayer = "review_gate_artifact"
    canonical_status: CorrectionCalibrationCanonicalStatus = "non_canonical"
    example_id: str = Field(..., min_length=1)
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    claim_id: str = Field(..., min_length=1)
    payload_class: PayloadClass
    expected_label: CorrectionIssueLabel
    predicted_label: CorrectionIssueLabel
    confidence: float = Field(..., ge=0.0, le=1.0)
    label_matched: bool
    minimal_correction_similarity: float = Field(..., ge=0.0, le=1.0)
    must_preserve_term_recall: float = Field(..., ge=0.0, le=1.0)
    forbidden_inference_hit: bool
    confidence_abs_error: float = Field(..., ge=0.0, le=1.0)
    source_trace_coverage_rate: float = Field(..., ge=0.0, le=1.0)
    evaluated_at: datetime

    @model_validator(mode="after")
    def normalize_case(self):
        self.example_id = self.example_id.strip()
        self.paper_id = self.paper_id.strip()
        self.run_id = self.run_id.strip()
        self.claim_id = self.claim_id.strip()
        return self


class CorrectionCalibrationPilotReport(_StrictCorrectionCalibrationModel):
    schema_version: Literal["correction_calibration_pilot_report.v1"] = (
        "correction_calibration_pilot_report.v1"
    )
    layer: CorrectionCalibrationLayer = "review_gate_artifact"
    canonical_status: CorrectionCalibrationCanonicalStatus = "non_canonical"
    evaluated_at: datetime
    payload_class: PayloadClass
    case_count: int = Field(..., ge=1)
    label_accuracy: float = Field(..., ge=0.0, le=1.0)
    mean_minimal_correction_similarity: float = Field(..., ge=0.0, le=1.0)
    mean_must_preserve_term_recall: float = Field(..., ge=0.0, le=1.0)
    forbidden_inference_rate: float = Field(..., ge=0.0, le=1.0)
    mean_confidence_abs_error: float = Field(..., ge=0.0, le=1.0)
    source_trace_coverage_rate: float = Field(..., ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.warnings = [warning.strip() for warning in self.warnings if warning.strip()]
        return self
