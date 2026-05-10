from __future__ import annotations

from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, model_validator


ArtifactGenerationArtifactType = Literal[
    "meeting_pack",
    "chart_pack",
    "image_evidence",
    "method_comparison",
    "protocol_card",
]
ArtifactGenerationDecision = Literal[
    "reused",
    "reused_after_correction",
    "abandoned",
    "escalated",
]
ArtifactGenerationDownstreamUse = Literal[
    "final_deliverable",
    "supporting_context",
    "follow_on_artifact",
    "human_review_queue",
    "not_used",
    "other",
]


class ArtifactGenerationOutcomeWriteRequest(BaseModel):
    paper_id: str | None = None
    run_id: str | None = None
    dna_id: str | None = None
    review_feedback_id: str | None = None
    decision: ArtifactGenerationDecision
    downstream_use: ArtifactGenerationDownstreamUse
    actor_id: str = Field(..., min_length=1)
    note: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.actor_id = self.actor_id.strip()
        self.note = self.note.strip()

        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.run_id is not None:
            self.run_id = self.run_id.strip() or None
        if self.dna_id is not None:
            self.dna_id = self.dna_id.strip() or None
        if self.review_feedback_id is not None:
            self.review_feedback_id = self.review_feedback_id.strip() or None

        if not any((self.paper_id, self.run_id, self.dna_id)):
            raise ValueError("ArtifactGenerationOutcome requires paper_id, run_id, or dna_id")
        if self.decision == "abandoned" and self.downstream_use != "not_used":
            raise ValueError("abandoned outcomes must use downstream_use=not_used")
        if self.decision in {"reused", "reused_after_correction"} and self.downstream_use == "not_used":
            raise ValueError("reused outcomes must not use downstream_use=not_used")
        return self


class ArtifactGenerationOutcome(ArtifactGenerationOutcomeWriteRequest):
    outcome_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_type: ArtifactGenerationArtifactType
    artifact_id: str = Field(..., min_length=1)
    timestamp: str | None = None

    @model_validator(mode="after")
    def normalize_record_fields(self):
        self.outcome_id = self.outcome_id.strip()
        self.artifact_id = self.artifact_id.strip()
        if self.timestamp is not None:
            self.timestamp = self.timestamp.strip() or None
        return self
