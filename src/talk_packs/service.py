from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from src.chart_packs.store import load_chart_pack_render
from src.image_evidence.service import load_declared_image_evidence_derivative_artifact
from src.schemas.talk_pack import (
    TalkPack,
    TalkPackListItem,
    TalkPackListResponse,
    TalkPackOutputKind,
    TalkPackOutputMember,
    TalkPackResponse,
    TalkPackSlideManifest,
)
from src.services.listing_resilience import load_available_items
from src.talk_packs.pptx_export import render_talk_pack_deck_artifacts
from src.talk_packs.store import (
    list_talk_pack_ids,
    load_talk_pack,
    load_talk_pack_artifact_bytes,
    load_talk_pack_artifact_json,
    load_talk_pack_artifact_text,
    save_talk_pack_artifact_bytes,
    save_talk_pack_bundle,
    talk_pack_dir,
)

logger = logging.getLogger(__name__)
_STALE_PREVIEW_SLIDE_RE = re.compile(r"slide-\d+\.png")


def persist_talk_pack_bundle(
    pack: TalkPack,
    *,
    text_artifacts: dict[str, str] | None = None,
    json_artifacts: dict[str, dict[str, object]] | None = None,
    binary_artifacts: dict[str, bytes] | None = None,
    root: Path | None = None,
) -> TalkPackResponse:
    save_talk_pack_bundle(
        pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )
    return talk_pack_response_payload(pack)


def get_talk_pack(talk_pack_id: str, *, root: Path | None = None) -> TalkPack:
    return load_talk_pack(talk_pack_id, root)


def render_talk_pack_deck_pptx(
    talk_pack_id: str,
    *,
    root: Path | None = None,
    chart_pack_root: Path | None = None,
    image_evidence_root: Path | None = None,
) -> TalkPackResponse:
    pack = load_talk_pack(talk_pack_id, root)
    slide_manifest_member = _require_output_member(pack, kind="slide_manifest", status="generated")
    key_numbers_member = _require_output_member(pack, kind="key_numbers", status="generated")
    deck_member = _require_output_member(pack, kind="deck_pptx")
    slide_manifest = _load_slide_manifest(pack, slide_manifest_member.path, root=root)
    if slide_manifest.talk_pack_id != pack.talk_pack_id:
        raise ValueError(
            "Talk Pack slide manifest talk_pack_id does not match owner manifest: "
            f"{slide_manifest.talk_pack_id} != {pack.talk_pack_id}"
        )
    if slide_manifest.paper_slug != pack.paper_slug:
        raise ValueError(
            "Talk Pack slide manifest paper_slug does not match owner manifest: "
            f"{slide_manifest.paper_slug} != {pack.paper_slug}"
        )
    _validate_slide_manifest_intent(pack, slide_manifest)

    key_numbers_text = load_talk_pack_artifact_text(pack.talk_pack_id, key_numbers_member.path, root)
    key_number_lookup, fallback_key_numbers = _extract_key_number_lookup(key_numbers_text)
    style_profile = _resolved_style_profile(pack, slide_manifest)
    template_attachment_refs = _resolved_template_attachment_refs(pack, slide_manifest)
    slide_key_numbers = _resolve_slide_key_numbers(slide_manifest, key_number_lookup)
    slide_visual_assets = _load_slide_visual_assets(
        slide_manifest,
        chart_pack_root=_effective_chart_pack_root(
            talk_pack_root=root,
            chart_pack_root=chart_pack_root,
        ),
        image_evidence_root=_effective_image_evidence_root(
            talk_pack_root=root,
            image_evidence_root=image_evidence_root,
        ),
    )
    pptx_bytes, preview_images = render_talk_pack_deck_artifacts(
        pack,
        slide_manifest=slide_manifest,
        style_profile=style_profile,
        template_attachment_refs=template_attachment_refs,
        key_number_lines=fallback_key_numbers,
        slide_key_numbers=slide_key_numbers,
        slide_visual_assets=slide_visual_assets,
    )
    text_artifacts, json_artifacts, binary_artifacts = _load_existing_bundle_payloads(pack, root=root)
    binary_artifacts[deck_member.path] = pptx_bytes

    updated_pack = pack.model_copy(deep=True)
    updated_pack.updated_at = datetime.now(timezone.utc)
    for member in updated_pack.output_members:
        if member.kind == "deck_pptx":
            member.status = "generated"
            break
    _refresh_deterministic_handoff_artifacts(
        updated_pack,
        slide_manifest=slide_manifest,
        slide_key_numbers=slide_key_numbers,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
    )

    save_talk_pack_bundle(
        updated_pack,
        text_artifacts=text_artifacts,
        json_artifacts=json_artifacts,
        binary_artifacts=binary_artifacts,
        root=root,
    )
    _replace_deck_preview_images(updated_pack.talk_pack_id, preview_images, root=root)
    return talk_pack_response_payload(updated_pack)


