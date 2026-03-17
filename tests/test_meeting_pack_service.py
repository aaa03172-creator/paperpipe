from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from src.profiles.profile_schema import Profile, ProfileConfig
from src.profiles.profile_store import save_profiles_snapshot
from src.profiles.research_dna_schema import RunLogEntry, ScreeningLogEntry
from src.profiles.research_dna_store import append_run_log, append_screening_log
from src.meeting_packs.service import (
    generate_meeting_pack,
    get_meeting_pack,
    regenerate_meeting_pack,
    rerender_meeting_pack,
    validate_meeting_pack,
)
from src.meeting_packs.store import (
    list_meeting_pack_ids,
    load_meeting_pack_markdown,
    meeting_pack_markdown_path,
    save_meeting_pack_bundle,
)
from src.schemas.meeting_pack import MeetingPack, MeetingPackGenerateRequest, MeetingPackOnePageSummary, MeetingPackSourceItem
from src.schemas.skills import SkillClaimCard, SkillClaimEvidence, SkillRunRecord, StructuredPaperState
from src.skills.storage import write_structured_state


def _write_state(
    vault_path: Path,
    slug: str,
    *,
    claim_text: str = "Intervention changed the inflammatory pathway.",
    tags: list[str] | None = None,
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
                claim=claim_text,
                evidence=[
                    SkillClaimEvidence(
                        id="evidence_def456",
                        claim_id="claim_abc123",
                        run_id="skill-20260313T000000Z-critical_appraisal",
                        text="Evidence text",
                        locator={
                            "page": 2,
                            "section": "Results",
                            "source": "state.json",
                        },
                    )
                ],
                tags=tags or [],
                outcomes=outcomes or [],
            )
        ],
        outcomes=outcomes or [],
    )
    write_structured_state(state_path, state)


def _write_state_with_claims(
    vault_path: Path,
    slug: str,
    *,
    claims: list[dict[str, object]],
) -> None:
    state_path = vault_path / ".pp" / slug / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = "skill-20260313T000000Z-critical_appraisal"
    claimset: list[SkillClaimCard] = []
    state_outcomes: list[str] = []
    for index, raw_claim in enumerate(claims, start=1):
        claim_id = f"claim_{index:02d}"
        evidence_id = f"evidence_{index:02d}"
        outcomes = [str(item) for item in raw_claim.get("outcomes", [])]
        for outcome in outcomes:
            if outcome not in state_outcomes:
                state_outcomes.append(outcome)
        claimset.append(
            SkillClaimCard(
                id=claim_id,
                run_id=run_id,
                claim=str(raw_claim["claim_text"]),
                evidence=[
                    SkillClaimEvidence(
                        id=evidence_id,
                        claim_id=claim_id,
                        run_id=run_id,
                        text=f"Evidence text {index}",
                        locator={
                            "page": index + 1,
                            "section": "Results",
                            "source": "state.json",
                        },
                    )
                ],
                tags=[str(item) for item in raw_claim.get("tags", [])],
                outcomes=outcomes,
            )
        )
    state = StructuredPaperState(
        paper_slug=slug,
        updated_at="2026-03-13T00:00:00Z",
        runs=[
            SkillRunRecord(
                id=run_id,
                action="critical_appraisal",
                ts="2026-03-13T00:00:00Z",
                status="succeeded",
                summary="Generated multi-claim evidence state.",
            )
        ],
        claimset=claimset,
        outcomes=state_outcomes,
    )
    write_structured_state(state_path, state)


def _write_empty_state(vault_path: Path, slug: str) -> None:
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
                summary="Generated empty claim/evidence state.",
            )
        ],
        claimset=[],
    )
    write_structured_state(state_path, state)


def _write_note(vault_path: Path, relative_path: str, body: str) -> None:
    note_path = vault_path / relative_path
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(body, encoding="utf-8")


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


def _save_legacy_pack(root: Path, *, pack_id: str, selector_type: str, selector_ref: str) -> None:
    pack = MeetingPack(
        id=pack_id,
        mode="journal_club",
        title="Legacy draft",
        created_at=datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc),
        readiness="evidence_backed",
        generation_request=None,
        source_items=[
            MeetingPackSourceItem(
                id="src_01",
                type=selector_type,
                ref=selector_ref,
                title=selector_ref,
                priority=1,
                included=True,
            )
        ],
        one_page_summary=MeetingPackOnePageSummary(overview="Legacy summary"),
        slides=[],
        speaker_notes=[],
        discussion_questions=[],
        expected_questions=[],
        next_steps=[],
        evidence_refs=[],
    )
    save_meeting_pack_bundle(pack, "# Legacy draft\n", root)


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


