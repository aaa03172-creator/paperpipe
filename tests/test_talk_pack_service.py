from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
import zlib
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.chart_packs.store import save_chart_pack_bundle
from src.image_evidence.service import register_image_evidence
from src.schemas.chart_pack import ChartPack
from src.schemas.image_evidence import ImageEvidenceRequest
from src.schemas.talk_pack import (
    TalkPack,
    TalkPackGenerateRequest,
    TalkPackOutputMember,
    TalkPackReviewArtifact,
    TalkPackUpstreamOwnerRef,
)
from src.talk_packs.service import (
    declared_talk_pack_artifact_paths,
    get_talk_pack,
    list_talk_pack_summaries,
    load_declared_talk_pack_artifact,
    persist_talk_pack_bundle,
    render_talk_pack_deck_pptx,
    summarize_talk_pack,
    talk_pack_list_response,
)
from src.talk_packs.store import talk_pack_json_path
from tests.talk_pack_pptx_runtime import require_talk_pack_pptx_runtime

_PNG_1X1_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)
_EMU_PER_INCH = 914400


def _png_bytes(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    def _chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    rows = b"".join(b"\x00" + bytes(rgba) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(rows))
        + _chunk(b"IEND", b"")
    )


def _slide_image_extents_inches(archive: ZipFile, slide_number: int) -> list[tuple[float, float]]:
    namespaces = {
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    }
    tree = ET.fromstring(archive.read(f"ppt/slides/slide{slide_number}.xml"))
    extents: list[tuple[float, float]] = []
    for picture in tree.findall(".//p:pic", namespaces):
        extent = picture.find(".//a:xfrm/a:ext", namespaces)
        if extent is None:
            continue
        extents.append(
            (
                int(extent.attrib["cx"]) / _EMU_PER_INCH,
                int(extent.attrib["cy"]) / _EMU_PER_INCH,
            )
        )
    return extents


def _sample_pack(
    *,
    talk_pack_id: str,
    title: str,
    updated_at: datetime,
    output_statuses: dict[str, str] | None = None,
    warnings: list[str] | None = None,
    style_profile: str = "paperpipe_baseline",
    template_attachment_refs: list[str] | None = None,
    max_slides: int | None = None,
) -> TalkPack:
    output_statuses = dict(output_statuses or {})
    template_attachment_refs = list(
        template_attachment_refs or ["attachment://smith-lab-journal-club-template.pptx"]
    )
    request = TalkPackGenerateRequest(
        paper_slug="wenzelShortchainFattyAcids2020",
        title=title,
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        selected_exports=["deck_pptx", "speaker_script"],
        style_profile=style_profile,
        template_attachment_refs=template_attachment_refs,
        max_slides=max_slides,
        auto_include_dependencies=True,
    )
    return TalkPack(
        talk_pack_id=talk_pack_id,
        paper_slug="wenzelShortchainFattyAcids2020",
        title=title,
        created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        updated_at=updated_at,
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        style_profile=style_profile,
        template_attachment_refs=template_attachment_refs,
        generation_request=request,
        upstream_owners=[
            TalkPackUpstreamOwnerRef(
                owner_kind="paper_state",
                ref="vault/.pp/wenzelShortchainFattyAcids2020/state.json",
                role="canonical",
            )
        ],
        selected_outputs=["deck_pptx", "speaker_script"],
        required_outputs=["slide_manifest", "key_numbers", "deck_pptx", "speaker_script"],
        output_members=[
            TalkPackOutputMember(
                kind="slide_manifest",
                path="slide_manifest.json",
                required=True,
                status=output_statuses.get("slide_manifest", "generated"),
            ),
            TalkPackOutputMember(
                kind="key_numbers",
                path="key_numbers.md",
                required=True,
                status=output_statuses.get("key_numbers", "generated"),
            ),
            TalkPackOutputMember(
                kind="deck_pptx",
                path="exports/deck.pptx",
                required=True,
                status=output_statuses.get("deck_pptx", "generated"),
            ),
            TalkPackOutputMember(
                kind="speaker_script",
                path="exports/speaker_script.md",
                required=True,
                status=output_statuses.get("speaker_script", "generated"),
            ),
        ],
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json"),
            TalkPackReviewArtifact(kind="style_lint", path="review/style_lint.json"),
        ],
        warnings=list(warnings or []),
    )


def _sample_bundle_payloads() -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bytes]]:
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


