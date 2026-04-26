from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from src.config import load_config
from src.protocol_attachments.service import (
    build_protocol_card_draft_from_attachment,
    get_protocol_attachment_bundle,
    get_protocol_attachment_markdown_for_user_surface,
    get_protocol_attachment_source,
    protocol_attachment_draft_response_payload,
)
from src.protocol_cards.service import (
    build_protocol_card_draft_from_note,
    get_protocol_card_bundle,
    get_protocol_version_item,
    protocol_card_draft_response_payload,
    protocol_card_list_response,
    protocol_card_response_payload,
    protocol_version_list_response,
    upsert_protocol_card,
)
from src.schemas.artifact_generation_outcome import (
    ArtifactGenerationOutcome,
    ArtifactGenerationOutcomeWriteRequest,
)
from src.schemas.artifact_review_feedback import (
    ArtifactReviewFeedbackCase,
    ArtifactReviewFeedbackWriteRequest,
)
from src.schemas.protocol_attachment import (
    ProtocolAttachmentBundle,
    ProtocolAttachmentDraftRequest,
    ProtocolAttachmentDraftResponse,
)
from src.schemas.protocol_card import (
    ProtocolCardDraftRequest,
    ProtocolCardDraftResponse,
    ProtocolCardListResponse,
    ProtocolCardRequest,
    ProtocolCardResponse,
    ProtocolVersion,
    ProtocolVersionListResponse,
)
from src.services.artifact_generation_outcomes import append_artifact_generation_outcome
from src.services.artifact_review_feedback import append_artifact_review_feedback
from src.services.runtime_paths import artifacts_root, protocol_attachments_root


router = APIRouter(prefix="/protocol-cards", tags=["protocol-cards"])


def _resolve_vault_path() -> Path:
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail=f"Obsidian vault not found: {vault_path}")
    if not vault_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Obsidian vault path is not a directory: {vault_path}")
    return vault_path


def _resolve_protocol_attachment_max_bytes() -> int:
    raw = (
        os.getenv("LATTICE_MAX_PROTOCOL_ATTACHMENT_BYTES")
        or os.getenv("PAPERPIPE_MAX_PROTOCOL_ATTACHMENT_BYTES")
        or ""
    ).strip()
    if not raw:
        return 15 * 1024 * 1024
    try:
        return max(int(raw), 1)
    except ValueError:
        return 15 * 1024 * 1024


