from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BC5CDREntityType = Literal["chemical", "disease"]
BC5CDRRelationType = Literal["chemical_induced_disease"]


class BC5CDRMention(BaseModel):
    mention_id: str = Field(..., min_length=1)
    entity_type: BC5CDREntityType
    text: str = Field(..., min_length=1)
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., gt=0)
    normalized_id: str | None = None


class BC5CDRRelation(BaseModel):
    relation_id: str = Field(..., min_length=1)
    relation_type: BC5CDRRelationType = "chemical_induced_disease"
    chemical_mention_id: str = Field(..., min_length=1)
    disease_mention_id: str = Field(..., min_length=1)


class BC5CDRDocument(BaseModel):
    schema_version: str = "bc5cdr.document.v1"
    doc_id: str = Field(..., min_length=1)
    title: str | None = None
    abstract: str | None = None
    mentions: list[BC5CDRMention] = Field(default_factory=list)
    relations: list[BC5CDRRelation] = Field(default_factory=list)


class BC5CDRScore(BaseModel):
    predicted_count: int = Field(default=0, ge=0)
    gold_count: int = Field(default=0, ge=0)
    hit_count: int = Field(default=0, ge=0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    recall: float = Field(default=0.0, ge=0.0, le=1.0)
    f1: float = Field(default=0.0, ge=0.0, le=1.0)


class BC5CDREvalReport(BaseModel):
    schema_version: str = "bc5cdr.eval_report.v1"
    evaluated_at: datetime
    gold_doc_id: str
    prediction_doc_id: str
    doc_id_match: bool = True
    mention_exact: BC5CDRScore = Field(default_factory=BC5CDRScore)
    mention_normalized: BC5CDRScore = Field(default_factory=BC5CDRScore)
    relation: BC5CDRScore = Field(default_factory=BC5CDRScore)
    warnings: list[str] = Field(default_factory=list)
