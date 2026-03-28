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
