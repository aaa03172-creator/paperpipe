from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.audit_slot_classification_goldset import run_audit
from src.services.slot_classification_audit import (
    build_slot_classification_goldset_audit,
    load_slot_classification_goldset_csv,
    load_slot_classification_predictions_jsonl,
)


def test_build_slot_classification_goldset_audit_reports_accuracy_and_coverage() -> None:
    goldset_rows = [
        {
            "paper_id": "paper-a",
            "doi": "10.1000/a",
            "title": "Clinical paper",
            "summary": "Human biomarker cohort.",
            "current_slot": "mechanism",
            "gold_slot": "clinical",
        },
        {
            "paper_id": "paper-b",
            "doi": "10.1000/b",
            "title": "Mechanism paper",
            "summary": "Mouse pathway study.",
            "current_slot": "clinical",
            "gold_slot": "mechanism",
        },
        {
            "paper_id": "paper-c",
            "doi": "10.1000/c",
            "title": "Methods paper",
            "summary": "Assay validation study.",
            "current_slot": "methods",
            "gold_slot": "methods",
            "gold_slot_rationale": "Benchmarking a new assay platform is treated as methods.",
        },
    ]
    predictions_by_key = {
        "doi:10.1000/a": {
            "doi": "10.1000/a",
            "current_slot": "unknown",
            "predicted_slot": "clinical",
            "prediction_status": "ok",
            "prediction_source": "fixture",
        },
        "paper_id:paper-b": {
            "paper_id": "paper-b",
            "current_slot": "clinical",
            "predicted_slot": "clinical",
            "prediction_status": "ok",
            "prediction_source": "fixture",
        },
    }

    summary, details = build_slot_classification_goldset_audit(
        goldset_rows=goldset_rows,
        predictions_by_key=predictions_by_key,
        run_id="slot_classification_audit_test",
        goldset_csv_path=Path("/tmp/goldset.csv"),
        predictions_jsonl_path=Path("/tmp/predictions.jsonl"),
    )

    assert summary.metrics.document_count == 3
    assert summary.metrics.evaluated_count == 2
    assert summary.metrics.matched_count == 1
    assert summary.metrics.mismatch_count == 1
    assert summary.metrics.missing_prediction_count == 1
    assert summary.metrics.accuracy == 0.5
    assert summary.metrics.prediction_coverage_rate == 0.6667
    assert summary.metrics.gold_slot_counts == {
        "clinical": 1,
        "mechanism": 1,
        "methods": 1,
    }
    assert summary.metrics.predicted_slot_counts == {"clinical": 2}
    assert summary.metrics.confusion_counts == {
        "clinical->clinical": 1,
        "mechanism->clinical": 1,
    }
    assert summary.metrics.per_gold_slot_accuracy == {
        "clinical": 1.0,
        "mechanism": 0.0,
        "methods": 0.0,
    }
    assert summary.metrics.per_gold_slot_coverage == {
        "clinical": 1.0,
        "mechanism": 1.0,
        "methods": 0.0,
    }
    assert summary.metrics.input_richness_counts == {
        "title_summary": 3,
    }
    assert summary.documents_with_mismatch == ["paper-b"]
    assert summary.documents_missing_prediction == ["paper-c"]
    assert len(details.documents) == 3
    assert details.documents[0].matched is True
    assert details.documents[0].current_slot == "unknown"
    assert details.documents[0].input_richness == "title_summary"
    assert details.documents[1].matched is False
    assert details.documents[2].predicted_slot is None
    assert details.documents[2].gold_slot_rationale == "Benchmarking a new assay platform is treated as methods."


def test_slot_classification_goldset_script_writes_snapshot(tmp_path: Path) -> None:
    goldset_csv = tmp_path / "goldset.csv"
    predictions_jsonl = tmp_path / "predictions.jsonl"
    out_dir = tmp_path / "out"
    goldset_csv.write_text(
        "\n".join(
            [
                "paper_id,doi,title,summary,full_text,current_slot,gold_slot,gold_slot_rationale",
                "paper-a,10.1000/a,Clinical paper,Human biomarker cohort.,,mechanism,clinical,Human cohort outcome focus is clinical.",
                "paper-b,10.1000/b,Mechanism paper,Mouse pathway study.,Results pathway activation,clinical,mechanism,Pathway and intervention focus is mechanism.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    predictions_jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "doi": "10.1000/a",
                        "predicted_slot": "clinical",
                        "prediction_status": "ok",
                        "prediction_source": "fixture",
                    }
                ),
                json.dumps(
                    {
                        "paper_id": "paper-b",
                        "predicted_slot": "mechanism",
                        "prediction_status": "ok",
                        "prediction_source": "fixture",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_root = run_audit(
        goldset_csv_path=goldset_csv,
        predictions_jsonl_path=predictions_jsonl,
        out_dir=out_dir,
        run_id="slot_classification_fixture_run",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))

    assert run_root == out_dir / "slot_classification_fixture_run"
    assert summary["metrics"]["document_count"] == 2
    assert summary["metrics"]["matched_count"] == 2
    assert summary["metrics"]["accuracy"] == 1.0
    assert summary["metrics"]["input_richness_counts"] == {
        "title_summary": 1,
        "title_summary_full_text": 1,
    }
    assert details["documents"][0]["paper_id"] == "paper-a"
    assert details["documents"][0]["gold_slot_rationale"] == "Human cohort outcome focus is clinical."
    audit_markdown = (run_root / "audit.md").read_text(encoding="utf-8")
    assert "## Gold Label Rationales" in audit_markdown
    assert "- paper-a (clinical): Human cohort outcome focus is clinical." in audit_markdown


def test_loaders_accept_curated_fixture_files() -> None:
    root = Path(__file__).resolve().parent / "fixtures"
    goldset_rows = load_slot_classification_goldset_csv(
        root / "slot_classification_goldset_curated_20260421.csv"
    )
    predictions = load_slot_classification_predictions_jsonl(
        root / "slot_classification_predictions_curated_20260421.jsonl"
    )

    assert len(goldset_rows) == 4
    assert goldset_rows[0]["gold_slot"] == "clinical"
    assert goldset_rows[1]["input_richness"] == "title_summary_full_text"
    assert goldset_rows[0]["gold_slot_rationale"] is None
    assert "doi:10.1000/example-clinical-001" in predictions
    assert predictions["doi:10.1000/example-clinical-001"]["prediction_source"] == "curated_stub"
