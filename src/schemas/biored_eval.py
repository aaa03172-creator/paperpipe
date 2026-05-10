from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BioREDRelationNovelty = Literal["novel", "background", "unknown"]


class BioREDMention(BaseModel):
    mention_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., gt=0)
    normalized_ids: list[str] = Field(default_factory=list)
    entity_id: str | None = None


class BioREDRelation(BaseModel):
    relation_id: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    head_mention_id: str = Field(..., min_length=1)
    tail_mention_id: str = Field(..., min_length=1)
    novelty: BioREDRelationNovelty = "unknown"


class BioREDDocument(BaseModel):
    schema_version: str = "biored.document.v1"
    doc_id: str = Field(..., min_length=1)
    title: str | None = None
    abstract: str | None = None
    mentions: list[BioREDMention] = Field(default_factory=list)
    relations: list[BioREDRelation] = Field(default_factory=list)


class BioREDScore(BaseModel):
    predicted_count: int = Field(default=0, ge=0)
    gold_count: int = Field(default=0, ge=0)
    hit_count: int = Field(default=0, ge=0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    recall: float = Field(default=0.0, ge=0.0, le=1.0)
    f1: float = Field(default=0.0, ge=0.0, le=1.0)


class BioREDEvalReport(BaseModel):
    schema_version: str = "biored.eval_report.v1"
    evaluated_at: datetime
    gold_doc_id: str
    prediction_doc_id: str
    doc_id_match: bool = True
    mention_exact: BioREDScore = Field(default_factory=BioREDScore)
    mention_normalized: BioREDScore = Field(default_factory=BioREDScore)
    relation: BioREDScore = Field(default_factory=BioREDScore)
    relation_novelty: BioREDScore = Field(default_factory=BioREDScore)
    warnings: list[str] = Field(default_factory=list)
