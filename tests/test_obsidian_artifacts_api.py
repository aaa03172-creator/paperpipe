import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import obsidian as obsidian_router


def test_obsidian_artifacts_prefers_resolved_claimset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    run_dir = tmp_path / "storage" / "artifacts" / "paper_obs_001" / "run_obs_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.json").write_text(json.dumps({"claims": ["legacy"]}), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(json.dumps({"claims": ["resolved"]}), encoding="utf-8")
    (run_dir / "stats_report.json").write_text(json.dumps({"checks": []}), encoding="utf-8")
    (run_dir / "chunks.jsonl").write_text(
        "\n".join([json.dumps({"chunk_id": "c1"}), json.dumps({"chunk_id": "c2"})]) + "\n",
        encoding="utf-8",
    )

    resp = client.get("/obsidian/artifacts", params={"paper_id": "paper_obs_001", "run_id": "run_obs_001"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["claimset_source"] == "claimset.resolved.json"
    assert payload["claimset"]["exists"] is True
    assert payload["claimset"]["data"]["claims"] == ["resolved"]
    assert payload["chunks"]["exists"] is True
    assert payload["chunks"]["data"]["line_count"] == 2
    assert len(payload["chunks"]["data"]["preview"]) == 2
    assert payload["stats_report"]["exists"] is True


def test_obsidian_artifacts_falls_back_to_legacy_claimset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    run_dir = tmp_path / "storage" / "artifacts" / "paper_obs_002" / "run_obs_002"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.json").write_text(json.dumps({"claims": ["legacy-only"]}), encoding="utf-8")

    resp = client.get("/obsidian/artifacts", params={"paper_id": "paper_obs_002", "run_id": "run_obs_002"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["claimset_source"] == "claimset.json"
    assert payload["claimset"]["exists"] is True
    assert payload["claimset"]["data"]["claims"] == ["legacy-only"]
    assert payload["chunks"]["exists"] is False
    assert payload["stats_report"]["exists"] is False


def test_obsidian_artifacts_returns_404_for_missing_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    resp = client.get("/obsidian/artifacts", params={"paper_id": "paper_missing", "run_id": "run_missing"})
    assert resp.status_code == 404


def test_obsidian_sync_prefers_resolved_claimset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    target_note = vault_dir / "paper_sync_001.md"
    target_note.write_text("# paper_sync_001\n", encoding="utf-8")

    monkeypatch.setattr(
        obsidian_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    run_dir = tmp_path / "storage" / "artifacts" / "paper_sync_001" / "run_sync_001"
    run_dir.mkdir(parents=True, exist_ok=True)

    legacy_claimset = {
        "doc_id": "paper_sync_001",
        "claims": [
            {
                "claim_id": "c-legacy",
                "type": "efficacy",
                "statement": "legacy claim",
                "confidence": 0.8,
                "evidence_spans": [{"raw_text": "legacy evidence"}],
            }
        ],
    }
    resolved_claimset = {
        "doc_id": "paper_sync_001",
        "claims": [
            {
                "claim_id": "c-resolved",
                "type": "efficacy",
                "statement": "resolved claim",
                "confidence": 0.9,
                "evidence_spans": [{"raw_text": "resolved evidence"}],
            }
        ],
    }

    (run_dir / "claimset.json").write_text(json.dumps(legacy_claimset), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(json.dumps(resolved_claimset), encoding="utf-8")

    client = TestClient(api_main.app)
    resp = client.post("/obsidian/sync", json={"paper_id": "paper_sync_001", "run_id": "run_sync_001"})
    assert resp.status_code == 200

    content = target_note.read_text(encoding="utf-8")
    assert "resolved claim" in content
    assert "legacy claim" not in content
