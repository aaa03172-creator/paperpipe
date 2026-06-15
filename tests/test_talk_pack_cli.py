from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

import src.cli as cli
from src.schemas.talk_pack import (
    TalkPack,
    TalkPackGenerateRequest,
    TalkPackOutputMember,
    TalkPackUpstreamOwnerRef,
)
from src.talk_packs.store import save_talk_pack_bundle


def _sample_pack(*, talk_pack_id: str = "talkpack_cli_demo") -> TalkPack:
    request = TalkPackGenerateRequest(
        paper_slug="paper-alpha",
        title="Paper Alpha talk",
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        selected_exports=["deck_pptx", "speaker_script"],
        auto_include_dependencies=True,
    )
    return TalkPack(
        talk_pack_id=talk_pack_id,
        paper_slug="paper-alpha",
        title="Paper Alpha talk",
        created_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 21, 1, 2, 3, tzinfo=timezone.utc),
        talk_mode="journal_club",
        audience_profile="mixed_research_group",
        duration_minutes=12,
        generation_request=request,
        upstream_owners=[
            TalkPackUpstreamOwnerRef(
                owner_kind="paper_state",
                ref="vault/.pp/paper-alpha/state.json",
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
    )


def _save_sample_bundle(root, *, talk_pack_id: str = "talkpack_cli_demo") -> TalkPack:
    pack = _sample_pack(talk_pack_id=talk_pack_id)
    save_talk_pack_bundle(
        pack,
        text_artifacts={
            "slide_manifest.json": '{"slides":[]}\n',
            "key_numbers.md": "# Key Numbers\n",
            "exports/speaker_script.md": "# Script\n",
        },
        binary_artifacts={"exports/deck.pptx": b"PPTX placeholder bytes"},
        root=root,
    )
    return pack


def test_talk_pack_cli_list_and_show_json(monkeypatch, tmp_path) -> None:
    talk_root = tmp_path / "talk_packs"
    pack = _save_sample_bundle(talk_root)
    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    runner = CliRunner()

    listed = runner.invoke(cli.app, ["talk-pack-list", "--json"])
    assert listed.exit_code == 0
    list_payload = json.loads(listed.output)
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["talk_pack_id"] == pack.talk_pack_id

    shown = runner.invoke(cli.app, ["talk-pack-show", pack.talk_pack_id])
    assert shown.exit_code == 0
    show_payload = json.loads(shown.output)
    assert show_payload["pack"]["talk_pack_id"] == pack.talk_pack_id
    assert show_payload["pack"]["paper_slug"] == "paper-alpha"


def test_talk_pack_cli_render_deck_uses_service(monkeypatch, tmp_path) -> None:
    talk_root = tmp_path / "talk_packs"
    pack = _save_sample_bundle(talk_root, talk_pack_id="talkpack_cli_render_demo")
    monkeypatch.setenv("PAPERPIPE_TALK_PACKS_DIR", str(talk_root))
    calls: list[str] = []

    def fake_render_talk_pack_deck_pptx(talk_pack_id: str):
        calls.append(talk_pack_id)
        from src.talk_packs.service import talk_pack_response_payload

        return talk_pack_response_payload(pack)

    monkeypatch.setattr("src.talk_packs.service.render_talk_pack_deck_pptx", fake_render_talk_pack_deck_pptx)

    result = CliRunner().invoke(cli.app, ["talk-pack-render-deck", pack.talk_pack_id])

    assert result.exit_code == 0
    assert calls == [pack.talk_pack_id]
    payload = json.loads(result.output)
    assert payload["pack"]["talk_pack_id"] == pack.talk_pack_id
