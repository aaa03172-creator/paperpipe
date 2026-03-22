from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main as api_main


def test_protocol_cards_api_post_roundtrip_and_reads(tmp_path, monkeypatch) -> None:
    protocol_root = tmp_path / "protocol_cards"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/protocol-cards",
        json={
            "protocol_id": "protocol_api_demo",
            "title": "API demo protocol",
            "purpose": "Evaluate treatment response",
            "source_kind": "paper_derived",
            "linked_paper_ids": ["paper-001"],
            "linked_note_slugs": ["paper-001-note"],
            "versions": [
                {
                    "version_id": "protver_api_demo_v1",
                    "version_number": 1,
                    "key_steps_summary": ["Seed cells", "Apply treatment"],
                    "critical_conditions": ["37 C"],
                    "content_snapshot": "Step 1: seed cells\nStep 2: apply treatment",
                    "status": "active",
                    "created_by": "operator",
                    "source_refs": [{"paper_slug": "paper-001-note", "claim_id": "claim-001"}],
                }
            ],
        },
    )
    assert created.status_code == 200
    payload = created.json()

    assert payload["protocol_card"]["protocol_id"] == "protocol_api_demo"
    assert payload["protocol_card"]["current_version_id"] == "protver_api_demo_v1"
    assert payload["protocol_card"]["validation_status"] == "draft"
    assert payload["versions"][0]["version_id"] == "protver_api_demo_v1"
    assert "# API demo protocol" in payload["markdown"]
    assert (protocol_root / "protocol_api_demo" / "protocol_card.json").exists()
    assert (protocol_root / "protocol_api_demo" / "versions" / "protver_api_demo_v1.json").exists()

    fetched = client.get("/protocol-cards/protocol_api_demo")
    assert fetched.status_code == 200
    assert fetched.json()["protocol_card"]["title"] == "API demo protocol"

    listed = client.get("/protocol-cards")
    assert listed.status_code == 200
    list_payload = listed.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["protocol_id"] == "protocol_api_demo"
    assert list_payload["items"][0]["version_count"] == 1

    versions = client.get("/protocol-cards/protocol_api_demo/versions")
    assert versions.status_code == 200
    assert versions.json()["total"] == 1
    assert versions.json()["items"][0]["version_id"] == "protver_api_demo_v1"

    version_item = client.get("/protocol-cards/protocol_api_demo/versions/protver_api_demo_v1")
    assert version_item.status_code == 200
    assert version_item.json()["version_number"] == 1
    assert version_item.json()["status"] == "active"


def test_protocol_cards_api_missing_bundle_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(tmp_path / "protocol_cards"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    assert client.get("/protocol-cards/missing").status_code == 404
    assert client.get("/protocol-cards/missing/versions").status_code == 404
    assert client.get("/protocol-cards/missing/versions/protver_missing_v1").status_code == 404
