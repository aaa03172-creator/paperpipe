from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.normalize_specialty_runtime_shadow import run_specialty_shadow_normalizer
from src.schemas.core import SpecialtyTrialExtraction


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _gold_payload(*, paper_id: str) -> dict:
    return SpecialtyTrialExtraction(
        paper_id=paper_id,
        citation={
            "title": "Targeting Prodromal Alzheimer Disease With Avagacestat",
            "authors_first": "Coric",
            "year": 2015,
            "journal_or_server": "JAMA Neurology",
        },
        population={"mci_only": True, "n_total": 263},
        intervention={"product_name": "Avagacestat"},
        comparator={"description": "Placebo"},
        outcomes={"cognition": []},
        eligibility_flags={"include_for_mci_mct_review": True},
        extraction_quality={"confidence": "high"},
    ).model_dump(mode="json")


def test_run_specialty_shadow_normalizer_writes_compare_ready_prediction(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold" / "paper.json"
    raw_path = tmp_path / "raw.txt"
    details_path = tmp_path / "details.json"
    out_dir = tmp_path / "out"

    _write_json(gold_path, _gold_payload(paper_id="paper-eligible"))
    raw_path.write_text(
        json.dumps(
            {
                "paper_id": None,
                "citation": None,
                "population": {"mci_only": True},
                "intervention": {"category": "γ-secretase inhibitor", "product_name": "avagacestat"},
                "comparator": "placebo",
                "ketone_confirmation": None,
                "outcomes": {"cognition": []},
                "risk_of_bias_hints": None,
                "eligibility_flags": None,
                "extraction_quality": {"missing_fields": ["paper_id", "citation"]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        details_path,
        {
            "documents": [
                {
                    "paper_id": "paper-eligible",
                    "gold_path": str(gold_path),
                    "status": "prediction_schema_invalid",
                    "raw_response_path": str(raw_path),
                }
            ]
        },
    )

    run_root = run_specialty_shadow_normalizer(
        materialized_details_path=details_path,
        out_dir=out_dir,
        run_id="normalized_ok",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["normalized_prediction_written_count"] == 1
    assert summary["compare_ready_count"] == 1
    assert summary["status_counts"]["normalized_prediction_written"] == 1
    assert generated_manifest["documents"][0]["paper_id"] == "paper-eligible"
    assert details["documents"][0]["status"] == "normalized_prediction_written"
    assert "citation_from_gold_metadata" in details["documents"][0]["normalization_actions"]
    assert "comparator_string_to_object" in details["documents"][0]["normalization_actions"]
    assert "intervention_category_to_other" in details["documents"][0]["normalization_actions"]


def test_run_specialty_shadow_normalizer_preserves_pairing_mismatch(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold" / "paper.json"
    raw_path = tmp_path / "raw.txt"
    details_path = tmp_path / "details.json"
    out_dir = tmp_path / "out"

    _write_json(gold_path, _gold_payload(paper_id="paper-eligible"))
    raw_path.write_text(
        json.dumps(
            {
                "paper_id": "doi:10.1234/example",
                "citation": None,
                "population": {"mci_only": True},
                "intervention": {"category": "γ-secretase inhibitor", "product_name": "avagacestat"},
                "comparator": "placebo",
                "ketone_confirmation": None,
                "outcomes": {"cognition": []},
                "risk_of_bias_hints": None,
                "eligibility_flags": None,
                "extraction_quality": {"missing_fields": ["citation"]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        details_path,
        {
            "documents": [
                {
                    "paper_id": "paper-eligible",
                    "gold_path": str(gold_path),
                    "status": "prediction_schema_invalid",
                    "raw_response_path": str(raw_path),
                }
            ]
        },
    )

    run_root = run_specialty_shadow_normalizer(
        materialized_details_path=details_path,
        out_dir=out_dir,
        run_id="normalized_pairing_mismatch",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["normalized_prediction_written_count"] == 0
    assert summary["status_counts"]["pairing_mismatch"] == 1
    assert generated_manifest["documents"] == []
    assert details["documents"][0]["status"] == "pairing_mismatch"
    assert details["documents"][0]["prediction_paper_id"] == "doi:10.1234/example"
