from __future__ import annotations

from pydantic import BaseModel, Field

from src.profiles.research_dna_schema import (
    ActorType,
    InterviewLogEntry,
    InterviewRound,
    ResearchDNAScreeningRecommendation,
    ResearchDNAScreeningSession,
    PilotRunArtifacts,
    ResearchDNANextScreeningCandidate,
    ResearchDNARerankGateReport,
    ResearchDNARerankArtifacts,
    ResearchDNAScreeningGuidanceArtifact,
    ResearchDNAScreeningGuidanceIndexArtifact,
    ResearchDNAScreeningProgressReport,
    ResearchDNAScreeningQueueArtifact,
    QueryVersion,
    ResearchDNA,
    ResearchDNAUpdate,
    ResearchIntent,
    ReasonCode,
    ScreeningDecision,
)
from src.profiles.profile_schema import Profile
from src.profiles.research_dna_projection import ResearchDNAProjectionResult


class ResearchDNAActorRequest(BaseModel):
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class ResearchDNACreateRequest(ResearchDNAActorRequest):
    topic: str = Field(..., min_length=1)
    intent: ResearchIntent
    dna_id: str | None = None
    title: str | None = None
    recommended_databases: list[str] = Field(default_factory=list)
    available_databases: list[str] = Field(default_factory=list)


class ResearchDNAPilotRunRequest(BaseModel):
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)
    run_id: str | None = None


class ResearchDNARerankRequest(BaseModel):
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)


class ResearchDNAGuidanceMaterializeRequest(BaseModel):
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)


class ResearchDNAScreeningRequest(BaseModel):
    run_id: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    decision: ScreeningDecision
    reason_code: ReasonCode
    note: str | None = None
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)


class ResearchDNAScreeningAdvanceRequest(BaseModel):
    run_id: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    decision: ScreeningDecision
    reason_code: ReasonCode
    note: str | None = None
    variant: str = Field(default="original", pattern="^(original|reranked)$")
    recent_limit: int = Field(default=5, ge=1, le=20)
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)


class ResearchDNAScreenCurrentRequest(BaseModel):
    run_id: str = Field(..., min_length=1)
    decision: ScreeningDecision
    reason_code: ReasonCode
    note: str | None = None
    variant: str = Field(default="original", pattern="^(original|reranked)$")
    recent_limit: int = Field(default=5, ge=1, le=20)
    expected_candidate_id: str | None = None
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)


class ResearchDNARefineRequest(ResearchDNAActorRequest):
    query_version: QueryVersion


class ResearchDNAUpdateRequest(ResearchDNAActorRequest):
    patch: ResearchDNAUpdate


class ResearchDNAProjectProfileRequest(ResearchDNAActorRequest):
    query_version: str | None = None
    database: str | None = None


class ResearchDNAInterviewRequest(BaseModel):
    round: InterviewRound
    question_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)


class ResearchDNAEnvelope(BaseModel):
    dna: ResearchDNA


class ResearchDNAPilotRunEnvelope(BaseModel):
    pilot_run: PilotRunArtifacts


class ResearchDNARerankEnvelope(BaseModel):
    rerank: ResearchDNARerankArtifacts


class ResearchDNAScreeningGuidanceArtifactEnvelope(BaseModel):
    guidance_artifact: ResearchDNAScreeningGuidanceArtifact


class ResearchDNAScreeningGuidanceIndexEnvelope(BaseModel):
    guidance_index: ResearchDNAScreeningGuidanceIndexArtifact


class ResearchDNAScreeningQueueEnvelope(BaseModel):
    screening_queue: ResearchDNAScreeningQueueArtifact


class ResearchDNANextScreeningCandidateEnvelope(BaseModel):
    next_candidate: ResearchDNANextScreeningCandidate


class ResearchDNAScreeningSessionEnvelope(BaseModel):
    session: ResearchDNAScreeningSession
    recommendation: ResearchDNAScreeningRecommendation
    gate: ResearchDNARerankGateReport


class ResearchDNAScreeningProgressEnvelope(BaseModel):
    progress: ResearchDNAScreeningProgressReport


class ResearchDNAScreeningRecommendationEnvelope(BaseModel):
    recommendation: ResearchDNAScreeningRecommendation


class ResearchDNARerankGateEnvelope(BaseModel):
    gate: ResearchDNARerankGateReport


class ResearchDNAScreeningGuidanceEnvelope(BaseModel):
    recommendation: ResearchDNAScreeningRecommendation
    gate: ResearchDNARerankGateReport


class ResearchDNAScreeningAdvanceEnvelope(BaseModel):
    dna: ResearchDNA
    next_candidate: ResearchDNANextScreeningCandidate
    session: ResearchDNAScreeningSession
    recommendation: ResearchDNAScreeningRecommendation
    gate: ResearchDNARerankGateReport
    screened_candidate_id: str
    decision: ScreeningDecision
    reason_code: ReasonCode
    variant: str


class ResearchDNAInterviewEnvelope(BaseModel):
    dna: ResearchDNA
    interview: InterviewLogEntry


class ResearchDNAProjectedProfileEnvelope(BaseModel):
    projection: ResearchDNAProjectionResult
