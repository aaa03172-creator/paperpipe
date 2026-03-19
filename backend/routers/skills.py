from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.schemas.skills import SkillRunRequest, SkillRunResponse
from src.skills.router import dispatch_skill_action


router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("/run", response_model=SkillRunResponse)
def run_skill(request: SkillRunRequest):
    try:
        return dispatch_skill_action(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
