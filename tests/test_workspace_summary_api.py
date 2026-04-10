from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from src.schemas.ops import HomeWorkspaceSummaryResponse


def test_workspace_summary_counts_visible_papers_and_notes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        api_main,
        "_list_visible_paper_items",
        lambda raw_limit=5000: [
            {
                "paper_id": "paper_clear",
                "status": "INDEXED",
                "issues_label": "No critical issues",
                "ops_summary": SimpleNamespace(state="ready"),
            },
            {
                "paper_id": "paper_review",
                "status": "FAILED",
                "issues_label": "Needs manual review",
                "ops_summary": None,
            },
            {
                "paper_id": "paper_blocked",
                "status": "INDEXED",
                "issues_label": "No critical issues",
                "ops_summary": SimpleNamespace(state="action_needed"),
            },
        ],
    )
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        api_main.paper_notes,
        "_build_index",
        lambda vault_path: SimpleNamespace(
            items=[
                SimpleNamespace(structured_state_present=True, updated_at="2026-04-10T00:00:00Z"),
                SimpleNamespace(structured_state_present=False, updated_at="2026-04-09T00:00:00Z"),
            ]
        ),
    )

    client = TestClient(api_main.app)
    response = client.get("/workspace-summary")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 2,
        "structured_notes": 1,
        "needs_review": 1,
        "blocked": 1,
        "latest_note_updated_at": "2026-04-10T00:00:00Z",
        "note_context_limited": False,
    }


def test_workspace_summary_marks_note_context_limited_when_note_index_fails(monkeypatch):
    monkeypatch.setattr(api_main, "_list_visible_paper_items", lambda raw_limit=5000: [])
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: Path("/missing-vault"))
    monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda vault_path: (_ for _ in ()).throw(FileNotFoundError()))

    client = TestClient(api_main.app)
    response = client.get("/workspace-summary")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 0,
        "structured_notes": 0,
        "needs_review": 0,
        "blocked": 0,
        "latest_note_updated_at": None,
        "note_context_limited": True,
    }


def test_workspace_summary_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")

    client = TestClient(api_main.app)
    blocked = client.get("/workspace-summary")
    assert blocked.status_code == 401
    assert blocked.json()["error_code"] == "UNAUTHORIZED"

    monkeypatch.setattr(
        api_main,
        "_build_home_workspace_summary",
        lambda: HomeWorkspaceSummaryResponse(
            saved_notes=1,
            structured_notes=1,
            needs_review=0,
            blocked=0,
            latest_note_updated_at="2026-04-10T00:00:00Z",
            note_context_limited=False,
        ),
    )
    allowed = client.get("/workspace-summary", headers={"X-API-Key": "secret-key"})
    assert allowed.status_code == 200
    assert allowed.json()["saved_notes"] == 1
