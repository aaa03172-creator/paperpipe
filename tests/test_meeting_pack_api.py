from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main as api_main
from src.profiles.profile_schema import Profile, ProfileConfig
from src.profiles.profile_store import save_profiles_snapshot
from src.profiles.research_dna_schema import RunLogEntry, ScreeningLogEntry
from src.profiles.research_dna_store import append_run_log, append_screening_log
from src.schemas.skills import SkillClaimCard, SkillClaimEvidence, SkillRunRecord, StructuredPaperState
from src.skills.storage import write_structured_state


def _write_config(path: Path, vault_path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "system:",
                "  log_level: INFO",
                "paths:",
                f"  zotero_base_dir: {vault_path}",
                f"  obsidian_vault: {vault_path}",
                "search:",
                "  constraints:",
                "    min_pubmed: 2",
                "    max_preprint: 1",
                "  slots:",
                "    primary:",
                '      query: "test"',
                "llm:",
                "  mode: local",
                "  features:",
                "    trial_extraction:",
                "      enabled: false",
                "    slot_classification:",
                "      enabled: false",
                "    one_liner:",
                "      enabled: false",
            ]
        ),
        encoding="utf-8",
    )


def _configure_env(monkeypatch: pytest.MonkeyPatch, *, config_path: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("PAPERPIPE_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(tmp_path / "meeting_packs"))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)


def _write_state(
    vault_path: Path,
    slug: str,
    *,
    entities: list[str] | None = None,
    outcomes: list[str] | None = None,
) -> None:
    state_path = vault_path / ".pp" / slug / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = StructuredPaperState(
        paper_slug=slug,
        updated_at="2026-03-13T00:00:00Z",
        runs=[
            SkillRunRecord(
                id="skill-20260313T000000Z-critical_appraisal",
                action="critical_appraisal",
                ts="2026-03-13T00:00:00Z",
                status="succeeded",
                summary="Generated claim/evidence state.",
            )
        ],
        claimset=[
            SkillClaimCard(
                id="claim_abc123",
                run_id="skill-20260313T000000Z-critical_appraisal",
                claim="Example claim about the inflammatory pathway",
                evidence=[
                    SkillClaimEvidence(
                        id="evidence_def456",
                        claim_id="claim_abc123",
                        run_id="skill-20260313T000000Z-critical_appraisal",
                        text="Evidence text",
                        locator={"page": 2, "section": "Results", "source": "state.json"},
                    )
                ],
                tags=entities or ["inflammatory pathway"],
                outcomes=outcomes or [],
            )
        ],
        entities=entities or ["inflammatory pathway"],
        outcomes=outcomes or [],
    )
    write_structured_state(state_path, state)


def _write_note(vault_path: Path, relative_path: str, body: str) -> None:
    note_path = vault_path / relative_path
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(body, encoding="utf-8")


def _write_screening_log(research_dna_root: Path, *, dna_id: str, run_id: str) -> None:
    append_screening_log(
        dna_id,
        ScreeningLogEntry(
            ts="2026-03-13T00:00:00Z",
            dna_id=dna_id,
            run_id=run_id,
            candidate_id="doi:10.1000/alpha",
            decision="exclude",
            reason_code="wrong_population",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root=research_dna_root,
    )
    append_screening_log(
        dna_id,
        ScreeningLogEntry(
            ts="2026-03-13T00:01:00Z",
            dna_id=dna_id,
            run_id=run_id,
            candidate_id="doi:10.1000/beta",
            decision="include",
            reason_code="other_noise",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root=research_dna_root,
    )


def _write_profile_run_log(
    research_dna_root: Path,
    *,
    dna_id: str,
    run_id: str,
    query_version: str,
    include_count: int,
    labeled_count: int,
) -> None:
    append_run_log(
        dna_id,
        RunLogEntry(
            ts="2026-03-13T00:10:00Z",
            run_id=run_id,
            dna_id=dna_id,
            query_version=query_version,
            status="completed",
            actor_type="human_cli",
            actor_id="tester",
            sources=["pubmed"],
            retrieved_count=max(include_count, labeled_count),
            deduped_count=max(include_count, labeled_count),
            dedupe_rate=0.0,
            pilot_n=20,
            labeled_count=labeled_count,
            include_count=include_count,
            exclude_count=max(0, labeled_count - include_count),
            unclear_count=0,
            precision_proxy=1.0 if labeled_count else 0.0,
            top_reason_codes=[],
        ),
        root=research_dna_root,
    )


def _write_projection_profile(path: Path, *, dna_id: str, query_version: str) -> str:
    profile = Profile(
        id=f"research_dna_{dna_id}",
        title=f"{dna_id} [DNA Projection]",
        enabled=False,
        schedule="manual",
        notes="\n".join(
            [
                "ResearchDNA Projection",
                "schema_version: research_dna.profile_projection.v1",
                f"source_dna_id: {dna_id}",
                f"source_query_version: {query_version}",
            ]
        ),
    )
    save_profiles_snapshot(
        ProfileConfig(profiles=[profile]),
        path,
        allow_unsafe_overwrite=True,
    )
    return profile.id


def _write_manual_profile(path: Path) -> str:
    profile = Profile(
        id="manual_profile",
        title="Manual profile",
        enabled=False,
        schedule="manual",
        notes="plain manual profile",
    )
    save_profiles_snapshot(
        ProfileConfig(profiles=[profile]),
        path,
        allow_unsafe_overwrite=True,
    )
    return profile.id


def test_meeting_pack_api_generate_and_fetch_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)
    _configure_env(monkeypatch, config_path=config_path, tmp_path=tmp_path)

    client = TestClient(api_main.app)
    generate = client.post(
        "/meeting-packs/generate",
        json={"mode": "journal_club", "source_items": [{"type": "paper_slug", "ref": slug}]},
    )

    assert generate.status_code == 200
    assert generate.json()["pack"]["readiness"] == "evidence_backed"
    assert generate.json()["markdown_sync"]["status"] == "in_sync"
    pack_id = generate.json()["pack"]["id"]

    fetched = client.get(f"/meeting-packs/{pack_id}")
    markdown = client.get(f"/meeting-packs/{pack_id}/markdown")

    assert fetched.status_code == 200
    assert markdown.status_code == 200
    assert fetched.json()["pack"]["id"] == pack_id
    assert fetched.json()["markdown_sync"]["status"] == "in_sync"
    assert "## Slide Outline" in markdown.text


def test_meeting_pack_api_supports_project_note_context_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_note(
        vault_path,
        "Projects/SCFA.md",
        "# SCFA project\n\nContext note for this topic. See [[wenzelShortchainFattyAcids2020]].\n",
    )
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)
    _configure_env(monkeypatch, config_path=config_path, tmp_path=tmp_path)

    client = TestClient(api_main.app)
    response = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "source_items": [{"type": "project_note", "ref": "Projects/SCFA.md"}],
            "max_slides": 6,
        },
    )

    assert response.status_code == 200
    pack = response.json()["pack"]
    source_types = [item["type"] for item in pack["source_items"]]
    assert "project_note" in source_types
    assert "paper_state" in source_types
    assert any("context-only inputs" in text for text in pack["one_page_summary"]["uncertainties"])