def _renderable_slide_manifest_json(talk_pack_id: str) -> str:
    return (
        "{\n"
        '  "schema_version": "draft",\n'
        '  "workflow": "talk_pack_slide_manifest",\n'
        f'  "talk_pack_id": "{talk_pack_id}",\n'
        '  "paper_slug": "wenzelShortchainFattyAcids2020",\n'
        '  "generated_at": "2026-04-21T01:02:03Z",\n'
        '  "talk_mode": "journal_club",\n'
        '  "audience_profile": "mixed_research_group",\n'
        '  "duration_minutes": 12,\n'
        '  "style_profile": "paperpipe_baseline",\n'
        '  "template_attachment_refs": ["attachment://smith-lab-journal-club-template.pptx"],\n'
        '  "slides": [\n'
        "    {\n"
        '      "slide_id": "s01",\n'
        '      "order": 1,\n'
        '      "slide_kind": "main",\n'
        '      "section": "opening",\n'
        '      "time_budget_seconds": 45,\n'
        '      "title": "Short-chain fatty acids frame the journal club question",\n'
        '      "primary_message": "Use the opening slide to explain why SCFAs matter before methods or data details.",\n'
        '      "speaker_priority": "must_say",\n'
        '      "claim_refs": ["claim_4d5f89ab12cd"],\n'
        '      "key_number_refs": ["kn_01"],\n'
        '      "source_artifact_refs": ["chartpack_20260421_scfa_visual"],\n'
        '      "visual_refs": ["chart_pack_render:chartpack_20260421_scfa_visual:chart_1"],\n'
        '      "notes_focus": [\n'
        '        "Define SCFAs in audience-appropriate language.",\n'
        '        "State why the paper matters before methods."\n'
        "      ],\n"
        '      "warnings": [\n'
        '        "Do not overclaim causality from associative evidence."\n'
        "      ]\n"
        "    },\n"
        "    {\n"
        '      "slide_id": "s02",\n'
        '      "order": 2,\n'
        '      "slide_kind": "backup",\n'
        '      "section": "conclusion",\n'
        '      "title": "Close with the one evidence-backed take-home",\n'
        '      "primary_message": "The ending slide should compress the discussion into one defensible take-home message.",\n'
        '      "speaker_priority": "skip_if_short_on_time",\n'
        '      "notes_focus": [\n'
        '        "Repeat the strongest supported message.",\n'
        '        "Name the main limitation before discussion opens."\n'
        "      ],\n"
        '      "warnings": []\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )


def _renderable_slide_manifest_with_two_visual_refs_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_json(talk_pack_id).replace(
        '"visual_refs": ["chart_pack_render:chartpack_20260421_scfa_visual:chart_1"]',
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        "]",
    )


def _renderable_slide_manifest_with_primary_supporting_visual_layout_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_with_two_visual_refs_json(talk_pack_id).replace(
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        "]",
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        '],\n'
        '      "visual_layout": "primary_supporting"',
    )


def _renderable_slide_manifest_with_main_plus_inset_visual_layout_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_with_two_visual_refs_json(talk_pack_id).replace(
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        "]",
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        '],\n'
        '      "visual_layout": "main_plus_inset"',
    )


def _renderable_slide_manifest_with_visual_labels_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_with_main_plus_inset_visual_layout_json(talk_pack_id).replace(
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        '],\n'
        '      "visual_layout": "main_plus_inset"',
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        '],\n'
        '      "visual_layout": "main_plus_inset",\n'
        '      "visual_labels": ["Overview chart", "Responder inset"]',
    )


def _renderable_slide_manifest_with_duplicate_visual_labels_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_with_main_plus_inset_visual_layout_json(talk_pack_id).replace(
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        '],\n'
        '      "visual_layout": "main_plus_inset"',
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2"'
        '],\n'
        '      "visual_layout": "main_plus_inset",\n'
        '      "visual_labels": ["Shared caption", "Shared caption"]',
    )


def _renderable_slide_manifest_with_evidence_refs_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_json(talk_pack_id).replace(
        '"source_artifact_refs": ["chartpack_20260421_scfa_visual"]',
        '"evidence_refs": ['
        '{"paper_slug": "wenzelShortchainFattyAcids2020", '
        '"claim_id": "claim_4d5f89ab12cd", '
        '"evidence_id": "ev_scfa_results_01", '
        '"run_id": "run_20260421", '
        '"locator": {"section": "Results", "page": 4}}'
        '],\n'
        '      "source_artifact_refs": ["chartpack_20260421_scfa_visual"]',
    )


def _renderable_slide_manifest_with_audience_clean_template_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_json(talk_pack_id).replace(
        '"template_attachment_refs": ["attachment://smith-lab-journal-club-template.pptx"]',
        '"template_attachment_refs": ["attachment://paperpipe-audience-clean-16x9"]',
    )


def _renderable_slide_manifest_with_unknown_template_ref_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_json(talk_pack_id).replace(
        '"template_attachment_refs": ["attachment://smith-lab-journal-club-template.pptx"]',
        '"template_attachment_refs": ["attachment://lab-audience-cleanup-template.pptx"]',
    )


def _renderable_slide_manifest_with_three_visual_refs_json(talk_pack_id: str) -> str:
    return _renderable_slide_manifest_json(talk_pack_id).replace(
        '"visual_refs": ["chart_pack_render:chartpack_20260421_scfa_visual:chart_1"]',
        '"visual_refs": ['
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_2", '
        '"chart_pack_render:chartpack_20260421_scfa_visual:chart_1:svg"'
        "]",
    )


def _renderable_slide_manifest_with_image_evidence_visual_json(talk_pack_id: str) -> str:
    return (
        _renderable_slide_manifest_json(talk_pack_id)
        .replace(
            '"source_artifact_refs": ["chartpack_20260421_scfa_visual"]',
            '"source_artifact_refs": ["img_scfa_visual"]',
        )
        .replace(
            '"visual_refs": ["chart_pack_render:chartpack_20260421_scfa_visual:chart_1"]',
            '"visual_refs": ["image_evidence_derivative:img_scfa_visual:thumb_01.png"]',
        )
    )


def _seed_chart_pack_visual(root: Path) -> None:
    save_chart_pack_bundle(
        ChartPack(
            chart_pack_id="chartpack_20260421_scfa_visual",
            title="SCFA visual chart",
            created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
            charts=[
                {
                    "chart_id": "chart_1",
                    "title": "SCFA pathway overview",
                    "template_id": "stats_check_status_counts",
                    "source_ref": {
                        "source_kind": "stats_report",
                        "paper_id": "paper-001",
                        "run_id": "run-001",
                    },
                    "field_mappings": [{"target_field": "status", "source_field": "verdict"}],
                    "data_snapshot_ref": {"kind": "data_csv", "path": "data/chart_1.csv"},
                    "spec_ref": {"kind": "spec_json", "path": "specs/chart_1.json"},
                    "render_refs": [{"kind": "render_svg", "path": "renders/chart_1.svg"}],
                },
                {
                    "chart_id": "chart_2",
                    "title": "SCFA responder subgroup",
                    "template_id": "stats_check_status_counts",
                    "source_ref": {
                        "source_kind": "stats_report",
                        "paper_id": "paper-001",
                        "run_id": "run-001",
                    },
                    "field_mappings": [{"target_field": "status", "source_field": "responder"}],
                    "data_snapshot_ref": {"kind": "data_csv", "path": "data/chart_2.csv"},
                    "spec_ref": {"kind": "spec_json", "path": "specs/chart_2.json"},
                    "render_refs": [{"kind": "render_svg", "path": "renders/chart_2.svg"}],
                },
            ],
        ),
        "# Chart Pack\n",
        data_snapshots={
            "chart_1": "status,count\nverified,4\n",
            "chart_2": "status,count\nresponder,2\nnon_responder,3\n",
        },
        specs={"chart_1": {"type": "bar"}, "chart_2": {"type": "bar"}},
        renders={
            "chart_1": {
                "svg": (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">'
                    '<rect width="320" height="180" fill="#F6F2E9"/>'
                    '<rect x="36" y="42" width="56" height="96" fill="#BC6C25"/>'
                    '<rect x="132" y="66" width="56" height="72" fill="#8F4D12"/>'
                    '<rect x="228" y="24" width="56" height="114" fill="#42535F"/>'
                    "</svg>"
                )
            },
            "chart_2": {
                "svg": (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">'
                    '<rect width="320" height="180" fill="#F6F2E9"/>'
                    '<circle cx="88" cy="94" r="28" fill="#8F4D12"/>'
                    '<circle cx="168" cy="70" r="22" fill="#BC6C25"/>'
                    '<circle cx="242" cy="110" r="34" fill="#42535F"/>'
                    "</svg>"
                )
            },
        },
        root=root,
    )


def _seed_image_evidence_visual(root: Path) -> None:
    register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_scfa_visual",
            title="SCFA microscopy crop",
            source_ref={"source_kind": "external_image_ref", "external_ref": "omero://image/123"},
            content_format="image/tiff",
            derived_outputs=[
                {
                    "derived_output_id": "thumb_01",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_scfa_visual",
                    "created_by": "operator",
                    "created_at": datetime(2026, 4, 21, 1, 5, tzinfo=timezone.utc),
                    "tool_name": "napari",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/thumb_01.png"},
                }
            ],
        ),
        derivative_artifacts={"derivatives/thumb_01.png": _PNG_1X1_BYTES},
        root=root,
        now=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
    )


