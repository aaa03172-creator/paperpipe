from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ChartPackGateStatus = Literal["pass", "warn", "fail"]


class ChartPackAcceptanceCheck(BaseModel):
    name: str
    required: bool = True
    source: str
    description: str = ""


class ChartPackAcceptanceContract(BaseModel):
    schema_version: str = "2026-04-17.chart-pack-handoff.v1"
    workflow: Literal["chart_pack"] = "chart_pack"
    chart_pack_id: str
    requested_scope: dict[str, object] = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list)
    acceptance_checks: list[ChartPackAcceptanceCheck] = Field(default_factory=list)
    operator_contract: dict[str, object] = Field(default_factory=dict)


class ChartPackQualityGateCheck(BaseModel):
    name: str
    status: ChartPackGateStatus
    detail: str = ""


class ChartPackQualityGate(BaseModel):
    schema_version: str = "2026-04-17.chart-pack-handoff.v1"
    workflow: Literal["chart_pack"] = "chart_pack"
    chart_pack_id: str
    overall_status: Literal["pass", "warn", "fail"] = "warn"
    bundle_ready: bool = False
    handoff_ready: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    checks: list[ChartPackQualityGateCheck] = Field(default_factory=list)
