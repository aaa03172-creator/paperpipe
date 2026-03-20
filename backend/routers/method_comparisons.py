from __future__ import annotations

from pathlib import Path
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from src.config import load_config
from src.method_comparisons.service import (
    generate_method_comparison,
    get_method_comparison,
    method_comparison_list_response,
    method_comparison_response_payload,
)
from src.schemas.method_comparison import (
    MethodComparisonListResponse,
    MethodComparisonRequest,
    MethodComparisonResponse,
)


router = APIRouter(prefix="/method-comparisons", tags=["method-comparisons"])


def _resolve_vault_path() -> Path:
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail=f"Obsidian vault not found: {vault_path}")
    if not vault_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Obsidian vault path is not a directory: {vault_path}")
    return vault_path


def _csv_download_filename(comparison_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", comparison_id).strip("._")
    if not safe_id:
        safe_id = "method-comparison"
    return f"{safe_id}.csv"


@router.post("/generate", response_model=MethodComparisonResponse)
def post_generate_method_comparison(payload: MethodComparisonRequest) -> MethodComparisonResponse:
    try:
        result = generate_method_comparison(
            request=payload,
            vault_path=_resolve_vault_path(),
        )
        return method_comparison_response_payload(result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=MethodComparisonListResponse)
def list_method_comparisons_route() -> MethodComparisonListResponse:
    try:
        return method_comparison_list_response()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{comparison_id}", response_model=MethodComparisonResponse)
def get_method_comparison_route(comparison_id: str) -> MethodComparisonResponse:
    try:
        return method_comparison_response_payload(get_method_comparison(comparison_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{comparison_id}/export.csv", response_class=PlainTextResponse)
def get_method_comparison_csv_route(comparison_id: str) -> PlainTextResponse:
    try:
        result = get_method_comparison(comparison_id)
        filename = _csv_download_filename(comparison_id)
        return PlainTextResponse(
            result.csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