def _renderable_bundle_payloads(talk_pack_id: str) -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bytes]]:
    return (
        {
            "slide_manifest.json": _renderable_slide_manifest_json(talk_pack_id),
            "key_numbers.md": (
                "# Key Numbers\n\n"
                "- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n"
                "- KN-02: 4.5x higher odds should be framed cautiously as associative.\n"
            ),
            "exports/speaker_script.md": "# Script\n\n- Opening\n- Closing\n",
        },
        {
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        {},
    )


def _actual_paper_unbounded_pack(
    *,
    updated_at: datetime,
    output_statuses: dict[str, str] | None = None,
) -> TalkPack:
    output_statuses = dict(output_statuses or {})
    request = TalkPackGenerateRequest(
        paper_slug="jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
        title="Dubois 2024 seminar talk",
        talk_mode="seminar",
        audience_profile="mixed_research_group",
        duration_minutes=45,
        selected_exports=["deck_pptx", "speaker_script"],
        style_profile="paperpipe_baseline",
        template_attachment_refs=["attachment://paperpipe-baseline-16x9"],
        auto_include_dependencies=True,
    )
    return TalkPack(
        talk_pack_id="talkpack_actual_paper_dubois2024_unbounded_test",
        paper_slug="jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
        title="Dubois 2024 seminar talk",
        created_at=datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc),
        updated_at=updated_at,
        talk_mode="seminar",
        audience_profile="mixed_research_group",
        duration_minutes=45,
        style_profile="paperpipe_baseline",
        template_attachment_refs=["attachment://paperpipe-baseline-16x9"],
        generation_request=request,
        upstream_owners=[
            TalkPackUpstreamOwnerRef(
                owner_kind="paper_state",
                ref="vault/.pp/jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024/state.json",
                role="canonical",
            )
        ],
        selected_outputs=["deck_pptx", "speaker_script"],
        required_outputs=["slide_manifest", "key_numbers", "deck_pptx", "speaker_script"],
        output_members=[
            TalkPackOutputMember(
                kind="slide_manifest",
                path="slide_manifest.json",
                required=True,
                status=output_statuses.get("slide_manifest", "generated"),
            ),
            TalkPackOutputMember(
                kind="key_numbers",
                path="key_numbers.md",
                required=True,
                status=output_statuses.get("key_numbers", "generated"),
            ),
            TalkPackOutputMember(
                kind="deck_pptx",
                path="exports/deck.pptx",
                required=True,
                status=output_statuses.get("deck_pptx", "generated"),
            ),
            TalkPackOutputMember(
                kind="speaker_script",
                path="exports/speaker_script.md",
                required=True,
                status=output_statuses.get("speaker_script", "generated"),
            ),
        ],
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json"),
            TalkPackReviewArtifact(kind="style_lint", path="review/style_lint.json"),
        ],
        warnings=[],
    )


