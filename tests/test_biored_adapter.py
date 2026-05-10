from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.convert_biored_to_evidence_bundle import main as run_biored_convert_cli
from src.schemas.biored_eval import BioREDDocument, BioREDMention, BioREDRelation
from src.services.biored_adapter import project_biored_to_evidence_extraction_bundle
from src.services.biored_eval import evaluate_biored_bundle, project_bundle_to_biored_document


def _gold_doc() -> BioREDDocument:
    return BioREDDocument(
        doc_id="biored-doc-1",
        title="EGFR variant predicts response",
        abstract="EGFR p.L858R sensitizes tumors to gefitinib in lung cancer.",
        mentions=[
            BioREDMention(
                mention_id="gene-1",
                entity_type="GeneOrGeneProduct",
                text="EGFR",
                char_start=0,
                char_end=4,
                normalized_ids=["NCBIGene:1956"],
            ),
            BioREDMention(
                mention_id="variant-1",
                entity_type="SequenceVariant",
                text="p.L858R",
                char_start=5,
                char_end=12,
                normalized_ids=["dbSNP:rs121913445"],
            ),
            BioREDMention(
                mention_id="chemical-1",
                entity_type="ChemicalEntity",
                text="gefitinib",
                char_start=35,
                char_end=44,
                normalized_ids=["MESH:C1100"],
            ),
            BioREDMention(
                mention_id="disease-1",
                entity_type="DiseaseOrPhenotypicFeature",
                text="lung cancer",
                char_start=48,
                char_end=59,
                normalized_ids=["MESH:D002283"],
            ),
        ],
        relations=[
            BioREDRelation(
                relation_id="rel-1",
                relation_type="Positive_Correlation",
                head_mention_id="gene-1",
                tail_mention_id="chemical-1",
                novelty="novel",
            )
        ],
    )


def test_project_biored_to_evidence_extraction_bundle_creates_entity_relation_and_novelty_metadata():
    bundle = project_biored_to_evidence_extraction_bundle(_gold_doc(), run_id="run-biored")

    assert bundle.paper_id == "biored-doc-1"
    assert bundle.doc_id == "biored-doc-1"
    assert bundle.metrics.entity_record_count == 4
    assert bundle.metrics.relation_record_count == 1
    relation_record = next(record for record in bundle.records if record.record_type == "relation")
    assert relation_record.metadata["head_record_id"] == "entity:gene-1"
    assert relation_record.metadata["tail_record_id"] == "entity:chemical-1"
    assert relation_record.metadata["novelty"] == "novel"


def test_biored_adapter_roundtrips_through_bundle_projection_and_eval():
    gold = _gold_doc()
    bundle = project_biored_to_evidence_extraction_bundle(gold)

    projected_doc, warnings = project_bundle_to_biored_document(bundle)
    report = evaluate_biored_bundle(gold_document=gold, bundle=bundle)

    assert warnings == []
    assert projected_doc.doc_id == gold.doc_id
    assert len(projected_doc.mentions) == 4
    assert len(projected_doc.relations) == 1
    assert report.mention_exact.f1 == 1.0
    assert report.mention_normalized.f1 == 1.0
    assert report.relation.f1 == 1.0
    assert report.relation_novelty.f1 == 1.0


def test_convert_biored_to_evidence_bundle_cli_writes_bundle(tmp_path: Path):
    input_path = tmp_path / "biored.json"
    out_dir = tmp_path / "out"
    input_path.write_text(_gold_doc().model_dump_json(indent=2), encoding="utf-8")

    exit_code = run_biored_convert_cli(
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
    assert payload["metrics"]["entity_record_count"] == 4
    assert payload["metrics"]["relation_record_count"] == 1
