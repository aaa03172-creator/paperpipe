from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
import yaml


class ProbeTaxonomy(str, Enum):
    FIGURE_GROUNDING = "figure_grounding"
    TABLE_INTERPRETATION = "table_interpretation"
    CLAIM_EVIDENCE_SEPARATION = "claim_evidence_separation"
    METHOD_RECONSTRUCTION = "method_reconstruction"
    LIMITATION_DETECTION = "limitation_detection"
    REPRODUCIBILITY = "reproducibility"
    CITATION_PAGE_GROUNDING = "citation_page_grounding"
    UNSUPPORTED_UNKNOWN_LOGGING = "unsupported_unknown_logging"


class BinaryRubric(BaseModel):
    rubric_id: str
    description: str
    kind: Literal[
        "answer_contains_all",
        "answer_contains_any",
        "answer_not_contains",
        "claim_contains_all",
        "evidence_contains_any",
        "locator_present",
        "unknown_logged",
    ]
    terms: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_terms_for_kind(self) -> "BinaryRubric":
        if self.kind not in {"locator_present", "unknown_logged"} and not self.terms:
            raise ValueError(f"{self.kind} rubric requires at least one term")
        return self


class PaperSkillProbe(BaseModel):
    probe_id: str
    taxonomy: ProbeTaxonomy
    difficulty: Literal["easy", "hard"]
    source_layer: Literal["raw_source", "compiled_knowledge", "derived_artifact"] = "raw_source"
    payload_class: Literal["local_only", "lab_allowed", "external_allowed"] = "local_only"
    source_excerpt: str
    prompt: str
    rubrics: list[BinaryRubric]

    @model_validator(mode="after")
    def validate_probe_shape(self) -> "PaperSkillProbe":
        if not self.rubrics:
            raise ValueError("probe requires at least one binary rubric")
        if not self.source_excerpt.strip():
            raise ValueError("probe requires a source excerpt")
        return self


class ProbeLocator(BaseModel):
    page: int | None = None
    chunk_id: str | None = None
    table_id: str | None = None
    figure_id: str | None = None
    quote: str | None = None


class ProbeEvidence(BaseModel):
    text: str
    locator: ProbeLocator | None = None


class ProbeClaim(BaseModel):
    text: str
    evidence: list[ProbeEvidence] = Field(default_factory=list)


class ProbeAnswer(BaseModel):
    probe_id: str
    answer: str = ""
    claims: list[ProbeClaim] = Field(default_factory=list)
    evidence: list[ProbeEvidence] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ProbeAnswerTemplate(BaseModel):
    probe_id: str
    taxonomy: ProbeTaxonomy
    difficulty: Literal["easy", "hard"]
    prompt: str
    answer: str = ""
    claims: list[ProbeClaim] = Field(default_factory=list)
    evidence: list[ProbeEvidence] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class RubricVerdict(BaseModel):
    rubric_id: str
    passed: bool
    detail: str


class ProbeResult(BaseModel):
    probe_id: str
    taxonomy: ProbeTaxonomy
    difficulty: Literal["easy", "hard"]
    passed: bool
    pass_rate: float
    verdicts: list[RubricVerdict]


class ProbeSetReport(BaseModel):
    schema_version: str = "paper_skill_gym.report.v1"
    probe_count: int
    passed_count: int
    pass_rate: float
    hard_pass_rate: float
    easy_pass_rate: float
    replay_balance_score: float
    results: list[ProbeResult]


class ReportDelta(BaseModel):
    metric: str
    baseline: float
    candidate: float
    delta: float
    passed: bool
    detail: str


class ProbeRegression(BaseModel):
    probe_id: str
    baseline_passed: bool
    candidate_passed: bool
    failed_rubrics: list[str] = Field(default_factory=list)
    failure_tags: list[str] = Field(default_factory=list)


class ProbeSetComparison(BaseModel):
    schema_version: str = "paper_skill_gym.comparison.v1"
    decision: Literal["accept", "reject"]
    baseline_report: str | None = None
    candidate_report: str | None = None
    deltas: list[ReportDelta]
    regressions: list[ProbeRegression] = Field(default_factory=list)
    protected_rubric_regressions: list[ProbeRegression] = Field(default_factory=list)
    failure_summary: dict[str, int] = Field(default_factory=dict)
    suggested_actions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def load_probe(path: Path) -> PaperSkillProbe:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Probe YAML must contain an object: {path}")
    return PaperSkillProbe.model_validate(payload)


def load_probes(probes_dir: Path) -> list[PaperSkillProbe]:
    return [load_probe(path) for path in sorted(probes_dir.glob("*.yaml"))]


def load_answers(path: Path) -> dict[str, ProbeAnswer]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("answers file must contain a list")
    answers: dict[str, ProbeAnswer] = {}
    for item in raw:
        answer = ProbeAnswer.model_validate(item)
        answers[answer.probe_id] = answer
    return answers


def answer_template_from_probe(probe: PaperSkillProbe) -> ProbeAnswerTemplate:
    return ProbeAnswerTemplate(
        probe_id=probe.probe_id,
        taxonomy=probe.taxonomy,
        difficulty=probe.difficulty,
        prompt=probe.prompt,
    )


def answer_from_mapping(probe_id: str, payload: dict[str, Any] | None) -> ProbeAnswer:
    if payload is None:
        return ProbeAnswer(probe_id=probe_id)
    merged = {"probe_id": probe_id, **payload}
    return ProbeAnswer.model_validate(merged)


def load_probe_set_report(path: Path) -> ProbeSetReport:
    return ProbeSetReport.model_validate_json(path.read_text(encoding="utf-8"))
