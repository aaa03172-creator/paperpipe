from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FigureCaptionMetrics(BaseModel):
    figure_count: int = 0
    page_count: int = 0


class FigureCaptionEntry(BaseModel):
    figure_id: str
    label: str
    page: int | None = None
    section: str
    caption: str
    confidence: Literal["heuristic_text_match"] = "heuristic_text_match"


class FigureCaptionSidecar(BaseModel):
    schema_version: Literal["figure_caption_sidecar.v1"] = "figure_caption_sidecar.v1"
    layer: Literal["compiled_knowledge"] = "compiled_knowledge"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    paper_id: str
    run_id: str
    source_artifacts: list[str] = Field(default_factory=lambda: ["document_artifact.json"])
    generated_at: datetime
    metrics: FigureCaptionMetrics
    figures: list[FigureCaptionEntry] = Field(default_factory=list)
