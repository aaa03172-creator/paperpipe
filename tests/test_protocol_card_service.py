from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.protocol_cards.service import (
    get_protocol_card_bundle,
    list_protocol_card_summaries,
    protocol_card_list_response,
    upsert_protocol_card,
)
from src.schemas.protocol_card import ProtocolCardRequest


def _sample_request(*, title: str = "Alpha assay", protocol_id: str | None = "protocol_alpha") -> ProtocolCardRequest:
    return ProtocolCardRequest(
        protocol_id=protocol_id,
        title=title,
        purpose="Evaluate treatment response",
        context="In vitro assay",
        source_kind="paper_derived",
        linked_paper_ids=["paper-001"],
        linked_note_slugs=["alpha-note"],
        versions=[
            {
                "version_id": "protver_alpha_v1",
                "version_number": 1,
                "key_steps_summary": ["Seed cells"],
                "critical_conditions": ["37 C"],
                "readouts": ["Cell viability"],
                "content_snapshot": "Step 1: seed cells",
                "status": "active",
                "created_by": "operator",
                "created_at": datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
                "source_refs": [{"paper_slug": "paper-alpha", "claim_id": "claim-001"}],
            }
        ],
    )


def test_upsert_protocol_card_roundtrip_builds_bundle_and_defaults_current_version(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    request = _sample_request()

    created = upsert_protocol_card(request=request, root=root)
    fetched = get_protocol_card_bundle("protocol_alpha", root=root)

    assert created.protocol_card.protocol_id == "protocol_alpha"
    assert created.protocol_card.current_version_id == "protver_alpha_v1"
    assert created.protocol_card.validation_status == "draft"
    assert created.versions[0].protocol_id == "protocol_alpha"
    assert fetched.protocol_card.title == "Alpha assay"
    assert fetched.versions[0].version_id == "protver_alpha_v1"
    assert "# Alpha assay" in fetched.markdown
    assert "Step 1: seed cells" in fetched.markdown


def test_upsert_protocol_card_generates_protocol_and_version_ids_when_missing(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    request = ProtocolCardRequest(
        title="Generated protocol",
        source_kind="mixed",
        versions=[
            {
                "version_number": 2,
                "content_snapshot": "Protocol snapshot",
                "status": "draft",
                "created_by": "operator",
            }
        ],
    )

    created = upsert_protocol_card(
        request=request,
        root=root,
        now=datetime(2026, 3, 23, 3, 0, tzinfo=timezone.utc),
    )

    assert created.protocol_card.protocol_id.startswith("protocol_20260323T030000Z_")
    assert created.versions[0].version_id.startswith("protver_20260323T030000Z_")
    assert created.protocol_card.current_version_id == created.versions[0].version_id


def test_protocol_card_list_response_orders_recent_first(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    older = _sample_request(title="Older protocol", protocol_id="protocol_older")
    newer = _sample_request(title="Newer protocol", protocol_id="protocol_newer")

    upsert_protocol_card(
        request=older,
        root=root,
        now=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
    )
    upsert_protocol_card(
        request=newer,
        root=root,
        now=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc) + timedelta(hours=1),
    )

    summaries = list_protocol_card_summaries(root=root)
    payload = protocol_card_list_response(root=root)

    assert [item.protocol_id for item in summaries] == ["protocol_newer", "protocol_older"]
    assert [item.protocol_id for item in payload.items] == ["protocol_newer", "protocol_older"]
    assert payload.total == 2
