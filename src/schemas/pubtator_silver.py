from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PubTatorLocation(BaseModel):
    offset: int = Field(..., ge=0)
    length: int = Field(..., ge=1)


class PubTatorAnnotation(BaseModel):
    annotation_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    infons: dict[str, str] = Field(default_factory=dict)
    locations: list[PubTatorLocation] = Field(default_factory=list)


class PubTatorRelationNode(BaseModel):
    refid: str = Field(..., min_length=1)
    role: str | None = None


class PubTatorRelation(BaseModel):
    relation_id: str = Field(..., min_length=1)
    infons: dict[str, str] = Field(default_factory=dict)
    nodes: list[PubTatorRelationNode] = Field(default_factory=list)


class PubTatorPassage(BaseModel):
    offset: int = Field(default=0, ge=0)
    text: str | None = None
    infons: dict[str, str] = Field(default_factory=dict)
    annotations: list[PubTatorAnnotation] = Field(default_factory=list)
    relations: list[PubTatorRelation] = Field(default_factory=list)


class PubTatorDocument(BaseModel):
    schema_version: str = "pubtator.document.v1"
    loaded_at: datetime | None = None
    doc_id: str = Field(..., min_length=1)
    passages: list[PubTatorPassage] = Field(default_factory=list)
