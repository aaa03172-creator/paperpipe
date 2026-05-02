from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import meeting_packs as meeting_packs_router
from tests.meeting_pack_actual_paper_fixture import ACTUAL_PAPER_ALIGNED_TITLE, write_actual_paper_aligned_source


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_state(
    vault_path: Path,
    slug: str,
    *,
    claim_text: str = "Intervention changed the inflammatory pathway.",
    claim_id: str = "claim_abc123",
    source_claim_id: str | None = None,
    evidence_id: str = "evidence_def456",
    chunk_id: str | None = None,
    include_direct_evidence: bool = True,
    grounded: bool | None = None,
    resolution: str | None = None,
) -> None:
    state_path = vault_path / ".pp" / slug / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "2026-03-09.chat-hooks.v1",
                "paper_slug": slug,
                "updated_at": "2026-03-13T00:00:00Z",
                "runs": [
                    {
                        "id": "skill-20260313T000000Z-critical_appraisal",
                        "action": "critical_appraisal",
                        "ts": "2026-03-13T00:00:00Z",
                        "status": "succeeded",
                        "summary": "Generated claim/evidence state.",
                    }
                ],
                "signals": {"has_claimset": True},
                "claimset": [
                    {
                        "id": claim_id,
                        "run_id": "skill-20260313T000000Z-critical_appraisal",
                        "source_claim_id": source_claim_id,
                        "claim": claim_text,
                        "evidence_ids": [evidence_id] if include_direct_evidence else [],
                        "evidence": (
                            [
                                {
                                    "id": evidence_id,
                                    "claim_id": claim_id,
                                    "run_id": "skill-20260313T000000Z-critical_appraisal",
                                    "text": "Evidence text",
                                    "locator": {
                                        "page": 2,
                                        "section": "Results",
                                        "source": "state.json",
                                        "chunk_id": chunk_id,
                                    },
                                    "grounded": grounded,
                                    "resolution": resolution,
                                }
                            ]
                            if include_direct_evidence
                            else []
                        ),
                    }
                ],
                "entities": ["inflammatory pathway"],
                "mesh": [],
                "outcomes": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_legacy_pack(root: Path, *, pack_id: str, slug: str) -> None:
    pack_dir = root / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "meeting_pack.json").write_text(
        json.dumps(
            {
                "id": pack_id,
                "mode": "journal_club",
                "title": "Legacy draft",
                "created_at": datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc).isoformat(),
                "status": "draft",
                "readiness": "evidence_backed",
                "source_items": [
                    {
                        "id": "src_01",
                        "type": "paper_slug",
                        "ref": slug,
                        "title": slug,
                        "priority": 1,
                        "included": True,
                    }
                ],
                "one_page_summary": {"overview": "Legacy summary"},
                "slides": [],
                "speaker_notes": [],
                "discussion_questions": [],
                "expected_questions": [],
                "next_steps": [],
                "evidence_refs": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (pack_dir / "meeting_pack.md").write_text("# Legacy draft\n", encoding="utf-8")


def test_meeting_packs_api_generates_roundtrip_and_markdown(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_dir, slug)
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        "---\naliases:\n  - SCFA paper\n---\n\n# SCFA paper\n",
    )

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 200
    payload = created.json()
    pack_id = payload["pack"]["id"]

    assert payload["pack"]["readiness"] == "evidence_backed"
    assert payload["markdown_sync"]["status"] == "in_sync"
    assert 5 <= len(payload["pack"]["slides"]) <= 8
    assert payload["pack"]["slides"][0]["evidence_refs"]
    assert (meeting_root / pack_id / "meeting_pack.json").exists()
    assert (meeting_root / pack_id / "meeting_pack.md").exists()

    fetched = client.get(f"/meeting-packs/{pack_id}")
    assert fetched.status_code == 200
    assert fetched.json()["pack"]["id"] == pack_id
    assert fetched.json()["markdown_sync"]["status"] == "in_sync"

    trace = client.get(f"/meeting-packs/{pack_id}/trace")
    assert trace.status_code == 200
    assert trace.json()["pack_id"] == pack_id
    assert trace.json()["available"] is True
    assert trace.json()["summary"]["matched_paper_slugs"] == [slug]
    assert trace.json()["summary"]["source_paths"] == [f".pp/{slug}/state.json"]

    validation = client.get(f"/meeting-packs/{pack_id}/validate")
    assert validation.status_code == 200
    assert validation.json()["validation"]["readiness"] == "evidence_backed"
    assert validation.json()["validation"]["markdown_sync"]["status"] == "in_sync"
    assert validation.json()["validation"]["can_regenerate"] is True
    assert validation.json()["validation"]["regenerate_strategy"] == "saved_request"

    markdown = client.get(f"/meeting-packs/{pack_id}/markdown")
    assert markdown.status_code == 200
    assert "## Slide Outline" in markdown.text


def test_meeting_packs_api_claim_without_direct_support_stays_background_only(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "claim-without-support"
    _write_state(vault_dir, slug, include_direct_evidence=False)

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 200
    payload = created.json()["pack"]

    assert payload["readiness"] == "background_only"
    assert "Structured evidence refs are missing" in (
        payload["one_page_summary"]["key_points"][0]["uncertainty_note"] or ""
    )


def test_meeting_packs_api_validate_surfaces_content_risk_warnings(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "alz-clinical-biological-construct"
    _write_state(
        vault_dir,
        slug,
        claim_text="The intervention shows an initial improvement window during early follow-up.",
    )

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "title": "Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 200
    pack_id = created.json()["pack"]["id"]

    validation = client.get(f"/meeting-packs/{pack_id}/validate")
    assert validation.status_code == 200
    warnings = validation.json()["validation"]["warnings"]
    assert any("Generic key-point wording was detected" in warning for warning in warnings)
    assert any("do not appear semantically aligned" in warning for warning in warnings)


def test_meeting_packs_api_keeps_abstract_aligned_actual_paper_probe_content_in_sync(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024"
    write_actual_paper_aligned_source(vault_dir, slug)

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 200
    payload = created.json()
    pack_id = payload["pack"]["id"]

    assert payload["pack"]["readiness"] == "evidence_backed"
    assert payload["pack"]["source_items"][0]["title"] == ACTUAL_PAPER_ALIGNED_TITLE
    assert ACTUAL_PAPER_ALIGNED_TITLE in payload["pack"]["title"]
    assert payload["markdown_sync"]["status"] == "in_sync"
    assert len(payload["pack"]["evidence_refs"]) == 3
    assert any(
        "clinical-biological construct" in key_point["text"].lower()
        for key_point in payload["pack"]["one_page_summary"]["key_points"]
    )

    gate = json.loads((meeting_root / pack_id / "quality_gate.json").read_text(encoding="utf-8"))
    check_map = {check["name"]: check for check in gate["checks"]}
    assert gate["overall_status"] == "pass"
    assert gate["reason_codes"] == []
    assert check_map["content_quality_risk_scan"]["status"] == "pass"

    validation = client.get(f"/meeting-packs/{pack_id}/validate")
    assert validation.status_code == 200
    validation_payload = validation.json()["validation"]
    assert validation_payload["markdown_sync"]["status"] == "in_sync"
    assert validation_payload["can_regenerate"] is True
    assert validation_payload["regenerate_strategy"] == "saved_request"
    assert validation_payload["warnings"] == []

    markdown = client.get(f"/meeting-packs/{pack_id}/markdown")
    assert markdown.status_code == 200
    assert "clinical-biological construct" in markdown.text.lower()


def test_meeting_packs_api_rejects_fixture_like_structured_state_by_default(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "real-looking-paper"
    _write_state(
        vault_dir,
        slug,
        claim_text="Fixture-like claim.",
        claim_id="claim_c0ffee000001",
        source_claim_id="e2e-claim-1",
        evidence_id="evidence_deadbeef0001",
        chunk_id="chunk-e2e-001",
    )

    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 400
    assert "appears to be a test fixture" in created.json()["detail"]


def test_meeting_packs_api_rejects_fixture_like_generation_request_by_default(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_dir, slug)

    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "title": "Backend visual meeting pack fixture",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )

    assert created.status_code == 400
    assert "test fixture" in created.json()["detail"]


def test_meeting_packs_api_allows_fixture_like_generation_request_in_e2e_runtime(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_dir, slug)

    monkeypatch.setenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", "1")
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "title": "Backend visual meeting pack fixture",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )

    assert created.status_code == 200
    assert created.json()["pack"]["title"] == "Backend visual meeting pack fixture"


def test_meeting_packs_api_lists_saved_packs_with_recent_first_order(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    _write_state(vault_dir, "paper-alpha")
    _write_state(vault_dir, "paper-beta")

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    older = client.post(
        "/meeting-packs/generate",
        json={
          "mode": "journal_club",
          "title": "Older draft",
          "source_items": [{"type": "paper_slug", "ref": "paper-alpha"}],
          "max_slides": 5,
        },
    )
    newer = client.post(
        "/meeting-packs/generate",
        json={
          "mode": "experiment_proposal",
          "title": "Newer draft",
          "source_items": [{"type": "paper_slug", "ref": "paper-beta"}],
          "max_slides": 5,
        },
    )
    assert older.status_code == 200
    assert newer.status_code == 200

    listed = client.get("/meeting-packs")
    assert listed.status_code == 200
    payload = listed.json()

    assert payload["total"] == 2
    assert [item["pack_id"] for item in payload["items"]] == [
        newer.json()["pack"]["id"],
        older.json()["pack"]["id"],
    ]
    assert payload["items"][0]["title"] == "Newer draft"
    assert payload["items"][0]["trace_entry_count"] == 2

    api_prefixed = client.get("/api/meeting-packs")
    assert api_prefixed.status_code == 200
    api_payload = api_prefixed.json()
    assert api_payload["total"] == 2
    assert [item["pack_id"] for item in api_payload["items"]] == [
        newer.json()["pack"]["id"],
        older.json()["pack"]["id"],
    ]


def test_meeting_packs_api_regenerates_and_rerenders_from_saved_pack(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_dir, slug)

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "title": "Custom meeting draft",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 200
    original = created.json()["pack"]
    original_id = original["id"]
    assert original["generation_request"]["max_slides"] == 5

    regenerated = client.post(f"/meeting-packs/{original_id}/regenerate")
    assert regenerated.status_code == 200
    regenerated_pack = regenerated.json()["pack"]
    assert regenerated_pack["id"] != original_id
    assert regenerated_pack["title"] == "Custom meeting draft"
    assert regenerated_pack["regenerated_from_pack_id"] == original_id
    assert regenerated_pack["generation_request"] == original["generation_request"]
    assert regenerated.json()["markdown_sync"]["status"] == "in_sync"

    markdown_path = meeting_root / original_id / "meeting_pack.md"
    markdown_path.write_text("# Corrupted\n", encoding="utf-8")

    drifted = client.get(f"/meeting-packs/{original_id}")
    assert drifted.status_code == 200
    assert drifted.json()["markdown_sync"]["status"] == "drifted"

    rerendered = client.post(f"/meeting-packs/{original_id}/rerender")
    assert rerendered.status_code == 200
    assert rerendered.json()["pack"]["id"] == original_id
    assert rerendered.json()["markdown_sync"]["status"] == "in_sync"
    assert "## Slide Outline" in rerendered.json()["markdown"]
    assert markdown_path.read_text(encoding="utf-8") == rerendered.json()["markdown"]


def test_meeting_packs_api_supports_bounded_legacy_regenerate_and_validate(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_dir, slug)
    legacy_id = "meetingpack_20260313T090000Z_journal_club_legacy001"
    _write_legacy_pack(meeting_root, pack_id=legacy_id, slug=slug)

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    validation = client.get(f"/meeting-packs/{legacy_id}/validate")
    assert validation.status_code == 200
    assert validation.json()["validation"]["can_regenerate"] is True
    assert validation.json()["validation"]["regenerate_strategy"] == "legacy_source_items"

    trace = client.get(f"/meeting-packs/{legacy_id}/trace")
    assert trace.status_code == 200
    assert trace.json()["available"] is False
    assert trace.json()["trace"] == []
    assert trace.json()["summary"]["entry_count"] == 0

    regenerated = client.post(f"/meeting-packs/{legacy_id}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()["pack"]["regenerated_from_pack_id"] == legacy_id


def test_meeting_packs_api_validate_marks_regenerate_unavailable_when_sources_are_missing(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_dir, slug)

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "source_items": [{"type": "paper_slug", "ref": slug}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 200
    pack_id = created.json()["pack"]["id"]

    shutil.rmtree(vault_dir)

    validation = client.get(f"/meeting-packs/{pack_id}/validate")
    assert validation.status_code == 200
    assert validation.json()["validation"]["can_regenerate"] is False
    assert validation.json()["validation"]["regenerate_strategy"] == "unavailable"
    assert any(
        "vault path is unavailable" in warning or "source validation failed" in warning
        for warning in validation.json()["validation"]["warnings"]
    )


def test_meeting_packs_api_supports_project_note_selection(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    meeting_root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_dir, slug)
    _write(vault_dir / "Projects" / "SCFA.md", "# SCFA project\n\nSee [[wenzelShortchainFattyAcids2020]].\n")

    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(meeting_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(meeting_packs_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "project_progress_update",
            "source_items": [{"type": "project_note", "ref": "Projects/SCFA.md"}],
            "max_slides": 5,
        },
    )
    assert created.status_code == 200
    payload = created.json()["pack"]

    assert payload["source_items"][0]["type"] == "project_note"
    assert any(item["type"] == "paper_state" for item in payload["source_items"])
    assert payload["slides"][0]["slide_title"] == "What changed for the project"
