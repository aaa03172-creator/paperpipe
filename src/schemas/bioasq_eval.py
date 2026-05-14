from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BioASQQuestion(BaseModel):
    question_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    ideal_answers: list[str] = Field(default_factory=list)
    exact_answers: list[str] = Field(default_factory=list)
    source_candidate_ids: list[str] = Field(default_factory=list)
    source_candidate_aliases: list[str] = Field(default_factory=list)
    source_snippets: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BioASQQuestionEval(BaseModel):
    question_id: str
    candidate_gold_count: int = Field(default=0, ge=0)
    candidate_hit_count: int = Field(default=0, ge=0)
    candidate_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    first_candidate_hit_rank: int | None = Field(default=None, ge=1)
    candidate_reciprocal_rank: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_average_precision: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_ndcg_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    top_1_hit: bool = False
    top_5_hit: bool = False
    top_10_hit: bool = False
    snippet_gold_count: int = Field(default=0, ge=0)
    snippet_hit_count: int = Field(default=0, ge=0)
    snippet_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_alias_hit: bool = False
    warnings: list[str] = Field(default_factory=list)


class BioASQRerankLabelRow(BaseModel):
    question_id: str
    question: str
    candidate_rank: int = Field(..., ge=1)
    candidate_id: str = ""
    paper_id: str = ""
    doi: str = ""
    title: str = ""
    summary: str = ""
    identifier_match: bool = False
    snippet_support: bool = False
    answer_alias_support: bool = False
    relevance_grade: int = Field(default=0, ge=0, le=2)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BioASQRerankExperimentQuestion(BaseModel):
    question_id: str
    row_count: int = Field(default=0, ge=0)
    positive_row_count: int = Field(default=0, ge=0)
    strong_positive_row_count: int = Field(default=0, ge=0)
    original_top_1_hit: bool = False
    reranked_top_1_hit: bool = False
    original_mrr: float = Field(default=0.0, ge=0.0, le=1.0)
    reranked_mrr: float = Field(default=0.0, ge=0.0, le=1.0)
    original_map: float = Field(default=0.0, ge=0.0, le=1.0)
    reranked_map: float = Field(default=0.0, ge=0.0, le=1.0)
    original_ndcg_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    reranked_ndcg_at_10: float = Field(default=0.0, ge=0.0, le=1.0)


class BioASQRerankExperimentReport(BaseModel):
    schema_version: str = "bioasq.rerank_experiment.v1"
    evaluated_at: datetime
    question_count: int = Field(default=0, ge=0)
    row_count: int = Field(default=0, ge=0)
    original_top_1_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    reranked_top_1_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    original_mrr: float = Field(default=0.0, ge=0.0, le=1.0)
    reranked_mrr: float = Field(default=0.0, ge=0.0, le=1.0)
    original_map: float = Field(default=0.0, ge=0.0, le=1.0)
    reranked_map: float = Field(default=0.0, ge=0.0, le=1.0)
    original_ndcg_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    reranked_ndcg_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    questions: list[BioASQRerankExperimentQuestion] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BioASQEvalReport(BaseModel):
    schema_version: str = "bioasq.eval_report.v1"
    evaluated_at: datetime
    question_count: int = Field(default=0, ge=0)
    candidate_macro_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_mrr: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_map: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_ndcg_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    snippet_macro_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_alias_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    top_1_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    top_5_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    top_10_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    questions: list[BioASQQuestionEval] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
