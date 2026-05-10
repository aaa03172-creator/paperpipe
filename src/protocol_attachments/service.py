from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
import importlib.util
import json
from pathlib import Path
import re

from src.protocol_attachments.store import (
    load_protocol_attachment_bundle,
    load_protocol_attachment_markdown,
    load_protocol_attachment_source_path,
    save_protocol_attachment_bundle,
)
from src.protocol_cards.service import build_protocol_card_draft_from_note
from src.schemas.protocol_attachment import (
    ProtocolAttachmentBundle,
    ProtocolAttachmentDraftRequest,
    ProtocolAttachmentDraftResponse,
    ProtocolAttachmentWarning,
)
from src.schemas.protocol_card import ProtocolCardDraftRequest, ProtocolCardRequest, ProtocolDraftSourceSummary
from src.services.event_log import sanitize_event_payload_for_log, sanitize_event_text_for_log


_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9._-]+")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")


@dataclass(frozen=True)
class ProtocolAttachmentDraftResult:
    attachment_bundle: ProtocolAttachmentBundle
    draft: ProtocolCardRequest
    paper_source_summary: ProtocolDraftSourceSummary | None
    warnings: list[ProtocolAttachmentWarning]


def build_protocol_card_draft_from_attachment(
    *,
    request: ProtocolAttachmentDraftRequest,
    content: bytes,
    root: Path | None = None,
    vault_path: Path | None = None,
    artifacts_root: Path | None = None,
    now: datetime | None = None,
) -> ProtocolAttachmentDraftResult:
    created_at = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    safe_request = _sanitize_attachment_request_for_user_surface(request)
    content_sha1 = sha1(content).hexdigest()
    attachment_bundle_id = _new_attachment_bundle_id(safe_request, content_sha1)
    safe_filename = _sanitize_filename(safe_request.filename)

    extracted_markdown, extraction_engine, attachment_warnings = _extract_attachment_markdown(
        filename=request.filename,
        media_type=request.media_type,
        content=content,
        attachment_bundle_id=attachment_bundle_id,
    )
    safe_extracted_markdown = _sanitize_attachment_text_for_user_surface(extracted_markdown)
    bundle = ProtocolAttachmentBundle(
        attachment_bundle_id=attachment_bundle_id,
        title=safe_request.title or Path(safe_request.filename).stem or attachment_bundle_id,
        source_filename=safe_request.filename,
        media_type=safe_request.media_type,
        byte_size=len(content),
        sha1=content_sha1,
        note_slug=safe_request.note_slug,
        paper_id=safe_request.paper_id,
        run_id=safe_request.run_id,
        created_at=created_at,
        source_ref={"kind": "source_file", "path": f"source/{safe_filename}"},
        extracted_markdown_ref=(
            {"kind": "extracted_markdown", "path": "extracted.md"}
            if extracted_markdown
            else None
        ),
        extraction_engine=extraction_engine,
        extraction_status="succeeded" if extracted_markdown else "failed",
        extracted_markdown_excerpt=_excerpt(safe_extracted_markdown, max_chars=1600) if safe_extracted_markdown else None,
        warnings=attachment_warnings,
    )
    save_protocol_attachment_bundle(
        bundle,
        source_bytes=content,
        extracted_markdown=extracted_markdown,
        root=root,
    )

    paper_source_summary: ProtocolDraftSourceSummary | None = None
    merged_warnings = [warning.model_copy(deep=True) for warning in attachment_warnings]
    if request.note_slug is not None:
        if vault_path is None:
            raise ValueError("vault_path is required when note_slug is provided for attachment drafting")
        note_result = build_protocol_card_draft_from_note(
            request=ProtocolCardDraftRequest(
                note_slug=safe_request.note_slug or request.note_slug,
                paper_id=safe_request.paper_id,
                run_id=safe_request.run_id,
            ),
            vault_path=vault_path,
            artifacts_root=artifacts_root,
        )
        paper_source_summary = note_result.source_summary
        merged_warnings.extend(
            [
                ProtocolAttachmentWarning(code=warning.code, message=warning.message)
                for warning in note_result.warnings
            ]
        )
        draft = _merge_note_draft_with_attachment(
            note_draft=note_result.draft,
            attachment_bundle=bundle,
            attachment_markdown=safe_extracted_markdown,
            request=safe_request,
        )
    else:
        draft = _draft_from_attachment_only(
            attachment_bundle=bundle,
            attachment_markdown=safe_extracted_markdown,
            request=safe_request,
        )
    draft = _sanitize_protocol_card_request_for_user_surface(draft)

    return ProtocolAttachmentDraftResult(
        attachment_bundle=_sanitize_protocol_attachment_bundle_for_user_surface(bundle),
        draft=draft,
        paper_source_summary=paper_source_summary,
        warnings=_dedupe_warnings(merged_warnings),
    )


