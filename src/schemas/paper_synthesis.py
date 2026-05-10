from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .chat import ChatEvidenceRef


PaperSynthesisStatus = Literal["draft"]
PaperSynthesisReadiness = Literal["evidence_backed", "background_only", "mixed"]
PaperSynthesisFreshness = Literal["current", "stale", "unknown"]
PaperSynthesisArtifactFamily = Literal["paper_synthesis"]
PaperSynthesisTemplateKind = Literal["paper", "project", "meeting", "decision", "concept"]
PaperSynthesisRequiredSourceKind = Literal["structured_state", "claimset_resolved", "run_meta"]
PaperSynthesisReviewArtifactKind = Literal["quality_gate", "acceptance_contract", "visual_evidence_ledger"]
PaperSynthesisAnswerRoute = Literal["canonical_state_then_upstream_evidence"]
PaperSynthesisSourceKind = Literal[
    "structured_state",
    "claimset_resolved",
    "document_artifact",
    "paper_note_state",
    "quality_gate",
    "acceptance_contract",
    "visual_evidence_ledger",
    "run_meta",
]


class PaperSynthesisSourceRef(BaseModel):
    kind: PaperSynthesisSourceKind
    paper_slug: str = Field(..., min_length=1)
    run_id: str | None = None
    path: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.paper_slug = self.paper_slug.strip()
        if self.run_id is not None:
            self.run_id = self.run_id.strip() or None
        if self.path is not None:
            self.path = self.path.strip() or None
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class PaperSynthesisLineageSummary(BaseModel):
    minimum_required_source_kinds: list[PaperSynthesisRequiredSourceKind] = Field(
        default_factory=lambda: ["structured_state", "claimset_resolved", "run_meta"]
    )
    present_required_source_kinds: list[PaperSynthesisRequiredSourceKind] = Field(default_factory=list)
    review_artifact_kinds: list[PaperSynthesisReviewArtifactKind] = Field(default_factory=list)
    answer_route: PaperSynthesisAnswerRoute = "canonical_state_then_upstream_evidence"


class PaperSynthesis(BaseModel):
    synthesis_id: str = Field(..., pattern=r"^papersynth_[A-Za-z0-9._-]+$")
    paper_slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    created_at: datetime
    updated_at: datetime
    artifact_family: PaperSynthesisArtifactFamily = "paper_synthesis"
    template_kind: PaperSynthesisTemplateKind = "paper"
    layer: Literal["compiled_knowledge"] = "compiled_knowledge"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    status: PaperSynthesisStatus = "draft"
    readiness: PaperSynthesisReadiness = "background_only"
    freshness: PaperSynthesisFreshness = "unknown"
    summary: str | None = None
    source_refs: list[PaperSynthesisSourceRef] = Field(default_factory=list, min_length=1)
    evidence_refs: list[ChatEvidenceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    lineage_summary: PaperSynthesisLineageSummary = Field(default_factory=PaperSynthesisLineageSummary)

    @model_validator(mode="after")
    def normalize_values(self):
        self.paper_slug = self.paper_slug.strip()
        self.title = self.title.strip()
        if self.summary is not None:
            self.summary = self.summary.strip() or None
        self.source_refs = _dedupe_source_refs(self.source_refs)
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings")
        self.uncertainty_notes = _dedupe_non_empty_strings(
            self.uncertainty_notes,
            field_name="uncertainty_notes",
        )
        present_source_kinds = {ref.kind for ref in self.source_refs}
        required_source_kinds = {"structured_state", "claimset_resolved", "run_meta"}
        missing_source_kinds = sorted(required_source_kinds - present_source_kinds)
        if missing_source_kinds:
            raise ValueError(
                "PaperSynthesis.source_refs must include "
                + ", ".join(missing_source_kinds)
                + " for minimum upstream lineage."
            )
        self.lineage_summary = _build_lineage_summary(self.source_refs)
        if self.readiness == "background_only" and self.evidence_refs:
            raise ValueError("PaperSynthesis.readiness=background_only must not carry evidence_refs")
        if self.readiness == "mixed" and not self.evidence_refs:
            raise ValueError("PaperSynthesis.readiness=mixed requires at least one evidence_ref")
        if self.readiness == "evidence_backed":
            if not self.evidence_refs:
                raise ValueError("PaperSynthesis.readiness=evidence_backed requires at least one evidence_ref")
            if self.warnings or self.uncertainty_notes:
                raise ValueError(
                    "PaperSynthesis.readiness=evidence_backed cannot coexist with warnings or uncertainty_notes"
                )
        return self


class PaperSynthesisGenerateRequest(BaseModel):
    paper_slug: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_values(self):
        self.paper_slug = self.paper_slug.strip()
        return self


class PaperSynthesisResponse(BaseModel):
    synthesis: PaperSynthesis
    markdown: str


class PaperSynthesisListItem(BaseModel):
    synthesis_id: str = Field(..., min_length=1)
    paper_slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    updated_at: datetime
    artifact_family: PaperSynthesisArtifactFamily = "paper_synthesis"
    template_kind: PaperSynthesisTemplateKind = "paper"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    readiness: PaperSynthesisReadiness
    freshness: PaperSynthesisFreshness
    warning_count: int = Field(default=0, ge=0)
    source_ref_count: int = Field(default=0, ge=0)
    evidence_ref_count: int = Field(default=0, ge=0)
    lineage_summary: PaperSynthesisLineageSummary = Field(default_factory=PaperSynthesisLineageSummary)


class PaperSynthesisListResponse(BaseModel):
    items: list[PaperSynthesisListItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


def _dedupe_non_empty_strings(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            raise ValueError(f"{field_name} entries must be non-empty")
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


def _dedupe_source_refs(values: list[PaperSynthesisSourceRef]) -> list[PaperSynthesisSourceRef]:
    normalized: list[PaperSynthesisSourceRef] = []
    seen: set[tuple[str, str, str | None, str | None]] = set()
    for item in values:
        key = (item.kind, item.paper_slug, item.run_id, item.path)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _build_lineage_summary(source_refs: list[PaperSynthesisSourceRef]) -> PaperSynthesisLineageSummary:
    required_source_kinds: list[PaperSynthesisRequiredSourceKind] = [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    review_artifact_kinds: list[PaperSynthesisReviewArtifactKind] = [
        "quality_gate",
        "acceptance_contract",
        "visual_evidence_ledger",
    ]
    present_source_kinds = {item.kind for item in source_refs}
    return PaperSynthesisLineageSummary(
        minimum_required_source_kinds=required_source_kinds,
        present_required_source_kinds=[kind for kind in required_source_kinds if kind in present_source_kinds],
        review_artifact_kinds=[kind for kind in review_artifact_kinds if kind in present_source_kinds],
    )
