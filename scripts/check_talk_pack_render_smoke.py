from __future__ import annotations

import argparse
import json
import sys
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.chart_packs.store import save_chart_pack_bundle  # noqa: E402
from src.image_evidence.service import register_image_evidence  # noqa: E402
from src.schemas.chart_pack import ChartPack  # noqa: E402
from src.schemas.image_evidence import ImageEvidenceRequest  # noqa: E402
from src.schemas.talk_pack import (  # noqa: E402
    TalkPack,
    TalkPackGenerateRequest,
    TalkPackOutputMember,
    TalkPackReviewArtifact,
    TalkPackUpstreamOwnerRef,
)
from src.talk_packs.service import (  # noqa: E402
    load_declared_talk_pack_artifact,
    render_talk_pack_deck_pptx,
)
from src.talk_packs.store import save_talk_pack_bundle  # noqa: E402

DEFAULT_ROOT = Path("tmp/talk_pack_render_smoke")
DEFAULT_TALK_PACK_ID = "talkpack_smoke_render_demo"
DEFAULT_EXPECTED_SUBSTRING = "Short-chain fatty acids frame the journal club question"
DEFAULT_EXPECTED_KEY_NUMBER_SUBSTRING = "12.4 mM butyrate concentration anchors the opening context."
DEFAULT_EXPECTED_PRIORITY_SUBSTRING = "Must say"
DEFAULT_EXPECTED_BACKUP_SUBSTRING = "Backup"
DEFAULT_EXPECTED_TIME_BUDGET_SUBSTRING = "45 sec"
DEFAULT_EXPECTED_CLAIM_REF_SUBSTRING = "claim_4d5f89ab12cd"
DEFAULT_EXPECTED_KEY_NUMBER_REF_SUBSTRING = "kn_01"
DEFAULT_EXPECTED_SOURCE_ARTIFACT_REF_SUBSTRING = "chartpack_20260421_scfa_visual"
DEFAULT_EXPECTED_VISUAL_REF_SUBSTRING = "chart_pack_render:chartpack_20260421_scfa_visual:chart_1"
_PNG_1X1_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def _sample_pack(talk_pack_id: str) -> TalkPack:
    request = TalkPackGenerateRequest(
        paper_slug="wenzelShortchainFattyAcids2020",
        title="SCFA journal club talk",
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        selected_exports=["deck_pptx", "speaker_script"],
        style_profile="paperpipe_baseline",
        template_attachment_refs=["attachment://smith-lab-journal-club-template.pptx"],
        auto_include_dependencies=True,
    )
    return TalkPack(
        talk_pack_id=talk_pack_id,
        paper_slug="wenzelShortchainFattyAcids2020",
        title="SCFA journal club talk",
        created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        style_profile="paperpipe_baseline",
        template_attachment_refs=["attachment://smith-lab-journal-club-template.pptx"],
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
                status="generated",
            ),
            TalkPackOutputMember(
                kind="key_numbers",
                path="key_numbers.md",
                required=True,
                status="generated",
            ),
            TalkPackOutputMember(
                kind="deck_pptx",
                path="exports/deck.pptx",
                required=True,
                status="blocked",
            ),
            TalkPackOutputMember(
                kind="speaker_script",
                path="exports/speaker_script.md",
                required=True,
                status="generated",
            ),
        ],
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json"),
            TalkPackReviewArtifact(kind="style_lint", path="review/style_lint.json"),
        ],
    )


