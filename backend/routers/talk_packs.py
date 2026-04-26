from __future__ import annotations

import mimetypes
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from src.schemas.talk_pack import TalkPackListResponse, TalkPackResponse
from src.talk_packs.service import (
    get_talk_pack,
    load_declared_talk_pack_artifact,
    render_talk_pack_deck_pptx,
    talk_pack_list_response,
    talk_pack_response_payload,
)


router = APIRouter(prefix="/talk-packs", tags=["talk-packs"])


def _safe_filename(value: str, *, fallback: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return safe_value or fallback


@router.get("", response_model=TalkPackListResponse)
def list_talk_packs_route() -> TalkPackListResponse:
    try:
        return talk_pack_list_response()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{talk_pack_id}", response_model=TalkPackResponse)
def get_talk_pack_route(talk_pack_id: str) -> TalkPackResponse:
    try:
        return talk_pack_response_payload(get_talk_pack(talk_pack_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{talk_pack_id}/render-deck", response_model=TalkPackResponse)
def post_render_talk_pack_deck_route(talk_pack_id: str) -> TalkPackResponse:
    try:
        return render_talk_pack_deck_pptx(talk_pack_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{talk_pack_id}/artifacts/{artifact_path:path}", response_class=Response)
def get_talk_pack_artifact_route(talk_pack_id: str, artifact_path: str) -> Response:
    try:
        _, normalized_path, content = load_declared_talk_pack_artifact(talk_pack_id, artifact_path)
        filename = _safe_filename(
            f"{talk_pack_id}_{normalized_path.rsplit('/', 1)[-1]}",
            fallback="talk-pack-artifact",
        )
        media_type = _guess_media_type(normalized_path)
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _guess_media_type(path: str) -> str:
    if path.endswith(".md"):
        return "text/markdown"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".pptx"):
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"
