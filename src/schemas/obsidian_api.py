from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class ObsidianArtifactBundle(BaseModel):
    paper_id: str
    run_id: str
    claimset_source: Literal["resolved", "legacy", "missing"]
    claimset_legacy: Optional[dict[str, Any]] = None
    claimset_resolved: Optional[dict[str, Any]] = None
    chunks: Optional[dict[str, Any]] = None
    stats_report: Optional[dict[str, Any]] = None
