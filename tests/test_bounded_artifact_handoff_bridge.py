from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.chart_packs.store import save_chart_pack_bundle
from src.image_evidence.store import save_image_evidence_bundle
from src.meeting_packs.store import save_meeting_pack_bundle
from src.method_comparisons.store import save_method_comparison_bundle
from src.paper_syntheses.store import save_paper_synthesis_bundle
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
from src.schemas.talk_pack import (
    TalkPack,
    TalkPackGenerateRequest,
    TalkPackOutputMember,
    TalkPackReviewArtifact,
    TalkPackUpstreamOwnerRef,
)
from src.talk_packs.store import save_talk_pack_bundle


def _browser_headers() -> dict[str, str]:
    return {"origin": "http://testserver"}


def _init_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
    return original_db_path


def _sample_talk_pack() -> TalkPack:
    request = TalkPackGenerateRequest(
        paper_slug="paper-browser-demo",
        title="Browser bridge talk pack",
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        selected_exports=["deck_pptx", "speaker_script"],
        auto_include_dependencies=True,
    )
    return TalkPack(
        talk_pack_id="talkpack_browser_bridge_001",
        paper_slug="paper-browser-demo",
        title="Browser bridge talk pack",
        created_at="2026-04-21T01:02:03Z",
        updated_at="2026-04-21T01:02:03Z",
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        generation_request=request,
        upstream_owners=[
            TalkPackUpstreamOwnerRef(
                owner_kind="paper_state",
                ref="vault/.pp/paper-browser-demo/state.json",
                role="canonical",
            )
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
    )


def _sample_talk_pack_bundle_payloads() -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bytes]]:
    return (
        {
            "slide_manifest.json": '{"slides":[]}\n',
            "key_numbers.md": "# Key Numbers\n",
            "exports/speaker_script.md": "# Script\n",
        },
        {
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        {
            "exports/deck.pptx": b"PPTX placeholder bytes",
        },
    )


def _sample_meeting_pack() -> MeetingPack:
    return MeetingPack(
        id="meetingpack_browser_bridge_001",
        mode="journal_club",
        title="Browser bridge meeting pack",
        created_at=datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc),
        generation_request=MeetingPackGenerateRequest(
            mode="journal_club",
            title="Browser bridge meeting pack",
            source_items=[MeetingPackSourceSelector(type="paper_slug", ref="paper-browser-demo")],
            max_slides=6,
        ),
        source_items=[
            MeetingPackSourceItem(
                id="src_01",
                type="paper_slug",
                ref="paper-browser-demo",
                title="paper-browser-demo",
                priority=1,
                included=True,
            )
        ],
        one_page_summary=MeetingPackOnePageSummary(overview="Summary"),
        evidence_refs=[
            MeetingPackEvidenceRef(
                id="evref_01",
                paper_slug="paper-browser-demo",
                support_type="direct",
            )
        ],
    )


def _sample_method_comparison() -> MethodComparison:
    return MethodComparison(
        comparison_id="methodcmp_browser_bridge_001",
        title="Browser bridge comparison",
        created_at=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
        readiness="evidence_backed",
        freshness="unknown",
        paper_ids=["paper-browser-demo"],
        columns=build_method_comparison_columns(["intervention", "primary_readout"]),
        rows=[
            {
                "paper_id": "paper-browser-demo",
                "title": "Demo paper",
                "cells": [
                    {"field_id": "intervention", "value": "Ketone ester", "status": "explicit"},
                    {"field_id": "primary_readout", "value": "Memory score", "status": "explicit"},
                ],
            }
        ],
    )


