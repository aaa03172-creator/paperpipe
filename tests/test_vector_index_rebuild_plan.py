from __future__ import annotations

import json
from pathlib import Path

from src.services.vector_index_rebuild import (
    build_vector_rebuild_dry_run_plan,
    collect_vector_rebuild_candidates,
    validate_vector_rebuild_candidates,
)


def _write_run(
    artifacts: Path,
    paper_segment: str,
    run_id: str,
    *,
    document_id: str,
    finished_at: str,
    chunk_count: int,
) -> None:
    run_dir = artifacts / paper_segment / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps({"status": "succeeded", "paper_id": document_id, "finished_at": finished_at}),
        encoding="utf-8",
    )
    (run_dir / "document_artifact.json").write_text(
        json.dumps(
            {
                "document_id": document_id,
                "meta": {"title": document_id, "authors": [], "source_ref": "/tmp/paper.pdf"},
                "pages": [],
                "tables": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "index_artifact.json").write_text(
        json.dumps({"doc_id": document_id, "chunk_count": chunk_count, "chunks": []}),
        encoding="utf-8",
    )


def _write_legacy_run(artifacts: Path, paper_segment: str, run_id: str, *, doc_id: str) -> None:
    run_dir = artifacts / paper_segment / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "document_artifact.json").write_text(
        json.dumps(
            {
                "doc_id": doc_id,
                "source": {"type": "pdf", "ref": "/tmp/paper.pdf"},
                "metadata": {"title": "Legacy", "authors": []},
                "sections": [
                    {
                        "name": "abstract",
                        "text": "Legacy text",
                        "char_start": 0,
                        "char_end": 11,
                    }
                ],
                "tables": [],
            }
        ),
        encoding="utf-8",
    )


def test_collect_vector_rebuild_candidates_keeps_latest_run_per_document(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    _write_run(
        artifacts,
        "paper-alpha",
        "run-old",
        document_id="doc-alpha",
        finished_at="2026-01-01T00:00:00Z",
        chunk_count=2,
    )
    _write_run(
        artifacts,
        "paper-alpha",
        "run-new",
        document_id="doc-alpha",
        finished_at="2026-01-02T00:00:00Z",
        chunk_count=3,
    )
    _write_run(
        artifacts,
        "paper-beta",
        "run-one",
        document_id="doc-beta",
        finished_at="2026-01-01T12:00:00Z",
        chunk_count=4,
    )

    candidates = collect_vector_rebuild_candidates(artifact_root=artifacts)

    assert [(item.document_id, item.run_id, item.chunk_count) for item in candidates] == [
        ("doc-alpha", "run-new", 3),
        ("doc-beta", "run-one", 4),
    ]


def test_build_vector_rebuild_dry_run_plan_does_not_create_backup_or_modify_chroma(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    vector_root = tmp_path / "rag"
    backup_root = tmp_path / "backups"
    vector_root.mkdir()
    _write_run(
        artifacts,
        "paper-alpha",
        "run-one",
        document_id="doc-alpha",
        finished_at="2026-01-01T00:00:00Z",
        chunk_count=2,
    )

    plan = build_vector_rebuild_dry_run_plan(
        artifact_root=artifacts,
        vector_root=vector_root,
        backup_root=backup_root,
    )

    assert plan["dry_run"] is True
    assert plan["will_modify_chroma"] is False
    assert plan["vector_root"] == str(vector_root.resolve())
    assert plan["backup_root"] == str(backup_root.resolve())
    assert plan["candidate_count"] == 1
    assert plan["total_candidate_chunks"] == 2
    assert plan["candidates"][0]["document_id"] == "doc-alpha"
    assert plan["candidates_sample"][0]["document_id"] == "doc-alpha"
    assert not backup_root.exists()
    assert sorted(vector_root.iterdir()) == []


def test_validate_vector_rebuild_candidates_accepts_v1_and_v2_artifacts(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    _write_run(
        artifacts,
        "paper-v2",
        "run-one",
        document_id="doc-v2",
        finished_at="2026-01-01T00:00:00Z",
        chunk_count=2,
    )
    _write_legacy_run(artifacts, "paper-v1", "run-one", doc_id="doc-v1")
    (artifacts / "paper-bad" / "run-one").mkdir(parents=True)
    (artifacts / "paper-bad" / "run-one" / "document_artifact.json").write_text(
        json.dumps({"not": "a document artifact"}),
        encoding="utf-8",
    )
    candidates = [
        {
            "document_artifact_path": "paper-v2/run-one/document_artifact.json",
        },
        {
            "document_artifact_path": "paper-v1/run-one/document_artifact.json",
        },
        {
            "document_artifact_path": "paper-bad/run-one/document_artifact.json",
        },
    ]

    result = validate_vector_rebuild_candidates(artifact_root=artifacts, candidates=candidates)

    assert result["valid_count"] == 2
    assert result["v1_count"] == 1
    assert result["v2_count"] == 1
    assert result["failure_count"] == 1
    assert result["failures"][0]["document_artifact_path"] == "paper-bad/run-one/document_artifact.json"


def test_validate_vector_rebuild_candidates_accepts_minimal_hybrid_page_artifact(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    run_dir = artifacts / "paper-hybrid" / "run-one"
    run_dir.mkdir(parents=True)
    (run_dir / "document_artifact.json").write_text(
        json.dumps(
            {
                "doc_id": "doc-hybrid",
                "pages": [
                    {
                        "page_index": 0,
                        "width": 100.0,
                        "height": 100.0,
                        "blocks": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = validate_vector_rebuild_candidates(
        artifact_root=artifacts,
        candidates=[{"document_artifact_path": "paper-hybrid/run-one/document_artifact.json"}],
    )

    assert result["valid_count"] == 1
    assert result["v1_count"] == 0
    assert result["v2_count"] == 1
    assert result["failure_count"] == 0
