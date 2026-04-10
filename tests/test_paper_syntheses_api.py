from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import paper_syntheses as paper_syntheses_router


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_note(vault_path: Path, slug: str, *, note_id: str, title: str) -> None:
    _write(
        vault_path / "Inbox" / "PaperPipe" / f"{slug}.md",
        f"---\nid: {note_id}\naliases:\n  - {title}\n---\n\n# {title}\n",
    )
    _write(
        vault_path / ".pp" / slug / "state.json",
        json.dumps(
            {
                "schema_version": "2026-03-09.chat-hooks.v1",
                "paper_slug": slug,
                "updated_at": "2026-04-08T00:00:00Z",
                "runs": [
                    {
                        "id": "run-current",
                        "action": "deep_read",
                        "ts": "2026-04-08T00:00:00Z",
                        "status": "succeeded",
                        "summary": "Canonical state snapshot",
                    }
                ],
                "signals": {"last_run_id": "run-current"},
                "claimset": [
                    {
                        "id": "claim_0",
                        "run_id": "run-current",
                        "claim": "Finding 0",
                        "evidence": [
                            {
                                "id": "evidence_0",
                                "run_id": "run-current",
                                "text": "Evidence 0",
                                "page": 1,
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                            }
                        ],
                    }
                ],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            },
            indent=2,
        ),
    )


def _write_fixture_note(vault_path: Path, slug: str, *, note_id: str, title: str) -> None:
    _write(
        vault_path / "Inbox" / "PaperPipe" / f"{slug}.md",
        f"---\nid: {note_id}\naliases:\n  - {title}\n---\n\n# {title}\n",
    )
    _write(
        vault_path / ".pp" / slug / "state.json",
        json.dumps(
            {
                "schema_version": "2026-03-09.chat-hooks.v1",
                "paper_slug": slug,
                "updated_at": "2026-04-08T00:00:00Z",
                "runs": [],
                "signals": {"last_run_id": "run-current"},
                "claimset": [
                    {
                        "id": "claim_c0ffee000001",
                        "source_claim_id": "e2e-claim-1",
                        "run_id": "run-current",
                        "claim": "Fixture finding",
                        "evidence_ids": ["evidence_deadbeef0001"],
                        "evidence": [
                            {
                                "id": "evidence_deadbeef0001",
                                "claim_id": "claim_c0ffee000001",
                                "run_id": "run-current",
                                "text": "Fixture evidence",
                                "page": 1,
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                                "locator": {"chunk_id": "chunk-e2e-001"},
                            }
                        ],
                    }
                ],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            },
            indent=2,
        ),
    )