def load_declared_talk_pack_artifact(
    talk_pack_id: str,
    artifact_path: str,
    *,
    root: Path | None = None,
) -> tuple[TalkPack, str, bytes]:
    pack = load_talk_pack(talk_pack_id, root)
    normalized_path = _normalize_artifact_path(artifact_path)
    declared_paths = declared_talk_pack_artifact_paths(pack)
    if normalized_path not in declared_paths:
        raise FileNotFoundError(
            f"Talk Pack artifact is not declared for talk_pack_id={talk_pack_id}: {normalized_path}"
        )
    return pack, normalized_path, load_talk_pack_artifact_bytes(talk_pack_id, normalized_path, root)


def load_talk_pack_deck_preview(
    talk_pack_id: str,
    preview_filename: str,
    *,
    root: Path | None = None,
) -> tuple[TalkPack, str, bytes]:
    pack = load_talk_pack(talk_pack_id, root)
    _require_output_member(pack, kind="deck_pptx", status="generated")
    filename = _normalize_preview_filename(preview_filename)
    path = f"preview/{filename}"
    content = load_talk_pack_artifact_bytes(talk_pack_id, path, root)
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Talk Pack deck preview is not a PNG file: {filename}")
    return pack, path, content


def list_talk_pack_summaries(*, root: Path | None = None) -> list[TalkPack]:
    items = load_available_items(
        list_talk_pack_ids(root),
        lambda talk_pack_id: load_talk_pack(talk_pack_id, root),
        item_kind="talk pack",
        logger=logger,
    )
    return sorted(items, key=lambda item: (item.updated_at, item.talk_pack_id), reverse=True)


def talk_pack_response_payload(pack: TalkPack) -> TalkPackResponse:
    return TalkPackResponse(pack=pack)


def talk_pack_list_response(*, root: Path | None = None) -> TalkPackListResponse:
    items = [
        summarize_talk_pack(pack)
        for pack in list_talk_pack_summaries(root=root)
    ]
    return TalkPackListResponse(items=items, total=len(items))


def summarize_talk_pack(pack: TalkPack) -> TalkPackListItem:
    return TalkPackListItem(
        talk_pack_id=pack.talk_pack_id,
        paper_slug=pack.paper_slug,
        title=pack.title,
        updated_at=pack.updated_at,
        artifact_family=pack.artifact_family,
        canonical_status=pack.canonical_status,
        talk_mode=pack.talk_mode,
        selected_output_count=len(pack.selected_outputs),
        generated_output_count=_generated_output_count(pack.output_members),
        warning_count=len(pack.warnings),
        has_generation_request=True,
        regenerated_from_talk_pack_id=pack.regenerated_from_talk_pack_id,
    )


def _generated_output_count(members: list[TalkPackOutputMember]) -> int:
    return sum(1 for member in members if member.status == "generated")


def declared_talk_pack_artifact_paths(pack: TalkPack) -> set[str]:
    declared = {
        _normalize_artifact_path(member.path)
        for member in pack.output_members
        if member.status == "generated"
    }
    declared.update(_normalize_artifact_path(artifact.path) for artifact in pack.review_artifacts)
    return declared


def _normalize_artifact_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("artifact_path must be non-empty")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"artifact_path is invalid: {path}")
    return pure.as_posix()


def _normalize_preview_filename(filename: str) -> str:
    raw = str(filename or "").strip()
    if not _STALE_PREVIEW_SLIDE_RE.fullmatch(raw):
        raise ValueError(f"Talk Pack deck preview filename is invalid: {filename}")
    return raw


def _require_output_member(
    pack: TalkPack,
    *,
    kind: TalkPackOutputKind,
    status: str | None = None,
) -> TalkPackOutputMember:
    for member in pack.output_members:
        if member.kind != kind:
            continue
        if status is not None and member.status != status:
            raise ValueError(
                f"Talk Pack output member {kind} must be {status} before this operation: "
                f"{member.status}"
            )
        return member
    raise ValueError(f"Talk Pack is missing required output member: {kind}")


def _load_slide_manifest(pack: TalkPack, path: str, *, root: Path | None = None) -> TalkPackSlideManifest:
    try:
        payload = load_talk_pack_artifact_json(pack.talk_pack_id, path, root)
    except ValueError:
        raw = load_talk_pack_artifact_text(pack.talk_pack_id, path, root)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Talk Pack slide manifest is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Talk Pack slide manifest must deserialize to an object: {path}")
    return TalkPackSlideManifest(**payload)


def _validate_slide_manifest_intent(pack: TalkPack, slide_manifest: TalkPackSlideManifest) -> None:
    field_pairs = [
        ("talk_mode", slide_manifest.talk_mode, pack.talk_mode),
        ("audience_profile", slide_manifest.audience_profile, pack.audience_profile),
        ("duration_minutes", slide_manifest.duration_minutes, pack.duration_minutes),
    ]
    for field_name, manifest_value, owner_value in field_pairs:
        if manifest_value is not None and manifest_value != owner_value:
            raise ValueError(
                f"Talk Pack slide manifest {field_name} does not match owner manifest: "
                f"{manifest_value} != {owner_value}"
            )
    request_max_slides = pack.generation_request.max_slides
    if (
        slide_manifest.max_slides is not None
        and request_max_slides is not None
        and slide_manifest.max_slides != request_max_slides
    ):
        raise ValueError(
            "Talk Pack slide manifest max_slides does not match saved generation_request: "
            f"{slide_manifest.max_slides} != {request_max_slides}"
        )


