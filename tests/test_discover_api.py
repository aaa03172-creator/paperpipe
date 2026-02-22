from __future__ import annotations

from fastapi.testclient import TestClient

import backend.main as api_main


def test_discover_queue_endpoint_smoke(monkeypatch):
    expected = {
        "seed": "seed-paper",
        "saved": 2,
        "recommended": 1,
        "pending_queue": 1,
        "note_path": "vault/Inbox/PaperPipe/seed-paper.md",
        "items": [
            {
                "paper_id": "doi:10.1000/recommended",
                "title": "Recommended Work",
                "status": "RECOMMENDED",
                "score": 0.9,
                "relation": "referenced",
                "year": 2024,
                "venue": "Nature Medicine",
                "doi": "10.1000/recommended",
                "reason": "relation=referenced, citations=150, score=0.900, year=2024",
            }
        ],
    }

    monkeypatch.setattr("backend.routers.discover.run_discovery_queue", lambda **kwargs: expected)
    client = TestClient(api_main.app)

    resp = client.post(
        "/discover/queue",
        json={"seed": "seed-paper", "limit": 10, "write_obsidian": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["seed"] == "seed-paper"
    assert body["saved"] == 2
    assert body["recommended"] == 1
    assert body["pending_queue"] == 1
    assert body["items"][0]["paper_id"] == "doi:10.1000/recommended"
