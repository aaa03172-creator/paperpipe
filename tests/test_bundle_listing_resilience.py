from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.chart_packs.service import list_chart_pack_summaries
from src.chart_packs.store import save_chart_pack_bundle
from src.image_evidence.service import list_image_evidence_summaries
from src.image_evidence.store import save_image_evidence_bundle
from src.meeting_packs.service import list_meeting_packs
from src.meeting_packs.store import save_meeting_pack_bundle
from src.method_comparisons.service import list_method_comparison_summaries
from src.method_comparisons.store import save_method_comparison_bundle
from src.paper_syntheses.service import list_paper_synthesis_summaries
from src.paper_syntheses.store import save_paper_synthesis_bundle
from src.protocol_cards.service import list_protocol_card_summaries
from src.protocol_cards.store import save_protocol_card_bundle
from src.schemas.chart_pack import ChartPack
from src.schemas.chat import ChatEvidenceRef
from src.schemas.image_evidence import ImageEvidence
from src.schemas.meeting_pack import (
    MeetingPack,
    MeetingPackEvidenceRef,
    MeetingPackGenerateRequest,
    MeetingPackOnePageSummary,
    MeetingPackSourceItem,
    MeetingPackSourceSelector,
)
from src.schemas.method_comparison import MethodComparison, build_method_comparison_columns
from src.schemas.paper_synthesis import PaperSynthesis, PaperSynthesisSourceRef
from src.schemas.protocol_card import ProtocolCard, ProtocolVersion, build_protocol_version_summary


def _write_bad_json(root: Path, item_id: str, filename: str) -> None:
    item_dir = root / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / filename).write_text("{bad json", encoding="utf-8")


def _sample_meeting_pack() -> MeetingPack:
    return MeetingPack(
        id="meetingpack_20260313T090000Z_listing_demo",
        mode="journal_club",
        title="Meeting draft",
        created_at=datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc),
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
        one_page_summary=MeetingPackOnePageSummary(overview="Summary"),
        evidence_refs=[MeetingPackEvidenceRef(id="evref_01", paper_slug="paper-alpha")],
    )


def _sample_chart_pack() -> ChartPack:
    return ChartPack(
        chart_pack_id="chartpack_20260320T120000Z_listing_demo",
        title="Chart pack demo",
        created_at=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        charts=[
            {
                "chart_id": "chart_1",
                "title": "Verification counts",
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [{"target_field": "status", "source_field": "verdict"}],
                "data_snapshot_ref": {"kind": "data_csv", "path": "data/chart_1.csv"},
                "spec_ref": {"kind": "spec_json", "path": "specs/chart_1.json"},
            }
        ],
    )


def _sample_image_evidence() -> ImageEvidence:
    return ImageEvidence(
        image_evidence_id="img_listing_demo",
        title="Representative microscopy image",
        created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
        paper_id="paper-001",
        paper_slug="paper-001-note",
        source_ref={"source_kind": "local_file", "local_path": "/tmp/image-001.tif"},
        content_format="image/tiff",
        metadata={"filename": "image-001.tif", "width_px": 1024, "height_px": 768},
    )


def _sample_method_comparison() -> MethodComparison:
    return MethodComparison(
        comparison_id="methodcmp_20260318T120000Z_listing_demo",
        title="Method comparison",
        created_at=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
        readiness="evidence_backed",
        freshness="unknown",
        paper_ids=["paper-001"],
        columns=build_method_comparison_columns(["intervention", "primary_readout"]),
        rows=[
            {
                "paper_id": "paper-001",
                "title": "Demo paper",
                "cells": [
                    {"field_id": "intervention", "value": "Ketone ester", "status": "explicit"},
                    {"field_id": "primary_readout", "value": "Memory score", "status": "explicit"},
                ],
            }
        ],
    )


def _sample_paper_synthesis() -> PaperSynthesis:
    return PaperSynthesis(
        synthesis_id="papersynth_20260407T120000Z_listing_demo",
        paper_slug="paper-alpha",
        title="Paper synthesis: paper-alpha",
        created_at=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 7, 12, 5, tzinfo=timezone.utc),
        readiness="mixed",
        freshness="current",
        summary="Condenses current paper-scoped evidence into a reviewable note.",
        source_refs=[
            PaperSynthesisSourceRef(kind="structured_state", paper_slug="paper-alpha", note="Primary canonical owner."),
            PaperSynthesisSourceRef(
                kind="claimset_resolved",
                paper_slug="paper-alpha",
                run_id="run-001",
                path="storage/artifacts/paper-alpha/run-001/claimset.resolved.json",
            ),
            PaperSynthesisSourceRef(
                kind="run_meta",
                paper_slug="paper-alpha",
                run_id="run-001",
                path="storage/artifacts/paper-alpha/run-001/run_meta.json",
            ),
        ],
        evidence_refs=[ChatEvidenceRef(paper_slug="paper-alpha", run_id="run-001")],
        warnings=["Compiled view only"],
    )


