from __future__ import annotations

from datetime import datetime
import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.schemas.paper_understanding_failures import (
    PAPER_UNDERSTANDING_FAILURE_DEFINITIONS,
    PaperUnderstandingFailureCode,
)


EvidenceGroundingScorecardStatus = Literal["pass", "warn", "fail"]
EvidenceGroundingMetricStatus = Literal["available", "not_available"]
EvidenceGroundingInputArtifactStatus = Literal["loaded", "missing", "load_failed"]
EvidenceGroundingPipelineStage = Literal[
    "extractor",
    "classifier",
    "grounding_checker",
    "consistency_checker",
    "parser",
    "metadata_resolver",
    "formatter",
    "unknown",
]
KNOWN_EVIDENCE_GROUNDING_PIPELINE_STAGES: tuple[str, ...] = (
    "extractor",
    "classifier",
    "grounding_checker",
    "consistency_checker",
    "parser",
    "metadata_resolver",
    "formatter",
    "unknown",
)
EvidenceGroundingFailureCode = PaperUnderstandingFailureCode
KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES: tuple[str, ...] = tuple(PAPER_UNDERSTANDING_FAILURE_DEFINITIONS)


class _StrictScorecardModel(BaseModel):
    model_config = {"extra": "forbid"}


def _reject_boolean_count(value: object, *, field_name: str) -> object:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer count, not a boolean")
    return value


class EvidenceGroundingMetric(_StrictScorecardModel):
    value: float | int | None = None
    status: EvidenceGroundingMetricStatus = "not_available"
    source: str | None = None
    detail: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean_value(cls, value):
        if isinstance(value, bool):
            raise ValueError("metric value must be numeric, not a boolean")
        if isinstance(value, str):
            raise ValueError("metric value must be a JSON number, not a string")
        if isinstance(value, (float, int)) and not math.isfinite(value):
            raise ValueError("metric value must be finite")
        return value

    @model_validator(mode="after")
    def validate_value_status(self):
        if self.status == "available" and self.value is None:
            raise ValueError("available metrics require a value")
        if self.status == "not_available" and self.value is not None:
            raise ValueError("not_available metrics must not carry a value")
        return self


class EvidenceGroundingInputArtifactDiagnostic(_StrictScorecardModel):
    artifact: str = Field(..., min_length=1)
    status: EvidenceGroundingInputArtifactStatus
    core_scorecard_input: bool = False
    detail: str | None = None

    @model_validator(mode="after")
    def normalize_diagnostic(self):
        self.artifact = self.artifact.strip()
        if not self.artifact:
            raise ValueError("artifact is required")
        if self.detail is not None:
            self.detail = self.detail.strip() or None
        return self


class EvidenceGroundingScorecardInputArtifactSummary(_StrictScorecardModel):
    source_artifact_count: int = Field(default=0, ge=0)
    input_artifact_diagnostic_count: int = Field(default=0, ge=0)
    core_input_artifact_count: int = Field(default=0, ge=0)
    loaded_core_input_artifact_count: int = Field(default=0, ge=0)
    missing_core_input_artifact_count: int = Field(default=0, ge=0)
    load_failed_core_input_artifact_count: int = Field(default=0, ge=0)
    non_core_input_artifact_count: int = Field(default=0, ge=0)

    @field_validator(
        "source_artifact_count",
        "input_artifact_diagnostic_count",
        "core_input_artifact_count",
        "loaded_core_input_artifact_count",
        "missing_core_input_artifact_count",
        "load_failed_core_input_artifact_count",
        "non_core_input_artifact_count",
        mode="before",
    )
    @classmethod
    def reject_boolean_counts(cls, value):
        return _reject_boolean_count(value, field_name="input_artifact_summary count")


