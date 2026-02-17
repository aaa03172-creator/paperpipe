from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class JobCreate(BaseModel):
    paper_id: str
    clean_reindex: bool = False

class JobStatus(BaseModel):
    job_id: str
    paper_id: Optional[str]
    run_id: Optional[str]
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled']
    progress: int
    stage: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    artifact_dir: Optional[str]
    log_path: Optional[str]

    class Config:
        from_attributes = True