def _remove_stale_deck_preview_images(talk_pack_id: str, *, root: Path | None = None) -> None:
    preview_dir = talk_pack_dir(talk_pack_id, root) / "preview"
    if not preview_dir.exists() or not preview_dir.is_dir():
        return
    for path in preview_dir.iterdir():
        if path.is_file() and _STALE_PREVIEW_SLIDE_RE.fullmatch(path.name):
            path.unlink()
    try:
        preview_dir.rmdir()
    except OSError:
        return


def _replace_deck_preview_images(
    talk_pack_id: str,
    preview_images: dict[str, bytes],
    *,
    root: Path | None = None,
) -> None:
    _remove_stale_deck_preview_images(talk_pack_id, root=root)
    for filename, content in sorted(preview_images.items()):
        if not _STALE_PREVIEW_SLIDE_RE.fullmatch(filename):
            raise ValueError(f"Talk Pack deck preview filename is invalid: {filename}")
        save_talk_pack_artifact_bytes(
            talk_pack_id,
            f"preview/{filename}",
            content,
            root,
        )


def _resolved_style_profile(pack: TalkPack, slide_manifest: TalkPackSlideManifest) -> str:
    manifest_value = slide_manifest.style_profile
    if manifest_value is not None and manifest_value != pack.style_profile:
        raise ValueError(
            "Talk Pack slide manifest style_profile does not match owner manifest: "
            f"{manifest_value} != {pack.style_profile}"
        )
    return manifest_value or pack.style_profile


def _resolved_template_attachment_refs(
    pack: TalkPack,
    slide_manifest: TalkPackSlideManifest,
) -> list[str]:
    manifest_values = slide_manifest.template_attachment_refs
    if manifest_values and manifest_values != pack.template_attachment_refs:
        raise ValueError(
            "Talk Pack slide manifest template_attachment_refs do not match owner manifest."
        )
    return manifest_values or pack.template_attachment_refs


def _load_existing_bundle_payloads(
    pack: TalkPack,
    *,
    root: Path | None = None,
) -> tuple[dict[str, str], dict[str, dict[str, object]], dict[str, bytes]]:
    text_artifacts: dict[str, str] = {}
    json_artifacts: dict[str, dict[str, object]] = {}
    binary_artifacts: dict[str, bytes] = {}
    generated_paths = [member.path for member in pack.output_members if member.status == "generated"]
    review_paths = [artifact.path for artifact in pack.review_artifacts]
    for path in generated_paths + review_paths:
        if path.endswith(".md"):
            text_artifacts[path] = load_talk_pack_artifact_text(pack.talk_pack_id, path, root)
        elif path.endswith(".json"):
            json_artifacts[path] = load_talk_pack_artifact_json(pack.talk_pack_id, path, root)
        else:
            binary_artifacts[path] = load_talk_pack_artifact_bytes(pack.talk_pack_id, path, root)
    return text_artifacts, json_artifacts, binary_artifacts


def _refresh_deterministic_handoff_artifacts(
    pack: TalkPack,
    *,
    slide_manifest: TalkPackSlideManifest,
    slide_key_numbers: dict[str, list[str]],
    text_artifacts: dict[str, str],
    json_artifacts: dict[str, dict[str, object]],
) -> None:
    speaker_script_path = _generated_output_member_path(pack, "speaker_script")
    if speaker_script_path is not None and speaker_script_path in text_artifacts:
        text_artifacts[speaker_script_path] = _build_speaker_script_markdown(
            pack,
            slide_manifest=slide_manifest,
            slide_key_numbers=slide_key_numbers,
        )

    presentation_review_path = _review_artifact_path(pack, "presentation_review")
    if presentation_review_path is not None and presentation_review_path in json_artifacts:
        json_artifacts[presentation_review_path] = _build_presentation_review(
            pack,
            slide_manifest=slide_manifest,
            speaker_script_generated=speaker_script_path is not None,
        )

    style_lint_path = _review_artifact_path(pack, "style_lint")
    if style_lint_path is not None and style_lint_path in json_artifacts:
        json_artifacts[style_lint_path] = _build_style_lint(
            pack,
            slide_manifest=slide_manifest,
            slide_key_numbers=slide_key_numbers,
        )


def _generated_output_member_path(pack: TalkPack, kind: str) -> str | None:
    for member in pack.output_members:
        if member.kind == kind and member.status == "generated":
            return member.path
    return None


def _review_artifact_path(pack: TalkPack, kind: str) -> str | None:
    for artifact in pack.review_artifacts:
        if artifact.kind == kind:
            return artifact.path
    return None


