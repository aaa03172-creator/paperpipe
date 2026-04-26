from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.compare_extraction_outputs import compare_extraction_rows, evaluate_extraction_pair
from src.schemas.core import SpecialtyTrialExtraction


def _specialty_trial_extraction_payload(
    paper_id: str,
    *,
    mci_only: bool = True,
    intervention_category: str = "mct",
    intervention_product_name: str | None = "Ketone ester",
    comparator_description: str | None = "Placebo",
    outcome_name: str | None = "ADAS-Cog",
    outcome_effect: str = "improved",
    sample_size: int = 48,
    duration_weeks: int = 12,
    include_for_review: bool = True,
    missing_fields: list[str] | None = None,
) -> dict:
    payload = SpecialtyTrialExtraction(
        paper_id=paper_id,
        citation={
            "title": paper_id,
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
            "doi": None,
            "url": None,
        },
        population={
            "mci_only": mci_only,
            "n_total": sample_size,
        },
        intervention={
            "category": intervention_category,
            "product_name": intervention_product_name,
            "duration_weeks": duration_weeks,
        },
        comparator={
            "description": comparator_description,
        },
        outcomes={
            "cognition": (
                []
                if outcome_name is None
                else [
                    {
                        "name": outcome_name,
                        "effect_direction": outcome_effect,
                    }
                ]
            )
        },
        eligibility_flags={
            "include_for_mci_mct_review": include_for_review,
        },
        extraction_quality={
            "confidence": "medium",
            "missing_fields": missing_fields or [],
        },
    ).model_dump(mode="json")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_compare_extraction_rows_classifies_expected_bucket_types(tmp_path: Path) -> None:
    pairs: list[dict] = []

    gold_missing = tmp_path / "gold_missing.json"
    pred_missing = tmp_path / "pred_missing.json"
    _write_json(gold_missing, _specialty_trial_extraction_payload("paper-missing", sample_size=48))
    _write_json(
        pred_missing,
        _specialty_trial_extraction_payload("paper-missing", sample_size=0, missing_fields=["sample_size"]),
    )
    pairs.append({"paper_id": "paper-missing", "gold_path": gold_missing, "prediction_path": pred_missing})

    gold_negation = tmp_path / "gold_negation.json"
    pred_negation = tmp_path / "pred_negation.json"
    _write_json(
        gold_negation,
        _specialty_trial_extraction_payload("paper-negation", outcome_effect="no_change", include_for_review=False),
    )
    _write_json(
        pred_negation,
        _specialty_trial_extraction_payload("paper-negation", outcome_effect="improved", include_for_review=True),
    )
    pairs.append({"paper_id": "paper-negation", "gold_path": gold_negation, "prediction_path": pred_negation})

    gold_comparator = tmp_path / "gold_comparator.json"
    pred_comparator = tmp_path / "pred_comparator.json"
    _write_json(
        gold_comparator,
        _specialty_trial_extraction_payload(
            "paper-comparator",
            intervention_product_name="Ketone ester",
            comparator_description="Placebo",
        ),
    )
    _write_json(
        pred_comparator,
        _specialty_trial_extraction_payload(
            "paper-comparator",
            intervention_product_name="Placebo",
            comparator_description="Ketone ester",
        ),
    )
    pairs.append({"paper_id": "paper-comparator", "gold_path": gold_comparator, "prediction_path": pred_comparator})

    gold_hallucination = tmp_path / "gold_hallucination.json"
    pred_hallucination = tmp_path / "pred_hallucination.json"
    _write_json(
        gold_hallucination,
        _specialty_trial_extraction_payload(
            "paper-hallucination",
            duration_weeks=0,
            missing_fields=["duration"],
        ),
    )
    _write_json(
        pred_hallucination,
        _specialty_trial_extraction_payload("paper-hallucination", duration_weeks=12),
    )
    pairs.append({"paper_id": "paper-hallucination", "gold_path": gold_hallucination, "prediction_path": pred_hallucination})

    gold_other = tmp_path / "gold_other.json"
    pred_other = tmp_path / "pred_other.json"
    _write_json(gold_other, _specialty_trial_extraction_payload("paper-other", duration_weeks=12))
    _write_json(pred_other, _specialty_trial_extraction_payload("paper-other", duration_weeks=24))
    pairs.append({"paper_id": "paper-other", "gold_path": gold_other, "prediction_path": pred_other})

    rows = [
        evaluate_extraction_pair(
            gold_path=pair["gold_path"],
            prediction_path=pair["prediction_path"],
            paper_id=pair["paper_id"],
        )
        for pair in pairs
    ]
    report = compare_extraction_rows(rows=rows)

    assert report["document_count"] == 5
    assert {entry["paper_id"] for entry in report["missing_core_field_docs"]} == {"paper-missing"}
    assert {entry["paper_id"] for entry in report["negation_failure_docs"]} == {"paper-negation"}
    assert {entry["paper_id"] for entry in report["comparator_confusion_docs"]} == {"paper-comparator"}
    assert {entry["paper_id"] for entry in report["hallucination_docs"]} == {"paper-hallucination"}
    assert {entry["paper_id"] for entry in report["other_core_mismatch_docs"]} == {"paper-other"}
    assert report["decision"]["passed"] is False
    assert "core_mismatch_docs" in report["decision"]["failed_checks"]
    assert report["core_field_match_rates"]["sample_size"] < 1.0
    assert report["core_field_match_rates"]["duration"] < 1.0