def _slide_manifest_json(talk_pack_id: str, *, visual_source: str) -> str:
    if visual_source == "image_evidence":
        source_artifact_ref = "img_scfa_visual"
        visual_ref = "image_evidence_derivative:img_scfa_visual:thumb_01.png"
    else:
        source_artifact_ref = "chartpack_20260421_scfa_visual"
        visual_ref = "chart_pack_render:chartpack_20260421_scfa_visual:chart_1"
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
        '      "speaker_priority": "must_say",\n'
        '      "title": "Short-chain fatty acids frame the journal club question",\n'
        '      "primary_message": "Use the opening slide to explain why SCFAs matter before methods or data details.",\n'
        '      "claim_refs": ["claim_4d5f89ab12cd"],\n'
        '      "key_number_refs": ["kn_01"],\n'
        f'      "source_artifact_refs": ["{source_artifact_ref}"],\n'
        f'      "visual_refs": ["{visual_ref}"],\n'
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
        '      "speaker_priority": "skip_if_short_on_time",\n'
        '      "title": "Close with the one evidence-backed take-home",\n'
        '      "primary_message": "The ending slide should compress the discussion into one defensible take-home message.",\n'
        '      "notes_focus": [\n'
        '        "Repeat the strongest supported message.",\n'
        '        "Name the main limitation before discussion opens."\n'
        "      ],\n"
        '      "warnings": []\n'
        "    }\n"
        "  ]\n"
        "}\n"
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
                }
            ],
        ),
        "# Chart Pack\n",
        data_snapshots={"chart_1": "status,count\nverified,4\n"},
        specs={"chart_1": {"type": "bar"}},
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
            }
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded Talk Pack PPTX render smoke check.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--talk-pack-id", default=DEFAULT_TALK_PACK_ID)
    parser.add_argument("--visual-source", choices=("chart_pack", "image_evidence"), default="chart_pack")
    parser.add_argument("--expect-slide-substring", default=DEFAULT_EXPECTED_SUBSTRING)
    parser.add_argument("--expect-key-number-substring", default=DEFAULT_EXPECTED_KEY_NUMBER_SUBSTRING)
    parser.add_argument("--expect-priority-substring", default=DEFAULT_EXPECTED_PRIORITY_SUBSTRING)
    parser.add_argument("--expect-backup-substring", default=DEFAULT_EXPECTED_BACKUP_SUBSTRING)
    parser.add_argument("--expect-time-budget-substring", default=DEFAULT_EXPECTED_TIME_BUDGET_SUBSTRING)
    parser.add_argument("--expect-claim-ref-substring", default=DEFAULT_EXPECTED_CLAIM_REF_SUBSTRING)
    parser.add_argument(
        "--expect-key-number-ref-substring",
        default=DEFAULT_EXPECTED_KEY_NUMBER_REF_SUBSTRING,
    )
    parser.add_argument(
        "--expect-source-artifact-ref-substring",
        default=DEFAULT_EXPECTED_SOURCE_ARTIFACT_REF_SUBSTRING,
    )
    parser.add_argument(
        "--expect-visual-ref-substring",
        default=DEFAULT_EXPECTED_VISUAL_REF_SUBSTRING,
    )
    args = parser.parse_args()

    expected_source_artifact_ref_substring = args.expect_source_artifact_ref_substring
    expected_visual_ref_substring = args.expect_visual_ref_substring
    if args.visual_source == "image_evidence":
        if expected_source_artifact_ref_substring == DEFAULT_EXPECTED_SOURCE_ARTIFACT_REF_SUBSTRING:
            expected_source_artifact_ref_substring = "img_scfa_visual"
        if expected_visual_ref_substring == DEFAULT_EXPECTED_VISUAL_REF_SUBSTRING:
            expected_visual_ref_substring = "image_evidence_derivative:img_scfa_visual:thumb_01.png"

    root = args.root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    chart_root = root.parent / "talk_pack_render_smoke_chart_packs"
    image_root = root.parent / "talk_pack_render_smoke_image_evidence"
    if args.visual_source == "chart_pack":
        chart_root.mkdir(parents=True, exist_ok=True)
        _seed_chart_pack_visual(chart_root)
    else:
        image_root.mkdir(parents=True, exist_ok=True)
        _seed_image_evidence_visual(image_root)
    pack = _sample_pack(args.talk_pack_id)
    save_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _slide_manifest_json(pack.talk_pack_id, visual_source=args.visual_source),
            "key_numbers.md": (
                "# Key Numbers\n\n"
                "- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n"
                "- KN-02: 4.5x higher odds should be framed cautiously as associative.\n"
            ),
            "exports/speaker_script.md": "# Script\n\n- Opening\n- Closing\n",
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
        chart_pack_root=chart_root if args.visual_source == "chart_pack" else None,
        image_evidence_root=image_root if args.visual_source == "image_evidence" else None,
    )
    _, normalized_path, content = load_declared_talk_pack_artifact(
        pack.talk_pack_id,
        "exports/deck.pptx",
        root=root,
    )
    if not content.startswith(b"PK"):
        raise SystemExit("rendered deck is not a ZIP-based pptx")

    archive_path = root / "talk_pack_render_check.pptx"
    archive_path.write_bytes(content)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        if "ppt/slides/slide1.xml" not in names:
            raise SystemExit("rendered deck is missing slide1.xml")
        if "ppt/notesSlides/notesSlide1.xml" not in names:
            raise SystemExit("rendered deck is missing notesSlide1.xml")
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        if args.expect_slide_substring not in slide_xml:
            raise SystemExit(
                f"rendered slide1.xml missing expected substring: {args.expect_slide_substring!r}"
            )
        if args.expect_key_number_substring not in slide_xml:
            raise SystemExit(
                "rendered slide1.xml missing expected key-number substring: "
                f"{args.expect_key_number_substring!r}"
            )
        for hidden_token in ("Speaker focus", "Guardrails", args.expect_priority_substring, args.expect_time_budget_substring):
            if hidden_token in slide_xml:
                raise SystemExit(
                    "rendered slide1.xml still exposes presenter-only scaffolding: "
                    f"{hidden_token!r}"
                )
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        if args.expect_priority_substring not in notes_xml:
            raise SystemExit(
                "rendered notesSlide1.xml missing expected speaker-priority substring: "
                f"{args.expect_priority_substring!r}"
            )
        if args.expect_time_budget_substring not in notes_xml:
            raise SystemExit(
                "rendered notesSlide1.xml missing expected time-budget substring: "
                f"{args.expect_time_budget_substring!r}"
            )
        if args.expect_claim_ref_substring not in notes_xml:
            raise SystemExit(
                "rendered notesSlide1.xml missing expected claim-ref substring: "
                f"{args.expect_claim_ref_substring!r}"
            )
        if args.expect_key_number_ref_substring not in notes_xml:
            raise SystemExit(
                "rendered notesSlide1.xml missing expected key-number-ref substring: "
                f"{args.expect_key_number_ref_substring!r}"
            )
        if expected_source_artifact_ref_substring not in notes_xml:
            raise SystemExit(
                "rendered notesSlide1.xml missing expected source-artifact-ref substring: "
                f"{expected_source_artifact_ref_substring!r}"
            )
        if expected_visual_ref_substring not in notes_xml:
            raise SystemExit(
                "rendered notesSlide1.xml missing expected visual-ref substring: "
                f"{expected_visual_ref_substring!r}"
            )
        if "paperpipe_baseline" not in notes_xml:
            raise SystemExit("rendered notesSlide1.xml missing style-profile note")
        if "attachment://smith-lab-journal-club-template.pptx" not in notes_xml:
            raise SystemExit("rendered notesSlide1.xml missing template-attachment note")
        slide2_xml = archive.read("ppt/slides/slide2.xml").decode("utf-8")
        if args.expect_backup_substring not in slide2_xml:
            raise SystemExit(
                "rendered slide2.xml missing expected backup badge substring: "
                f"{args.expect_backup_substring!r}"
            )
        if not any(name.startswith("ppt/media/") for name in names):
            raise SystemExit("rendered deck is missing embedded visual media files")
        slide_count = sum(1 for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
        notes_count = sum(
            1 for name in names if name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")
        )

    preview_dir = root / pack.talk_pack_id / "preview"
    preview_paths = sorted(preview_dir.glob("slide-*.png"))
    if len(preview_paths) != slide_count:
        raise SystemExit(
            "rendered deck preview count does not match slide count: "
            f"{len(preview_paths)} != {slide_count}"
        )
    for preview_path in preview_paths:
        if not preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise SystemExit(f"rendered deck preview is not a PNG: {preview_path}")

    payload = {
        "talk_pack_id": response.pack.talk_pack_id,
        "deck_status": next(
            member.status for member in response.pack.output_members if member.kind == "deck_pptx"
        ),
        "artifact_path": normalized_path,
        "slide_count": slide_count,
        "notes_count": notes_count,
        "preview_count": len(preview_paths),
        "key_numbers_included": True,
        "backup_badge_visible": True,
        "audience_scaffolding_hidden": True,
        "presenter_metadata_in_notes": True,
        "traceability_notes_included": True,
        "artifact_ref_notes_included": True,
        "style_profile_notes_included": True,
        "visual_embedding_included": True,
        "visual_source": args.visual_source,
        "archive_path": str(archive_path),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
