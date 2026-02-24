import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import obsidian as obsidian_router


def _claimset_payload(claim_id: str, statement: str, evidence: str) -> dict:
    return {
        "doc_id": "paper_sync_001",
        "claims": [
            {
                "claim_id": claim_id,
                "type": "efficacy",
                "statement": statement,
                "confidence": 0.9,
                "evidence_spans": [{"raw_text": evidence}],
            }
        ],
    }


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

    legacy_claimset = _claimset_payload("c-legacy", "legacy claim", "legacy evidence")
    resolved_claimset = _claimset_payload("c-resolved", "resolved claim", "resolved evidence")

    (run_dir / "claimset.json").write_text(json.dumps(legacy_claimset), encoding="utf-8")
    (run_dir / "claimset.resolved.json").write_text(json.dumps(resolved_claimset), encoding="utf-8")

    client = TestClient(api_main.app)
    resp = client.post("/obsidian/sync", json={"paper_id": "paper_sync_001", "run_id": "run_sync_001"})
    assert resp.status_code == 200

    content = target_note.read_text(encoding="utf-8")
    assert "resolved claim" in content
    assert "legacy claim" not in content


def test_obsidian_sync_replaces_existing_marker_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    target_note = vault_dir / "paper_sync_001.md"
    target_note.write_text(
        (
            "# paper_sync_001\n\n"
            "<!-- AI_AGENT_START -->\n"
            "obsolete\n"
            "<!-- AI_AGENT_END -->\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        obsidian_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    run_dir = tmp_path / "storage" / "artifacts" / "paper_sync_001" / "run_sync_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    first_claimset = _claimset_payload("c-first", "first claim", "first evidence")
    second_claimset = _claimset_payload("c-second", "second claim", "second evidence")
    (run_dir / "claimset.resolved.json").write_text(json.dumps(first_claimset), encoding="utf-8")

    client = TestClient(api_main.app)
    first = client.post("/obsidian/sync", json={"paper_id": "paper_sync_001", "run_id": "run_sync_001"})
    assert first.status_code == 200

    (run_dir / "claimset.resolved.json").write_text(json.dumps(second_claimset), encoding="utf-8")
    second = client.post("/obsidian/sync", json={"paper_id": "paper_sync_001", "run_id": "run_sync_001"})
    assert second.status_code == 200

    content = target_note.read_text(encoding="utf-8")
    assert "second claim" in content
    assert "first claim" not in content
    assert content.count(obsidian_router.MARKER_START) == 1
    assert content.count(obsidian_router.MARKER_END) == 1


def test_obsidian_sync_uses_atomic_write(tmp_path, monkeypatch):
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
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(_claimset_payload("c-atomic", "atomic claim", "atomic evidence")),
        encoding="utf-8",
    )

    writes = []
    original_atomic_write = obsidian_router._atomic_write_text

    def _capturing_atomic_write(path, content):
        writes.append(path)
        return original_atomic_write(path, content)

    monkeypatch.setattr(obsidian_router, "_atomic_write_text", _capturing_atomic_write)

    client = TestClient(api_main.app)
    response = client.post("/obsidian/sync", json={"paper_id": "paper_sync_001", "run_id": "run_sync_001"})
    assert response.status_code == 200
    assert target_note in writes
