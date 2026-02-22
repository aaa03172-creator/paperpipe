from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DownloadFailure(str, Enum):
    NO_LINK = "no_link"
    RATE_LIMIT = "rate_limit"
    TEMP_FAIL = "temp_fail"
    PERM_FAIL = "perm_fail"
    POLICY_BLOCK = "policy_block"
    BAD_CONTENT = "bad_content"


class DownloadAttempt(BaseModel):
    provider: str
    timestamp: datetime = Field(default_factory=datetime.now)
    status: DownloadFailure
    candidate_url: Optional[str] = None
    message: Optional[str] = None
    retry_no: int = 0
    will_retry: bool = False


class DownloadCandidate(BaseModel):
    url: str
    source_name: str
    is_oa: bool
    confidence: float
    license: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
