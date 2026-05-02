from __future__ import annotations

import mimetypes
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from src.image_evidence.service import (
    get_image_evidence_bundle,
    image_evidence_handoff_payload,
    image_evidence_list_response,
    image_evidence_response_payload,
    load_declared_image_evidence_derivative_artifact,
    register_image_evidence,
)
from src.schemas.image_evidence import (
    ImageEvidenceListResponse,
    ImageEvidenceRequest,
    ImageEvidenceResponse,
    ImageHandoffTarget,
    ImageViewState,
)


router = APIRouter(prefix="/image-evidence", tags=["image-evidence"])


def _safe_filename(value: str, *, fallback: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return safe_value or fallback


@router.post("/register", response_model=ImageEvidenceResponse)
def post_register_image_evidence(payload: ImageEvidenceRequest) -> ImageEvidenceResponse:
    try:
        return image_evidence_response_payload(register_image_evidence(request=payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=ImageEvidenceListResponse)
def list_image_evidence_route() -> ImageEvidenceListResponse:
    try:
        return image_evidence_list_response()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{image_evidence_id}", response_model=ImageEvidenceResponse)
def get_image_evidence_route(image_evidence_id: str) -> ImageEvidenceResponse:
    try:
        return image_evidence_response_payload(get_image_evidence_bundle(image_evidence_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{image_evidence_id}/view-state", response_model=ImageViewState)
def get_image_evidence_view_state_route(image_evidence_id: str) -> ImageViewState:
    try:
        result = get_image_evidence_bundle(image_evidence_id)
        if result.view_state is None:
            raise FileNotFoundError(f"Image Evidence view-state not found: image_evidence_id={image_evidence_id}")
        return result.view_state
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{image_evidence_id}/handoff", response_model=list[ImageHandoffTarget])
def get_image_evidence_handoff_route(image_evidence_id: str) -> list[ImageHandoffTarget]:
    try:
        result = get_image_evidence_bundle(image_evidence_id)
        if result.image_evidence.handoff_ref is None:
            raise FileNotFoundError(f"Image Evidence handoff not found: image_evidence_id={image_evidence_id}")
        return image_evidence_handoff_payload(result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{image_evidence_id}/derivatives/{artifact_subpath:path}", response_class=Response)
def get_image_evidence_derivative_route(image_evidence_id: str, artifact_subpath: str) -> Response:
    try:
        _, normalized_path, content = load_declared_image_evidence_derivative_artifact(
            image_evidence_id,
            artifact_subpath,
        )
        filename = _safe_filename(
            f"{image_evidence_id}_{normalized_path.rsplit('/', 1)[-1]}",
            fallback="image-evidence-derivative",
        )
        media_type = _guess_media_type(normalized_path)
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _guess_media_type(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"
