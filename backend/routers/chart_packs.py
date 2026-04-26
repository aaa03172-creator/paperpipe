from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from src.chart_packs.service import (
    chart_pack_list_response,
    chart_pack_response_payload,
    generate_chart_pack,
    get_chart_pack,
)
from src.chart_packs.store import load_chart_pack_render
from src.schemas.chart_pack import ChartPackListResponse, ChartPackRequest, ChartPackResponse


router = APIRouter(prefix="/chart-packs", tags=["chart-packs"])


def _safe_filename(value: str, *, fallback: str, suffix: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if not safe_value:
        safe_value = fallback
    return f"{safe_value}.{suffix}"


@router.post("/generate", response_model=ChartPackResponse)
def post_generate_chart_pack(payload: ChartPackRequest) -> ChartPackResponse:
    try:
        return chart_pack_response_payload(generate_chart_pack(request=payload))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=ChartPackListResponse)
def list_chart_packs_route() -> ChartPackListResponse:
    try:
        return chart_pack_list_response()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{chart_pack_id}", response_model=ChartPackResponse)
def get_chart_pack_route(chart_pack_id: str) -> ChartPackResponse:
    try:
        return chart_pack_response_payload(get_chart_pack(chart_pack_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{chart_pack_id}/markdown", response_class=PlainTextResponse)
def get_chart_pack_markdown_route(chart_pack_id: str) -> PlainTextResponse:
    try:
        return PlainTextResponse(get_chart_pack(chart_pack_id).markdown)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{chart_pack_id}/charts/{chart_id}/data.csv", response_class=PlainTextResponse)
def get_chart_pack_data_csv_route(chart_pack_id: str, chart_id: str) -> PlainTextResponse:
    try:
        result = get_chart_pack(chart_pack_id)
        csv_text = result.data_snapshots.get(chart_id)
        if csv_text is None:
            raise FileNotFoundError(f"Chart Pack data CSV not found: chart_pack_id={chart_pack_id}, chart_id={chart_id}")
        filename = _safe_filename(
            f"{chart_pack_id}_{chart_id}",
            fallback="chart-pack-data",
            suffix="csv",
        )
        return PlainTextResponse(
            csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{chart_pack_id}/charts/{chart_id}/spec.json", response_class=JSONResponse)
def get_chart_pack_spec_route(chart_pack_id: str, chart_id: str) -> JSONResponse:
    try:
        result = get_chart_pack(chart_pack_id)
        spec_payload = result.specs.get(chart_id)
        if spec_payload is None:
            raise FileNotFoundError(f"Chart Pack spec JSON not found: chart_pack_id={chart_pack_id}, chart_id={chart_id}")
        filename = _safe_filename(
            f"{chart_pack_id}_{chart_id}",
            fallback="chart-pack-spec",
            suffix="json",
        )
        return JSONResponse(
            spec_payload,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{chart_pack_id}/charts/{chart_id}/render.svg", response_class=Response)
def get_chart_pack_render_svg_route(chart_pack_id: str, chart_id: str) -> Response:
    try:
        svg_text = load_chart_pack_render(chart_pack_id, chart_id, extension="svg")
        filename = _safe_filename(
            f"{chart_pack_id}_{chart_id}",
            fallback="chart-pack-render",
            suffix="svg",
        )
        return Response(
            svg_text,
            media_type="image/svg+xml",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
