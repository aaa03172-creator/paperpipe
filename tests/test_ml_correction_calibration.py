from __future__ import annotations

import json
from datetime import datetime, timezone

from src.schemas.ml_quality_eval import MLQualityEvalManifest, MLQualityMetricSpec
from src.schemas.ml_training_examples import CorrectionReviewExample, TrainingSourceSpan
from src.services.ml_correction_calibration import (
    build_correction_calibration_case,
    build_correction_calibration_pilot_report,
    write_correction_calibration_case,
    write_correction_calibration_pilot_report,
)
from src.services.ml_quality_eval import build_ml_quality_eval_report


def _now() -> datetime:
    return datetime(2026, 6, 14, 16, 0, tzinfo=timezone.utc)


def _span() -> TrainingSourceSpan:
    return TrainingSourceSpan(
        span_id="span-001",
        source_ref="document_artifact.json#/pages/0/blocks/0/lines/0",
        page_index=0,
        block_id="results",
        char_start=10,
        char_end=120,
    )


def _example() -> CorrectionReviewExample:
    return CorrectionReviewExample(
        example_id="correction-example-001",
        paper_id="paper-001",
        run_id="run-001",
        claim_id="claim-001",
        claim_text="Treatment improves survival.",
        evidence_text_ref="document_artifact.json#/pages/0/blocks/0/lines/0",
        payload_class="local_only",
        observed_issue="overclaim",
        expected_label="overclaim",
        minimal_correction="Treatment was associated with improved survival in this cohort.",
        must_preserve_terms=["survival", "cohort"],
        must_not_infer=["causal effect", "unreported subgroup"],
        source_spans=[_span()],
        review_status="accepted",
        created_at=_now(),
    )


def test_correction_calibration_case_scores_label_correction_and_safety() -> None:
    case = build_correction_calibration_case(
        _example(),
        predicted_label="overclaim",
        proposed_correction="Treatment was associated with improved survival in this cohort.",
        confidence=0.8,
        evaluated_at=_now(),
    )

    assert case.schema_version == "correction_calibration_case.v1"
    assert case.label_matched is True
    assert case.minimal_correction_similarity == 1.0
    assert case.must_preserve_term_recall == 1.0
    assert case.forbidden_inference_hit is False
    assert case.confidence_abs_error == 0.2


def test_correction_calibration_pilot_report_feeds_quality_gate() -> None:
    safe_case = build_correction_calibration_case(
        _example(),
        predicted_label="overclaim",
        proposed_correction="Treatment was associated with improved survival in this cohort.",
        confidence=0.8,
        evaluated_at=_now(),
    )
    unsafe_case = build_correction_calibration_case(
        _example().model_copy(update={"example_id": "correction-example-002"}),
        predicted_label="unsupported",
        proposed_correction="Treatment caused a causal effect in an unreported subgroup.",
        confidence=0.9,
        evaluated_at=_now(),
    )
    pilot_report = build_correction_calibration_pilot_report([safe_case, unsafe_case], evaluated_at=_now())

    assert pilot_report.schema_version == "correction_calibration_pilot_report.v1"
    assert pilot_report.label_accuracy == 0.5
    assert pilot_report.forbidden_inference_rate == 0.5
    assert pilot_report.mean_confidence_abs_error == 0.55

    manifest = MLQualityEvalManifest(
        eval_id="correction_calibration_gate_001",
        task="correction_calibration",
        payload_class="local_only",
        fixed_manifest_ref="goldset/manifests/correction_calibration_fixed.json",
        case_ids=[safe_case.example_id, unsafe_case.example_id],
        primary_metric_id="label_accuracy",
        metric_specs=[
            MLQualityMetricSpec(
                metric_id="label_accuracy",
                direction="higher_is_better",
                min_relative_improvement=0.2,
            ),
            MLQualityMetricSpec(
                metric_id="forbidden_inference_rate",
                direction="lower_is_better",
                max_allowed_regression=0.0,
                hard_fail_on_regression=True,
            ),
        ],
        safety_metric_ids=["forbidden_inference_rate"],
        created_at=_now(),
    )

    gate_report = build_ml_quality_eval_report(
        manifest,
        baseline_metrics={
            "label_accuracy": 0.25,
            "forbidden_inference_rate": 0.75,
        },
        candidate_metrics={
            "label_accuracy": pilot_report.label_accuracy,
            "forbidden_inference_rate": pilot_report.forbidden_inference_rate,
        },
        baseline_run_ref="correction_calibration_baseline.json",
        candidate_run_ref="correction_calibration_pilot_report.json",
        generated_at=_now(),
    )

    assert gate_report.promotion_recommendation == "promote"


def test_correction_calibration_sidecar_writers_persist_noncanonical_outputs(tmp_path) -> None:
    case = build_correction_calibration_case(
        _example(),
        predicted_label="overclaim",
        proposed_correction="Treatment was associated with improved survival in this cohort.",
        confidence=0.8,
        evaluated_at=_now(),
    )
    report = build_correction_calibration_pilot_report([case], evaluated_at=_now())

    case_path = write_correction_calibration_case(case, tmp_path / "case.json")
    report_path = write_correction_calibration_pilot_report(report, tmp_path / "report.json")

    case_payload = json.loads(case_path.read_text(encoding="utf-8"))
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert case_payload["canonical_status"] == "non_canonical"
    assert report_payload["canonical_status"] == "non_canonical"
    assert report_payload["payload_class"] == "local_only"
