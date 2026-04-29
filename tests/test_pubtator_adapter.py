from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.convert_pubtator_to_evidence_bundle import main as run_pubtator_convert_cli
from src.services.pubtator_adapter import load_pubtator_document, project_pubtator_to_evidence_extraction_bundle


def _sample_pubtator_payload() -> dict:
    return {
        "documents": [
            {
                "id": "pubtator-doc-1",
                "passages": [
                    {
                        "offset": 0,
                        "infons": {"type": "title"},
                        "text": "EGFR variant predicts response",
                    },
                    {
                        "offset": 0,
                        "infons": {"type": "abstract"},
                        "text": "EGFR p.L858R sensitizes tumors to gefitinib in lung cancer.",
                        "annotations": [
                            {
                                "id": "T1",
                                "infons": {"type": "Gene", "identifier": "NCBIGene:1956"},
                                "text": "EGFR",
                                "locations": [{"offset": 0, "length": 4}],
                            },
                            {
                                "id": "T2",
                                "infons": {"type": "SequenceVariant", "identifier": "dbSNP:rs121913445"},
                                "text": "p.L858R",
                                "locations": [{"offset": 5, "length": 7}],
                            },
                            {
                                "id": "T3",
                                "infons": {"type": "Chemical", "identifier": "MESH:C1100"},
                                "text": "gefitinib",
                                "locations": [{"offset": 34, "length": 9}],
                            },
                            {
                                "id": "T4",
                                "infons": {"type": "Disease", "identifier": "MESH:D002283"},
                                "text": "lung cancer",
                                "locations": [{"offset": 47, "length": 11}],
                            },
                        ],
                        "relations": [
                            {
                                "id": "R1",
                                "infons": {"type": "Positive_Correlation", "novelty": "novel"},
                                "nodes": [{"refid": "T1", "role": "head"}, {"refid": "T3", "role": "tail"}],
                            }
                        ],
                    },
                ],
            }
        ]
    }


def test_load_pubtator_document_accepts_single_document_bioc_collection(tmp_path: Path) -> None:
    input_path = tmp_path / "pubtator.json"
    input_path.write_text(json.dumps(_sample_pubtator_payload(), ensure_ascii=False, indent=2), encoding="utf-8")

    document = load_pubtator_document(input_path)

    assert document.doc_id == "pubtator-doc-1"
    assert len(document.passages) == 2
    assert document.passages[1].annotations[0].annotation_id == "T1"
    assert document.passages[1].relations[0].relation_id == "R1"


def test_project_pubtator_to_evidence_extraction_bundle_marks_silver_bootstrap(tmp_path: Path) -> None:
    input_path = tmp_path / "pubtator.json"
    input_path.write_text(json.dumps(_sample_pubtator_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    document = load_pubtator_document(input_path)

    bundle = project_pubtator_to_evidence_extraction_bundle(document, run_id="pubtator-run")

    assert bundle.doc_id == "pubtator-doc-1"
    assert bundle.metrics.entity_record_count == 4
    assert bundle.metrics.relation_record_count == 1
    assert bundle.warnings == ["silver_bootstrap:pubtator_central"]

    entity_record = next(record for record in bundle.records if record.record_id == "entity:T1")
    relation_record = next(record for record in bundle.records if record.record_id == "relation:R1")
    assert entity_record.metadata["bootstrap_tier"] == "silver"
    assert entity_record.metadata["annotation_source"] == "pubtator_central"
    assert entity_record.metadata["entity_type"] == "GeneOrGeneProduct"
    assert relation_record.metadata["head_record_id"] == "entity:T1"
    assert relation_record.metadata["tail_record_id"] == "entity:T3"
    assert "bootstrap:silver" in relation_record.tags


def test_convert_pubtator_to_evidence_bundle_cli_writes_bundle_from_repo_sample(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = repo_root / "goldset" / "pubtator_silver" / "repo_grounded_pilot_20260409" / "source" / "repo_egfr_pubtator.json"
    out_dir = tmp_path / "out"

    exit_code = run_pubtator_convert_cli(
        [
            "--input",
            str(input_path),
            "--out-dir",
            str(out_dir),
            "--run-id",
            "pubtator-cli",
        ]
    )

    assert exit_code == 0
    bundle_path = out_dir / "evidence_extraction_bundle.json"
    assert bundle_path.exists()
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "pubtator-cli"
    assert payload["metrics"]["entity_record_count"] == 4
    assert payload["metrics"]["relation_record_count"] == 1
    assert payload["warnings"] == ["silver_bootstrap:pubtator_central"]


def test_project_pubtator_to_evidence_extraction_bundle_skips_relations_with_unsupported_endpoints(tmp_path: Path) -> None:
    payload = _sample_pubtator_payload()
    payload["documents"][0]["passages"][1]["annotations"].append(
        {
            "id": "T5",
            "infons": {"type": "CellType", "identifier": "CL:0000540"},
            "text": "tumor cell",
            "locations": [{"offset": 20, "length": 10}],
        }
    )
    payload["documents"][0]["passages"][1]["relations"] = [
        {
            "id": "R2",
            "infons": {"type": "Association"},
            "nodes": [{"refid": "T1", "role": "head"}, {"refid": "T5", "role": "tail"}],
        }
    ]
    input_path = tmp_path / "pubtator.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    document = load_pubtator_document(input_path)

    bundle = project_pubtator_to_evidence_extraction_bundle(document, run_id="pubtator-run")

    assert bundle.metrics.entity_record_count == 4
    assert bundle.metrics.relation_record_count == 0
    assert all(record.record_type != "relation" for record in bundle.records)
