from __future__ import annotations

from hashlib import sha1
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


SkillActionName = Literal["extract_markdown", "validate_citations", "critical_appraisal"]
SkillRunStatus = Literal["succeeded", "failed", "blocked"]
SkillNetworkMode = Literal["none", "allowlist", "full"]


class SkillActionInfo(BaseModel):
    action: SkillActionName
    title: str
    button_label: str
    description: str
    source_skills: list[str] = Field(default_factory=list)
    license: str | None = None
    network: SkillNetworkMode = "none"
    sandbox: str | None = None
    secrets_required: list[str] = Field(default_factory=list)
    enabled: bool = True
    disabled_reason: str | None = None


def _normalize_id_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def _stable_id(prefix: str, *parts: Any) -> str:
    normalized = [_normalize_id_part(part) for part in parts]
    payload = "|".join(part for part in normalized if part)
    if not payload:
        payload = prefix
    return f"{prefix}_{sha1(payload.encode('utf-8')).hexdigest()[:12]}"


def _dedupe_id(raw_id: str, seen: set[str]) -> str:
    candidate = raw_id
    suffix = 2
    while candidate in seen:
        candidate = f"{raw_id}_{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def build_stable_claim_id(*parts: Any) -> str:
    return _stable_id("claim", *parts)


def build_stable_evidence_id(*parts: Any) -> str:
    return _stable_id("evidence", *parts)


class SkillEvidenceLocator(BaseModel):
    page: int | None = None
    span: list[int] = Field(default_factory=list)
    section: str | None = None
    chunk_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox_pdf: list[float] | None = None
    bbox_pct: dict[str, float] | None = None
    table_id: str | None = None
    cell_id: str | None = None
    source: str | None = None


class SkillClaimEvidence(BaseModel):
    id: str | None = None
    claim_id: str | None = None
    run_id: str | None = None
    text: str
    page: int | None = None
    section: str | None = None
    source: str | None = None
    grounded: bool | None = None
    resolution: str | None = None
    locator: SkillEvidenceLocator | None = None

    @model_validator(mode="after")
    def populate_locator(self):
        if self.locator is None:
            span = []
            locator_has_values = any(
                value is not None and value != ""
                for value in (self.page, self.section, self.source)
            )
            if locator_has_values:
                self.locator = SkillEvidenceLocator(
                    page=self.page,
                    span=span,
                    section=self.section,
                    source=self.source,
                )
        return self


class SkillClaimCard(BaseModel):
    id: str
    source_claim_id: str | None = None
    run_id: str | None = None
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: list[SkillClaimEvidence] = Field(default_factory=list)
    confidence: float | None = None
    tags: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_evidence_links(self):
        if not str(self.id).strip():
            self.id = build_stable_claim_id(self.claim, ",".join(self.tags))

        seen_ids: set[str] = set()
        evidence_ids: list[str] = []
        for evidence in self.evidence:
            if evidence.claim_id is None:
                evidence.claim_id = self.id
            if evidence.run_id is None and self.run_id is not None:
                evidence.run_id = self.run_id
            if evidence.locator is None:
                evidence.locator = SkillEvidenceLocator(
                    page=evidence.page,
                    section=evidence.section,
                    source=evidence.source,
                )
            if evidence.id is None:
                locator = evidence.locator
                evidence.id = build_stable_evidence_id(
                    self.id,
                    evidence.text,
                    getattr(locator, "page", None),
                    ",".join(str(item) for item in getattr(locator, "span", [])),
                    getattr(locator, "section", None),
                    getattr(locator, "chunk_id", None),
                    getattr(locator, "char_start", None),
                    getattr(locator, "char_end", None),
                    getattr(locator, "table_id", None),
                    getattr(locator, "cell_id", None),
                )
            evidence.id = _dedupe_id(evidence.id, seen_ids)
            evidence_ids.append(evidence.id)

        if not self.evidence_ids:
            self.evidence_ids = evidence_ids
        else:
            self.evidence_ids = [
                evidence_id
                for evidence_id in self.evidence_ids
                if isinstance(evidence_id, str) and evidence_id.strip()
            ] or evidence_ids
        return self


class SkillRunRecord(BaseModel):
    id: str
    action: SkillActionName
    ts: str
    status: SkillRunStatus
    summary: str
    artifacts: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class StructuredPaperState(BaseModel):
    schema_version: str = "2026-03-09.chat-hooks.v1"
    paper_slug: str
    updated_at: str
    runs: list[SkillRunRecord] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)
    claimset: list[SkillClaimCard] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    mesh: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_signals(self):
        signals = dict(self.signals)
        signals.setdefault("has_claimset", bool(self.claimset))
        signals.setdefault("claim_count", len(self.claimset))
        signals.setdefault("evidence_count", sum(len(claim.evidence) for claim in self.claimset))
        signals.setdefault("run_count", len(self.runs))
        if self.runs:
            signals.setdefault("last_run_id", self.runs[0].id)
            signals.setdefault("last_action", self.runs[0].action)
            signals.setdefault("last_status", self.runs[0].status)
        self.signals = signals
        return self


class SkillRunRequest(BaseModel):
    slug: str = Field(..., min_length=1)
    action: SkillActionName
    append_markdown_summary: bool = True
    force: bool = False


class SkillRunResponse(BaseModel):
    slug: str
    note_path: str
    structured_path: str
    run: SkillRunRecord
    state: StructuredPaperState
    frontmatter_pp: dict[str, Any] = Field(default_factory=dict)