def _write_run(artifacts_root: Path, paper_id: str, run_id: str, *, statement: str = "Finding 0") -> None:
    run_dir = artifacts_root / paper_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "succeeded",
                "finished_at": "2026-04-08T01:00:00Z",
                "parser_backend": "docling",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(
            {
                "doc_id": paper_id,
                "claims": [
                    {
                        "claim_id": "CLM-0",
                        "statement": statement,
                        "evidence_spans": [
                            {
                                "quote": "Evidence 0",
                                "page": 1,
                                "section": "Results",
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


def test_paper_syntheses_api_generate_roundtrip_with_note_id_artifact_resolution(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="doi:10.1000/a", title="Alpha Trial")
    _write_run(artifacts_root, "doi:10.1000/a", "run-current")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(paper_syntheses_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post("/paper-syntheses/generate", json={"paper_slug": "paper-alpha"})
    assert created.status_code == 200
    payload = created.json()
    synthesis_id = payload["synthesis"]["synthesis_id"]

    assert payload["synthesis"]["paper_slug"] == "paper-alpha"
    assert payload["synthesis"]["artifact_family"] == "paper_synthesis"
    assert payload["synthesis"]["template_kind"] == "paper"
    assert payload["synthesis"]["readiness"] == "evidence_backed"
    assert payload["synthesis"]["canonical_status"] == "non_canonical"
    assert payload["synthesis"]["lineage_summary"]["minimum_required_source_kinds"] == [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    assert payload["synthesis"]["lineage_summary"]["present_required_source_kinds"] == [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    assert payload["synthesis"]["lineage_summary"]["answer_route"] == "canonical_state_then_upstream_evidence"
    assert payload["synthesis"]["lineage_summary"]["review_artifact_kinds"] == []
    assert {item["kind"] for item in payload["synthesis"]["source_refs"]} >= {
        "structured_state",
        "claimset_resolved",
        "run_meta",
    }
    assert "Promoted biomedical answers must jump back" in payload["markdown"]
    assert (output_root / synthesis_id / "paper_synthesis.json").exists()
    assert (output_root / synthesis_id / "paper_synthesis.md").exists()

    fetched = client.get(f"/paper-syntheses/{synthesis_id}")
    assert fetched.status_code == 200
    assert fetched.json()["synthesis"]["synthesis_id"] == synthesis_id
    assert fetched.headers.get("PaperPipe-Compatibility-Route") == "paper_synthesis_bundle"
    assert fetched.headers.get("PaperPipe-Preferred-Manifest-Route") == f"/paper-syntheses/{synthesis_id}/manifest"
    assert fetched.headers.get("PaperPipe-Preferred-Markdown-Route") == f"/paper-syntheses/{synthesis_id}/markdown"
    manifest = client.get(f"/paper-syntheses/{synthesis_id}/manifest")
    assert manifest.status_code == 200
    assert manifest.json()["synthesis_id"] == synthesis_id
    assert manifest.json()["lineage_summary"]["answer_route"] == "canonical_state_then_upstream_evidence"

    markdown = client.get(f"/paper-syntheses/{synthesis_id}/markdown")
    assert markdown.status_code == 200
    assert markdown.text.startswith("---\nartifact_family: paper_synthesis\n")


def test_paper_syntheses_openapi_marks_bundle_route_as_compatibility_fetch(tmp_path, monkeypatch):
    output_root = tmp_path / "paper_syntheses"
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]

    bundle_route = paths["/paper-syntheses/{synthesis_id}"]["get"]
    manifest_route = paths["/paper-syntheses/{synthesis_id}/manifest"]["get"]
    markdown_route = paths["/paper-syntheses/{synthesis_id}/markdown"]["get"]

    assert bundle_route["deprecated"] is True
    assert "compatibility route" in bundle_route["summary"].lower()
    assert "/paper-syntheses/{synthesis_id}/manifest" in bundle_route["description"]
    assert bundle_route.get("deprecated") is True
    assert manifest_route.get("deprecated") is not True
    assert markdown_route.get("deprecated") is not True


def test_paper_syntheses_api_lists_recent_first(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="paper-alpha", title="Alpha Trial")
    _write_note(vault_dir, "paper-beta", note_id="paper-beta", title="Beta Trial")
    _write_run(artifacts_root, "paper-alpha", "run-alpha", statement="Alpha finding")
    _write_run(artifacts_root, "paper-beta", "run-beta", statement="Beta finding")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(paper_syntheses_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    older = client.post("/paper-syntheses/generate", json={"paper_slug": "paper-alpha"})
    newer = client.post("/paper-syntheses/generate", json={"paper_slug": "paper-beta"})
    assert older.status_code == 200
    assert newer.status_code == 200

    listed = client.get("/paper-syntheses")
    assert listed.status_code == 200
    payload = listed.json()

    assert payload["total"] == 2
    assert [item["paper_slug"] for item in payload["items"]] == ["paper-beta", "paper-alpha"]
    assert payload["items"][0]["canonical_status"] == "non_canonical"
    assert payload["items"][0]["source_ref_count"] >= 3
    assert payload["items"][0]["evidence_ref_count"] == 1
    assert payload["items"][0]["lineage_summary"]["present_required_source_kinds"] == [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    assert payload["items"][0]["lineage_summary"]["review_artifact_kinds"] == []


def test_paper_syntheses_api_can_filter_by_paper_slug(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="paper-alpha", title="Alpha Trial")
    _write_note(vault_dir, "paper-beta", note_id="paper-beta", title="Beta Trial")
    _write_run(artifacts_root, "paper-alpha", "run-alpha", statement="Alpha finding")
    _write_run(artifacts_root, "paper-beta", "run-beta", statement="Beta finding")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(paper_syntheses_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    assert client.post("/paper-syntheses/generate", json={"paper_slug": "paper-alpha"}).status_code == 200
    assert client.post("/paper-syntheses/generate", json={"paper_slug": "paper-beta"}).status_code == 200

    filtered = client.get("/paper-syntheses", params={"paper_slug": "paper-beta"})

    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["total"] == 1
    assert [item["paper_slug"] for item in payload["items"]] == ["paper-beta"]
    assert payload["items"][0]["canonical_status"] == "non_canonical"
    assert payload["items"][0]["lineage_summary"]["answer_route"] == "canonical_state_then_upstream_evidence"


def test_paper_syntheses_api_returns_404_when_missing(tmp_path, monkeypatch):
    output_root = tmp_path / "paper_syntheses"
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    response = client.get("/paper-syntheses/papersynth_missing")

    assert response.status_code == 404


def test_paper_syntheses_api_generate_rejects_fixture_structured_state_by_default(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_fixture_note(vault_dir, "paper-alpha", note_id="doi:10.1000/a", title="Alpha Trial")
    _write_run(artifacts_root, "doi:10.1000/a", "run-current")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(paper_syntheses_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    response = client.post("/paper-syntheses/generate", json={"paper_slug": "paper-alpha"})

    assert response.status_code == 404
    assert "appears to be a test fixture" in response.json()["detail"]
