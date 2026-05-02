from __future__ import annotations

from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, model_validator


# Keep this local so direct module loading for audit scripts does not trigger
# the heavier src.schemas package import chain.
ProjectContextEntityType = Literal[
    "paper",
    "run",
    "meeting_pack",
    "research_dna",
    "paper_note",
    "protocol_card",
    "method_comparison",
    "chart_pack",
    "image_evidence",
]


ProjectContextRelationshipType = Literal[
    "primary_focus",
    "supporting_context",
    "background_context",
    "follow_up_candidate",
    "blocked_or_conflicting",
    "out_of_scope",
]


class ProjectContextLinkDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = Field(..., pattern=r"^pmproj_[A-Za-z0-9._-]+$")
    layer: Literal["raw_memory"] = "raw_memory"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    entity_type: ProjectContextEntityType
    entity_id: str = Field(..., min_length=1)
    relationship_type: ProjectContextRelationshipType
    actor_id: str = Field(..., min_length=1)
    note: str = Field(..., min_length=1)
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.decision_id = self.decision_id.strip()
        self.project_id = self.project_id.strip()
        self.entity_id = self.entity_id.strip()
        self.actor_id = self.actor_id.strip()
        self.note = self.note.strip()
        if self.timestamp is not None:
            self.timestamp = self.timestamp.strip() or None
        return self
