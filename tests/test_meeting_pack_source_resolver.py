from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.meeting_packs.evidence import build_meeting_pack_evidence_ledger
from src.meeting_packs.source_resolver import resolve_meeting_pack_sources
from src.profiles.profile_schema import Profile, ProfileConfig
from src.profiles.profile_store import save_profiles_snapshot
from src.profiles.research_dna_schema import RunLogEntry, ScreeningLogEntry
from src.profiles.research_dna_store import append_run_log, append_screening_log, research_dna_log_path
from src.schemas.meeting_pack import MeetingPackSourceSelector
from src.schemas.skills import SkillClaimCard, SkillClaimEvidence, SkillRunRecord, StructuredPaperState
from src.skills.storage import write_structured_state


def _write_state(
    vault_path: Path,
    slug: str,
    *,
    entities: list[str] | None = None,
    outcomes: list[str] | None = None,
    tags: list[str] | None = None,
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
                tags=tags or ["inflammatory pathway"],
                outcomes=outcomes or [],
            )
        ],
        entities=entities or ["inflammatory pathway"],
        outcomes=outcomes or [],
    )
    write_structured_state(state_path, state)


def _write_fixture_state(vault_path: Path, slug: str) -> None:
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
                id="claim_c0ffee000001",
                run_id="skill-20260313T000000Z-critical_appraisal",
                claim="Fixture-like claim.",
                source_claim_id="e2e-claim-1",
                evidence=[
                    SkillClaimEvidence(
                        id="evidence_deadbeef0001",
                        claim_id="claim_c0ffee000001",
                        run_id="skill-20260313T000000Z-critical_appraisal",
                        text="Fixture evidence",
                        locator={"page": 2, "section": "Results", "source": "state.json", "chunk_id": "chunk-e2e-001"},
                    )
                ],
                tags=["fixture"],
            )
        ],
    )
    write_structured_state(state_path, state)