def _actual_paper_unbounded_slide_manifest_json(talk_pack_id: str) -> str:
    payload = {
        "schema_version": "draft",
        "workflow": "talk_pack_slide_manifest",
        "talk_pack_id": talk_pack_id,
        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
        "generated_at": "2026-04-22T03:05:00Z",
        "talk_mode": "seminar",
        "audience_profile": "mixed_research_group",
        "duration_minutes": 45,
        "style_profile": "paperpipe_baseline",
        "template_attachment_refs": ["attachment://paperpipe-baseline-16x9"],
        "slides": [
            {
                "slide_id": "s01",
                "order": 1,
                "slide_kind": "main",
                "section": "opening",
                "time_budget_seconds": 240,
                "title": "Dubois 2024 argues that clinical AD should not be defined by biomarkers alone",
                "primary_message": "The paper reframes Alzheimer disease for clinical use as a clinical-biological construct, not a purely biomarker-defined label.",
                "speaker_priority": "must_say",
                "claim_refs": ["claim_clinical_biological_construct"],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_clinical_biological_construct",
                        "evidence_id": "ev_dubois_construct_statement",
                        "locator": {"section": "Recommendation"},
                    }
                ],
                "source_artifact_refs": [
                    "vault/.pp/jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024/state.json"
                ],
                "notes_focus": [
                    "Open by naming the paper as a recommendation statement, not a treatment trial.",
                    "Tell the audience the key dispute is label discipline, not whether biomarkers matter.",
                ],
                "warnings": [
                    "Do not turn the opening into an anti-biomarker argument."
                ],
            },
            {
                "slide_id": "s02",
                "order": 2,
                "slide_kind": "main",
                "section": "context",
                "time_budget_seconds": 240,
                "title": "This is a language-and-disclosure paper, so the clinical consequences come from naming",
                "primary_message": "The recommendation matters because diagnostic words change disclosure, counseling, follow-up, and trial framing even before they change treatment.",
                "speaker_priority": "must_say",
                "claim_refs": ["claim_clinical_biological_construct"],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_clinical_biological_construct",
                        "evidence_id": "ev_dubois_disclosure_context",
                        "locator": {"section": "Clinical implications"},
                    }
                ],
                "source_artifact_refs": [
                    "vault/.pp/jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024/state.json"
                ],
                "notes_focus": [
                    "Make the clinical context explicit before showing the figures.",
                    "Set up why a wording paper still deserves a full seminar discussion.",
                ],
                "warnings": [
                    "Do not imply the paper itself provides outcome evidence for one labeling strategy over another."
                ],
            },
            {
                "slide_id": "s03",
                "order": 3,
                "slide_kind": "main",
                "section": "definitions",
                "time_budget_seconds": 300,
                "title": "The construct keeps biology in the definition but requires clinical use to stay clinically interpretable",
                "primary_message": "Dubois et al. are not removing biomarkers; they are arguing that the disease label should stay anchored to a clinically intelligible construct.",
                "speaker_priority": "must_say",
                "claim_refs": ["claim_clinical_biological_construct"],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_clinical_biological_construct",
                        "evidence_id": "ev_dubois_biology_and_clinical_use",
                        "locator": {"section": "Definition"},
                    }
                ],
                "source_artifact_refs": [
                    "vault/.pp/jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024/state.json"
                ],
                "notes_focus": [
                    "Use this slide to separate the concept from the later label examples.",
                    "Tell the audience this is the philosophical center of the paper.",
                ],
                "warnings": [
                    "Avoid making the construct sound softer than the authors intend."
                ],
            },
            {
                "slide_id": "s04",
                "order": 4,
                "slide_kind": "main",
                "section": "definitions",
                "time_budget_seconds": 420,
                "title": "The IWG lexicon is the paper's clearest guardrail against overcalling normal cognition as AD",
                "primary_message": "The lexicon creates distinct at-risk, presymptomatic, and clinical AD buckets, which is the paper's main defense against biomarker-positive overdiagnosis.",
                "speaker_priority": "must_say",
                "claim_refs": ["claim_at_risk_not_ad"],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_at_risk_not_ad",
                        "evidence_id": "ev_dubois_iwg_lexicon_box",
                        "locator": {"section": "Lexicon"},
                    }
                ],
                "key_number_refs": ["kn_01"],
                "source_artifact_refs": ["img_dubois_lexicon_box"],
                "visual_refs": [
                    "image_evidence_derivative:img_dubois_lexicon_box:lexicon_box.png"
                ],
                "visual_labels": ["IWG lexicon box"],
                "notes_focus": [
                    "Walk slowly through the lexicon because the later comparison depends on it.",
                    "Use the risk example only as an illustrative anchor, not as the slide's main point.",
                ],
                "warnings": [
                    "Do not present the lexicon box as a quantitative prediction tool."
                ],
            },
            {
                "slide_id": "s05",
                "order": 5,
                "slide_kind": "main",
                "section": "practice_shift",
                "time_budget_seconds": 480,
                "title": "The practical split from AA 2024 is most visible in biomarker-positive normal cognition",
                "primary_message": "The side-by-side comparison shows why IWG 2024 resists calling many biomarker-positive cognitively normal people AD, even when AA 2024 would move closer to that label.",
                "speaker_priority": "must_say",
                "claim_refs": ["claim_core1_biomarker_risk", "claim_at_risk_not_ad"],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_core1_biomarker_risk",
                        "evidence_id": "ev_dubois_biomarker_positive_risk_label",
                        "locator": {"section": "Comparison with AA 2024"},
                    },
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_at_risk_not_ad",
                        "evidence_id": "ev_dubois_iwg_lexicon_box",
                        "locator": {"section": "Lexicon"},
                    },
                ],
                "key_number_refs": ["kn_02"],
                "source_artifact_refs": [
                    "img_dubois_diagnostic_table",
                    "img_dubois_lexicon_box",
                ],
                "visual_refs": [
                    "image_evidence_derivative:img_dubois_diagnostic_table:diagnostic_table.png",
                    "image_evidence_derivative:img_dubois_lexicon_box:lexicon_box.png",
                ],
                "visual_layout": "main_plus_inset",
                "visual_labels": [
                    "AA 2024 vs IWG 2024 comparison",
                    "IWG lexicon reminder",
                ],
                "notes_focus": [
                    "Treat the comparison table as the main evidence-bearing visual.",
                    "Use the inset only to remind the audience why the labels diverge.",
                ],
                "warnings": [
                    "Do not oversell the comparison table as outcome evidence."
                ],
            },
            {
                "slide_id": "s06",
                "order": 6,
                "slide_kind": "main",
                "section": "implications",
                "time_budget_seconds": 300,
                "title": "In practice, the paper is really about disclosure posture, counseling, and what you promise patients",
                "primary_message": "Once the label shifts from AD to at-risk, the downstream conversation changes: how certain you sound, what trajectory you imply, and how urgently you frame action.",
                "speaker_priority": "nice_to_say",
                "claim_refs": ["claim_core1_biomarker_risk"],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_core1_biomarker_risk",
                        "evidence_id": "ev_dubois_disclosure_context",
                        "locator": {"section": "Clinical implications"},
                    }
                ],
                "source_artifact_refs": [
                    "vault/.pp/jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024/state.json"
                ],
                "notes_focus": [
                    "Translate the paper into clinical conversation terms.",
                    "Explain why this matters even if the biomarker evidence itself is unchanged.",
                ],
                "warnings": [
                    "Keep this slide grounded in disclosure consequences rather than therapeutic speculation."
                ],
            },
            {
                "slide_id": "s07",
                "order": 7,
                "slide_kind": "main",
                "section": "limitations",
                "time_budget_seconds": 300,
                "title": "The recommendation is careful, but it still leaves an unresolved tension between restraint and delay",
                "primary_message": "The strength of the paper is linguistic caution, but the unresolved question is whether that caution prevents overdiagnosis or simply delays clearer action for some patients.",
                "speaker_priority": "nice_to_say",
                "claim_refs": ["claim_core1_biomarker_risk"],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_core1_biomarker_risk",
                        "evidence_id": "ev_dubois_unresolved_label_tension",
                        "locator": {"section": "Discussion"},
                    }
                ],
                "source_artifact_refs": [
                    "vault/.pp/jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024/state.json"
                ],
                "notes_focus": [
                    "Turn from summary into critique here.",
                    "Frame this as the main journal-club tension rather than a flaw you can settle from the abstract alone.",
                ],
                "warnings": [
                    "Do not present this limitation as disproving the recommendation."
                ],
            },
            {
                "slide_id": "s08",
                "order": 8,
                "slide_kind": "main",
                "section": "discussion",
                "time_budget_seconds": 300,
                "title": "The seminar question is not whether biomarkers matter, but when biomarker evidence is enough to justify the AD label",
                "primary_message": "A longer talk can end on the boundary question: what evidence threshold should turn biomarker-positive, cognitively normal people into AD rather than at-risk?",
                "speaker_priority": "must_say",
                "claim_refs": [
                    "claim_core1_biomarker_risk",
                    "claim_clinical_biological_construct",
                ],
                "evidence_refs": [
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_core1_biomarker_risk",
                        "evidence_id": "ev_dubois_biomarker_positive_risk_label",
                        "locator": {"section": "Discussion"},
                    },
                    {
                        "paper_slug": "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024",
                        "claim_id": "claim_clinical_biological_construct",
                        "evidence_id": "ev_dubois_construct_statement",
                        "locator": {"section": "Recommendation"},
                    },
                ],
                "source_artifact_refs": [
                    "vault/.pp/jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024/state.json"
                ],
                "notes_focus": [
                    "Use this as the discussion handoff.",
                    "Invite the audience to compare clinical caution with trial-readiness logic.",
                ],
                "warnings": [
                    "Keep the closing question bounded to the recommendation's scope."
                ],
            },
            {
                "slide_id": "s09",
                "order": 9,
                "slide_kind": "backup",
                "section": "backup",
                "title": "This long-form deck is still abstract-aligned, not a full-text methods-and-results appraisal",
                "primary_message": "Even this expanded seminar version preserves bounded paper visuals and traceability, but it still does not replace a full-text critique of the paper's evidence base.",
                "speaker_priority": "skip_if_short_on_time",
                "notes_focus": [
                    "Use only if someone asks how far the deck should be trusted as a paper appraisal."
                ],
                "warnings": [
                    "Do not imply the expanded version became a full-text evidence review."
                ],
            },
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def _actual_paper_unbounded_bundle_payloads(
    talk_pack_id: str,
) -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bytes]]:
    return (
        {
            "slide_manifest.json": _actual_paper_unbounded_slide_manifest_json(talk_pack_id),
            "key_numbers.md": (
                "# Key Numbers\n\n"
                "- kn_01: 21.9% risk example illustrates why biomarker-positive normal cognition should not be labeled deterministically.\n"
                "- kn_02: 17% progression context shows why disclosure language still matters clinically.\n"
            ),
            "exports/speaker_script.md": "# Script\n\n- Opening\n- Discussion\n- Backup\n",
        },
        {
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "pass"},
        },
        {},
    )


