from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.protocol_cards.service import (
    get_protocol_card_bundle,
    get_protocol_version_item,
    protocol_card_list_response,
    protocol_card_response_payload,
    protocol_version_list_response,
    upsert_protocol_card,
)
from src.schemas.protocol_card import (
    ProtocolCardListResponse,
    ProtocolCardRequest,
    ProtocolCardResponse,
    ProtocolVersion,
    ProtocolVersionListResponse,
)


router = APIRouter(prefix="/protocol-cards", tags=["protocol-cards"])


@router.post("", response_model=ProtocolCardResponse)
def post_protocol_card(payload: ProtocolCardRequest) -> ProtocolCardResponse:
    try:
        return protocol_card_response_payload(upsert_protocol_card(request=payload))
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
