from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ProjectMemoryWorkspaceStatus = Literal["active", "archived"]
ProjectMemoryItemType = Literal["question", "judgment", "note", "todo", "uncertainty", "decision"]
ProjectMemoryConfidenceStatus = Literal["tentative", "working", "confident", "superseded"]
ProjectMemoryFreshnessStatus = Literal["current", "aging", "stale", "superseded"]
ProjectMemoryEntityType = Literal[
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
ProjectMemoryRelationshipType = Literal["references", "supports", "blocks", "decides", "mentions"]


class ProjectMemoryEntityLink(BaseModel):
    entity_type: ProjectMemoryEntityType
    entity_id: str = Field(..., min_length=1)
    relationship_type: ProjectMemoryRelationshipType
    note: str | None = None

    @model_validator(mode="after")
    def normalize_entity_link(self):
        self.entity_id = self.entity_id.strip()
        if not self.entity_id:
            raise ValueError("ProjectMemoryEntityLink.entity_id must not be blank")
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class ProjectMemoryItem(BaseModel):
    item_id: str = Field(..., pattern=r"^pmitem_[A-Za-z0-9._-]+$")
    project_id: str = Field(..., pattern=r"^pmproj_[A-Za-z0-9._-]+$")
    layer: Literal["raw_memory"] = "raw_memory"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    item_type: ProjectMemoryItemType
    content: str = Field(..., min_length=1)
    confidence_status: ProjectMemoryConfidenceStatus = "working"
    freshness_status: ProjectMemoryFreshnessStatus = "current"
    linked_entities: list[ProjectMemoryEntityLink] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def normalize_item(self):
        self.item_id = self.item_id.strip()
        self.project_id = self.project_id.strip()
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("ProjectMemoryItem.content must not be blank")
        self.linked_entities = _dedupe_entity_links(self.linked_entities)
        return self


class ProjectMemoryWorkspace(BaseModel):
    project_id: str = Field(..., pattern=r"^pmproj_[A-Za-z0-9._-]+$")
    title: str = Field(..., min_length=1)
    layer: Literal["raw_memory"] = "raw_memory"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    objective: str | None = None
    status: ProjectMemoryWorkspaceStatus = "active"
    notes: str | None = None
    linked_paper_ids: list[str] = Field(default_factory=list)
    linked_research_dna_ids: list[str] = Field(default_factory=list)
    linked_meeting_pack_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def normalize_workspace(self):
        self.project_id = self.project_id.strip()
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("ProjectMemoryWorkspace.title must not be blank")
        if self.objective is not None:
            self.objective = self.objective.strip() or None
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        self.linked_paper_ids = _dedupe_non_empty_strings(self.linked_paper_ids, field_name="linked_paper_ids")
        self.linked_research_dna_ids = _dedupe_non_empty_strings(
            self.linked_research_dna_ids,
            field_name="linked_research_dna_ids",
        )
        self.linked_meeting_pack_ids = _dedupe_non_empty_strings(
            self.linked_meeting_pack_ids,
            field_name="linked_meeting_pack_ids",
        )
        return self


def _dedupe_non_empty_strings(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{field_name} must not contain blank strings")
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _dedupe_entity_links(values: list[ProjectMemoryEntityLink]) -> list[ProjectMemoryEntityLink]:
    normalized: list[ProjectMemoryEntityLink] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in values:
        key = (item.entity_type, item.entity_id, item.relationship_type, item.note)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized
