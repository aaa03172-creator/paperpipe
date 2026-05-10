from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.protocol_card import (
    ProtocolCard,
    ProtocolVersion,
    build_protocol_version_summary,
    summarize_protocol_card,
)


def _sample_protocol_version(
    *,
    version_id: str = "protver_alpha_v1",
    version_number: int = 1,
    status: str = "active",
) -> ProtocolVersion:
    return ProtocolVersion(
        version_id=version_id,
        protocol_id="protocol_alpha",
        version_number=version_number,
        key_steps_summary=[" Seed cells ", " Add treatment "],
        materials=["DMEM", "DMEM", "FBS"],
        equipment=["incubator"],
        critical_conditions=[" 37 C ", "5% CO2"],
        readouts=["Cell viability"],
        cautions=["Do not overconfluence"],
        content_snapshot=" Step 1: seed cells\nStep 2: add treatment ",
        change_reason=" Initial draft ",
        status=status,
        created_by=" operator ",
        created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
        source_refs=[
            {
                "paper_slug": "paper-alpha",
                "claim_id": "claim-001",
                "run_id": "run-001",
                "locator": {"page": 4, "table_id": "tbl-1"},
            }
        ],
        note=" Use as baseline ",
    )


def test_protocol_version_summary_tracks_source_ref_count() -> None:
    version = _sample_protocol_version()
    summary = build_protocol_version_summary(version)

    assert version.key_steps_summary == ["Seed cells", "Add treatment"]
    assert version.materials == ["DMEM", "FBS"]
    assert version.created_by == "operator"
    assert version.content_snapshot == "Step 1: seed cells\nStep 2: add treatment"
    assert summary.version_id == "protver_alpha_v1"
    assert summary.source_ref_count == 1
    assert summary.change_reason == "Initial draft"


def test_protocol_card_summary_preserves_bounded_identity_state() -> None:
    version = _sample_protocol_version()
    card = ProtocolCard(
        protocol_id="protocol_alpha",
        title=" Alpha assay protocol ",
        purpose=" Evaluate treatment response ",
        context=" In vitro assay ",
        source_kind="paper_derived",
        linked_paper_ids=["paper-001", "paper-001", "paper-002"],
        linked_note_slugs=[" alpha-note ", "beta-note"],
        current_version_id=version.version_id,
        validation_status="reviewed",
        created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        version_summaries=[build_protocol_version_summary(version)],
    )
    summary = summarize_protocol_card(card)

    assert card.title == "Alpha assay protocol"
    assert card.linked_paper_ids == ["paper-001", "paper-002"]
    assert card.linked_note_slugs == ["alpha-note", "beta-note"]
    assert summary.protocol_id == "protocol_alpha"
    assert summary.version_count == 1
    assert summary.current_version_id == "protver_alpha_v1"
    assert summary.linked_paper_count == 2


def test_protocol_card_rejects_duplicate_version_numbers() -> None:
    version = _sample_protocol_version()
    duplicate_number = build_protocol_version_summary(
        _sample_protocol_version(version_id="protver_alpha_v1_1", version_number=1, status="draft")
    )

    with pytest.raises(ValidationError):
        ProtocolCard(
            protocol_id="protocol_alpha",
            title="Alpha assay protocol",
            source_kind="mixed",
            created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
            version_summaries=[build_protocol_version_summary(version), duplicate_number],
        )


def test_protocol_card_rejects_unknown_current_version_reference() -> None:
    version = _sample_protocol_version()

    with pytest.raises(ValidationError):
        ProtocolCard(
            protocol_id="protocol_alpha",
            title="Alpha assay protocol",
            source_kind="internal_adaptation",
            current_version_id="protver_missing",
            created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
            version_summaries=[build_protocol_version_summary(version)],
        )


def test_protocol_version_requires_protocol_prefixed_ids() -> None:
    with pytest.raises(ValidationError):
        ProtocolVersion(
            version_id="version-1",
            protocol_id="protocol-alpha",
            version_number=1,
            content_snapshot="Step 1",
            created_by="operator",
            created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
        )
