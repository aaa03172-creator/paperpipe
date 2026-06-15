from __future__ import annotations

import json
from datetime import datetime, timezone

from src.schemas.ml_quality_eval import MLQualityEvalManifest, MLQualityMetricSpec
from src.schemas.ml_training_examples import EvidenceRerankExample, TrainingSourceSpan
from src.services.ml_evidence_reranking import (
    build_evidence_rerank_candidate_pool,
    build_evidence_rerank_pilot_report,
    reranked_candidates,
    write_evidence_rerank_candidate_pool,
    write_evidence_rerank_pilot_report,
)
from src.services.ml_quality_eval import build_ml_quality_eval_report


def _now() -> datetime:
    return datetime(2026, 6, 14, 14, 0, tzinfo=timezone.utc)


def _span(span_id: str, page_index: int = 0) -> TrainingSourceSpan:
    return TrainingSourceSpan(
        span_id=span_id,
        source_ref=f"document_artifact.json#/pages/{page_index}/blocks/0/lines/0",
        page_index=page_index,
        block_id=f"chunk-{span_id}",
        char_start=0,
        char_end=100,
    )


def _example() -> EvidenceRerankExample:
    return EvidenceRerankExample(
        example_id="rerank-example-001",
        paper_id="paper-001",
        run_id="run-001",
        claim_id="claim-001",
        claim_text="Treatment was associated with improved survival in the cohort.",
        payload_class="local_only",
        positive_span_ids=["positive"],
        hard_negative_span_ids=["hard-negative"],
        candidate_span_pool_ref="candidate_spans.json",
        ranking_source="hybrid",
        source_spans=[_span("hard-negative"), _span("weak"), _span("positive")],
        adjudication_status="reviewed",
        created_at=_now(),
    )


def test_evidence_rerank_candidate_pool_scores_and_reranks_positive_span() -> None:
    pool = build_evidence_rerank_candidate_pool(
        _example(),
        candidate_text_by_span_id={
            "hard-negative": "The paper describes treatment allocation and baseline covariates.",
            "weak": "The cohort was followed for safety events.",
            "positive": "Treatment was associated with improved survival in the cohort after adjustment.",
        },
        created_at=_now(),
    )

    assert pool.schema_version == "evidence_rerank_candidate_pool.v1"
    assert pool.candidates[0].span_id == "hard-negative"
    assert pool.candidates[0].is_hard_negative is True
    assert reranked_candidates(pool)[0].span_id == "positive"
    assert reranked_candidates(pool)[0].is_positive is True


def test_evidence_rerank_pilot_report_feeds_quality_eval_gate() -> None:
    example = _example()
    pool = build_evidence_rerank_candidate_pool(
        example,
        candidate_text_by_span_id={
            "hard-negative": "The paper describes treatment allocation and baseline covariates.",
            "weak": "The cohort was followed for safety events.",
            "positive": "Treatment was associated with improved survival in the cohort after adjustment.",
        },
        created_at=_now(),
    )
    pilot_report = build_evidence_rerank_pilot_report([pool], evaluated_at=_now())

    assert pilot_report.schema_version == "evidence_rerank_pilot_report.v1"
    assert pilot_report.original_top_1_hit_rate == 0.0
    assert pilot_report.reranked_top_1_hit_rate == 1.0
    assert pilot_report.hard_negative_top_1_rate == 0.0

    manifest = MLQualityEvalManifest(
        eval_id="evidence_rerank_gate_001",
        task="evidence_reranking",
        payload_class="local_only",
        fixed_manifest_ref="goldset/manifests/evidence_rerank_fixed.json",
        case_ids=[example.example_id],
        primary_metric_id="evidence_span_recall",
        metric_specs=[
            MLQualityMetricSpec(
                metric_id="evidence_span_recall",
                direction="higher_is_better",
                min_relative_improvement=0.2,
            ),
            MLQualityMetricSpec(
                metric_id="hard_negative_top_1_rate",
                direction="lower_is_better",
                max_allowed_regression=0.0,
                hard_fail_on_regression=True,
            ),
        ],
        safety_metric_ids=["hard_negative_top_1_rate"],
        created_at=_now(),
    )

    gate_report = build_ml_quality_eval_report(
        manifest,
        baseline_metrics={
            "evidence_span_recall": pilot_report.original_top_1_hit_rate,
            "hard_negative_top_1_rate": 1.0,
        },
        candidate_metrics={
            "evidence_span_recall": pilot_report.reranked_top_1_hit_rate,
            "hard_negative_top_1_rate": pilot_report.hard_negative_top_1_rate,
        },
        baseline_run_ref="evidence_rerank_baseline.json",
        candidate_run_ref="evidence_rerank_pilot_report.json",
        generated_at=_now(),
    )

    assert gate_report.promotion_recommendation == "promote"


def test_evidence_rerank_sidecar_writers_persist_noncanonical_outputs(tmp_path) -> None:
    pool = build_evidence_rerank_candidate_pool(
        _example(),
        candidate_text_by_span_id={
            "hard-negative": "The paper describes treatment allocation and baseline covariates.",
            "weak": "The cohort was followed for safety events.",
            "positive": "Treatment was associated with improved survival in the cohort after adjustment.",
        },
        created_at=_now(),
    )
    report = build_evidence_rerank_pilot_report([pool], evaluated_at=_now())

    pool_path = write_evidence_rerank_candidate_pool(pool, tmp_path / "pool.json")
    report_path = write_evidence_rerank_pilot_report(report, tmp_path / "report.json")

    pool_payload = json.loads(pool_path.read_text(encoding="utf-8"))
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert pool_payload["canonical_status"] == "non_canonical"
    assert report_payload["canonical_status"] == "non_canonical"
    assert report_payload["payload_class"] == "local_only"
