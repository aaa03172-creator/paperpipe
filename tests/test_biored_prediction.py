from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.generate_biored_bundle_predictions import generate_predictions
from src.schemas.biored_eval import BioREDDocument
from src.services.biored_prediction import build_biored_prediction_inputs, repair_biored_prediction_payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_biored_prediction_inputs_extracts_title_and_abstract_from_pages(tmp_path: Path) -> None:
    document_artifact = tmp_path / "document_artifact.json"
    _write_json(
        document_artifact,
        {
            "pages": [
                {
                    "blocks": [
                        {"lines": [{"text": "EGFR variant predicts response"}]},
                        {"lines": [{"text": "EGFR p.L858R predicts response to gefitinib in lung cancer."}]},
                    ]
                }
            ]
        },
    )

    paper = build_biored_prediction_inputs(document_artifact, paper_id="paper-1")

    assert paper["title"] == "EGFR variant predicts response"
    assert "predicts response to gefitinib" in paper["abstract"]


def test_repair_biored_prediction_payload_fills_ids_offsets_relation_endpoints_and_novelty() -> None:
    abstract = "EGFR p.L858R sensitizes tumors to gefitinib in lung cancer."
    repaired = repair_biored_prediction_payload(
        {
            "mentions": [
                {"type": "gene", "text": "EGFR", "normalized_ids": "NCBIGene:1956"},
                {"type": "sequence variant", "text": "p.L858R", "normalized_ids": ["dbSNP:rs121913445"]},
                {"type": "drug", "text": "gefitinib", "normalized_ids": "MESH:C1100"},
                {"type": "disease", "text": "lung cancer", "normalized_ids": "MESH:D002283"},
            ],
            "relations": [
                {
                    "type": "positive correlation",
                    "head_text": "EGFR",
                    "tail_text": "gefitinib",
                    "novelty": "new",
                }
            ],
        },
        paper_id="paper-1",
        abstract_text=abstract,
        default_title="EGFR paper",
    )
    validated = BioREDDocument.model_validate(repaired)

    assert validated.doc_id == "paper-1"
    assert len(validated.mentions) == 4
    assert validated.mentions[0].entity_type == "GeneOrGeneProduct"
    assert validated.mentions[0].char_start == 0
    assert validated.mentions[0].char_end == 4
    assert validated.mentions[2].entity_type == "ChemicalEntity"
    assert validated.mentions[2].normalized_ids == ["MESH:C1100"]
    assert len(validated.relations) == 1
    assert validated.relations[0].relation_type == "Positive_Correlation"
    assert validated.relations[0].novelty == "novel"
    assert validated.relations[0].head_mention_id == validated.mentions[0].mention_id
    assert validated.relations[0].tail_mention_id == validated.mentions[2].mention_id


def test_repair_biored_prediction_payload_uses_distinct_spans_for_repeated_mentions() -> None:
    abstract = "EGFR mutations keep EGFR sensitive to gefitinib."
    repaired = repair_biored_prediction_payload(
        {
            "mentions": [
                {"entity_type": "GeneOrGeneProduct", "text": "EGFR"},
                {"entity_type": "gene", "text": "EGFR"},
            ],
            "relations": [],
        },
        paper_id="paper-1",
        abstract_text=abstract,
        default_title="Repeated EGFR",
    )
    validated = BioREDDocument.model_validate(repaired)

    spans = [(mention.char_start, mention.char_end) for mention in validated.mentions]
    assert spans == [(0, 4), (20, 24)]


class _FakeClient:
    def __init__(self, payload: dict):
        self.payload = payload

    def chat(self, **_: object) -> dict:
        return {"message": {"content": json.dumps(self.payload)}}


class _ManifestFakeClient:
    def chat(self, **kwargs: object) -> dict:
        messages = kwargs.get("messages") or []
        prompt = ""
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            prompt = str(messages[0].get("content") or "")

        if "EGFR p.L858R sensitizes tumors to gefitinib in lung cancer." in prompt:
            payload = {
                "mentions": [
                    {"type": "gene", "text": "EGFR", "normalized_ids": ["NCBIGene:1956"]},
                    {"type": "sequence variant", "text": "p.L858R", "normalized_ids": ["dbSNP:rs121913445"]},
                    {"type": "chemical", "text": "gefitinib", "normalized_ids": ["MESH:C1100"]},
                    {"type": "disease", "text": "lung cancer", "normalized_ids": ["MESH:D002283"]},
                ],
                "relations": [
                    {
                        "type": "positive correlation",
                        "head_text": "EGFR",
                        "tail_text": "gefitinib",
                        "novelty": "novel",
                    }
                ],
            }
        elif "KRAS G12D is associated with pancreatic cancer." in prompt:
            payload = {
                "mentions": [
                    {"type": "gene", "text": "KRAS", "normalized_ids": ["NCBIGene:3845"]},
                    {"type": "variant", "text": "G12D", "normalized_ids": ["dbSNP:rs121913529"]},
                    {"type": "disease", "text": "pancreatic cancer", "normalized_ids": ["MESH:D010190"]},
                ],
                "relations": [
                    {
                        "type": "association",
                        "head_text": "G12D",
                        "tail_text": "pancreatic cancer",
                        "novelty": "known",
                    }
                ],
            }
        else:
            raise AssertionError(f"Unexpected prompt content: {prompt[:200]}")

        return {"message": {"content": json.dumps(payload)}}


