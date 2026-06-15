from __future__ import annotations

import json
from datetime import datetime, timezone

from src.schemas.ml_quality_eval import MLQualityEvalManifest, MLQualityMetricSpec
from src.schemas.ml_training_examples import TrainingExample, TrainingInputRef, TrainingSourceSpan
from src.services.ml_extraction_normalization import (
    build_extraction_normalization_case,
    build_extraction_normalization_pilot_report,
    write_extraction_normalization_case,
    write_extraction_normalization_pilot_report,
)
from src.services.ml_quality_eval import build_ml_quality_eval_report


def _now() -> datetime:
    return datetime(2026, 6, 14, 15, 0, tzinfo=timezone.utc)


def _span() -> TrainingSourceSpan:
    return TrainingSourceSpan(
        span_id="span-001",
        source_ref="document_artifact.json#/pages/0/blocks/0/lines/0",
        page_index=0,
        block_id="abstract",
        char_start=10,
        char_end=80,
    )


def _example() -> TrainingExample:
    return TrainingExample(
        example_id="extraction-example-001",
        paper_id="paper-001",
        run_id="run-001",
        artifact_id="artifact-001",
        task_type="extraction",
        payload_class="local_only",
        input_ref=TrainingInputRef(
            artifact_path="runs/run-001/extraction_candidate.json",
            artifact_kind="extraction_candidate",
        ),
        source_spans=[_span()],
        candidate_output={
            "population": {"condition": "MCI"},
            "intervention": "ketone ester",
            "outcome": {"primary": "memory score"},
        },
        reviewed_output={
            "population": {"condition": "mild cognitive impairment"},
            "intervention": "ketone ester",
            "outcome": {"primary": "memory score", "timepoint": "12 weeks"},
        },
        review_status="reviewed",
        failure_taxonomy=["normalization_mismatch", "missing_timepoint"],
        created_at=_now(),
    )


def test_extraction_normalization_case_compares_reviewed_fields() -> None:
    case = build_extraction_normalization_case(_example(), evaluated_at=_now())

    assert case.schema_version == "extraction_normalization_case.v1"
    assert case.example_id == "extraction-example-001"
    assert case.reviewed_field_count == 4
    assert case.matched_reviewed_field_count == 2
    assert case.missing_reviewed_field_count == 1
    assert case.extra_candidate_field_count == 0
    assert case.field_exact_match_rate == 0.5
    assert case.field_coverage_rate == 0.75
    assert case.source_trace_coverage_rate == 1.0
    assert [field.field_path for field in case.field_results] == [
        "intervention",
        "outcome.primary",
        "outcome.timepoint",
        "population.condition",
    ]


def test_extraction_normalization_case_allows_empty_candidate_output() -> None:
    example = _example().model_copy(update={"candidate_output": {}})

    case = build_extraction_normalization_case(example, evaluated_at=_now())

    assert case.reviewed_field_count == 4
    assert case.matched_reviewed_field_count == 0
    assert case.missing_reviewed_field_count == 4
    assert case.field_exact_match_rate == 0.0
    assert case.field_coverage_rate == 0.0


def test_extraction_normalization_pilot_report_feeds_quality_gate() -> None:
    case = build_extraction_normalization_case(_example(), evaluated_at=_now())
    pilot_report = build_extraction_normalization_pilot_report([case], evaluated_at=_now())

    assert pilot_report.schema_version == "extraction_normalization_pilot_report.v1"
    assert pilot_report.field_exact_match_rate == 0.5
    assert pilot_report.field_coverage_rate == 0.75
    assert pilot_report.source_trace_coverage_rate == 1.0

    manifest = MLQualityEvalManifest(
        eval_id="extraction_normalization_gate_001",
        task="extraction_normalization",
        payload_class="local_only",
        fixed_manifest_ref="goldset/manifests/extraction_normalization_fixed.json",
        case_ids=[case.example_id],
        primary_metric_id="field_exact_match_rate",
        metric_specs=[
            MLQualityMetricSpec(
                metric_id="field_exact_match_rate",
                direction="higher_is_better",
                min_relative_improvement=0.2,
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

    gate_report = build_ml_quality_eval_report(
        manifest,
        baseline_metrics={
            "field_exact_match_rate": 0.25,
            "source_trace_coverage_rate": 1.0,
        },
        candidate_metrics={
            "field_exact_match_rate": pilot_report.field_exact_match_rate,
            "source_trace_coverage_rate": pilot_report.source_trace_coverage_rate,
        },
        baseline_run_ref="extraction_normalization_baseline.json",
        candidate_run_ref="extraction_normalization_pilot_report.json",
        generated_at=_now(),
    )

    assert gate_report.promotion_recommendation == "promote"


def test_extraction_normalization_sidecar_writers_persist_noncanonical_outputs(tmp_path) -> None:
    case = build_extraction_normalization_case(_example(), evaluated_at=_now())
    report = build_extraction_normalization_pilot_report([case], evaluated_at=_now())

    case_path = write_extraction_normalization_case(case, tmp_path / "case.json")
    report_path = write_extraction_normalization_pilot_report(report, tmp_path / "report.json")

    case_payload = json.loads(case_path.read_text(encoding="utf-8"))
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert case_payload["canonical_status"] == "non_canonical"
    assert report_payload["canonical_status"] == "non_canonical"
    assert report_payload["payload_class"] == "local_only"