def _build_speaker_script_markdown(
    pack: TalkPack,
    *,
    slide_manifest: TalkPackSlideManifest,
    slide_key_numbers: dict[str, list[str]],
) -> str:
    lines = [
        "# Speaker Script",
        "",
        f"- Talk pack: `{pack.talk_pack_id}`",
        f"- Paper: `{pack.paper_slug}`",
        f"- Mode: `{pack.talk_mode}`",
        f"- Audience: `{pack.audience_profile}`",
        f"- Duration target: {pack.duration_minutes} min",
        "",
        "## Main Path",
        "",
    ]
    main_slides = [slide for slide in sorted(slide_manifest.slides, key=lambda item: item.order) if slide.slide_kind == "main"]
    backup_slides = [slide for slide in sorted(slide_manifest.slides, key=lambda item: item.order) if slide.slide_kind == "backup"]
    for slide in main_slides:
        lines.extend(_speaker_script_slide_lines(slide, slide_key_numbers.get(slide.slide_id, [])))
    if backup_slides:
        lines.extend(["## Backup Slides", ""])
        for slide in backup_slides:
            lines.extend(_speaker_script_slide_lines(slide, slide_key_numbers.get(slide.slide_id, [])))
    return "\n".join(lines).rstrip() + "\n"


def _speaker_script_slide_lines(slide, key_numbers: list[str]) -> list[str]:
    priority = _humanize_priority(slide.speaker_priority) or "not specified"
    time_budget = _humanize_seconds(slide.time_budget_seconds) or "not specified"
    lines = [
        f"### Slide {slide.order}: {slide.title}",
        "",
        f"- Primary message: {slide.primary_message}",
        f"- Presenter priority: {priority}",
        f"- Time budget: {time_budget}",
    ]
    if slide.notes_focus:
        lines.append("- Presenter focus:")
        lines.extend(f"  - {item}" for item in slide.notes_focus)
    else:
        lines.append("- Presenter focus: keep the slide anchored to the primary message.")
    if key_numbers:
        lines.append("- Key numbers to say carefully:")
        lines.extend(f"  - {item}" for item in key_numbers)
    if slide.visual_refs:
        lines.append("- Visuals to explain:")
        for index, visual_ref in enumerate(slide.visual_refs):
            label = slide.visual_labels[index] if index < len(slide.visual_labels) else visual_ref
            lines.append(f"  - {label}: `{visual_ref}`")
    if slide.claim_refs or slide.source_artifact_refs or slide.evidence_refs:
        lines.append("- Traceability:")
        if slide.claim_refs:
            lines.append(f"  - Claims: {', '.join(slide.claim_refs)}")
        if slide.evidence_refs:
            evidence_ids = [
                ref.evidence_id or ref.claim_id or ref.paper_slug
                for ref in slide.evidence_refs
            ]
            lines.append(f"  - Evidence refs: {', '.join(item for item in evidence_ids if item)}")
        if slide.source_artifact_refs:
            lines.append(f"  - Source artifacts: {', '.join(slide.source_artifact_refs)}")
    if slide.warnings:
        lines.append("- Guardrails:")
        lines.extend(f"  - {item}" for item in slide.warnings)
    lines.extend(["", "---", ""])
    return lines


def _build_presentation_review(
    pack: TalkPack,
    *,
    slide_manifest: TalkPackSlideManifest,
    speaker_script_generated: bool,
) -> dict[str, object]:
    missing_dependencies = _missing_required_outputs(pack)
    presenter_checks = [
        _review_check(
            "audience_fit",
            "presenter_view",
            "pass",
            "low",
            f"Talk mode `{pack.talk_mode}` and audience `{pack.audience_profile}` match the owner manifest.",
            ["talk_pack.json", "slide_manifest.json"],
        ),
        _time_fit_check(pack, slide_manifest),
        _narrative_flow_check(slide_manifest),
        _figure_explainability_check(slide_manifest),
        _qa_readiness_check(slide_manifest, speaker_script_generated),
    ]
    evaluator_checks = [
        _scientific_fidelity_check(slide_manifest),
        _evidence_honesty_check(slide_manifest),
        _slide_judgment_check(slide_manifest),
        _discussion_quality_check(slide_manifest),
        _seminar_readiness_check(missing_dependencies),
    ]
    presenter_status = _overall_status_for_checks(presenter_checks)
    evaluator_status = _overall_status_for_checks(evaluator_checks)
    overall_status = _overall_status_for_checks(
        [
            {"status": presenter_status},
            {"status": evaluator_status},
            *(
                [
                    {
                        "status": "fail",
                        "name": "missing_dependencies",
                    }
                ]
                if missing_dependencies
                else []
            ),
        ]
    )
    return {
        "schema_version": "draft",
        "workflow": "talk_pack_review",
        "talk_pack_id": pack.talk_pack_id,
        "paper_slug": pack.paper_slug,
        "generated_at": _utc_now_iso(),
        "overall_status": overall_status,
        "reason_codes": _reason_codes_for_checks([*presenter_checks, *evaluator_checks]),
        "selected_outputs": list(pack.selected_outputs),
        "required_outputs": list(pack.required_outputs),
        "missing_dependencies": missing_dependencies,
        "presenter_view": {
            "overall_status": presenter_status,
            "checks": presenter_checks,
        },
        "evaluator_view": {
            "overall_status": evaluator_status,
            "checks": evaluator_checks,
        },
        "warnings": _warnings_for_checks([*presenter_checks, *evaluator_checks]),
    }


