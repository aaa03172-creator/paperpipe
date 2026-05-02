from __future__ import annotations

from hashlib import sha1
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


SkillActionName = Literal["extract_markdown", "validate_citations", "critical_appraisal", "deep_read"]
SkillRunStatus = Literal["succeeded", "failed", "blocked"]
SkillNetworkMode = Literal["none", "allowlist", "full"]
ReadingAssistBlockKind = Literal["one_line_summary", "abstract", "critical_analysis"]
AppraisalCheckStatus = Literal["pass", "warn", "fail", "not_run"]
AppraisalConcernSeverity = Literal["info", "warn", "fail"]
SECTION_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


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


def _normalize_section_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return SECTION_KEY_PATTERN.sub("-", text).strip("-")


def build_section_signal_summary(claimset: list[SkillClaimCard]) -> list[dict[str, Any]]:
    sections: dict[str, dict[str, Any]] = {}
    for claim in claimset or []:
        claim_section_keys: set[str] = set()
        for index, evidence in enumerate(claim.evidence or []):
            locator = evidence.locator
            section_label = str(
                (getattr(locator, "section", None) if locator is not None else None)
                or evidence.section
                or ""
            ).strip()
            if not section_label:
                continue
            key = _normalize_section_key(section_label) or section_label.lower()
            if not key:
                continue

            section_entry = sections.get(key)
            if section_entry is None:
                section_entry = {
                    "key": key,
                    "label": section_label,
                    "claim_count": 0,
                    "evidence_count": 0,
                    "representative_claim_id": None,
                    "representative_evidence_id": None,
                    "pages": [],
                }

            if key not in claim_section_keys:
                section_entry["claim_count"] += 1
                claim_section_keys.add(key)
            section_entry["evidence_count"] += 1

            claim_id = str(claim.id or "").strip() or None
            if section_entry["representative_claim_id"] is None:
                section_entry["representative_claim_id"] = claim_id

            evidence_id = str(evidence.id or "").strip() or None
            if evidence_id is None and claim_id:
                evidence_id = f"{claim_id}-evidence-{index + 1}"
            if section_entry["representative_evidence_id"] is None:
                section_entry["representative_evidence_id"] = evidence_id

            page_value = getattr(locator, "page", None) if locator is not None else None
            if page_value is None:
                page_value = evidence.page
            if isinstance(page_value, int):
                section_entry["pages"].append(page_value)

            sections[key] = section_entry

    items: list[dict[str, Any]] = []
    for entry in sections.values():
        unique_pages = sorted(set(int(page) for page in entry.pop("pages", []) if isinstance(page, int)))
        items.append(
            {
                **entry,
                "page_start": unique_pages[0] if unique_pages else None,
                "page_end": unique_pages[-1] if unique_pages else None,
            }
        )

    return sorted(
        items,
        key=lambda item: (
            -int(item.get("evidence_count") or 0),
            -int(item.get("claim_count") or 0),
            str(item.get("label") or "").lower(),
        ),
    )


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


class CriticalAppraisalCheck(BaseModel):
    code: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    status: AppraisalCheckStatus
    detail: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_values(self):
        self.code = self.code.strip()
        self.label = self.label.strip()
        self.detail = self.detail.strip()
        return self


class CriticalAppraisalConcern(BaseModel):
    code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    detail: str = Field(..., min_length=1)
    severity: AppraisalConcernSeverity = "warn"
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_values(self):
        self.code = self.code.strip()
        self.title = self.title.strip()
        self.detail = self.detail.strip()
        self.claim_ids = [str(value).strip() for value in self.claim_ids if str(value).strip()]
        self.evidence_ids = [str(value).strip() for value in self.evidence_ids if str(value).strip()]
        self.source_artifacts = [str(value).strip() for value in self.source_artifacts if str(value).strip()]
        return self


class CriticalAppraisalQuestion(BaseModel):
    code: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_values(self):
        self.code = self.code.strip()
        self.question = self.question.strip()
        self.rationale = self.rationale.strip()
        self.claim_ids = [str(value).strip() for value in self.claim_ids if str(value).strip()]
        self.evidence_ids = [str(value).strip() for value in self.evidence_ids if str(value).strip()]
        return self


