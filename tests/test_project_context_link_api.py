import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main


def _write_project_workspace(root: Path, *, project_id: str) -> None:
    project_dir = root / "storage" / "project_memory" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": project_id,
        "title": "Project context test workspace",
        "layer": "raw_memory",
        "canonical_status": "non_canonical",
        "status": "active",
        "linked_paper_ids": [],
        "linked_research_dna_ids": [],
        "linked_meeting_pack_ids": [],
        "created_at": "2026-04-13T00:00:00Z",
        "updated_at": "2026-04-13T00:00:00Z",
    }
    (project_dir / "project.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_project_context_link_post_persists_generated_decision_id_and_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_project_workspace(tmp_path, project_id="pmproj_context_alpha")
    client = TestClient(api_main.app)

    payload = {
        "project_id": "pmproj_context_alpha",
        "entity_type": "paper",
        "entity_id": "paper_context_001",
        "relationship_type": "primary_focus",
        "actor_id": "reviewer_001",
        "note": "Core paper for the current project framing.",
    }
    resp = client.post("/project-context-links", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    log_file = Path("storage/project_context_links.jsonl")
    assert log_file.exists()
    rows = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["project_id"] == payload["project_id"]
    assert saved["relationship_type"] == payload["relationship_type"]
    assert isinstance(saved.get("decision_id"), str)
    assert isinstance(saved.get("timestamp"), str)


def test_project_context_link_sanitizes_note_and_metadata_before_storage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_project_workspace(tmp_path, project_id="pmproj_context_sanitize")
    client = TestClient(api_main.app)

    payload = {
        "project_id": "pmproj_context_sanitize",
        "entity_type": "paper",
        "entity_id": "paper_context_sanitize",
        "relationship_type": "primary_focus",
        "actor_id": "reviewer_sanitize",
        "note": "Use Authorization: Bearer ctxlinksecret123 and sk-proj-contextsecret123456.",
        "metadata": {
            "api_key": "ctx-link-api-key-secret",
            "source_url": "postgres://ctx_user:ctx_password@example.test:5432/paperpipe",
            "nested": {"token": "ctx-link-token-secret"},
        },
    }
    resp = client.post("/project-context-links", json=payload)
    assert resp.status_code == 200

    log_file = Path("storage/project_context_links.jsonl")
    raw_log = log_file.read_text(encoding="utf-8")
    assert "ctxlinksecret123" not in raw_log
    assert "sk-proj-contextsecret123456" not in raw_log
    assert "ctx-link-api-key-secret" not in raw_log
    assert "ctx_password" not in raw_log
    assert "ctx-link-token-secret" not in raw_log

    saved = json.loads(raw_log.strip())
    assert saved["note"] == "Use Authorization: <redacted> and <redacted>."
    assert saved["metadata"]["api_key"] == "<redacted>"
    assert saved["metadata"]["source_url"] == "<redacted>"
    assert saved["metadata"]["nested"]["token"] == "<redacted>"

    listed = client.get("/project-context-links", params={"project_id": "pmproj_context_sanitize"})
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["note"] == "Use Authorization: <redacted> and <redacted>."
    assert item["metadata"]["api_key"] == "<redacted>"


def test_project_context_link_sanitizes_legacy_raw_rows_on_read(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = Path("storage/project_context_links.jsonl")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        json.dumps(
            {
                "project_id": "pmproj_context_legacy",
                "entity_type": "paper",
                "entity_id": "paper_context_legacy",
                "relationship_type": "supporting_context",
                "actor_id": "reviewer_legacy",
                "note": "Legacy note with Authorization: Bearer legacyctxlinksecret123.",
                "timestamp": "2026-04-13T00:00:00Z",
                "metadata": {
                    "password": "legacy-context-password",
                    "dsn": "mysql://ctx_user:ctx_password@example.test:3306/paperpipe",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client = TestClient(api_main.app)

    resp = client.get("/project-context-links", params={"project_id": "pmproj_context_legacy"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["note"] == "Legacy note with Authorization: <redacted>"
    assert items[0]["metadata"]["password"] == "<redacted>"
    assert items[0]["metadata"]["dsn"] == "<redacted>"


def test_project_context_link_post_requires_existing_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payload = {
        "project_id": "pmproj_missing",
        "entity_type": "paper",
        "entity_id": "paper_context_404",
        "relationship_type": "supporting_context",
        "actor_id": "reviewer_001",
        "note": "Should fail without workspace.",
    }
    resp = client.post("/project-context-links", json=payload)
    assert resp.status_code == 404
    assert "Project Memory workspace not found" in resp.json()["detail"]
    assert not Path("storage/project_context_links.jsonl").exists()


def test_project_context_link_rejects_invalid_entity_type_without_appending_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_project_workspace(tmp_path, project_id="pmproj_context_invalid_entity")
    log_file = Path("storage/project_context_links.jsonl")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    existing_row = {
        "project_id": "pmproj_context_invalid_entity",
        "entity_type": "paper",
        "entity_id": "paper_context_existing",
        "relationship_type": "supporting_context",
        "actor_id": "reviewer_existing",
        "note": "Existing context link.",
        "timestamp": "2026-04-13T00:00:00Z",
    }
    log_file.write_text(json.dumps(existing_row) + "\n", encoding="utf-8")
    before = log_file.read_text(encoding="utf-8")
    client = TestClient(api_main.app)

    resp = client.post(
        "/project-context-links",
        json={
            "project_id": "pmproj_context_invalid_entity",
            "entity_type": "unsupported_entity",
            "entity_id": "paper_context_001",
            "relationship_type": "supporting_context",
            "actor_id": "reviewer_001",
            "note": "This should be rejected by the API contract.",
        },
    )
    assert resp.status_code == 422
    assert log_file.read_text(encoding="utf-8") == before


def test_project_context_link_rejects_invalid_relationship_type_without_appending_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_project_workspace(tmp_path, project_id="pmproj_context_invalid_relationship")
    log_file = Path("storage/project_context_links.jsonl")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("", encoding="utf-8")
    client = TestClient(api_main.app)

    resp = client.post(
        "/project-context-links",
        json={
            "project_id": "pmproj_context_invalid_relationship",
            "entity_type": "paper",
            "entity_id": "paper_context_001",
            "relationship_type": "primary",
            "actor_id": "reviewer_001",
            "note": "This should be rejected by the API contract.",
        },
    )
    assert resp.status_code == 422
    assert log_file.read_text(encoding="utf-8") == ""


def test_project_context_link_rejects_path_like_project_id_without_storage_side_effect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    resp = client.post(
        "/project-context-links",
        json={
            "project_id": "pmproj_../escape",
            "entity_type": "paper",
            "entity_id": "paper_context_001",
            "relationship_type": "supporting_context",
            "actor_id": "reviewer_001",
            "note": "This should not reach storage path resolution.",
        },
    )
    assert resp.status_code == 422
    assert "project_id" in str(resp.json()["detail"])
    assert not Path("storage/project_context_links.jsonl").exists()


def test_project_context_link_get_filters_and_orders_latest_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_project_workspace(tmp_path, project_id="pmproj_context_beta")
    client = TestClient(api_main.app)

    payloads = [
        {
            "project_id": "pmproj_context_beta",
            "entity_type": "paper",
            "entity_id": "paper_context_old",
            "relationship_type": "background_context",
            "actor_id": "reviewer_001",
            "note": "Older note.",
        },
        {
            "project_id": "pmproj_context_beta",
            "entity_type": "meeting_pack",
            "entity_id": "meetingpack_context_new",
            "relationship_type": "follow_up_candidate",
            "actor_id": "reviewer_001",
            "note": "Newer note.",
        },
        {
            "project_id": "pmproj_context_beta",
            "entity_type": "paper",
            "entity_id": "paper_context_blocked",
            "relationship_type": "blocked_or_conflicting",
            "actor_id": "reviewer_002",
            "note": "Conflict note.",
        },
    ]
    for payload in payloads:
        resp = client.post("/project-context-links", json=payload)
        assert resp.status_code == 200

    filtered = client.get(
        "/project-context-links",
        params={"project_id": "pmproj_context_beta", "actor_id": "reviewer_001", "limit": 1},
    )
    assert filtered.status_code == 200
    items = filtered.json()
    assert len(items) == 1
    assert items[0]["entity_id"] == "meetingpack_context_new"

    relationship_filtered = client.get(
        "/project-context-links",
        params={"relationship_type": "blocked_or_conflicting"},
    )
    assert relationship_filtered.status_code == 200
    relationship_items = relationship_filtered.json()
    assert len(relationship_items) == 1
    assert relationship_items[0]["actor_id"] == "reviewer_002"


def test_project_context_link_uses_runtime_storage_log_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paperpipe_home = tmp_path / "app-home"
    monkeypatch.setenv("PAPERPIPE_HOME", str(paperpipe_home))
    _write_project_workspace(paperpipe_home, project_id="pmproj_context_runtime")
    client = TestClient(api_main.app)

    payload = {
        "project_id": "pmproj_context_runtime",
        "entity_type": "research_dna",
        "entity_id": "dna_context_runtime",
        "relationship_type": "supporting_context",
        "actor_id": "reviewer_runtime",
        "note": "Relevant DNA context for the project.",
    }
    resp = client.post("/project-context-links", json=payload)
    assert resp.status_code == 200

    log_file = (paperpipe_home / "storage" / "project_context_links.jsonl").resolve()
    assert log_file.exists()
    rows = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["entity_id"] == payload["entity_id"]