def _append_projection_screening_include(
    research_dna_root: Path,
    *,
    dna_id: str,
    run_id: str,
    candidate_id: str,
) -> None:
    append_screening_log(
        dna_id,
        ScreeningLogEntry(
            ts="2026-03-13T00:11:00Z",
            dna_id=dna_id,
            run_id=run_id,
            candidate_id=candidate_id,
            decision="include",
            reason_code="other_noise",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root=research_dna_root,
    )


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


def test_generate_meeting_pack_persists_json_and_markdown(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.mode == "journal_club"
    assert response.pack.readiness == "evidence_backed"
    assert response.pack.evidence_refs[0].id == "evref_01"
    assert response.pack.generation_request is not None
    assert response.pack.generation_request.max_slides == 5
    assert [entry.action for entry in response.pack.retrieval_trace] == ["selector_selected", "paper_state_loaded"]
    assert response.pack.retrieval_trace[-1].source_path == f".pp/{slug}/state.json"
    assert response.markdown_sync is not None
    assert response.markdown_sync.status == "in_sync"
    assert 5 <= len(response.pack.slides) <= 8
    assert "## Slide Outline" in (response.markdown or "")
    assert list_meeting_pack_ids(root) == [response.pack.id]
    stored = get_meeting_pack(response.pack.id, root=root)
    assert stored.pack.retrieval_trace == response.pack.retrieval_trace


def test_regenerate_meeting_pack_uses_saved_generation_request_and_creates_new_pack(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    created = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            title="Custom meeting draft",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )

    regenerated = regenerate_meeting_pack(
        created.pack.id,
        vault_path=vault_path,
        root=root,
    )

    assert regenerated.pack.id != created.pack.id
    assert regenerated.pack.title == "Custom meeting draft"
    assert regenerated.pack.regenerated_from_pack_id == created.pack.id
    assert regenerated.pack.generation_request is not None
    assert regenerated.pack.generation_request.model_dump() == created.pack.generation_request.model_dump()
    assert regenerated.markdown_sync is not None
    assert regenerated.markdown_sync.status == "in_sync"
    assert set(list_meeting_pack_ids(root)) == {created.pack.id, regenerated.pack.id}


def test_rerender_meeting_pack_rebuilds_markdown_from_saved_json(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    created = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )

    markdown_path = meeting_pack_markdown_path(created.pack.id, root)
    markdown_path.write_text("# Corrupted\n", encoding="utf-8")

    drifted = get_meeting_pack(created.pack.id, root=root)
    assert drifted.markdown_sync is not None
    assert drifted.markdown_sync.status == "drifted"

    rerendered = rerender_meeting_pack(created.pack.id, root=root)

    assert rerendered.pack.id == created.pack.id
    assert rerendered.pack.readiness == "evidence_backed"
    assert rerendered.markdown_sync is not None
    assert rerendered.markdown_sync.status == "in_sync"
    assert rerendered.markdown == load_meeting_pack_markdown(created.pack.id, root)
    assert rerendered.markdown != "# Corrupted\n"
    assert "## Slide Outline" in (rerendered.markdown or "")


def test_validate_meeting_pack_reports_drift_and_saved_request_strategy(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    created = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )

    markdown_path = meeting_pack_markdown_path(created.pack.id, root)
    markdown_path.write_text("# Corrupted\n", encoding="utf-8")

    validation = validate_meeting_pack(created.pack.id, root=root, vault_path=vault_path)

    assert validation.validation.pack_id == created.pack.id
    assert validation.validation.regenerate_strategy == "saved_request"
    assert validation.validation.can_regenerate is True
    assert validation.validation.markdown_sync.status == "drifted"


def test_regenerate_meeting_pack_supports_bounded_legacy_source_item_fallback(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    legacy_id = "meetingpack_20260313T090000Z_journal_club_legacy001"
    _save_legacy_pack(root, pack_id=legacy_id, selector_type="paper_slug", selector_ref=slug)

    validation = validate_meeting_pack(legacy_id, root=root, vault_path=vault_path)
    assert validation.validation.can_regenerate is True
    assert validation.validation.regenerate_strategy == "legacy_source_items"

    regenerated = regenerate_meeting_pack(legacy_id, vault_path=vault_path, root=root)
    assert regenerated.pack.id != legacy_id
    assert regenerated.pack.regenerated_from_pack_id == legacy_id


def test_validate_meeting_pack_marks_regenerate_unavailable_when_sources_are_missing(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    created = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )

    shutil.rmtree(vault_path)

    validation = validate_meeting_pack(created.pack.id, root=root, vault_path=vault_path)

    assert validation.validation.can_regenerate is False
    assert validation.validation.regenerate_strategy == "unavailable"
    assert any("source validation failed" in warning for warning in validation.validation.warnings)


def test_generate_meeting_pack_marks_empty_pack_as_background_only(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "empty-paper"
    _write_empty_state(vault_path, slug)

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.readiness == "background_only"
    assert response.markdown is not None
    assert "- Readiness: background_only" in response.markdown


def test_generate_meeting_pack_modes_have_visible_contrast(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    journal = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
        ),
        vault_path=vault_path,
        root=root,
    )
    proposal = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="experiment_proposal",
            source_items=[{"type": "paper_slug", "ref": slug}],
        ),
        vault_path=vault_path,
        root=root,
    )

    assert len(journal.pack.slides) >= 5
    assert len(proposal.pack.slides) >= 5
    assert journal.pack.slides[0].slide_title != proposal.pack.slides[0].slide_title
    assert journal.pack.slides[1].slide_title != proposal.pack.slides[1].slide_title
    assert journal.pack.discussion_questions[0].question != proposal.pack.discussion_questions[0].question


def test_generate_meeting_pack_dedupes_duplicate_source_selectors(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[
                {"type": "paper_slug", "ref": slug},
                {"type": "paper_slug", "ref": slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert len(response.pack.source_items) == 1
    assert len(response.pack.one_page_summary.key_points) == 1


def test_generate_meeting_pack_uses_actual_source_item_id_for_first_claim_slide(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "empty-paper"
    second_slug = "claimed-paper"
    _write_empty_state(vault_path, first_slug)
    _write_state(vault_path, second_slug)

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    claim_slide = next(slide for slide in response.pack.slides if slide.optional_figure_candidates)
    assert claim_slide.optional_figure_candidates[0].source_item_id == "src_02"


def test_generate_meeting_pack_treats_note_sources_as_context_only(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_note(
        vault_path,
        "Projects/SCFA.md",
        "# SCFA project\n\nContext note for this topic. See [[wenzelShortchainFattyAcids2020]].\n",
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "project_note", "ref": "Projects/SCFA.md"}],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    source_types = [item.type for item in response.pack.source_items]
    assert "project_note" in source_types
    assert "paper_state" in source_types
    assert len(response.pack.one_page_summary.key_points) == 1
    assert response.pack.one_page_summary.key_points[0].text == "Intervention changed the inflammatory pathway."
    assert "Relevance framing uses note context: SCFA project (context-only)." in response.pack.one_page_summary.overview
    assert (
        "Note frame SCFA project can explain relevance, but paper interpretation should stay source-first."
        in (response.pack.one_page_summary.key_points[0].uncertainty_note or "")
    )
    assert any(
        "context-only inputs" in uncertainty
        for uncertainty in response.pack.one_page_summary.uncertainties
    )
    assert any(
        "context-only inputs" in note
        for note in response.pack.slides[0].caution_notes
    )
    assert any("Relevance frame: SCFA project." == bullet for bullet in response.pack.slides[0].bullets)
    assert any(
        "Note context: SCFA project can frame discussion relevance" in bullet
        for bullet in response.pack.slides[1].bullets
    )
    assert any(
        "framing comes from notes" in item.question
        for item in response.pack.discussion_questions
    )
    assert any(
        "framing is ours versus the paper's" in item.question
        for item in response.pack.expected_questions
    )
    assert any(
        "framing bullets come from notes" in item.action
        for item in response.pack.next_steps
    )


def test_generate_meeting_pack_surfaces_caution_for_multiple_secondary_notes(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_note(
        vault_path,
        "Projects/SCFA.md",
        "# SCFA project\n\nSee [[wenzelShortchainFattyAcids2020]].\n",
    )
    _write_note(
        vault_path,
        "Research/SCFA overview.md",
        "# SCFA overview\n\nSee [[wenzelShortchainFattyAcids2020]].\n",
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[
                {"type": "project_note", "ref": "Projects/SCFA.md"},
                {"type": "research_note", "ref": "Research/SCFA overview.md"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert any(
        "Multiple secondary notes were selected" in uncertainty
        for uncertainty in response.pack.one_page_summary.uncertainties
    )
    assert any(
        "Multiple secondary notes may diverge" in note
        for note in response.pack.slides[0].caution_notes
    )


def test_generate_meeting_pack_surfaces_screening_context_as_context_only(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))

    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_001")

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[
                {"type": "paper_slug", "ref": slug},
                {"type": "screening_decision", "ref": "dna_test:pilot_001"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert any(
        "Screening rationale from pilot_001" in uncertainty
        for uncertainty in response.pack.one_page_summary.uncertainties
    )
    assert (
        "Selection context includes screening run(s): pilot_001 (context-only)."
        in response.pack.one_page_summary.overview
    )
    assert (
        "Screening scope pilot_001 explains selection context only, not claim strength."
        in (response.pack.one_page_summary.key_points[0].uncertainty_note or "")
    )
    assert any(
        "Screening rationale is contextual only" in note
        for note in response.pack.slides[0].caution_notes
    )
    context_bullets = "\n".join(response.pack.slides[1].bullets)
    opening_bullets = "\n".join(response.pack.slides[0].bullets)
    assert "Discussion set includes screening context from: pilot_001." in opening_bullets
    assert "Discussion screening scope: pilot_001" in context_bullets
    assert "top reasons=" in context_bullets
    assert "wrong_population" in context_bullets
    assert "other_noise" in context_bullets
    assert any(
        "screening scope shape which evidence reached this discussion" in item.question
        for item in response.pack.discussion_questions
    )
    assert any(
        "papers make it into today's discussion set" in item.question
        for item in response.pack.expected_questions
    )
    assert any(
        "Re-check screening reason codes before presenting this set as a balanced discussion sample."
        in item.action
        for item in response.pack.next_steps
    )


def test_generate_meeting_pack_uses_note_context_in_project_progress_followups(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_note(
        vault_path,
        "Projects/SCFA.md",
        "# SCFA project\n\nContext note for this topic. See [[wenzelShortchainFattyAcids2020]].\n",
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="project_progress_update",
            source_items=[{"type": "project_note", "ref": "Projects/SCFA.md"}],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert "Project note frame: SCFA project (context-only)." in response.pack.one_page_summary.overview
    assert (
        "Project note frame SCFA project explains why this claim matters operationally"
        in (response.pack.one_page_summary.key_points[0].uncertainty_note or "")
    )
    assert any(
        "Project note frame: SCFA project highlights current blockers/actions." == bullet
        for bullet in response.pack.slides[0].bullets
    )
    assert any(
        "Project note context: SCFA project helps separate blockers/actions" in bullet
        for bullet in response.pack.slides[1].bullets
    )
    assert any(
        "project framing is still note-derived" in item.question
        for item in response.pack.discussion_questions
    )
    assert any(
        "project note or from the underlying evidence state" in item.question
        for item in response.pack.expected_questions
    )
    assert any(
        "Separate project-note framing from evidence-backed progress bullets" in item.action
        for item in response.pack.next_steps
    )


def test_generate_meeting_pack_uses_screening_scope_in_literature_update_followups(
    tmp_path,
    monkeypatch,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))

    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_001")

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": slug},
                {"type": "screening_decision", "ref": "dna_test:pilot_001"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert (
        "Current evidence scope is bounded by screening run(s): pilot_001 (context-only)."
        in response.pack.one_page_summary.overview
    )
    assert (
        "Screening scope pilot_001 defines which papers are in the update set; it is contextual only."
        in (response.pack.one_page_summary.key_points[0].uncertainty_note or "")
    )
    assert any(
        "Current literature scope is bounded by screening run(s): pilot_001." == bullet
        for bullet in response.pack.slides[0].bullets
    )
    assert any(
        "Literature-update screening scope: pilot_001" in bullet
        for bullet in response.pack.slides[1].bullets
    )
    assert any(
        "screening scope shape the apparent trend" in item.question
        for item in response.pack.discussion_questions
    )
    assert any(
        "papers in scope for this update" in item.question
        for item in response.pack.expected_questions
    )
    assert any(
        "Re-check screening reason codes before presenting the current set as a topic trend."
        in item.action
        for item in response.pack.next_steps
    )


def test_generate_meeting_pack_prefers_structured_paper_title_over_context_titles(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))

    slug = "paper-alpha"
    _write_state(vault_path, slug)
    _write_note(
        vault_path,
        "Projects/SCFA.md",
        "# SCFA project\n\nContext note for this topic. See [[paper-alpha]].\n",
    )
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_001")

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "project_note", "ref": "Projects/SCFA.md"},
                {"type": "screening_decision", "ref": "dna_test:pilot_001"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.title.startswith("paper-alpha literature update draft")
    assert "current evidence movement for paper-alpha" in response.pack.one_page_summary.overview
    assert any(
        "Selected source context: paper-alpha" == bullet
        for bullet in response.pack.slides[0].bullets
    )
    assert any(
        "Update context comes from: paper-alpha" == bullet
        for bullet in response.pack.slides[1].bullets
    )
    assert any(
        "Topic framing note: SCFA project." == bullet
        for bullet in response.pack.slides[0].bullets
    )


def test_generate_meeting_pack_uses_note_context_in_experiment_proposal_summary(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_note(
        vault_path,
        "Projects/SCFA.md",
        "# SCFA project\n\nContext note for this topic. See [[wenzelShortchainFattyAcids2020]].\n",
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="experiment_proposal",
            source_items=[{"type": "project_note", "ref": "Projects/SCFA.md"}],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert "Proposal framing uses note context: SCFA project (context-only)." in response.pack.one_page_summary.overview
    assert (
        "Proposal note frame SCFA project can motivate this prior-evidence point"
        in (response.pack.one_page_summary.key_points[0].uncertainty_note or "")
    )
    assert any(
        "Proposal motivation includes context from: SCFA project." == bullet
        for bullet in response.pack.slides[0].bullets
    )
    assert any(
        "Proposal note context: SCFA project helps explain rationale" in bullet
        for bullet in response.pack.slides[1].bullets
    )


def test_generate_meeting_pack_keeps_multi_source_claims_source_specific_without_forcing_conflict(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "paper-alpha"
    second_slug = "paper-beta"
    _write_state(vault_path, first_slug, claim_text="Inflammation marker decreased after intervention.")
    _write_state(vault_path, second_slug, claim_text="Cognitive outcome improved after intervention.")

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts == []
    assert response.pack.one_page_summary.consensus_points == []
    claim_slides = [slide for slide in response.pack.slides if slide.slide_title.startswith("Main evidence")]
    assert len(claim_slides) == 2
    assert all(
        any("source-specific claim slide" in note for note in slide.caution_notes)
        for slide in claim_slides
    )


def test_generate_meeting_pack_surfaces_possible_divergence_for_shared_focus_terms(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "paper-alpha"
    second_slug = "paper-beta"
    _write_state(
        vault_path,
        first_slug,
        claim_text="Intervention reduced inflammatory pathway activity.",
        tags=["inflammatory pathway"],
        outcomes=["inflammation"],
    )
    _write_state(
        vault_path,
        second_slug,
        claim_text="Intervention did not reduce inflammatory pathway activity.",
        tags=["inflammatory pathway"],
        outcomes=["inflammation"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts
    conflict = response.pack.one_page_summary.conflicts[0]
    assert conflict.conflict_type == "possible_divergence"
    assert "inflammatory pathway" in conflict.label
    assert len(conflict.source_item_ids) == 2
    assert len(conflict.evidence_refs) >= 2
    limits_slide = next(
        slide for slide in response.pack.slides if slide.slide_title == "Convergence, divergence, and uncertainty"
    )
    assert any("[Conflict] Selected sources describe inflammatory pathway" in bullet for bullet in limits_slide.bullets)
    assert "[Conflict] Possible divergence: inflammatory pathway" in (response.markdown or "")


def test_generate_meeting_pack_surfaces_possible_divergence_for_paraphrased_focus_terms(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "paper-alpha"
    second_slug = "paper-beta"
    _write_state(
        vault_path,
        first_slug,
        claim_text="Intervention improved cognitive performance.",
        tags=["cognitive performance"],
    )
    _write_state(
        vault_path,
        second_slug,
        claim_text="Intervention showed no change in cognition.",
        tags=["cognition"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert any(
        conflict.conflict_type == "possible_divergence"
        and len(conflict.source_item_ids) == 2
        and "null/no-change wording" in conflict.summary
        for conflict in response.pack.one_page_summary.conflicts
    )


def test_generate_meeting_pack_surfaces_partial_consensus_counts_for_divergent_sources(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state(
        vault_path,
        "paper-alpha",
        claim_text="Intervention reduced inflammatory pathway activity.",
        tags=["inflammatory pathway"],
    )
    _write_state(
        vault_path,
        "paper-beta",
        claim_text="Intervention lowered inflammatory pathway activity.",
        tags=["inflammatory pathway"],
    )
    _write_state(
        vault_path,
        "paper-gamma",
        claim_text="Intervention showed no change in inflammatory pathway activity.",
        tags=["inflammatory pathway"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
                {"type": "paper_slug", "ref": "paper-gamma"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert any(
        conflict.conflict_type == "possible_divergence"
        and "2 sources use positive-outcome wording" in conflict.summary
        and "1 source uses null/no-change wording" in conflict.summary
        and "higher-is-worse framing" in conflict.summary
        for conflict in response.pack.one_page_summary.conflicts
    )
    assert response.pack.one_page_summary.consensus_points
    consensus = response.pack.one_page_summary.consensus_points[0]
    assert consensus.consensus_type == "majority_directional_alignment"
    assert len(consensus.source_item_ids) == 2
    assert consensus.outlier_source_item_ids == ["src_03"]
    assert len(consensus.evidence_refs) == 2
    assert "2 of 3 sources" in consensus.summary
    assert "partial convergence only" in consensus.summary
    assert "[Consensus] Partial directional convergence:" in (response.markdown or "")


def test_generate_meeting_pack_surfaces_directional_consensus_for_paraphrased_focus_terms(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "paper-alpha"
    second_slug = "paper-beta"
    _write_state(
        vault_path,
        first_slug,
        claim_text="Intervention reduced inflammatory pathway activity.",
        tags=["inflammatory pathway"],
    )
    _write_state(
        vault_path,
        second_slug,
        claim_text="Intervention lowered inflammation markers.",
        tags=["inflammation markers"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.consensus_points
    consensus = response.pack.one_page_summary.consensus_points[0]
    assert consensus.consensus_type == "directional_alignment"
    assert len(consensus.source_item_ids) == 2
    assert len(consensus.evidence_refs) >= 2
    limits_slide = next(
        slide for slide in response.pack.slides if slide.slide_title == "Convergence, divergence, and uncertainty"
    )
    assert any("[Consensus] Selected sources describe" in bullet for bullet in limits_slide.bullets)
    assert "[Consensus] Directional convergence:" in (response.markdown or "")


def test_generate_meeting_pack_surfaces_directional_consensus_for_curated_safety_family(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state(
        vault_path,
        "paper-alpha",
        claim_text="Intervention improved safety profile.",
        tags=["safety"],
    )
    _write_state(
        vault_path,
        "paper-beta",
        claim_text="Intervention improved tolerability.",
        tags=["tolerability"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts == []
    assert response.pack.one_page_summary.consensus_points
    consensus = response.pack.one_page_summary.consensus_points[0]
    assert consensus.consensus_type == "directional_alignment"
    assert len(consensus.source_item_ids) == 2
    assert len(consensus.evidence_refs) >= 2


def test_generate_meeting_pack_aligns_tolerability_and_adverse_events_under_focus_relative_framing(
    tmp_path,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state(
        vault_path,
        "paper-alpha",
        claim_text="Intervention improved tolerability.",
        tags=["tolerability"],
    )
    _write_state(
        vault_path,
        "paper-beta",
        claim_text="Intervention reduced adverse events.",
        tags=["adverse events"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts == []
    assert response.pack.one_page_summary.consensus_points
    consensus = response.pack.one_page_summary.consensus_points[0]
    assert consensus.consensus_type == "directional_alignment"
    assert "focus-relative framing" in consensus.summary


def test_generate_meeting_pack_aligns_benefit_and_increase_wording_for_higher_is_better_focus(
    tmp_path,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "paper-alpha"
    second_slug = "paper-beta"
    _write_state(
        vault_path,
        first_slug,
        claim_text="Intervention improved memory performance.",
        tags=["memory"],
    )
    _write_state(
        vault_path,
        second_slug,
        claim_text="Intervention increased cognitive performance.",
        tags=["cognition"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts == []
    assert response.pack.one_page_summary.consensus_points
    consensus = response.pack.one_page_summary.consensus_points[0]
    assert consensus.consensus_type == "directional_alignment"
    assert "higher-is-better framing" in consensus.summary


def test_generate_meeting_pack_surfaces_directional_consensus_for_curated_glycemic_family(
    tmp_path,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state(
        vault_path,
        "paper-alpha",
        claim_text="Intervention reduced blood sugar levels.",
        tags=["blood sugar"],
    )
    _write_state(
        vault_path,
        "paper-beta",
        claim_text="Intervention lowered glycemic levels.",
        tags=["glycemic levels"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts == []
    assert response.pack.one_page_summary.consensus_points
    consensus = response.pack.one_page_summary.consensus_points[0]
    assert consensus.consensus_type == "directional_alignment"
    assert len(consensus.source_item_ids) == 2
    assert "higher-is-worse framing" in consensus.summary


def test_generate_meeting_pack_surfaces_glycemic_family_divergence_for_blood_sugar_terms(
    tmp_path,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state(
        vault_path,
        "paper-alpha",
        claim_text="Intervention showed no change in blood sugar levels.",
        tags=["blood sugar"],
    )
    _write_state(
        vault_path,
        "paper-beta",
        claim_text="Intervention lowered glycemic levels.",
        tags=["glycemic levels"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts
    conflict = response.pack.one_page_summary.conflicts[0]
    assert conflict.conflict_type == "possible_divergence"
    assert "higher-is-worse framing" in conflict.summary


def test_generate_meeting_pack_keeps_benefit_and_increase_wording_as_uncertain_for_ambiguous_focus(
    tmp_path,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "paper-alpha"
    second_slug = "paper-beta"
    _write_state(
        vault_path,
        first_slug,
        claim_text="Intervention improved signaling response.",
        tags=["signaling response"],
    )
    _write_state(
        vault_path,
        second_slug,
        claim_text="Intervention increased signaling response.",
        tags=["signal response"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts == []
    assert response.pack.one_page_summary.consensus_points == []


def test_generate_meeting_pack_surfaces_memory_cognition_divergence_with_valence_framing(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    first_slug = "paper-alpha"
    second_slug = "paper-beta"
    _write_state(
        vault_path,
        first_slug,
        claim_text="Intervention improved memory function.",
        tags=["memory"],
    )
    _write_state(
        vault_path,
        second_slug,
        claim_text="Intervention showed no change in cognition.",
        tags=["cognition"],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": first_slug},
                {"type": "paper_slug", "ref": second_slug},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.conflicts
    conflict = response.pack.one_page_summary.conflicts[0]
    assert conflict.conflict_type == "possible_divergence"
    assert len(conflict.source_item_ids) == 2
    assert "higher-is-better framing" in conflict.summary


def test_generate_meeting_pack_surfaces_cross_focus_pattern_for_distinct_aligned_families(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    for slug in ("paper-alpha", "paper-beta"):
        _write_state_with_claims(
            vault_path,
            slug,
            claims=[
                {
                    "claim_text": "Intervention reduced inflammatory pathway activity.",
                    "tags": ["inflammatory pathway"],
                },
                {
                    "claim_text": "Intervention reduced glucose levels.",
                    "tags": ["glycemic control"],
                },
            ],
        )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.consensus_points[0].consensus_type == "cross_focus_pattern"
    pattern = next(
        consensus
        for consensus in response.pack.one_page_summary.consensus_points
        if consensus.consensus_type == "cross_focus_pattern"
    )
    assert len(pattern.source_item_ids) == 2
    assert len(pattern.evidence_refs) == 4
    assert pattern.label == "Cross-focus pattern: glycemic control and inflammatory pathway"
    assert "higher-is-worse framing" in pattern.summary
    assert "not as proof that these outcomes are interchangeable" in pattern.summary
    limits_slide = next(
        slide for slide in response.pack.slides if slide.slide_title == "Convergence, divergence, and uncertainty"
    )
    assert any(
        "[Consensus] The same 2 sources describe glycemic control and inflammatory pathway" in bullet
        for bullet in limits_slide.bullets
    )
    assert "Cross-focus pattern: glycemic control and inflammatory pathway" in (response.markdown or "")


def test_generate_meeting_pack_does_not_surface_cross_focus_pattern_for_same_evidence_set(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    for slug in ("paper-alpha", "paper-beta"):
        _write_state(
            vault_path,
            slug,
            claim_text="Intervention reduced inflammatory pathway activity.",
            tags=["inflammatory pathway", "glycemic control"],
        )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert all(
        consensus.consensus_type != "cross_focus_pattern"
        for consensus in response.pack.one_page_summary.consensus_points
    )


def test_generate_meeting_pack_keeps_cross_focus_pattern_visible_when_three_families_align(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    for slug in ("paper-alpha", "paper-beta"):
        _write_state_with_claims(
            vault_path,
            slug,
            claims=[
                {
                    "claim_text": "Intervention reduced inflammatory pathway activity.",
                    "tags": ["inflammatory pathway"],
                },
                {
                    "claim_text": "Intervention reduced glucose levels.",
                    "tags": ["glycemic control"],
                },
                {
                    "claim_text": "Intervention reduced pain burden.",
                    "tags": ["pain burden"],
                },
            ],
        )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert len(response.pack.one_page_summary.consensus_points) == 3
    assert response.pack.one_page_summary.consensus_points[0].consensus_type == "cross_focus_pattern"
    limits_slide = next(
        slide for slide in response.pack.slides if slide.slide_title == "Convergence, divergence, and uncertainty"
    )
    assert any(
        "[Consensus] The same 2 sources describe glycemic control, inflammatory pathway, and pain burden"
        in bullet
        for bullet in limits_slide.bullets
    )


def test_generate_meeting_pack_surfaces_partial_cross_focus_pattern_for_shared_majority_sources(
    tmp_path,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state_with_claims(
        vault_path,
        "paper-alpha",
        claims=[
            {
                "claim_text": "Intervention reduced inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention reduced glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )
    _write_state_with_claims(
        vault_path,
        "paper-beta",
        claims=[
            {
                "claim_text": "Intervention lowered inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention lowered glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )
    _write_state_with_claims(
        vault_path,
        "paper-gamma",
        claims=[
            {
                "claim_text": "Intervention showed no change in inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention showed no change in glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
                {"type": "paper_slug", "ref": "paper-gamma"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert response.pack.one_page_summary.consensus_points[0].consensus_type == "cross_focus_majority_pattern"
    pattern = response.pack.one_page_summary.consensus_points[0]
    assert pattern.label == "Partial cross-focus convergence: glycemic control and inflammatory pathway"
    assert len(pattern.source_item_ids) == 2
    assert pattern.outlier_source_item_ids == ["src_03"]
    assert len(pattern.evidence_refs) == 4
    assert "The same 2 of 3 sources describe glycemic control and inflammatory pathway" in pattern.summary
    assert "remaining 1 source diverges across at least one family" in pattern.summary
    limits_slide = next(
        slide for slide in response.pack.slides if slide.slide_title == "Convergence, divergence, and uncertainty"
    )
    assert any(
        "[Consensus] The same 2 of 3 sources describe glycemic control and inflammatory pathway"
        in bullet
        for bullet in limits_slide.bullets
    )
    assert "[Consensus] Partial cross-focus convergence: glycemic control and inflammatory pathway" in (
        response.markdown or ""
    )


def test_generate_meeting_pack_rejects_partial_cross_focus_pattern_when_majority_subset_differs(
    tmp_path,
):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state_with_claims(
        vault_path,
        "paper-alpha",
        claims=[
            {
                "claim_text": "Intervention reduced inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention reduced glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )
    _write_state_with_claims(
        vault_path,
        "paper-beta",
        claims=[
            {
                "claim_text": "Intervention lowered inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention showed no change in glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )
    _write_state_with_claims(
        vault_path,
        "paper-gamma",
        claims=[
            {
                "claim_text": "Intervention showed no change in inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention lowered glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
                {"type": "paper_slug", "ref": "paper-gamma"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert all(
        consensus.consensus_type != "cross_focus_majority_pattern"
        for consensus in response.pack.one_page_summary.consensus_points
    )


def test_generate_meeting_pack_canonicalizes_cross_focus_label_and_evidence_order(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    _write_state_with_claims(
        vault_path,
        "paper-alpha",
        claims=[
            {
                "claim_text": "Intervention reduced inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention reduced glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )
    _write_state_with_claims(
        vault_path,
        "paper-beta",
        claims=[
            {
                "claim_text": "Intervention lowered inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention lowered glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )
    forward = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    alt_vault_path = tmp_path / "vault_reversed"
    alt_root = tmp_path / "meeting_packs_reversed"
    _write_state_with_claims(
        alt_vault_path,
        "paper-alpha",
        claims=[
            {
                "claim_text": "Intervention reduced inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
            {
                "claim_text": "Intervention reduced glucose levels.",
                "tags": ["glycemic control"],
            },
        ],
    )
    _write_state_with_claims(
        alt_vault_path,
        "paper-beta",
        claims=[
            {
                "claim_text": "Intervention lowered glucose levels.",
                "tags": ["glycemic control"],
            },
            {
                "claim_text": "Intervention lowered inflammatory pathway activity.",
                "tags": ["inflammatory pathway"],
            },
        ],
    )
    reversed_claim_order = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[
                {"type": "paper_slug", "ref": "paper-alpha"},
                {"type": "paper_slug", "ref": "paper-beta"},
            ],
            max_slides=6,
        ),
        vault_path=alt_vault_path,
        root=alt_root,
    )

    forward_pattern = next(
        consensus
        for consensus in forward.pack.one_page_summary.consensus_points
        if consensus.consensus_type == "cross_focus_pattern"
    )
    reversed_pattern = next(
        consensus
        for consensus in reversed_claim_order.pack.one_page_summary.consensus_points
        if consensus.consensus_type == "cross_focus_pattern"
    )

    assert forward_pattern.label == reversed_pattern.label
    assert forward_pattern.source_item_ids == reversed_pattern.source_item_ids
    assert forward_pattern.outlier_source_item_ids == reversed_pattern.outlier_source_item_ids
    assert forward_pattern.evidence_refs == reversed_pattern.evidence_refs


def test_generate_meeting_pack_supports_profile_selector_via_service_override(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    profiles_path = tmp_path / "profiles.yaml"
    dna_root = tmp_path / "research_dna"
    slug = "paper-alpha"
    dna_id = "dna_profile_test"
    run_id = "pilot_profile_test"
    query_version = "v2"
    _write_state(
        vault_path,
        slug,
        claim_text="Intervention reduced inflammatory pathway activity.",
        tags=["inflammatory pathway"],
        outcomes=["metabolic signal"],
    )
    profile_id = _write_projection_profile(profiles_path, dna_id=dna_id, query_version=query_version)
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))
    _write_profile_run_log(
        dna_root,
        dna_id=dna_id,
        run_id=run_id,
        query_version=query_version,
        include_count=1,
        labeled_count=1,
    )
    _append_projection_screening_include(
        dna_root,
        dna_id=dna_id,
        run_id=run_id,
        candidate_id=slug,
    )

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="literature_update",
            source_items=[{"type": "project_profile", "ref": profile_id}],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
        profiles_path=profiles_path,
    )

    source_types = [item.type for item in response.pack.source_items]
    assert "project_profile" in source_types
    assert "paper_state" in source_types


def test_generate_meeting_pack_surfaces_conflict_for_multiple_screening_runs(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    dna_root = tmp_path / "research_dna"
    monkeypatch.setenv("PAPERPIPE_RESEARCH_DNA_DIR", str(dna_root))

    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_001")
    _write_screening_log(dna_root, dna_id="dna_test", run_id="pilot_002")

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[
                {"type": "paper_slug", "ref": slug},
                {"type": "screening_decision", "ref": "dna_test:pilot_001"},
                {"type": "screening_decision", "ref": "dna_test:pilot_002"},
            ],
            max_slides=6,
        ),
        vault_path=vault_path,
        root=root,
    )

    assert any(
        conflict.conflict_type == "selection_scope"
        and "Multiple screening runs were selected" in conflict.summary
        for conflict in response.pack.one_page_summary.conflicts
    )
    assert any(
        conflict.conflict_type == "selection_scope"
        and "Screening context without mapped structured papers" in conflict.summary
        for conflict in response.pack.one_page_summary.conflicts
    )
    assert any(
        "[Conflict] Multiple screening runs were selected" in note
        for note in response.pack.slides[0].caution_notes
    )
