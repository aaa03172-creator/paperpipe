from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.ml_quality_eval import MLQualityEvalManifest, MLQualityMetricSpec
from src.services.ml_quality_eval import build_ml_quality_eval_report, write_ml_quality_eval_report


def _now() -> datetime:
    return datetime(2026, 6, 14, 13, 0, tzinfo=timezone.utc)


def _manifest() -> MLQualityEvalManifest:
    return MLQualityEvalManifest(
        eval_id="ml_eval_evidence_rerank_v1",
        task="evidence_reranking",
        payload_class="local_only",
        fixed_manifest_ref="goldset/manifests/evidence_rerank_fixed.json",
        case_ids=["case-001", "case-002"],
        primary_metric_id="evidence_span_recall",
        metric_specs=[
            MLQualityMetricSpec(
                metric_id="evidence_span_recall",
                direction="higher_is_better",
                min_relative_improvement=0.2,
            ),
            MLQualityMetricSpec(
                metric_id="unsupported_claim_rate",
                direction="lower_is_better",
                max_allowed_regression=0.0,
                hard_fail_on_regression=True,
            ),
        ],
        safety_metric_ids=["unsupported_claim_rate"],
        created_at=_now(),
    )


def test_ml_quality_eval_manifest_validates_fixed_baseline_contract() -> None:
    manifest = _manifest()

    assert manifest.schema_version == "ml_quality_eval_manifest.v1"
    assert manifest.layer == "review_gate_artifact"
    assert manifest.canonical_status == "non_canonical"
    assert manifest.primary_metric_id == "evidence_span_recall"
    assert manifest.safety_metric_ids == ["unsupported_claim_rate"]


def test_ml_quality_eval_manifest_rejects_unknown_primary_metric() -> None:
    with pytest.raises(ValidationError):
        MLQualityEvalManifest(
            eval_id="ml_eval_bad",
            task="evidence_reranking",
            fixed_manifest_ref="goldset/manifests/evidence_rerank_fixed.json",
            case_ids=["case-001"],
            primary_metric_id="missing_metric",
            metric_specs=[
                MLQualityMetricSpec(metric_id="evidence_span_recall", direction="higher_is_better")
            ],
            created_at=_now(),
        )


def test_ml_quality_eval_report_promotes_only_when_primary_and_safety_gates_pass() -> None:
    report = build_ml_quality_eval_report(
        _manifest(),
        baseline_metrics={
            "evidence_span_recall": 0.5,
            "unsupported_claim_rate": 0.1,
        },
        candidate_metrics={
            "evidence_span_recall": 0.62,
            "unsupported_claim_rate": 0.08,
        },
        baseline_run_ref="eval/baseline.json",
        candidate_run_ref="eval/candidate.json",
        generated_at=_now(),
    )

    assert report.schema_version == "ml_quality_eval_report.v1"
    assert report.promotion_recommendation == "promote"
    assert report.case_count == 2
    assert report.reason_codes == []
    primary = next(result for result in report.metric_results if result.metric_id == "evidence_span_recall")
    assert primary.relative_delta == 0.24
    assert primary.passed is True


def test_ml_quality_eval_report_holds_when_primary_improvement_is_insufficient() -> None:
    report = build_ml_quality_eval_report(
        _manifest(),
        baseline_metrics={
            "evidence_span_recall": 0.5,
            "unsupported_claim_rate": 0.1,
        },
        candidate_metrics={
            "evidence_span_recall": 0.55,
            "unsupported_claim_rate": 0.09,
        },
        baseline_run_ref="eval/baseline.json",
        candidate_run_ref="eval/candidate.json",
        generated_at=_now(),
    )

    assert report.promotion_recommendation == "hold"
    assert "insufficient_relative_improvement" in report.reason_codes


def test_ml_quality_eval_report_rejects_safety_metric_regression() -> None:
    report = build_ml_quality_eval_report(
        _manifest(),
        baseline_metrics={
            "evidence_span_recall": 0.5,
            "unsupported_claim_rate": 0.1,
        },
        candidate_metrics={
            "evidence_span_recall": 0.7,
            "unsupported_claim_rate": 0.12,
        },
        baseline_run_ref="eval/baseline.json",
        candidate_run_ref="eval/candidate.json",
        generated_at=_now(),
    )

    assert report.promotion_recommendation == "reject"
    assert "hard_regression" in report.reason_codes


def test_ml_quality_eval_report_writer_persists_noncanonical_gate_artifact(tmp_path) -> None:
    report = build_ml_quality_eval_report(
        _manifest(),
        baseline_metrics={
            "evidence_span_recall": 0.5,
            "unsupported_claim_rate": 0.1,
        },
        candidate_metrics={
            "evidence_span_recall": 0.62,
            "unsupported_claim_rate": 0.08,
        },
        baseline_run_ref="eval/baseline.json",
        candidate_run_ref="eval/candidate.json",
        generated_at=_now(),
    )

    out = write_ml_quality_eval_report(report, tmp_path / "ml_quality_eval_report.json")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "ml_quality_eval_report.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["payload_class"] == "local_only"
    assert payload["promotion_recommendation"] == "promote"