def _write_screening_log(
    research_dna_root: Path,
    *,
    dna_id: str,
    run_id: str,
    start_minute: int = 0,
) -> None:
    append_screening_log(
        dna_id,
        ScreeningLogEntry(
            ts=f"2026-03-13T00:{start_minute:02d}:00Z",
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
            ts=f"2026-03-13T00:{start_minute + 1:02d}:00Z",
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


def test_meeting_pack_source_resolver_loads_paper_slug_state(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[MeetingPackSourceSelector(type="paper_slug", ref=slug)],
    )

    assert len(bundle.sources) == 1
    assert bundle.selected_items[0].type == "paper_slug"
    assert bundle.sources[0].source_item.ref == slug
    assert bundle.sources[0].structured_state.paper_slug == slug
    assert [entry.action for entry in bundle.retrieval_trace] == ["selector_selected", "paper_state_loaded"]
    assert bundle.retrieval_trace[-1].matched_paper_slugs == [slug]
    assert bundle.retrieval_trace[-1].source_path == f".pp/{slug}/state.json"


def test_meeting_pack_source_resolver_rejects_missing_structured_state(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_meeting_pack_sources(
            vault_path=tmp_path / "vault",
            source_selectors=[MeetingPackSourceSelector(type="paper_slug", ref="missing-paper")],
        )


def test_meeting_pack_source_resolver_rejects_fixture_state_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)
    vault_path = tmp_path / "vault"
    slug = "real-looking-paper"
    _write_fixture_state(vault_path, slug)

    with pytest.raises(ValueError, match="appears to be a test fixture"):
        resolve_meeting_pack_sources(
            vault_path=vault_path,
            source_selectors=[MeetingPackSourceSelector(type="paper_slug", ref=slug)],
        )


def test_meeting_pack_source_resolver_allows_fixture_state_when_opted_in(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", "1")
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)
    vault_path = tmp_path / "vault"
    slug = "real-looking-paper"
    _write_fixture_state(vault_path, slug)

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[MeetingPackSourceSelector(type="paper_slug", ref=slug)],
    )

    assert bundle.sources[0].structured_state.paper_slug == slug


def test_meeting_pack_source_resolver_loads_project_note_links(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    project_note = vault_path / "Projects" / "SCFA.md"
    project_note.parent.mkdir(parents=True, exist_ok=True)
    project_note.write_text("# SCFA project\n\nSee [[wenzelShortchainFattyAcids2020]].\n", encoding="utf-8")

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[MeetingPackSourceSelector(type="project_note", ref="Projects/SCFA.md")],
    )

    assert bundle.selected_items[0].type == "project_note"
    assert bundle.selected_items[0].title == "SCFA project"
    assert [source.structured_state.paper_slug for source in bundle.sources] == [slug]


def test_meeting_pack_source_resolver_rejects_escaping_note_selector(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    outside_note = tmp_path / "outside.md"
    outside_note.write_text("# Outside\n\nSee [[paper-alpha]].\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        resolve_meeting_pack_sources(
            vault_path=vault_path,
            source_selectors=[MeetingPackSourceSelector(type="project_note", ref="../outside.md")],
        )


def test_meeting_pack_source_resolver_loads_paper_note_by_own_slug_when_unlinked(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    note_path = vault_path / "Inbox" / f"{slug}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Paper note\n\nNo explicit linked paper list.\n", encoding="utf-8")

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[MeetingPackSourceSelector(type="paper_note", ref=f"Inbox/{slug}.md")],
    )

    assert bundle.selected_items[0].type == "paper_note"
    assert [source.structured_state.paper_slug for source in bundle.sources] == [slug]
    assert [entry.action for entry in bundle.retrieval_trace] == [
        "selector_selected",
        "note_fallback_resolved",
        "paper_states_loaded",
    ]
    assert bundle.retrieval_trace[1].matched_paper_slugs == [slug]
    assert bundle.retrieval_trace[2].metadata["loaded_slugs"] == [slug]


def test_meeting_pack_source_resolver_rejects_unlinked_project_note_without_explicit_papers(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault"
    _write_state(vault_path, "paper-alpha")
    note_path = vault_path / "Projects" / "Unlinked.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Unlinked project\n\nNo linked papers here.\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="No structured paper states resolved from project_note"):
        resolve_meeting_pack_sources(
            vault_path=vault_path,
            source_selectors=[MeetingPackSourceSelector(type="project_note", ref="Projects/Unlinked.md")],
        )


def test_meeting_pack_source_resolver_loads_screening_run_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "vault"
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_001")

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[MeetingPackSourceSelector(type="screening_decision", ref="dna_test:pilot_001")],
    )

    assert bundle.sources == []
    assert bundle.selected_items[0].type == "screening_decision"
    assert bundle.screening_contexts[0].run_id == "pilot_001"
    assert bundle.screening_contexts[0].include_count == 1
    assert bundle.screening_contexts[0].exclude_count == 1
    assert set(bundle.screening_contexts[0].top_reason_codes) == {"wrong_population", "other_noise"}


def test_meeting_pack_source_resolver_sanitizes_legacy_screening_notes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "vault"
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))
    screening_path = research_dna_log_path("dna_test", "screening", dna_root)
    screening_path.parent.mkdir(parents=True, exist_ok=True)
    screening_path.write_text(
        json.dumps(
            {
                "ts": "2026-03-13T00:00:00Z",
                "dna_id": "dna_test",
                "run_id": "pilot_secret_001",
                "candidate_id": "doi:10.1000/secret",
                "decision": "exclude",
                "reason_code": "wrong_population",
                "note": "Legacy note Authorization: Bearer meetingdnatoken123 and sk-proj-meetingdnasecret123456.",
                "actor_type": "human_cli",
                "actor_id": "tester",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[MeetingPackSourceSelector(type="screening_decision", ref="dna_test:pilot_secret_001")],
    )

    assert bundle.screening_contexts[0].notes == ["Legacy note Authorization: <redacted> and <redacted>."]


def test_meeting_pack_source_resolver_requires_explicit_screening_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "vault"
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_001")

    with pytest.raises(ValueError, match="screening_decision ref must be <dna_id>:<run_id>"):
        resolve_meeting_pack_sources(
            vault_path=vault_path,
            source_selectors=[MeetingPackSourceSelector(type="screening_decision", ref="dna_test")],
        )


def test_meeting_pack_source_resolver_loads_topic_matches_from_structured_signals(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault"
    _write_state(vault_path, "paper-alpha")
    _write_state(vault_path, "paper-beta", entities=["medium chain triglycerides"])

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[MeetingPackSourceSelector(type="topic", ref="medium-chain triglycerides")],
    )

    assert bundle.selected_items[0].type == "topic"
    assert [source.structured_state.paper_slug for source in bundle.sources] == ["paper-beta"]


def test_meeting_pack_source_resolver_rejects_topic_without_structured_match(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    _write_state(vault_path, "paper-alpha")

    with pytest.raises(FileNotFoundError, match="No structured paper states resolved from topic"):
        resolve_meeting_pack_sources(
            vault_path=vault_path,
            source_selectors=[MeetingPackSourceSelector(type="topic", ref="no-such-topic")],
        )


@pytest.mark.parametrize("selector_type", ["project_profile", "research_profile"])
def test_meeting_pack_source_resolver_supports_projection_profile_selectors(
    tmp_path: Path,
    selector_type: str,
) -> None:
    vault_path = tmp_path / "vault"
    dna_root = tmp_path / "research_dna"
    profiles_path = tmp_path / "profiles.yaml"
    dna_id = "dna_profile_test"
    run_id = "pilot_profile_test"
    query_version = "v2"
    _write_state(vault_path, "paper-alpha")
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
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))
    try:
        bundle = resolve_meeting_pack_sources(
            vault_path=vault_path,
            research_dna_root=dna_root,
            source_selectors=[MeetingPackSourceSelector(type=selector_type, ref=profile_id)],
        )
    finally:
        monkeypatch.undo()

    assert bundle.selected_items[0].type == selector_type
    assert bundle.selected_items[0].ref == profile_id
    assert [source.structured_state.paper_slug for source in bundle.sources] == ["paper-alpha"]


def test_meeting_pack_source_resolver_rejects_projection_profile_without_mapped_states(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault"
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
            candidate_id="missing-paper",
            decision="include",
            reason_code="other_noise",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root=dna_root,
    )
    profile_id = _write_projection_profile(profiles_path, dna_id=dna_id, query_version=query_version)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))
    try:
        with pytest.raises(
            FileNotFoundError,
            match="No structured paper states matched the included screening decisions",
        ):
            resolve_meeting_pack_sources(
                vault_path=vault_path,
                research_dna_root=dna_root,
                source_selectors=[MeetingPackSourceSelector(type="research_profile", ref=profile_id)],
            )
    finally:
        monkeypatch.undo()