class EvidenceGroundingRuntimeProxyMetrics(_StrictScorecardModel):
    input_artifact_coverage_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    missing_input_artifact_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    malformed_input_artifact_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    claim_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    evidence_span_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    grounded_evidence_ratio: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    unresolved_grounding_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    unsupported_claim_rate_proxy: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    unknown_claim_rate_proxy: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    low_overlap_claim_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    missing_location_claim_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    grounded_limitation_rate_proxy: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    page_coverage_ratio: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    missing_topic_signal_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    duplicate_cluster_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    evidence_extraction_record_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    evidence_backed_extraction_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    grounded_extraction_ref_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    visual_evidence_entry_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    visual_evidence_claim_link_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    visual_evidence_unknown_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    visual_evidence_unsupported_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    visual_not_allowed_claim_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    visual_direct_contradiction_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    claim_evidence_direct_contradiction_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    caption_only_figure_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    ambiguous_visual_panel_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    table_parse_failure_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    table_cell_value_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    figure_table_conflict_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    downstream_traceability_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    handoff_review_ready: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    handoff_check_pass_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    handoff_hard_fail_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    review_burden_per_paper: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    accepted_correction_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    correction_reuse_candidate_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    correction_feedback_link_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    reviewed_eval_fixture_count: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)


class EvidenceGroundingGoldScoredMetrics(_StrictScorecardModel):
    claim_precision: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    claim_recall: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    evidence_support_precision: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    locator_precision: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    unsupported_claim_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    overstatement_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    contradiction_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    limitation_recall: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    gap_recall: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    method_result_confusion_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    figure_reference_precision: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    table_reference_precision: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    table_cell_locator_precision: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    table_cell_value_accuracy: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    figure_caption_link_accuracy: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    figure_visual_text_accuracy: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    metadata_match_rate: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)
    parser_section_accuracy: EvidenceGroundingMetric = Field(default_factory=EvidenceGroundingMetric)


class EvidenceGroundingStageFailureSummary(_StrictScorecardModel):
    stage: EvidenceGroundingPipelineStage
    failure_count: int = Field(default=0, ge=0)
    failure_codes: list[EvidenceGroundingFailureCode] = Field(default_factory=list)
    detail: str | None = None

    @field_validator("failure_count", mode="before")
    @classmethod
    def reject_boolean_failure_count(cls, value):
        return _reject_boolean_count(value, field_name="failure_count")

    @model_validator(mode="after")
    def normalize_summary(self):
        self.failure_codes = [
            _validate_failure_code(code, field_name="failure_codes")
            for code in _dedupe_non_empty_strings(self.failure_codes, field_name="failure_codes")
        ]
        if self.detail is not None:
            self.detail = self.detail.strip() or None
        return self


class EvidenceGroundingStageMetricSummary(_StrictScorecardModel):
    stage: EvidenceGroundingPipelineStage
    runtime_proxy_metrics: dict[str, EvidenceGroundingMetric] = Field(default_factory=dict)
    gold_scored_metrics: dict[str, EvidenceGroundingMetric] = Field(default_factory=dict)
    available_metric_count: int = 0
    detail: str | None = None

    @model_validator(mode="after")
    def normalize_summary(self):
        self.runtime_proxy_metrics = _normalize_metric_dict(self.runtime_proxy_metrics)
        self.gold_scored_metrics = _normalize_metric_dict(self.gold_scored_metrics)
        self.available_metric_count = sum(
            1
            for metric in list(self.runtime_proxy_metrics.values()) + list(self.gold_scored_metrics.values())
            if metric.status == "available"
        )
        if self.detail is not None:
            self.detail = self.detail.strip() or None
        return self


