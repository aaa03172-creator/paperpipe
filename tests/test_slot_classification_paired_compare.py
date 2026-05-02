from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.compare_slot_classification_paired_benchmarks import run_compare
from src.schemas.slot_classification_paired_compare import SlotClassificationPairedCompareThresholds
from src.services.slot_classification_paired_compare import (
    build_slot_classification_paired_compare,
    load_slot_classification_audit_summary,
)


def test_build_slot_classification_paired_compare_flags_regression_and_migration(tmp_path: Path) -> None:
    baseline_default_path = _write_summary(
        tmp_path / "baseline_default.json",
        run_id="baseline_default",
        accuracy=1.0,
        mismatch_count=0,
        documents_with_mismatch=[],
    )
    baseline_boundary_path = _write_summary(
        tmp_path / "baseline_boundary.json",
        run_id="baseline_boundary",
        accuracy=0.75,
        mismatch_count=1,
        documents_with_mismatch=["doi:10.1000/old-boundary"],
    )
    candidate_default_path = _write_summary(
        tmp_path / "candidate_default.json",
        run_id="candidate_default",
        accuracy=0.9091,
        mismatch_count=1,
        documents_with_mismatch=["doi:10.1000/new-default"],
    )
    candidate_boundary_path = _write_summary(
        tmp_path / "candidate_boundary.json",
        run_id="candidate_boundary",
        accuracy=0.75,
        mismatch_count=1,
        documents_with_mismatch=["doi:10.1000/new-boundary"],
    )

    resolved_baseline_default_path, baseline_default_summary = load_slot_classification_audit_summary(
        baseline_default_path
    )
    resolved_baseline_boundary_path, baseline_boundary_summary = load_slot_classification_audit_summary(
        baseline_boundary_path
    )
    resolved_candidate_default_path, candidate_default_summary = load_slot_classification_audit_summary(
        candidate_default_path
    )
    resolved_candidate_boundary_path, candidate_boundary_summary = load_slot_classification_audit_summary(
        candidate_boundary_path
    )

    summary = build_slot_classification_paired_compare(
        baseline_default_summary=baseline_default_summary,
        baseline_default_summary_path=resolved_baseline_default_path,
        baseline_boundary_summary=baseline_boundary_summary,
        baseline_boundary_summary_path=resolved_baseline_boundary_path,
        candidate_default_summary=candidate_default_summary,
        candidate_default_summary_path=resolved_candidate_default_path,
        candidate_boundary_summary=candidate_boundary_summary,
        candidate_boundary_summary_path=resolved_candidate_boundary_path,
        run_id="slot_classification_pair_compare_test",
        thresholds=SlotClassificationPairedCompareThresholds(),
    )

    assert summary.decision.passed is False
    assert summary.decision.failed_checks == [
        "default_template_accuracy",
        "default_template_mismatch_count",
    ]
    assert summary.decision.regressions == [
        "default_template_accuracy",
        "default_template_mismatch_count",
    ]
    assert summary.decision.error_migration_detected is True
    assert summary.decision.tradeoff_review_required is True
    assert summary.decision.surfaces_with_mismatch_migration == ["boundary_companion"]
    assert summary.decision.default_template_resolved_mismatches == []
    assert summary.decision.default_template_new_mismatches == ["doi:10.1000/new-default"]
    assert summary.decision.boundary_companion_resolved_mismatches == ["doi:10.1000/old-boundary"]
    assert summary.decision.boundary_companion_new_mismatches == ["doi:10.1000/new-boundary"]


def test_slot_classification_paired_compare_script_writes_snapshot(tmp_path: Path) -> None:
    baseline_default = _write_summary(
        tmp_path / "baseline_default.json",
        run_id="baseline_default",
        accuracy=1.0,
        mismatch_count=0,
        documents_with_mismatch=[],
    )
    baseline_boundary = _write_summary(
        tmp_path / "baseline_boundary.json",
        run_id="baseline_boundary",
        accuracy=0.75,
        mismatch_count=1,
        documents_with_mismatch=["doi:10.1000/boundary"],
    )
    candidate_default = _write_summary(
        tmp_path / "candidate_default.json",
        run_id="candidate_default",
        accuracy=1.0,
        mismatch_count=0,
        documents_with_mismatch=[],
    )
    candidate_boundary = _write_summary(
        tmp_path / "candidate_boundary.json",
        run_id="candidate_boundary",
        accuracy=0.75,
        mismatch_count=1,
        documents_with_mismatch=["doi:10.1000/boundary"],
    )
    out_dir = tmp_path / "out"

    run_root = run_compare(
        baseline_default_summary_path=baseline_default,
        baseline_boundary_summary_path=baseline_boundary,
        candidate_default_summary_path=candidate_default,
        candidate_boundary_summary_path=candidate_boundary,
        out_dir=out_dir,
        run_id="slot_classification_pair_compare_fixture",
        thresholds=SlotClassificationPairedCompareThresholds(),
    )

    assert run_root == out_dir / "slot_classification_pair_compare_fixture"
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["decision"]["passed"] is True
    assert summary["decision"]["error_migration_detected"] is False
    assert summary["decision"]["surfaces_with_mismatch_migration"] == []
    compare_markdown = (run_root / "compare.md").read_text(encoding="utf-8")
    assert "- Passed: True" in compare_markdown
    assert "- boundary_companion: resolved=['-'], new=['-']" in compare_markdown


def _write_summary(
    path: Path,
    *,
    run_id: str,
    accuracy: float,
    mismatch_count: int,
    documents_with_mismatch: list[str],
    prediction_coverage_rate: float = 1.0,
    document_count: int = 4,
) -> Path:
    payload = {
        "schema_version": "slot_classification_goldset_audit_summary.v3",
        "generated_at": "2026-04-22T00:00:00Z",
        "run_id": run_id,
        "metrics": {
            "document_count": document_count,
            "evaluated_count": document_count,
            "matched_count": document_count - mismatch_count,
            "mismatch_count": mismatch_count,
            "missing_prediction_count": 0,
            "accuracy": accuracy,
            "prediction_coverage_rate": prediction_coverage_rate,
        },
        "documents_with_mismatch": documents_with_mismatch,
        "documents_missing_prediction": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
