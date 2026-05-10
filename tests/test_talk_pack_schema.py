from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.talk_pack import (
    TalkPack,
    TalkPackGenerateRequest,
    TalkPackListItem,
    TalkPackListResponse,
    TalkPackOutputMember,
    TalkPackResponse,
    TalkPackReviewArtifact,
    TalkPackSlideManifestSlide,
    TalkPackSupportingArtifactRef,
    TalkPackUpstreamOwnerRef,
)


def _sample_request() -> TalkPackGenerateRequest:
    return TalkPackGenerateRequest(
        paper_slug="wenzelShortchainFattyAcids2020",
        title=" SCFA journal club talk ",
        talk_mode="journal_club",
        audience_profile=" mixed_research_group ",
        duration_minutes=12,
        context=" Weekly lab journal club ",
        selected_exports=["deck_pptx", "speaker_script", "deck_pptx"],
        optional_extensions=["clinical_implications", "clinical_implications"],
        style_profile="paperpipe_editorial",
        template_attachment_refs=[
            "attachment://smith-lab-journal-club-template.pptx",
            "attachment://smith-lab-journal-club-template.pptx",
        ],
        supporting_artifact_refs=[
            TalkPackSupportingArtifactRef(
                artifact_family="paper_synthesis",
                ref="synth_20260420_wenzel",
                role="preferred_summary",
            ),
            TalkPackSupportingArtifactRef(
                artifact_family="paper_synthesis",
                ref="synth_20260420_wenzel",
                role="preferred_summary",
            ),
        ],
        max_slides=10,
        auto_include_dependencies=True,
    )


def _sample_pack() -> TalkPack:
    request = _sample_request()
    return TalkPack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        paper_slug="wenzelShortchainFattyAcids2020",
        title="SCFA journal club talk",
        created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        style_profile="paperpipe_editorial",
        template_attachment_refs=["attachment://smith-lab-journal-club-template.pptx"],
        generation_request=request,
        upstream_owners=[
            TalkPackUpstreamOwnerRef(
                owner_kind="paper_state",
                ref="vault/.pp/wenzelShortchainFattyAcids2020/state.json",
                role="canonical",
            ),
            TalkPackUpstreamOwnerRef(
                owner_kind="derived_manifest",
                ref="synth_20260420_wenzel",
                role="derived",
            ),
        ],
        selected_outputs=["deck_pptx", "speaker_script"],
        required_outputs=["slide_manifest", "key_numbers", "deck_pptx", "speaker_script"],
        output_members=[
            TalkPackOutputMember(kind="slide_manifest", path="slide_manifest.json", required=True),
            TalkPackOutputMember(kind="key_numbers", path="key_numbers.md", required=True),
            TalkPackOutputMember(kind="deck_pptx", path="exports/deck.pptx", required=True),
            TalkPackOutputMember(kind="speaker_script", path="exports/speaker_script.md", required=True),
        ],
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json"),
            TalkPackReviewArtifact(kind="style_lint", path="review/style_lint.json"),
        ],
        warnings=["Presentation should stay within 12 minutes."],
        uncertainty_notes=["Clinical implications remain tentative."],
    )


def test_talk_pack_generate_request_normalizes_and_dedupes() -> None:
    request = _sample_request()

    assert request.title == "SCFA journal club talk"
    assert request.audience_profile == "mixed_research_group"
    assert request.context == "Weekly lab journal club"
    assert request.selected_exports == ["deck_pptx", "speaker_script"]
    assert request.optional_extensions == ["clinical_implications"]
    assert request.style_profile == "paperpipe_editorial"
    assert request.template_attachment_refs == ["attachment://smith-lab-journal-club-template.pptx"]
    assert len(request.supporting_artifact_refs) == 1


def test_talk_pack_schema_accepts_valid_example() -> None:
    pack = _sample_pack()

    assert pack.artifact_family == "talk_pack"
    assert pack.layer == "user_facing_artifact"
    assert pack.canonical_status == "non_canonical"
    assert pack.required_outputs == ["slide_manifest", "key_numbers", "deck_pptx", "speaker_script"]
    assert pack.output_members[0].path == "slide_manifest.json"
    assert pack.review_artifacts[0].kind == "presentation_review"


def test_talk_pack_requires_owner_to_match_saved_generation_request() -> None:
    payload = _sample_pack().model_dump(mode="python")
    payload["style_profile"] = "paperpipe_baseline"

    with pytest.raises(ValidationError):
        TalkPack(**payload)


def test_talk_pack_requires_selected_outputs_to_be_in_required_outputs() -> None:
    with pytest.raises(ValidationError):
        TalkPack(
            talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
            paper_slug="wenzelShortchainFattyAcids2020",
            title="SCFA journal club talk",
            created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
            talk_mode="journal_club",
            audience_profile="mixed_research_group",
            duration_minutes=12,
            generation_request=_sample_request(),
            upstream_owners=[
                TalkPackUpstreamOwnerRef(owner_kind="paper_state", ref="vault/.pp/example/state.json")
            ],
            selected_outputs=["deck_pptx"],
            required_outputs=["slide_manifest", "key_numbers"],
        )


