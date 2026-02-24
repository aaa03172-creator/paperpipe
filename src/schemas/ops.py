from __future__ import annotations

from pydantic import BaseModel, Field


class DownloaderOpsMetrics(BaseModel):
    db_exists: bool
    window_hours: int
    paper_rows: int
    attempt_rows: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    provider_counts: dict[str, int] = Field(default_factory=dict)
    retry_attempts_total: int = 0
    retry_attempts_by_provider: dict[str, int] = Field(default_factory=dict)
    rate_limit_retry_signals: int = 0
    rate_limit_exhausted: int = 0
    missing_pdf_rows: int = 0
    has_download_attempts_column: bool = False


class DownloaderOpsMetricsResponse(BaseModel):
    metrics: DownloaderOpsMetrics
    alerts: list[str] = Field(default_factory=list)
