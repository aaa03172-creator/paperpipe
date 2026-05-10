import json
from pathlib import Path

from src.quality.teacher_review import build_prediction_row, review_teacher_bundle, select_context_chunks


def _write_bundle(bundle_dir: Path) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "teacher_bundle.v1",
                "paper_id": "zotero:testPaper2026",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    prior_output = {
        "summary": "Prior summary",
        "claimset_json": {
            "doc_id": "doc:test",
            "claims": [
                {
                    "claim_id": "CLM-OLD-1",
                    "type": "finding",
                    "statement": "Bilingualism is associated with a delay in dementia symptoms.",
                    "evidence_spans": [
                        {
                            "page": 5,
                            "section": "page_5",
                            "source_span": [18, 95],
                            "raw_text": "We discuss recent evidence that bilingualism is associated with a delay in the onset of symptoms of dementia.",
                            "quote": "delay in the onset of symptoms of dementia",
                            "rationale": "Source statement directly supports the claim.",
                        }
                    ],
                    "limitations": [],
                    "confidence": 0.8,
                }
            ],
        },
    }
    (bundle_dir / "prior_output.json").write_text(json.dumps(prior_output, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle_dir / "tables.json").write_text("[]", encoding="utf-8")
    chunks = [
        {
            "chunk_id": "chunk-page-1",
            "section_name": "page_1",
            "text": "Introductory material.",
        },
        {
            "chunk_id": "chunk-page-5",
            "section_name": "page_5",
            "text": "We discuss recent evidence that bilingualism is associated with a delay in the onset of symptoms of dementia. Additional source details.",
        },
    ]
    with (bundle_dir / "input_chunks.jsonl").open("w", encoding="utf-8") as handle:
        for row in chunks:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_select_context_chunks_prioritizes_prior_evidence_pages(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_bundle(bundle_dir)

    from src.quality.teacher_review import load_teacher_bundle

    bundle = load_teacher_bundle(bundle_dir)
    selected = select_context_chunks(bundle, max_chunks=1, max_chars=5000)

    assert len(selected) == 1
    assert selected[0].chunk_id == "chunk-page-5"


def test_review_teacher_bundle_augments_locations_and_filters_unsupported_claims(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_bundle(bundle_dir)

    def fake_llm(prompt: str, system_prompt: str) -> str:
        assert "Expected doc_id: doc:test" in prompt
        assert "chunk-page-5" in prompt
        assert "conservative teacher reviewer" in system_prompt.lower()
        return json.dumps(
            {
                "doc_id": "wrong-doc",
                "claims": [
                    {
                        "claim_id": "CLM-001",
                        "type": "finding",
                        "statement": "Bilingualism is associated with a delay in dementia symptoms.",
                        "evidence_spans": [
                            {
                                "raw_text": "We discuss recent evidence that bilingualism is associated with a delay in the onset of symptoms of dementia.",
                                "quote": "delay in the onset of symptoms of dementia",
                                "rationale": "The source sentence states the association.",
                            }
                        ],
                        "limitations": [],
                        "confidence": 0.84,
                    },
                    {
                        "claim_id": "CLM-002",
                        "type": "finding",
                        "statement": "Unsupported claim should be dropped.",
                        "evidence_spans": [
                            {
                                "raw_text": "This sentence does not exist in the source bundle.",
                                "quote": "does not exist in the source bundle",
                                "rationale": "Unsupported.",
                            }
                        ],
                        "limitations": [],
                        "confidence": 0.72,
                    },
                ],
            },
            ensure_ascii=False,
        )

    result = review_teacher_bundle(bundle_dir=bundle_dir, llm_callable=fake_llm)
    claimset = result["claimset"]

    assert claimset.doc_id == "doc:test"
    assert len(claimset.claims) == 1
    span = claimset.claims[0].evidence_spans[0]
    assert span.page == 5
    assert span.chunk_id == "chunk-page-5"
    assert span.section == "page_5"
    assert span.source_span is not None
    assert span.source_span[0] == 0
    matched = "We discuss recent evidence that bilingualism is associated with a delay in the onset of symptoms of dementia."
    source_text = "We discuss recent evidence that bilingualism is associated with a delay in the onset of symptoms of dementia. Additional source details."
    assert source_text[span.source_span[0] : span.source_span[1]] == matched
    assert result["output_path"].exists()
    assert result["meta_path"].exists()
    assert result["raw_path"].exists()


def test_build_prediction_row_uses_teacher_output_contract(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_bundle(bundle_dir)

    def fake_llm(_: str, __: str) -> str:
        return json.dumps(
            {
                "doc_id": "doc:test",
                "claims": [
                    {
                        "claim_id": "CLM-001",
                        "type": "finding",
                        "statement": "Bilingualism is associated with a delay in dementia symptoms.",
                        "evidence_spans": [
                            {
                                "raw_text": "We discuss recent evidence that bilingualism is associated with a delay in the onset of symptoms of dementia.",
                                "quote": "delay in the onset of symptoms of dementia",
                                "rationale": "The source sentence states the association.",
                            }
                        ],
                        "limitations": [],
                        "confidence": 0.84,
                    }
                ],
            },
            ensure_ascii=False,
        )

    result = review_teacher_bundle(bundle_dir=bundle_dir, llm_callable=fake_llm)
    row = build_prediction_row(result)

    assert row["paper_id"] == "zotero:testPaper2026"
    assert row["teacher_output"]["doc_id"] == "doc:test"
    assert row["summary"] == "Prior summary"
    assert row["bundle_dir"] == str(bundle_dir)
    assert row["teacher_output_path"].endswith("teacher_output.json")