def test_generate_predictions_writes_prediction_bundle_and_eval(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    source_path = tmp_path / "document_artifact.json"
    manifest_path = tmp_path / "manifest.json"

    _write_json(
        gold_path,
        {
            "doc_id": "paper-1",
            "title": "EGFR variant predicts response",
            "abstract": "EGFR predicts response to gefitinib in lung cancer.",
            "mentions": [
                {
                    "mention_id": "gene-1",
                    "entity_type": "GeneOrGeneProduct",
                    "text": "EGFR",
                    "char_start": 0,
                    "char_end": 4,
                    "normalized_ids": ["NCBIGene:1956"],
                },
                {
                    "mention_id": "chemical-1",
                    "entity_type": "ChemicalEntity",
                    "text": "gefitinib",
                    "char_start": 26,
                    "char_end": 35,
                    "normalized_ids": ["MESH:C1100"],
                },
            ],
            "relations": [
                {
                    "relation_id": "rel-1",
                    "relation_type": "Positive_Correlation",
                    "head_mention_id": "gene-1",
                    "tail_mention_id": "chemical-1",
                    "novelty": "novel",
                }
            ],
        },
    )
    _write_json(
        source_path,
        {
            "pages": [
                {
                    "blocks": [
                        {"lines": [{"text": "EGFR variant predicts response"}]},
                        {"lines": [{"text": "EGFR predicts response to gefitinib in lung cancer."}]},
                    ]
                }
            ]
        },
    )
    _write_json(
        manifest_path,
        {
            "documents": [
                {
                    "paper_id": "paper-1",
                    "gold_path": str(gold_path),
                    "gold_source_paths": [str(source_path)],
                }
            ]
        },
    )

    fake_client = _FakeClient(
        {
            "mentions": [
                {"type": "gene", "text": "EGFR", "normalized_ids": ["NCBIGene:1956"]},
                {"type": "chemical", "text": "gefitinib", "normalized_ids": ["MESH:C1100"]},
            ],
            "relations": [
                {
                    "type": "positive correlation",
                    "head_text": "EGFR",
                    "tail_text": "gefitinib",
                    "novelty": "novel",
                }
            ],
        }
    )

    run_root = generate_predictions(
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        run_id="run-1",
        model="fake-model",
        timeout_seconds=5,
        client=fake_client,
    )

    prediction_path = run_root / "predictions" / "paper-1.json"
    bundle_path = run_root / "bundles" / "paper-1" / "evidence_extraction_bundle.json"
    eval_path = run_root / "eval" / "paper-1.json"
    metrics_path = run_root / "metrics.json"

    assert prediction_path.exists()
    assert bundle_path.exists()
    assert eval_path.exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["success_count"] == 1
    assert metrics["rows"][0]["mention_exact_f1"] == 1.0
    assert metrics["rows"][0]["relation_f1"] == 1.0
    assert metrics["rows"][0]["relation_novelty_f1"] == 1.0


def test_generate_predictions_replays_repo_manifest(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "goldset" / "manifests" / "biored_prediction_repo_grounded_pilot_20260409.json"

    run_root = generate_predictions(
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        run_id="repo-manifest-run",
        model="fake-model",
        timeout_seconds=5,
        client=_ManifestFakeClient(),
    )

    generated_manifest = json.loads((run_root / "generated_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_root / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["success_count"] == 2
    assert generated_manifest["source_manifest"] == str(manifest_path)
    assert len(generated_manifest["documents"]) == 2

    rows_by_paper = {row["paper_id"]: row for row in metrics["rows"]}
    assert rows_by_paper["repo-biored-egfr-gefitinib"]["mention_exact_f1"] == 1.0
    assert rows_by_paper["repo-biored-egfr-gefitinib"]["relation_f1"] == 1.0
    assert rows_by_paper["repo-biored-kras-pancreatic"]["mention_exact_f1"] == 1.0
    assert rows_by_paper["repo-biored-kras-pancreatic"]["relation_f1"] == 1.0
    assert rows_by_paper["repo-biored-kras-pancreatic"]["relation_novelty_f1"] == 1.0
