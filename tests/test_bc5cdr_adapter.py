from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.convert_bc5cdr_to_evidence_bundle import main as run_bc5cdr_convert_cli
from src.schemas.bc5cdr_eval import BC5CDRDocument, BC5CDRMention, BC5CDRRelation
from src.services.bc5cdr_adapter import project_bc5cdr_to_evidence_extraction_bundle
from src.services.bc5cdr_eval import evaluate_bc5cdr_bundle, project_bundle_to_bc5cdr_document


def _gold_doc() -> BC5CDRDocument:
    return BC5CDRDocument(
        doc_id="bc5cdr-doc-1",
        title="Aspirin and headache",
        abstract="Aspirin can induce headache.",
        mentions=[
            BC5CDRMention(
                mention_id="chem-1",
                entity_type="chemical",
                text="Aspirin",
                char_start=0,
                char_end=7,
                normalized_id="MESH:C0004057",
            ),
            BC5CDRMention(
                mention_id="disease-1",
                entity_type="disease",
                text="headache",
                char_start=19,
                char_end=27,
                normalized_id="MESH:D006261",
            ),
        ],
        relations=[
            BC5CDRRelation(
                relation_id="rel-1",
                chemical_mention_id="chem-1",
                disease_mention_id="disease-1",
            )
        ],
    )


def test_project_bc5cdr_to_evidence_extraction_bundle_creates_entity_and_relation_records():
    bundle = project_bc5cdr_to_evidence_extraction_bundle(_gold_doc(), run_id="run-bc5cdr")

    assert bundle.paper_id == "bc5cdr-doc-1"
    assert bundle.doc_id == "bc5cdr-doc-1"
    assert bundle.run_id == "run-bc5cdr"
    assert bundle.metrics.entity_record_count == 2
    assert bundle.metrics.relation_record_count == 1
    assert bundle.metrics.artifact_backed_record_count == 3
    relation_record = next(record for record in bundle.records if record.record_type == "relation")
    assert relation_record.metadata["chemical_record_id"] == "entity:chem-1"
    assert relation_record.metadata["disease_record_id"] == "entity:disease-1"


def test_bc5cdr_adapter_roundtrips_through_bundle_projection_and_eval():
    gold = _gold_doc()
    bundle = project_bc5cdr_to_evidence_extraction_bundle(gold)

    projected_doc, warnings = project_bundle_to_bc5cdr_document(bundle)
    report = evaluate_bc5cdr_bundle(gold_document=gold, bundle=bundle)

    assert warnings == []
    assert projected_doc.doc_id == gold.doc_id
    assert len(projected_doc.mentions) == 2
    assert len(projected_doc.relations) == 1
    assert report.mention_exact.f1 == 1.0
    assert report.mention_normalized.f1 == 1.0
    assert report.relation.f1 == 1.0


def test_convert_bc5cdr_to_evidence_bundle_cli_writes_bundle(tmp_path: Path):
    input_path = tmp_path / "bc5cdr.json"
    out_dir = tmp_path / "out"
    input_path.write_text(_gold_doc().model_dump_json(indent=2), encoding="utf-8")

    exit_code = run_bc5cdr_convert_cli(
        [
            "--input",
            str(input_path),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "cli-run",
        ]
    )

    assert exit_code == 0
    bundle_path = out_dir / "evidence_extraction_bundle.json"
    assert bundle_path.exists()
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "cli-run"
    assert payload["metrics"]["entity_record_count"] == 2
    assert payload["metrics"]["relation_record_count"] == 1