async def _read_upload_with_size_limit(file: UploadFile, *, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Protocol attachment exceeds the configured limit of {max_bytes} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=ProtocolCardResponse)
def post_protocol_card(payload: ProtocolCardRequest) -> ProtocolCardResponse:
    try:
        return protocol_card_response_payload(upsert_protocol_card(request=payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft-from-note", response_model=ProtocolCardDraftResponse)
def post_protocol_card_draft_from_note(payload: ProtocolCardDraftRequest) -> ProtocolCardDraftResponse:
    try:
        return protocol_card_draft_response_payload(
            build_protocol_card_draft_from_note(
                request=payload,
                vault_path=_resolve_vault_path(),
                artifacts_root=artifacts_root(),
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft-from-attachment", response_model=ProtocolAttachmentDraftResponse)
async def post_protocol_card_draft_from_attachment(
    file: UploadFile = File(...),
    note_slug: str | None = Form(None),
    paper_id: str | None = Form(None),
    run_id: str | None = Form(None),
    title: str | None = Form(None),
    purpose: str | None = Form(None),
) -> ProtocolAttachmentDraftResponse:
    filename = str(file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Choose a file to attach.")
    try:
        payload = await _read_upload_with_size_limit(
            file,
            max_bytes=_resolve_protocol_attachment_max_bytes(),
        )
    finally:
        await file.close()
    if not payload:
        raise HTTPException(status_code=400, detail="The selected attachment is empty.")

    try:
        return protocol_attachment_draft_response_payload(
            build_protocol_card_draft_from_attachment(
                request=ProtocolAttachmentDraftRequest(
                    filename=filename,
                    media_type=str(file.content_type or "").strip() or None,
                    note_slug=note_slug,
                    paper_id=paper_id,
                    run_id=run_id,
                    title=title,
                    purpose=purpose,
                ),
                content=payload,
                root=protocol_attachments_root(),
                vault_path=_resolve_vault_path() if note_slug else None,
                artifacts_root=artifacts_root() if note_slug else None,
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/attachments/{attachment_bundle_id}", response_model=ProtocolAttachmentBundle)
def get_protocol_attachment_route(attachment_bundle_id: str) -> ProtocolAttachmentBundle:
    try:
        return get_protocol_attachment_bundle(attachment_bundle_id, root=protocol_attachments_root())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/attachments/{attachment_bundle_id}/source")
def get_protocol_attachment_source_route(
    attachment_bundle_id: str,
    download: bool = Query(False),
) -> FileResponse:
    try:
        bundle, path = get_protocol_attachment_source(attachment_bundle_id, root=protocol_attachments_root())
        return FileResponse(
            path,
            media_type=bundle.media_type or "application/octet-stream",
            filename=bundle.source_filename,
            content_disposition_type="attachment" if download else "inline",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/attachments/{attachment_bundle_id}/extracted-markdown",
    response_class=PlainTextResponse,
)
def get_protocol_attachment_markdown_route(attachment_bundle_id: str) -> PlainTextResponse:
    try:
        return PlainTextResponse(
            get_protocol_attachment_markdown_for_user_surface(attachment_bundle_id, root=protocol_attachments_root())
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=ProtocolCardListResponse)
def list_protocol_cards_route() -> ProtocolCardListResponse:
    try:
        return protocol_card_list_response()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{protocol_id}", response_model=ProtocolCardResponse)
def get_protocol_card_route(protocol_id: str) -> ProtocolCardResponse:
    try:
        return protocol_card_response_payload(get_protocol_card_bundle(protocol_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{protocol_id}/markdown", response_class=PlainTextResponse)
def get_protocol_card_markdown_route(protocol_id: str) -> PlainTextResponse:
    try:
        return PlainTextResponse(get_protocol_card_bundle(protocol_id).markdown)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{protocol_id}/outcome")
def post_protocol_card_outcome(protocol_id: str, payload: ArtifactGenerationOutcomeWriteRequest):
    try:
        get_protocol_card_bundle(protocol_id)
        outcome = append_artifact_generation_outcome(
            ArtifactGenerationOutcome(
                artifact_type="protocol_card",
                artifact_id=protocol_id,
                **payload.model_dump(mode="python"),
            )
        )
        return {
            "status": "saved",
            "message": "Artifact generation outcome recorded successfully.",
            "outcome_id": outcome.outcome_id,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{protocol_id}/review")
def post_protocol_card_review(protocol_id: str, payload: ArtifactReviewFeedbackWriteRequest):
    try:
        get_protocol_card_bundle(protocol_id)
        feedback = append_artifact_review_feedback(
            ArtifactReviewFeedbackCase(
                artifact_type="protocol_card",
                artifact_id=protocol_id,
                **payload.model_dump(mode="python"),
            )
        )
        return {
            "status": "saved",
            "message": "Artifact review feedback recorded successfully.",
            "feedback_id": feedback.feedback_id,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{protocol_id}/versions", response_model=ProtocolVersionListResponse)
def list_protocol_card_versions_route(protocol_id: str) -> ProtocolVersionListResponse:
    try:
        return protocol_version_list_response(protocol_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{protocol_id}/versions/{version_id}", response_model=ProtocolVersion)
def get_protocol_card_version_route(protocol_id: str, version_id: str) -> ProtocolVersion:
    try:
        return get_protocol_version_item(protocol_id, version_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
