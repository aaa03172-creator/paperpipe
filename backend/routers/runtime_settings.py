from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.schemas.runtime_settings import (
    RuntimeLLMConnectionTestResponse,
    RuntimeLLMSettingsResponse,
    RuntimeLLMSettingsUpdateRequest,
)
from src.services.runtime_settings import (
    get_llm_runtime_settings,
    test_llm_runtime_connection,
    update_llm_runtime_settings,
)


router = APIRouter(prefix="/runtime-settings", tags=["runtime-settings"])


@router.get("/llm", response_model=RuntimeLLMSettingsResponse)
def get_runtime_llm_settings():
    try:
        return get_llm_runtime_settings()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/llm", response_model=RuntimeLLMSettingsResponse)
def put_runtime_llm_settings(request: RuntimeLLMSettingsUpdateRequest):
    try:
        return update_llm_runtime_settings(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/llm/test", response_model=RuntimeLLMConnectionTestResponse)
def post_runtime_llm_connection_test():
    try:
        return test_llm_runtime_connection()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
