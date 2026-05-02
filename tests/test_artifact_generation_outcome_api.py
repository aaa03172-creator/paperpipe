import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main as api_main


def test_artifact_generation_outcome_post_persists_generated_outcome_id_and_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payload = {
        "artifact_type": "meeting_pack",
        "artifact_id": "meetingpack_outcome_001",
        "paper_id": "paper_outcome_001",
        "run_id": "run_outcome_001",
        "decision": "reused_after_correction",
        "downstream_use": "final_deliverable",
        "actor_id": "reviewer_001",
        "note": "Used after tightening the opening slide and discussion framing.",
    }
    resp = client.post("/artifact-generation-outcomes", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    outcome_file = Path("storage/artifact_generation_outcomes.jsonl")
    assert outcome_file.exists()
    rows = [line for line in outcome_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["artifact_type"] == payload["artifact_type"]
    assert saved["artifact_id"] == payload["artifact_id"]
    assert saved["decision"] == payload["decision"]
    assert saved["downstream_use"] == payload["downstream_use"]
    assert isinstance(saved.get("outcome_id"), str)
    assert isinstance(saved.get("timestamp"), str)


def test_artifact_generation_outcome_get_filters_and_orders_latest_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payloads = [
        {
            "artifact_type": "chart_pack",
            "artifact_id": "chartpack_outcome_old",
            "paper_id": "paper_outcome_002",
            "run_id": "run_outcome_old",
            "decision": "reused",
            "downstream_use": "supporting_context",
            "actor_id": "reviewer_001",
            "note": "Used as supporting context.",
        },
        {
            "artifact_type": "chart_pack",
            "artifact_id": "chartpack_outcome_new",
            "paper_id": "paper_outcome_002",
            "run_id": "run_outcome_new",
            "decision": "reused_after_correction",
            "downstream_use": "final_deliverable",
            "actor_id": "reviewer_001",
            "note": "Used after label cleanup.",
        },
        {
            "artifact_type": "protocol_card",
            "artifact_id": "protocol_outcome_other",
            "dna_id": "dna_outcome_other",
            "decision": "abandoned",
            "downstream_use": "not_used",
            "actor_id": "reviewer_002",
            "note": "Dropped because the evidence base was still too thin.",
        },
    ]
    for payload in payloads:
        resp = client.post("/artifact-generation-outcomes", json=payload)
        assert resp.status_code == 200

    filtered = client.get(
        "/artifact-generation-outcomes",
        params={"artifact_type": "chart_pack", "paper_id": "paper_outcome_002", "limit": 1},
    )
    assert filtered.status_code == 200
    items = filtered.json()
    assert len(items) == 1
    assert items[0]["artifact_id"] == "chartpack_outcome_new"

    abandoned = client.get(
        "/artifact-generation-outcomes",
        params={"decision": "abandoned", "downstream_use": "not_used"},
    )
    assert abandoned.status_code == 200
    abandoned_items = abandoned.json()
    assert len(abandoned_items) == 1
    assert abandoned_items[0]["artifact_type"] == "protocol_card"


def test_artifact_generation_outcome_uses_runtime_storage_log_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paperpipe_home = tmp_path / "app-home"
    monkeypatch.setenv("PAPERPIPE_HOME", str(paperpipe_home))

    client = TestClient(api_main.app)

    payload = {
        "artifact_type": "image_evidence",
        "artifact_id": "img_outcome_runtime",
        "run_id": "run_outcome_runtime",
        "decision": "escalated",
        "downstream_use": "human_review_queue",
        "actor_id": "reviewer_runtime",
        "note": "Escalated to specialist review before reuse.",
    }
    resp = client.post("/artifact-generation-outcomes", json=payload)
    assert resp.status_code == 200

    outcome_file = (paperpipe_home / "storage" / "artifact_generation_outcomes.jsonl").resolve()
    assert outcome_file.exists()
    rows = [line for line in outcome_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["artifact_id"] == payload["artifact_id"]


def test_artifact_generation_outcome_sanitizes_secret_like_note_and_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payload = {
        "artifact_type": "protocol_card",
        "artifact_id": "protocol_outcome_secret",
        "paper_id": "paper_outcome_secret",
        "run_id": "run_outcome_secret",
        "decision": "escalated",
        "downstream_use": "human_review_queue",
        "actor_id": "reviewer_secret",
        "note": (
            "Escalated with Authorization: Bearer artifact-outcome-token-123 "
            "and sk-proj-artifact-outcome-secret-abcdef removed."
        ),
        "metadata": {
            "password": "metadata-outcome-password",
            "context": "redis://paperpipe:secret@example.local/0",
        },
    }

    resp = client.post("/artifact-generation-outcomes", json=payload)
    assert resp.status_code == 200

    outcome_file = Path("storage/artifact_generation_outcomes.jsonl")
    raw_file = outcome_file.read_text(encoding="utf-8")
    assert "artifact-outcome-token-123" not in raw_file
    assert "sk-proj-artifact-outcome-secret-abcdef" not in raw_file
    assert "metadata-outcome-password" not in raw_file
    assert "redis://paperpipe:secret@example.local/0" not in raw_file

    saved = json.loads(raw_file.strip())
    assert saved["note"] == "Escalated with Authorization: <redacted> and <redacted> removed."
    assert saved["metadata"]["password"] == "<redacted>"
    assert saved["metadata"]["context"] == "<redacted>"

    listed = client.get(
        "/artifact-generation-outcomes",
        params={"artifact_id": "protocol_outcome_secret"},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["note"] == saved["note"]
    assert listed.json()[0]["metadata"] == saved["metadata"]


def test_artifact_generation_outcome_list_sanitizes_legacy_raw_secret_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outcome_file = Path("storage/artifact_generation_outcomes.jsonl")
    outcome_file.parent.mkdir(parents=True, exist_ok=True)
    outcome_file.write_text(
        json.dumps(
            {
                "outcome_id": "legacy-outcome-secret",
                "artifact_type": "meeting_pack",
                "artifact_id": "meeting_outcome_legacy_secret",
                "paper_id": "paper_outcome_legacy_secret",
                "decision": "escalated",
                "downstream_use": "human_review_queue",
                "actor_id": "reviewer_legacy",
                "note": "Legacy outcome contains Authorization: Bearer legacy-outcome-token-123.",
                "metadata": {"secret": "legacy-outcome-metadata-secret"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(api_main.app)
    listed = client.get(
        "/artifact-generation-outcomes",
        params={"artifact_id": "meeting_outcome_legacy_secret"},
    )
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["note"] == "Legacy outcome contains Authorization: <redacted>"
    assert item["metadata"]["secret"] == "<redacted>"