def get_protocol_attachment_bundle(attachment_bundle_id: str, *, root: Path | None = None) -> ProtocolAttachmentBundle:
    return _sanitize_protocol_attachment_bundle_for_user_surface(
        load_protocol_attachment_bundle(attachment_bundle_id, root)
    )


def get_protocol_attachment_markdown(attachment_bundle_id: str, *, root: Path | None = None) -> str:
    return load_protocol_attachment_markdown(attachment_bundle_id, root)


def get_protocol_attachment_markdown_for_user_surface(attachment_bundle_id: str, *, root: Path | None = None) -> str:
    return _sanitize_attachment_text_for_user_surface(load_protocol_attachment_markdown(attachment_bundle_id, root)) or ""


def get_protocol_attachment_source(attachment_bundle_id: str, *, root: Path | None = None) -> tuple[ProtocolAttachmentBundle, Path]:
    bundle, path = load_protocol_attachment_source_path(attachment_bundle_id, root)
    return _sanitize_protocol_attachment_bundle_for_user_surface(bundle), path


def protocol_attachment_draft_response_payload(
    result: ProtocolAttachmentDraftResult,
) -> ProtocolAttachmentDraftResponse:
    return ProtocolAttachmentDraftResponse(
        attachment_bundle=_sanitize_protocol_attachment_bundle_for_user_surface(result.attachment_bundle),
        draft=_sanitize_protocol_card_request_for_user_surface(result.draft),
        paper_source_summary=result.paper_source_summary,
        warnings=result.warnings,
    )


def _sanitize_attachment_text_for_user_surface(text: str | None) -> str | None:
    return sanitize_event_text_for_log(text)


def _sanitize_attachment_request_for_user_surface(
    request: ProtocolAttachmentDraftRequest,
) -> ProtocolAttachmentDraftRequest:
    filename = _display_filename_for_user_surface(request.filename)
    return request.model_copy(
        update={
            "filename": filename,
            "media_type": sanitize_event_text_for_log(request.media_type),
            "note_slug": sanitize_event_text_for_log(request.note_slug),
            "paper_id": sanitize_event_text_for_log(request.paper_id),
            "run_id": sanitize_event_text_for_log(request.run_id),
            "title": sanitize_event_text_for_log(request.title),
            "purpose": sanitize_event_text_for_log(request.purpose),
        }
    )


def _display_filename_for_user_surface(filename: str) -> str:
    basename = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip() or "attachment"
    return sanitize_event_text_for_log(basename) or "attachment"


def _sanitize_protocol_card_request_for_user_surface(draft: ProtocolCardRequest) -> ProtocolCardRequest:
    payload = sanitize_event_payload_for_log(draft.model_dump(mode="python"))
    return ProtocolCardRequest.model_validate(payload)


def _sanitize_protocol_attachment_bundle_for_user_surface(
    bundle: ProtocolAttachmentBundle,
) -> ProtocolAttachmentBundle:
    updates = {
        "title": sanitize_event_text_for_log(bundle.title),
        "source_filename": _display_filename_for_user_surface(bundle.source_filename),
        "media_type": sanitize_event_text_for_log(bundle.media_type),
        "note_slug": sanitize_event_text_for_log(bundle.note_slug),
        "paper_id": sanitize_event_text_for_log(bundle.paper_id),
        "run_id": sanitize_event_text_for_log(bundle.run_id),
        "extraction_engine": sanitize_event_text_for_log(bundle.extraction_engine),
        "extracted_markdown_excerpt": sanitize_event_text_for_log(bundle.extracted_markdown_excerpt),
        "source_ref": bundle.source_ref.model_copy(
            update={"path": sanitize_event_text_for_log(bundle.source_ref.path) or bundle.source_ref.path}
        ),
        "extracted_markdown_ref": (
            bundle.extracted_markdown_ref.model_copy(
                update={
                    "path": sanitize_event_text_for_log(bundle.extracted_markdown_ref.path)
                    or bundle.extracted_markdown_ref.path
                }
            )
            if bundle.extracted_markdown_ref is not None
            else None
        ),
        "warnings": [
            warning.model_copy(
                update={
                    "code": sanitize_event_text_for_log(warning.code) or warning.code,
                    "message": sanitize_event_text_for_log(warning.message) or warning.message,
                }
            )
            for warning in bundle.warnings
        ],
    }
    return bundle.model_copy(update=updates)


