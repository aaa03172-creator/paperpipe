from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.ml_lora_experiment_gate import LoRAExperimentDatasetRef
from src.schemas.ml_quality_eval import MLQualityEvalManifest, MLQualityMetricSpec
from src.services.ml_lora_experiment_gate import (
    build_lora_experiment_gate,
    write_lora_experiment_gate,
)
from src.services.ml_quality_eval import build_ml_quality_eval_report


def _now() -> datetime:
    return datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)


def _dataset_ref() -> LoRAExperimentDatasetRef:
    return LoRAExperimentDatasetRef(
        dataset_id="reader-extractor-local-001",
        training_examples_ref="runs/run-001/ml_training_examples.jsonl",
        eval_manifest_ref="goldset/manifests/reader_extractor_lora_fixed.json",
        example_count=128,
        reviewed_example_count=96,
    )


def test_lora_experiment_gate_marks_safe_local_plan_runnable() -> None:
    gate = build_lora_experiment_gate(
        experiment_id="reader-extractor-lora-001",
        payload_class="local_only",
        base_model_ref="ollama://qwen3.5:4b",
        adapter_artifact_ref="models/local/reader-extractor-lora-001",
        dataset_ref=_dataset_ref(),
        eval_manifest_ref="goldset/manifests/reader_extractor_lora_fixed.json",
        safety_metric_ids=["source_trace_coverage_rate", "forbidden_inference_rate"],
        created_at=_now(),
    )

    assert gate.schema_version == "lora_experiment_gate.v1"
    assert gate.runnable is True
    assert gate.block_reason_codes == []
    assert gate.canonical_status == "non_canonical"


def test_lora_experiment_gate_blocks_external_payload_and_missing_safety_metric() -> None:
    gate = build_lora_experiment_gate(
        experiment_id="reader-extractor-lora-002",
        payload_class="external_allowed",
        base_model_ref="hf://example/reader",
        adapter_artifact_ref="models/local/reader-extractor-lora-002",
        dataset_ref=_dataset_ref(),
        eval_manifest_ref="goldset/manifests/reader_extractor_lora_fixed.json",
        safety_metric_ids=["source_trace_coverage_rate"],
        created_at=_now(),
    )

    assert gate.runnable is False
    assert gate.block_reason_codes == [
        "payload_must_remain_local_or_lab",
        "missing_required_safety_metric",
    ]


def test_lora_experiment_gate_rejects_nonlocal_adapter_artifact_ref() -> None:
    with pytest.raises(ValidationError):
        build_lora_experiment_gate(
            experiment_id="reader-extractor-lora-003",
            payload_class="local_only",
            base_model_ref="ollama://qwen3.5:4b",
            adapter_artifact_ref="https://example.com/adapter",
            dataset_ref=_dataset_ref(),
            eval_manifest_ref="goldset/manifests/reader_extractor_lora_fixed.json",
            safety_metric_ids=["source_trace_coverage_rate", "forbidden_inference_rate"],
            created_at=_now(),
        )


def test_lora_quality_report_remains_hold_until_candidate_beats_fixed_eval() -> None:
    manifest = MLQualityEvalManifest(
        eval_id="reader_extractor_lora_gate_001",
        task="reader_extractor_lora",
        payload_class="local_only",
        fixed_manifest_ref="goldset/manifests/reader_extractor_lora_fixed.json",
        case_ids=["case-001", "case-002"],
        primary_metric_id="reader_extractor_composite_f1",
        metric_specs=[
            MLQualityMetricSpec(
                metric_id="reader_extractor_composite_f1",
                direction="higher_is_better",
                min_relative_improvement=0.05,
            ),
            MLQualityMetricSpec(
                metric_id="source_trace_coverage_rate",
                direction="higher_is_better",
                max_allowed_regression=0.0,
                hard_fail_on_regression=True,
            ),
        ],
        safety_metric_ids=["source_trace_coverage_rate"],
        created_at=_now(),
    )

    report = build_ml_quality_eval_report(
        manifest,
        baseline_metrics={
            "reader_extractor_composite_f1": 0.8,
            "source_trace_coverage_rate": 1.0,
        },
        candidate_metrics={
            "reader_extractor_composite_f1": 0.81,
            "source_trace_coverage_rate": 1.0,
        },
        baseline_run_ref="reader_extractor_baseline.json",
        candidate_run_ref="reader_extractor_lora_candidate.json",
        generated_at=_now(),
    )

    assert report.promotion_recommendation == "hold"
    assert "insufficient_relative_improvement" in report.reason_codes


def test_lora_experiment_gate_writer_persists_noncanonical_output(tmp_path) -> None:
    gate = build_lora_experiment_gate(
        experiment_id="reader-extractor-lora-004",
        payload_class="local_only",
        base_model_ref="ollama://qwen3.5:4b",
        adapter_artifact_ref="models/local/reader-extractor-lora-004",
        dataset_ref=_dataset_ref(),
        eval_manifest_ref="goldset/manifests/reader_extractor_lora_fixed.json",
        safety_metric_ids=["source_trace_coverage_rate", "forbidden_inference_rate"],
        created_at=_now(),
    )

    out = write_lora_experiment_gate(gate, tmp_path / "gate.json")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["canonical_status"] == "non_canonical"
    assert payload["payload_class"] == "local_only"