def _seed_actual_paper_image_evidence_visuals(root: Path) -> None:
    register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_dubois_lexicon_box",
            title="Dubois lexicon box",
            source_ref={"source_kind": "local_file", "local_path": "paper_visual_source/dubois_lexicon_box.png"},
            content_format="image/png",
            derived_outputs=[
                {
                    "derived_output_id": "lexicon_box",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_dubois_lexicon_box",
                    "created_by": "operator",
                    "created_at": datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc),
                    "tool_name": "manual_crop",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/lexicon_box.png"},
                }
            ],
        ),
        derivative_artifacts={
            "derivatives/lexicon_box.png": _png_bytes(395, 740, (188, 108, 37, 255))
        },
        root=root,
        now=datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc),
    )
    register_image_evidence(
        request=ImageEvidenceRequest(
            image_evidence_id="img_dubois_diagnostic_table",
            title="Dubois diagnostic table",
            source_ref={
                "source_kind": "local_file",
                "local_path": "paper_visual_source/dubois_diagnostic_table.png",
            },
            content_format="image/png",
            derived_outputs=[
                {
                    "derived_output_id": "diagnostic_table",
                    "kind": "thumbnail",
                    "source_image_evidence_id": "img_dubois_diagnostic_table",
                    "created_by": "operator",
                    "created_at": datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc),
                    "tool_name": "manual_crop",
                    "bundle_ref": {"kind": "derived_file", "path": "derivatives/diagnostic_table.png"},
                }
            ],
        ),
        derivative_artifacts={
            "derivatives/diagnostic_table.png": _png_bytes(460, 582, (66, 83, 95, 255))
        },
        root=root,
        now=datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc),
    )


def test_persist_talk_pack_bundle_returns_response_and_writes_owner(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
    )
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()

    response = persist_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    assert response.pack.talk_pack_id == pack.talk_pack_id
    assert talk_pack_json_path(pack.talk_pack_id, root).exists()


def test_get_talk_pack_roundtrips_saved_bundle(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
    )
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()
    persist_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    loaded = get_talk_pack(pack.talk_pack_id, root=root)

    assert loaded.talk_pack_id == pack.talk_pack_id
    assert loaded.title == pack.title


def test_summarize_talk_pack_counts_generated_outputs_only() -> None:
    pack = _sample_pack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked", "speaker_script": "skipped"},
        warnings=["warning a", "warning b"],
    )

    summary = summarize_talk_pack(pack)

    assert summary.selected_output_count == 2
    assert summary.generated_output_count == 2
    assert summary.warning_count == 2
    assert summary.has_generation_request is True


def test_talk_pack_list_response_sorts_newest_first_and_skips_unreadable(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    older = _sample_pack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        title="Older talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
    )
    newer = _sample_pack(
        talk_pack_id="talkpack_20260421T020304Z_journal_club_b2c3d4e5",
        title="Newer talk",
        updated_at=datetime(2026, 4, 21, 2, 3, 4, tzinfo=timezone.utc),
    )
    older_text, older_json, older_binary = _sample_bundle_payloads()
    newer_text, newer_json, newer_binary = _sample_bundle_payloads()
    persist_talk_pack_bundle(
        older,
        text_artifacts=older_text,
        json_artifacts=older_json,
        binary_artifacts=older_binary,
        root=root,
    )
    persist_talk_pack_bundle(
        newer,
        text_artifacts=newer_text,
        json_artifacts=newer_json,
        binary_artifacts=newer_binary,
        root=root,
    )

    corrupt_dir = root / "talkpack_corrupt"
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    (corrupt_dir / "talk_pack.json").write_text("{bad json", encoding="utf-8")

    summaries = list_talk_pack_summaries(root=root)
    response = talk_pack_list_response(root=root)

    assert [item.title for item in summaries] == ["Newer talk", "Older talk"]
    assert [item.title for item in response.items] == ["Newer talk", "Older talk"]
    assert response.total == 2
    assert response.items[0].generated_output_count == 4


