import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main


def test_artifact_feedback_post_persists_generated_feedback_id_and_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payload = {
        "artifact_type": "meeting_pack",
        "artifact_id": "meetingpack_review_001",
        "paper_id": "paper_review_001",
        "run_id": "run_review_001",
        "decision": "correct",
        "reason_code": "missing_context",
        "actor_id": "reviewer_001",
        "note": "Need stronger project-context framing in the opener.",
    }
    resp = client.post("/artifact-feedback", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    feedback_file = Path("storage/artifact_review_feedback.jsonl")
    assert feedback_file.exists()
    rows = [line for line in feedback_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["artifact_type"] == payload["artifact_type"]
    assert saved["artifact_id"] == payload["artifact_id"]
    assert saved["decision"] == payload["decision"]
    assert saved["reason_code"] == payload["reason_code"]
    assert isinstance(saved.get("feedback_id"), str)
    assert isinstance(saved.get("timestamp"), str)


def test_artifact_feedback_get_filters_and_orders_latest_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payloads = [
        {
            "artifact_type": "chart_pack",
            "artifact_id": "chartpack_review_older",
            "paper_id": "paper_review_002",
            "run_id": "run_review_older",
            "decision": "accept",
            "reason_code": "ready_for_use",
            "actor_id": "reviewer_001",
            "note": "Looks good.",
        },
        {
            "artifact_type": "chart_pack",
            "artifact_id": "chartpack_review_newer",
            "paper_id": "paper_review_002",
            "run_id": "run_review_newer",
            "decision": "correct",
            "reason_code": "label_cleanup",
            "actor_id": "reviewer_001",
            "note": "Axis labels should be normalized.",
        },
        {
            "artifact_type": "protocol_card",
            "artifact_id": "protocol_review_other",
            "dna_id": "dna_review_other",
            "decision": "reject",
            "reason_code": "missing_sources",
            "actor_id": "reviewer_002",
            "note": "Needs clearer evidence links before reuse.",
        },
    ]
    for payload in payloads:
        resp = client.post("/artifact-feedback", json=payload)
        assert resp.status_code == 200

    artifact_filtered = client.get(
        "/artifact-feedback",
        params={"artifact_type": "chart_pack", "paper_id": "paper_review_002", "limit": 1},
    )
    assert artifact_filtered.status_code == 200
    items = artifact_filtered.json()
    assert len(items) == 1
    assert items[0]["artifact_id"] == "chartpack_review_newer"

    dna_filtered = client.get("/artifact-feedback", params={"dna_id": "dna_review_other"})
    assert dna_filtered.status_code == 200
    dna_items = dna_filtered.json()
    assert len(dna_items) == 1
    assert dna_items[0]["artifact_type"] == "protocol_card"


def test_artifact_feedback_uses_runtime_storage_log_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paperpipe_home = tmp_path / "app-home"
    monkeypatch.setenv("PAPERPIPE_HOME", str(paperpipe_home))

    client = TestClient(api_main.app)

    payload = {
        "artifact_type": "image_evidence",
        "artifact_id": "img_review_runtime",
        "run_id": "run_review_runtime",
        "decision": "escalate",
        "reason_code": "domain_review_needed",
        "actor_id": "reviewer_runtime",
        "note": "Needs specialist validation before external sharing.",
    }
    resp = client.post("/artifact-feedback", json=payload)
    assert resp.status_code == 200

    feedback_file = (paperpipe_home / "storage" / "artifact_review_feedback.jsonl").resolve()
    assert feedback_file.exists()
    rows = [line for line in feedback_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["artifact_id"] == payload["artifact_id"]


def test_artifact_feedback_sanitizes_secret_like_note_and_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payload = {
        "artifact_type": "meeting_pack",
        "artifact_id": "meetingpack_review_secret",
        "paper_id": "paper_review_secret",
        "run_id": "run_review_secret",
        "decision": "correct",
        "reason_code": "missing_context",
        "actor_id": "reviewer_secret",
        "note": (
            "Do not persist Authorization: Bearer artifact-review-token-123 "
            "or sk-proj-artifact-review-secret-abcdef."
        ),
        "metadata": {
            "api_key": "metadata-review-key-123",
            "context": "postgresql://paperpipe:secret@example.local/review",
        },
    }

    resp = client.post("/artifact-feedback", json=payload)
    assert resp.status_code == 200

    feedback_file = Path("storage/artifact_review_feedback.jsonl")
    raw_file = feedback_file.read_text(encoding="utf-8")
    assert "artifact-review-token-123" not in raw_file
    assert "sk-proj-artifact-review-secret-abcdef" not in raw_file
    assert "metadata-review-key-123" not in raw_file
    assert "postgresql://paperpipe:secret@example.local/review" not in raw_file

    saved = json.loads(raw_file.strip())
    assert saved["note"] == "Do not persist Authorization: <redacted> or <redacted>."
    assert saved["metadata"]["api_key"] == "<redacted>"
    assert saved["metadata"]["context"] == "<redacted>"

    listed = client.get("/artifact-feedback", params={"artifact_id": "meetingpack_review_secret"})
    assert listed.status_code == 200
    assert listed.json()[0]["note"] == saved["note"]
    assert listed.json()[0]["metadata"] == saved["metadata"]


def test_artifact_feedback_list_sanitizes_legacy_raw_secret_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    feedback_file = Path("storage/artifact_review_feedback.jsonl")
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    feedback_file.write_text(
        json.dumps(
            {
                "feedback_id": "legacy-review-secret",
                "artifact_type": "protocol_card",
                "artifact_id": "protocol_review_legacy_secret",
                "paper_id": "paper_review_legacy_secret",
                "decision": "correct",
                "reason_code": "legacy_secret",
                "actor_id": "reviewer_legacy",
                "note": "Legacy note contains Authorization: Bearer legacy-review-token-123.",
                "metadata": {"token": "legacy-review-metadata-token"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    listed = client.get("/artifact-feedback", params={"artifact_id": "protocol_review_legacy_secret"})
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["note"] == "Legacy note contains Authorization: <redacted>"
    assert item["metadata"]["token"] == "<redacted>"