def _sample_protocol_version(
    *,
    version_id: str = "protver_listing_v1",
    version_number: int = 1,
) -> ProtocolVersion:
    return ProtocolVersion(
        version_id=version_id,
        protocol_id="protocol_listing_demo",
        version_number=version_number,
        key_steps_summary=["Seed cells"],
        critical_conditions=["37 C"],
        readouts=["Cell viability"],
        content_snapshot=f"Protocol snapshot {version_number}",
        status="active",
        created_by="operator",
        created_at=datetime(2026, 3, 23, 1, version_number, tzinfo=timezone.utc),
        source_refs=[{"paper_slug": "paper-alpha", "claim_id": f"claim-{version_number:03d}"}],
    )


def _sample_protocol_card(version: ProtocolVersion) -> ProtocolCard:
    return ProtocolCard(
        protocol_id="protocol_listing_demo",
        title="Alpha assay protocol",
        purpose="Evaluate treatment response",
        context="In vitro assay",
        source_kind="paper_derived",
        linked_paper_ids=["paper-001"],
        linked_note_slugs=["alpha-note"],
        current_version_id=version.version_id,
        validation_status="reviewed",
        created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        version_summaries=[build_protocol_version_summary(version)],
    )


def test_meeting_pack_listing_skips_unreadable_bundle(tmp_path, caplog) -> None:
    root = tmp_path / "meeting_packs"
    pack = _sample_meeting_pack()
    save_meeting_pack_bundle(pack, "# Draft\n", root=root)
    _write_bad_json(root, "meetingpack_20260313T090000Z_broken", "meeting_pack.json")

    payload = list_meeting_packs(root=root)

    assert payload.total == 1
    assert [item.pack_id for item in payload.items] == [pack.id]
    assert "Skipping unreadable meeting pack during listing" in caplog.text


def test_chart_pack_listing_skips_unreadable_bundle(tmp_path) -> None:
    root = tmp_path / "chart_packs"
    chart_pack = _sample_chart_pack()
    save_chart_pack_bundle(
        chart_pack,
        "# Chart Pack\n",
        data_snapshots={"chart_1": "status,count\nverified,4\n"},
        specs={"chart_1": {"type": "bar", "x": "status", "y": "count"}},
        root=root,
    )
    _write_bad_json(root, "chartpack_20260320T120000Z_broken", "chart_pack.json")

    items = list_chart_pack_summaries(root=root)

    assert [item.chart_pack_id for item in items] == [chart_pack.chart_pack_id]


def test_image_evidence_listing_skips_unreadable_bundle(tmp_path) -> None:
    root = tmp_path / "image_evidence"
    image_evidence = _sample_image_evidence()
    save_image_evidence_bundle(image_evidence, root=root)
    _write_bad_json(root, "img_broken", "image_evidence.json")

    items = list_image_evidence_summaries(root=root)

    assert [item.image_evidence_id for item in items] == [image_evidence.image_evidence_id]


def test_method_comparison_listing_skips_unreadable_bundle(tmp_path) -> None:
    root = tmp_path / "method_comparisons"
    comparison = _sample_method_comparison()
    save_method_comparison_bundle(comparison, "paper_id,intervention\npaper-001,Ketone ester\n", "# Comparison\n", root=root)
    _write_bad_json(root, "methodcmp_20260318T120000Z_broken", "comparison.json")

    items = list_method_comparison_summaries(root=root)

    assert [item.comparison_id for item in items] == [comparison.comparison_id]


def test_paper_synthesis_listing_skips_unreadable_bundle(tmp_path) -> None:
    root = tmp_path / "paper_syntheses"
    synthesis = _sample_paper_synthesis()
    save_paper_synthesis_bundle(synthesis, "# Paper synthesis\n", root=root)
    _write_bad_json(root, "papersynth_20260407T120000Z_broken", "paper_synthesis.json")

    items = list_paper_synthesis_summaries(root=root)

    assert [item.synthesis_id for item in items] == [synthesis.synthesis_id]


def test_protocol_card_listing_skips_unreadable_bundle(tmp_path) -> None:
    root = tmp_path / "protocol_cards"
    version = _sample_protocol_version()
    card = _sample_protocol_card(version)
    save_protocol_card_bundle(card, "# Protocol Card\n", versions=[version], root=root)
    _write_bad_json(root, "protocol_broken", "protocol_card.json")

    items = list_protocol_card_summaries(root=root)

    assert [item.protocol_id for item in items] == [card.protocol_id]
