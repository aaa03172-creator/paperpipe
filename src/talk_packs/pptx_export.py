from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.schemas.talk_pack import TalkPack, TalkPackSlideManifest
from src.services.runtime_paths import repo_root

_DEFAULT_CODEX_NODE_BIN = (
    Path.home()
    / ".cache"
    / "codex-runtimes"
    / "codex-primary-runtime"
    / "dependencies"
    / "node"
    / "bin"
    / "node"
)
_DEFAULT_CODEX_NODE_MODULES_DIR = (
    Path.home()
    / ".cache"
    / "codex-runtimes"
    / "codex-primary-runtime"
    / "dependencies"
    / "node"
    / "node_modules"
)
_AUDIENCE_CLEAN_TEMPLATE_REFS = {
    "attachment://paperpipe-audience-clean-16x9",
    "attachment://paperpipe-audience_clean-16x9",
    "paperpipe-audience-clean-16x9",
    "paperpipe-audience_clean-16x9",
}


def render_talk_pack_pptx_bytes(
    pack: TalkPack,
    *,
    slide_manifest: TalkPackSlideManifest,
    style_profile: str,
    template_attachment_refs: list[str] | None = None,
    key_number_lines: list[str] | None = None,
    slide_key_numbers: dict[str, list[str]] | None = None,
    slide_visual_assets: dict[str, list[dict[str, str]]] | None = None,
) -> bytes:
    pptx_bytes, _preview_images = render_talk_pack_deck_artifacts(
        pack,
        slide_manifest=slide_manifest,
        style_profile=style_profile,
        template_attachment_refs=template_attachment_refs,
        key_number_lines=key_number_lines,
        slide_key_numbers=slide_key_numbers,
        slide_visual_assets=slide_visual_assets,
    )
    return pptx_bytes


