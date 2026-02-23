import json

from fastapi.testclient import TestClient

from backend.main import app
from src.core.artifact_paths import build_artifact_dir


def test_obsidian_artifacts_api_prefers_resolved_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "doi:10.1000/api_resolved"
    run_id = "run_api_1"
    artifact_dir = build_artifact_dir(run_id=run_id, paper_id=paper_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    (artifact_dir / "claimset.resolved.json").write_text(
        json.dumps(
            {
                "paper_id": paper_id,
                "run_id": run_id,
                "stage": "resolved",
                "schema_version": "1.0",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_fingerprint": "fp1",
                        "text": "resolved claim",
                        "type": "efficacy",
                        "evidence": [{"chunk_id": "p01_c01", "quote": "q"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "claimset.json").write_text(
        json.dumps({"doc_id": "legacy_doc", "claims": []}),
        encoding="utf-8",
    )
    (artifact_dir / "chunks.json").write_text(
        json.dumps(
            {
                "paper_id": paper_id,
                "run_id": run_id,
                "schema_version": "1.0",
                "chunk_count": 1,
                "chunks": [{"chunk_id": "p01_c01", "page": 1, "text": "chunk text"}],
            }
        ),
        encoding="utf-8",
    )

    with TestClient(app) as client:
        resp = client.get("/obsidian/artifacts", params={"paper_id": paper_id, "run_id": run_id})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["claimset_source"] == "resolved"
    assert payload["claimset_resolved"]["stage"] == "resolved"
    assert payload["claimset_legacy"]["doc_id"] == paper_id
    assert payload["chunks"]["chunk_count"] == 1


def test_obsidian_artifacts_api_falls_back_to_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "doi:10.1000/api_legacy"
    run_id = "run_api_2"
    artifact_dir = build_artifact_dir(run_id=run_id, paper_id=paper_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "claimset.json").write_text(
        json.dumps({"doc_id": "legacy_doc", "claims": []}),
        encoding="utf-8",
    )

    with TestClient(app) as client:
        resp = client.get("/obsidian/artifacts", params={"paper_id": paper_id, "run_id": run_id})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["claimset_source"] == "legacy"
    assert payload["claimset_legacy"]["doc_id"] == "legacy_doc"
    assert payload["claimset_resolved"] is None
    assert payload["chunks"] is None


def test_obsidian_artifacts_api_returns_404_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with TestClient(app) as client:
        resp = client.get(
            "/obsidian/artifacts",
            params={"paper_id": "doi:10.1000/missing", "run_id": "run_api_3"},
        )
    assert resp.status_code == 404
