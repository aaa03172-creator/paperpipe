from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.image_evidence.service import (
    get_image_evidence_bundle,
    image_evidence_handoff_payload,
    image_evidence_list_response,
    image_evidence_response_payload,
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