def test_declared_talk_pack_artifact_paths_include_generated_outputs_and_reviews_only() -> None:
    pack = _sample_pack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"speaker_script": "blocked"},
        warnings=[],
    )

    declared = declared_talk_pack_artifact_paths(pack)

    assert declared == {
        "slide_manifest.json",
        "key_numbers.md",
        "exports/deck.pptx",
        "review/presentation_review.json",
        "review/style_lint.json",
    }


def test_load_declared_talk_pack_artifact_rejects_undeclared_and_invalid_paths(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_20260421T010203Z_journal_club_a1b2c3d4",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"speaker_script": "blocked"},
        warnings=[],
    )
    text_artifacts, json_artifacts, binary_artifacts = _sample_bundle_payloads()
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            key: value
            for key, value in text_artifacts.items()
            if key != "exports/speaker_script.md"
        },
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    loaded_pack, normalized_path, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "review/presentation_review.json",
        root=root,
    )
    assert loaded_pack.talk_pack_id == pack.talk_pack_id
    assert normalized_path == "review/presentation_review.json"
    assert content.startswith(b"{")

    with pytest.raises(FileNotFoundError, match="is not declared"):
        load_declared_talk_pack_artifact(pack.talk_pack_id, "exports/speaker_script.md", root=root)

    with pytest.raises(ValueError, match="artifact_path is invalid"):
        load_declared_talk_pack_artifact(pack.talk_pack_id, "../secret.txt", root=root)


def test_render_talk_pack_deck_pptx_generates_real_pptx_and_updates_manifest(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    text_artifacts, json_artifacts, binary_artifacts = _renderable_bundle_payloads(pack.talk_pack_id)
    persist_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )
    preview_dir = root / pack.talk_pack_id / "preview"
    preview_dir.mkdir(parents=True)
    stale_preview = preview_dir / "slide-01.png"
    stale_preview.write_bytes(b"stale preview")
    manual_preview_note = preview_dir / "operator-note.txt"
    manual_preview_note.write_text("keep this note\n", encoding="utf-8")

    response = render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    rendered_member = next(
        member for member in response.pack.output_members if member.kind == "deck_pptx"
    )
    assert rendered_member.status == "generated"
    assert response.pack.updated_at > pack.updated_at
    assert stale_preview.exists()
    assert stale_preview.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert len(sorted(preview_dir.glob("slide-*.png"))) == 2
    assert manual_preview_note.read_text(encoding="utf-8") == "keep this note\n"
    assert "preview/slide-01.png" not in declared_talk_pack_artifact_paths(response.pack)
    with pytest.raises(FileNotFoundError, match="is not declared"):
        load_declared_talk_pack_artifact(
            pack.talk_pack_id,
            "preview/slide-01.png",
            root=root,
        )

    _, normalized_path, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    assert normalized_path == "exports/deck.pptx"
    assert content.startswith(b"PK")

    archive_path = tmp_path / "rendered.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert "ppt/slides/slide1.xml" in names
        assert "ppt/slides/slide2.xml" in names
        assert "ppt/notesSlides/notesSlide1.xml" in names
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Short-chain fatty acids frame the journal club question" in slide_xml
        assert "Visual context" in slide_xml
        assert "Evidence anchor" in slide_xml
        assert "12.4 mM butyrate concentration anchors the opening context." in slide_xml
        assert "45 sec" not in slide_xml
        assert "Must say" not in slide_xml
        assert "Speaker focus" not in slide_xml
        assert "Guardrails" not in slide_xml
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "paperpipe_baseline" in notes_xml
        assert "attachment://smith-lab-journal-club-template.pptx" in notes_xml
        assert "45 sec" in notes_xml
        assert "Must say" in notes_xml
        assert "claim_4d5f89ab12cd" in notes_xml
        assert "kn_01" in notes_xml
        assert "chartpack_20260421_scfa_visual" in notes_xml
        assert "chart_pack_render:chartpack_20260421_scfa_visual:chart_1" in notes_xml
        assert any(name.startswith("ppt/media/") for name in names)
        slide2_xml = archive.read("ppt/slides/slide2.xml").decode("utf-8")
        assert "Backup" in slide2_xml
        assert "Verified numbers" not in slide2_xml

    _, _, script_content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/speaker_script.md",
        root=root,
    )
    speaker_script = script_content.decode("utf-8")
    assert "### Slide 1: Short-chain fatty acids frame the journal club question" in speaker_script
    assert "Presenter focus:" in speaker_script
    assert "Claims: claim_4d5f89ab12cd" in speaker_script
    assert "12.4 mM butyrate concentration anchors the opening context." in speaker_script

    _, _, review_content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "review/presentation_review.json",
        root=root,
    )
    presentation_review = json.loads(review_content.decode("utf-8"))
    assert presentation_review["workflow"] == "talk_pack_review"
    assert presentation_review["talk_pack_id"] == pack.talk_pack_id
    assert presentation_review["presenter_view"]["checks"]
    assert presentation_review["evaluator_view"]["checks"]
    assert "evidence_honesty" in presentation_review["reason_codes"]

    _, _, lint_content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "review/style_lint.json",
        root=root,
    )
    style_lint = json.loads(lint_content.decode("utf-8"))
    assert style_lint["workflow"] == "talk_pack_style_lint"
    assert {
        finding["name"]
        for finding in style_lint["findings"]
    } >= {
        "slide_density_high",
        "figure_takeaway_missing",
        "transition_language_missing",
        "numeric_formatting_inconsistent",
    }


