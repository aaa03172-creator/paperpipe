from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.compare_extraction_outputs import evaluate_extraction_pair
from scripts.eval.repair_specialty_runtime_shadow_semantics import run_specialty_shadow_semantic_repair
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
        study_design={"duration_weeks": 104},
        population={"mci_only": True, "n_total": 263},
        intervention={"product_name": "Avagacestat", "duration_weeks": 104},
        comparator={"description": "Placebo"},
        outcomes={"cognition": [{"name": "Key clinical outcome measures", "effect_direction": "no_change"}]},
        eligibility_flags={"include_for_mci_mct_review": True},
        extraction_quality={"confidence": "high"},
    ).model_dump(mode="json")


def test_semantic_repair_recovers_coric_core_fields(tmp_path: Path, monkeypatch) -> None:
    gold_path = tmp_path / "gold" / "paper.json"
    raw_path = tmp_path / "raw.txt"
    details_path = tmp_path / "details.json"
    out_dir = tmp_path / "out"
    artifact_path = tmp_path / "artifact.json"

    _write_json(gold_path, _gold_payload(paper_id="paper-eligible"))
    raw_path.write_text(
        json.dumps(
            {
                "paper_id": None,
                "citation": None,
                "study_design": {"type": "randomized", "parallel": True},
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
    artifact_path.write_text("{}", encoding="utf-8")
    _write_json(
        details_path,
        {
            "documents": [
                {
                    "paper_id": "paper-eligible",
                    "gold_path": str(gold_path),
                    "status": "prediction_schema_invalid",
                    "raw_response_path": str(raw_path),
                    "document_artifact_path": str(artifact_path),
                }
            ]
        },
    )

    def _fake_load_artifact(path: Path) -> object:
        return object()

    def _fake_build_inputs(doc: object, *, paper_id: str, gold_extraction: SpecialtyTrialExtraction) -> tuple[dict, str]:
        return (
            {
                "paper_id": paper_id,
                "title": gold_extraction.citation.title,
                "summary": (
                    "Targeting Prodromal Alzheimer Disease With Avagacestat. "
                    "Of 1358 outpatients screened, 263 met MCI and CSF biomarker criteria for randomization "
                    "into the treatment phase. INTERVENTIONS Oral avagacestat or placebo daily. "
                    "At 2 years, progression to dementia was more frequent. "
                    "No significant treatment differences were observed in key clinical outcome measures."
                ),
            },
            "Oral avagacestat or placebo daily. At 2 years, no significant treatment differences were observed in key clinical outcome measures.",
        )

    monkeypatch.setattr(
        "scripts.eval.repair_specialty_runtime_shadow_semantics._load_artifact",
        _fake_load_artifact,
    )
    monkeypatch.setattr(
        "scripts.eval.repair_specialty_runtime_shadow_semantics._build_specialty_shadow_inputs",
        _fake_build_inputs,
    )

    run_root = run_specialty_shadow_semantic_repair(
        materialized_details_path=details_path,
        out_dir=out_dir,
        run_id="semantic_ok",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["semantic_prediction_written_count"] == 1
    assert summary["compare_ready_count"] == 1
    assert details["documents"][0]["status"] == "semantic_prediction_written"
    assert "intervention_category_to_unknown_for_named_product" in details["documents"][0]["semantic_repair_actions"]
    assert "population_n_total_from_source" in details["documents"][0]["semantic_repair_actions"]
    assert "duration_weeks_from_source" in details["documents"][0]["semantic_repair_actions"]
    assert "outcome_name_from_source" in details["documents"][0]["semantic_repair_actions"]
    assert "outcome_effect_no_change_from_source" in details["documents"][0]["semantic_repair_actions"]

    row = evaluate_extraction_pair(
        gold_path=Path(generated_manifest["documents"][0]["gold_path"]),
        prediction_path=Path(generated_manifest["documents"][0]["prediction_path"]),
        paper_id="paper-eligible",
    )
    assert row["schema_valid"] is True
    assert row["pairing_valid"] is True
    assert row["mismatched_fields"] == []
    assert row["buckets"] == []


def test_semantic_repair_preserves_pairing_mismatch(tmp_path: Path, monkeypatch) -> None:
    gold_path = tmp_path / "gold" / "paper.json"
    raw_path = tmp_path / "raw.txt"
    details_path = tmp_path / "details.json"
    out_dir = tmp_path / "out"
    artifact_path = tmp_path / "artifact.json"

    _write_json(gold_path, _gold_payload(paper_id="paper-eligible"))
    raw_path.write_text(
        json.dumps(
            {
                "paper_id": "doi:10.1234/example",
                "citation": None,
                "study_design": {"type": "randomized", "parallel": True},
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
    artifact_path.write_text("{}", encoding="utf-8")
    _write_json(
        details_path,
        {
            "documents": [
                {
                    "paper_id": "paper-eligible",
                    "gold_path": str(gold_path),
                    "status": "prediction_schema_invalid",
                    "raw_response_path": str(raw_path),
                    "document_artifact_path": str(artifact_path),
                }
            ]
        },
    )

    monkeypatch.setattr(
        "scripts.eval.repair_specialty_runtime_shadow_semantics._load_artifact",
        lambda path: object(),
    )
    monkeypatch.setattr(
        "scripts.eval.repair_specialty_runtime_shadow_semantics._build_specialty_shadow_inputs",
        lambda doc, *, paper_id, gold_extraction: (
            {"paper_id": paper_id, "title": gold_extraction.citation.title, "summary": "Oral avagacestat or placebo daily. At 2 years."},
            "No significant treatment differences were observed in key clinical outcome measures.",
        ),
    )

    run_root = run_specialty_shadow_semantic_repair(
        materialized_details_path=details_path,
        out_dir=out_dir,
        run_id="semantic_pairing_mismatch",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))

    assert summary["semantic_prediction_written_count"] == 0
    assert summary["status_counts"]["pairing_mismatch"] == 1
    assert generated_manifest["documents"] == []
    assert details["documents"][0]["status"] == "pairing_mismatch"
    assert details["documents"][0]["prediction_paper_id"] == "doi:10.1234/example"