def test_talk_pack_requires_explicit_output_members_for_required_outputs() -> None:
    payload = _sample_pack().model_dump(mode="python")
    payload["output_members"] = [
        member
        for member in payload["output_members"]
        if member["kind"] != "key_numbers"
    ]

    with pytest.raises(ValidationError):
        TalkPack(**payload)


def test_talk_pack_rejects_duplicate_output_member_kinds() -> None:
    with pytest.raises(ValidationError):
        TalkPack(
            talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
            paper_slug="wenzelShortchainFattyAcids2020",
            title="SCFA journal club talk",
            created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
            talk_mode="journal_club",
            audience_profile="mixed_research_group",
            duration_minutes=12,
            generation_request=_sample_request(),
            upstream_owners=[
                TalkPackUpstreamOwnerRef(owner_kind="paper_state", ref="vault/.pp/example/state.json")
            ],
            selected_outputs=["deck_pptx"],
            required_outputs=["deck_pptx"],
            output_members=[
                TalkPackOutputMember(kind="deck_pptx", path="exports/deck-a.pptx"),
                TalkPackOutputMember(kind="deck_pptx", path="exports/deck-b.pptx"),
            ],
        )


def test_talk_pack_rejects_duplicate_review_artifact_kinds() -> None:
    with pytest.raises(ValidationError):
        TalkPack(
            talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
            paper_slug="wenzelShortchainFattyAcids2020",
            title="SCFA journal club talk",
            created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
            talk_mode="journal_club",
            audience_profile="mixed_research_group",
            duration_minutes=12,
            generation_request=_sample_request(),
            upstream_owners=[
                TalkPackUpstreamOwnerRef(owner_kind="paper_state", ref="vault/.pp/example/state.json")
            ],
            selected_outputs=["deck_pptx"],
            required_outputs=["deck_pptx"],
            review_artifacts=[
                TalkPackReviewArtifact(kind="presentation_review", path="review/a.json"),
                TalkPackReviewArtifact(kind="presentation_review", path="review/b.json"),
            ],
        )


def test_talk_pack_rejects_invalid_member_artifact_paths() -> None:
    with pytest.raises(ValidationError, match="TalkPackOutputMember.path"):
        TalkPackOutputMember(kind="deck_pptx", path="../exports/deck.pptx")

    with pytest.raises(ValidationError, match="TalkPackReviewArtifact.path"):
        TalkPackReviewArtifact(kind="presentation_review", path="/review/presentation_review.json")


def test_talk_pack_response_and_list_shapes_accept_valid_payloads() -> None:
    pack = _sample_pack()
    response = TalkPackResponse(pack=pack)
    item = TalkPackListItem(
        talk_pack_id=pack.talk_pack_id,
        paper_slug=pack.paper_slug,
        title=pack.title,
        updated_at=pack.updated_at,
        talk_mode=pack.talk_mode,
        selected_output_count=len(pack.selected_outputs),
        generated_output_count=len(pack.output_members),
        warning_count=len(pack.warnings),
        has_generation_request=True,
    )
    listing = TalkPackListResponse(items=[item], total=1)

    assert response.pack.talk_pack_id == pack.talk_pack_id
    assert listing.total == 1
    assert listing.items[0].artifact_family == "talk_pack"


def test_talk_pack_slide_manifest_visual_labels_preserve_duplicate_positions() -> None:
    slide = TalkPackSlideManifestSlide(
        slide_id="slide_01",
        order=1,
        title="Comparison",
        primary_message="Keep both captions audience-facing and identical.",
        visual_refs=[
            "chart_pack_render:chartpack_20260421_scfa_visual:chart_1",
            "chart_pack_render:chartpack_20260421_scfa_visual:chart_2",
        ],
        visual_labels=["Shared caption", "Shared caption"],
    )

    assert slide.visual_labels == ["Shared caption", "Shared caption"]


def test_talk_pack_slide_manifest_preserves_chat_evidence_refs() -> None:
    slide = TalkPackSlideManifestSlide(
        slide_id="slide_01",
        order=1,
        title="Evidence-linked opening",
        primary_message="Keep slide-level evidence refs structured and reloadable.",
        evidence_refs=[
            {
                "paper_slug": "wenzelShortchainFattyAcids2020",
                "claim_id": "claim_4d5f89ab12cd",
                "evidence_id": "ev_scfa_results_01",
                "run_id": "run_20260421",
                "locator": {"section": "Results", "page": 4},
            }
        ],
    )

    dumped = slide.model_dump(mode="json", exclude_none=True)

    assert slide.evidence_refs[0].paper_slug == "wenzelShortchainFattyAcids2020"
    assert slide.evidence_refs[0].locator is not None
    assert slide.evidence_refs[0].locator.section == "Results"
    assert dumped["evidence_refs"][0]["evidence_id"] == "ev_scfa_results_01"