def render_talk_pack_deck_artifacts(
    pack: TalkPack,
    *,
    slide_manifest: TalkPackSlideManifest,
    style_profile: str,
    template_attachment_refs: list[str] | None = None,
    key_number_lines: list[str] | None = None,
    slide_key_numbers: dict[str, list[str]] | None = None,
    slide_visual_assets: dict[str, list[dict[str, str]]] | None = None,
) -> tuple[bytes, dict[str, bytes]]:
    node_bin, node_modules_dir = _resolve_talk_pack_pptx_runtime()
    builder_source = (repo_root() / "src" / "talk_packs" / "talk_pack_pptx_builder.mjs").resolve()
    if not builder_source.exists():
        raise ValueError(f"Talk Pack PPTX builder not found: {builder_source}")

    payload = {
        "talk_pack_id": pack.talk_pack_id,
        "paper_slug": pack.paper_slug,
        "deck_title": pack.title,
        "talk_mode": pack.talk_mode,
        "audience_profile": pack.audience_profile,
        "duration_minutes": pack.duration_minutes,
        "style_profile": style_profile,
        "template_attachment_refs": [
            ref for ref in (template_attachment_refs or []) if str(ref or "").strip()
        ],
        "template_variant": _resolve_template_variant(template_attachment_refs),
        "key_numbers": [line for line in (key_number_lines or []) if str(line or "").strip()],
        "slides": [
            {
                "slide_id": slide.slide_id,
                "order": slide.order,
                "slide_kind": slide.slide_kind,
                "section": slide.section,
                "title": slide.title,
                "primary_message": slide.primary_message,
                "speaker_priority": slide.speaker_priority,
                "time_budget_seconds": slide.time_budget_seconds,
                "claim_refs": slide.claim_refs,
                "key_number_refs": slide.key_number_refs,
                "evidence_refs": [
                    ref.model_dump(mode="json", exclude_none=True)
                    for ref in slide.evidence_refs
                ],
                "key_numbers": (slide_key_numbers or {}).get(slide.slide_id, []),
                "source_artifact_refs": slide.source_artifact_refs,
                "visual_refs": slide.visual_refs,
                "visual_layout": slide.visual_layout,
                "visual_labels": slide.visual_labels,
                "visual_assets": (slide_visual_assets or {}).get(slide.slide_id, []),
                "notes_focus": slide.notes_focus,
                "warnings": slide.warnings,
            }
            for slide in sorted(slide_manifest.slides, key=lambda item: item.order)
        ],
    }

    with tempfile.TemporaryDirectory(prefix="paperpipe_talk_pack_pptx_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        workdir = tmp_root / "build"
        workdir.mkdir(parents=True, exist_ok=True)
        _prepare_node_modules_link(workdir, node_modules_dir)
        (workdir / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")

        builder_path = workdir / builder_source.name
        shutil.copyfile(builder_source, builder_path)

        input_path = tmp_root / "talk_pack_input.json"
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        output_path = tmp_root / "output.pptx"
        preview_dir = tmp_root / "preview"

        completed = subprocess.run(
            [str(node_bin), str(builder_path), str(input_path), str(output_path), str(preview_dir)],
            cwd=workdir,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            details = stderr or stdout or "unknown error"
            raise ValueError(f"Talk Pack PPTX export failed: {details}")
        if not output_path.exists():
            raise ValueError("Talk Pack PPTX export did not produce output.pptx")
        preview_images = {
            path.name: path.read_bytes()
            for path in sorted(preview_dir.glob("slide-*.png"))
            if path.is_file()
        }
        return output_path.read_bytes(), preview_images


def talk_pack_pptx_runtime_available() -> bool:
    try:
        _resolve_talk_pack_pptx_runtime()
    except ValueError:
        return False
    return True


def _resolve_talk_pack_pptx_runtime() -> tuple[Path, Path]:
    node_bin_candidates = [
        os.getenv("PAPERPIPE_TALK_PACK_NODE_BIN", "").strip(),
        os.getenv("PAPERPIPE_WORKSPACE_NODE_BIN", "").strip(),
        str(_DEFAULT_CODEX_NODE_BIN),
    ]
    node_modules_candidates = [
        os.getenv("PAPERPIPE_TALK_PACK_NODE_MODULES_DIR", "").strip(),
        os.getenv("PAPERPIPE_WORKSPACE_NODE_MODULES_DIR", "").strip(),
        str(_DEFAULT_CODEX_NODE_MODULES_DIR),
    ]

    node_bin = _first_existing_file(node_bin_candidates)
    node_modules_dir = _first_existing_dir(node_modules_candidates)
    if node_bin is None or node_modules_dir is None:
        raise ValueError(
            "Talk Pack PPTX runtime is unavailable. "
            "Set PAPERPIPE_TALK_PACK_NODE_BIN and PAPERPIPE_TALK_PACK_NODE_MODULES_DIR."
        )
    artifact_tool_dir = node_modules_dir / "@oai" / "artifact-tool"
    if not artifact_tool_dir.exists():
        raise ValueError(
            "Talk Pack PPTX runtime is unavailable because @oai/artifact-tool is missing. "
            "Set PAPERPIPE_TALK_PACK_NODE_MODULES_DIR to a bundled workspace runtime node_modules path."
        )
    if _skia_canvas_package_dir(node_modules_dir) is None:
        raise ValueError(
            "Talk Pack PPTX runtime is unavailable because skia-canvas is missing. "
            "Set PAPERPIPE_TALK_PACK_NODE_MODULES_DIR to a node_modules path that includes skia-canvas."
        )
    return node_bin, node_modules_dir


def _first_existing_file(candidates: list[str]) -> Path | None:
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw).expanduser().resolve()
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _first_existing_dir(candidates: list[str]) -> Path | None:
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _prepare_node_modules_link(workdir: Path, node_modules_dir: Path) -> None:
    local_node_modules = workdir / "node_modules"
    local_node_modules.mkdir(parents=True, exist_ok=True)
    oai_link = local_node_modules / "@oai"
    if oai_link.exists() or oai_link.is_symlink():
        pass
    else:
        oai_link.symlink_to((node_modules_dir / "@oai").resolve(), target_is_directory=True)

    skia_canvas_link = local_node_modules / "skia-canvas"
    if skia_canvas_link.exists() or skia_canvas_link.is_symlink():
        return
    skia_canvas_source = _skia_canvas_package_dir(node_modules_dir)
    if skia_canvas_source is not None:
        skia_canvas_link.symlink_to(skia_canvas_source.resolve(), target_is_directory=True)


def _skia_canvas_package_dir(node_modules_dir: Path) -> Path | None:
    candidates = (
        node_modules_dir / "skia-canvas",
        node_modules_dir / "@oai" / "artifact-tool" / "node_modules" / "skia-canvas",
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _resolve_template_variant(template_attachment_refs: list[str] | None) -> str:
    normalized_refs = [str(ref or "").strip().lower() for ref in (template_attachment_refs or [])]
    if any(ref in _AUDIENCE_CLEAN_TEMPLATE_REFS for ref in normalized_refs):
        return "audience_clean"
    return "default"
