from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.generate_bc5cdr_bundle_predictions import generate_predictions
from src.schemas.bc5cdr_eval import BC5CDRDocument
from src.services.bc5cdr_prediction import build_bc5cdr_prediction_inputs, repair_bc5cdr_prediction_payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_bc5cdr_prediction_inputs_extracts_title_and_abstract_from_pages(tmp_path: Path) -> None:
    document_artifact = tmp_path / "document_artifact.json"
    _write_json(
        document_artifact,
        {
            "pages": [
                {
                    "blocks": [
                        {"lines": [{"text": "Aspirin and headache"}]},
                        {"lines": [{"text": "Aspirin can induce headache in some patients."}]},
                    ]
                }
            ]
        },
    )

    paper = build_bc5cdr_prediction_inputs(document_artifact, paper_id="paper-1")

    assert paper["title"] == "Aspirin and headache"
    assert "Aspirin can induce headache" in paper["abstract"]


def test_build_bc5cdr_prediction_inputs_reads_section_artifacts(tmp_path: Path) -> None:
    document_artifact = tmp_path / "document_artifact.json"
    _write_json(
        document_artifact,
        {
            "sections": [
                {"name": "page_1", "text": "Title line\nAspirin can induce headache in some patients."},
                {"name": "page_2", "text": "Additional abstract detail."},
            ]
        },
    )

    paper = build_bc5cdr_prediction_inputs(document_artifact, paper_id="paper-1")

    assert paper["title"] == "Title line"
    assert "Additional abstract detail" in paper["abstract"]


def test_repair_bc5cdr_prediction_payload_fills_ids_offsets_and_relation_endpoints() -> None:
    abstract = "Aspirin can induce headache."
    repaired = repair_bc5cdr_prediction_payload(
        {
            "mentions": [
                {"entity_type": "drug", "text": "Aspirin"},
                {"entity_type": "condition", "text": "headache"},
            ],
            "relations": [
                {
                    "type": "chemical induced disease",
                    "chemical_text": "Aspirin",
                    "disease_text": "headache",
                }
            ],
        },
        paper_id="paper-1",
        abstract_text=abstract,
        default_title="Aspirin paper",
    )
    validated = BC5CDRDocument.model_validate(repaired)

    assert validated.doc_id == "paper-1"
    assert len(validated.mentions) == 2
    assert validated.mentions[0].char_start == 0
    assert validated.mentions[0].char_end == 7
    assert len(validated.relations) == 1
    assert validated.relations[0].chemical_mention_id == validated.mentions[0].mention_id
    assert validated.relations[0].disease_mention_id == validated.mentions[1].mention_id


def test_repair_bc5cdr_prediction_payload_uses_distinct_spans_for_repeated_mentions() -> None:
    abstract = "Aspirin caused headache, and aspirin worsened headache."
    repaired = repair_bc5cdr_prediction_payload(
        {
            "mentions": [
                {"entity_type": "chemical", "text": "Aspirin"},
                {"entity_type": "disease", "text": "headache"},
                {"entity_type": "chemical", "text": "aspirin"},
                {"entity_type": "disease", "text": "headache"},
            ],
            "relations": [],
        },
        paper_id="paper-1",
        abstract_text=abstract,
        default_title="Repeated mentions",
    )
    validated = BC5CDRDocument.model_validate(repaired)

    spans = [(mention.char_start, mention.char_end) for mention in validated.mentions]
    assert spans[0] == (0, 7)
    assert spans[1] == (15, 23)
    assert spans[2] == (29, 36)
    assert spans[3] == (46, 54)


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

        if "Aspirin induced gastritis in adults." in prompt:
            payload = {
                "mentions": [
                    {"entity_type": "drug", "text": "Aspirin", "normalized_id": "MESH:C0004057"},
                    {"entity_type": "condition", "text": "gastritis", "normalized_id": "MESH:D005756"},
                ],
                "relations": [
                    {
                        "type": "CID",
                        "chemical_text": "Aspirin",
                        "disease_text": "gastritis",
                    }
                ],
            }
        elif "Ibuprofen caused rash after treatment." in prompt:
            payload = {
                "mentions": [
                    {"entity_type": "chemical", "text": "Ibuprofen", "normalized_id": "MESH:C0020740"},
                    {"entity_type": "disease", "text": "rash", "normalized_id": "MESH:D012871"},
                ],
                "relations": [
                    {
                        "type": "chemical induced disease",
                        "chemical_text": "Ibuprofen",
                        "disease_text": "rash",
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
            "title": "Aspirin and headache",
            "abstract": "Aspirin can induce headache.",
            "mentions": [
                {
                    "mention_id": "chem-1",
                    "entity_type": "chemical",
                    "text": "Aspirin",
                    "char_start": 0,
                    "char_end": 7,
                    "normalized_id": "MESH:C0004057",
                },
                {
                    "mention_id": "disease-1",
                    "entity_type": "disease",
                    "text": "headache",
                    "char_start": 19,
                    "char_end": 27,
                    "normalized_id": "MESH:D006261",
                },
            ],
            "relations": [
                {
                    "relation_id": "rel-1",
                    "relation_type": "chemical_induced_disease",
                    "chemical_mention_id": "chem-1",
                    "disease_mention_id": "disease-1",
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
                        {"lines": [{"text": "Aspirin and headache"}]},
                        {"lines": [{"text": "Aspirin can induce headache."}]},
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
                {"entity_type": "chemical", "text": "Aspirin"},
                {"entity_type": "disease", "text": "headache"},
            ],
            "relations": [
                {
                    "chemical_text": "Aspirin",
                    "disease_text": "headache",
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


def test_generate_predictions_replays_repo_manifest(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "goldset" / "manifests" / "bc5cdr_prediction_repo_grounded_pilot_20260413.json"

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

    assert generated_manifest["source_manifest"] == str(manifest_path)
    assert len(generated_manifest["documents"]) == 2
    assert metrics["success_count"] == 2

    rows_by_paper = {row["paper_id"]: row for row in metrics["rows"]}
    assert rows_by_paper["repo-bc5cdr-aspirin-gastritis"]["mention_exact_f1"] == 1.0
    assert rows_by_paper["repo-bc5cdr-aspirin-gastritis"]["mention_normalized_f1"] == 1.0
    assert rows_by_paper["repo-bc5cdr-aspirin-gastritis"]["relation_f1"] == 1.0
    assert rows_by_paper["repo-bc5cdr-ibuprofen-rash"]["mention_exact_f1"] == 1.0
    assert rows_by_paper["repo-bc5cdr-ibuprofen-rash"]["mention_normalized_f1"] == 1.0
    assert rows_by_paper["repo-bc5cdr-ibuprofen-rash"]["relation_f1"] == 1.0

    bundle_path = Path(rows_by_paper["repo-bc5cdr-ibuprofen-rash"]["bundle_path"])
    assert bundle_path.exists()
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["doc_id"] == "repo-bc5cdr-ibuprofen-rash"
