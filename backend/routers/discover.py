from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.discovery_queue import run_discovery_queue

router = APIRouter(prefix="/discover", tags=["discover"])


class DiscoverQueueRequest(BaseModel):
    seed: str
    limit: int = Field(default=10, ge=1, le=30)
    write_obsidian: bool = True


class DiscoverItem(BaseModel):
    paper_id: str
    title: str
    status: str
    score: float
    relation: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    reason: str


class DiscoverQueueResponse(BaseModel):
    seed: str
    saved: int
    recommended: int
    pending_queue: int
    note_path: Optional[str] = None
    items: List[DiscoverItem]


@router.post("/queue", response_model=DiscoverQueueResponse)
def discover_queue(req: DiscoverQueueRequest):
    try:
        result: Dict[str, Any] = run_discovery_queue(
            seed=req.seed,
            limit=req.limit,
            write_obsidian=req.write_obsidian,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"discover queue failed: {exc}")

    return result