def _build_style_lint(
    pack: TalkPack,
    *,
    slide_manifest: TalkPackSlideManifest,
    slide_key_numbers: dict[str, list[str]],
) -> dict[str, object]:
    findings = [
        _style_finding(
            "slide_density_high",
            "warn",
            "warn" if _dense_slide_orders(slide_manifest) else "pass",
            _dense_slide_detail(slide_manifest),
            ["slide_manifest.json", "deck.pptx"],
        ),
        _style_finding(
            "figure_takeaway_missing",
            "warn",
            "warn" if _visual_label_gap_orders(slide_manifest) else "pass",
            _visual_label_gap_detail(slide_manifest),
            ["slide_manifest.json", "deck.pptx"],
        ),
        _style_finding(
            "transition_language_missing",
            "warn",
            "warn" if _notes_focus_gap_orders(slide_manifest) else "pass",
            _notes_focus_gap_detail(slide_manifest),
            ["slide_manifest.json", "speaker_script.md"],
        ),
        _style_finding(
            "numeric_formatting_inconsistent",
            "nit",
            "warn" if _unresolved_key_number_orders(slide_manifest, slide_key_numbers) else "pass",
            _unresolved_key_number_detail(slide_manifest, slide_key_numbers),
            ["key_numbers.md", "slide_manifest.json"],
        ),
    ]
    return {
        "schema_version": "draft",
        "workflow": "talk_pack_style_lint",
        "talk_pack_id": pack.talk_pack_id,
        "paper_slug": pack.paper_slug,
        "generated_at": _utc_now_iso(),
        "overall_status": _overall_status_for_checks(findings),
        "selected_outputs": list(pack.selected_outputs),
        "findings": findings,
    }


def _review_check(
    name: str,
    perspective: str,
    status: str,
    severity: str,
    detail: str,
    target_artifacts: list[str],
    *,
    fixable_by_ai: bool = True,
) -> dict[str, object]:
    return {
        "name": name,
        "perspective": perspective,
        "status": status,
        "severity": severity,
        "detail": detail,
        "target_artifacts": target_artifacts,
        "fixable_by_ai": fixable_by_ai,
    }


def _style_finding(
    name: str,
    category: str,
    status: str,
    detail: str,
    target_artifacts: list[str],
    *,
    fixable_by_ai: bool = True,
) -> dict[str, object]:
    return {
        "name": name,
        "category": category,
        "status": status,
        "detail": detail,
        "target_artifacts": target_artifacts,
        "fixable_by_ai": fixable_by_ai,
    }


def _time_fit_check(pack: TalkPack, slide_manifest: TalkPackSlideManifest) -> dict[str, object]:
    main_slides = [slide for slide in slide_manifest.slides if slide.slide_kind == "main"]
    missing = [slide.order for slide in main_slides if slide.time_budget_seconds is None]
    total_seconds = sum(slide.time_budget_seconds or 0 for slide in main_slides)
    target_seconds = pack.duration_minutes * 60
    if missing:
        return _review_check(
            "time_fit",
            "presenter_view",
            "warn",
            "medium",
            f"Main slides without explicit time budgets: {_format_orders(missing)}.",
            ["slide_manifest.json", "speaker_script.md"],
        )
    if total_seconds > target_seconds:
        return _review_check(
            "time_fit",
            "presenter_view",
            "warn",
            "medium",
            f"Main-slide time budgets total {_humanize_seconds(total_seconds)}, above the {pack.duration_minutes} min target.",
            ["slide_manifest.json", "speaker_script.md"],
        )
    return _review_check(
        "time_fit",
        "presenter_view",
        "pass",
        "low",
        f"Main-slide time budgets total {_humanize_seconds(total_seconds)} within the {pack.duration_minutes} min target.",
        ["slide_manifest.json", "speaker_script.md"],
    )


def _narrative_flow_check(slide_manifest: TalkPackSlideManifest) -> dict[str, object]:
    sections = [str(slide.section or "").lower() for slide in slide_manifest.slides if slide.slide_kind == "main"]
    has_open = bool(sections) and sections[0] in {"opening", "context", "background"}
    has_close = any(section in {"discussion", "conclusion", "close"} for section in sections)
    status = "pass" if has_open and has_close else "warn"
    detail = "Main path has an opening/framing section and a discussion or closing section." if status == "pass" else "Main path is missing a clear opening or discussion/close section."
    return _review_check(
        "narrative_flow",
        "presenter_view",
        status,
        "medium" if status == "warn" else "low",
        detail,
        ["slide_manifest.json", "speaker_script.md"],
    )


def _figure_explainability_check(slide_manifest: TalkPackSlideManifest) -> dict[str, object]:
    gaps = _visual_label_gap_orders(slide_manifest)
    status = "warn" if gaps else "pass"
    detail = f"Visual-bearing slides missing audience-facing labels: {_format_orders(gaps)}." if gaps else "Visual-bearing slides include audience-facing labels or have no visuals."
    return _review_check(
        "figure_explainability",
        "presenter_view",
        status,
        "medium" if status == "warn" else "low",
        detail,
        ["slide_manifest.json", "deck.pptx"],
    )


