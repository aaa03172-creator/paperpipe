from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.ml_training_examples import PayloadClass


LoRAExperimentLayer = Literal["review_gate_artifact"]
LoRAExperimentCanonicalStatus = Literal["non_canonical"]
LoRAExperimentTask = Literal["reader_extractor_lora"]


class _StrictLoRAExperimentModel(BaseModel):
    model_config = {"extra": "forbid"}


class LoRAExperimentDatasetRef(_StrictLoRAExperimentModel):
    dataset_id: str = Field(..., min_length=1)
    training_examples_ref: str = Field(..., min_length=1)
    eval_manifest_ref: str = Field(..., min_length=1)
    example_count: int = Field(..., ge=1)
    reviewed_example_count: int = Field(..., ge=0)

    @model_validator(mode="after")
    def normalize_dataset_ref(self):
        self.dataset_id = self.dataset_id.strip()
        self.training_examples_ref = _artifact_relative_ref(self.training_examples_ref)
        self.eval_manifest_ref = _artifact_relative_ref(self.eval_manifest_ref)
        if self.reviewed_example_count > self.example_count:
            raise ValueError("reviewed_example_count cannot exceed example_count")
        return self


class LoRAExperimentGate(_StrictLoRAExperimentModel):
    schema_version: Literal["lora_experiment_gate.v1"] = "lora_experiment_gate.v1"
    layer: LoRAExperimentLayer = "review_gate_artifact"
    canonical_status: LoRAExperimentCanonicalStatus = "non_canonical"
    task: LoRAExperimentTask = "reader_extractor_lora"
    experiment_id: str = Field(..., min_length=1)
    payload_class: PayloadClass
    base_model_ref: str = Field(..., min_length=1)
    adapter_artifact_ref: str = Field(..., min_length=1)
    dataset_ref: LoRAExperimentDatasetRef
    eval_manifest_ref: str = Field(..., min_length=1)
    safety_metric_ids: list[str] = Field(default_factory=list)
    min_reviewed_examples: int = Field(default=64, ge=1)
    runnable: bool
    block_reason_codes: list[str] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def normalize_gate(self):
        self.experiment_id = self.experiment_id.strip()
        self.base_model_ref = self.base_model_ref.strip()
        self.adapter_artifact_ref = _local_artifact_ref(self.adapter_artifact_ref)
        self.eval_manifest_ref = _artifact_relative_ref(self.eval_manifest_ref)
        self.safety_metric_ids = _dedupe_required_strings(self.safety_metric_ids)
        self.block_reason_codes = _dedupe_required_strings(self.block_reason_codes)
        return self


def _artifact_relative_ref(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("artifact ref is required")
    if stripped.startswith("/") or ".." in stripped.split("/"):
        raise ValueError("artifact ref must be artifact-relative")
    return stripped


def _local_artifact_ref(value: str) -> str:
    stripped = _artifact_relative_ref(value)
    if "://" in stripped:
        raise ValueError("adapter_artifact_ref must be a local artifact ref")
    return stripped


def _dedupe_required_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            raise ValueError("entries must be non-empty")
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
