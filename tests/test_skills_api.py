import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from backend.routers import paper_notes as paper_notes_router
from src.skills import runner as skills_runner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_policy(path: Path, *, critical_appraisal_secret: str | None = None) -> None:
    lines = [
        "version: 1",
        "",
        "defaults:",
        "  enabled: false",
        "  sandbox: native",
        "  network: none",
        "  timeout_seconds: 30",
        "",
        "project_scoped_skills:",
        "  - citation-management",
        "  - peer-review",
        "",
        "actions:",
        "  validate_citations:",
        "    enabled: true",
        "    category: core-safe",
        "    source_skill: citation-management",
        "    license: MIT",
        "    sandbox: native",
        "    network: none",
        "    timeout_seconds: 15",
        "  critical_appraisal:",
        "    enabled: true",
        "    category: core-safe",
        "    source_skill: peer-review",
        "    license: MIT",
        "    sandbox: docker",
        "    network: none",
        "    timeout_seconds: 15",
    ]
    if critical_appraisal_secret:
        lines.extend(
            [
                "    secrets_required:",
                f"      - {critical_appraisal_secret}",
                '    notes: "Requires local secret before appraisal can run."',
            ]
        )
    _write(path, "\n".join(lines) + "\n")


def _note_content(slug: str) -> str:
    return f"""---
id: zotero:{slug}
aliases: ["Skills Note"]
tags:
  - Topic/Memory
  - Outcome/Recall
date_processed: 2026-03-09
confidence: 0.87
status: INDEXED
doi: 10.1000/182
zotero_link: zotero://select/items/1_SKILLS
---

# Skills Note

## Summary

Compact note for structured skill execution.

## 🔗 References
* [Publisher Link](https://example.org/paper)
"""


