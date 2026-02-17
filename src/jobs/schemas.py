from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class JobCreate(BaseModel):
    paper_id: str
    clean_reindex: bool = False

class JobStatus(BaseModel):
    job_id: str
    paper_id: Optional[str] = None
    run_id: Optional[str] = None
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled']
    progress: int
    stage: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    artifact_dir: Optional[str] = None
    log_path: Optional[str] = None

    class Config:
        from_attributes = True

