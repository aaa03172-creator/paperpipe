from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.check_specialty_runtime_promotion_gate import build_promotion_gate_summary, run_promotion_gate


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_promotion_gate_summary_reports_runtime_blockers() -> None:
    summary = build_promotion_gate_summary(
        sidecar_metrics={
            "run_id": "sidecar_ok",
            "document_count": 16,
            "comparison": {"decision": {"passed": True}},
        },
        runtime_shadow_summary={
            "run_id": "shadow_none",
            "document_count": 16,
            "documents_with_shadow_comparable_runtime_artifact": 0,
        },
        materialized_shadow_summary={
            "run_id": "materialized_none",
            "document_count": 16,
            "eligible_document_count": 1,
            "compare_ready_count": 0,
            "status_counts": {"pairing_mismatch": 0, "prediction_schema_invalid": 0},
            "schema_invalid_reason_counts": {},
            "runtime_feature_enabled": False,
            "provider_available": True,
        },
        semantic_shadow_summary=None,
        semantic_shadow_compare_metrics=None,
        run_id="gate_blocked",
    )

    assert summary["decision"]["promotion_ready"] is False
    assert summary["materialized_shadow"]["prediction_schema_invalid_count"] == 0
    assert summary["materialized_shadow"]["schema_invalid_reason_counts"] == {}
    assert summary["materialized_shadow"]["pairing_mismatch_count"] == 0
    assert summary["semantic_shadow"]["two_step_rfc_viable"] is False
    assert summary["decision"]["blockers"] == [
        "no_persisted_runtime_specialty_artifact",
        "no_materialized_specialty_shadow_artifact",
        "runtime_specialty_feature_disabled",
    ]


def test_build_promotion_gate_summary_surfaces_schema_invalid_blocker() -> None:
    summary = build_promotion_gate_summary(
        sidecar_metrics={
            "run_id": "sidecar_ok",
            "document_count": 16,
            "comparison": {"decision": {"passed": True}},
        },
        runtime_shadow_summary={
            "run_id": "shadow_none",
            "document_count": 16,
            "documents_with_shadow_comparable_runtime_artifact": 0,
        },
        materialized_shadow_summary={
            "run_id": "materialized_schema_invalid",
            "document_count": 16,
            "eligible_document_count": 1,
            "compare_ready_count": 0,
            "status_counts": {"pairing_mismatch": 0, "prediction_schema_invalid": 1},
            "schema_invalid_reason_counts": {"invalid_intervention_category": 1},
            "runtime_feature_enabled": False,
            "provider_available": True,
        },
        semantic_shadow_summary=None,
        semantic_shadow_compare_metrics=None,
        run_id="gate_schema_invalid",
    )

    assert summary["decision"]["promotion_ready"] is False
    assert summary["materialized_shadow"]["prediction_schema_invalid_count"] == 1
    assert summary["materialized_shadow"]["schema_invalid_reason_counts"] == {
        "invalid_intervention_category": 1,
    }
    assert "materialized_shadow_schema_invalid" in summary["decision"]["blockers"]


def test_build_promotion_gate_summary_surfaces_semantic_shadow_viability_without_unblocking_promotion() -> None:
    summary = build_promotion_gate_summary(
        sidecar_metrics={
            "run_id": "sidecar_ok",
            "document_count": 16,
            "comparison": {"decision": {"passed": True}},
        },
        runtime_shadow_summary={
            "run_id": "shadow_none",
            "document_count": 16,
            "documents_with_shadow_comparable_runtime_artifact": 0,
        },
        materialized_shadow_summary={
            "run_id": "materialized_schema_invalid",
            "document_count": 16,
            "eligible_document_count": 1,
            "compare_ready_count": 0,
            "status_counts": {"pairing_mismatch": 0, "prediction_schema_invalid": 1},
            "schema_invalid_reason_counts": {"invalid_intervention_category": 1},
            "runtime_feature_enabled": False,
            "provider_available": True,
        },
        semantic_shadow_summary={
            "run_id": "semantic_shadow_ok",
            "document_count": 16,
            "semantic_prediction_written_count": 1,
            "compare_ready_count": 1,
        },
        semantic_shadow_compare_metrics={
            "run_id": "semantic_compare_ok",
            "document_count": 1,
            "comparison": {"document_count": 1, "decision": {"passed": True, "failed_checks": []}},
        },
        run_id="gate_semantic_viable",
    )

    assert summary["decision"]["promotion_ready"] is False
    assert summary["semantic_shadow"]["semantic_prediction_written_count"] == 1
    assert summary["semantic_shadow"]["compare_ready_count"] == 1
    assert summary["semantic_shadow"]["compare_passed"] is True
    assert summary["semantic_shadow"]["two_step_rfc_viable"] is True
    assert "no_persisted_runtime_specialty_artifact" in summary["decision"]["blockers"]
    assert "materialized_shadow_schema_invalid" in summary["decision"]["blockers"]


def test_run_promotion_gate_writes_summary(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    shadow = tmp_path / "shadow.json"
    materialized = tmp_path / "materialized.json"
    out_dir = tmp_path / "out"

    _write_json(
        sidecar,
        {
            "run_id": "sidecar_ok",
            "document_count": 1,
            "comparison": {"decision": {"passed": True}},
        },
    )
    _write_json(
        shadow,
        {
            "run_id": "shadow_ok",
            "document_count": 1,
            "documents_with_shadow_comparable_runtime_artifact": 1,
        },
    )
    _write_json(
        materialized,
        {
            "run_id": "materialized_ok",
            "document_count": 1,
            "eligible_document_count": 1,
            "compare_ready_count": 1,
            "status_counts": {"pairing_mismatch": 0, "prediction_schema_invalid": 0},
            "schema_invalid_reason_counts": {},
            "runtime_feature_enabled": True,
            "provider_available": True,
        },
    )

    run_root = run_promotion_gate(
        sidecar_metrics_path=sidecar,
        runtime_shadow_summary_path=shadow,
        materialized_shadow_summary_path=materialized,
        semantic_shadow_summary_path=None,
        semantic_shadow_compare_metrics_path=None,
        out_dir=out_dir,
        run_id="gate_ok",
    )

    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["promotion_ready"] is True
    assert payload["materialized_shadow"]["prediction_schema_invalid_count"] == 0
    assert payload["materialized_shadow"]["schema_invalid_reason_counts"] == {}
    assert payload["materialized_shadow"]["pairing_mismatch_count"] == 0
    assert payload["decision"]["blockers"] == []
