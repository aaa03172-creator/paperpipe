from datetime import datetime, timezone

from src.meeting_packs.handoff_artifacts import (
    build_meeting_pack_acceptance_contract,
    build_meeting_pack_quality_gate,
)
from src.schemas.meeting_pack import (
    MeetingPack,
    MeetingPackGenerateRequest,
    MeetingPackOnePageSummary,
    MeetingPackSourceItem,
    MeetingPackSourceSelector,
)


def _sample_pack(*, readiness: str = "evidence_backed", include_trace: bool = True) -> MeetingPack:
    return MeetingPack(
        id="meetingpack_20260327T120000000000Z_journal_club_a1b2c3d4",
        mode="journal_club",
        title="Meeting draft",
        created_at=datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc),
        readiness=readiness,
        generation_request=MeetingPackGenerateRequest(
            mode="journal_club",
            title="Meeting draft",
            source_items=[MeetingPackSourceSelector(type="paper_slug", ref="paper-alpha")],
            max_slides=6,
        ),
        source_items=[
            MeetingPackSourceItem(
                id="src_01",
                type="paper_slug",
                ref="paper-alpha",
                title="paper-alpha",
                priority=1,
                included=True,
            )
        ],
        retrieval_trace=[
            {
                "order": 1,
                "selector_type": "paper_slug",
                "selector_ref": "paper-alpha",
                "action": "selector_selected",
                "outcome": "selected",
                "detail": "Selected paper slug paper-alpha.",
            }
        ]
        if include_trace
        else [],
        one_page_summary=MeetingPackOnePageSummary(overview="Summary"),
    )


def test_meeting_pack_handoff_contract_records_generation_shape():
    pack = _sample_pack()

    contract = build_meeting_pack_acceptance_contract(
        pack=pack,
        regenerate_strategy="saved_request",
    )

    assert contract.workflow == "meeting_pack"
    assert contract.pack_id == pack.id
    assert contract.requested_scope["mode"] == "journal_club"
    assert contract.expected_outputs == ["meeting_pack.json", "meeting_pack.md"]
    assert contract.operator_contract["regenerate_strategy_snapshot"] == "saved_request"


def test_meeting_pack_quality_gate_marks_evidence_backed_pack_as_discussion_ready():
    pack = _sample_pack(readiness="evidence_backed", include_trace=True)

    gate = build_meeting_pack_quality_gate(
        pack=pack,
        regenerate_strategy="saved_request",
        markdown_sync_status="in_sync",
    )

    assert gate.overall_status == "pass"
    assert gate.bundle_ready is True
    assert gate.discussion_ready is True
    assert gate.reason_codes == []


def test_meeting_pack_quality_gate_warns_for_background_only_pack():
    pack = _sample_pack(readiness="background_only", include_trace=False)

    gate = build_meeting_pack_quality_gate(
        pack=pack,
        regenerate_strategy="saved_request",
        markdown_sync_status="in_sync",
    )

    assert gate.overall_status == "warn"
    assert gate.bundle_ready is True
    assert gate.discussion_ready is False
    assert "BACKGROUND_ONLY" in gate.reason_codes
    assert "TRACE_MISSING" in gate.reason_codes