def test_meeting_pack_api_supports_screening_context_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)
    _configure_env(monkeypatch, config_path=config_path, tmp_path=tmp_path)
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_001")

    client = TestClient(api_main.app)
    response = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "literature_update",
            "source_items": [{"type": "screening_decision", "ref": "dna_test:pilot_001"}],
            "max_slides": 5,
        },
    )

    assert response.status_code == 200
    pack = response.json()["pack"]
    assert [item["type"] for item in pack["source_items"]] == ["screening_decision"]
    assert any(conflict["conflict_type"] == "selection_scope" for conflict in pack["one_page_summary"]["conflicts"])


def test_meeting_pack_api_supports_topic_exact_structured_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    _write_state(vault_path, "paper-alpha")
    _write_state(vault_path, "paper-beta", entities=["medium chain triglycerides"])
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)
    _configure_env(monkeypatch, config_path=config_path, tmp_path=tmp_path)

    client = TestClient(api_main.app)
    response = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "literature_update",
            "source_items": [{"type": "topic", "ref": "medium-chain triglycerides"}],
            "max_slides": 5,
        },
    )

    assert response.status_code == 200
    pack = response.json()["pack"]
    refs = {item["ref"] for item in pack["source_items"] if item["type"] == "paper_state"}
    assert refs == {"paper-beta"}
    assert pack["evidence_refs"]


def test_meeting_pack_api_rejects_invalid_source_type_at_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)
    _configure_env(monkeypatch, config_path=config_path, tmp_path=tmp_path)

    client = TestClient(api_main.app)
    response = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "journal_club",
            "source_items": [{"type": "not_a_real_selector", "ref": "whatever"}],
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("selector_type", ["project_profile", "research_profile"])
def test_meeting_pack_api_supports_projection_profile_selectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selector_type: str,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    _write_state(vault_path, "paper-alpha")
    dna_root = tmp_path / "research_dna"
    profiles_path = tmp_path / "profiles.yaml"
    dna_id = "dna_profile_test"
    run_id = "pilot_profile_test"
    query_version = "v2"
    _write_profile_run_log(
        dna_root,
        dna_id=dna_id,
        run_id=run_id,
        query_version=query_version,
        include_count=1,
        labeled_count=1,
    )
    append_screening_log(
        dna_id,
        ScreeningLogEntry(
            ts="2026-03-13T00:11:00Z",
            dna_id=dna_id,
            run_id=run_id,
            candidate_id="paper-alpha",
            decision="include",
            reason_code="other_noise",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root=dna_root,
    )
    profile_id = _write_projection_profile(profiles_path, dna_id=dna_id, query_version=query_version)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)
    _configure_env(monkeypatch, config_path=config_path, tmp_path=tmp_path)
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))

    client = TestClient(api_main.app)
    response = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "literature_update",
            "source_items": [{"type": selector_type, "ref": profile_id}],
            "max_slides": 5,
        },
    )

    assert response.status_code == 200
    pack = response.json()["pack"]
    assert selector_type in [item["type"] for item in pack["source_items"]]
    assert "paper_state" in [item["type"] for item in pack["source_items"]]
    assert {item["ref"] for item in pack["source_items"] if item["type"] == "paper_state"} == {"paper-alpha"}


@pytest.mark.parametrize("selector_type", ["project_profile", "research_profile"])
def test_meeting_pack_api_rejects_manual_profile_selectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selector_type: str,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    _write_state(vault_path, "paper-alpha")
    profiles_path = tmp_path / "profiles.yaml"
    profile_id = _write_manual_profile(profiles_path)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, vault_path)
    _configure_env(monkeypatch, config_path=config_path, tmp_path=tmp_path)
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))

    client = TestClient(api_main.app)
    response = client.post(
        "/meeting-packs/generate",
        json={
            "mode": "literature_update",
            "source_items": [{"type": selector_type, "ref": profile_id}],
            "max_slides": 5,
        },
    )

    assert response.status_code == 400
    assert "currently support only ResearchDNA projection profiles" in response.json()["detail"]
