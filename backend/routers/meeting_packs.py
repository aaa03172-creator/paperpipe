from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from src.config import load_config
from src.meeting_packs.service import (
    generate_meeting_pack,
    get_meeting_pack,
    get_meeting_pack_trace,
    list_meeting_packs,
    regenerate_meeting_pack,
    rerender_meeting_pack,
    validate_meeting_pack,
)
from src.schemas.meeting_pack import (
    MeetingPackGenerateRequest,
    MeetingPackListResponse,
    MeetingPackResponse,
    MeetingPackTraceResponse,
    MeetingPackValidationResponse,
)


router = APIRouter(prefix="/meeting-packs", tags=["meeting-packs"])


def _resolve_vault_path() -> Path:
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail=f"Obsidian vault not found: {vault_path}")
    if not vault_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Obsidian vault path is not a directory: {vault_path}")
    return vault_path


def _resolve_vault_path_if_available() -> Path | None:
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    if not vault_path.exists() or not vault_path.is_dir():
        return None
    return vault_path


@router.post("/generate", response_model=MeetingPackResponse)
def post_generate_meeting_pack(payload: MeetingPackGenerateRequest) -> MeetingPackResponse:
    try:
        return generate_meeting_pack(
            request=payload,
            vault_path=_resolve_vault_path(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=MeetingPackListResponse)
def list_meeting_packs_route() -> MeetingPackListResponse:
    try:
        return list_meeting_packs()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{pack_id}", response_model=MeetingPackResponse)
def get_meeting_pack_route(pack_id: str) -> MeetingPackResponse:
    try:
        return get_meeting_pack(pack_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{pack_id}/trace", response_model=MeetingPackTraceResponse)
def get_meeting_pack_trace_route(pack_id: str) -> MeetingPackTraceResponse:
    try:
        return get_meeting_pack_trace(pack_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{pack_id}/validate", response_model=MeetingPackValidationResponse)
def validate_meeting_pack_route(pack_id: str) -> MeetingPackValidationResponse:
    try:
        return validate_meeting_pack(
            pack_id,
            vault_path=_resolve_vault_path_if_available(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{pack_id}/regenerate", response_model=MeetingPackResponse)
def post_regenerate_meeting_pack(pack_id: str) -> MeetingPackResponse:
    try:
        return regenerate_meeting_pack(
            pack_id,
            vault_path=_resolve_vault_path(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{pack_id}/rerender", response_model=MeetingPackResponse)
def post_rerender_meeting_pack(pack_id: str) -> MeetingPackResponse:
    try:
        return rerender_meeting_pack(pack_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{pack_id}/markdown", response_class=PlainTextResponse)
def get_meeting_pack_markdown_route(pack_id: str) -> PlainTextResponse:
    try:
        response = get_meeting_pack(pack_id)
        return PlainTextResponse(response.markdown or "")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
