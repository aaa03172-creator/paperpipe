from __future__ import annotations

from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, model_validator


ArtifactReviewArtifactType = Literal[
    "meeting_pack",
    "chart_pack",
    "image_evidence",
    "method_comparison",
    "protocol_card",
]
ArtifactReviewDecision = Literal["accept", "reject", "correct", "escalate"]


class ArtifactReviewFeedbackWriteRequest(BaseModel):
    paper_id: str | None = None
    run_id: str | None = None
    dna_id: str | None = None
    decision: ArtifactReviewDecision
    reason_code: str = Field(..., min_length=1)
    actor_id: str = Field(..., min_length=1)
    note: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.reason_code = self.reason_code.strip()
        self.actor_id = self.actor_id.strip()
        self.note = self.note.strip()

        if self.paper_id is not None:
            self.paper_id = self.paper_id.strip() or None
        if self.run_id is not None:
            self.run_id = self.run_id.strip() or None
        if self.dna_id is not None:
            self.dna_id = self.dna_id.strip() or None

        if not any((self.paper_id, self.run_id, self.dna_id)):
            raise ValueError("ArtifactReviewFeedbackCase requires paper_id, run_id, or dna_id")
        return self


class ArtifactReviewFeedbackCase(ArtifactReviewFeedbackWriteRequest):
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_type: ArtifactReviewArtifactType
    artifact_id: str = Field(..., min_length=1)
    timestamp: str | None = None

    @model_validator(mode="after")
    def normalize_record_fields(self):
        self.feedback_id = self.feedback_id.strip()
        self.artifact_id = self.artifact_id.strip()
        if self.timestamp is not None:
            self.timestamp = self.timestamp.strip() or None
        return self
