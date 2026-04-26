from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.check_public_data_bootstrap_status import (
    build_public_data_bootstrap_summary,
    run_public_data_bootstrap_status,
)


def test_build_public_data_bootstrap_summary_uses_repo_grounded_assets() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    summary = build_public_data_bootstrap_summary(
        bc5cdr_manifest_path=repo_root / "goldset" / "manifests" / "bc5cdr_prediction_repo_grounded_pilot_20260413.json",
        biored_manifest_path=repo_root / "goldset" / "manifests" / "biored_prediction_repo_grounded_pilot_20260409.json",
        pubtator_manifest_path=repo_root / "goldset" / "manifests" / "pubtator_silver_repo_grounded_pilot_20260409.json",
        bioasq_questions_path=repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "questions"
        / "repo_grounded_questions.json",
        bioasq_run_metrics_path=repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "run_dir"
        / "metrics.json",
        bioasq_screening_queue_path=repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "run_dir"
        / "screening_queue.jsonl",
        run_id="public_data_repo_check",
    )

    assert summary["decision"]["repo_grounded_replay_ready"] is True
    assert summary["decision"]["runtime_promotion_ready"] is False
    assert summary["lanes"]["bc5cdr_prediction"]["document_count"] == 2
    assert summary["lanes"]["bc5cdr_prediction"]["source_shape_counts"] == {"pages": 1, "sections": 1}
    assert summary["lanes"]["biored_prediction"]["document_count"] == 2
    assert summary["lanes"]["biored_prediction"]["supports_relation_novelty"] is True
    assert summary["lanes"]["pubtator_silver"]["source_shape_counts"] == {
        "bioc_collection": 1,
        "direct_document": 1,
    }
    assert summary["lanes"]["bioasq_eval"]["question_count"] == 2
    assert summary["lanes"]["bioasq_eval"]["screening_row_count"] == 3
    assert summary["lanes"]["bioasq_eval"]["question_identifier_alias_fixture_count"] == 1
    assert summary["lanes"]["bioasq_eval"]["row_identifier_alias_fixture_count"] == 1
    assert "project_context_relevance" in summary["internal_data_still_required_for"]


def test_run_public_data_bootstrap_status_writes_summary(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    run_root = run_public_data_bootstrap_status(
        bc5cdr_manifest_path=repo_root / "goldset" / "manifests" / "bc5cdr_prediction_repo_grounded_pilot_20260413.json",
        biored_manifest_path=repo_root / "goldset" / "manifests" / "biored_prediction_repo_grounded_pilot_20260409.json",
        pubtator_manifest_path=repo_root / "goldset" / "manifests" / "pubtator_silver_repo_grounded_pilot_20260409.json",
        bioasq_questions_path=repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "questions"
        / "repo_grounded_questions.json",
        bioasq_run_metrics_path=repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "run_dir"
        / "metrics.json",
        bioasq_screening_queue_path=repo_root
        / "goldset"
        / "bioasq_eval"
        / "repo_grounded_pilot_20260410"
        / "run_dir"
        / "screening_queue.jsonl",
        out_dir=tmp_path / "out",
        run_id="public_data_repo_run",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "public_data_repo_run"
    assert payload["decision"]["sidecar_bootstrap_ready"] is True
    assert payload["decision"]["blockers"] == []
