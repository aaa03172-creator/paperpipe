import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import feedback as feedback_router
from src.schemas.agent_artifacts import FeedbackCase


def test_feedback_retriever_is_lazy_until_indexing(monkeypatch):
    constructed = []

    class FakeFeedbackRetriever:
        def __init__(self):
            constructed.append(True)

        def add_feedback(self, _case):
            return True

    monkeypatch.setattr(feedback_router, "FeedbackRetriever", FakeFeedbackRetriever)
    retriever = feedback_router._LazyFeedbackRetriever()

    assert constructed == []

    assert retriever.add_feedback(
        FeedbackCase(
            paper_id="paper_feedback_lazy",
            run_id="run_feedback_lazy",
            user_correction="lazy construction",
            accepted=True,
        )
    ) is True
    assert constructed == [True]


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


def test_feedback_uses_runtime_storage_for_feedback_log(tmp_path, monkeypatch):
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


def test_feedback_sanitizes_secret_like_correction_before_storage_and_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_add_feedback(case):
        captured["case"] = case
        return True

    monkeypatch.setattr(feedback_router.feedback_retriever, "add_feedback", fake_add_feedback)
    client = TestClient(api_main.app)

    raw_correction = (
        "Authorization: Bearer feedback-token-123; "
        "key=sk-proj-feedback-secret-abcdef; "
        "db=postgresql://paperpipe:secret@example.local/db"
    )
    payload = {
        "paper_id": "paper_feedback_secret",
        "run_id": "run_feedback_secret",
        "user_correction": raw_correction,
        "accepted": True,
    }
    resp = client.post("/feedback", json=payload)
    assert resp.status_code == 200

    feedback_file = Path("storage/feedback.jsonl")
    raw_file = feedback_file.read_text(encoding="utf-8")
    assert "feedback-token-123" not in raw_file
    assert "sk-proj-feedback-secret-abcdef" not in raw_file
    assert "postgresql://paperpipe:secret@example.local/db" not in raw_file

    saved = json.loads(raw_file.strip())
    assert saved["user_correction"] == "Authorization: <redacted>; key=<redacted>; db=<redacted>"
    assert captured["case"].user_correction == saved["user_correction"]

    listed = client.get("/feedback", params={"paper_id": "paper_feedback_secret"})
    assert listed.status_code == 200
    assert listed.json()[0]["user_correction"] == saved["user_correction"]


def test_feedback_list_sanitizes_legacy_raw_secret_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    feedback_file = Path("storage/feedback.jsonl")
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    feedback_file.write_text(
        json.dumps(
            {
                "feedback_id": "legacy-feedback-secret",
                "paper_id": "paper_feedback_legacy_secret",
                "run_id": "run_feedback_legacy_secret",
                "user_correction": "Use Authorization: Bearer legacy-feedback-token-123 safely.",
                "accepted": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    listed = client.get("/feedback", params={"paper_id": "paper_feedback_legacy_secret"})
    assert listed.status_code == 200
    assert listed.json()[0]["user_correction"] == "Use Authorization: <redacted> safely."
