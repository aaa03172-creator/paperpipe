from __future__ import annotations

from pathlib import Path

from scripts.eval.check_local_pdf_ingest_index_oracle import (
    build_chunk_summary,
    build_run_summary,
    evaluate_expectations,
)
from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2


def _fake_doc() -> DocumentArtifactV2:
    pages = []
    for page_index in range(2):
        text = ("Human-derived systems support translational drug development. " * 35).strip()
        pages.append(
            PageV2(
                page_index=page_index,
                width=595.0,
                height=842.0,
                blocks=[
                    BlockV2(
                        block_id=f"b{page_index}",
                        lines=[
                            LineV2(
                                line_id=f"l{page_index}",
                                text=text,
                                spans=[SpanV2(span_id=f"s{page_index}", text=text)],
                            )
                        ],
                    )
                ],
            )
        )
    return DocumentArtifactV2(
        document_id="file:fake.pdf",
        meta=ArtifactMetaV2(
            title="Reimagining human-centric drug development with new approach methodologies",
            year=2026,
            journal="Science",
            source_ref="/tmp/fake.pdf",
        ),
        pages=pages,
        tables=[],
    )


def test_build_chunk_summary_preserves_page_hinted_chunk_ids() -> None:
    summary = build_chunk_summary(_fake_doc())

    assert summary["chunk_count"] >= 4
    assert summary["chunks_with_page_hint"] == summary["chunk_count"]
    assert "p01_c01" in summary["first_chunk_ids"]
    assert summary["page_chunk_counts"]["1"] >= 2


def test_evaluate_expectations_passes_science_review_contract() -> None:
    doc = _fake_doc()
    chunk_summary = build_chunk_summary(doc)
    document_summary = {
        "title": doc.meta.title,
        "page_count": len(doc.pages),
        "table_count": len(doc.tables),
    }

    decision = evaluate_expectations(
        document_summary=document_summary,
        chunk_summary=chunk_summary,
        expected={
            "title_contains": "human-centric drug development",
            "page_count": 2,
            "table_count": 0,
            "min_chunk_count": 4,
            "require_page_hints": True,
            "required_chunk_ids": ["p01_c01"],
        },
        actual_sha256="abc",
        expected_sha256="abc",
    )

    assert decision["passed"] is True
    assert decision["checks"]["source_pdf_sha256"]["passed"] is True


def test_build_run_summary_marks_failed_documents() -> None:
    summary = build_run_summary(
        manifest={"manifest_batch_id": "fixture"},
        details=[
            {"document_id": "ok", "status": "completed", "decision": {"passed": True}},
            {"document_id": "bad", "status": "missing_pdf", "decision": {"passed": False}},
        ],
        manifest_path=Path("/tmp/manifest.json"),
        run_id="run-fixture",
    )

    assert summary["decision"]["passed"] is False
    assert summary["decision"]["failed_documents"] == ["bad"]
    assert summary["passed_count"] == 1
    assert summary["failed_count"] == 1
