from __future__ import annotations

from pathlib import Path

import pytest

from src.talk_packs.pptx_export import talk_pack_pptx_runtime_available


def require_talk_pack_pptx_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
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