def _parse_frontmatter(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    end_index = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    return "\n".join(lines[1:end_index]), "\n".join(lines[end_index + 1 :]).lstrip("\n")


def test_skills_run_writes_sidecar_and_updates_frontmatter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"

    vault_dir = tmp_path / "vault"
    slug = "skills-note"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md"
    _write(note_path, _note_content(slug))
    _write_policy(tmp_path / "config" / "skills_policy.yaml")

    config = SimpleNamespace(
        paths=SimpleNamespace(obsidian_vault=vault_dir, library_dir=tmp_path / "Library"),
        system=SimpleNamespace(unpaywall_email=None),
    )
    monkeypatch.setattr(skills_runner, "load_config", lambda: config)
    monkeypatch.setattr(paper_notes_router, "load_config", lambda: config)

    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        response = client.post(
            "/skills/run",
            json={"slug": slug, "action": "validate_citations", "append_markdown_summary": True},
        )
        assert response.status_code == 200
        payload = response.json()

        state_path = vault_dir / ".pp" / slug / "state.json"
        runs_dir = vault_dir / ".pp" / slug / "runs"
        run_files = sorted(runs_dir.glob("*_validate_citations.json"))

        assert payload["structured_path"] == f".pp/{slug}/state.json"
        assert payload["run"]["artifacts"]["structured_path"] == f".pp/{slug}/state.json"
        assert payload["run"]["artifacts"]["write_scope"]["structured_state"] is True
        assert payload["run"]["artifacts"]["write_scope"]["frontmatter_pp"] is True
        assert payload["run"]["artifacts"]["write_scope"]["markdown_summary"] is True
        assert state_path.exists()
        assert len(run_files) == 1

        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["paper_slug"] == slug
        assert state["runs"][0]["action"] == "validate_citations"
        assert state["runs"][0]["status"] == "succeeded"
        assert state["runs"][0]["artifacts"]["structured_path"] == f".pp/{slug}/state.json"
        assert state["runs"][0]["artifacts"]["write_scope"]["structured_state"] is True
        assert state["runs"][0]["artifacts"]["write_scope"]["frontmatter_pp"] is True
        assert state["runs"][0]["artifacts"]["write_scope"]["markdown_summary"] is True
        assert state["signals"]["citation_count"] == 3
        assert state["signals"]["run_count"] == 1
        assert state["signals"]["last_action"] == "validate_citations"

        frontmatter_text, body = _parse_frontmatter(note_path)
        assert "structured_path: .pp/skills-note/state.json" in frontmatter_text
        assert "- validate_citations" in frontmatter_text
        assert "citation_count: 3" in frontmatter_text
        assert "## 🔧 Automation Results (short)" in body
        assert "validate_citations: Checked 3 references" in body

        detail = client.get(f"/paper-notes/{slug}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["structured_state"]["signals"]["citation_count"] == 3
        assert detail_payload["structured_state"]["runs"][0]["action"] == "validate_citations"
        assert any(
            action["action"] == "validate_citations" and action["enabled"] is True
            for action in detail_payload["available_actions"]
        )

        conn = db_utils.get_db_connection()
        action_row = conn.execute(
            """
            SELECT paper_id, action_type, source, payload_json
            FROM user_actions
            WHERE paper_id = ?
            ORDER BY ts DESC, rowid DESC
            LIMIT 1
            """,
            (f"zotero:{slug}",),
        ).fetchone()
        conn.close()
        assert action_row is not None
        assert action_row["action_type"] == "skill_run"
        assert action_row["source"] == "ui"
        action_payload = json.loads(action_row["payload_json"])
        assert action_payload["action"] == "validate_citations"
        assert action_payload["slug"] == slug
    finally:
        db_utils.DB_PATH = original_db_path


def test_skills_run_can_skip_markdown_summary_append(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "skills-note-quiet"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md"
    _write(note_path, _note_content(slug))
    _write_policy(tmp_path / "config" / "skills_policy.yaml")

    config = SimpleNamespace(
        paths=SimpleNamespace(obsidian_vault=vault_dir, library_dir=tmp_path / "Library"),
        system=SimpleNamespace(unpaywall_email=None),
    )
    monkeypatch.setattr(skills_runner, "load_config", lambda: config)
    monkeypatch.setattr(paper_notes_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    response = client.post(
        "/skills/run",
        json={"slug": slug, "action": "validate_citations", "append_markdown_summary": False},
    )
    assert response.status_code == 200
    payload = response.json()

    state_path = vault_dir / ".pp" / slug / "state.json"
    runs_dir = vault_dir / ".pp" / slug / "runs"
    run_files = sorted(runs_dir.glob("*_validate_citations.json"))

    assert state_path.exists()
    assert len(run_files) == 1
    assert payload["run"]["artifacts"]["structured_path"] == f".pp/{slug}/state.json"
    assert payload["run"]["artifacts"]["write_scope"]["structured_state"] is True
    assert payload["run"]["artifacts"]["write_scope"]["frontmatter_pp"] is True
    assert payload["run"]["artifacts"]["write_scope"]["markdown_summary"] is False

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["runs"][0]["artifacts"]["structured_path"] == f".pp/{slug}/state.json"
    assert state["runs"][0]["artifacts"]["write_scope"]["structured_state"] is True
    assert state["runs"][0]["artifacts"]["write_scope"]["frontmatter_pp"] is True
    assert state["runs"][0]["artifacts"]["write_scope"]["markdown_summary"] is False

    frontmatter_text, body = _parse_frontmatter(note_path)
    assert "structured_path: .pp/skills-note-quiet/state.json" in frontmatter_text
    assert "- validate_citations" in frontmatter_text
    assert "citation_count: 3" in frontmatter_text
    assert "## 🔧 Automation Results (short)" not in body
    assert "validate_citations: Checked 3 references" not in body


def test_paper_note_detail_disables_actions_when_required_secret_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "skills-note-disabled"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md"
    _write(note_path, _note_content(slug))
    policy_path = tmp_path / "config" / "skills_policy.yaml"
    _write_policy(policy_path, critical_appraisal_secret="PAPERPIPE_APPRAISAL_SECRET")
    monkeypatch.setenv("PAPERPIPE_SKILLS_POLICY_PATH", str(policy_path))
    monkeypatch.delenv("PAPERPIPE_APPRAISAL_SECRET", raising=False)

    config = SimpleNamespace(
        paths=SimpleNamespace(obsidian_vault=vault_dir, library_dir=tmp_path / "Library"),
        system=SimpleNamespace(unpaywall_email=None),
    )
    monkeypatch.setattr(skills_runner, "load_config", lambda: config)
    monkeypatch.setattr(paper_notes_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    detail = client.get(f"/paper-notes/{slug}")
    assert detail.status_code == 200
    detail_payload = detail.json()

    validate_action = next(action for action in detail_payload["available_actions"] if action["action"] == "validate_citations")
    appraisal_action = next(action for action in detail_payload["available_actions"] if action["action"] == "critical_appraisal")

    assert validate_action["enabled"] is True
    assert validate_action["disabled_reason"] is None
    assert appraisal_action["enabled"] is False
    assert appraisal_action["secrets_required"] == ["PAPERPIPE_APPRAISAL_SECRET"]
    assert appraisal_action["disabled_reason"] == "Blocked: missing required secret PAPERPIPE_APPRAISAL_SECRET."
