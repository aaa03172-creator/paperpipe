from src.schemas import Paper, PaperStatus


def _mk(status):
    return Paper(
        id="x",
        title="t",
        authors=[],
        published="2026-01-01",
        source="test",
        summary="s",
        link="http://example.com",
        processing_status=status,
    )


def test_legacy_status_auto_approved_is_normalized():
    p = _mk("Auto-Approved")
    assert p.processing_status == PaperStatus.APPROVED


def test_legacy_status_pending_review_is_normalized():
    p = _mk("Pending Review")
    assert p.processing_status == PaperStatus.PENDING_REVIEW


def test_canonical_status_is_preserved():
    p = _mk("QUARANTINED")
    assert p.processing_status == PaperStatus.QUARANTINED


def test_escalation_metadata_defaults_and_roundtrip_are_preserved():
    p = Paper(
        id="x",
        title="t",
        authors=[],
        published="2026-01-01",
        source="test",
        summary="s",
        link="http://example.com",
        is_escalated=True,
        escalation_final_route="FAST_LANE_APPROVE",
        escalation_in_biomedical_scope=True,
        escalation_reason_codes=["FASTLANE_GUIDANCE"],
    )

    assert p.is_escalated is True
    assert p.escalation_final_route == "FAST_LANE_APPROVE"
    assert p.escalation_in_biomedical_scope is True
    assert p.escalation_reason_codes == ["FASTLANE_GUIDANCE"]
