from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.schemas.chat import ChatLocator
from src.schemas.meeting_pack import (
    MeetingPack,
    MeetingPackConsensus,
    MeetingPackConflict,
    MeetingPackEvidenceRef,
    MeetingPackExpectedQuestion,
    MeetingPackGenerateRequest,
    MeetingPackKeyPoint,
    MeetingPackListResponse,
    MeetingPackNextStep,
    MeetingPackOnePageSummary,
    MeetingPackQuestion,
    MeetingPackRetrievalTraceEntry,
    MeetingPackSlide,
    MeetingPackSourceItem,
    MeetingPackSourceSelector,
    MeetingPackSpeakerNote,
    MeetingPackResponse,
    MeetingPackTraceResponse,
    MeetingPackValidationResponse,
)


def _sample_pack() -> MeetingPack:
    return MeetingPack(
        id="meetingpack_20260313T090000Z_journal_club_a1b2c3d4",
        mode="journal_club",
        title="SCFA paper journal club draft",
        created_at=datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc),
        generation_request=MeetingPackGenerateRequest(
            mode="journal_club",
            title="SCFA paper journal club draft",
            source_items=[
                MeetingPackSourceSelector(type="paper_slug", ref="wenzelShortchainFattyAcids2020"),
            ],
            max_slides=6,
        ),
        source_items=[
            MeetingPackSourceItem(
                id="src_01",
                type="paper_slug",
                ref="wenzelShortchainFattyAcids2020",
                title="wenzelShortchainFattyAcids2020",
                priority=1,
                included=True,
            )
        ],
        retrieval_trace=[
            MeetingPackRetrievalTraceEntry(
                order=1,
                selector_type="paper_slug",
                selector_ref="wenzelShortchainFattyAcids2020",
                action="selector_selected",
                outcome="selected",
                detail="Direct structured paper selector accepted.",
                source_item_id="src_01",
                matched_paper_slugs=["wenzelShortchainFattyAcids2020"],
            )
        ],
        one_page_summary=MeetingPackOnePageSummary(
            overview="Draft overview text.",
            key_points=[
                MeetingPackKeyPoint(
                    label="Main finding",
                    text="The paper reports reduced inflammatory signaling.",
                    evidence_refs=["evref_01"],
                )
            ],
            consensus_points=[
                MeetingPackConsensus(
                    label="Directional convergence: inflammation",
                    summary="Selected sources describe inflammation with aligned decrease-like wording across 2 source(s).",
                    consensus_type="directional_alignment",
                    source_item_ids=["src_01", "src_02"],
                    evidence_refs=["evref_01"],
                )
            ],
            conflicts=[
                MeetingPackConflict(
                    label="Possible divergence: inflammation",
                    summary="Selected sources describe inflammation with benefit-like wording and null/no-change wording.",
                    conflict_type="possible_divergence",
                    source_item_ids=["src_01"],
                    evidence_refs=["evref_01"],
                )
            ],
            uncertainties=["Outcome magnitude is not consistently extractable."],
        ),
        slides=[
            MeetingPackSlide(
                slide_title="Why this paper matters",
                purpose="Frame the question and relevance",
                bullets=[
                    "Study asks whether the intervention changes the inflammatory pathway.",
                    "Evidence is strongest for directionality, not magnitude.",
                ],
                evidence_refs=["evref_01"],
                caution_notes=["Do not quote an effect size unless re-verified."],
            )
        ],
        speaker_notes=[
            MeetingPackSpeakerNote(
                slide_index=1,
                text="Open with the biological question before describing the assay.",
                evidence_refs=["evref_01"],
            )
        ],
        discussion_questions=[
            MeetingPackQuestion(
                question="How convincing is the causal interpretation?",
                rationale="Mechanistic depth is limited.",
                evidence_refs=["evref_01"],
            )
        ],
        expected_questions=[
            MeetingPackExpectedQuestion(
                question="What is the strongest limitation of this paper?",
                suggested_response="Measurement limitations are the safest leading limitation.",
                evidence_refs=["evref_01"],
            )
        ],
        next_steps=[
            MeetingPackNextStep(
                action="Re-check methods before presenting.",
                why="Assay limitations are likely to come up in discussion.",
                priority="high",
                evidence_refs=["evref_01"],
            )
        ],
        evidence_refs=[
            MeetingPackEvidenceRef(
                id="evref_01",
                paper_slug="wenzelShortchainFattyAcids2020",
                claim_id="claim_4d5f89ab12cd",
                evidence_id="evidence_81b6d88e2f43",
                run_id="skill-20260309T000000Z-critical_appraisal",
                locator=ChatLocator(page=1, section="Abstract"),
                support_type="direct",
                note="Supports the primary direction-of-effect statement.",
            )
        ],
    )


def test_meeting_pack_schema_accepts_valid_example():
    pack = _sample_pack()
    assert pack.mode == "journal_club"
    assert pack.output_mode_family == "lab_meeting"
    assert pack.readiness == "evidence_backed"
    assert pack.slides[0].evidence_refs == ["evref_01"]
    assert pack.evidence_refs[0].locator.section == "Abstract"
    assert pack.generation_request is not None
    assert pack.generation_request.max_slides == 6
    assert pack.retrieval_trace[0].action == "selector_selected"
    assert pack.one_page_summary.consensus_points[0].consensus_type == "directional_alignment"
    assert pack.one_page_summary.conflicts[0].conflict_type == "possible_divergence"