class CriticalAppraisalReport(BaseModel):
    schema_version: str = "critical_appraisal.v2"
    layer: Literal["review_gate"] = "review_gate"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    claim_count: int = 0
    evidence_count: int = 0
    avg_confidence: float = 0.0
    verified_checks: int = 0
    inconsistent_checks: int = 0
    checks: list[CriticalAppraisalCheck] = Field(default_factory=list)
    concerns: list[CriticalAppraisalConcern] = Field(default_factory=list)
    questions: list[CriticalAppraisalQuestion] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_values(self):
        self.label = self.label.strip()
        self.summary = self.summary.strip()
        self.claim_count = max(int(self.claim_count or 0), 0)
        self.evidence_count = max(int(self.evidence_count or 0), 0)
        self.verified_checks = max(int(self.verified_checks or 0), 0)
        self.inconsistent_checks = max(int(self.inconsistent_checks or 0), 0)
        self.avg_confidence = round(float(self.avg_confidence or 0.0), 4)
        self.warnings = [str(value).strip() for value in self.warnings if str(value).strip()]
        self.source_artifacts = [str(value).strip() for value in self.source_artifacts if str(value).strip()]
        return self


class SkillRunRecord(BaseModel):
    id: str
    action: SkillActionName
    ts: str
    status: SkillRunStatus
    summary: str
    artifacts: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class ReadingAssistProvenance(BaseModel):
    source_field: str = Field(..., min_length=1)
    source_locale: str = Field(default="en", min_length=2)
    translator: str | None = None
    model: str | None = None
    version: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.source_field = self.source_field.strip()
        self.source_locale = self.source_locale.strip().lower()
        if self.translator is not None:
            self.translator = self.translator.strip() or None
        if self.model is not None:
            self.model = self.model.strip() or None
        if self.version is not None:
            self.version = self.version.strip() or None
        return self


class ReadingAssistBlock(BaseModel):
    kind: ReadingAssistBlockKind
    text: str = Field(..., min_length=1)
    source_heading: str | None = None
    provenance: ReadingAssistProvenance | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.text = self.text.strip()
        if self.source_heading is not None:
            self.source_heading = self.source_heading.strip() or None
        return self


class ReadingAssistPayload(BaseModel):
    locale: str = Field(..., min_length=2)
    canonical_locale: str = Field(default="en", min_length=2)
    machine_translated: bool = True
    partial: bool = True
    blocks: list[ReadingAssistBlock] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_values(self):
        self.locale = self.locale.strip().lower()
        self.canonical_locale = self.canonical_locale.strip().lower()
        return self


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
    reading_assists: list[ReadingAssistPayload] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_signals(self):
        signals = dict(self.signals)
        section_summary = build_section_signal_summary(self.claimset)
        section_signal_detail = f"claimset_section_count={len(section_summary)}, summary_present={'true' if section_summary else 'false'}"
        reading_assist_locales: list[str] = []
        for payload in self.reading_assists:
            locale = str(payload.locale or "").strip().lower()
            if locale and payload.blocks and locale not in reading_assist_locales:
                reading_assist_locales.append(locale)
        signals.setdefault("has_claimset", bool(self.claimset))
        signals.setdefault("claim_count", len(self.claimset))
        signals.setdefault("evidence_count", sum(len(claim.evidence) for claim in self.claimset))
        signals.setdefault("run_count", len(self.runs))
        signals.setdefault("section_count", len(section_summary))
        signals.setdefault("has_reading_assists", bool(reading_assist_locales))
        signals.setdefault("reading_assist_count", len(reading_assist_locales))
        signals.setdefault("reading_assist_locales", reading_assist_locales)
        if self.runs:
            latest_run_data = dict(self.runs[0].data)
            if section_summary:
                latest_run_data["section_summary"] = section_summary
                latest_run_data["section_count"] = len(section_summary)
                latest_run_data.setdefault("section_navigation_signal_status", "pass")
                latest_run_data.setdefault("section_navigation_signal_detail", section_signal_detail)
                signals.setdefault("quality_gate_section_navigation_signal", "pass")
            else:
                latest_run_data.pop("section_summary", None)
                latest_run_data.pop("section_count", None)
            self.runs[0].data = latest_run_data
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
