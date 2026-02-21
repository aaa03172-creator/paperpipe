from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal, List
from datetime import datetime

class JobCreate(BaseModel):
    paper_id: str
    clean_reindex: bool = False
    run_verify: bool = False
    persona_id: str = "default"

class JobStatus(BaseModel):
    job_id: str
    paper_id: Optional[str]
    run_id: Optional[str]
    persona_id: Optional[str]
    run_verify: Optional[int]
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled']
    progress: int
    stage: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    artifact_dir: Optional[str]
    log_path: Optional[str]
    bootstrap_meta_path: Optional[str] = None
    similar_feedback_count: Optional[int] = None
    persona_applied: Optional[bool] = None
    artifact_document_written: Optional[bool] = None
    artifact_index_written: Optional[bool] = None
    artifact_claimset_written: Optional[bool] = None
    artifact_stats_written: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class JobBootstrapMeta(BaseModel):
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    paper_id: Optional[str] = None
    persona_id: Optional[str] = None
    persona_applied: Optional[bool] = None
    similar_feedback_count: Optional[int] = None
    similar_feedback_paper_ids: List[str] = []
    run_verify: Optional[bool] = None
    reader_model: Optional[str] = None
    verifier_used: Optional[bool] = None
    verifier_status: Optional[str] = None
    stats_report_written: Optional[bool] = None
    artifact_document_written: Optional[bool] = None
    artifact_index_written: Optional[bool] = None
    artifact_claimset_written: Optional[bool] = None
    artifact_stats_written: Optional[bool] = None
    timestamp: Optional[str] = None

    model_config = ConfigDict(extra="allow")
