from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.talk_packs.pptx_export import talk_pack_pptx_runtime_available

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_talk_pack_pptx_runtime_unavailable_without_skia_canvas(tmp_path, monkeypatch) -> None:
    node_bin = tmp_path / "node" / "bin" / "node"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    node_modules_dir = tmp_path / "node" / "node_modules"
    (node_modules_dir / "@oai" / "artifact-tool").mkdir(parents=True)

    monkeypatch.setenv("PAPERPIPE_TALK_PACK_NODE_BIN", str(node_bin))
    monkeypatch.setenv("PAPERPIPE_TALK_PACK_NODE_MODULES_DIR", str(node_modules_dir))
    monkeypatch.delenv("PAPERPIPE_WORKSPACE_NODE_BIN", raising=False)
    monkeypatch.delenv("PAPERPIPE_WORKSPACE_NODE_MODULES_DIR", raising=False)

    assert talk_pack_pptx_runtime_available() is False


def test_check_talk_pack_render_smoke_script_renders_real_pptx(tmp_path, monkeypatch) -> None:
    if not talk_pack_pptx_runtime_available():
        pytest.skip("Talk Pack PPTX runtime unavailable in current environment.")

    node_bin = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node"
    )
    node_modules_dir = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "node_modules"
    )
    monkeypatch.setenv("PAPERPIPE_TALK_PACK_NODE_BIN", str(node_bin))
    monkeypatch.setenv("PAPERPIPE_TALK_PACK_NODE_MODULES_DIR", str(node_modules_dir))

    script_path = REPO_ROOT / "scripts" / "check_talk_pack_render_smoke.py"
    output_root = tmp_path / "talk_pack_render_smoke"
    env = os.environ.copy()
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--root",
            str(output_root),
            "--talk-pack-id",
            "talkpack_script_smoke_demo",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["talk_pack_id"] == "talkpack_script_smoke_demo"
    assert payload["deck_status"] == "generated"
    assert payload["artifact_path"] == "exports/deck.pptx"
    assert payload["slide_count"] == 2
    assert payload["notes_count"] >= 1
    assert payload["preview_count"] == 2
    assert payload["key_numbers_included"] is True
    assert payload["backup_badge_visible"] is True
    assert payload["audience_scaffolding_hidden"] is True
    assert payload["presenter_metadata_in_notes"] is True
    assert payload["traceability_notes_included"] is True
    assert payload["artifact_ref_notes_included"] is True
    assert payload["style_profile_notes_included"] is True
    assert payload["visual_embedding_included"] is True
    assert payload["visual_source"] == "chart_pack"


def test_check_talk_pack_render_smoke_script_supports_image_evidence_visuals(tmp_path, monkeypatch) -> None:
    if not talk_pack_pptx_runtime_available():
        pytest.skip("Talk Pack PPTX runtime unavailable in current environment.")

    node_bin = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node"
    )
    node_modules_dir = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "node_modules"
    )
    monkeypatch.setenv("PAPERPIPE_TALK_PACK_NODE_BIN", str(node_bin))
    monkeypatch.setenv("PAPERPIPE_TALK_PACK_NODE_MODULES_DIR", str(node_modules_dir))

    script_path = REPO_ROOT / "scripts" / "check_talk_pack_render_smoke.py"
    output_root = tmp_path / "talk_pack_render_smoke_image_evidence"
    env = os.environ.copy()
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--root",
            str(output_root),
            "--talk-pack-id",
            "talkpack_script_smoke_image_evidence_demo",
            "--visual-source",
            "image_evidence",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["talk_pack_id"] == "talkpack_script_smoke_image_evidence_demo"
    assert payload["deck_status"] == "generated"
    assert payload["artifact_path"] == "exports/deck.pptx"
    assert payload["slide_count"] == 2
    assert payload["notes_count"] >= 1
    assert payload["preview_count"] == 2
    assert payload["key_numbers_included"] is True
    assert payload["backup_badge_visible"] is True
    assert payload["audience_scaffolding_hidden"] is True
    assert payload["presenter_metadata_in_notes"] is True
    assert payload["traceability_notes_included"] is True
    assert payload["artifact_ref_notes_included"] is True
    assert payload["style_profile_notes_included"] is True
    assert payload["visual_embedding_included"] is True
    assert payload["visual_source"] == "image_evidence"
