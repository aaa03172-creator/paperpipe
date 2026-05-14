from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


ArtifactHistoryPromotionArtifactType = Literal["meeting_pack", "protocol_card"]
ArtifactHistoryPromotionPolicyMode = Literal["manual_review_only"]
ArtifactHistoryPromotionManualAction = Literal[
    "review_recent_samples",
    "write_promotion_note",
    "open_explicit_rfc_before_default_owner_change",
]


class ArtifactHistoryPromotionGateThresholds(BaseModel):
    required_families: list[ArtifactHistoryPromotionArtifactType] = Field(min_length=1)
    min_review_feedback_events: int = Field(ge=0)
    min_generation_outcome_events: int = Field(ge=0)
    min_paired_artifacts: int = Field(ge=0)

    @model_validator(mode="after")
    def normalize_required_families(self):
        self.required_families = [item.strip() for item in self.required_families]
        return self


class ArtifactHistoryPromotionPolicy(BaseModel):
    schema_version: Literal["artifact_history_promotion_policy.v1"]
    status: Literal["active"]
    policy_mode: ArtifactHistoryPromotionPolicyMode
    required_families: list[ArtifactHistoryPromotionArtifactType] = Field(min_length=1)
    thresholds: ArtifactHistoryPromotionGateThresholds
    requires_real_operator_history: bool = True
    discussion_ready_when_gate_passes: bool = True
    allows_default_owner_change: bool = False
    allows_automatic_runtime_promotion: bool = False
    required_manual_actions: list[ArtifactHistoryPromotionManualAction] = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_policy_consistency(self):
        self.required_families = [item.strip() for item in self.required_families]
        if self.required_families != self.thresholds.required_families:
            raise ValueError("required_families must match thresholds.required_families")
        if self.policy_mode == "manual_review_only":
            if self.allows_default_owner_change:
                raise ValueError("manual_review_only policy must not allow default owner change")
            if self.allows_automatic_runtime_promotion:
                raise ValueError("manual_review_only policy must not allow automatic runtime promotion")
        return self


ArtifactHistoryPromotionGateThresholds.model_rebuild()
ArtifactHistoryPromotionPolicy.model_rebuild()
