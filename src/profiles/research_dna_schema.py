from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ResearchIntent = Literal["explore", "systematic_review", "update"]
ResearchStatus = Literal["DRAFT", "PILOT", "LOCKED"]
QueryMode = Literal["recall", "precision"]
InterviewRound = Literal["researcher", "librarian"]
ActorType = Literal["human_cli", "human_api", "system", "agent"]
RunStatus = Literal["started", "completed", "partial", "failed"]
GoldsetKind = Literal["none", "retrospective_provisional", "external_benchmark"]
ScreeningDecision = Literal["include", "exclude", "unclear"]
ReasonCode = Literal[
    "wrong_population",
    "wrong_intervention_or_exposure",
    "wrong_outcome",
    "wrong_study_type",
    "wrong_domain_or_condition",
    "protocol_editorial_or_review_only",
    "non_human_or_preclinical_only",
    "duplicate",
    "insufficient_metadata",
    "other_noise",
]
ApprovalAction = Literal[
    "create",
    "update",
    "approve_pilot",
    "refine",
    "lock",
    "unlock",
    "submit_screening",
    "change_goldset_kind",
    "project_profile",
]
BenchmarkDecision = Literal["include", "exclude"]


class ResearchScope(BaseModel):
    population: List[str] = Field(default_factory=list)
    intervention_or_exposure: List[str] = Field(default_factory=list)
    comparison: List[str] = Field(default_factory=list)
    outcomes: List[str] = Field(default_factory=list)
    concept_blocks: Dict[str, List[str]] = Field(default_factory=dict)


class ResearchCriteria(BaseModel):
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)


class ResearchFilters(BaseModel):
    year_start: Optional[int] = Field(default=None, ge=0)
    year_end: Optional[int] = Field(default=None, ge=0)
    language: List[str] = Field(default_factory=list)
    study_type: List[str] = Field(default_factory=list)


class QueryVersion(BaseModel):
    version: str = Field(..., pattern=r"^v[0-9]+$")
    mode: QueryMode = "recall"
    per_db: Dict[str, str] = Field(default_factory=dict)
    change_summary: str = ""
    created_at: datetime
    created_by: str


class PilotConfig(BaseModel):
    n: int = Field(default=30, ge=20, le=50)
    goldset_kind: GoldsetKind = "none"
    goldset: List[str] = Field(default_factory=list)
    goldset_sources: List[str] = Field(default_factory=list)
    goldset_note: Optional[str] = None


class Governance(BaseModel):
    approved_for_pilot_at: Optional[datetime] = None
    approved_for_pilot_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    change_policy: Optional[str] = None


class ResearchDNAUpdate(BaseModel):
    title: Optional[str] = None
    intent: Optional[ResearchIntent] = None
    scope: Optional[ResearchScope] = None
    criteria: Optional[ResearchCriteria] = None
    recommended_databases: Optional[List[str]] = None
    available_databases: Optional[List[str]] = None
    filters: Optional[ResearchFilters] = None
    pilot: Optional[PilotConfig] = None
    change_policy: Optional[str] = None


class ResearchDNA(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    revision: int = Field(default=0, ge=0)
    title: str
    intent: ResearchIntent
    status: ResearchStatus = "DRAFT"
    scope: ResearchScope = Field(default_factory=ResearchScope)
    criteria: ResearchCriteria = Field(default_factory=ResearchCriteria)
    recommended_databases: List[str] = Field(default_factory=list)
    available_databases: List[str] = Field(default_factory=list)
    filters: ResearchFilters = Field(default_factory=ResearchFilters)
    query_versions: List[QueryVersion] = Field(default_factory=list)
    pilot: PilotConfig = Field(default_factory=PilotConfig)
    governance: Governance = Field(default_factory=Governance)


class InterviewLogEntry(BaseModel):
    ts: datetime
    dna_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    round: InterviewRound
    question_id: str
    question: str
    answer: str
    actor_type: ActorType
    actor_id: str


class RunLogEntry(BaseModel):
    ts: datetime
    run_id: str
    dna_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    query_version: str = Field(..., pattern=r"^v[0-9]+$")
    status: RunStatus
    actor_type: ActorType
    actor_id: str
    sources: List[str] = Field(default_factory=list)
    retrieved_count: int = Field(default=0, ge=0)
    deduped_count: int = Field(default=0, ge=0)
    dedupe_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    pilot_n: int = Field(default=30, ge=20, le=50)
    labeled_count: int = Field(default=0, ge=0)
    include_count: int = Field(default=0, ge=0)
    exclude_count: int = Field(default=0, ge=0)
    unclear_count: int = Field(default=0, ge=0)
    precision_proxy: float = Field(default=0.0, ge=0.0, le=1.0)
    goldset_recall: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    goldset_hit_count: Optional[int] = Field(default=None, ge=0)
    goldset_total: Optional[int] = Field(default=None, ge=0)
    external_benchmark_recall: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    external_benchmark_hit_count: Optional[int] = Field(default=None, ge=0)
    external_benchmark_total: Optional[int] = Field(default=None, ge=0)
    top_reason_codes: List[str] = Field(default_factory=list)


class PilotRunArtifacts(BaseModel):
    run_id: str
    dna_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    run_dir: str
    query_version: str = Field(..., pattern=r"^v[0-9]+$")
    sources: List[str] = Field(default_factory=list)
    retrieved_count: int = Field(default=0, ge=0)
    deduped_count: int = Field(default=0, ge=0)
    dedupe_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    screening_queue_path: str
    metrics_path: str


class ScreeningLogEntry(BaseModel):
    ts: datetime
    dna_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    run_id: str
    candidate_id: str
    decision: ScreeningDecision
    reason_code: ReasonCode
    note: Optional[str] = None
    actor_type: ActorType
    actor_id: str


class ApprovalAuditEntry(BaseModel):
    ts: datetime
    dna_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    action: ApprovalAction
    actor_type: ActorType
    actor_id: str
    reason: str
    before_version: Optional[str] = Field(default=None, pattern=r"^v[0-9]+$")
    after_version: Optional[str] = Field(default=None, pattern=r"^v[0-9]+$")
    run_id: Optional[str] = None


class ExternalBenchmarkStudyDecision(BaseModel):
    source_reference: str
    title: str
    identifier: str
    decision: BenchmarkDecision
    reason: str
    local_overlap: bool = False
    note: Optional[str] = None


class ExternalBenchmarkManifest(BaseModel):
    schema_version: Literal["research_dna.external_benchmark_manifest.v1"] = (
        "research_dna.external_benchmark_manifest.v1"
    )
    manifest_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    dna_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    source_label: str
    source_url: str
    created_at: datetime
    created_by: str
    scope_note: str
    studies: List[ExternalBenchmarkStudyDecision] = Field(default_factory=list)
