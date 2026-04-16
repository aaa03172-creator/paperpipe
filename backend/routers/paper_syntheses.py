from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from src.config import load_config
from src.paper_syntheses.service import (
    generate_paper_synthesis,
    get_paper_synthesis,
    paper_synthesis_list_response,
    paper_synthesis_response_payload,
)
from src.schemas.paper_synthesis import (
    PaperSynthesisGenerateRequest,
    PaperSynthesis,
    PaperSynthesisListResponse,
    PaperSynthesisResponse,
)


router = APIRouter(prefix="/paper-syntheses", tags=["paper-syntheses"])


def _resolve_vault_path() -> Path:
    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail=f"Obsidian vault not found: {vault_path}")
    if not vault_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Obsidian vault path is not a directory: {vault_path}")
    return vault_path


def _paper_synthesis_compatibility_headers(synthesis_id: str) -> dict[str, str]:
    manifest_path = f"/paper-syntheses/{synthesis_id}/manifest"
    markdown_path = f"/paper-syntheses/{synthesis_id}/markdown"
    return {
        "PaperPipe-Compatibility-Route": "paper_synthesis_bundle",
        "PaperPipe-Preferred-Manifest-Route": manifest_path,
        "PaperPipe-Preferred-Markdown-Route": markdown_path,
    }


@router.post("/generate", response_model=PaperSynthesisResponse)
def post_generate_paper_synthesis(payload: PaperSynthesisGenerateRequest) -> PaperSynthesisResponse:
    try:
        return paper_synthesis_response_payload(
            generate_paper_synthesis(
                request=payload,
                vault_path=_resolve_vault_path(),
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=PaperSynthesisListResponse)
def list_paper_syntheses_route(paper_slug: str | None = None) -> PaperSynthesisListResponse:
    try:
        return paper_synthesis_list_response(paper_slug=paper_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{synthesis_id}",
    response_model=PaperSynthesisResponse,
    deprecated=True,
    summary="Fetch paper synthesis bundle (compatibility route)",
    description=(
        "Compatibility bundle fetch that returns both the structured synthesis manifest and the derived markdown export. "
        "Prefer `/paper-syntheses/{synthesis_id}/manifest` for structured provenance inspection and "
        "`/paper-syntheses/{synthesis_id}/markdown` for user-facing markdown export."
    ),
)
def get_paper_synthesis_route(synthesis_id: str, response: Response) -> PaperSynthesisResponse:
    try:
        payload = paper_synthesis_response_payload(get_paper_synthesis(synthesis_id))
        for header_name, header_value in _paper_synthesis_compatibility_headers(synthesis_id).items():
            response.headers[header_name] = header_value
        return payload
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{synthesis_id}/manifest",
    response_model=PaperSynthesis,
    summary="Fetch paper synthesis manifest",
    description=(
        "Structured manifest for compiled-knowledge inspection. "
        "Use this for source refs, lineage summary, warnings, and other non-markdown provenance fields."
    ),
)
def get_paper_synthesis_manifest_route(synthesis_id: str) -> PaperSynthesis:
    try:
        return get_paper_synthesis(synthesis_id).synthesis
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{synthesis_id}/markdown",
    response_class=PlainTextResponse,
    summary="Fetch paper synthesis markdown export",
    description="Derived markdown export for user-facing reading or file-backed downstream handoff.",
)
def get_paper_synthesis_markdown_route(synthesis_id: str) -> PlainTextResponse:
    try:
        return PlainTextResponse(get_paper_synthesis(synthesis_id).markdown)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
