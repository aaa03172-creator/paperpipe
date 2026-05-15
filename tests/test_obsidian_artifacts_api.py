import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from backend.routers import obsidian as obsidian_router
from src.services.identity import artifact_paper_segment


def _set_artifacts_root(monkeypatch, root):
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))


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
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")
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
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")
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
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")
    client = TestClient(api_main.app)

    resp = client.get("/obsidian/artifacts", params={"paper_id": "paper_missing", "run_id": "run_missing"})
    assert resp.status_code == 404


def test_obsidian_artifacts_honor_artifacts_root_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_artifacts = tmp_path / "external-artifacts"
    _set_artifacts_root(monkeypatch, custom_artifacts)
    client = TestClient(api_main.app)

    run_dir = custom_artifacts / "paper_obs_override" / "run_obs_override"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(json.dumps({"claims": ["resolved-override"]}), encoding="utf-8")
    (run_dir / "stats_report.json").write_text(json.dumps({"checks": []}), encoding="utf-8")

    resp = client.get("/obsidian/artifacts", params={"paper_id": "paper_obs_override", "run_id": "run_obs_override"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["claimset_source"] == "claimset.resolved.json"
    assert payload["claimset"]["exists"] is True
    assert payload["claimset"]["data"]["claims"] == ["resolved-override"]
    assert payload["stats_report"]["exists"] is True


def test_obsidian_artifacts_resolve_hashed_path_for_unsafe_paper_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")
    client = TestClient(api_main.app)

    paper_id = "doi:10.1000/test-paper"
    run_id = "run_obs_hashed"
    run_dir = tmp_path / "storage" / "artifacts" / artifact_paper_segment(paper_id) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(json.dumps({"claims": ["resolved-safe-key"]}), encoding="utf-8")

    resp = client.get("/obsidian/artifacts", params={"paper_id": paper_id, "run_id": run_id})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["claimset_source"] == "claimset.resolved.json"
    assert payload["claimset"]["data"]["claims"] == ["resolved-safe-key"]


def test_obsidian_mirror_returns_generated_payload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")
    monkeypatch.setenv("LATTICE_PUBLIC_BASE_URL", "http://127.0.0.1:9000")

    run_dir = tmp_path / "storage" / "artifacts" / "paper_mirror_001" / "run_mirror_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(_claimset_payload("c-mirror", "mirror claim", "mirror evidence")),
        encoding="utf-8",
    )
    (run_dir / "stats_report.json").write_text(
        json.dumps(
            {
                "doc_id": "paper_mirror_001",
                "run_id": "run_mirror_001",
                "checks": [
                    {
                        "check_id": "check-001",
                        "test_type": "ttest",
                        "code": "print('ok')",
                        "outputs": "ok",
                        "verdict": "verified",
                        "notes": "ok",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    resp = client.get("/obsidian/mirror", params={"paper_id": "paper_mirror_001", "run_id": "run_mirror_001"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["has_claimset"] is True
    assert payload["has_stats_report"] is True
    assert len(payload["claims"]) == 1
    assert payload["claims"][0]["statement"] == "mirror claim"
    assert payload["claims"][0]["confidence"] == 0.9
    assert len(payload["stats_checks"]) == 1
    assert payload["stats_checks"][0]["test_type"] == "ttest"
    assert payload["stats_checks"][0]["verdict"] == "verified"
    assert payload["stats_checks"][0]["claim_id"] == "check-001"
    assert payload["stats_checks"][0]["evidence_page"] is None
    assert "note_exists" not in payload
    assert "note_path" not in payload
    assert "mirror claim" in payload["generated_markdown"]
    assert "[Review in Lattice](http://127.0.0.1:9000/ui/workbench/paper_mirror_001)" in payload["generated_markdown"]
    assert "<!-- AI_AGENT_START -->" in payload["generated_markdown"]


def test_obsidian_mirror_exposes_grounding_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")

    run_dir = tmp_path / "storage" / "artifacts" / "paper_mirror_002" / "run_mirror_002"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(
            {
                "doc_id": "paper_mirror_002",
                "claims": [
                    {
                        "claim_id": "c-grounded",
                        "type": "efficacy",
                        "statement": "grounded claim",
                        "confidence": 0.91,
                        "evidence_spans": [
                            {
                                "raw_text": "quoted source text",
                                "quote": "quoted source text",
                                "page": 2,
                                "chunk_id": "p03_c01",
                                "grounded": True,
                                "resolution": "OK",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    resp = client.get("/obsidian/mirror", params={"paper_id": "paper_mirror_002", "run_id": "run_mirror_002"})
    assert resp.status_code == 200
    payload = resp.json()

    claim = payload["claims"][0]
    assert claim["evidence_page"] == 3
    assert claim["evidence_chunk_id"] == "p03_c01"
    assert claim["evidence_grounded"] is True
    assert claim["evidence_resolution"] == "OK"


def test_obsidian_mirror_generated_markdown_uses_one_indexed_pages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")

    run_dir = tmp_path / "storage" / "artifacts" / "paper_mirror_003" / "run_mirror_003"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(
            {
                "doc_id": "paper_mirror_003",
                "claims": [
                    {
                        "claim_id": "c-page",
                        "type": "efficacy",
                        "statement": "page labeled claim",
                        "confidence": 0.88,
                        "evidence_spans": [
                            {
                                "raw_text": "page indexed quote",
                                "quote": "page indexed quote",
                                "page": 0,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    resp = client.get("/obsidian/mirror", params={"paper_id": "paper_mirror_003", "run_id": "run_mirror_003"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["claims"][0]["evidence_page"] == 1
    assert "(Page 1)" in payload["generated_markdown"]


def test_obsidian_mirror_returns_404_when_no_artifact_for_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")
    client = TestClient(api_main.app)

    resp = client.get("/obsidian/mirror", params={"paper_id": "paper_missing", "run_id": "run_missing"})
    assert resp.status_code == 404


def test_obsidian_sync_prefers_resolved_claimset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")
    monkeypatch.setenv("LATTICE_PUBLIC_BASE_URL", "http://127.0.0.1:9000")
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"

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

    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        resp = client.post("/obsidian/sync", json={"paper_id": "paper_sync_001", "run_id": "run_sync_001"})
        assert resp.status_code == 200

        content = target_note.read_text(encoding="utf-8")
        assert "resolved claim" in content
        assert "legacy claim" not in content
        assert "[Review in Lattice](http://127.0.0.1:9000/ui/workbench/paper_sync_001)" in content

        conn = db_utils.get_db_connection()
        action_row = conn.execute(
            """
            SELECT paper_id, action_type, source, payload_json
            FROM user_actions
            WHERE paper_id = ?
            ORDER BY ts DESC, rowid DESC
            LIMIT 1
            """,
            ("paper_sync_001",),
        ).fetchone()
        conn.close()
        assert action_row is not None
        assert action_row["action_type"] == "obsidian_sync"
        assert action_row["source"] == "obsidian"
        action_payload = json.loads(action_row["payload_json"])
        assert action_payload["run_id"] == "run_sync_001"
    finally:
        db_utils.DB_PATH = original_db_path


def test_obsidian_sync_can_find_note_by_frontmatter_id_when_filename_is_cleaned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    target_note = vault_dir / "Targeting Prodromal Alzheimer Disease With Avagacestat.md"
    target_note.write_text(
        "---\n"
        "id: zotero:coricTargetingProdromalAlzheimer2015\n"
        "aliases: [\"Targeting Prodromal Alzheimer Disease With Avagacestat\"]\n"
        "---\n\n"
        "# Targeting Prodromal Alzheimer Disease With Avagacestat\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        obsidian_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    run_dir = tmp_path / "storage" / "artifacts" / "zotero:coricTargetingProdromalAlzheimer2015" / "run_sync_clean_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved_claimset = _claimset_payload("c-clean", "cleaned filename claim", "cleaned filename evidence")
    (run_dir / "claimset.resolved.json").write_text(json.dumps(resolved_claimset), encoding="utf-8")

    client = TestClient(api_main.app)
    response = client.post(
        "/obsidian/sync",
        json={"paper_id": "zotero:coricTargetingProdromalAlzheimer2015", "run_id": "run_sync_clean_001"},
    )
    assert response.status_code == 200

    content = target_note.read_text(encoding="utf-8")
    assert "cleaned filename claim" in content


def test_obsidian_sync_replaces_existing_marker_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")

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
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")

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
