from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StatsFallbackEvalCheckEntry(BaseModel):
    check_id: str
    verdict: str
    method: str | None = None
    notes: str | None = None
    auto_fallback: bool = False
    fallback_reason: str | None = None


class StatsFallbackEvalMetrics(BaseModel):
    check_count: int = 0
    verified_count: int = 0
    partially_verified_count: int = 0
    inconsistent_count: int = 0
    unverifiable_count: int = 0
    auto_fallback_count: int = 0
    no_table_count: int = 0
    no_api_context_count: int = 0
    degenerate_table_shape_count: int = 0
    no_extractable_stats_count: int = 0
    no_executable_verification_count: int = 0
    unspecified_unverifiable_count: int = 0


class StatsFallbackEvalSidecar(BaseModel):
    schema_version: str = "stats_fallback_eval.v1"
    generated_at: datetime
    paper_id: str
    doc_id: str
    run_id: str
    table_extraction_pass: str = "pass1"
    table_failure_taxonomy: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_pages: list[int] = Field(default_factory=list)
    checks: list[StatsFallbackEvalCheckEntry] = Field(default_factory=list)
    metrics: StatsFallbackEvalMetrics
