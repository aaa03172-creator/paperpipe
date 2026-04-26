from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from backend import main as api_main
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
from src.talk_packs.store import save_talk_pack_bundle
from tests.talk_pack_pptx_runtime import require_talk_pack_pptx_runtime

_PNG_1X1_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
)


def _sample_pack(
    *,
    talk_pack_id: str,
    title: str,
    updated_at: datetime,
    output_statuses: dict[str, str] | None = None,
    review_artifacts: list[TalkPackReviewArtifact] | None = None,
    warnings: list[str] | None = None,
    style_profile: str = "paperpipe_baseline",
    template_attachment_refs: list[str] | None = None,
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
        review_artifacts=review_artifacts
        or [
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
        '      "notes_focus": ["Define SCFAs before methods."],\n'
        '      "warnings": ["Do not overclaim causality from associative evidence."]\n'
        "    }\n"
        "  ]\n"
        "}\n"
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
                }
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


def test_talk_packs_api_get_and_list_roundtrip(tmp_path, monkeypatch) -> None:
    talk_root = tmp_path / "talk_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_api_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"speaker_script": "blocked"},
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json")
        ],
        warnings=["Presentation should stay within 12 minutes."],
    )
    text_artifacts = {
        "slide_manifest.json": '{"slides":[]}\n',
        "key_numbers.md": "# Key Numbers\n",
    }
    json_artifacts = {
        "review/presentation_review.json": {"overall_status": "pass"},
    }
    binary_artifacts = {
        "exports/deck.pptx": b"PPTX placeholder bytes",
    }
    save_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    fetched = client.get("/talk-packs/talkpack_api_demo")
    assert fetched.status_code == 200
    payload = fetched.json()
    assert payload["pack"]["talk_pack_id"] == "talkpack_api_demo"
    assert payload["pack"]["title"] == "SCFA journal club talk"
    assert payload["pack"]["review_artifacts"] == [
        {
            "kind": "presentation_review",
            "path": "review/presentation_review.json",
            "role": "review_only",
        }
    ]

    listed = client.get("/talk-packs")
    assert listed.status_code == 200
    list_payload = listed.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["talk_pack_id"] == "talkpack_api_demo"
    assert list_payload["items"][0]["selected_output_count"] == 2
    assert list_payload["items"][0]["generated_output_count"] == 3
    assert list_payload["items"][0]["warning_count"] == 1
    assert list_payload["items"][0]["has_generation_request"] is True

    artifact = client.get("/talk-packs/talkpack_api_demo/artifacts/key_numbers.md")
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("text/markdown")
    assert artifact.headers["content-disposition"] == (
        'attachment; filename="talkpack_api_demo_key_numbers.md"'
    )
    assert artifact.text == "# Key Numbers\n"

    review_artifact = client.get(
        "/talk-packs/talkpack_api_demo/artifacts/review/presentation_review.json"
    )
    assert review_artifact.status_code == 200
    assert review_artifact.headers["content-type"].startswith("application/json")
    assert review_artifact.json()["overall_status"] == "pass"

    deck_artifact = client.get("/talk-packs/talkpack_api_demo/artifacts/exports/deck.pptx")
    assert deck_artifact.status_code == 200
    assert deck_artifact.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert deck_artifact.content == b"PPTX placeholder bytes"


def test_talk_packs_api_lists_recent_first_and_skips_corrupt(tmp_path, monkeypatch) -> None:
    talk_root = tmp_path / "talk_packs"
    older = _sample_pack(
        talk_pack_id="talkpack_older",
        title="Older talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
    )
    newer = _sample_pack(
        talk_pack_id="talkpack_newer",
        title="Newer talk",
        updated_at=datetime(2026, 4, 21, 2, 3, 4, tzinfo=timezone.utc),
    )
    older_text, older_json, older_binary = _sample_bundle_payloads()
    newer_text, newer_json, newer_binary = _sample_bundle_payloads()
    save_talk_pack_bundle(
        older,
        text_artifacts=older_text,
        json_artifacts=older_json,
        binary_artifacts=older_binary,
        root=talk_root,
    )
    save_talk_pack_bundle(
        newer,
        text_artifacts=newer_text,
        json_artifacts=newer_json,
        binary_artifacts=newer_binary,
        root=talk_root,
    )

    corrupt_dir = talk_root / "talkpack_corrupt"
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    (corrupt_dir / "talk_pack.json").write_text("{bad json", encoding="utf-8")

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    listed = client.get("/talk-packs")

    assert listed.status_code == 200
    payload = listed.json()
    assert [item["title"] for item in payload["items"]] == ["Newer talk", "Older talk"]
    assert payload["total"] == 2


def test_talk_packs_api_returns_404_when_pack_missing(tmp_path, monkeypatch) -> None:
    talk_root = tmp_path / "talk_packs"
    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    response = client.get("/talk-packs/talkpack_missing")

    assert response.status_code == 404
    assert "Talk Pack JSON not found" in response.json()["detail"]


def test_talk_packs_api_rejects_undeclared_or_invalid_artifact_paths(tmp_path, monkeypatch) -> None:
    talk_root = tmp_path / "talk_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_api_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"speaker_script": "blocked"},
        review_artifacts=[
            TalkPackReviewArtifact(kind="presentation_review", path="review/presentation_review.json")
        ],
        warnings=[],
    )
    save_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": '{"slides":[]}\n',
            "key_numbers.md": "# Key Numbers\n",
        },
        json_artifacts={"review/presentation_review.json": {"overall_status": "pass"}},
        binary_artifacts={"exports/deck.pptx": b"PPTX placeholder bytes"},
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    undeclared = client.get("/talk-packs/talkpack_api_demo/artifacts/exports/speaker_script.md")
    assert undeclared.status_code == 404
    assert "is not declared" in undeclared.json()["detail"]

    invalid = client.get("/talk-packs/talkpack_api_demo/artifacts/%2E%2E/secret.txt")
    assert invalid.status_code == 400
    assert "artifact_path is invalid" in invalid.json()["detail"]


