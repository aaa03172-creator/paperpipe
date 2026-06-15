from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.schemas.ml_lora_experiment_gate import LoRAExperimentDatasetRef, LoRAExperimentGate
from src.schemas.ml_training_examples import PayloadClass


_REQUIRED_SAFETY_METRIC_IDS = frozenset({"source_trace_coverage_rate", "forbidden_inference_rate"})


def build_lora_experiment_gate(
    *,
    experiment_id: str,
    payload_class: PayloadClass,
    base_model_ref: str,
    adapter_artifact_ref: str,
    dataset_ref: LoRAExperimentDatasetRef,
    eval_manifest_ref: str,
    safety_metric_ids: list[str],
    min_reviewed_examples: int = 64,
    created_at: datetime | None = None,
) -> LoRAExperimentGate:
    block_reason_codes = _block_reason_codes(
        payload_class=payload_class,
        dataset_ref=dataset_ref,
        eval_manifest_ref=eval_manifest_ref,
        safety_metric_ids=safety_metric_ids,
        min_reviewed_examples=min_reviewed_examples,
    )
    return LoRAExperimentGate(
        experiment_id=experiment_id,
        payload_class=payload_class,
        base_model_ref=base_model_ref,
        adapter_artifact_ref=adapter_artifact_ref,
        dataset_ref=dataset_ref,
        eval_manifest_ref=eval_manifest_ref,
        safety_metric_ids=safety_metric_ids,
        min_reviewed_examples=min_reviewed_examples,
        runnable=not block_reason_codes,
        block_reason_codes=block_reason_codes,
        created_at=created_at or datetime.now(timezone.utc),
    )


def write_lora_experiment_gate(gate: LoRAExperimentGate, out: Path) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(gate.model_dump_json(indent=2), encoding="utf-8")
    return out


def _block_reason_codes(
    *,
    payload_class: PayloadClass,
    dataset_ref: LoRAExperimentDatasetRef,
    eval_manifest_ref: str,
    safety_metric_ids: list[str],
    min_reviewed_examples: int,
) -> list[str]:
    reasons: list[str] = []
    if payload_class == "external_allowed":
        reasons.append("payload_must_remain_local_or_lab")
    if dataset_ref.reviewed_example_count < min_reviewed_examples:
        reasons.append("insufficient_reviewed_examples")
    if dataset_ref.eval_manifest_ref != eval_manifest_ref:
        reasons.append("dataset_eval_manifest_mismatch")
    if not _REQUIRED_SAFETY_METRIC_IDS.issubset(set(safety_metric_ids)):
        reasons.append("missing_required_safety_metric")
    return reasons