def test_evaluate_extraction_pair_honors_normalized_missing_field_aliases_and_pairing_guards(tmp_path: Path) -> None:
    gold_alias = tmp_path / "gold_alias.json"
    pred_alias = tmp_path / "pred_alias.json"
    _write_json(
        gold_alias,
        _specialty_trial_extraction_payload(
            "paper-alias",
            duration_weeks=12,
            missing_fields=["study_design.duration_weeks"],
        ),
    )
    _write_json(pred_alias, _specialty_trial_extraction_payload("paper-alias", duration_weeks=12))

    alias_row = evaluate_extraction_pair(gold_path=gold_alias, prediction_path=pred_alias, paper_id="paper-alias")
    assert alias_row["gold_snapshot"]["duration_weeks"] is None
    assert "hallucination" in alias_row["buckets"]

    gold_pair = tmp_path / "gold_pair.json"
    pred_pair = tmp_path / "pred_pair.json"
    _write_json(gold_pair, _specialty_trial_extraction_payload("paper-a"))
    _write_json(pred_pair, _specialty_trial_extraction_payload("paper-b"))

    wrapped_payload = {
        "specialty_trial_extraction": _specialty_trial_extraction_payload("paper-wrapped")
    }
    wrapped_gold = tmp_path / "wrapped_gold.json"
    wrapped_pred = tmp_path / "wrapped_pred.json"
    _write_json(wrapped_gold, wrapped_payload)
    _write_json(wrapped_pred, wrapped_payload)

    wrapped_row = evaluate_extraction_pair(
        gold_path=wrapped_gold,
        prediction_path=wrapped_pred,
        paper_id="paper-wrapped",
    )
    assert wrapped_row["pairing_valid"] is True
    assert wrapped_row["buckets"] == []

    pairing_row = evaluate_extraction_pair(gold_path=gold_pair, prediction_path=pred_pair)
    assert pairing_row["pairing_valid"] is False
    assert pairing_row["buckets"] == ["pairing_mismatch"]
    assert "PAIRING_MISMATCH" in str(pairing_row["error"])


def test_compare_extraction_outputs_cli_writes_metrics_and_rows(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "eval" / "compare_extraction_outputs.py"

    gold_ok = tmp_path / "gold_ok.json"
    pred_ok = tmp_path / "pred_ok.json"
    gold_swap = tmp_path / "gold_swap.json"
    pred_swap = tmp_path / "pred_swap.json"
    _write_json(gold_ok, _specialty_trial_extraction_payload("paper-ok"))
    _write_json(pred_ok, _specialty_trial_extraction_payload("paper-ok"))
    _write_json(gold_swap, _specialty_trial_extraction_payload("paper-swap"))
    _write_json(
        pred_swap,
        _specialty_trial_extraction_payload(
            "paper-swap",
            intervention_product_name="Placebo",
            comparator_description="Ketone ester",
        ),
    )

    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "documents": [
                {
                    "paper_id": "paper-ok",
                    "gold_path": "gold_ok.json",
                    "prediction_path": "pred_ok.json",
                },
                {
                    "paper_id": "paper-swap",
                    "gold_path": "gold_swap.json",
                    "prediction_path": "pred_swap.json",
                },
            ],
        },
    )

    out_dir = tmp_path / "snapshots"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--manifest",
            str(manifest),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "fixture_run",
        ],
        check=True,
        cwd=repo_root,
    )

    run_root = out_dir / "fixture_run"
    metrics = json.loads((run_root / "metrics.json").read_text(encoding="utf-8"))
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (run_root / "detailed_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert metrics["document_count"] == 2
    assert summary["status"] == "ok"
    assert len(rows) == 2
    assert metrics["comparison"]["decision"]["passed"] is False
    assert "comparator_confusion_docs" in metrics["comparison"]["decision"]["failed_checks"]
    assert metrics["comparison"]["pairing_mismatch_docs"] == []
    assert rows[0]["schema_version"] == "extraction_regression_eval_row.v1"
