from __future__ import annotations

import json
from pathlib import Path

from scripts.rebuild_vector_index import main


def _write_run(artifacts: Path) -> None:
    run_dir = artifacts / "paper-alpha" / "run-one"
    run_dir.mkdir(parents=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "status": "succeeded",
                "paper_id": "doc-alpha",
                "finished_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "document_artifact.json").write_text(
        json.dumps(
            {
                "document_id": "doc-alpha",
                "meta": {
                    "title": "Alpha",
                    "authors": [],
                    "source_ref": "alpha.pdf",
                },
                "pages": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "index_artifact.json").write_text(
        json.dumps({"doc_id": "doc-alpha", "chunk_count": 2, "chunks": []}),
        encoding="utf-8",
    )


def test_rebuild_vector_index_script_defaults_to_dry_run(tmp_path: Path, capsys):
    artifacts = tmp_path / "artifacts"
    vector_root = tmp_path / "rag"
    backup_root = tmp_path / "backups"
    vector_root.mkdir()
    _write_run(artifacts)

    exit_code = main(
        [
            "--artifact-root",
            str(artifacts),
            "--vector-root",
            str(vector_root),
            "--backup-root",
            str(backup_root),
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "status=dry_run" in output
    assert "candidate_count=1" in output
    assert "will_modify_chroma=False" in output
    assert not backup_root.exists()
    assert sorted(vector_root.iterdir()) == []


def test_rebuild_vector_index_script_refuses_apply_without_confirmation(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    vector_root = tmp_path / "rag"
    backup_root = tmp_path / "backups"
    output = tmp_path / "out.json"
    vector_root.mkdir()
    _write_run(artifacts)

    exit_code = main(
        [
            "--artifact-root",
            str(artifacts),
            "--vector-root",
            str(vector_root),
            "--backup-root",
            str(backup_root),
            "--apply",
            "--json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["status"] == "refused"
    assert payload["plan"]["will_modify_chroma"] is False
    assert payload["plan"]["candidate_count"] == 1
    assert not backup_root.exists()
    assert sorted(vector_root.iterdir()) == []


def test_rebuild_vector_index_script_preflight_failure_happens_before_backup(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    vector_root = tmp_path / "rag"
    backup_root = tmp_path / "backups"
    output = tmp_path / "out.json"
    run_dir = artifacts / "paper-bad" / "run-one"
    run_dir.mkdir(parents=True)
    vector_root.mkdir()
    (vector_root / "chroma.sqlite3").write_text("existing", encoding="utf-8")
    (run_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "bad-shape"}), encoding="utf-8")
    (run_dir / "index_artifact.json").write_text(json.dumps({"chunk_count": 1}), encoding="utf-8")

    exit_code = main(
        [
            "--artifact-root",
            str(artifacts),
            "--vector-root",
            str(vector_root),
            "--backup-root",
            str(backup_root),
            "--apply",
            "--confirm",
            "REBUILD_LOCAL_CHROMA",
            "--json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert "Preflight failed before backup/delete" in payload["error"]
    assert not backup_root.exists()
    assert (vector_root / "chroma.sqlite3").read_text(encoding="utf-8") == "existing"


def test_rebuild_vector_index_script_refuses_apply_when_no_candidates(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    vector_root = tmp_path / "rag"
    backup_root = tmp_path / "backups"
    output = tmp_path / "out.json"
    artifacts.mkdir()
    vector_root.mkdir()
    (vector_root / "chroma.sqlite3").write_text("existing", encoding="utf-8")

    exit_code = main(
        [
            "--artifact-root",
            str(artifacts),
            "--vector-root",
            str(vector_root),
            "--backup-root",
            str(backup_root),
            "--apply",
            "--confirm",
            "REBUILD_LOCAL_CHROMA",
            "--json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert "No rebuild candidates found" in payload["error"]
    assert not backup_root.exists()
    assert (vector_root / "chroma.sqlite3").read_text(encoding="utf-8") == "existing"


def test_rebuild_vector_index_script_restores_backup_after_index_failure(tmp_path: Path, monkeypatch):
    artifacts = tmp_path / "artifacts"
    vector_root = tmp_path / "rag"
    backup_root = tmp_path / "backups"
    output = tmp_path / "out.json"
    vector_root.mkdir()
    (vector_root / "chroma.sqlite3").write_text("existing", encoding="utf-8")
    _write_run(artifacts)

    class FakeCollection:
        def get(self, **_kwargs):
            return {"ids": ["old-vector"]}

        def delete(self, ids):
            assert ids == ["old-vector"]

    class FailingIndexer:
        def __init__(self, *, persist_path=None):
            self.persist_path = Path(persist_path)
            self.collection = FakeCollection()

        def process(self, _doc):
            (self.persist_path / "chroma.sqlite3").write_text("partial", encoding="utf-8")
            raise RuntimeError("embedding service unavailable")

    import src.agents.indexer_agent as indexer_module

    monkeypatch.setattr(indexer_module, "IndexerAgent", FailingIndexer)

    exit_code = main(
        [
            "--artifact-root",
            str(artifacts),
            "--vector-root",
            str(vector_root),
            "--backup-root",
            str(backup_root),
            "--apply",
            "--confirm",
            "REBUILD_LOCAL_CHROMA",
            "--json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["result"]["applied"] is False
    assert payload["result"]["restored_from_backup"] is True
    assert payload["result"]["failure_count"] == 1
    assert "embedding service unavailable" in payload["result"]["failures"][0]["error"]
    assert (vector_root / "chroma.sqlite3").read_text(encoding="utf-8") == "existing"
    backups = list(backup_root.glob("rag_before_rebuild_*"))
    assert len(backups) == 1
    assert (backups[0] / "chroma.sqlite3").read_text(encoding="utf-8") == "existing"