def _qa_readiness_check(slide_manifest: TalkPackSlideManifest, speaker_script_generated: bool) -> dict[str, object]:
    has_discussion = any(
        str(slide.section or "").lower() == "discussion"
        for slide in slide_manifest.slides
        if slide.slide_kind == "main"
    )
    status = "pass" if has_discussion and speaker_script_generated else "warn"
    detail = "Discussion slide and generated speaker script are present." if status == "pass" else "Q&A readiness is shallow without both a discussion slide and generated speaker script."
    return _review_check(
        "qa_readiness",
        "presenter_view",
        status,
        "medium" if status == "warn" else "low",
        detail,
        ["slide_manifest.json", "speaker_script.md"],
    )


def _scientific_fidelity_check(slide_manifest: TalkPackSlideManifest) -> dict[str, object]:
    gaps = [
        slide.order
        for slide in slide_manifest.slides
        if slide.slide_kind == "main" and (not slide.claim_refs or not slide.source_artifact_refs)
    ]
    status = "fail" if gaps else "pass"
    detail = f"Main slides missing claim/source traceability: {_format_orders(gaps)}." if gaps else "All main slides carry claim and source-artifact traceability."
    return _review_check(
        "scientific_fidelity",
        "evaluator_view",
        status,
        "high" if status == "fail" else "low",
        detail,
        ["slide_manifest.json"],
    )


def _evidence_honesty_check(slide_manifest: TalkPackSlideManifest) -> dict[str, object]:
    claim_slides = [slide for slide in slide_manifest.slides if slide.slide_kind == "main" and slide.claim_refs]
    missing_evidence_refs = [slide.order for slide in claim_slides if not slide.evidence_refs]
    if missing_evidence_refs:
        return _review_check(
            "evidence_honesty",
            "evaluator_view",
            "warn",
            "medium",
            f"Claim-bearing slides without structured evidence_refs[]: {_format_orders(missing_evidence_refs)}; source refs remain available.",
            ["slide_manifest.json"],
        )
    return _review_check(
        "evidence_honesty",
        "evaluator_view",
        "pass",
        "low",
        "Claim-bearing slides include structured evidence refs.",
        ["slide_manifest.json"],
    )


def _slide_judgment_check(slide_manifest: TalkPackSlideManifest) -> dict[str, object]:
    crowded = [slide.order for slide in slide_manifest.slides if len(slide.visual_refs) > 2]
    status = "fail" if crowded else "pass"
    detail = f"Slides exceed the supported visual count: {_format_orders(crowded)}." if crowded else "Slides stay within the supported visual count."
    return _review_check(
        "slide_judgment",
        "evaluator_view",
        status,
        "high" if status == "fail" else "low",
        detail,
        ["slide_manifest.json", "deck.pptx"],
    )


def _discussion_quality_check(slide_manifest: TalkPackSlideManifest) -> dict[str, object]:
    discussion_slides = [
        slide for slide in slide_manifest.slides if str(slide.section or "").lower() == "discussion"
    ]
    status = "pass" if discussion_slides else "warn"
    detail = "A discussion slide is present." if status == "pass" else "No explicit discussion slide is present."
    return _review_check(
        "discussion_quality",
        "evaluator_view",
        status,
        "medium" if status == "warn" else "low",
        detail,
        ["slide_manifest.json"],
    )


def _seminar_readiness_check(missing_dependencies: list[str]) -> dict[str, object]:
    status = "fail" if missing_dependencies else "pass"
    detail = f"Missing required outputs: {', '.join(missing_dependencies)}." if missing_dependencies else "Required outputs are generated or explicitly represented."
    return _review_check(
        "seminar_readiness",
        "evaluator_view",
        status,
        "high" if status == "fail" else "low",
        detail,
        ["talk_pack.json"],
    )


def _missing_required_outputs(pack: TalkPack) -> list[str]:
    member_status_by_kind = {member.kind: member.status for member in pack.output_members}
    return [
        kind
        for kind in pack.required_outputs
        if member_status_by_kind.get(kind) != "generated"
    ]


def _dense_slide_orders(slide_manifest: TalkPackSlideManifest) -> list[int]:
    return [
        slide.order
        for slide in slide_manifest.slides
        if len(slide.title) > 140 or len(slide.primary_message) > 260
    ]


def _dense_slide_detail(slide_manifest: TalkPackSlideManifest) -> str:
    orders = _dense_slide_orders(slide_manifest)
    return f"Potentially dense slide text on slides: {_format_orders(orders)}." if orders else "Slide titles and primary messages stay within the current density heuristic."


def _visual_label_gap_orders(slide_manifest: TalkPackSlideManifest) -> list[int]:
    return [
        slide.order
        for slide in slide_manifest.slides
        if slide.visual_refs and len(slide.visual_labels) < len(slide.visual_refs)
    ]


def _visual_label_gap_detail(slide_manifest: TalkPackSlideManifest) -> str:
    orders = _visual_label_gap_orders(slide_manifest)
    return f"Visual refs without matching audience-facing labels on slides: {_format_orders(orders)}." if orders else "Visual refs have matching audience-facing labels where needed."


def _notes_focus_gap_orders(slide_manifest: TalkPackSlideManifest) -> list[int]:
    return [
        slide.order
        for slide in slide_manifest.slides
        if slide.slide_kind == "main" and not slide.notes_focus
    ]


