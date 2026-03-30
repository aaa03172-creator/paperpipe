from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MeetingPackGateStatus = Literal["pass", "warn", "fail"]


class MeetingPackAcceptanceCheck(BaseModel):
    name: str
    required: bool = True
    source: str
    description: str = ""


class MeetingPackAcceptanceContract(BaseModel):
    schema_version: str = "2026-03-27.meeting-pack-handoff.v1"
    workflow: Literal["meeting_pack"] = "meeting_pack"
    pack_id: str
    requested_scope: dict[str, object] = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list)
    acceptance_checks: list[MeetingPackAcceptanceCheck] = Field(default_factory=list)
    operator_contract: dict[str, object] = Field(default_factory=dict)


class MeetingPackQualityGateCheck(BaseModel):
    name: str
    status: MeetingPackGateStatus
    detail: str = ""


class MeetingPackQualityGate(BaseModel):
    schema_version: str = "2026-03-27.meeting-pack-handoff.v1"
    workflow: Literal["meeting_pack"] = "meeting_pack"
    pack_id: str
    overall_status: Literal["pass", "warn", "fail"] = "warn"
    bundle_ready: bool = False
    discussion_ready: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    checks: list[MeetingPackQualityGateCheck] = Field(default_factory=list)