def test_meeting_pack_response_schema_accepts_markdown_sync():
    response = MeetingPackResponse(
        pack=_sample_pack(),
        markdown="# Draft\n",
        markdown_sync={
            "status": "drifted",
            "stored_markdown_sha1": "a" * 40,
            "rendered_markdown_sha1": "b" * 40,
            "note": "Stored markdown differs from the deterministic render of meeting_pack.json.",
        },
    )

    assert response.markdown_sync is not None
    assert response.markdown_sync.status == "drifted"
    assert response.pack.output_mode_family == "lab_meeting"


def test_meeting_pack_validation_response_schema_accepts_legacy_strategy():
    response = MeetingPackValidationResponse(
        validation={
            "pack_id": "meetingpack_20260313T090000Z_journal_club_a1b2c3d4",
            "readiness": "background_only",
            "markdown_sync": {
                "status": "in_sync",
                "stored_markdown_sha1": "a" * 40,
                "rendered_markdown_sha1": "a" * 40,
            },
            "can_regenerate": True,
            "regenerate_strategy": "legacy_source_items",
            "warnings": ["Legacy pack regenerate fell back to source_items."],
        }
    )

    assert response.validation.regenerate_strategy == "legacy_source_items"


def test_meeting_pack_trace_response_schema_accepts_summary_and_trace():
    response = MeetingPackTraceResponse(
        pack_id="meetingpack_20260313T090000Z_journal_club_a1b2c3d4",
        available=True,
        summary={
            "entry_count": 2,
            "selector_count": 1,
            "matched_paper_count": 1,
            "source_path_count": 1,
            "action_counts": {
                "selector_selected": 1,
                "paper_state_loaded": 1,
            },
            "outcome_counts": {
                "selected": 1,
                "loaded": 1,
            },
            "matched_paper_slugs": ["wenzelShortchainFattyAcids2020"],
            "source_paths": [".pp/wenzelShortchainFattyAcids2020/state.json"],
        },
        trace=_sample_pack().retrieval_trace,
    )

    assert response.available is True
    assert response.summary.entry_count == 2
    assert response.summary.action_counts["selector_selected"] == 1


def test_meeting_pack_list_response_schema_accepts_summary_items():
    response = MeetingPackListResponse(
        generated_at=datetime(2026, 3, 17, 9, 5, tzinfo=timezone.utc),
        total=1,
        items=[
            {
                "pack_id": "meetingpack_20260313T090000Z_journal_club_a1b2c3d4",
                "title": "SCFA paper journal club draft",
                "mode": "journal_club",
                "created_at": "2026-03-13T09:00:00Z",
                "readiness": "evidence_backed",
                "source_count": 2,
                "slide_count": 6,
                "trace_entry_count": 5,
                "primary_source_title": "wenzelShortchainFattyAcids2020",
                "has_generation_request": True,
            }
        ],
    )

    assert response.total == 1
    assert response.items[0].pack_id.endswith("a1b2c3d4")
    assert response.items[0].trace_entry_count == 5


def test_meeting_pack_generate_request_accepts_typed_source_selectors():
    request = MeetingPackGenerateRequest(
        mode="experiment_proposal",
        source_items=[
            MeetingPackSourceSelector(type="paper_slug", ref="wenzelShortchainFattyAcids2020"),
            MeetingPackSourceSelector(type="project_note", ref="Projects/SCFA.md"),
        ],
        max_slides=6,
    )

    assert request.mode == "experiment_proposal"
    assert request.max_slides == 6
    assert request.source_items[1].type == "project_note"


def test_meeting_pack_schema_accepts_majority_directional_alignment_consensus():
    consensus = MeetingPackConsensus(
        label="Partial directional convergence: inflammation",
        summary="2 of 3 sources describe inflammation with aligned positive-outcome wording.",
        consensus_type="majority_directional_alignment",
        source_item_ids=["src_01", "src_02"],
        outlier_source_item_ids=["src_03"],
        evidence_refs=["evref_01", "evref_02"],
    )

    assert consensus.consensus_type == "majority_directional_alignment"
    assert consensus.outlier_source_item_ids == ["src_03"]


def test_meeting_pack_schema_accepts_cross_focus_pattern_consensus():
    consensus = MeetingPackConsensus(
        label="Cross-focus pattern: inflammatory pathway and adverse events",
        summary="The same 2 sources describe inflammatory pathway and adverse events with aligned positive-outcome wording under a higher-is-worse framing.",
        consensus_type="cross_focus_pattern",
        source_item_ids=["src_01", "src_02"],
        evidence_refs=["evref_01", "evref_02", "evref_03", "evref_04"],
    )

    assert consensus.consensus_type == "cross_focus_pattern"


def test_meeting_pack_schema_accepts_cross_focus_majority_pattern_consensus():
    consensus = MeetingPackConsensus(
        label="Partial cross-focus convergence: inflammatory pathway and glycemic control",
        summary="The same 2 of 3 sources describe inflammatory pathway and glycemic control with aligned positive-outcome wording under a higher-is-worse framing across these families.",
        consensus_type="cross_focus_majority_pattern",
        source_item_ids=["src_01", "src_02"],
        outlier_source_item_ids=["src_03"],
        evidence_refs=["evref_01", "evref_02", "evref_03", "evref_04"],
    )

    assert consensus.consensus_type == "cross_focus_majority_pattern"
    assert consensus.outlier_source_item_ids == ["src_03"]


def test_meeting_pack_schema_rejects_invalid_mode():
    with pytest.raises(ValueError):
        MeetingPackGenerateRequest(mode="unsupported_mode", source_items=[])


def test_meeting_pack_generate_request_requires_at_least_one_source():
    with pytest.raises(ValueError):
        MeetingPackGenerateRequest(mode="journal_club", source_items=[])