def _notes_focus_gap_detail(slide_manifest: TalkPackSlideManifest) -> str:
    orders = _notes_focus_gap_orders(slide_manifest)
    return f"Main slides without notes_focus transition support: {_format_orders(orders)}." if orders else "Main slides carry presenter focus notes for transitions and caveats."


def _unresolved_key_number_orders(
    slide_manifest: TalkPackSlideManifest,
    slide_key_numbers: dict[str, list[str]],
) -> list[int]:
    return [
        slide.order
        for slide in slide_manifest.slides
        if slide.key_number_refs and not slide_key_numbers.get(slide.slide_id)
    ]


def _unresolved_key_number_detail(
    slide_manifest: TalkPackSlideManifest,
    slide_key_numbers: dict[str, list[str]],
) -> str:
    orders = _unresolved_key_number_orders(slide_manifest, slide_key_numbers)
    return f"Slides with key_number_refs but no resolved key-number text: {_format_orders(orders)}." if orders else "Slide key-number refs resolve to key-number text."


def _overall_status_for_checks(checks: list[dict[str, object]]) -> str:
    statuses = {str(check.get("status")) for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _reason_codes_for_checks(checks: list[dict[str, object]]) -> list[str]:
    return [
        str(check.get("name"))
        for check in checks
        if check.get("status") in {"warn", "fail"} and check.get("name")
    ]


def _warnings_for_checks(checks: list[dict[str, object]]) -> list[str]:
    return [
        str(check.get("detail"))
        for check in checks
        if check.get("status") == "warn" and check.get("detail")
    ]


def _humanize_seconds(seconds: int | None) -> str | None:
    if seconds is None or seconds <= 0:
        return None
    if seconds < 60:
        return f"{seconds} sec"
    minutes, remainder = divmod(seconds, 60)
    if remainder == 0:
        return f"{minutes} min"
    return f"{minutes}m {remainder}s"


def _humanize_priority(priority: str | None) -> str | None:
    if priority == "must_say":
        return "Must say"
    if priority == "nice_to_say":
        return "Nice to say"
    if priority == "skip_if_short_on_time":
        return "Skip if short on time"
    return priority


def _format_orders(orders: list[int]) -> str:
    return ", ".join(str(order) for order in orders) if orders else "none"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_key_number_lookup(markdown: str) -> tuple[dict[str, str], list[str]]:
    lines = markdown.splitlines()
    bullet_lines: list[str] = []
    table_lines: list[str] = []
    key_lookup: dict[str, str] = {}
    table_header: list[str] | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            bullet = line[2:].strip()
            bullet_lines.append(bullet)
            key, value = _split_key_number_entry(bullet)
            if key is not None:
                _register_key_number_lookup_entry(key_lookup, key, value)
            continue
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(not cell for cell in cells):
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        normalized_header = [cell.lower() for cell in cells]
        if "label" in normalized_header and (
            "display_value" in normalized_header or "exact_value" in normalized_header
        ):
            table_header = normalized_header
            continue
        if table_header is None or len(cells) != len(table_header):
            continue
        row = dict(zip(table_header, cells, strict=False))
        key_number_id = row.get("key_number_id", "").strip()
        label = row.get("label", "").strip()
        display_value = row.get("display_value", "").strip()
        exact_value = row.get("exact_value", "").strip()
        unit = row.get("unit", "").strip()
        if not label:
            continue
        value = display_value or exact_value
        if unit and value and unit not in value:
            value = f"{value} {unit}"
        entry = ": ".join(part for part in (label, value) if part)
        table_lines.append(entry)
        if key_number_id:
            _register_key_number_lookup_entry(key_lookup, key_number_id, entry)
        if label:
            _register_key_number_lookup_entry(key_lookup, label, entry)
    combined = []
    seen: set[str] = set()
    for item in bullet_lines + table_lines:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        combined.append(normalized)
        seen.add(normalized)
    return key_lookup, combined[:3]


def _split_key_number_entry(entry: str) -> tuple[str | None, str]:
    text = str(entry or "").strip()
    if not text:
        return None, text
    if ":" not in text:
        return None, text
    key, remainder = text.split(":", 1)
    normalized_key = key.strip()
    normalized_value = text.strip()
    if not normalized_key:
        return None, normalized_value
    return normalized_key, normalized_value


def _register_key_number_lookup_entry(
    key_lookup: dict[str, str],
    key: str,
    value: str,
) -> None:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return
    raw_key = str(key or "").strip()
    if not raw_key:
        return
    for candidate in {raw_key, _normalize_key_number_key(raw_key)}:
        if candidate and candidate not in key_lookup:
            key_lookup[candidate] = normalized_value


def _normalize_key_number_key(key: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(key or "").strip()).strip("_").lower()
    return normalized


def _resolve_slide_key_numbers(
    slide_manifest: TalkPackSlideManifest,
    key_number_lookup: dict[str, str],
) -> dict[str, list[str]]:
    resolved: dict[str, list[str]] = {}
    for slide in slide_manifest.slides:
        if not slide.key_number_refs:
            continue
        lines: list[str] = []
        seen: set[str] = set()
        for ref in slide.key_number_refs:
            value = key_number_lookup.get(ref) or key_number_lookup.get(_normalize_key_number_key(ref))
            if value is None:
                continue
            if value in seen:
                continue
            lines.append(value)
            seen.add(value)
        if lines:
            resolved[slide.slide_id] = lines[:3]
    return resolved


def _load_slide_visual_assets(
    slide_manifest: TalkPackSlideManifest,
    *,
    chart_pack_root: Path | None = None,
    image_evidence_root: Path | None = None,
) -> dict[str, list[dict[str, str]]]:
    assets_by_slide: dict[str, list[dict[str, str]]] = {}
    for slide in slide_manifest.slides:
        if len(slide.visual_refs) > 2:
            raise ValueError(
                "Talk Pack PPTX export currently supports at most two visual_refs per slide: "
                f"{slide.slide_id}"
            )
        assets: list[dict[str, str]] = []
        for visual_ref in slide.visual_refs:
            assets.append(
                _resolve_slide_visual_ref(
                    visual_ref,
                    chart_pack_root=chart_pack_root,
                    image_evidence_root=image_evidence_root,
                )
            )
        if assets:
            assets_by_slide[slide.slide_id] = assets
    return assets_by_slide


def _resolve_slide_visual_ref(
    visual_ref: str,
    *,
    chart_pack_root: Path | None = None,
    image_evidence_root: Path | None = None,
) -> dict[str, str]:
    raw = str(visual_ref or "").strip()
    parts = raw.split(":")
    if not parts:
        raise ValueError(
            "Talk Pack visual_refs currently support only "
            "'chart_pack_render:<chart_pack_id>:<chart_id>[:svg]' or "
            "'image_evidence_derivative:<image_evidence_id>:<artifact_subpath>' entries."
        )
    if parts[0] == "chart_pack_render":
        if len(parts) not in {3, 4}:
            raise ValueError(
                "Talk Pack visual_refs currently support only "
                "'chart_pack_render:<chart_pack_id>:<chart_id>[:svg]' or "
                "'image_evidence_derivative:<image_evidence_id>:<artifact_subpath>' entries."
            )
        _, chart_pack_id, chart_id, *extension_parts = parts
        extension = extension_parts[0] if extension_parts else "svg"
        if extension != "svg":
            raise ValueError(
                "Talk Pack visual_refs currently support only SVG chart-pack renders: "
                f"{visual_ref}"
            )
        svg_text = load_chart_pack_render(chart_pack_id, chart_id, extension=extension, root=chart_pack_root)
        return {
            "label": f"{chart_pack_id}/{chart_id}.{extension}",
            "alt": f"{chart_pack_id} {chart_id} visual context",
            "data_url": _svg_text_to_data_url(svg_text),
        }
    if parts[0] == "image_evidence_derivative" and len(parts) == 3:
        _, image_evidence_id, artifact_subpath = parts
        _, normalized_path, content = load_declared_image_evidence_derivative_artifact(
            image_evidence_id,
            _normalize_image_evidence_visual_subpath(artifact_subpath),
            root=image_evidence_root,
        )
        media_type = _guess_visual_media_type(normalized_path)
        return {
            "label": f"{image_evidence_id}/{normalized_path.rsplit('/', 1)[-1]}",
            "alt": f"{image_evidence_id} derivative visual context",
            "data_url": _binary_bytes_to_data_url(content, media_type),
        }
    raise ValueError(
        "Talk Pack visual_refs currently support only "
        "'chart_pack_render:<chart_pack_id>:<chart_id>[:svg]' or "
        "'image_evidence_derivative:<image_evidence_id>:<artifact_subpath>' entries."
    )


def _normalize_image_evidence_visual_subpath(path: str) -> str:
    normalized = str(path or "").strip()
    if normalized.startswith("derivatives/"):
        return normalized.removeprefix("derivatives/")
    return normalized


def _guess_visual_media_type(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    if guessed is None or not guessed.startswith("image/"):
        raise ValueError(
            "Talk Pack image-evidence visual_refs must resolve to an image derivative: "
            f"{path}"
        )
    return guessed


def _binary_bytes_to_data_url(content: bytes, media_type: str) -> str:
    payload = base64.b64encode(content).decode("ascii")
    return f"data:{media_type};base64,{payload}"


def _svg_text_to_data_url(svg_text: str) -> str:
    payload = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


def _effective_chart_pack_root(
    *,
    talk_pack_root: Path | None,
    chart_pack_root: Path | None,
) -> Path | None:
    if chart_pack_root is not None:
        return chart_pack_root
    if talk_pack_root is None:
        return None
    sibling_root = talk_pack_root.expanduser().resolve().parent / "chart_packs"
    if sibling_root.exists():
        return sibling_root
    return None


def _effective_image_evidence_root(
    *,
    talk_pack_root: Path | None,
    image_evidence_root: Path | None,
) -> Path | None:
    if image_evidence_root is not None:
        return image_evidence_root
    if talk_pack_root is None:
        return None
    sibling_root = talk_pack_root.expanduser().resolve().parent / "image_evidence"
    if sibling_root.exists():
        return sibling_root
    return None