def _sample_chart_pack() -> ChartPack:
    return ChartPack(
        chart_pack_id="chartpack_browser_bridge_001",
        title="Browser bridge chart pack",
        created_at=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        charts=[
            {
                "chart_id": "chart_1",
                "title": "Verification counts",
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-browser-demo",
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
        image_evidence_id="img_browser_bridge_001",
        title="Representative microscopy image",
        created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
        paper_id="paper-browser-demo",
        paper_slug="paper-browser-demo",
        source_ref={"source_kind": "local_file", "local_path": "/tmp/image-001.tif"},
        content_format="image/tiff",
        metadata={"filename": "image-001.tif", "width_px": 1024, "height_px": 768},
        derived_outputs=[
            {
                "derived_output_id": "thumb_01",
                "kind": "thumbnail",
                "source_image_evidence_id": "img_browser_bridge_001",
                "created_by": "tester",
                "created_at": "2026-04-21T01:02:03Z",
                "tool_name": "napari",
                "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
            }
        ],
    )


def _sample_paper_synthesis() -> PaperSynthesis:
    return PaperSynthesis(
        synthesis_id="papersynth_browser_bridge_001",
        paper_slug="paper-browser-demo",
        title="Paper synthesis: browser bridge",
        created_at=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 7, 12, 5, tzinfo=timezone.utc),
        readiness="mixed",
        freshness="current",
        summary="Condenses current paper-scoped evidence into a reviewable note.",
        source_refs=[
            PaperSynthesisSourceRef(kind="structured_state", paper_slug="paper-browser-demo", note="Primary canonical owner."),
            PaperSynthesisSourceRef(
                kind="claimset_resolved",
                paper_slug="paper-browser-demo",
                run_id="run-001",
                path="storage/artifacts/paper-browser-demo/run-001/claimset.resolved.json",
            ),
            PaperSynthesisSourceRef(
                kind="run_meta",
                paper_slug="paper-browser-demo",
                run_id="run-001",
                path="storage/artifacts/paper-browser-demo/run-001/run_meta.json",
            ),
        ],
        evidence_refs=[ChatEvidenceRef(paper_slug="paper-browser-demo", run_id="run-001")],
        warnings=["Compiled view only"],
    )


def _sample_protocol_version() -> ProtocolVersion:
    return ProtocolVersion(
        version_id="protver_browser_bridge_v1",
        protocol_id="protocol_browser_bridge_001",
        version_number=1,
        key_steps_summary=["Seed cells", "Add treatment"],
        materials=["DMEM", "FBS"],
        equipment=["incubator"],
        critical_conditions=["37 C", "5% CO2"],
        readouts=["Cell viability"],
        cautions=["Do not overconfluence"],
        content_snapshot="Protocol snapshot 1",
        change_reason="Initial draft",
        status="active",
        created_by="operator",
        created_at=datetime(2026, 3, 23, 1, 1, tzinfo=timezone.utc),
        source_refs=[{"paper_slug": "paper-browser-demo", "claim_id": "claim-001"}],
    )


def _sample_protocol_card(version: ProtocolVersion) -> ProtocolCard:
    return ProtocolCard(
        protocol_id="protocol_browser_bridge_001",
        title="Browser bridge protocol",
        purpose="Evaluate treatment response",
        context="In vitro assay",
        source_kind="paper_derived",
        linked_paper_ids=["paper-browser-demo"],
        linked_note_slugs=["browser-note"],
        current_version_id=version.version_id,
        validation_status="reviewed",
        created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc),
        version_summaries=[build_protocol_version_summary(version)],
    )


