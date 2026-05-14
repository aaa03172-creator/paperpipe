from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import protocol_cards as protocol_cards_router
from src.services.runtime_paths import preferred_artifact_paper_dir


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_jsonl_rows(path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_note(vault_path, slug: str, *, note_id: str, title: str, body: str) -> None:
    _write(
        vault_path / "Inbox" / "PaperPipe" / f"{slug}.md",
        f"---\nid: {note_id}\ntitle: {title}\n---\n\n{body.strip()}\n",
    )


def _write_structured_state(vault_path, slug: str, *, run_id: str) -> None:
    _write(
        vault_path / ".pp" / slug / "state.json",
        json.dumps(
            {
                "schema_version": "2026-03-09.chat-hooks.v1",
                "paper_slug": slug,
                "updated_at": "2026-04-10T09:00:00Z",
                "runs": [
                    {
                        "id": run_id,
                        "action": "deep_read",
                        "ts": "2026-04-10T09:00:00Z",
                        "status": "succeeded",
                        "summary": "Canonical state snapshot",
                    }
                ],
                "signals": {"last_run_id": run_id},
                "claimset": [],
                "entities": [],
                "mesh": [],
                "outcomes": ["Cell viability"],
            },
            indent=2,
        ),
    )


def _write_resolved_claimset(artifacts_root, paper_id: str, run_id: str) -> None:
    run_dir = preferred_artifact_paper_dir(paper_id, root=artifacts_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(
            {
                "doc_id": paper_id,
                "claims": [
                    {
                        "claim_id": "CLM-0",
                        "statement": "Cells were seeded before treatment.",
                        "type": "procedure",
                        "evidence_spans": [
                            {
                                "quote": "Cells were seeded into assay plates.",
                                "page": 1,
                                "section": "Methods",
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


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

    markdown = client.get("/protocol-cards/protocol_api_demo/markdown")
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/plain")
    assert "# API demo protocol" in markdown.text

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


def test_protocol_cards_api_records_generation_outcome(tmp_path, monkeypatch) -> None:
    protocol_root = tmp_path / "protocol_cards"
    outcome_path = tmp_path / "storage" / "artifact_generation_outcomes.jsonl"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH", str(outcome_path))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/protocol-cards",
        json={
            "protocol_id": "protocol_api_outcome",
            "title": "API outcome protocol",
            "source_kind": "paper_derived",
            "linked_paper_ids": ["paper-001"],
            "versions": [
                {
                    "version_id": "protver_api_outcome_v1",
                    "version_number": 1,
                    "content_snapshot": "Step 1: seed cells",
                    "status": "active",
                    "created_by": "operator",
                }
            ],
        },
    )
    assert created.status_code == 200

    response = client.post(
        "/protocol-cards/protocol_api_outcome/outcome",
        json={
            "paper_id": "paper-001",
            "decision": "reused",
            "downstream_use": "supporting_context",
            "actor_id": "reviewer_001",
            "note": "Used as supporting context for the next lab packet.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert isinstance(response.json()["outcome_id"], str)

    rows = _read_jsonl_rows(outcome_path)
    assert len(rows) == 1
    assert rows[0]["artifact_type"] == "protocol_card"
    assert rows[0]["artifact_id"] == "protocol_api_outcome"
    assert rows[0]["decision"] == "reused"
    assert rows[0]["downstream_use"] == "supporting_context"


def test_protocol_cards_api_records_review_feedback(tmp_path, monkeypatch) -> None:
    protocol_root = tmp_path / "protocol_cards"
    feedback_path = tmp_path / "storage" / "artifact_review_feedback.jsonl"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.setenv("PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH", str(feedback_path))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    created = client.post(
        "/protocol-cards",
        json={
            "protocol_id": "protocol_api_review",
            "title": "API review protocol",
            "source_kind": "paper_derived",
            "linked_paper_ids": ["paper-001"],
            "versions": [
                {
                    "version_id": "protver_api_review_v1",
                    "version_number": 1,
                    "content_snapshot": "Step 1: seed cells",
                    "status": "active",
                    "created_by": "operator",
                }
            ],
        },
    )
    assert created.status_code == 200

    response = client.post(
        "/protocol-cards/protocol_api_review/review",
        json={
            "paper_id": "paper-001",
            "decision": "correct",
            "reason_code": "missing_detail",
            "actor_id": "reviewer_001",
            "note": "Needs one more procedural detail before reuse.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert isinstance(response.json()["feedback_id"], str)

    rows = _read_jsonl_rows(feedback_path)
    assert len(rows) == 1
    assert rows[0]["artifact_type"] == "protocol_card"
    assert rows[0]["artifact_id"] == "protocol_api_review"
    assert rows[0]["decision"] == "correct"
    assert rows[0]["reason_code"] == "missing_detail"


def test_protocol_cards_api_builds_draft_from_note(tmp_path, monkeypatch) -> None:
    protocol_root = tmp_path / "protocol_cards"
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    _write_note(
        vault_dir,
        "paper-alpha",
        note_id="doi:10.1000/a",
        title="Alpha Trial",
        body=(
            "# Alpha Trial\n\n"
            "## Methods\n"
            "- Prepare cells\n"
            "- Apply treatment\n"
            "- Measure viability\n"
        ),
    )
    _write_structured_state(vault_dir, "paper-alpha", run_id="run-current")
    _write_resolved_claimset(artifacts_root, "doi:10.1000/a", "run-current")

    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    monkeypatch.setattr(
        protocol_cards_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.post("/protocol-cards/draft-from-note", json={"note_slug": "paper-alpha"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["title"] == "Alpha Trial protocol draft"
    assert payload["draft"]["linked_paper_ids"] == ["doi:10.1000/a"]
    assert payload["draft"]["versions"][0]["key_steps_summary"] == [
        "Prepare cells",
        "Apply treatment",
        "Measure viability",
    ]
    assert payload["source_summary"]["run_id"] == "run-current"
    assert payload["source_summary"]["used_structured_state"] is True
    assert payload["source_summary"]["used_claimset"] is True
    assert payload["source_summary"]["claim_count"] == 1
    assert payload["source_summary"]["evidence_count"] == 1
    assert payload["warnings"] == []


def test_protocol_cards_api_missing_bundle_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(tmp_path / "protocol_cards"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    assert client.get("/protocol-cards/protocol_missing").status_code == 404
    assert client.get("/protocol-cards/protocol_missing/markdown").status_code == 404
    assert client.get("/protocol-cards/protocol_missing/versions").status_code == 404
    assert client.get("/protocol-cards/protocol_missing/versions/protver_missing_v1").status_code == 404
    assert client.post(
        "/protocol-cards/protocol_missing/outcome",
        json={
            "paper_id": "paper-001",
            "decision": "abandoned",
            "downstream_use": "not_used",
            "actor_id": "reviewer_001",
            "note": "Missing bundle.",
        },
    ).status_code == 404
    assert client.post(
        "/protocol-cards/protocol_missing/review",
        json={
            "paper_id": "paper-001",
            "decision": "reject",
            "reason_code": "missing_bundle",
            "actor_id": "reviewer_001",
            "note": "Missing bundle.",
        },
    ).status_code == 404


def test_protocol_cards_api_does_not_resolve_encoded_traversal_ids_outside_root(tmp_path, monkeypatch) -> None:
    protocol_root = tmp_path / "protocol_cards"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    (outside / "protocol_card.json").write_text('{"sentinel":"do-not-read"}', encoding="utf-8")
    (outside / "protocol_card.md").write_text("SENTINEL-MARKDOWN", encoding="utf-8")
    (outside / "versions").mkdir()
    (outside / "versions" / "protver_escape_v1.json").write_text(
        '{"sentinel":"version-do-not-read"}',
        encoding="utf-8",
    )

    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    responses = [
        client.get("/protocol-cards/..%2Foutside"),
        client.get("/protocol-cards/..%2Foutside/markdown"),
        client.get("/protocol-cards/..%2Foutside/versions"),
        client.get("/protocol-cards/..%2Foutside/versions/protver_escape_v1"),
        client.get("/protocol-cards/protocol_safe/versions/..%2Fprotver_escape_v1"),
        client.post(
            "/protocol-cards/..%2Foutside/outcome",
            json={
                "paper_id": "paper-001",
                "decision": "abandoned",
                "downstream_use": "not_used",
                "actor_id": "reviewer_001",
                "note": "Traversal probe.",
            },
        ),
        client.post(
            "/protocol-cards/..%2Foutside/review",
            json={
                "paper_id": "paper-001",
                "decision": "reject",
                "reason_code": "traversal_probe",
                "actor_id": "reviewer_001",
                "note": "Traversal probe.",
            },
        ),
    ]

    assert all(response.status_code in {400, 404} for response in responses)
    combined = "\n".join(response.text for response in responses)
    assert "SENTINEL" not in combined
    assert "do-not-read" not in combined


def test_protocol_cards_api_draft_from_note_returns_404_for_missing_note(tmp_path, monkeypatch) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(tmp_path / "protocol_cards"))
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    monkeypatch.setattr(
        protocol_cards_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.post("/protocol-cards/draft-from-note", json={"note_slug": "missing-note"})

    assert response.status_code == 404


def test_protocol_card_version_detail_requires_parent_bundle(tmp_path, monkeypatch) -> None:
    protocol_root = tmp_path / "protocol_cards"
    version_dir = protocol_root / "protocol_orphan_demo" / "versions"
    version_dir.mkdir(parents=True)
    (version_dir / "protver_orphan_demo_v1.json").write_text(
        json.dumps(
            {
                "version_id": "protver_orphan_demo_v1",
                "protocol_id": "protocol_orphan_demo",
                "version_number": 1,
                "content_snapshot": "Step 1",
                "status": "active",
                "created_by": "operator",
                "created_at": "2026-03-22T12:00:00Z",
                "source_refs": [{"paper_slug": "paper-001-note"}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(protocol_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    assert client.get("/protocol-cards/protocol_orphan_demo/versions").status_code == 404
    assert client.get("/protocol-cards/protocol_orphan_demo/versions/protver_orphan_demo_v1").status_code == 404
