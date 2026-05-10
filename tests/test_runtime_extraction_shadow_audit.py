from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.audit_runtime_extraction_shadow import classify_shadow_record, run_shadow_audit
from src.schemas.core import BiomedicalClinicalExtraction, SpecialtyTrialExtraction


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _specialty_payload(paper_id: str) -> dict:
    return SpecialtyTrialExtraction(
        paper_id=paper_id,
        citation={
            "title": "Shadow Specialty Study",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        },
        population={"mci_only": True, "n_total": 42},
        intervention={"product_name": "Test intervention"},
        outcomes={"cognition": [{"name": "ADAS-Cog-12"}]},
        eligibility_flags={"include_for_mci_mct_review": True},
        extraction_quality={"confidence": "high"},
    ).model_dump(mode="json")


def _biomedical_payload(paper_id: str) -> dict:
    return BiomedicalClinicalExtraction(
        paper_id=paper_id,
        citation={
            "title": "Shadow Biomedical Study",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        },
        population={"condition": "Example disease", "n_total": 30},
        intervention={"category": "diagnostic", "name": "Biomarker panel"},
        extraction_quality={"confidence": "medium"},
    ).model_dump(mode="json")


def test_classify_shadow_record_distinguishes_runtime_buckets(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    artifacts_root = tmp_path / "artifacts"
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    _write_json(gold_dir / "paper-a.json", _specialty_payload("paper-a"))
    _write_json(gold_dir / "paper-b.json", _specialty_payload("paper-b"))
    _write_json(gold_dir / "paper-c.json", _specialty_payload("paper-c"))
    _write_json(gold_dir / "paper-d.json", _specialty_payload("paper-d"))
    _write_json(gold_dir / "paper-e.json", _specialty_payload("paper-e"))

    _write_json(
        manifest_path,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "documents": [
                {"paper_id": "paper-a", "gold_path": str(gold_dir / "paper-a.json"), "gold_source_paths": []},
                {"paper_id": "paper-b", "gold_path": str(gold_dir / "paper-b.json"), "gold_source_paths": []},
                {"paper_id": "paper-c", "gold_path": str(gold_dir / "paper-c.json"), "gold_source_paths": []},
                {"paper_id": "paper-d", "gold_path": str(gold_dir / "paper-d.json"), "gold_source_paths": []},
                {"paper_id": "paper-e", "gold_path": str(gold_dir / "paper-e.json"), "gold_source_paths": []},
            ],
        },
    )

    run_a = artifacts_root / "paper-a" / "run_20260328_000001"
    _write_json(run_a / "run_meta.json", {"status": "succeeded", "clinical_extraction_status": "not_clinical_note"})
    _write_json(
        run_a / "bootstrap_meta.json",
        {"clinical_extraction_status": "not_clinical_note", "clinical_extraction_note_type": "non_clinical"},
    )

    run_b = artifacts_root / "paper-b" / "run_20260328_000001"
    _write_json(run_b / "run_meta.json", {"status": "succeeded", "clinical_extraction_status": "completed"})
    _write_json(run_b / "bootstrap_meta.json", {"clinical_extraction_note_type": "clinical"})
    _write_json(run_b / "clinical_extraction.json", _specialty_payload("paper-b"))

    run_c = artifacts_root / "paper-c" / "run_20260328_000001"
    _write_json(run_c / "run_meta.json", {"status": "succeeded", "clinical_extraction_status": "completed"})
    _write_json(run_c / "bootstrap_meta.json", {"clinical_extraction_note_type": "clinical"})
    _write_json(run_c / "clinical_extraction.json", _biomedical_payload("paper-c"))

    run_d = artifacts_root / "paper-d" / "run_20260328_000001"
    _write_json(run_d / "bootstrap_meta.json", {"run_id": "run_20260328_000001"})

    docs = json.loads(manifest_path.read_text())["documents"]
    buckets = {
        doc["paper_id"]: classify_shadow_record(
            manifest_path=manifest_path,
            doc=doc,
            artifacts_root=artifacts_root,
        )["bucket"]
        for doc in docs
    }

    assert buckets == {
        "paper-a": "not_clinical_note",
        "paper-b": "specialty_runtime_artifact",
        "paper-c": "biomedical_runtime_artifact",
        "paper-d": "legacy_missing_status",
        "paper-e": "no_runtime_run",
    }


def test_run_shadow_audit_writes_summary_details_and_compare_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    artifacts_root = tmp_path / "artifacts"
    out_dir = tmp_path / "out"
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    _write_json(gold_dir / "paper-a.json", _specialty_payload("paper-a"))
    _write_json(gold_dir / "paper-b.json", _specialty_payload("paper-b"))
    _write_json(
        manifest_path,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "documents": [
                {"paper_id": "paper-a", "gold_path": str(gold_dir / "paper-a.json"), "gold_source_paths": []},
                {"paper_id": "paper-b", "gold_path": str(gold_dir / "paper-b.json"), "gold_source_paths": []},
            ],
        },
    )

    run_a = artifacts_root / "paper-a" / "run_20260328_000001"
    _write_json(run_a / "run_meta.json", {"status": "succeeded", "clinical_extraction_status": "completed"})
    _write_json(run_a / "clinical_extraction.json", _specialty_payload("paper-a"))

    run_b = artifacts_root / "paper-b" / "run_20260328_000001"
    _write_json(run_b / "run_meta.json", {"status": "succeeded", "clinical_extraction_status": "not_clinical_note"})
    _write_json(run_b / "bootstrap_meta.json", {"clinical_extraction_note_type": "non_clinical"})

    run_root = run_shadow_audit(
        manifest_path=manifest_path,
        artifacts_root=artifacts_root,
        out_dir=out_dir,
        run_id="shadow_audit_test",
    )

    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    details = json.loads((run_root / "details.json").read_text(encoding="utf-8"))
    compare_manifest = json.loads((run_root / "shadow_compare_manifest.json").read_text(encoding="utf-8"))

    assert summary["document_count"] == 2
    assert summary["documents_with_runtime_runs"] == 2
    assert summary["documents_with_shadow_comparable_runtime_artifact"] == 1
    assert summary["bucket_counts"]["specialty_runtime_artifact"] == 1
    assert summary["bucket_counts"]["not_clinical_note"] == 1
    assert summary["shadow_compare_manifest_document_count"] == 1
    assert compare_manifest["documents"] == [
        {
            "paper_id": "paper-a",
            "gold_path": str(gold_dir / "paper-a.json"),
            "prediction_path": str((run_a / "clinical_extraction.json").resolve()),
        }
    ]
    assert [item["paper_id"] for item in details["documents"]] == ["paper-a", "paper-b"]