def test_api_prefixed_bounded_artifact_handoff_surfaces_bridge_browser_reads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_API_KEY", "secret-key")
    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(tmp_path / "talk_packs"))
    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(tmp_path / "meeting_packs"))
    monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(tmp_path / "method_comparisons"))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(tmp_path / "chart_packs"))
    monkeypatch.setenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", str(tmp_path / "image_evidence"))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(tmp_path / "paper_syntheses"))
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(tmp_path / "protocol_cards"))

    original_db_path = _init_temp_db(tmp_path, monkeypatch)
    try:
        talk_pack = _sample_talk_pack()
        text_artifacts, json_artifacts, binary_artifacts = _sample_talk_pack_bundle_payloads()
        save_talk_pack_bundle(
            talk_pack,
            text_artifacts=text_artifacts,
            json_artifacts=json_artifacts,
            binary_artifacts=binary_artifacts,
            root=tmp_path / "talk_packs",
        )

        save_meeting_pack_bundle(
            _sample_meeting_pack(),
            "# Browser bridge meeting pack\n",
            root=tmp_path / "meeting_packs",
        )
        save_method_comparison_bundle(
            _sample_method_comparison(),
            "paper_id,intervention\npaper-browser-demo,Ketone ester\n",
            "# Comparison\n",
            root=tmp_path / "method_comparisons",
        )
        save_chart_pack_bundle(
            _sample_chart_pack(),
            "# Browser bridge chart pack\n",
            data_snapshots={"chart_1": "status,count\nverified,4\n"},
            specs={"chart_1": {"type": "bar", "x": "status", "y": "count"}},
            root=tmp_path / "chart_packs",
        )
        save_image_evidence_bundle(
            _sample_image_evidence(),
            derivative_artifacts={"derivatives/thumb_01.png": b"PNG"},
            root=tmp_path / "image_evidence",
        )
        save_paper_synthesis_bundle(
            _sample_paper_synthesis(),
            "# Paper synthesis\n",
            root=tmp_path / "paper_syntheses",
        )
        protocol_version = _sample_protocol_version()
        save_protocol_card_bundle(
            _sample_protocol_card(protocol_version),
            "# Browser bridge protocol\n",
            versions=[protocol_version],
            root=tmp_path / "protocol_cards",
        )

        client = TestClient(api_main.app)

        talk_pack_artifact = client.get(
            "/api/talk-packs/talkpack_browser_bridge_001/artifacts/key_numbers.md",
            headers=_browser_headers(),
        )
        assert talk_pack_artifact.status_code == 200
        assert talk_pack_artifact.headers["content-type"].startswith("text/markdown")
        assert talk_pack_artifact.text.startswith("# Key Numbers")

        meeting_pack_markdown = client.get(
            "/api/meeting-packs/meetingpack_browser_bridge_001/markdown",
            headers=_browser_headers(),
        )
        assert meeting_pack_markdown.status_code == 200
        assert meeting_pack_markdown.headers["content-type"].startswith("text/plain")
        assert "Browser bridge meeting pack" in meeting_pack_markdown.text

        method_comparison_markdown = client.get(
            "/api/method-comparisons/methodcmp_browser_bridge_001/markdown",
            headers=_browser_headers(),
        )
        assert method_comparison_markdown.status_code == 200
        assert method_comparison_markdown.headers["content-type"].startswith("text/plain")
        assert method_comparison_markdown.text.startswith("# Comparison")

        chart_pack_markdown = client.get(
            "/api/chart-packs/chartpack_browser_bridge_001/markdown",
            headers=_browser_headers(),
        )
        assert chart_pack_markdown.status_code == 200
        assert chart_pack_markdown.headers["content-type"].startswith("text/plain")
        assert "Browser bridge chart pack" in chart_pack_markdown.text

        image_evidence_derivative = client.get(
            "/api/image-evidence/img_browser_bridge_001/derivatives/thumb_01.png",
            headers=_browser_headers(),
        )
        assert image_evidence_derivative.status_code == 200
        assert image_evidence_derivative.content == b"PNG"

        paper_synthesis_markdown = client.get(
            "/api/paper-syntheses/papersynth_browser_bridge_001/markdown",
            headers=_browser_headers(),
        )
        assert paper_synthesis_markdown.status_code == 200
        assert paper_synthesis_markdown.headers["content-type"].startswith("text/plain")
        assert "# Paper synthesis" in paper_synthesis_markdown.text

        protocol_card_markdown = client.get(
            "/api/protocol-cards/protocol_browser_bridge_001/markdown",
            headers=_browser_headers(),
        )
        assert protocol_card_markdown.status_code == 200
        assert protocol_card_markdown.headers["content-type"].startswith("text/plain")
        assert protocol_card_markdown.text.startswith("# Browser bridge protocol")
    finally:
        db_utils.DB_PATH = original_db_path
