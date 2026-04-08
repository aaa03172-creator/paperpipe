from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DeepReadGateStatus = Literal["pass", "warn", "fail", "not_run"]


class DeepReadAcceptanceCheck(BaseModel):
    name: str
    required: bool = True
    source: str
    description: str = ""


class DeepReadAcceptanceContract(BaseModel):
    schema_version: str = "2026-03-27.deepread-handoff.v1"
    workflow: Literal["deep_read"] = "deep_read"
    paper_id: str
    run_id: str
    requested_scope: dict[str, object] = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list)
    acceptance_checks: list[DeepReadAcceptanceCheck] = Field(default_factory=list)
    promotion_contract: dict[str, object] = Field(default_factory=dict)


class DeepReadQualityGateCheck(BaseModel):
    name: str
    status: DeepReadGateStatus
    detail: str = ""


class DeepReadQualityGate(BaseModel):
    schema_version: str = "2026-03-27.deepread-handoff.v1"
    workflow: Literal["deep_read"] = "deep_read"
    paper_id: str
    run_id: str
    overall_status: Literal["pass", "warn", "fail"] = "warn"
    current_promotion_candidate: bool = False
    review_ready: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    checks: list[DeepReadQualityGateCheck] = Field(default_factory=list)


class DeepReadContextManifestAttempt(BaseModel):
    attempt_idx: int
    label: str
    status: str = "unknown"
    context_mode: str | None = None
    context_chars: int | None = None
    prompt_chars: int | None = None
    estimated_prompt_tokens: int | None = None
    estimated_response_tokens: int | None = None
    included_chunk_count: int | None = None
    unique_section_count: int | None = None
    unique_page_hint_count: int | None = None
    sentence_focus_count: int | None = None
    truncated_chunk_count: int | None = None


class DeepReadContextManifest(BaseModel):
    schema_version: str = "2026-04-01.deepread-context-manifest.v1"
    workflow: Literal["deep_read"] = "deep_read"
    paper_id: str
    run_id: str
    configured_attempt_order: str | None = None
    effective_attempt_order: list[str] = Field(default_factory=list)
    attempt_count: int = 0
    return_mode: str | None = None
    selected_attempt: int | None = None
    selected_attempt_label: str | None = None
    final_claim_count: int | None = None
    used_heuristic_fallback: bool = False
    attempts: list[DeepReadContextManifestAttempt] = Field(default_factory=list)
    selected_attempt_summary: DeepReadContextManifestAttempt | None = None
