from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.eval.evaluate_evidence_extraction_bundle import main as run_bc5cdr_cli
from src.schemas.bc5cdr_eval import BC5CDRDocument, BC5CDRMention, BC5CDRRelation
from src.schemas.evidence_extraction import (
    EvidenceExtractionBundle,
    EvidenceExtractionMetrics,
    EvidenceExtractionRecord,
)
from src.services.bc5cdr_eval import evaluate_bc5cdr_bundle, project_bundle_to_bc5cdr_document


def _bundle_with_bc5cdr_records() -> EvidenceExtractionBundle:
    return EvidenceExtractionBundle(
        generated_at=datetime.now(timezone.utc),
        paper_id="doc-1",
        doc_id="doc-1",
        run_id="run-1",
        source_artifacts=["evidence_extraction_bundle.json"],
        metrics=EvidenceExtractionMetrics(record_count=3, entity_record_count=2, relation_record_count=1),
        records=[
            EvidenceExtractionRecord(
                record_id="entity:chem:1",
                record_type="entity",
                label="Chemical",
                value="Aspirin",
                normalized_value="MESH:C0004057",
                source_artifact="evidence_extraction_bundle.json",
                status="derived",
                metadata={
                    "entity_type": "chemical",
                    "mention_text": "Aspirin",
                    "char_start": 0,
                    "char_end": 7,
                },
            ),
            EvidenceExtractionRecord(
                record_id="entity:disease:1",
                record_type="entity",
                label="Disease",
                value="Headache",
                normalized_value="MESH:D006261",
                source_artifact="evidence_extraction_bundle.json",
                status="derived",
                metadata={
                    "entity_type": "disease",
                    "mention_text": "Headache",
                    "char_start": 20,
                    "char_end": 28,
                },
            ),
            EvidenceExtractionRecord(
                record_id="relation:1",
                record_type="relation",
                label="CID",
                value="Aspirin causes headache",
                source_artifact="evidence_extraction_bundle.json",
                status="derived",
                metadata={
                    "relation_type": "chemical_induced_disease",
                    "chemical_record_id": "entity:chem:1",
                    "disease_record_id": "entity:disease:1",
                },
            ),
        ],
    )


def _gold_doc() -> BC5CDRDocument:
    return BC5CDRDocument(
        doc_id="doc-1",
        mentions=[
            BC5CDRMention(
                mention_id="gold-chem",
                entity_type="chemical",
                text="Aspirin",
                char_start=0,
                char_end=7,
                normalized_id="MESH:C0004057",
            ),
            BC5CDRMention(
                mention_id="gold-disease",
                entity_type="disease",
                text="Headache",
                char_start=20,
                char_end=28,
                normalized_id="MESH:D006261",
            ),
        ],
        relations=[
            BC5CDRRelation(
                relation_id="gold-rel",
                chemical_mention_id="gold-chem",
                disease_mention_id="gold-disease",
            )
        ],
    )


def test_project_bundle_to_bc5cdr_document_maps_entity_and_relation_records():
    bundle = _bundle_with_bc5cdr_records()

    prediction_document, warnings = project_bundle_to_bc5cdr_document(bundle)

    assert warnings == []
    assert prediction_document.doc_id == "doc-1"
    assert len(prediction_document.mentions) == 2
    assert len(prediction_document.relations) == 1
    assert prediction_document.relations[0].chemical_mention_id == "entity:chem:1"


def test_evaluate_bc5cdr_bundle_scores_exact_and_relation_matches():
    report = evaluate_bc5cdr_bundle(
        gold_document=_gold_doc(),
        bundle=_bundle_with_bc5cdr_records(),
    )

    assert report.doc_id_match is True
    assert report.mention_exact.f1 == 1.0
    assert report.mention_normalized.f1 == 1.0
    assert report.relation.f1 == 1.0
    assert report.warnings == []


def test_evaluate_bc5cdr_bundle_reports_projection_warnings_for_bad_records():
    bundle = _bundle_with_bc5cdr_records()
    bundle.records[0].metadata.pop("char_start")

    report = evaluate_bc5cdr_bundle(gold_document=_gold_doc(), bundle=bundle)

    assert report.mention_exact.hit_count == 1
    assert "entity_missing_offsets:entity:chem:1" in report.warnings


def test_evaluate_bc5cdr_bundle_relation_match_does_not_require_normalized_ids():
    bundle = _bundle_with_bc5cdr_records()
    bundle.records[0].normalized_value = None
    bundle.records[1].normalized_value = None

    report = evaluate_bc5cdr_bundle(gold_document=_gold_doc(), bundle=bundle)

    assert report.mention_normalized.f1 == 0.0
    assert report.relation.f1 == 1.0


def test_bc5cdr_eval_cli_writes_report(tmp_path: Path):
    gold_path = tmp_path / "gold.json"
    prediction_path = tmp_path / "bundle.json"
    out_path = tmp_path / "report.json"

    gold_path.write_text(_gold_doc().model_dump_json(indent=2), encoding="utf-8")
    prediction_path.write_text(_bundle_with_bc5cdr_records().model_dump_json(indent=2), encoding="utf-8")

    exit_code = run_bc5cdr_cli(
        [
            "--gold",
            str(gold_path),
            "--prediction-bundle",
            str(prediction_path),
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["mention_exact"]["f1"] == 1.0
    assert payload["relation"]["f1"] == 1.0
