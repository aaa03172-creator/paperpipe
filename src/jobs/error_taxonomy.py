from __future__ import annotations

from typing import Optional

# Canonical taxonomy codes (stable contract for ops/UI/replay)
INPUT_PDF_NOT_FOUND = "INPUT_PDF_NOT_FOUND"
PIPELINE_FAILED = "PIPELINE_FAILED"
RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
WORKER_EXCEPTION = "WORKER_EXCEPTION"
USER_CANCELLED = "USER_CANCELLED"
UNKNOWN_ERROR = "UNKNOWN_ERROR"


def classify_failure(error_message: str | None, default: str = PIPELINE_FAILED) -> str:
    text = str(error_message or "").lower()
    if "pdf not found" in text:
        return INPUT_PDF_NOT_FOUND
    if "cancel" in text:
        return USER_CANCELLED
    if text:
        return default
    return UNKNOWN_ERROR


def taxonomy_category(code: Optional[str]) -> str:
    key = str(code or "").strip().upper()
    if key == INPUT_PDF_NOT_FOUND:
        return "input"
    if key in {PIPELINE_FAILED, RUNTIME_EXCEPTION}:
        return "pipeline"
    if key == WORKER_EXCEPTION:
        return "worker"
    if key == USER_CANCELLED:
        return "user_action"
    return "unknown"


def taxonomy_retryable(code: Optional[str]) -> bool:
    key = str(code or "").strip().upper()
    if key in {INPUT_PDF_NOT_FOUND, USER_CANCELLED}:
        return False
    if key in {PIPELINE_FAILED, RUNTIME_EXCEPTION, WORKER_EXCEPTION, UNKNOWN_ERROR}:
        return True
    return True