class EvidenceGroundingCandidateConfig(_StrictScorecardModel):
    parser_version: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_model_version: str | None = None
    prompt_version: str | None = None
    reader_profile_version: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self):
        for field_name in (
            "parser_version",
            "llm_provider",
            "llm_model",
            "llm_model_version",
            "prompt_version",
            "reader_profile_version",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self

    def has_lineage(self) -> bool:
        return any(
            getattr(self, field_name)
            for field_name in (
                "parser_version",
                "llm_provider",
                "llm_model",
                "llm_model_version",
                "prompt_version",
                "reader_profile_version",
            )
        )

    def has_complete_replay_lineage(self) -> bool:
        return all(
            getattr(self, field_name)
            for field_name in (
                "parser_version",
                "llm_provider",
                "llm_model",
                "llm_model_version",
                "prompt_version",
                "reader_profile_version",
            )
        )


class EvidenceGroundingScorecardRepairTarget(_StrictScorecardModel):
    claim_id: str
    span_index: int = Field(ge=0)
    resolution: str | None = None
    grounded: bool | None = None
    page: int | None = None
    section: str | None = None
    chunk_id: str | None = None
    has_quote: bool = False
    has_raw_text: bool = False
    quote_char_count: int = Field(default=0, ge=0)
    raw_text_char_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize_target(self):
        self.claim_id = _normalize_required_string(self.claim_id, field_name="claim_id")
        for field_name in ("resolution", "section", "chunk_id"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, str(value).strip() or None)
        return self


class EvidenceGroundingScorecard(_StrictScorecardModel):
    schema_version: Literal["evidence_grounding_scorecard.v1"] = "evidence_grounding_scorecard.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    paper_id: str
    doc_id: str
    run_id: str
    source_artifacts: list[str] = Field(default_factory=list)
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] = Field(default_factory=list)
    input_artifact_summary: EvidenceGroundingScorecardInputArtifactSummary = Field(
        default_factory=EvidenceGroundingScorecardInputArtifactSummary
    )
    readiness_status: EvidenceGroundingScorecardStatus
    runtime_proxy_metrics: EvidenceGroundingRuntimeProxyMetrics = Field(
        default_factory=EvidenceGroundingRuntimeProxyMetrics
    )
    gold_scored_metrics: EvidenceGroundingGoldScoredMetrics = Field(default_factory=EvidenceGroundingGoldScoredMetrics)
    stage_metric_summary: list[EvidenceGroundingStageMetricSummary] = Field(default_factory=list)
    failure_counts_by_code: dict[str, int] = Field(default_factory=dict)
    stage_failure_summary: list[EvidenceGroundingStageFailureSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    repair_targets: list[EvidenceGroundingScorecardRepairTarget] = Field(default_factory=list)
    recommended_next_action: str
    candidate_config: EvidenceGroundingCandidateConfig | None = None

    @field_validator("failure_counts_by_code", mode="before")
    @classmethod
    def reject_boolean_failure_counts(cls, value):
        if isinstance(value, dict):
            for count in value.values():
                if isinstance(count, bool):
                    raise ValueError("failure_counts_by_code values must be integer counts, not booleans")
        return value

    @model_validator(mode="after")
    def normalize_lists(self):
        for field_name in ("paper_id", "doc_id", "run_id", "recommended_next_action"):
            setattr(self, field_name, _normalize_required_string(getattr(self, field_name), field_name=field_name))
        self.source_artifacts = _dedupe_non_empty_strings(self.source_artifacts, field_name="source_artifacts")
        expected_input_artifact_summary = EvidenceGroundingScorecardInputArtifactSummary(
            source_artifact_count=len(self.source_artifacts),
            input_artifact_diagnostic_count=len(self.input_artifact_diagnostics),
            core_input_artifact_count=sum(
                1 for diagnostic in self.input_artifact_diagnostics if diagnostic.core_scorecard_input
            ),
            loaded_core_input_artifact_count=sum(
                1
                for diagnostic in self.input_artifact_diagnostics
                if diagnostic.core_scorecard_input and diagnostic.status == "loaded"
            ),
            missing_core_input_artifact_count=sum(
                1
                for diagnostic in self.input_artifact_diagnostics
                if diagnostic.core_scorecard_input and diagnostic.status == "missing"
            ),
            load_failed_core_input_artifact_count=sum(
                1
                for diagnostic in self.input_artifact_diagnostics
                if diagnostic.core_scorecard_input and diagnostic.status == "load_failed"
            ),
            non_core_input_artifact_count=sum(
                1 for diagnostic in self.input_artifact_diagnostics if not diagnostic.core_scorecard_input
            ),
        )
        if (
            "input_artifact_summary" in self.model_fields_set
            and self.input_artifact_summary != expected_input_artifact_summary
        ):
            raise ValueError("input_artifact_summary must match source_artifacts and input_artifact_diagnostics")
        self.input_artifact_summary = expected_input_artifact_summary
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings")
        self.reason_codes = _dedupe_non_empty_strings(self.reason_codes, field_name="reason_codes")
        failure_counts_by_code: dict[str, int] = {}
        for code, count in sorted(self.failure_counts_by_code.items()):
            if not str(code).strip():
                continue
            normalized_count = int(count)
            if normalized_count < 0:
                raise ValueError("failure_counts_by_code values must be non-negative")
            if normalized_count > 0:
                failure_counts_by_code[
                    _validate_failure_code(code, field_name="failure_counts_by_code")
                ] = normalized_count
        self.failure_counts_by_code = failure_counts_by_code
        self.stage_failure_summary = [
            summary for summary in self.stage_failure_summary if summary.failure_count > 0
        ]
        self.stage_metric_summary = [
            summary for summary in self.stage_metric_summary if summary.available_metric_count > 0
        ]
        return self


class EvidenceGroundingScorecardBuildRequest(_StrictScorecardModel):
    run_dir: str = Field(..., min_length=1)
    out: str | None = None
    write: bool = True
    paper_understanding_gold_path: str | None = None
    candidate_config: EvidenceGroundingCandidateConfig | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.run_dir = self.run_dir.strip()
        if not self.run_dir:
            raise ValueError("run_dir is required")
        for field_name in ("out", "paper_understanding_gold_path"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class EvidenceGroundingScorecardInputBackfillItemRequest(_StrictScorecardModel):
    paper_id: str = Field(..., min_length=1)
    source_run_dir: str = Field(..., min_length=1)
    paper_understanding_gold_path: str | None = None
    run_id: str | None = None
    output_name: str | None = None

    @model_validator(mode="after")
    def normalize_item(self):
        self.paper_id = _normalize_required_string(self.paper_id, field_name="paper_id")
        self.source_run_dir = _normalize_required_string(self.source_run_dir, field_name="source_run_dir")
        for field_name in ("paper_understanding_gold_path", "run_id", "output_name"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class EvidenceGroundingScorecardInputBackfillRequest(_StrictScorecardModel):
    items: list[EvidenceGroundingScorecardInputBackfillItemRequest] = Field(default_factory=list)
    benchmark_manifest_paths: list[str] = Field(default_factory=list)
    benchmark_manifest_package_paths: list[str] = Field(default_factory=list)
    out_run_root: str = Field(..., min_length=1)
    out: str | None = None
    run_dir_map_out: str | None = None
    reviewed_fixtures_dir: str | None = None
    require_reviewed_fixtures: bool = False
    overwrite: bool = False
    write_scorecards: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        self.out_run_root = _normalize_required_string(self.out_run_root, field_name="out_run_root")
        self.benchmark_manifest_paths = _dedupe_non_empty_strings(
            self.benchmark_manifest_paths,
            field_name="benchmark_manifest_paths",
        )
        self.benchmark_manifest_package_paths = _dedupe_non_empty_strings(
            self.benchmark_manifest_package_paths,
            field_name="benchmark_manifest_package_paths",
        )
        if not self.items and not self.benchmark_manifest_paths and not self.benchmark_manifest_package_paths:
            raise ValueError(
                "items, benchmark_manifest_paths, or benchmark_manifest_package_paths "
                "must contain at least one run source"
            )
        for field_name in ("out", "run_dir_map_out", "reviewed_fixtures_dir"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self

class EvidenceGroundingScorecardInputBackfillItem(_StrictScorecardModel):
    paper_id: str
    source_run_dir: str
    output_run_dir: str
    status: Literal["pass", "fail"]
    generated_artifacts: list[str] = Field(default_factory=list)
    scorecard_readiness_status: EvidenceGroundingScorecardStatus | None = None
    scorecard_reason_codes: list[str] = Field(default_factory=list)
    scorecard_readiness_metrics: dict[str, EvidenceGroundingMetric] = Field(default_factory=dict)
    scorecard_repair_targets: list[EvidenceGroundingScorecardRepairTarget] = Field(default_factory=list)
    reviewed_eval_fixture_count: int | None = Field(default=None, ge=0)
    error: str | None = None

    @model_validator(mode="after")
    def normalize_item(self):
        for field_name in ("paper_id", "source_run_dir", "output_run_dir"):
            setattr(self, field_name, _normalize_required_string(getattr(self, field_name), field_name=field_name))
        self.generated_artifacts = _dedupe_non_empty_strings(
            self.generated_artifacts,
            field_name="generated_artifacts",
        )
        self.scorecard_reason_codes = _dedupe_non_empty_strings(
            self.scorecard_reason_codes,
            field_name="scorecard_reason_codes",
        )
        self.scorecard_readiness_metrics = {
            _normalize_required_string(name, field_name="scorecard_readiness_metrics"): metric
            for name, metric in sorted(self.scorecard_readiness_metrics.items())
        }
        if self.error is not None:
            self.error = self.error.strip() or None
        return self


class EvidenceGroundingScorecardInputBackfillReport(_StrictScorecardModel):
    schema_version: Literal["evidence_grounding_scorecard_input_backfill.v1"] = (
        "evidence_grounding_scorecard_input_backfill.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    out_run_root: str
    run_dir_map_path: str | None = None
    reviewed_fixtures_dir: str | None = None
    item_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    scorecard_pass_count: int = 0
    scorecard_warn_count: int = 0
    scorecard_fail_count: int = 0
    items: list[EvidenceGroundingScorecardInputBackfillItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.out_run_root = _normalize_required_string(self.out_run_root, field_name="out_run_root")
        if self.run_dir_map_path is not None:
            self.run_dir_map_path = self.run_dir_map_path.strip() or None
        if self.reviewed_fixtures_dir is not None:
            self.reviewed_fixtures_dir = self.reviewed_fixtures_dir.strip() or None
        self.item_count = len(self.items)
        self.pass_count = sum(1 for item in self.items if item.status == "pass")
        self.fail_count = sum(1 for item in self.items if item.status == "fail")
        self.scorecard_pass_count = sum(1 for item in self.items if item.scorecard_readiness_status == "pass")
        self.scorecard_warn_count = sum(1 for item in self.items if item.scorecard_readiness_status == "warn")
        self.scorecard_fail_count = sum(1 for item in self.items if item.scorecard_readiness_status == "fail")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings")
        return self


def _normalize_required_string(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _dedupe_non_empty_strings(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            raise ValueError(f"{field_name} entries must be non-empty")
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _normalize_metric_dict(values: dict[str, EvidenceGroundingMetric]) -> dict[str, EvidenceGroundingMetric]:
    return {
        str(name).strip(): metric
        for name, metric in sorted(values.items())
        if str(name).strip()
    }


def _validate_failure_code(raw: str, *, field_name: str) -> EvidenceGroundingFailureCode:
    code = str(raw or "").strip()
    if not code:
        raise ValueError(f"{field_name} entries must be non-empty")
    if code not in KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES:
        raise ValueError(f"unknown evidence grounding failure code: {code}")
    return code  # type: ignore[return-value]
