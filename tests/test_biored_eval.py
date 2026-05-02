from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.eval.evaluate_biored_evidence_bundle import main as run_biored_cli
from src.schemas.biored_eval import BioREDDocument, BioREDMention, BioREDRelation
from src.schemas.evidence_extraction import (
    EvidenceExtractionBundle,
    EvidenceExtractionMetrics,
    EvidenceExtractionRecord,
)
from src.services.biored_eval import evaluate_biored_bundle, project_bundle_to_biored_document


def _bundle_with_biored_records() -> EvidenceExtractionBundle:
    return EvidenceExtractionBundle(
        generated_at=datetime.now(timezone.utc),
        paper_id="doc-1",
        doc_id="doc-1",
        run_id="run-1",
        source_artifacts=["evidence_extraction_bundle.json"],
        metrics=EvidenceExtractionMetrics(record_count=3, entity_record_count=2, relation_record_count=1),
        records=[
            EvidenceExtractionRecord(
                record_id="entity:gene:1",
                record_type="entity",
                label="GeneOrGeneProduct",
                value="EGFR",
                normalized_value="NCBIGene:1956",
                source_artifact="evidence_extraction_bundle.json",
                status="derived",
                metadata={
                    "entity_type": "GeneOrGeneProduct",
                    "mention_text": "EGFR",
                    "char_start": 0,
                    "char_end": 4,
                },
            ),
            EvidenceExtractionRecord(
                record_id="entity:chemical:1",
                record_type="entity",
                label="ChemicalEntity",
                value="gefitinib",
                normalized_value="MESH:C1100",
                source_artifact="evidence_extraction_bundle.json",
                status="derived",
                metadata={
                    "entity_type": "ChemicalEntity",
                    "mention_text": "gefitinib",
                    "char_start": 35,
                    "char_end": 44,
                },
            ),
            EvidenceExtractionRecord(
                record_id="relation:1",
                record_type="relation",
                label="Positive Correlation",
                value="EGFR to gefitinib",
                source_artifact="evidence_extraction_bundle.json",
                status="derived",
                metadata={
                    "relation_type": "Positive_Correlation",
                    "head_record_id": "entity:gene:1",
                    "tail_record_id": "entity:chemical:1",
                    "novelty": "novel",
                },
            ),
        ],
    )


def _gold_doc() -> BioREDDocument:
    return BioREDDocument(
        doc_id="doc-1",
        mentions=[
            BioREDMention(
                mention_id="gold-gene",
                entity_type="GeneOrGeneProduct",
                text="EGFR",
                char_start=0,
                char_end=4,
                normalized_ids=["NCBIGene:1956"],
            ),
            BioREDMention(
                mention_id="gold-chemical",
                entity_type="ChemicalEntity",
                text="gefitinib",
                char_start=35,
                char_end=44,
                normalized_ids=["MESH:C1100"],
            ),
        ],
        relations=[
            BioREDRelation(
                relation_id="gold-rel",
                relation_type="Positive_Correlation",
                head_mention_id="gold-gene",
                tail_mention_id="gold-chemical",
                novelty="novel",
            )
        ],
    )


def test_project_bundle_to_biored_document_maps_entity_and_relation_records():
    bundle = _bundle_with_biored_records()

    prediction_document, warnings = project_bundle_to_biored_document(bundle)

    assert warnings == []
    assert prediction_document.doc_id == "doc-1"
    assert len(prediction_document.mentions) == 2
    assert len(prediction_document.relations) == 1
    assert prediction_document.relations[0].head_mention_id == "entity:gene:1"


def test_evaluate_biored_bundle_scores_exact_relation_and_novelty_matches():
    report = evaluate_biored_bundle(
        gold_document=_gold_doc(),
        bundle=_bundle_with_biored_records(),
    )

    assert report.doc_id_match is True
    assert report.mention_exact.f1 == 1.0
    assert report.mention_normalized.f1 == 1.0
    assert report.relation.f1 == 1.0
    assert report.relation_novelty.f1 == 1.0
    assert report.warnings == []


def test_evaluate_biored_bundle_handles_missing_offsets_and_separate_novelty_score():
    bundle = _bundle_with_biored_records()
    bundle.records[0].metadata.pop("char_start")
    bundle.records[2].metadata["novelty"] = "background"

    report = evaluate_biored_bundle(gold_document=_gold_doc(), bundle=bundle)

    assert report.mention_exact.hit_count == 1
    assert report.relation_novelty.f1 == 0.0
    assert "entity_missing_offsets:entity:gene:1" in report.warnings


def test_biored_eval_cli_writes_report(tmp_path: Path):
    gold_path = tmp_path / "gold.json"
    prediction_path = tmp_path / "bundle.json"
    out_path = tmp_path / "report.json"

    gold_path.write_text(_gold_doc().model_dump_json(indent=2), encoding="utf-8")
    prediction_path.write_text(_bundle_with_biored_records().model_dump_json(indent=2), encoding="utf-8")

    exit_code = run_biored_cli(
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
    assert payload["relation_novelty"]["f1"] == 1.0