@pytest.mark.parametrize("selector_type", ["project_profile", "research_profile"])
def test_meeting_pack_source_resolver_rejects_manual_profile_selectors(
    tmp_path: Path,
    selector_type: str,
) -> None:
    vault_path = tmp_path / "vault"
    profiles_path = tmp_path / "profiles.yaml"
    _write_state(vault_path, "paper-alpha")
    profile_id = _write_manual_profile(profiles_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PAPERPIPE_PROFILES_PATH", str(profiles_path))
    try:
        with pytest.raises(
            NotImplementedError,
            match="currently support only ResearchDNA projection profiles",
        ):
            resolve_meeting_pack_sources(
                vault_path=vault_path,
                source_selectors=[MeetingPackSourceSelector(type=selector_type, ref=profile_id)],
            )
    finally:
        monkeypatch.undo()


def test_meeting_pack_evidence_ledger_dedupes_same_paper_selector(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    bundle = resolve_meeting_pack_sources(
        vault_path=vault_path,
        source_selectors=[
            MeetingPackSourceSelector(type="paper_slug", ref=slug),
            MeetingPackSourceSelector(type="paper_slug", ref=slug),
        ],
    )
    ledger = build_meeting_pack_evidence_ledger(bundle)

    assert len(bundle.sources) == 1
    assert len(ledger.evidence_refs) == 1
    assert ledger.evidence_refs[0].id == "evref_01"
    assert ledger.evidence_ref_map[(slug, "claim_abc123", "evidence_def456")] == "evref_01"