def test_talk_packs_api_render_deck_generates_real_pptx(tmp_path, monkeypatch) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": _renderable_slide_manifest_json(pack.talk_pack_id),
            "key_numbers.md": "# Key Numbers\n\n- KN-01: 12.4 mM butyrate concentration anchors the opening context.\n",
            "exports/speaker_script.md": "# Script\n",
        },
        json_artifacts={
            "review/presentation_review.json": {"overall_status": "pass"},
            "review/style_lint.json": {"overall_status": "warn"},
        },
        binary_artifacts={},
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200
    payload = rendered.json()
    deck_member = next(
        member for member in payload["pack"]["output_members"] if member["kind"] == "deck_pptx"
    )
    assert deck_member["status"] == "generated"

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api.pptx"
    archive_path.write_bytes(artifact.content)
    with ZipFile(archive_path) as archive:
        assert "ppt/slides/slide1.xml" in archive.namelist()
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
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
        assert any(name.startswith("ppt/media/") for name in archive.namelist())


def test_talk_packs_api_render_deck_supports_two_visual_refs_per_slide(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_two_visual_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_two_visuals.pptx"
    archive_path.write_bytes(artifact.content)
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


def test_talk_packs_api_render_deck_supports_primary_supporting_visual_layout(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_primary_supporting_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_primary_supporting.pptx"
    archive_path.write_bytes(artifact.content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "Primary visual" in slide_xml
        assert "Supporting visual" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_1.svg" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_2.svg" in slide_xml
        assert "[Visual Layout]" in notes_xml
        assert "primary_supporting" in notes_xml


def test_talk_packs_api_render_deck_supports_main_plus_inset_visual_layout(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_main_plus_inset_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_main_plus_inset.pptx"
    archive_path.write_bytes(artifact.content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "Main visual" in slide_xml
        assert "Inset" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_1.svg" in slide_xml
        assert "chartpack_20260421_scfa_visual/chart_2.svg" in slide_xml
        assert "[Visual Layout]" in notes_xml
        assert "main_plus_inset" in notes_xml


def test_talk_packs_api_render_deck_supports_human_visual_labels(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_visual_labels_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_visual_labels.pptx"
    archive_path.write_bytes(artifact.content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "Overview chart" in slide_xml
        assert "Responder inset" in slide_xml
        assert "[Visual Labels]" in notes_xml
        assert "Overview chart" in notes_xml
        assert "Responder inset" in notes_xml


def test_talk_packs_api_render_deck_preserves_duplicate_visual_labels(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_duplicate_visual_labels_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_duplicate_visual_labels.pptx"
    archive_path.write_bytes(artifact.content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert slide_xml.count("Shared caption") == 2
        assert "[Visual Labels]" in notes_xml
        assert notes_xml.count("Shared caption") == 2


def test_talk_packs_api_render_deck_applies_audience_clean_template_variant(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_audience_clean_template_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
        template_attachment_refs=["attachment://paperpipe-audience-clean-16x9"],
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_audience_clean_template.pptx"
    archive_path.write_bytes(artifact.content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "OPENING" not in slide_xml
        assert "wenzelShortchainFattyAcids2020" not in slide_xml
        assert "Journal club • Mixed research group • 12 min" in slide_xml
        assert "paperpipe-audience-clean-16x9" in notes_xml
        assert "[Template Variant]" in notes_xml
        assert "audience_clean" in notes_xml


def test_talk_packs_api_render_deck_keeps_unknown_template_refs_trace_only(
    tmp_path,
    monkeypatch,
) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    chart_root = tmp_path / "chart_packs"
    unknown_template_ref = "attachment://lab-audience-cleanup-template.pptx"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_unknown_template_ref_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
        template_attachment_refs=[unknown_template_ref],
    )
    _seed_chart_pack_visual(chart_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(chart_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_unknown_template_ref.pptx"
    archive_path.write_bytes(artifact.content)
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


def test_talk_packs_api_render_deck_supports_image_evidence_visual_refs(tmp_path, monkeypatch) -> None:
    require_talk_pack_pptx_runtime(monkeypatch)
    talk_root = tmp_path / "talk_packs"
    image_root = tmp_path / "image_evidence"
    pack = _sample_pack(
        talk_pack_id="talkpack_render_api_image_evidence_demo",
        title="SCFA journal club talk",
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        output_statuses={"deck_pptx": "blocked"},
    )
    _seed_image_evidence_visual(image_root)
    save_talk_pack_bundle(
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
        root=talk_root,
    )

    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    monkeypatch.setenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", str(image_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)

    rendered = client.post(f"/talk-packs/{pack.talk_pack_id}/render-deck")
    assert rendered.status_code == 200

    artifact = client.get(f"/talk-packs/{pack.talk_pack_id}/artifacts/exports/deck.pptx")
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"PK")

    archive_path = tmp_path / "rendered_api_image_evidence.pptx"
    archive_path.write_bytes(artifact.content)
    with ZipFile(archive_path) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Visual context" in slide_xml
        notes_xml = archive.read("ppt/notesSlides/notesSlide1.xml").decode("utf-8")
        assert "img_scfa_visual" in notes_xml
        assert "image_evidence_derivative:img_scfa_visual:thumb_01.png" in notes_xml
        assert any(name.startswith("ppt/media/") for name in archive.namelist())