def _new_attachment_bundle_id(request: ProtocolAttachmentDraftRequest, content_sha1: str) -> str:
    payload = request.model_dump(mode="json", exclude_none=True)
    digest = sha1(
        json.dumps(
            {"request": payload, "content_sha1": content_sha1},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"protatt_{digest}"


def _sanitize_filename(filename: str) -> str:
    path = Path(filename)
    stem = _NON_ALNUM_RE.sub("_", path.stem).strip("._") or "attachment"
    suffix = _NON_ALNUM_RE.sub("", path.suffix)[:16]
    return f"{stem}{suffix}" if suffix.startswith(".") else f"{stem}{suffix}"


def _extract_attachment_markdown(
    *,
    filename: str,
    media_type: str | None,
    content: bytes,
    attachment_bundle_id: str,
) -> tuple[str | None, str | None, list[ProtocolAttachmentWarning]]:
    warnings: list[ProtocolAttachmentWarning] = []
    suffix = Path(filename).suffix.lower()
    if _is_plain_text_attachment(suffix=suffix, media_type=media_type):
        try:
            text = content.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace").strip()
            warnings.append(
                ProtocolAttachmentWarning(
                    code="TEXT_DECODE_REPLACED",
                    message="Attachment text required unicode replacement during decode; review extracted markdown for corruption.",
                )
            )
        if not text:
            warnings.append(
                ProtocolAttachmentWarning(
                    code="ATTACHMENT_TEXT_EMPTY",
                    message="Attachment text was empty after decode; the draft is a placeholder around the uploaded raw source bundle.",
                )
            )
            return None, "plain_text", warnings
        return text, "plain_text", warnings

    if importlib.util.find_spec("markitdown") is not None:
        try:
            from markitdown import MarkItDown  # type: ignore

            temp_path = Path.cwd() / ".tmp" / f"{attachment_bundle_id}{suffix or '.bin'}"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(content)
            try:
                text = str(MarkItDown().convert(str(temp_path)).text_content or "").strip()
            finally:
                if temp_path.exists():
                    temp_path.unlink()
            if text:
                return text, "markitdown", warnings
        except Exception:
            warnings.append(
                ProtocolAttachmentWarning(
                    code="MARKITDOWN_CONVERSION_FAILED",
                    message="Automatic document conversion failed; the uploaded raw source bundle was preserved for manual review.",
                )
            )

    warnings.append(
        ProtocolAttachmentWarning(
            code="ATTACHMENT_EXTRACTION_UNAVAILABLE",
            message=(
                "Automatic text extraction is unavailable for this attachment type in the current runtime. "
                "The raw source bundle was saved, but review should use the uploaded file directly before saving downstream."
            ),
        )
    )
    return None, None, warnings


def _is_plain_text_attachment(*, suffix: str, media_type: str | None) -> bool:
    if suffix in {".md", ".markdown", ".txt", ".text", ".csv", ".tsv", ".json", ".yaml", ".yml"}:
        return True
    media = str(media_type or "").strip().lower()
    return media.startswith("text/")


def _draft_from_attachment_only(
    *,
    attachment_bundle: ProtocolAttachmentBundle,
    attachment_markdown: str | None,
    request: ProtocolAttachmentDraftRequest,
) -> ProtocolCardRequest:
    content_snapshot = attachment_markdown or _attachment_placeholder_text(attachment_bundle)
    return ProtocolCardRequest(
        title=request.title or f"{Path(request.filename).stem} protocol draft",
        purpose=request.purpose or _first_meaningful_sentence(attachment_markdown) or f"Review external protocol material from {request.filename}.",
        context=(
            f"Protocol draft built from uploaded attachment bundle {attachment_bundle.attachment_bundle_id}. "
            "Review the extracted text and raw source before saving."
        ),
        source_kind="internal_adaptation",
        linked_paper_ids=[request.paper_id] if request.paper_id else [],
        linked_note_slugs=[request.note_slug] if request.note_slug else [],
        validation_status="unreviewed",
        versions=[
            {
                "version_number": 1,
                "key_steps_summary": _extract_key_steps(content_snapshot),
                "materials": [],
                "equipment": [],
                "critical_conditions": [],
                "readouts": [],
                "cautions": [],
                "content_snapshot": content_snapshot,
                "change_reason": "Initial attachment-derived protocol draft created from uploaded raw source.",
                "status": "draft",
                "created_by": "protocol_attachment_ingest",
                "source_refs": [],
                "note": f"Attachment bundle: {attachment_bundle.attachment_bundle_id} ({attachment_bundle.source_filename})",
            }
        ],
    )


def _merge_note_draft_with_attachment(
    *,
    note_draft: ProtocolCardRequest,
    attachment_bundle: ProtocolAttachmentBundle,
    attachment_markdown: str | None,
    request: ProtocolAttachmentDraftRequest,
) -> ProtocolCardRequest:
    merged = note_draft.model_copy(deep=True)
    version = merged.versions[0].model_copy(deep=True)
    attachment_block = _attachment_markdown_block(attachment_bundle, attachment_markdown)
    version.content_snapshot = "\n\n".join(
        part.strip()
        for part in [version.content_snapshot, attachment_block]
        if str(part or "").strip()
    ).strip()
    version.key_steps_summary = _dedupe_strings(
        list(version.key_steps_summary) + _extract_key_steps(attachment_markdown or "")
    )
    version.note = "\n".join(
        part
        for part in [
            str(version.note or "").strip(),
            f"Attachment bundle: {attachment_bundle.attachment_bundle_id} ({attachment_bundle.source_filename})",
        ]
        if part
    )

    merged.source_kind = "mixed"
    merged.title = request.title or merged.title
    merged.purpose = request.purpose or merged.purpose
    merged.context = (
        f"{str(merged.context or '').strip()} Augmented with uploaded attachment bundle "
        f"{attachment_bundle.attachment_bundle_id}."
    ).strip()
    if request.paper_id and request.paper_id not in merged.linked_paper_ids:
        merged.linked_paper_ids = [*merged.linked_paper_ids, request.paper_id]
    if request.note_slug and request.note_slug not in merged.linked_note_slugs:
        merged.linked_note_slugs = [*merged.linked_note_slugs, request.note_slug]
    merged.versions = [version]
    return merged


def _attachment_markdown_block(
    attachment_bundle: ProtocolAttachmentBundle,
    attachment_markdown: str | None,
) -> str:
    heading = f"## Attached Material: {attachment_bundle.source_filename}"
    body = attachment_markdown or _attachment_placeholder_text(attachment_bundle)
    return f"{heading}\n{body}".strip()


def _attachment_placeholder_text(attachment_bundle: ProtocolAttachmentBundle) -> str:
    return (
        f"Uploaded attachment bundle `{attachment_bundle.attachment_bundle_id}` was preserved as raw source "
        f"for `{attachment_bundle.source_filename}`, but automatic text extraction is unavailable in the current runtime."
    )


def _extract_key_steps(content_snapshot: str, *, max_items: int = 6) -> list[str]:
    steps: list[str] = []
    for raw_line in content_snapshot.splitlines():
        match = _LIST_ITEM_RE.match(raw_line)
        candidate = match.group(1).strip() if match else ""
        if candidate and candidate not in steps:
            steps.append(candidate)
        if len(steps) >= max_items:
            return steps

    sentence_candidates = re.split(r"(?:\.\s+|\n+)", content_snapshot)
    for sentence in sentence_candidates:
        normalized = " ".join(sentence.strip().split())
        if len(normalized) < 20:
            continue
        if normalized not in steps:
            steps.append(normalized)
        if len(steps) >= max_items:
            break
    return steps


def _first_meaningful_sentence(text: str | None) -> str | None:
    for sentence in re.split(r"(?:\.\s+|\n+)", str(text or "")):
        normalized = " ".join(sentence.strip().split())
        if len(normalized) >= 24 and not normalized.startswith("#"):
            return normalized
    return None


def _dedupe_strings(values: list[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            items.append(text)
            seen.add(text)
    return items


def _dedupe_warnings(warnings: list[ProtocolAttachmentWarning]) -> list[ProtocolAttachmentWarning]:
    deduped: list[ProtocolAttachmentWarning] = []
    seen: set[tuple[str, str]] = set()
    for warning in warnings:
        key = (warning.code, warning.message)
        if key not in seen:
            deduped.append(warning)
            seen.add(key)
    return deduped


def _excerpt(text: str, *, max_chars: int) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"
