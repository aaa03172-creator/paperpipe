from __future__ import annotations

from pydantic import BaseModel, Field


class IntakeOverrideLog(BaseModel):
    schema_version: str = "intake_override_log.v1"
    producer: str
    analysis_available: bool = False
    llm_tagging_used: bool = False
    llm_slot_classification_used: bool = False
    input_slot: str | None = None
    stored_slot: str | None = None
    slot_changed: bool = False
    input_tags: list[str] = Field(default_factory=list)
    stored_tags: list[str] = Field(default_factory=list)
    tags_changed: bool = False
    processing_status: str | None = None
    issues_state: str | None = None
    confidence: float | None = None
