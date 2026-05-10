from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from src.profiles.research_dna_schema import (
    ActorType,
    InterviewLogEntry,
    InterviewRound,
    ResearchDNAResumeSnapshot,
    ResearchDNAScreeningRecommendation,
    ResearchDNAScreeningSession,
    PilotRunArtifacts,
    ResearchDNARunIndex,
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
    run_id: str | None = Field(default=None, min_length=1)
    latest_run: bool = False
    candidate_id: str = Field(..., min_length=1)
    decision: ScreeningDecision
    reason_code: ReasonCode
    note: str | None = None
    variant: str = Field(default="original", pattern="^(original|reranked)$")
    recent_limit: int = Field(default=5, ge=1, le=20)
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_run_selector(self) -> "ResearchDNAScreeningAdvanceRequest":
        if self.run_id and self.latest_run:
            raise ValueError("Provide either run_id or latest_run, not both")
        if not self.run_id and not self.latest_run:
            raise ValueError("Provide run_id or set latest_run=true")
        return self


class ResearchDNAScreenCurrentRequest(BaseModel):
    run_id: str | None = Field(default=None, min_length=1)
    latest_run: bool = False
    decision: ScreeningDecision
    reason_code: ReasonCode
    note: str | None = None
    variant: str = Field(default="original", pattern="^(original|reranked)$")
    recent_limit: int = Field(default=5, ge=1, le=20)
    expected_candidate_id: str | None = None
    actor_type: ActorType = "human_api"
    actor_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_run_selector(self) -> "ResearchDNAScreenCurrentRequest":
        if self.run_id and self.latest_run:
            raise ValueError("Provide either run_id or latest_run, not both")
        if not self.run_id and not self.latest_run:
            raise ValueError("Provide run_id or set latest_run=true")
        return self


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


class ResearchDNARunIndexEnvelope(BaseModel):
    run_index: ResearchDNARunIndex


class ResearchDNAResumeEnvelope(BaseModel):
    resume: ResearchDNAResumeSnapshot


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
