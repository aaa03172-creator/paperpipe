"""
Pydantic 스키마 정의.
LLM에서 추출한 데이터의 유효성을 검사하고 타입을 강제하는 데 사용됩니다.
"""

from __future__ import annotations

from src.schemas.downloader import DownloadAttempt, DownloadCandidate, DownloadFailure
from src.schemas.paper import Paper, PaperStatus, ReadingStatus
from src.schemas.trial import (
    Citation,
    Comparator,
    EligibilityFlags,
    ExtractionQuality,
    Intervention,
    KetoneConfirmation,
    Outcome,
    Outcomes,
    PaperTagging,
    Population,
    RiskOfBiasHints,
    SafetyAdherence,
    StudyDesign,
    TrialExtraction,
)

__all__ = [
    "DownloadFailure",
    "DownloadAttempt",
    "DownloadCandidate",
    "PaperStatus",
    "ReadingStatus",
    "Paper",
    "Citation",
    "StudyDesign",
    "Population",
    "Intervention",
    "Comparator",
    "KetoneConfirmation",
    "Outcome",
    "Outcomes",
    "SafetyAdherence",
    "RiskOfBiasHints",
    "EligibilityFlags",
    "ExtractionQuality",
    "PaperTagging",
    "TrialExtraction",
]
