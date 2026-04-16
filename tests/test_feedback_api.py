import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main


def test_feedback_post_persists_generated_feedback_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payload = {
        "paper_id": "paper_feedback_001",
        "run_id": "run_feedback_001",
        "user_correction": "Need stronger evidence link.",
        "accepted": True,
    }
    resp = client.post("/feedback", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    feedback_file = Path("storage/feedback.jsonl")
    assert feedback_file.exists()
    rows = [line for line in feedback_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["paper_id"] == payload["paper_id"]
    assert saved["run_id"] == payload["run_id"]
    assert isinstance(saved.get("feedback_id"), str)
    assert len(saved["feedback_id"]) > 0


def test_feedback_get_filters_and_limits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payloads = [
        {
            "paper_id": "paper_feedback_002",
            "run_id": "run_feedback_older",
            "user_correction": "first correction",
            "accepted": False,
        },
        {
            "paper_id": "paper_feedback_002",
            "run_id": "run_feedback_newer",
            "user_correction": "second correction",
            "accepted": True,
        },
        {
            "paper_id": "paper_feedback_other",
            "run_id": "run_feedback_other",
            "user_correction": "third correction",
            "accepted": True,
        },
    ]
    for payload in payloads:
        resp = client.post("/feedback", json=payload)
        assert resp.status_code == 200

    paper_filtered = client.get("/feedback", params={"paper_id": "paper_feedback_002", "limit": 1})
    assert paper_filtered.status_code == 200
    items = paper_filtered.json()
    assert len(items) == 1
    # latest-first
    assert items[0]["run_id"] == "run_feedback_newer"

    run_filtered = client.get("/feedback", params={"run_id": "run_feedback_older"})
    assert run_filtered.status_code == 200
    run_items = run_filtered.json()
    assert len(run_items) == 1
    assert run_items[0]["paper_id"] == "paper_feedback_002"


def test_feedback_uses_runtime_storage_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paperpipe_home = tmp_path / "app-home"
    monkeypatch.setenv("PAPERPIPE_HOME", str(paperpipe_home))
    client = TestClient(api_main.app)

    payload = {
        "paper_id": "paper_feedback_runtime",
        "run_id": "run_feedback_runtime",
        "user_correction": "runtime path check",
        "accepted": False,
    }
    resp = client.post("/feedback", json=payload)
    assert resp.status_code == 200

    feedback_file = (paperpipe_home / "storage" / "feedback.jsonl").resolve()
    assert feedback_file.exists()
    rows = [line for line in feedback_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["paper_id"] == payload["paper_id"]
