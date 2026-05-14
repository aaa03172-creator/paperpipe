from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.schemas.core import DownloadAttempt, DownloadFailure, Paper


class DownloadCandidate(BaseModel):
    """Provider-resolved candidate URL plus OA metadata."""

    url: str
    source_name: str
    is_oa: bool
    confidence: float = 1.0
    license: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class DownloadResult(BaseModel):
    """Structured router result with final reason and full attempts."""

    success: bool
    local_pdf_path: Optional[Path] = None
    pdf_link: Optional[str] = None
    attempts: list[DownloadAttempt] = Field(default_factory=list)
    final_status: Optional[DownloadFailure] = None
    message: Optional[str] = None


class DownloadProvider(ABC):
    """Abstract contract for OA download providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def resolve_pdf(self, paper: Paper) -> Optional[DownloadCandidate]:
        raise NotImplementedError
