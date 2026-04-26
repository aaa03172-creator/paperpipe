from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.audit_slot_classification_rerun_drift import run_audit
from src.services.slot_classification_rerun_drift import build_slot_classification_rerun_drift, load_slot_classification_audit_run


def test_build_slot_classification_rerun_drift_reports_changed_predictions(tmp_path: Path) -> None:
    prior_run = _write_audit_run(
        tmp_path / "prior",
        run_id="slot_prior",
        documents=[
            _doc("paper-a", "10.1000/a", "methods", "methods", True),
            _doc("paper-b", "10.1000/b", "clinical", "methods", False),
        ],
        accuracy=0.5,
        mismatch_count=1,
    )
    new_run = _write_audit_run(
        tmp_path / "new",
        run_id="slot_new",
        documents=[
            _doc("paper-a", "10.1000/a", "methods", "methods", True),
            _doc("paper-b", "10.1000/b", "clinical", "clinical", True),
        ],
        accuracy=1.0,
        mismatch_count=0,
    )

    prior_summary_path, prior_details_path, prior_summary, prior_details = load_slot_classification_audit_run(prior_run)
    new_summary_path, new_details_path, new_summary, new_details = load_slot_classification_audit_run(new_run)
    summary, details = build_slot_classification_rerun_drift(
        prior_summary=prior_summary,
        prior_summary_path=prior_summary_path,
        prior_details=prior_details,
        prior_details_path=prior_details_path,
        new_summary=new_summary,
        new_summary_path=new_summary_path,
        new_details=new_details,
        new_details_path=new_details_path,
        run_id="slot_rerun_drift_test",
    )

    assert summary.metrics.document_count == 2
    assert summary.metrics.drift_count == 1
    assert summary.metrics.drift_rate == 0.5
    assert summary.metrics.predicted_slot_changed_count == 1
    assert summary.metrics.mismatch_status_changed_count == 1
    assert summary.documents_with_drift == ["paper-b"]
    assert len(details.documents) == 1
    assert details.documents[0].paper_id == "paper-b"
    assert details.documents[0].prior_predicted_slot == "methods"
    assert details.documents[0].new_predicted_slot == "clinical"
    assert details.documents[0].changed_fields == ["predicted_slot", "matched"]


def test_slot_classification_rerun_drift_script_writes_snapshot(tmp_path: Path) -> None:
    prior_run = _write_audit_run(
        tmp_path / "prior",
        run_id="slot_prior",
        documents=[_doc("paper-a", "10.1000/a", "methods", "methods", True)],
        accuracy=1.0,
        mismatch_count=0,
    )
    new_run = _write_audit_run(
        tmp_path / "new",
        run_id="slot_new",
        documents=[_doc("paper-a", "10.1000/a", "methods", "clinical", False)],
        accuracy=0.0,
        mismatch_count=1,
    )
    out_dir = tmp_path / "out"

    run_root = run_audit(
        prior_run_path=prior_run,
        new_run_path=new_run,
        out_dir=out_dir,
        run_id="slot_rerun_drift_fixture",
    )

    assert run_root == out_dir / "slot_rerun_drift_fixture"
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["metrics"]["drift_count"] == 1
    assert summary["documents_with_drift"] == ["paper-a"]
    markdown = (run_root / "audit.md").read_text(encoding="utf-8")
    assert "- Prior Run: slot_prior" in markdown
    assert "- paper-a: gold=methods, prior=methods, new=clinical" in markdown


def _write_audit_run(
    root: Path,
    *,
    run_id: str,
    documents: list[dict],
    accuracy: float,
    mismatch_count: int,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": "slot_classification_goldset_audit_summary.v3",
        "generated_at": "2026-04-22T00:00:00Z",
        "run_id": run_id,
        "metrics": {
            "document_count": len(documents),
            "evaluated_count": len(documents),
            "matched_count": len(documents) - mismatch_count,
            "mismatch_count": mismatch_count,
            "missing_prediction_count": 0,
            "accuracy": accuracy,
            "prediction_coverage_rate": 1.0,
        },
        "documents_with_mismatch": [doc["paper_id"] for doc in documents if doc["matched"] is False],
        "documents_missing_prediction": [],
    }
    details = {
        "schema_version": "slot_classification_goldset_audit_details.v3",
        "generated_at": "2026-04-22T00:00:00Z",
        "run_id": run_id,
        "documents": documents,
    }
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return root


def _doc(paper_id: str, doi: str, gold_slot: str, predicted_slot: str, matched: bool) -> dict:
    return {
        "paper_id": paper_id,
        "doi": doi,
        "title": paper_id,
        "gold_slot": gold_slot,
        "predicted_slot": predicted_slot,
        "matched": matched,
        "prediction_status": "ok",
    }
