from __future__ import annotations

from typing import Any, Optional, Literal

from pydantic import BaseModel, Field

from src.services.runtime_paths import artifacts_root


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


class RuntimeReadinessCheck(BaseModel):
    name: str
    status: Literal["ok", "warn", "error"] = "ok"
    detail: str = ""
    path: Optional[str] = None


class RuntimeReadinessResponse(BaseModel):
    status: Literal["ok", "degraded", "error"] = "ok"
    checks: list[RuntimeReadinessCheck] = Field(default_factory=list)


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
    source: Literal["job_log", "synthetic", "db_event", "user_action"] = "job_log"
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


class UserActionEntry(BaseModel):
    action_id: str
    ts: str
    paper_id: Optional[str] = None
    action_type: str
    source: str
    payload: Optional[Any] = None


class UserActionListResponse(BaseModel):
    actions: list[UserActionEntry] = Field(default_factory=list)


class ObsidianArtifactsResponse(BaseModel):
    paper_id: str
    run_id: str
    claimset_source: Optional[str] = None
    claimset: ArtifactFileEntry = Field(default_factory=ArtifactFileEntry)
    chunks: ArtifactFileEntry = Field(default_factory=ArtifactFileEntry)
    stats_report: ArtifactFileEntry = Field(default_factory=ArtifactFileEntry)


class ObsidianMirrorClaim(BaseModel):
    claim_id: str
    claim_type: str
    statement: str
    confidence: float
    evidence_quote: Optional[str] = None
    evidence_page: Optional[int] = None
    evidence_chunk_id: Optional[str] = None
    evidence_grounded: Optional[bool] = None
    evidence_resolution: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)


class ObsidianMirrorStatCheck(BaseModel):
    check_id: str
    test_type: str
    verdict: str
    claim_id: Optional[str] = None
    evidence_page: Optional[int] = None
    evidence_chunk_id: Optional[str] = None
    evidence_grounded: Optional[bool] = None
    evidence_resolution: Optional[str] = None
    hypothesis: Optional[str] = None
    notes: Optional[str] = None
    decision_error: bool = False


class ObsidianMirrorResponse(BaseModel):
    paper_id: str
    run_id: str
    generated_markdown: str
    has_claimset: bool = False
    has_stats_report: bool = False
    claims: list[ObsidianMirrorClaim] = Field(default_factory=list)
    stats_checks: list[ObsidianMirrorStatCheck] = Field(default_factory=list)


class PersonaOption(BaseModel):
    id: str
    title: str
    enabled: bool = True
    kind: Literal["compatibility", "reasoning_persona", "profile"] = "profile"
    notes: Optional[str] = None
    schedule: Optional[str] = None
    query_focus: Optional[str] = None
    source: Literal["builtin", "yaml"] = "yaml"


class PersonaListResponse(BaseModel):
    personas: list[PersonaOption] = Field(default_factory=list)


class StatsRepairRequest(BaseModel):
    paper_ids: list[str] = Field(default_factory=list)
    run_id: Optional[str] = None
    artifacts_root: str = Field(default_factory=lambda: str(artifacts_root()))
    max_checks: int = Field(default=6, ge=1)
    write_bootstrap_meta: bool = True
    skip_existing: bool = True
    dry_run: bool = False


class StatsRepairResult(BaseModel):
    paper_id: str
    run_id: Optional[str] = None
    status: Literal["seeded", "planned", "skipped"]
    checks: int = 0
    reason: str = ""


class StatsRepairResponse(BaseModel):
    seeded: int = 0
    planned: int = 0
    skipped: int = 0
    total: int = 0
    results: list[StatsRepairResult] = Field(default_factory=list)