def test_render_talk_pack_deck_pptx_rejects_slide_manifest_intent_drift(tmp_path) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_intent_drift_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    text_artifacts, json_artifacts, binary_artifacts = _renderable_bundle_payloads(pack.talk_pack_id)
    text_artifacts["slide_manifest.json"] = text_artifacts["slide_manifest.json"].replace(
        '"talk_mode": "journal_club"',
        '"talk_mode": "seminar"',
    )
    persist_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    with pytest.raises(ValueError, match="talk_mode"):
        render_talk_pack_deck_pptx(pack.talk_pack_id, root=root)


def test_render_talk_pack_deck_pptx_rejects_slide_manifest_max_slides_drift(
    tmp_path,
) -> None:
    root = tmp_path / "talk_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_max_slides_drift_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
        max_slides=10,
    )
    text_artifacts, json_artifacts, binary_artifacts = _renderable_bundle_payloads(pack.talk_pack_id)
    text_artifacts["slide_manifest.json"] = text_artifacts["slide_manifest.json"].replace(
        '"duration_minutes": 12,\n',
        '"duration_minutes": 12,\n'
        '  "max_slides": 8,\n',
    )
    persist_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    with pytest.raises(ValueError, match="max_slides"):
        render_talk_pack_deck_pptx(pack.talk_pack_id, root=root)


