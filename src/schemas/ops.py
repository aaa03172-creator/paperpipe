from __future__ import annotations

from typing import Any, Optional, Literal

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


class ArtifactFileEntry(BaseModel):
    exists: bool = False
    path: Optional[str] = None
    data: Optional[Any] = None


class ArtifactBundleResponse(BaseModel):
    paper_id: str
    run_id: str
    files: dict[str, ArtifactFileEntry] = Field(default_factory=dict)


class RunTimelineEvent(BaseModel):
    event: Literal["log", "done", "status", "error"] = "log"
    source: Literal["job_log", "synthetic"] = "job_log"
    ts: Optional[str] = None
    stage: Optional[str] = None
    progress: Optional[int] = None
    level: Optional[str] = None
    message: Optional[str] = None
    raw: Optional[str] = None


class RunTimelineResponse(BaseModel):
    run_id: str
    job_id: Optional[str] = None
    paper_id: Optional[str] = None
    events: list[RunTimelineEvent] = Field(default_factory=list)


class ObsidianArtifactsResponse(BaseModel):
    paper_id: str
    run_id: str
    claimset_source: Optional[str] = None
    claimset: ArtifactFileEntry = Field(default_factory=ArtifactFileEntry)
    chunks: ArtifactFileEntry = Field(default_factory=ArtifactFileEntry)
    stats_report: ArtifactFileEntry = Field(default_factory=ArtifactFileEntry)


class PersonaOption(BaseModel):
    id: str
    title: str
    enabled: bool = True
    notes: Optional[str] = None
    schedule: Optional[str] = None
    query_focus: Optional[str] = None
    source: Literal["builtin", "yaml"] = "yaml"


class PersonaListResponse(BaseModel):
    personas: list[PersonaOption] = Field(default_factory=list)
