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