def test_render_talk_pack_deck_pptx_applies_editorial_style_profile(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_editorial_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
        style_profile="paperpipe_editorial",
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_json(pack.talk_pack_id).replace(
                '"style_profile": "paperpipe_baseline"',
                '"style_profile": "paperpipe_editorial"',
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_editorial.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "8F3A34" in slide_xml or "8f3a34" in slide_xml
        assert "paperpipe_editorial" in notes_xml


def test_render_talk_pack_deck_pptx_supports_two_visual_refs_per_slide(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_two_visual_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_two_visual_refs_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    response = render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    rendered_member = next(
        member for member in response.pack.output_members if member.kind == "deck_pptx"
    )
    assert rendered_member.status == "generated"
    preview_dir = root / pack.talk_pack_id / "preview"
    preview_images = sorted(preview_dir.glob("slide-*.png"))
    assert len(preview_images) == 2
    assert all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in preview_images)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_two_visuals.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "Visual context" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_1.svg" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_2.svg" in slide_xml
        assert "chart_pack_render:chartpack_20260421_scfa_visual:chart_1" in notes_xml
        assert "chart_pack_render:chartpack_20260421_scfa_visual:chart_2" in notes_xml
        assert len([name for name in names if name.startswith("ppt/media/")]) >= 2


def test_render_talk_pack_deck_pptx_supports_primary_supporting_visual_layout(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_primary_supporting_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_primary_supporting_visual_layout_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_primary_supporting.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "Primary visual" in slide_xml
        assert "Supporting visual" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_1.svg" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_2.svg" in slide_xml
        assert "[Visual Layout]" in notes_xml
        assert "primary_supporting" in notes_xml


def test_render_talk_pack_deck_pptx_supports_main_plus_inset_visual_layout(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_main_plus_inset_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_main_plus_inset_visual_layout_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_main_plus_inset.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "Main visual" in slide_xml
        assert "Inset" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_1.svg" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_2.svg" in slide_xml
        assert "[Visual Layout]" in notes_xml
        assert "main_plus_inset" in notes_xml


def test_render_talk_pack_deck_pptx_supports_human_visual_labels(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_visual_labels_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_visual_labels_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_visual_labels.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "Overview chart" in slide_xml
        assert "Responder inset" in slide_xml
        assert "[Visual Labels]" in notes_xml
        assert "Overview chart" in notes_xml
        assert "Responder inset" in notes_xml


def test_render_talk_pack_deck_pptx_preserves_duplicate_visual_labels(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_duplicate_visual_labels_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_duplicate_visual_labels_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_duplicate_visual_labels.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert slide_xml.count("Shared caption") == 2
        assert "[Visual Labels]" in notes_xml
        assert notes_xml.count("Shared caption") == 2


def test_render_talk_pack_deck_pptx_preserves_evidence_refs_in_speaker_notes(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_evidence_refs_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_evidence_refs_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_evidence_refs.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "[Evidence Refs]" in notes_xml
        assert "wenzelShortchainFattyAcids2020" in notes_xml
        assert "ev_scfa_results_01" in notes_xml
        assert "Results" in notes_xml


def test_render_talk_pack_deck_pptx_applies_audience_clean_template_variant(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_audience_clean_template_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
        template_attachment_refs=["attachment://paperpipe-audience-clean-16x9"],
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_audience_clean_template_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_audience_clean_template.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "OPENING" not in slide_xml
        assert "wenzelShortchainFattyAcids2020" not in slide_xml
        assert "Journal club • Mixed research group • 12 min" in slide_xml
        assert "paperpipe-audience-clean-16x9" in notes_xml
        assert "[Template Variant]" in notes_xml
        assert "audience_clean" in notes_xml


def test_render_talk_pack_deck_pptx_keeps_unknown_template_refs_trace_only(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    unknown_template_ref = "attachment://lab-audience-cleanup-template.pptx"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_unknown_template_ref_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
        template_attachment_refs=[unknown_template_ref],
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_unknown_template_ref_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_unknown_template_ref.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "OPENING" in slide_xml
        assert "wenzelShortchainFattyAcids2020" in slide_xml
        assert "Journal club • Mixed research group • 12 min" not in slide_xml
        assert unknown_template_ref in notes_xml
        assert "[Template Variant]" in notes_xml
        assert "default" in notes_xml
        assert "audience_clean" not in notes_xml


def test_render_talk_pack_deck_pptx_rejects_more_than_two_visual_refs_per_slide(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_multi_visual_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_three_visual_refs_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    with pytest.raises(ValueError, match="at most two visual_refs per slide"):
        render_talk_pack_deck_pptx(pack.talk_pack_id, root=root, chart_pack_root=chart_root)


def test_render_talk_pack_deck_pptx_supports_image_evidence_visual_refs(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    image_root = tmp_path / "image_evidence"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_image_evidence_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_image_evidence_visual(image_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_image_evidence_visual_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    response = render_talk_pack_deck_pptx(
        pack.talk_pack_id,
        root=root,
        image_evidence_root=image_root,
    )

    rendered_member = next(
        member for member in response.pack.output_members if member.kind == "deck_pptx"
    )
    assert rendered_member.status == "generated"
    preview_dir = root / pack.talk_pack_id / "preview"
    preview_images = sorted(preview_dir.glob("slide-*.png"))
    assert len(preview_images) == 2
    assert all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in preview_images)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_image_evidence.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Visual context" in slide_xml
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "img_scfa_visual" in notes_xml
        assert "image_evidence_derivative:img_scfa_visual:thumb_01.png" in notes_xml
        assert any(name.startswith("ppt/media/") for name in names)


def test_render_talk_pack_deck_pptx_discovers_sibling_image_evidence_root(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    workspace_root = tmp_path / "workspace"
    root = workspace_root / "talk_packs"
    image_root = workspace_root / "image_evidence"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_image_evidence_sibling_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_image_evidence_visual(image_root)
    persist_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_with_image_evidence_visual_json(
                pack.talk_pack_id
            ),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=root,
    )

    response = render_talk_pack_deck_pptx(pack.talk_pack_id, root=root)

    rendered_member = next(
        member for member in response.pack.output_members if member.kind == "deck_pptx"
    )
    assert rendered_member.status == "generated"
    preview_dir = root / pack.talk_pack_id / "preview"
    preview_images = sorted(preview_dir.glob("slide-*.png"))
    assert len(preview_images) == 2
    assert all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in preview_images)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_image_evidence_sibling_root.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Visual context" in slide_xml
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "image_evidence_derivative:img_scfa_visual:thumb_01.png" in notes_xml
        assert any(name.startswith("ppt/media/") for name in names)


def test_render_talk_pack_deck_pptx_keeps_actual_paper_unbounded_quality_bar(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    root = tmp_path / "talk_packs"
    image_root = tmp_path / "image_evidence"
    pack = _actual_paper_unbounded_pack(
        updated_at=datetime(2026, 4, 22, 3, 0, 0, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_actual_paper_image_evidence_visuals(image_root)
    text_artifacts, json_artifacts, binary_artifacts = _actual_paper_unbounded_bundle_payloads(
        pack.talk_pack_id
    )
    persist_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )

    response = render_talk_pack_deck_pptx(
        pack.talk_pack_id,
        root=root,
        image_evidence_root=image_root,
    )

    rendered_member = next(
        member for member in response.pack.output_members if member.kind == "deck_pptx"
    )
    assert rendered_member.status == "generated"
    preview_dir = root / pack.talk_pack_id / "preview"
    preview_images = sorted(preview_dir.glob("slide-*.png"))
    assert len(preview_images) == 9
    assert all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in preview_images)

    _, _, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    archive_path = tmp_path / "rendered_actual_paper_unbounded.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        slide1_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes1_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        slide4_xml = archive.read("ppt/slides/slide4.xml").decode("utf-8")
        notes4_xml = archive.read("ppt/notesSlides/notesSlide4.xml").decode("utf-8")
        slide5_xml = archive.read("ppt/slides/slide5.xml").decode("utf-8")
        notes5_xml = archive.read("ppt/notesSlides/notesSlide5.xml").decode("utf-8")
        slide9_xml = archive.read("ppt/slides/slide9.xml").decode("utf-8")
        notes9_xml = archive.read("ppt/notesSlides/notesSlide9.xml").decode("utf-8")

        assert "Dubois 2024 argues that clinical AD should not be defined by biomarkers alone" in slide1_xml
        assert "Must say" not in slide1_xml
        assert "Nice to say" not in slide1_xml
        assert "Skip if short on time" not in slide1_xml
        assert "Speaker focus" not in slide1_xml
        assert "Guardrails" not in slide1_xml
        assert "Must say" in notes1_xml
        assert "[Notes Focus]" in notes1_xml
        assert "[Warnings]" in notes1_xml
        assert "claim_clinical_biological_construct" in notes1_xml

        assert "Evidence anchor" in slide4_xml
        assert "IWG lexicon box" in slide4_xml
        assert "Must say" not in slide4_xml
        assert "Speaker focus" not in slide4_xml
        assert "kn_01" in notes4_xml
        assert "img_dubois_lexicon_box" in notes4_xml
        assert "image_evidence_derivative:img_dubois_lexicon_box:lexicon_box.png" in notes4_xml
        assert "Must say" in notes4_xml
        slide4_extents = _slide_image_extents_inches(archive, 4)
        assert len(slide4_extents) == 1
        assert slide4_extents[0][0] >= 2.45

        assert "Evidence anchor" in slide5_xml
        assert "AA 2024 vs IWG 2024 comparison" in slide5_xml
        assert "IWG lexicon reminder" in slide5_xml
        assert "Must say" not in slide5_xml
        assert "Speaker focus" not in slide5_xml
        assert "kn_02" in notes5_xml
        assert "main_plus_inset" in notes5_xml
        assert "image_evidence_derivative:img_dubois_diagnostic_table:diagnostic_table.png" in notes5_xml
        assert "image_evidence_derivative:img_dubois_lexicon_box:lexicon_box.png" in notes5_xml
        slide5_extents = sorted(
            _slide_image_extents_inches(archive, 5),
            key=lambda extent: extent[0] * extent[1],
            reverse=True,
        )
        assert len(slide5_extents) == 2
        assert slide5_extents[0][0] >= 3.2
        assert slide5_extents[1][0] >= 1.4

        assert "Backup" in slide9_xml
        assert "Skip if short on time" not in slide9_xml
        assert "Skip if short on time" in notes9_xml
        assert any(name.startswith("ppt/media/") for name in names)

    _, _, script_content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/speaker_script.md",
        root=root,
    )
    speaker_script = script_content.decode("utf-8")
    assert "Presenter priority: Must say" in speaker_script
    assert "Time budget: 7 min" in speaker_script
    assert "Evidence refs: ev_dubois_iwg_lexicon_box" in speaker_script

    _, _, review_content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "review/presentation_review.json",
        root=root,
    )
    presentation_review = json.loads(review_content.decode("utf-8"))
    assert presentation_review["workflow"] == "talk_pack_review"
    assert presentation_review["overall_status"] == "pass"
    assert presentation_review["reason_codes"] == []

    _, _, lint_content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "review/style_lint.json",
        root=root,
    )
    style_lint = json.loads(lint_content.decode("utf-8"))
    assert style_lint["workflow"] == "talk_pack_style_lint"
    assert style_lint["overall_status"] == "pass"
