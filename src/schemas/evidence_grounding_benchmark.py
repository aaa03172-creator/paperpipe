from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.evidence_grounding_scorecard import (
    EvidenceGroundingCandidateConfig,
    EvidenceGroundingScorecard,
    EvidenceGroundingFailureCode,
    EvidenceGroundingStageFailureSummary,
    KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES,
    KNOWN_EVIDENCE_GROUNDING_PIPELINE_STAGES,
)
from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGoldReleaseManifestBuildItem,
    PaperUnderstandingGoldReleasePackageReport,
)


EvidenceGroundingMetricDirection = Literal["higher_is_better", "lower_is_better"]
EvidenceGroundingFailureComparisonGroup = Literal["failure_counts_by_code", "stage_failure_summary"]
EvidenceGroundingMetricGatePolicy = Literal["all_comparable", "p0_gold", "explicit"]
EvidenceGroundingThresholdPolicy = Literal["none", "p0_gold_minimum", "explicit"]
EvidenceGroundingThresholdKind = Literal["minimum", "maximum"]
EvidenceGroundingThresholdStatus = Literal["passed", "failed", "not_available"]
EvidenceGroundingThresholdCalibrationPreset = Literal["p0_gold", "explicit"]
EvidenceGroundingContractReadinessStatus = Literal["pass", "warn", "fail"]
EvidenceGroundingFixedGoldsetRunReadinessStatus = Literal["pass", "fail"]
EvidenceGroundingThresholdAdoptionReviewStatus = Literal["pass", "warn", "fail"]
EvidenceGroundingRoadmapCompletionStatus = Literal["pass", "warn", "fail"]
_UNRESOLVED_COMMAND_PLACEHOLDER_RE = re.compile(r"<[^<>]+>")
EVIDENCE_GROUNDING_CORRECTION_EVIDENCE_PATH_DESCRIPTION = (
    "Optional claim/evidence correction evidence path. Accepts raw ClaimEvidenceCorrectionCase JSONL "
    "or a claim_evidence_eval_candidate_export.v1 JSON review artifact."
)


class EvidenceGroundingBenchmarkManifestItem(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    run_dir: str = Field(..., min_length=1)
    paper_id: str | None = None
    run_id: str | None = None
    candidate_config: EvidenceGroundingCandidateConfig | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceGroundingBenchmarkManifest(BaseModel):
    schema_version: Literal["evidence_grounding_benchmark_manifest.v1"] = (
        "evidence_grounding_benchmark_manifest.v1"
    )
    benchmark_id: str = Field(..., min_length=1)
    goldset_id: str | None = None
    goldset_split: str | None = None
    goldset_manifest_path: str | None = None
    items: list[EvidenceGroundingBenchmarkManifestItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_items(self):
        self.benchmark_id = self.benchmark_id.strip()
        if self.goldset_id is not None:
            self.goldset_id = self.goldset_id.strip() or None
        if self.goldset_split is not None:
            self.goldset_split = self.goldset_split.strip() or None
        if self.goldset_manifest_path is not None:
            self.goldset_manifest_path = self.goldset_manifest_path.strip() or None
        if not self.items:
            raise ValueError("benchmark manifest requires at least one item")
        return self


class EvidenceGroundingBenchmarkManifestFromGoldsetRequest(BaseModel):
    benchmark_id: str = Field(..., min_length=1)
    goldset_manifest_path: str = Field(..., min_length=1)
    run_root: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    run_dir_template: str = "{paper_id}"
    candidate_prefix: str = ""
    candidate_config: EvidenceGroundingCandidateConfig | None = None
    require_complete_candidate_config: bool = False
    require_ready: bool = True
    require_existing_runs: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        self.benchmark_id = self.benchmark_id.strip()
        self.goldset_manifest_path = self.goldset_manifest_path.strip()
        self.run_root = self.run_root.strip()
        self.out = self.out.strip()
        self.run_dir_template = self.run_dir_template.strip()
        self.candidate_prefix = self.candidate_prefix.strip()
        if not self.benchmark_id:
            raise ValueError("benchmark_id is required")
        if not self.goldset_manifest_path:
            raise ValueError("goldset_manifest_path is required")
        if not self.run_root:
            raise ValueError("run_root is required")
        if not self.out:
            raise ValueError("out is required")
        if not self.run_dir_template:
            raise ValueError("run_dir_template is required")
        return self


class EvidenceGroundingBenchmarkManifestFromStagedGoldRequest(BaseModel):
    benchmark_id: str = Field(..., min_length=1)
    staging_manifest_path: str = Field(..., min_length=1)
    goldset_id: str = Field(..., min_length=1)
    goldset_split: str = Field(..., min_length=1)
    goldset_manifest_out: str = Field(..., min_length=1)
    run_root: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    run_dir_template: str = "{paper_id}"
    candidate_prefix: str = ""
    candidate_config: EvidenceGroundingCandidateConfig | None = None
    require_complete_candidate_config: bool = False
    require_ready: bool = True
    require_existing_runs: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "benchmark_id",
            "staging_manifest_path",
            "goldset_id",
            "goldset_split",
            "goldset_manifest_out",
            "run_root",
            "out",
            "run_dir_template",
            "candidate_prefix",
        ):
            value = getattr(self, field_name)
            setattr(self, field_name, value.strip())
        if not self.benchmark_id:
            raise ValueError("benchmark_id is required")
        if not self.staging_manifest_path:
            raise ValueError("staging_manifest_path is required")
        if not self.goldset_id:
            raise ValueError("goldset_id is required")
        if not self.goldset_split:
            raise ValueError("goldset_split is required")
        if not self.goldset_manifest_out:
            raise ValueError("goldset_manifest_out is required")
        if not self.run_root:
            raise ValueError("run_root is required")
        if not self.out:
            raise ValueError("out is required")
        if not self.run_dir_template:
            raise ValueError("run_dir_template is required")
        return self


class EvidenceGroundingBenchmarkManifestPackage(BaseModel):
    schema_version: Literal["evidence_grounding_benchmark_manifest_package.v1"] = (
        "evidence_grounding_benchmark_manifest_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    package_id: str = Field(..., min_length=1)
    release_package_path: str = Field(..., min_length=1)
    release_package: PaperUnderstandingGoldReleasePackageReport
    run_root: str = Field(..., min_length=1)
    run_dir_template: str = "{paper_id}"
    out_dir: str = Field(..., min_length=1)
    benchmark_manifest_paths: list[str] = Field(default_factory=list)
    benchmark_manifests: list[EvidenceGroundingBenchmarkManifest] = Field(default_factory=list)
    manifest_count: int = Field(ge=0)
    item_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        self.package_id = self.package_id.strip()
        self.release_package_path = self.release_package_path.strip()
        self.run_root = self.run_root.strip()
        self.run_dir_template = self.run_dir_template.strip()
        self.out_dir = self.out_dir.strip()
        self.benchmark_manifest_paths = _dedupe_non_empty_strings(
            self.benchmark_manifest_paths,
            field_name="benchmark_manifest_paths",
        ) if self.benchmark_manifest_paths else []
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.release_package_path:
            raise ValueError("release_package_path is required")
        if not self.run_root:
            raise ValueError("run_root is required")
        if not self.run_dir_template:
            raise ValueError("run_dir_template is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        return self


class EvidenceGroundingBenchmarkManifestPackageFromReleasePackageRequest(BaseModel):
    release_package_path: str = Field(..., min_length=1)
    run_root: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    package_id: str = "evidence-grounding-benchmark-manifest-package"
    benchmark_id_prefix: str = "evidence-grounding"
    run_dir_template: str = "{paper_id}"
    run_dir_map_path: str | None = None
    candidate_prefix: str = ""
    candidate_config: EvidenceGroundingCandidateConfig | None = None
    require_complete_candidate_config: bool = False
    require_ready: bool = True
    require_existing_runs: bool = True
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "release_package_path",
            "run_root",
            "out_dir",
            "package_id",
            "benchmark_id_prefix",
            "run_dir_template",
            "candidate_prefix",
        ):
            value = getattr(self, field_name)
            setattr(self, field_name, value.strip())
        if not self.release_package_path:
            raise ValueError("release_package_path is required")
        if not self.run_root:
            raise ValueError("run_root is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.benchmark_id_prefix:
            raise ValueError("benchmark_id_prefix is required")
        if not self.run_dir_template:
            raise ValueError("run_dir_template is required")
        if self.run_dir_map_path is not None:
            self.run_dir_map_path = self.run_dir_map_path.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingBenchmarkRunDirMap(BaseModel):
    schema_version: Literal["evidence_grounding_benchmark_run_dir_map.v1"] = (
        "evidence_grounding_benchmark_run_dir_map.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    benchmark_manifest_package_path: str = Field(..., min_length=1)
    out: str | None = None
    item_count: int = Field(ge=0)
    run_dir_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_run_dir_map(self):
        self.benchmark_manifest_package_path = self.benchmark_manifest_package_path.strip()
        if self.out is not None:
            self.out = self.out.strip() or None
        if not self.benchmark_manifest_package_path:
            raise ValueError("benchmark_manifest_package_path is required")
        self.run_dir_map = {
            str(paper_id).strip(): str(run_dir).strip()
            for paper_id, run_dir in sorted(self.run_dir_map.items())
            if str(paper_id).strip() and str(run_dir).strip()
        }
        if self.item_count != len(self.run_dir_map):
            raise ValueError("item_count must match run_dir_map size")
        return self


class EvidenceGroundingBenchmarkRunDirMapRequest(BaseModel):
    benchmark_manifest_package_path: str = Field(..., min_length=1)
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.benchmark_manifest_package_path = self.benchmark_manifest_package_path.strip()
        if not self.benchmark_manifest_package_path:
            raise ValueError("benchmark_manifest_package_path is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingBenchmarkRunDirMapDiscovery(BaseModel):
    schema_version: Literal["evidence_grounding_benchmark_run_dir_map_discovery.v1"] = (
        "evidence_grounding_benchmark_run_dir_map_discovery.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    release_package_path: str = Field(..., min_length=1)
    run_root: str = Field(..., min_length=1)
    out: str | None = None
    required_artifacts: list[str] = Field(default_factory=list)
    requested_paper_count: int = Field(ge=0)
    selected_run_dir_count: int = Field(ge=0)
    missing_paper_count: int = Field(ge=0)
    missing_paper_ids: list[str] = Field(default_factory=list)
    run_dir_map: dict[str, str] = Field(default_factory=dict)
    candidate_alternate_run_dirs: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_discovery(self):
        self.release_package_path = self.release_package_path.strip()
        self.run_root = self.run_root.strip()
        if self.out is not None:
            self.out = self.out.strip() or None
        if not self.release_package_path:
            raise ValueError("release_package_path is required")
        if not self.run_root:
            raise ValueError("run_root is required")
        self.required_artifacts = [
            str(item).strip() for item in self.required_artifacts if str(item).strip()
        ]
        self.missing_paper_ids = sorted(
            {str(item).strip() for item in self.missing_paper_ids if str(item).strip()}
        )
        self.run_dir_map = {
            str(paper_id).strip(): str(run_dir).strip()
            for paper_id, run_dir in sorted(self.run_dir_map.items())
            if str(paper_id).strip() and str(run_dir).strip()
        }
        self.candidate_alternate_run_dirs = {
            str(paper_id).strip(): sorted(
                {str(run_dir).strip() for run_dir in run_dirs if str(run_dir).strip()}
            )
            for paper_id, run_dirs in sorted(self.candidate_alternate_run_dirs.items())
            if str(paper_id).strip()
        }
        self.candidate_alternate_run_dirs = {
            paper_id: run_dirs
            for paper_id, run_dirs in self.candidate_alternate_run_dirs.items()
            if run_dirs
        }
        if self.selected_run_dir_count != len(self.run_dir_map):
            raise ValueError("selected_run_dir_count must match run_dir_map size")
        if self.missing_paper_count != len(self.missing_paper_ids):
            raise ValueError("missing_paper_count must match missing_paper_ids size")
        if self.requested_paper_count != self.selected_run_dir_count + self.missing_paper_count:
            raise ValueError("requested_paper_count must match selected plus missing paper counts")
        return self


class EvidenceGroundingBenchmarkRunDirMapDiscoveryRequest(BaseModel):
    release_package_path: str = Field(..., min_length=1)
    run_root: str = Field(..., min_length=1)
    out: str | None = None
    report_out: str | None = None
    required_artifacts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_request(self):
        self.release_package_path = self.release_package_path.strip()
        self.run_root = self.run_root.strip()
        if not self.release_package_path:
            raise ValueError("release_package_path is required")
        if not self.run_root:
            raise ValueError("run_root is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        if self.report_out is not None:
            self.report_out = self.report_out.strip() or None
        self.required_artifacts = [
            str(item).strip() for item in self.required_artifacts if str(item).strip()
        ]
        return self


class EvidenceGroundingCandidateLineagePatchTemplateRecord(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    paper_id: str | None = None
    run_id: str | None = None
    run_dir: str = Field(..., min_length=1)
    missing_replay_fields: list[str] = Field(default_factory=list)
    available_replay_context: dict[str, str] = Field(default_factory=dict)
    suggested_lineage_values: dict[str, str] = Field(default_factory=dict)
    patch_fields: dict[str, str] = Field(default_factory=dict)
    source_candidate_config: dict[str, Any] = Field(default_factory=dict)
    review_required: bool = True
    notes: str = "Fill missing replay lineage from evidence-backed source context before rebuilding manifests."

    @model_validator(mode="after")
    def normalize_record(self):
        self.candidate_id = self.candidate_id.strip()
        self.paper_id = self.paper_id.strip() if self.paper_id is not None else None
        self.run_id = self.run_id.strip() if self.run_id is not None else None
        self.run_dir = self.run_dir.strip()
        self.missing_replay_fields = _dedupe_non_empty_strings(
            self.missing_replay_fields,
            field_name="missing_replay_fields",
        )
        self.available_replay_context = {
            str(key).strip(): str(value).strip()
            for key, value in sorted(self.available_replay_context.items())
            if str(key).strip() and str(value).strip()
        }
        self.suggested_lineage_values = {
            str(key).strip(): str(value).strip()
            for key, value in sorted(self.suggested_lineage_values.items())
            if str(key).strip() and str(value).strip()
        }
        self.patch_fields = {
            str(key).strip(): str(value).strip()
            for key, value in sorted(self.patch_fields.items())
            if str(key).strip()
        }
        self.source_candidate_config = {
            str(key).strip(): value
            for key, value in sorted(self.source_candidate_config.items())
            if str(key).strip() and value is not None
        }
        if not self.candidate_id:
            raise ValueError("candidate_id is required")
        if not self.run_dir:
            raise ValueError("run_dir is required")
        return self


class EvidenceGroundingCandidateLineagePatchTemplate(BaseModel):
    schema_version: Literal["evidence_grounding_candidate_lineage_patch_template.v1"] = (
        "evidence_grounding_candidate_lineage_patch_template.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    benchmark_manifest_package_path: str = Field(..., min_length=1)
    target_count: int = Field(ge=0)
    records: list[EvidenceGroundingCandidateLineagePatchTemplateRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_template(self):
        self.benchmark_manifest_package_path = self.benchmark_manifest_package_path.strip()
        if not self.benchmark_manifest_package_path:
            raise ValueError("benchmark_manifest_package_path is required")
        if self.target_count != len(self.records):
            raise ValueError("target_count must match records size")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingPatchTemplateFillReadinessRecord(BaseModel):
    record_ref: str = Field(..., min_length=1)
    missing_replay_fields: list[str] = Field(default_factory=list)
    patch_field_names: list[str] = Field(default_factory=list)
    blank_patch_fields: list[str] = Field(default_factory=list)
    filled_patch_fields: list[str] = Field(default_factory=list)
    suggested_field_names: list[str] = Field(default_factory=list)
    suggested_values: dict[str, str] = Field(default_factory=dict)
    missing_suggestion_fields: list[str] = Field(default_factory=list)
    available_context_keys: list[str] = Field(default_factory=list)
    review_required: bool = True
    ready_for_human_fill_review: bool = False

    @model_validator(mode="after")
    def normalize_record(self):
        self.record_ref = self.record_ref.strip()
        if not self.record_ref:
            raise ValueError("record_ref is required")
        self.missing_replay_fields = _dedupe_non_empty_strings(
            self.missing_replay_fields,
            field_name="missing_replay_fields",
        )
        self.patch_field_names = _dedupe_non_empty_strings(
            self.patch_field_names,
            field_name="patch_field_names",
        )
        self.blank_patch_fields = _dedupe_non_empty_strings(
            self.blank_patch_fields,
            field_name="blank_patch_fields",
        )
        self.filled_patch_fields = _dedupe_non_empty_strings(
            self.filled_patch_fields,
            field_name="filled_patch_fields",
        )
        self.suggested_field_names = _dedupe_non_empty_strings(
            self.suggested_field_names,
            field_name="suggested_field_names",
        )
        self.suggested_values = {
            str(key).strip(): str(value).strip()
            for key, value in sorted(self.suggested_values.items())
            if str(key).strip() and str(value).strip()
        }
        self.missing_suggestion_fields = _dedupe_non_empty_strings(
            self.missing_suggestion_fields,
            field_name="missing_suggestion_fields",
        )
        self.available_context_keys = _dedupe_non_empty_strings(
            self.available_context_keys,
            field_name="available_context_keys",
        )
        return self


class EvidenceGroundingPatchTemplateFillReadinessReport(BaseModel):
    schema_version: Literal["evidence_grounding_patch_template_fill_readiness.v1"] = (
        "evidence_grounding_patch_template_fill_readiness.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_patch_template_path: str = Field(..., min_length=1)
    source_patch_template_schema_version: Literal[
        "evidence_grounding_candidate_lineage_patch_template.v1",
        "claim_evidence_correction_repair_patch_template.v1",
    ]
    target_count: int = Field(ge=0)
    record_count: int = Field(ge=0)
    blank_patch_field_count: int = Field(ge=0)
    filled_patch_field_count: int = Field(ge=0)
    missing_suggestion_field_count: int = Field(ge=0)
    ready_record_count: int = Field(ge=0)
    ready_for_human_fill_review: bool = False
    records: list[EvidenceGroundingPatchTemplateFillReadinessRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.source_patch_template_path = self.source_patch_template_path.strip()
        if not self.source_patch_template_path:
            raise ValueError("source_patch_template_path is required")
        if self.record_count != len(self.records):
            raise ValueError("record_count must match records size")
        if self.blank_patch_field_count != sum(len(record.blank_patch_fields) for record in self.records):
            raise ValueError("blank_patch_field_count must match records")
        if self.filled_patch_field_count != sum(len(record.filled_patch_fields) for record in self.records):
            raise ValueError("filled_patch_field_count must match records")
        if self.missing_suggestion_field_count != sum(
            len(record.missing_suggestion_fields) for record in self.records
        ):
            raise ValueError("missing_suggestion_field_count must match records")
        if self.ready_record_count != sum(1 for record in self.records if record.ready_for_human_fill_review):
            raise ValueError("ready_record_count must match records")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingPatchTemplateFillTask(BaseModel):
    task_id: str = Field(..., min_length=1)
    record_ref: str = Field(..., min_length=1)
    field_name: str = Field(..., min_length=1)
    suggested_value: str | None = None
    available_context_keys: list[str] = Field(default_factory=list)
    available_context_values: dict[str, str] = Field(default_factory=dict)
    filled_patch_fields: list[str] = Field(default_factory=list)
    review_required: bool = True

    @model_validator(mode="after")
    def normalize_task(self):
        self.task_id = self.task_id.strip()
        self.record_ref = self.record_ref.strip()
        self.field_name = self.field_name.strip()
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.record_ref:
            raise ValueError("record_ref is required")
        if not self.field_name:
            raise ValueError("field_name is required")
        if self.suggested_value is not None:
            self.suggested_value = self.suggested_value.strip() or None
        self.available_context_keys = _dedupe_non_empty_strings(
            self.available_context_keys,
            field_name="available_context_keys",
        )
        self.available_context_values = {
            str(key).strip(): str(value).strip()
            for key, value in sorted(self.available_context_values.items())
            if str(key).strip() and str(value).strip()
        }
        self.filled_patch_fields = _dedupe_non_empty_strings(
            self.filled_patch_fields,
            field_name="filled_patch_fields",
        )
        return self


class EvidenceGroundingPatchTemplateFillTaskExport(BaseModel):
    schema_version: Literal["evidence_grounding_patch_template_fill_task_export.v1"] = (
        "evidence_grounding_patch_template_fill_task_export.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_fill_readiness_path: str = Field(..., min_length=1)
    source_patch_template_path: str = Field(..., min_length=1)
    task_export_csv_path: str | None = None
    task_export_markdown_path: str | None = None
    source_patch_template_schema_version: Literal[
        "evidence_grounding_candidate_lineage_patch_template.v1",
        "claim_evidence_correction_repair_patch_template.v1",
    ]
    record_count: int = Field(ge=0)
    task_count: int = Field(ge=0)
    suggested_task_count: int = Field(ge=0)
    missing_suggestion_task_count: int = Field(ge=0)
    tasks: list[EvidenceGroundingPatchTemplateFillTask] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_export(self):
        self.source_fill_readiness_path = self.source_fill_readiness_path.strip()
        self.source_patch_template_path = self.source_patch_template_path.strip()
        if self.task_export_csv_path is not None:
            self.task_export_csv_path = self.task_export_csv_path.strip() or None
        if self.task_export_markdown_path is not None:
            self.task_export_markdown_path = self.task_export_markdown_path.strip() or None
        if not self.source_fill_readiness_path:
            raise ValueError("source_fill_readiness_path is required")
        if not self.source_patch_template_path:
            raise ValueError("source_patch_template_path is required")
        if self.task_count != len(self.tasks):
            raise ValueError("task_count must match tasks size")
        if self.suggested_task_count != sum(1 for task in self.tasks if task.suggested_value):
            raise ValueError("suggested_task_count must match tasks")
        if self.missing_suggestion_task_count != sum(1 for task in self.tasks if not task.suggested_value):
            raise ValueError("missing_suggestion_task_count must match tasks")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingPatchTemplateFillTaskExportRequest(BaseModel):
    fill_readiness_path: str = Field(..., min_length=1)
    out: str | None = None
    csv_out: str | None = None
    markdown_out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in ("fill_readiness_path", "out", "csv_out", "markdown_out"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if not self.fill_readiness_path:
            raise ValueError("fill_readiness_path is required")
        return self


class EvidenceGroundingPatchTemplateFillReviewStatusItem(BaseModel):
    task_id: str = Field(..., min_length=1)
    record_ref: str = Field(..., min_length=1)
    field_name: str = Field(..., min_length=1)
    suggested_value: str | None = None
    available_context_keys: list[str] = Field(default_factory=list)
    available_context_values: dict[str, str] = Field(default_factory=dict)
    filled_patch_fields: list[str] = Field(default_factory=list)
    status: Literal["pass", "fail"]
    has_reviewer_value: bool = False
    has_reviewer_evidence: bool = False
    findings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_item(self):
        self.task_id = self.task_id.strip()
        self.record_ref = self.record_ref.strip()
        self.field_name = self.field_name.strip()
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.record_ref:
            raise ValueError("record_ref is required")
        if not self.field_name:
            raise ValueError("field_name is required")
        if self.suggested_value is not None:
            self.suggested_value = self.suggested_value.strip() or None
        self.available_context_keys = _dedupe_non_empty_strings(
            self.available_context_keys,
            field_name="available_context_keys",
        )
        self.available_context_values = {
            str(key).strip(): str(value).strip()
            for key, value in sorted(self.available_context_values.items())
            if str(key).strip() and str(value).strip()
        }
        self.filled_patch_fields = _dedupe_non_empty_strings(
            self.filled_patch_fields,
            field_name="filled_patch_fields",
        )
        self.findings = _dedupe_non_empty_strings(self.findings, field_name="findings") if self.findings else []
        return self


class EvidenceGroundingPatchTemplateFillReviewStatusReport(BaseModel):
    schema_version: Literal["evidence_grounding_patch_template_fill_review_status.v1"] = (
        "evidence_grounding_patch_template_fill_review_status.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_task_export_path: str = Field(..., min_length=1)
    reviewed_csv_path: str = Field(..., min_length=1)
    annotated_csv_path: str | None = None
    open_csv_path: str | None = None
    open_record_csv_path: str | None = None
    source_patch_template_path: str = Field(..., min_length=1)
    source_patch_template_schema_version: Literal[
        "evidence_grounding_candidate_lineage_patch_template.v1",
        "claim_evidence_correction_repair_patch_template.v1",
    ]
    task_count: int = Field(ge=0)
    reviewed_value_count: int = Field(ge=0)
    missing_value_count: int = Field(ge=0)
    missing_evidence_count: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    open_csv_row_count: int | None = Field(default=None, ge=0)
    missing_value_count_by_field: dict[str, int] = Field(default_factory=dict)
    missing_evidence_count_by_field: dict[str, int] = Field(default_factory=dict)
    suggested_value_count_by_field: dict[str, int] = Field(default_factory=dict)
    missing_suggestion_count_by_field: dict[str, int] = Field(default_factory=dict)
    missing_suggestion_task_ids_by_field: dict[str, list[str]] = Field(default_factory=dict)
    available_context_count_by_field: dict[str, int] = Field(default_factory=dict)
    missing_context_count_by_field: dict[str, int] = Field(default_factory=dict)
    missing_context_task_ids_by_field: dict[str, list[str]] = Field(default_factory=dict)
    available_context_keys_by_field: dict[str, list[str]] = Field(default_factory=dict)
    available_context_values_by_field: dict[str, list[str]] = Field(default_factory=dict)
    fail_count_by_field: dict[str, int] = Field(default_factory=dict)
    open_record_count: int = Field(default=0, ge=0)
    open_record_refs: list[str] = Field(default_factory=list)
    open_field_names_by_record_ref: dict[str, list[str]] = Field(default_factory=dict)
    open_task_ids: list[str] = Field(default_factory=list)
    open_task_ids_by_field: dict[str, list[str]] = Field(default_factory=dict)
    open_task_ids_by_record_ref: dict[str, list[str]] = Field(default_factory=dict)
    open_record_filled_patch_field_counts_by_field: dict[str, int] = Field(default_factory=dict)
    open_record_filled_patch_fields_by_record_ref: dict[str, list[str]] = Field(default_factory=dict)
    ready_for_apply: bool = False
    items: list[EvidenceGroundingPatchTemplateFillReviewStatusItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        def count_by_field(predicate) -> dict[str, int]:
            counts: dict[str, int] = {}
            for item in self.items:
                if predicate(item):
                    counts[item.field_name] = counts.get(item.field_name, 0) + 1
            return dict(sorted(counts.items()))

        def normalize_count_map(value: dict[str, int]) -> dict[str, int]:
            return {
                str(key).strip(): int(count)
                for key, count in sorted(value.items())
                if str(key).strip() and int(count) > 0
            }

        def default_missing_value_hint_split_maps() -> tuple[dict[str, int], dict[str, int]]:
            with_hint: dict[str, int] = {}
            without_hint: dict[str, int] = {}
            for field_name, missing_count in self.merged_missing_value_counts_by_field.items():
                hinted_count = min(
                    missing_count,
                    self.merged_reviewer_value_hint_counts_by_field.get(field_name, 0),
                )
                if hinted_count > 0:
                    with_hint[field_name] = hinted_count
                remaining_count = missing_count - hinted_count
                if remaining_count > 0:
                    without_hint[field_name] = remaining_count
            return with_hint, without_hint

        def context_keys_by_field() -> dict[str, list[str]]:
            values: dict[str, set[str]] = {}
            for item in self.items:
                for key in item.available_context_values:
                    values.setdefault(item.field_name, set()).add(str(key).strip())
            return {
                field_name: sorted(key for key in keys if key)
                for field_name, keys in sorted(values.items())
                if keys
            }

        def context_values_by_field() -> dict[str, list[str]]:
            values: dict[str, set[str]] = {}
            for item in self.items:
                for raw_key, raw_value in item.available_context_values.items():
                    key = str(raw_key).strip()
                    value = str(raw_value).strip()
                    if key and value:
                        values.setdefault(item.field_name, set()).add(f"{key}={value}")
            return {
                field_name: sorted(context_values)
                for field_name, context_values in sorted(values.items())
                if context_values
            }

        def normalize_key_list_map(value: dict[str, list[str]]) -> dict[str, list[str]]:
            normalized: dict[str, list[str]] = {}
            for raw_key, raw_values in sorted(value.items()):
                key = str(raw_key).strip()
                if not key:
                    continue
                values = _dedupe_non_empty_strings(
                    [str(item) for item in raw_values],
                    field_name=f"available_context_keys_by_field.{key}",
                )
                if values:
                    normalized[key] = values
            return normalized

        expected_open_task_ids = [
            item.task_id for item in self.items if item.status == "fail"
        ]
        expected_open_record_refs = sorted(
            {item.record_ref for item in self.items if item.status == "fail"}
        )
        expected_open_field_names_by_record_ref: dict[str, list[str]] = {}
        expected_open_task_ids_by_record_ref: dict[str, list[str]] = {}
        expected_open_task_ids_by_field: dict[str, list[str]] = {}
        expected_open_record_filled_patch_fields_by_record_ref: dict[str, set[str]] = {}
        for item in self.items:
            if item.status != "fail":
                continue
            expected_open_field_names_by_record_ref.setdefault(
                item.record_ref,
                [],
            ).append(item.field_name)
            expected_open_task_ids_by_record_ref.setdefault(
                item.record_ref,
                [],
            ).append(item.task_id)
            expected_open_task_ids_by_field.setdefault(item.field_name, []).append(
                item.task_id
            )
            if item.filled_patch_fields:
                expected_open_record_filled_patch_fields_by_record_ref.setdefault(
                    item.record_ref,
                    set(),
                ).update(item.filled_patch_fields)
        expected_open_field_names_by_record_ref = {
            record_ref: sorted(set(field_names))
            for record_ref, field_names in sorted(
                expected_open_field_names_by_record_ref.items()
            )
            if field_names
        }
        expected_open_task_ids_by_record_ref = {
            record_ref: sorted(task_ids)
            for record_ref, task_ids in sorted(
                expected_open_task_ids_by_record_ref.items()
            )
            if task_ids
        }
        expected_open_task_ids_by_field = {
            field_name: sorted(task_ids)
            for field_name, task_ids in sorted(expected_open_task_ids_by_field.items())
            if task_ids
        }
        expected_open_record_filled_patch_fields_by_record_ref_normalized = {
            record_ref: sorted(field_names)
            for record_ref, field_names in sorted(
                expected_open_record_filled_patch_fields_by_record_ref.items()
            )
            if field_names
        }
        expected_open_record_filled_patch_field_counts_by_field: dict[str, int] = {}
        for field_names in expected_open_record_filled_patch_fields_by_record_ref_normalized.values():
            for field_name in field_names:
                expected_open_record_filled_patch_field_counts_by_field[field_name] = (
                    expected_open_record_filled_patch_field_counts_by_field.get(field_name, 0) + 1
                )
        expected_open_record_filled_patch_field_counts_by_field = dict(
            sorted(expected_open_record_filled_patch_field_counts_by_field.items())
        )
        self.source_task_export_path = self.source_task_export_path.strip()
        self.reviewed_csv_path = self.reviewed_csv_path.strip()
        if self.annotated_csv_path is not None:
            self.annotated_csv_path = self.annotated_csv_path.strip() or None
        if self.open_csv_path is not None:
            self.open_csv_path = self.open_csv_path.strip() or None
        if self.open_record_csv_path is not None:
            self.open_record_csv_path = self.open_record_csv_path.strip() or None
        self.source_patch_template_path = self.source_patch_template_path.strip()
        if not self.source_task_export_path:
            raise ValueError("source_task_export_path is required")
        if not self.reviewed_csv_path:
            raise ValueError("reviewed_csv_path is required")
        if not self.source_patch_template_path:
            raise ValueError("source_patch_template_path is required")
        if self.task_count != len(self.items):
            raise ValueError("task_count must match items size")
        if self.reviewed_value_count != sum(1 for item in self.items if item.has_reviewer_value):
            raise ValueError("reviewed_value_count must match items")
        if self.missing_value_count != sum(1 for item in self.items if not item.has_reviewer_value):
            raise ValueError("missing_value_count must match items")
        if self.missing_evidence_count != sum(
            1 for item in self.items if item.has_reviewer_value and not item.has_reviewer_evidence
        ):
            raise ValueError("missing_evidence_count must match items")
        if self.pass_count != sum(1 for item in self.items if item.status == "pass"):
            raise ValueError("pass_count must match items")
        if self.fail_count != sum(1 for item in self.items if item.status == "fail"):
            raise ValueError("fail_count must match items")
        if self.open_csv_row_count is None:
            self.open_csv_row_count = self.fail_count
        if self.open_csv_row_count != self.fail_count:
            raise ValueError("open_csv_row_count must match fail_count")
        expected_missing_value_count_by_field = count_by_field(lambda item: not item.has_reviewer_value)
        expected_missing_evidence_count_by_field = count_by_field(
            lambda item: item.has_reviewer_value and not item.has_reviewer_evidence
        )
        expected_suggested_value_count_by_field = count_by_field(lambda item: bool(item.suggested_value))
        expected_missing_suggestion_count_by_field = count_by_field(lambda item: not item.suggested_value)
        expected_missing_suggestion_task_ids_by_field: dict[str, list[str]] = {}
        for item in self.items:
            if item.suggested_value:
                continue
            expected_missing_suggestion_task_ids_by_field.setdefault(item.field_name, []).append(
                item.task_id
            )
        expected_missing_suggestion_task_ids_by_field = {
            field_name: sorted(task_ids)
            for field_name, task_ids in sorted(
                expected_missing_suggestion_task_ids_by_field.items()
            )
            if task_ids
        }
        expected_available_context_count_by_field = count_by_field(lambda item: bool(item.available_context_values))
        expected_missing_context_count_by_field = count_by_field(lambda item: not item.available_context_values)
        expected_missing_context_task_ids_by_field: dict[str, list[str]] = {}
        for item in self.items:
            if item.available_context_values:
                continue
            expected_missing_context_task_ids_by_field.setdefault(item.field_name, []).append(
                item.task_id
            )
        expected_missing_context_task_ids_by_field = {
            field_name: sorted(task_ids)
            for field_name, task_ids in sorted(
                expected_missing_context_task_ids_by_field.items()
            )
            if task_ids
        }
        expected_available_context_keys_by_field = context_keys_by_field()
        expected_available_context_values_by_field = context_values_by_field()
        expected_fail_count_by_field = count_by_field(lambda item: item.status == "fail")
        self.missing_value_count_by_field = normalize_count_map(self.missing_value_count_by_field)
        self.missing_evidence_count_by_field = normalize_count_map(self.missing_evidence_count_by_field)
        self.suggested_value_count_by_field = normalize_count_map(self.suggested_value_count_by_field)
        self.missing_suggestion_count_by_field = normalize_count_map(self.missing_suggestion_count_by_field)
        self.missing_suggestion_task_ids_by_field = normalize_key_list_map(
            self.missing_suggestion_task_ids_by_field
        )
        self.available_context_count_by_field = normalize_count_map(self.available_context_count_by_field)
        self.missing_context_count_by_field = normalize_count_map(self.missing_context_count_by_field)
        self.missing_context_task_ids_by_field = normalize_key_list_map(
            self.missing_context_task_ids_by_field
        )
        self.available_context_keys_by_field = normalize_key_list_map(self.available_context_keys_by_field)
        self.available_context_values_by_field = normalize_key_list_map(
            self.available_context_values_by_field
        )
        self.fail_count_by_field = normalize_count_map(self.fail_count_by_field)
        self.open_record_refs = _dedupe_non_empty_strings(
            self.open_record_refs,
            field_name="open_record_refs",
        ) if self.open_record_refs else []
        self.open_field_names_by_record_ref = normalize_key_list_map(
            self.open_field_names_by_record_ref
        )
        self.open_task_ids = _dedupe_non_empty_strings(
            self.open_task_ids,
            field_name="open_task_ids",
        ) if self.open_task_ids else []
        self.open_task_ids_by_field = normalize_key_list_map(self.open_task_ids_by_field)
        self.open_task_ids_by_record_ref = normalize_key_list_map(
            self.open_task_ids_by_record_ref
        )
        self.open_record_filled_patch_field_counts_by_field = normalize_count_map(
            self.open_record_filled_patch_field_counts_by_field
        )
        self.open_record_filled_patch_fields_by_record_ref = normalize_key_list_map(
            self.open_record_filled_patch_fields_by_record_ref
        )
        if self.open_record_count == 0 and self.fail_count > 0:
            self.open_record_count = len(expected_open_record_refs)
        if not self.open_record_refs:
            self.open_record_refs = expected_open_record_refs
        if not self.open_field_names_by_record_ref:
            self.open_field_names_by_record_ref = expected_open_field_names_by_record_ref
        if not self.missing_value_count_by_field:
            self.missing_value_count_by_field = expected_missing_value_count_by_field
        if not self.missing_evidence_count_by_field:
            self.missing_evidence_count_by_field = expected_missing_evidence_count_by_field
        if not self.suggested_value_count_by_field:
            self.suggested_value_count_by_field = expected_suggested_value_count_by_field
        if not self.missing_suggestion_count_by_field:
            self.missing_suggestion_count_by_field = expected_missing_suggestion_count_by_field
        if not self.missing_suggestion_task_ids_by_field:
            self.missing_suggestion_task_ids_by_field = expected_missing_suggestion_task_ids_by_field
        if not self.available_context_count_by_field:
            self.available_context_count_by_field = expected_available_context_count_by_field
        if not self.missing_context_count_by_field:
            self.missing_context_count_by_field = expected_missing_context_count_by_field
        if not self.missing_context_task_ids_by_field:
            self.missing_context_task_ids_by_field = expected_missing_context_task_ids_by_field
        if not self.available_context_keys_by_field:
            self.available_context_keys_by_field = expected_available_context_keys_by_field
        if not self.available_context_values_by_field:
            self.available_context_values_by_field = expected_available_context_values_by_field
        if not self.fail_count_by_field:
            self.fail_count_by_field = expected_fail_count_by_field
        if not self.open_task_ids:
            self.open_task_ids = expected_open_task_ids
        if not self.open_task_ids_by_field:
            self.open_task_ids_by_field = expected_open_task_ids_by_field
        if not self.open_task_ids_by_record_ref:
            self.open_task_ids_by_record_ref = expected_open_task_ids_by_record_ref
        if not self.open_record_filled_patch_field_counts_by_field:
            self.open_record_filled_patch_field_counts_by_field = (
                expected_open_record_filled_patch_field_counts_by_field
            )
        if not self.open_record_filled_patch_fields_by_record_ref:
            self.open_record_filled_patch_fields_by_record_ref = (
                expected_open_record_filled_patch_fields_by_record_ref_normalized
            )
        if self.missing_value_count_by_field != expected_missing_value_count_by_field:
            raise ValueError("missing_value_count_by_field must match items")
        if self.missing_evidence_count_by_field != expected_missing_evidence_count_by_field:
            raise ValueError("missing_evidence_count_by_field must match items")
        if self.suggested_value_count_by_field != expected_suggested_value_count_by_field:
            raise ValueError("suggested_value_count_by_field must match items")
        if self.missing_suggestion_count_by_field != expected_missing_suggestion_count_by_field:
            raise ValueError("missing_suggestion_count_by_field must match items")
        if self.missing_suggestion_task_ids_by_field != expected_missing_suggestion_task_ids_by_field:
            raise ValueError("missing_suggestion_task_ids_by_field must match items")
        if self.available_context_count_by_field != expected_available_context_count_by_field:
            raise ValueError("available_context_count_by_field must match items")
        if self.missing_context_count_by_field != expected_missing_context_count_by_field:
            raise ValueError("missing_context_count_by_field must match items")
        if self.missing_context_task_ids_by_field != expected_missing_context_task_ids_by_field:
            raise ValueError("missing_context_task_ids_by_field must match items")
        if self.available_context_keys_by_field != expected_available_context_keys_by_field:
            raise ValueError("available_context_keys_by_field must match items")
        if self.available_context_values_by_field != expected_available_context_values_by_field:
            raise ValueError("available_context_values_by_field must match items")
        if self.fail_count_by_field != expected_fail_count_by_field:
            raise ValueError("fail_count_by_field must match items")
        if self.open_record_count != len(expected_open_record_refs):
            raise ValueError("open_record_count must match failed items")
        if self.open_record_refs != expected_open_record_refs:
            raise ValueError("open_record_refs must match failed items")
        if self.open_field_names_by_record_ref != expected_open_field_names_by_record_ref:
            raise ValueError("open_field_names_by_record_ref must match failed items")
        if self.open_task_ids != expected_open_task_ids:
            raise ValueError("open_task_ids must match failed items")
        if self.open_task_ids_by_field != expected_open_task_ids_by_field:
            raise ValueError("open_task_ids_by_field must match failed items")
        if self.open_task_ids_by_record_ref != expected_open_task_ids_by_record_ref:
            raise ValueError("open_task_ids_by_record_ref must match failed items")
        if (
            self.open_record_filled_patch_field_counts_by_field
            != expected_open_record_filled_patch_field_counts_by_field
        ):
            raise ValueError(
                "open_record_filled_patch_field_counts_by_field must match failed items"
            )
        if (
            self.open_record_filled_patch_fields_by_record_ref
            != expected_open_record_filled_patch_fields_by_record_ref_normalized
        ):
            raise ValueError("open_record_filled_patch_fields_by_record_ref must match failed items")
        if self.ready_for_apply != (self.task_count > 0 and self.fail_count == 0):
            raise ValueError("ready_for_apply must match task and fail counts")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingFrontierHumanReviewQueueSplitSource(BaseModel):
    source_open_csv_path: str = Field(..., min_length=1)
    reviewed_csv_path: str = Field(..., min_length=1)
    source_fill_review_status_path: str | None = None
    source_task_export_path: str | None = None
    source_reviewed_csv_path: str | None = None
    fill_review_audit_command_hint: str | None = None
    fill_task_apply_command_hint: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    source_row_count: int = Field(ge=0)
    merged_review_row_count: int = Field(ge=0)
    merged_reviewed_value_count: int = Field(default=0, ge=0)
    merged_missing_value_count: int = Field(default=0, ge=0)
    merged_reviewed_evidence_count: int = Field(default=0, ge=0)
    merged_missing_evidence_count: int = Field(default=0, ge=0)
    merged_reviewer_value_hint_count: int = Field(default=0, ge=0)
    merged_reviewer_evidence_hint_count: int = Field(default=0, ge=0)
    merged_missing_value_with_hint_count: int = Field(default=0, ge=0)
    merged_missing_value_without_hint_count: int = Field(default=0, ge=0)
    merged_missing_value_task_ids: list[str] = Field(default_factory=list)
    merged_missing_evidence_task_ids: list[str] = Field(default_factory=list)
    merged_missing_value_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_missing_evidence_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_reviewer_value_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_reviewer_evidence_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_missing_value_with_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_missing_value_without_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    fill_review_blocker_reasons: list[str] = Field(default_factory=list)
    next_action_kind: Literal["complete_human_review", "run_fill_review_audit"] = "complete_human_review"
    next_action_command_hint: str | None = None
    ready_for_fill_review_audit: bool = False

    @model_validator(mode="after")
    def normalize_source(self):
        def normalize_count_map(value: dict[str, int]) -> dict[str, int]:
            return {
                str(key).strip(): int(count)
                for key, count in sorted(value.items())
                if str(key).strip() and int(count) > 0
            }

        self.source_open_csv_path = self.source_open_csv_path.strip()
        self.reviewed_csv_path = self.reviewed_csv_path.strip()
        if not self.source_open_csv_path:
            raise ValueError("source_open_csv_path is required")
        if not self.reviewed_csv_path:
            raise ValueError("reviewed_csv_path is required")
        if self.source_fill_review_status_path is not None:
            self.source_fill_review_status_path = self.source_fill_review_status_path.strip() or None
        if self.source_task_export_path is not None:
            self.source_task_export_path = self.source_task_export_path.strip() or None
        if self.source_reviewed_csv_path is not None:
            self.source_reviewed_csv_path = self.source_reviewed_csv_path.strip() or None
        if self.fill_review_audit_command_hint is not None:
            self.fill_review_audit_command_hint = self.fill_review_audit_command_hint.strip() or None
        if self.fill_task_apply_command_hint is not None:
            self.fill_task_apply_command_hint = self.fill_task_apply_command_hint.strip() or None
        if self.next_action_command_hint is not None:
            self.next_action_command_hint = self.next_action_command_hint.strip() or None
        self.requirement_ids = _dedupe_non_empty_strings(
            self.requirement_ids,
            field_name="requirement_ids",
        ) if self.requirement_ids else []
        self.merged_missing_value_task_ids = _dedupe_non_empty_strings(
            self.merged_missing_value_task_ids,
            field_name="merged_missing_value_task_ids",
        ) if self.merged_missing_value_task_ids else []
        self.merged_missing_evidence_task_ids = _dedupe_non_empty_strings(
            self.merged_missing_evidence_task_ids,
            field_name="merged_missing_evidence_task_ids",
        ) if self.merged_missing_evidence_task_ids else []
        self.fill_review_blocker_reasons = _dedupe_non_empty_strings(
            self.fill_review_blocker_reasons,
            field_name="fill_review_blocker_reasons",
        ) if self.fill_review_blocker_reasons else []
        self.merged_missing_value_counts_by_field = normalize_count_map(
            self.merged_missing_value_counts_by_field
        )
        self.merged_missing_evidence_counts_by_field = normalize_count_map(
            self.merged_missing_evidence_counts_by_field
        )
        self.merged_reviewer_value_hint_counts_by_field = normalize_count_map(
            self.merged_reviewer_value_hint_counts_by_field
        )
        self.merged_reviewer_evidence_hint_counts_by_field = normalize_count_map(
            self.merged_reviewer_evidence_hint_counts_by_field
        )
        self.merged_missing_value_with_hint_counts_by_field = normalize_count_map(
            self.merged_missing_value_with_hint_counts_by_field
        )
        self.merged_missing_value_without_hint_counts_by_field = normalize_count_map(
            self.merged_missing_value_without_hint_counts_by_field
        )
        if (
            "merged_missing_value_with_hint_counts_by_field" not in self.model_fields_set
            and "merged_missing_value_without_hint_counts_by_field" not in self.model_fields_set
        ):
            (
                self.merged_missing_value_with_hint_counts_by_field,
                self.merged_missing_value_without_hint_counts_by_field,
            ) = default_missing_value_hint_split_maps()
        if (
            "merged_missing_value_with_hint_count" not in self.model_fields_set
            and "merged_missing_value_without_hint_count" not in self.model_fields_set
        ):
            self.merged_missing_value_with_hint_count = sum(
                self.merged_missing_value_with_hint_counts_by_field.values()
            )
            self.merged_missing_value_without_hint_count = sum(
                self.merged_missing_value_without_hint_counts_by_field.values()
            )
        if self.merged_reviewed_value_count + self.merged_missing_value_count != self.merged_review_row_count:
            raise ValueError("merged value counts must match merged_review_row_count")
        if self.merged_reviewed_evidence_count + self.merged_missing_evidence_count != self.merged_review_row_count:
            raise ValueError("merged evidence counts must match merged_review_row_count")
        if self.merged_reviewer_value_hint_count > self.merged_review_row_count:
            raise ValueError("merged_reviewer_value_hint_count cannot exceed merged_review_row_count")
        if self.merged_reviewer_evidence_hint_count > self.merged_review_row_count:
            raise ValueError("merged_reviewer_evidence_hint_count cannot exceed merged_review_row_count")
        if self.merged_missing_value_with_hint_count + self.merged_missing_value_without_hint_count != self.merged_missing_value_count:
            raise ValueError("merged missing value hint counts must match merged_missing_value_count")
        if len(self.merged_missing_value_task_ids) != self.merged_missing_value_count:
            raise ValueError("merged_missing_value_task_ids must match merged_missing_value_count")
        if len(self.merged_missing_evidence_task_ids) != self.merged_missing_evidence_count:
            raise ValueError("merged_missing_evidence_task_ids must match merged_missing_evidence_count")
        if sum(self.merged_missing_value_counts_by_field.values()) != self.merged_missing_value_count:
            raise ValueError("merged_missing_value_counts_by_field must match merged_missing_value_count")
        if sum(self.merged_missing_evidence_counts_by_field.values()) != self.merged_missing_evidence_count:
            raise ValueError("merged_missing_evidence_counts_by_field must match merged_missing_evidence_count")
        if sum(self.merged_reviewer_value_hint_counts_by_field.values()) != self.merged_reviewer_value_hint_count:
            raise ValueError("merged_reviewer_value_hint_counts_by_field must match merged_reviewer_value_hint_count")
        if sum(self.merged_reviewer_evidence_hint_counts_by_field.values()) != self.merged_reviewer_evidence_hint_count:
            raise ValueError("merged_reviewer_evidence_hint_counts_by_field must match merged_reviewer_evidence_hint_count")
        if sum(self.merged_missing_value_with_hint_counts_by_field.values()) != self.merged_missing_value_with_hint_count:
            raise ValueError("merged_missing_value_with_hint_counts_by_field must match merged_missing_value_with_hint_count")
        if sum(self.merged_missing_value_without_hint_counts_by_field.values()) != self.merged_missing_value_without_hint_count:
            raise ValueError("merged_missing_value_without_hint_counts_by_field must match merged_missing_value_without_hint_count")
        expected_blocker_reasons: list[str] = []
        if self.merged_review_row_count == 0:
            expected_blocker_reasons.append("no_review_rows")
        if self.merged_missing_value_count > 0:
            expected_blocker_reasons.append("missing_reviewer_value")
        if self.merged_missing_evidence_count > 0:
            expected_blocker_reasons.append("missing_reviewer_evidence")
        if "fill_review_blocker_reasons" not in self.model_fields_set:
            self.fill_review_blocker_reasons = expected_blocker_reasons
        if self.fill_review_blocker_reasons != expected_blocker_reasons:
            raise ValueError("fill_review_blocker_reasons must match merged review counts")
        if self.ready_for_fill_review_audit != (not expected_blocker_reasons):
            raise ValueError("ready_for_fill_review_audit must match merged review counts")
        expected_next_action_kind = (
            "complete_human_review"
            if expected_blocker_reasons
            else "run_fill_review_audit"
        )
        if "next_action_kind" not in self.model_fields_set:
            self.next_action_kind = expected_next_action_kind
        if self.next_action_kind != expected_next_action_kind:
            raise ValueError("next_action_kind must match fill review readiness")
        expected_next_action_command_hint = (
            None
            if expected_blocker_reasons
            else self.fill_review_audit_command_hint
        )
        if "next_action_command_hint" not in self.model_fields_set:
            self.next_action_command_hint = expected_next_action_command_hint
        if self.next_action_command_hint != expected_next_action_command_hint:
            raise ValueError("next_action_command_hint must match fill review readiness")
        return self


class EvidenceGroundingFrontierHumanReviewQueueSplitReport(BaseModel):
    schema_version: Literal["evidence_grounding_frontier_human_review_queue_split.v1"] = (
        "evidence_grounding_frontier_human_review_queue_split.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    queue_csv_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    source_csv_count: int = Field(ge=0)
    merged_review_row_count: int = Field(ge=0)
    merged_reviewed_value_count: int = Field(default=0, ge=0)
    merged_missing_value_count: int = Field(default=0, ge=0)
    merged_reviewed_evidence_count: int = Field(default=0, ge=0)
    merged_missing_evidence_count: int = Field(default=0, ge=0)
    merged_reviewer_value_hint_count: int = Field(default=0, ge=0)
    merged_reviewer_evidence_hint_count: int = Field(default=0, ge=0)
    merged_missing_value_with_hint_count: int = Field(default=0, ge=0)
    merged_missing_value_without_hint_count: int = Field(default=0, ge=0)
    merged_missing_value_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_missing_evidence_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_reviewer_value_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_reviewer_evidence_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_missing_value_with_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    merged_missing_value_without_hint_counts_by_field: dict[str, int] = Field(default_factory=dict)
    ready_source_count: int = Field(default=0, ge=0)
    blocked_source_count: int = Field(default=0, ge=0)
    ready_reviewed_csv_paths: list[str] = Field(default_factory=list)
    blocked_reviewed_csv_paths: list[str] = Field(default_factory=list)
    blocked_source_reasons_by_reviewed_csv_path: dict[str, list[str]] = Field(default_factory=dict)
    ready_fill_review_audit_command_hints: list[str] = Field(default_factory=list)
    sources: list[EvidenceGroundingFrontierHumanReviewQueueSplitSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        def merged_count_map(field_name: str) -> dict[str, int]:
            values: dict[str, int] = {}
            for source in self.sources:
                for key, count in getattr(source, field_name).items():
                    values[key] = values.get(key, 0) + count
            return dict(sorted(values.items()))

        def normalize_key_list_map(value: dict[str, list[str]]) -> dict[str, list[str]]:
            normalized: dict[str, list[str]] = {}
            for raw_key, raw_values in value.items():
                key = str(raw_key or "").strip()
                if not key:
                    raise ValueError("blocked_source_reasons_by_reviewed_csv_path keys must be non-empty")
                normalized[key] = _dedupe_non_empty_strings(
                    list(raw_values or []),
                    field_name="blocked_source_reasons_by_reviewed_csv_path values",
                )
            return normalized

        def normalize_count_map(value: dict[str, int]) -> dict[str, int]:
            return {
                str(key).strip(): int(count)
                for key, count in sorted(value.items())
                if str(key).strip() and int(count) > 0
            }

        self.queue_csv_path = self.queue_csv_path.strip()
        self.out_dir = self.out_dir.strip()
        if not self.queue_csv_path:
            raise ValueError("queue_csv_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if self.source_csv_count != len(self.sources):
            raise ValueError("source_csv_count must match sources size")
        if self.merged_review_row_count != sum(source.merged_review_row_count for source in self.sources):
            raise ValueError("merged_review_row_count must match sources")
        if self.merged_reviewed_value_count != sum(source.merged_reviewed_value_count for source in self.sources):
            raise ValueError("merged_reviewed_value_count must match sources")
        if self.merged_missing_value_count != sum(source.merged_missing_value_count for source in self.sources):
            raise ValueError("merged_missing_value_count must match sources")
        if self.merged_reviewed_evidence_count != sum(source.merged_reviewed_evidence_count for source in self.sources):
            raise ValueError("merged_reviewed_evidence_count must match sources")
        if self.merged_missing_evidence_count != sum(source.merged_missing_evidence_count for source in self.sources):
            raise ValueError("merged_missing_evidence_count must match sources")
        if self.merged_reviewer_value_hint_count != sum(source.merged_reviewer_value_hint_count for source in self.sources):
            raise ValueError("merged_reviewer_value_hint_count must match sources")
        if self.merged_reviewer_evidence_hint_count != sum(source.merged_reviewer_evidence_hint_count for source in self.sources):
            raise ValueError("merged_reviewer_evidence_hint_count must match sources")
        if "merged_missing_value_with_hint_count" not in self.model_fields_set:
            self.merged_missing_value_with_hint_count = sum(
                source.merged_missing_value_with_hint_count for source in self.sources
            )
        if "merged_missing_value_without_hint_count" not in self.model_fields_set:
            self.merged_missing_value_without_hint_count = sum(
                source.merged_missing_value_without_hint_count for source in self.sources
            )
        if self.merged_missing_value_with_hint_count != sum(source.merged_missing_value_with_hint_count for source in self.sources):
            raise ValueError("merged_missing_value_with_hint_count must match sources")
        if self.merged_missing_value_without_hint_count != sum(source.merged_missing_value_without_hint_count for source in self.sources):
            raise ValueError("merged_missing_value_without_hint_count must match sources")
        self.merged_missing_value_counts_by_field = normalize_count_map(
            self.merged_missing_value_counts_by_field
        )
        self.merged_missing_evidence_counts_by_field = normalize_count_map(
            self.merged_missing_evidence_counts_by_field
        )
        self.merged_reviewer_value_hint_counts_by_field = normalize_count_map(
            self.merged_reviewer_value_hint_counts_by_field
        )
        self.merged_reviewer_evidence_hint_counts_by_field = normalize_count_map(
            self.merged_reviewer_evidence_hint_counts_by_field
        )
        self.merged_missing_value_with_hint_counts_by_field = normalize_count_map(
            self.merged_missing_value_with_hint_counts_by_field
        )
        self.merged_missing_value_without_hint_counts_by_field = normalize_count_map(
            self.merged_missing_value_without_hint_counts_by_field
        )
        if self.merged_missing_value_counts_by_field != merged_count_map("merged_missing_value_counts_by_field"):
            raise ValueError("merged_missing_value_counts_by_field must match sources")
        if self.merged_missing_evidence_counts_by_field != merged_count_map("merged_missing_evidence_counts_by_field"):
            raise ValueError("merged_missing_evidence_counts_by_field must match sources")
        if self.merged_reviewer_value_hint_counts_by_field != merged_count_map("merged_reviewer_value_hint_counts_by_field"):
            raise ValueError("merged_reviewer_value_hint_counts_by_field must match sources")
        if self.merged_reviewer_evidence_hint_counts_by_field != merged_count_map("merged_reviewer_evidence_hint_counts_by_field"):
            raise ValueError("merged_reviewer_evidence_hint_counts_by_field must match sources")
        if "merged_missing_value_with_hint_counts_by_field" not in self.model_fields_set:
            self.merged_missing_value_with_hint_counts_by_field = merged_count_map(
                "merged_missing_value_with_hint_counts_by_field"
            )
        if "merged_missing_value_without_hint_counts_by_field" not in self.model_fields_set:
            self.merged_missing_value_without_hint_counts_by_field = merged_count_map(
                "merged_missing_value_without_hint_counts_by_field"
            )
        if self.merged_missing_value_with_hint_counts_by_field != merged_count_map("merged_missing_value_with_hint_counts_by_field"):
            raise ValueError("merged_missing_value_with_hint_counts_by_field must match sources")
        if self.merged_missing_value_without_hint_counts_by_field != merged_count_map("merged_missing_value_without_hint_counts_by_field"):
            raise ValueError("merged_missing_value_without_hint_counts_by_field must match sources")
        if self.ready_source_count != sum(1 for source in self.sources if source.ready_for_fill_review_audit):
            raise ValueError("ready_source_count must match sources")
        if self.blocked_source_count != sum(1 for source in self.sources if not source.ready_for_fill_review_audit):
            raise ValueError("blocked_source_count must match sources")
        expected_ready_paths = [
            source.reviewed_csv_path
            for source in self.sources
            if source.ready_for_fill_review_audit
        ]
        expected_blocked_paths = [
            source.reviewed_csv_path
            for source in self.sources
            if not source.ready_for_fill_review_audit
        ]
        expected_blocked_reasons = {
            source.reviewed_csv_path: source.fill_review_blocker_reasons
            for source in self.sources
            if not source.ready_for_fill_review_audit
        }
        expected_ready_audit_commands = [
            str(source.next_action_command_hint)
            for source in self.sources
            if (
                source.ready_for_fill_review_audit
                and source.next_action_kind == "run_fill_review_audit"
                and source.next_action_command_hint
            )
        ]
        self.ready_reviewed_csv_paths = _dedupe_non_empty_strings(
            self.ready_reviewed_csv_paths,
            field_name="ready_reviewed_csv_paths",
        ) if self.ready_reviewed_csv_paths else []
        self.blocked_reviewed_csv_paths = _dedupe_non_empty_strings(
            self.blocked_reviewed_csv_paths,
            field_name="blocked_reviewed_csv_paths",
        ) if self.blocked_reviewed_csv_paths else []
        self.blocked_source_reasons_by_reviewed_csv_path = normalize_key_list_map(
            self.blocked_source_reasons_by_reviewed_csv_path
        )
        self.ready_fill_review_audit_command_hints = _dedupe_non_empty_strings(
            self.ready_fill_review_audit_command_hints,
            field_name="ready_fill_review_audit_command_hints",
        ) if self.ready_fill_review_audit_command_hints else []
        if "ready_reviewed_csv_paths" not in self.model_fields_set:
            self.ready_reviewed_csv_paths = expected_ready_paths
        if "blocked_reviewed_csv_paths" not in self.model_fields_set:
            self.blocked_reviewed_csv_paths = expected_blocked_paths
        if "blocked_source_reasons_by_reviewed_csv_path" not in self.model_fields_set:
            self.blocked_source_reasons_by_reviewed_csv_path = expected_blocked_reasons
        if "ready_fill_review_audit_command_hints" not in self.model_fields_set:
            self.ready_fill_review_audit_command_hints = expected_ready_audit_commands
        if self.ready_reviewed_csv_paths != expected_ready_paths:
            raise ValueError("ready_reviewed_csv_paths must match sources")
        if self.blocked_reviewed_csv_paths != expected_blocked_paths:
            raise ValueError("blocked_reviewed_csv_paths must match sources")
        if self.blocked_source_reasons_by_reviewed_csv_path != expected_blocked_reasons:
            raise ValueError("blocked_source_reasons_by_reviewed_csv_path must match sources")
        if self.ready_fill_review_audit_command_hints != expected_ready_audit_commands:
            raise ValueError("ready_fill_review_audit_command_hints must match sources")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingCandidateLineagePatchTemplateRequest(BaseModel):
    benchmark_manifest_package_path: str = Field(..., min_length=1)
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.benchmark_manifest_package_path = self.benchmark_manifest_package_path.strip()
        if not self.benchmark_manifest_package_path:
            raise ValueError("benchmark_manifest_package_path is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingCandidateLineagePatchApplyRequest(BaseModel):
    patch_template_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    package_id: str = "evidence-grounding-candidate-lineage-repaired-manifest-package"
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.patch_template_path = self.patch_template_path.strip()
        self.out_dir = self.out_dir.strip()
        self.package_id = self.package_id.strip()
        if not self.patch_template_path:
            raise ValueError("patch_template_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingBenchmarkRunRequest(BaseModel):
    manifest_path: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_request(self):
        self.manifest_path = self.manifest_path.strip()
        self.out = self.out.strip()
        if not self.manifest_path:
            raise ValueError("manifest_path is required")
        if not self.out:
            raise ValueError("out is required")
        return self


class EvidenceGroundingBenchmarkAggregateMetric(BaseModel):
    value: float | int | None = None
    status: Literal["available", "not_available"] = "not_available"
    item_count: int = 0
    source: str | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def validate_value_status(self):
        if self.status == "available" and self.value is None:
            raise ValueError("available aggregate metrics require a value")
        if self.status == "not_available" and self.value is not None:
            raise ValueError("not_available aggregate metrics must not carry a value")
        return self


class EvidenceGroundingBenchmarkScorecardItem(BaseModel):
    candidate_id: str
    run_dir: str
    paper_id: str
    run_id: str
    scorecard: EvidenceGroundingScorecard
    candidate_config: EvidenceGroundingCandidateConfig | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceGroundingBenchmarkStageMetricSummary(BaseModel):
    stage: str
    runtime_proxy_metrics: dict[str, EvidenceGroundingBenchmarkAggregateMetric] = Field(default_factory=dict)
    gold_scored_metrics: dict[str, EvidenceGroundingBenchmarkAggregateMetric] = Field(default_factory=dict)
    available_metric_count: int = 0
    detail: str | None = None

    @model_validator(mode="after")
    def normalize_summary(self):
        self.runtime_proxy_metrics = {
            str(name).strip(): metric
            for name, metric in sorted(self.runtime_proxy_metrics.items())
            if str(name).strip()
        }
        self.gold_scored_metrics = {
            str(name).strip(): metric
            for name, metric in sorted(self.gold_scored_metrics.items())
            if str(name).strip()
        }
        self.available_metric_count = sum(
            1
            for metric in list(self.runtime_proxy_metrics.values()) + list(self.gold_scored_metrics.values())
            if metric.status == "available"
        )
        if self.detail is not None:
            self.detail = self.detail.strip() or None
        return self


class EvidenceGroundingBenchmarkReport(BaseModel):
    schema_version: Literal["evidence_grounding_benchmark.v1"] = "evidence_grounding_benchmark.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    benchmark_id: str
    goldset_id: str | None = None
    goldset_split: str | None = None
    goldset_manifest_path: str | None = None
    goldset_item_count: int | None = None
    goldset_covered_paper_count: int | None = None
    goldset_missing_paper_ids: list[str] = Field(default_factory=list)
    goldset_extra_paper_ids: list[str] = Field(default_factory=list)
    goldset_readiness_pass_count: int | None = None
    goldset_readiness_warn_count: int | None = None
    goldset_readiness_fail_count: int | None = None
    goldset_not_ready_paper_ids: list[str] = Field(default_factory=list)
    scorecard_readiness_pass_count: int = Field(default=0, ge=0)
    scorecard_readiness_warn_count: int = Field(default=0, ge=0)
    scorecard_readiness_fail_count: int = Field(default=0, ge=0)
    scorecard_not_ready_candidate_ids: list[str] = Field(default_factory=list)
    item_count: int
    scorecards: list[EvidenceGroundingBenchmarkScorecardItem]
    candidate_configs: list[EvidenceGroundingCandidateConfig] = Field(default_factory=list)
    aggregate_runtime_proxy_metrics: dict[str, EvidenceGroundingBenchmarkAggregateMetric] = Field(default_factory=dict)
    aggregate_gold_scored_metrics: dict[str, EvidenceGroundingBenchmarkAggregateMetric] = Field(default_factory=dict)
    aggregate_failure_counts_by_code: dict[EvidenceGroundingFailureCode, int] = Field(default_factory=dict)
    aggregate_stage_failure_summary: list[EvidenceGroundingStageFailureSummary] = Field(default_factory=list)
    aggregate_stage_metric_summary: list[EvidenceGroundingBenchmarkStageMetricSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.aggregate_failure_counts_by_code = {
            _validate_failure_code(code, field_name="aggregate_failure_counts_by_code"): int(count)
            for code, count in sorted(self.aggregate_failure_counts_by_code.items())
            if str(code).strip() and int(count) > 0
        }
        return self


class EvidenceGroundingBenchmarkRunPackage(BaseModel):
    schema_version: Literal["evidence_grounding_benchmark_run_package.v1"] = (
        "evidence_grounding_benchmark_run_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    package_id: str = Field(..., min_length=1)
    benchmark_manifest_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    benchmark_report_paths: list[str] = Field(default_factory=list)
    benchmark_reports: list[EvidenceGroundingBenchmarkReport] = Field(default_factory=list)
    report_count: int = Field(ge=0)
    item_count: int = Field(ge=0)
    scorecard_count: int = Field(ge=0)
    scorecard_readiness_pass_count: int = Field(default=0, ge=0)
    scorecard_readiness_warn_count: int = Field(default=0, ge=0)
    scorecard_readiness_fail_count: int = Field(default=0, ge=0)
    scorecard_not_ready_candidate_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        self.package_id = self.package_id.strip()
        self.benchmark_manifest_package_path = self.benchmark_manifest_package_path.strip()
        self.out_dir = self.out_dir.strip()
        self.benchmark_report_paths = _dedupe_non_empty_strings(
            self.benchmark_report_paths,
            field_name="benchmark_report_paths",
        ) if self.benchmark_report_paths else []
        self.scorecard_not_ready_candidate_ids = (
            _dedupe_non_empty_strings(
                self.scorecard_not_ready_candidate_ids,
                field_name="scorecard_not_ready_candidate_ids",
            )
            if self.scorecard_not_ready_candidate_ids
            else []
        )
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.benchmark_manifest_package_path:
            raise ValueError("benchmark_manifest_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        return self


class EvidenceGroundingBenchmarkRunPackageRequest(BaseModel):
    benchmark_manifest_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    package_id: str = "evidence-grounding-benchmark-run-package"
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.benchmark_manifest_package_path = self.benchmark_manifest_package_path.strip()
        self.out_dir = self.out_dir.strip()
        self.package_id = self.package_id.strip()
        if not self.benchmark_manifest_package_path:
            raise ValueError("benchmark_manifest_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingP0OverstatementReviewEvidenceRef(BaseModel):
    locator: str = ""
    quote: str = ""


class EvidenceGroundingP0OverstatementReviewGoldStatement(BaseModel):
    group: str = Field(..., min_length=1)
    statement_id: str | None = None
    kind: str | None = None
    text: str = ""
    evidence_refs: list[EvidenceGroundingP0OverstatementReviewEvidenceRef] = Field(default_factory=list)
    review_failure_codes: list[str] = Field(default_factory=list)


class EvidenceGroundingP0OverstatementReviewClaimRow(BaseModel):
    split: str | None = None
    paper_id: str = Field(..., min_length=1)
    run_id: str | None = None
    claim_id: str = Field(..., min_length=1)
    claim_type: str | None = None
    system_claim: str = ""
    system_evidence_refs: list[EvidenceGroundingP0OverstatementReviewEvidenceRef] = Field(default_factory=list)
    supported: bool | None = None
    unsupported: bool | None = None
    unknown: bool | None = None
    statement_evidence_overlap_ratio: float | None = None
    low_statement_evidence_overlap: bool | None = None
    grounding_resolutions: list[str] = Field(default_factory=list)
    gold_context: list[EvidenceGroundingP0OverstatementReviewGoldStatement] = Field(default_factory=list)
    review_prompt: str = (
        "Does the system claim overstate, broaden, causalize, or overgeneralize beyond the listed evidence/gold context?"
    )
    reviewer_decision: str = ""
    reviewer_rationale: str = ""

    @model_validator(mode="after")
    def normalize_row(self):
        for field_name in (
            "split",
            "paper_id",
            "run_id",
            "claim_id",
            "claim_type",
            "system_claim",
            "review_prompt",
            "reviewer_decision",
            "reviewer_rationale",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, str(value).strip())
        if not self.paper_id:
            raise ValueError("paper_id is required")
        if not self.claim_id:
            raise ValueError("claim_id is required")
        self.grounding_resolutions = (
            _dedupe_non_empty_strings(
                self.grounding_resolutions,
                field_name="grounding_resolutions",
            )
            if self.grounding_resolutions
            else []
        )
        return self


class EvidenceGroundingP0OverstatementReviewPaper(BaseModel):
    split: str | None = None
    paper_id: str = Field(..., min_length=1)
    run_id: str | None = None
    run_dir: str | None = None
    citation: dict[str, Any] = Field(default_factory=dict)
    paper_type: str | None = None
    scorecard_readiness_status: str | None = None
    failure_counts_by_code: dict[str, int] = Field(default_factory=dict)
    overstatement_rate_status: dict[str, Any] = Field(default_factory=dict)
    gold_statement_count: int = Field(default=0, ge=0)
    system_claim_count: int = Field(default=0, ge=0)
    gold_statements: list[EvidenceGroundingP0OverstatementReviewGoldStatement] = Field(default_factory=list)
    system_claims: list[EvidenceGroundingP0OverstatementReviewClaimRow] = Field(default_factory=list)


class EvidenceGroundingP0OverstatementReviewPacket(BaseModel):
    schema_version: Literal["evidence_grounding_p0_overstatement_review_packet.v1"] = (
        "evidence_grounding_p0_overstatement_review_packet.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_benchmark_report_paths: list[str] = Field(default_factory=list)
    purpose: str = (
        "Compact reviewer packet for deciding whether system claims overstate source evidence or gold statements."
    )
    review_instruction: str = (
        "Use this packet to add explicit OVERSTATED_RESULT labels or reviewed claim/evidence fixtures only after reviewer judgment."
    )
    paper_count: int = Field(default=0, ge=0)
    claim_review_row_count: int = Field(default=0, ge=0)
    papers: list[EvidenceGroundingP0OverstatementReviewPaper] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_packet(self):
        self.source_benchmark_report_paths = (
            _dedupe_non_empty_strings(
                self.source_benchmark_report_paths,
                field_name="source_benchmark_report_paths",
            )
            if self.source_benchmark_report_paths
            else []
        )
        self.paper_count = len(self.papers)
        self.claim_review_row_count = sum(len(paper.system_claims) for paper in self.papers)
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingP0OverstatementReviewPacketExportRequest(BaseModel):
    benchmark_report_paths: list[str] = Field(..., min_length=1)
    out: str | None = None
    csv_out: str | None = None
    markdown_out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.benchmark_report_paths = _dedupe_non_empty_strings(
            self.benchmark_report_paths,
            field_name="benchmark_report_paths",
        )
        for field_name in ("out", "csv_out", "markdown_out"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class EvidenceGroundingP0OverstatementReviewDecisionRow(BaseModel):
    split: str | None = None
    paper_id: str = Field(..., min_length=1)
    run_id: str | None = None
    claim_id: str = Field(..., min_length=1)
    system_claim: str = ""
    reviewer_decision: str = ""
    normalized_decision: Literal[
        "overstated",
        "not_overstated",
        "uncertain",
        "missing",
        "invalid",
    ]
    reviewer_rationale: str = ""
    included_in_metric: bool = False
    issue_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_row(self):
        for field_name in (
            "split",
            "paper_id",
            "run_id",
            "claim_id",
            "system_claim",
            "reviewer_decision",
            "reviewer_rationale",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, str(value).strip())
        self.issue_codes = (
            _dedupe_non_empty_strings(self.issue_codes, field_name="issue_codes")
            if self.issue_codes
            else []
        )
        return self


class EvidenceGroundingP0OverstatementReviewSummary(BaseModel):
    schema_version: Literal["evidence_grounding_p0_overstatement_review_summary.v1"] = (
        "evidence_grounding_p0_overstatement_review_summary.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_packet_path: str = Field(..., min_length=1)
    source_reviewed_csv_path: str | None = None
    open_issue_csv_path: str | None = None
    decision_policy: str = (
        "overstated=yes/OVERSTATED_RESULT, not_overstated=no/NOT_OVERSTATED, "
        "uncertain values are excluded and keep the metric not ready."
    )
    paper_count: int = Field(default=0, ge=0)
    claim_review_row_count: int = Field(default=0, ge=0)
    reviewed_claim_count: int = Field(default=0, ge=0)
    included_claim_count: int = Field(default=0, ge=0)
    overstated_claim_count: int = Field(default=0, ge=0)
    not_overstated_claim_count: int = Field(default=0, ge=0)
    uncertain_claim_count: int = Field(default=0, ge=0)
    missing_decision_count: int = Field(default=0, ge=0)
    invalid_decision_count: int = Field(default=0, ge=0)
    missing_rationale_count: int = Field(default=0, ge=0)
    extra_reviewed_csv_row_count: int = Field(default=0, ge=0)
    duplicate_reviewed_csv_key_count: int = Field(default=0, ge=0)
    ready_for_p0_metric: bool = False
    overstatement_rate_status: dict[str, Any] = Field(default_factory=dict)
    rows: list[EvidenceGroundingP0OverstatementReviewDecisionRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_summary(self):
        self.source_packet_path = self.source_packet_path.strip()
        if not self.source_packet_path:
            raise ValueError("source_packet_path is required")
        if self.source_reviewed_csv_path is not None:
            self.source_reviewed_csv_path = self.source_reviewed_csv_path.strip() or None
        if self.open_issue_csv_path is not None:
            self.open_issue_csv_path = self.open_issue_csv_path.strip() or None
        self.claim_review_row_count = len(self.rows)
        self.reviewed_claim_count = sum(
            1
            for row in self.rows
            if row.normalized_decision in {"overstated", "not_overstated", "uncertain"}
        )
        self.included_claim_count = sum(1 for row in self.rows if row.included_in_metric)
        self.overstated_claim_count = sum(1 for row in self.rows if row.normalized_decision == "overstated")
        self.not_overstated_claim_count = sum(
            1 for row in self.rows if row.normalized_decision == "not_overstated"
        )
        self.uncertain_claim_count = sum(1 for row in self.rows if row.normalized_decision == "uncertain")
        self.missing_decision_count = sum(1 for row in self.rows if row.normalized_decision == "missing")
        self.invalid_decision_count = sum(1 for row in self.rows if row.normalized_decision == "invalid")
        self.missing_rationale_count = sum(
            1
            for row in self.rows
            if row.normalized_decision in {"overstated", "not_overstated"}
            and not row.reviewer_rationale
        )
        ready = (
            self.claim_review_row_count > 0
            and self.included_claim_count == self.claim_review_row_count
            and self.missing_decision_count == 0
            and self.invalid_decision_count == 0
            and self.uncertain_claim_count == 0
            and self.missing_rationale_count == 0
            and self.extra_reviewed_csv_row_count == 0
            and self.duplicate_reviewed_csv_key_count == 0
        )
        self.ready_for_p0_metric = bool(ready)
        if self.ready_for_p0_metric:
            self.overstatement_rate_status = {
                "value": self.overstated_claim_count / self.included_claim_count,
                "status": "available",
                "item_count": self.included_claim_count,
                "source": "evidence_grounding_p0_overstatement_review_summary.v1",
            }
        else:
            self.overstatement_rate_status = {
                "value": None,
                "status": "not_available",
                "item_count": self.included_claim_count,
                "source": "evidence_grounding_p0_overstatement_review_summary.v1",
                "detail": (
                    "Requires complete reviewer decisions and rationales for every P0 overstatement row."
                ),
            }
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingP0OverstatementReviewSummaryRequest(BaseModel):
    packet_path: str = Field(..., min_length=1)
    reviewed_csv_path: str | None = None
    out: str | None = None
    open_issue_csv_out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in ("packet_path", "reviewed_csv_path", "out", "open_issue_csv_out"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if not self.packet_path:
            raise ValueError("packet_path is required")
        return self


class EvidenceGroundingActiveReviewReadinessBlocker(BaseModel):
    blocker_id: str = Field(..., min_length=1)
    count: int | None = Field(default=None, ge=0)
    required_action: str | None = None

    @model_validator(mode="after")
    def normalize_blocker(self):
        self.blocker_id = self.blocker_id.strip()
        if not self.blocker_id:
            raise ValueError("blocker_id is required")
        if self.required_action is not None:
            self.required_action = self.required_action.strip() or None
        return self


class EvidenceGroundingActiveReviewReadinessStructuredCorrection(BaseModel):
    fill_review_status_path: str = Field(..., min_length=1)
    reviewed_csv_path: str | None = None
    open_csv_path: str | None = None
    open_record_csv_path: str | None = None
    source_task_export_path: str | None = None
    ready_for_apply: bool
    open_csv_row_count: int = Field(ge=0)
    open_record_count: int = Field(ge=0)
    missing_value_count: int = Field(ge=0)
    missing_evidence_count: int = Field(ge=0)

    @model_validator(mode="after")
    def normalize_structured_correction(self):
        self.fill_review_status_path = self.fill_review_status_path.strip()
        if not self.fill_review_status_path:
            raise ValueError("fill_review_status_path is required")
        for field_name in (
            "reviewed_csv_path",
            "open_csv_path",
            "open_record_csv_path",
            "source_task_export_path",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class EvidenceGroundingActiveReviewReadinessP0Overstatement(BaseModel):
    summary_path: str = Field(..., min_length=1)
    source_packet_path: str | None = None
    source_reviewed_csv_path: str | None = None
    open_issue_csv_path: str | None = None
    ready_for_p0_metric: bool
    claim_review_row_count: int = Field(ge=0)
    missing_decision_count: int = Field(ge=0)
    invalid_decision_count: int = Field(ge=0)
    uncertain_claim_count: int = Field(ge=0)
    missing_rationale_count: int = Field(ge=0)

    @model_validator(mode="after")
    def normalize_p0_overstatement(self):
        self.summary_path = self.summary_path.strip()
        if not self.summary_path:
            raise ValueError("summary_path is required")
        for field_name in (
            "source_packet_path",
            "source_reviewed_csv_path",
            "open_issue_csv_path",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class EvidenceGroundingActiveReviewReadinessBriefAudit(BaseModel):
    audit_path: str | None = None
    all_passed: bool = True
    fail_count: int = Field(default=0, ge=0)
    counts: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_brief_audit(self):
        if self.audit_path is not None:
            self.audit_path = self.audit_path.strip() or None
        if self.all_passed and self.fail_count:
            raise ValueError("fail_count must be 0 when all_passed is true")
        self.counts = {key.strip(): value for key, value in self.counts.items() if key.strip()}
        for key, value in self.counts.items():
            if value < 0:
                raise ValueError(f"counts values must be non-negative: {key}")
        return self


class EvidenceGroundingActiveReviewReadinessWorkItem(BaseModel):
    item_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    reviewer_action: str = Field(..., min_length=1)
    edit_path: str | None = None
    context_path: str | None = None
    open_issue_path: str | None = None
    verification_command_hint: str | None = None
    expected_paper_reading: str = Field(..., min_length=1)
    primary_review_source: str = Field(..., min_length=1)
    open_item_count: int = Field(ge=0)
    open_record_count: int | None = Field(default=None, ge=0)
    open_paper_count: int | None = Field(default=None, ge=0)
    blocked_roadmap_requirement_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_work_item(self):
        for field_name in (
            "item_id",
            "label",
            "reviewer_action",
            "expected_paper_reading",
            "primary_review_source",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} is required")
            setattr(self, field_name, value)
        for field_name in (
            "edit_path",
            "context_path",
            "open_issue_path",
            "verification_command_hint",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        self.blocked_roadmap_requirement_ids = _dedupe_non_empty_strings(
            self.blocked_roadmap_requirement_ids,
            field_name="blocked_roadmap_requirement_ids",
        )
        return self


class EvidenceGroundingActiveReviewReadinessReport(BaseModel):
    schema_version: Literal["evidence_grounding_active_review_readiness.v1"] = (
        "evidence_grounding_active_review_readiness.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    ready_for_downstream_review_steps: bool
    structured_correction: EvidenceGroundingActiveReviewReadinessStructuredCorrection
    p0_overstatement: EvidenceGroundingActiveReviewReadinessP0Overstatement
    active_brief_audit: EvidenceGroundingActiveReviewReadinessBriefAudit
    structured_open_review_cell_count: int | None = Field(default=None, ge=0)
    structured_open_record_count: int | None = Field(default=None, ge=0)
    p0_open_decision_count: int | None = Field(default=None, ge=0)
    p0_open_paper_count: int | None = Field(default=None, ge=0)
    structured_expected_paper_reading: str = "no"
    structured_primary_review_source: str = "full context packet and reviewed/open-record CSVs"
    p0_expected_paper_reading: str = "targeted"
    p0_primary_review_source: str = "packet Markdown with full gold context"
    p0_original_paper_reading_condition: str = (
        "only when packet evidence or gold context is insufficient or contradictory"
    )
    reviewer_work_items: list[EvidenceGroundingActiveReviewReadinessWorkItem] = Field(
        default_factory=list
    )
    reviewer_work_item_count: int = Field(default=0, ge=0)
    reviewer_open_item_counts_by_expected_paper_reading: dict[str, int] = Field(
        default_factory=dict
    )
    reviewer_open_paper_counts_by_expected_paper_reading: dict[str, int] = Field(
        default_factory=dict
    )
    blocker_count: int = Field(ge=0)
    blockers: list[EvidenceGroundingActiveReviewReadinessBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_readiness(self):
        if self.blocker_count != len(self.blockers):
            raise ValueError("blocker_count must match blockers size")
        expected_ready = (
            self.structured_correction.ready_for_apply
            and self.p0_overstatement.ready_for_p0_metric
            and self.active_brief_audit.all_passed
        )
        if self.ready_for_downstream_review_steps != expected_ready:
            raise ValueError("ready_for_downstream_review_steps must match component readiness")
        if self.ready_for_downstream_review_steps and self.blockers:
            raise ValueError("ready reports must not include blockers")
        for field_name in (
            "structured_expected_paper_reading",
            "structured_primary_review_source",
            "p0_expected_paper_reading",
            "p0_primary_review_source",
            "p0_original_paper_reading_condition",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} is required")
            setattr(self, field_name, value)
        if (
            "reviewer_work_item_count" in self.model_fields_set
            and self.reviewer_work_item_count != len(self.reviewer_work_items)
        ):
            raise ValueError("reviewer_work_item_count must match reviewer_work_items length")
        expected_open_item_counts_by_expected_paper_reading: dict[str, int] = {}
        expected_open_paper_counts_by_expected_paper_reading: dict[str, int] = {}
        for item in self.reviewer_work_items:
            expected_open_item_counts_by_expected_paper_reading[item.expected_paper_reading] = (
                expected_open_item_counts_by_expected_paper_reading.get(
                    item.expected_paper_reading,
                    0,
                )
                + item.open_item_count
            )
            if item.open_paper_count is not None:
                expected_open_paper_counts_by_expected_paper_reading[
                    item.expected_paper_reading
                ] = (
                    expected_open_paper_counts_by_expected_paper_reading.get(
                        item.expected_paper_reading,
                        0,
                    )
                    + item.open_paper_count
                )
        if (
            "reviewer_open_item_counts_by_expected_paper_reading" in self.model_fields_set
            and self.reviewer_open_item_counts_by_expected_paper_reading
            != expected_open_item_counts_by_expected_paper_reading
        ):
            raise ValueError(
                "reviewer_open_item_counts_by_expected_paper_reading must match "
                "reviewer_work_items"
            )
        if (
            "reviewer_open_paper_counts_by_expected_paper_reading" in self.model_fields_set
            and self.reviewer_open_paper_counts_by_expected_paper_reading
            != expected_open_paper_counts_by_expected_paper_reading
        ):
            raise ValueError(
                "reviewer_open_paper_counts_by_expected_paper_reading must match "
                "reviewer_work_items"
            )
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingActiveReviewerHandoffRefreshReport(BaseModel):
    schema_version: Literal["evidence_grounding_active_reviewer_handoff_refresh.v1"] = (
        "evidence_grounding_active_reviewer_handoff_refresh.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    structured_brief_path: str = Field(..., min_length=1)
    structured_reviewed_csv_path: str = Field(..., min_length=1)
    structured_fill_review_status_path: str = Field(..., min_length=1)
    structured_open_records_csv_path: str = Field(..., min_length=1)
    p0_brief_path: str = Field(..., min_length=1)
    p0_reviewed_csv_path: str = Field(..., min_length=1)
    p0_open_issue_csv_path: str = Field(..., min_length=1)
    brief_audit_path: str = Field(..., min_length=1)
    brief_audit_all_passed: bool
    brief_audit_pass_count: int = Field(ge=0)
    brief_audit_fail_count: int = Field(ge=0)
    brief_audit_counts: dict[str, int] = Field(default_factory=dict)
    active_review_readiness_path: str | None = None
    active_review_ready_for_downstream_review_steps: bool | None = None
    active_review_readiness_blocker_count: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_refresh(self):
        for field_name in (
            "structured_brief_path",
            "structured_reviewed_csv_path",
            "structured_fill_review_status_path",
            "structured_open_records_csv_path",
            "p0_brief_path",
            "p0_reviewed_csv_path",
            "p0_open_issue_csv_path",
            "brief_audit_path",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} is required")
            setattr(self, field_name, value)
        if self.active_review_readiness_path is not None:
            self.active_review_readiness_path = self.active_review_readiness_path.strip() or None
        if self.brief_audit_all_passed and self.brief_audit_fail_count:
            raise ValueError("brief_audit_fail_count must be 0 when brief_audit_all_passed is true")
        self.brief_audit_counts = {
            key.strip(): value
            for key, value in self.brief_audit_counts.items()
            if key.strip()
        }
        for key, value in self.brief_audit_counts.items():
            if value < 0:
                raise ValueError(f"brief_audit_counts values must be non-negative: {key}")
        if self.active_review_readiness_path is None:
            if self.active_review_ready_for_downstream_review_steps is not None:
                raise ValueError("active readiness state requires active_review_readiness_path")
            if self.active_review_readiness_blocker_count is not None:
                raise ValueError("active readiness blocker count requires active_review_readiness_path")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class EvidenceGroundingActiveReviewReadinessRequest(BaseModel):
    structured_fill_review_status_path: str = Field(..., min_length=1)
    p0_summary_path: str = Field(..., min_length=1)
    active_brief_audit_path: str | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "structured_fill_review_status_path",
            "p0_summary_path",
            "active_brief_audit_path",
            "out",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if not self.structured_fill_review_status_path:
            raise ValueError("structured_fill_review_status_path is required")
        if not self.p0_summary_path:
            raise ValueError("p0_summary_path is required")
        return self


class EvidenceGroundingMetricComparison(BaseModel):
    name: str
    metric_group: Literal["runtime_proxy_metrics", "gold_scored_metrics"]
    direction: EvidenceGroundingMetricDirection
    baseline: float | int
    candidate: float | int
    delta: float
    tolerance: float
    passed: bool
    regression: bool


class EvidenceGroundingFailureCountComparison(BaseModel):
    name: str
    metric_group: EvidenceGroundingFailureComparisonGroup
    baseline: int = 0
    candidate: int = 0
    delta: int = 0
    passed: bool
    regression: bool

    @model_validator(mode="after")
    def validate_name_for_group(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("failure comparison name is required")
        if self.metric_group == "failure_counts_by_code":
            _validate_failure_code(self.name, field_name="failure_count_comparisons.name")
        elif self.name not in KNOWN_EVIDENCE_GROUNDING_PIPELINE_STAGES:
            raise ValueError(f"unknown evidence grounding pipeline stage: {self.name}")
        return self


class EvidenceGroundingStageMetricComparison(BaseModel):
    stage: str
    name: str
    metric_group: Literal["runtime_proxy_metrics", "gold_scored_metrics"]
    direction: EvidenceGroundingMetricDirection
    baseline: float | int
    candidate: float | int
    delta: float
    tolerance: float
    passed: bool
    regression: bool


class EvidenceGroundingThresholdCheck(BaseModel):
    name: str
    metric_group: Literal["runtime_proxy_metrics", "gold_scored_metrics"]
    direction: EvidenceGroundingMetricDirection
    threshold_kind: EvidenceGroundingThresholdKind
    threshold: float
    candidate: float | int | None = None
    stage: str | None = None
    status: EvidenceGroundingThresholdStatus
    passed: bool
    detail: str | None = None


class EvidenceGroundingComparisonDecision(BaseModel):
    passed: bool
    compared_metric_count: int
    failed_checks: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvidenceGroundingCorrectionReuseGainSummary(BaseModel):
    status: Literal["available", "not_available"] = "not_available"
    candidate_reuse_signal: bool = False
    candidate_correction_reuse_candidate_rate: float | int | None = None
    candidate_reviewed_eval_fixture_count: float | int | None = None
    improved_p0_metric_count: int = 0
    regressed_p0_metric_count: int = 0
    net_p0_improvement: float | None = None
    metric_improvements: dict[str, float] = Field(default_factory=dict)
    detail: str | None = None


class EvidenceGroundingScorecardComparisonReport(BaseModel):
    schema_version: Literal["evidence_grounding_scorecard_comparison.v1"] = (
        "evidence_grounding_scorecard_comparison.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    baseline: dict[str, Any]
    candidate: dict[str, Any]
    thresholds: dict[str, float]
    gate_policy: EvidenceGroundingMetricGatePolicy = "all_comparable"
    gate_metric_names: list[str] = Field(default_factory=list)
    threshold_policy: EvidenceGroundingThresholdPolicy = "none"
    comparisons: list[EvidenceGroundingMetricComparison]
    failure_count_comparisons: list[EvidenceGroundingFailureCountComparison] = Field(default_factory=list)
    stage_metric_comparisons: list[EvidenceGroundingStageMetricComparison] = Field(default_factory=list)
    threshold_checks: list[EvidenceGroundingThresholdCheck] = Field(default_factory=list)
    correction_reuse_gain: EvidenceGroundingCorrectionReuseGainSummary = Field(
        default_factory=EvidenceGroundingCorrectionReuseGainSummary
    )
    decision: EvidenceGroundingComparisonDecision


class EvidenceGroundingScorecardComparisonRequest(BaseModel):
    baseline_path: str = Field(..., min_length=1)
    candidate_path: str = Field(..., min_length=1)
    out: str | None = None
    tolerance: float = Field(default=0.0, ge=0.0)
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "all_comparable"
    threshold_preset: Literal["none", "p0_gold_minimum"] = "none"
    threshold_metric_values: dict[str, float] | None = None
    threshold_calibration_report_path: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.baseline_path = self.baseline_path.strip()
        self.candidate_path = self.candidate_path.strip()
        if self.out is not None:
            self.out = self.out.strip() or None
        if self.threshold_calibration_report_path is not None:
            self.threshold_calibration_report_path = self.threshold_calibration_report_path.strip() or None
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if not self.baseline_path:
            raise ValueError("baseline_path is required")
        if not self.candidate_path:
            raise ValueError("candidate_path is required")
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        return self


class EvidenceGroundingScorecardComparisonFromComparisonSuiteRequest(BaseModel):
    comparison_suite_path: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    tolerance: float = Field(default=0.0, ge=0.0)
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "all_comparable"
    threshold_preset: Literal["none", "p0_gold_minimum"] = "none"
    threshold_metric_values: dict[str, float] | None = None
    threshold_calibration_report_path: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.comparison_suite_path = self.comparison_suite_path.strip()
        self.out = self.out.strip()
        if not self.comparison_suite_path:
            raise ValueError("comparison_suite_path is required")
        if not self.out:
            raise ValueError("out is required")
        if self.threshold_calibration_report_path is not None:
            self.threshold_calibration_report_path = self.threshold_calibration_report_path.strip() or None
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        return self


class EvidenceGroundingFixedGoldsetComparisonSuiteRequest(BaseModel):
    goldset_manifest_path: str = Field(..., min_length=1)
    baseline_run_root: str = Field(..., min_length=1)
    candidate_run_root: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    suite_id: str = "evidence-grounding-fixed-goldset-comparison"
    baseline_benchmark_id: str = "baseline"
    candidate_benchmark_id: str = "candidate"
    run_dir_template: str = "{paper_id}"
    tolerance: float = Field(default=0.0, ge=0.0)
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "all_comparable"
    threshold_preset: Literal["none", "p0_gold_minimum"] = "none"
    threshold_metric_values: dict[str, float] | None = None
    threshold_calibration_report_path: str | None = None
    baseline_candidate_config: EvidenceGroundingCandidateConfig | None = None
    candidate_candidate_config: EvidenceGroundingCandidateConfig | None = None
    require_complete_candidate_config: bool = False
    require_ready: bool = True
    require_existing_runs: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "goldset_manifest_path",
            "baseline_run_root",
            "candidate_run_root",
            "out_dir",
            "suite_id",
            "baseline_benchmark_id",
            "candidate_benchmark_id",
            "run_dir_template",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.goldset_manifest_path:
            raise ValueError("goldset_manifest_path is required")
        if not self.baseline_run_root:
            raise ValueError("baseline_run_root is required")
        if not self.candidate_run_root:
            raise ValueError("candidate_run_root is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.suite_id:
            raise ValueError("suite_id is required")
        if not self.baseline_benchmark_id:
            raise ValueError("baseline_benchmark_id is required")
        if not self.candidate_benchmark_id:
            raise ValueError("candidate_benchmark_id is required")
        if not self.run_dir_template:
            raise ValueError("run_dir_template is required")
        if self.threshold_calibration_report_path is not None:
            self.threshold_calibration_report_path = self.threshold_calibration_report_path.strip() or None
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        return self


class EvidenceGroundingFixedGoldsetComparisonSuiteFromStagedGoldRequest(BaseModel):
    staging_manifest_path: str = Field(..., min_length=1)
    goldset_id: str = Field(..., min_length=1)
    goldset_split: str = Field(..., min_length=1)
    goldset_manifest_out: str = Field(..., min_length=1)
    baseline_run_root: str = Field(..., min_length=1)
    candidate_run_root: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    suite_id: str = "evidence-grounding-fixed-goldset-comparison"
    baseline_benchmark_id: str = "baseline"
    candidate_benchmark_id: str = "candidate"
    run_dir_template: str = "{paper_id}"
    tolerance: float = Field(default=0.0, ge=0.0)
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "all_comparable"
    threshold_preset: Literal["none", "p0_gold_minimum"] = "none"
    threshold_metric_values: dict[str, float] | None = None
    threshold_calibration_report_path: str | None = None
    baseline_candidate_config: EvidenceGroundingCandidateConfig | None = None
    candidate_candidate_config: EvidenceGroundingCandidateConfig | None = None
    require_complete_candidate_config: bool = False
    require_ready: bool = True
    require_existing_runs: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "staging_manifest_path",
            "goldset_id",
            "goldset_split",
            "goldset_manifest_out",
            "baseline_run_root",
            "candidate_run_root",
            "out_dir",
            "suite_id",
            "baseline_benchmark_id",
            "candidate_benchmark_id",
            "run_dir_template",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.staging_manifest_path:
            raise ValueError("staging_manifest_path is required")
        if not self.goldset_id:
            raise ValueError("goldset_id is required")
        if not self.goldset_split:
            raise ValueError("goldset_split is required")
        if not self.goldset_manifest_out:
            raise ValueError("goldset_manifest_out is required")
        if not self.baseline_run_root:
            raise ValueError("baseline_run_root is required")
        if not self.candidate_run_root:
            raise ValueError("candidate_run_root is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.suite_id:
            raise ValueError("suite_id is required")
        if not self.baseline_benchmark_id:
            raise ValueError("baseline_benchmark_id is required")
        if not self.candidate_benchmark_id:
            raise ValueError("candidate_benchmark_id is required")
        if not self.run_dir_template:
            raise ValueError("run_dir_template is required")
        if self.threshold_calibration_report_path is not None:
            self.threshold_calibration_report_path = self.threshold_calibration_report_path.strip() or None
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        return self


class EvidenceGroundingFixedGoldsetComparisonSuite(BaseModel):
    schema_version: Literal["evidence_grounding_fixed_goldset_comparison_suite.v1"] = (
        "evidence_grounding_fixed_goldset_comparison_suite.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    suite_id: str = Field(..., min_length=1)
    goldset_manifest_path: str = Field(..., min_length=1)
    baseline_manifest_path: str = Field(..., min_length=1)
    candidate_manifest_path: str = Field(..., min_length=1)
    baseline_report_path: str = Field(..., min_length=1)
    candidate_report_path: str = Field(..., min_length=1)
    run_readiness_report_path: str = Field(..., min_length=1)
    comparison_run_ready: bool = False
    run_readiness_fail_count: int = Field(ge=0)
    comparison_report_path: str = Field(..., min_length=1)
    comparison_passed: bool = False
    comparison_failed_checks: list[str] = Field(default_factory=list)
    comparison_regressions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_suite(self):
        for field_name in (
            "suite_id",
            "goldset_manifest_path",
            "baseline_manifest_path",
            "candidate_manifest_path",
            "baseline_report_path",
            "candidate_report_path",
            "run_readiness_report_path",
            "comparison_report_path",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        self.comparison_failed_checks = _dedupe_non_empty_strings(
            self.comparison_failed_checks,
            field_name="comparison_failed_checks",
        ) if self.comparison_failed_checks else []
        self.comparison_regressions = _dedupe_non_empty_strings(
            self.comparison_regressions,
            field_name="comparison_regressions",
        ) if self.comparison_regressions else []
        return self


class EvidenceGroundingFixedGoldsetComparisonSuitePackage(BaseModel):
    schema_version: Literal["evidence_grounding_fixed_goldset_comparison_suite_package.v1"] = (
        "evidence_grounding_fixed_goldset_comparison_suite_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    package_id: str = Field(..., min_length=1)
    baseline_run_package_path: str = Field(..., min_length=1)
    candidate_run_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    comparison_suite_paths: list[str] = Field(default_factory=list)
    comparison_report_paths: list[str] = Field(default_factory=list)
    run_readiness_report_paths: list[str] = Field(default_factory=list)
    comparison_suites: list[EvidenceGroundingFixedGoldsetComparisonSuite] = Field(default_factory=list)
    suite_count: int = Field(ge=0)
    comparison_pass_count: int = Field(ge=0)
    comparison_fail_count: int = Field(ge=0)
    run_readiness_fail_count: int = Field(ge=0)
    baseline_run_package_scorecard_readiness_fields_present: bool = True
    candidate_run_package_scorecard_readiness_fields_present: bool = True
    baseline_scorecard_readiness_pass_count: int = Field(default=0, ge=0)
    baseline_scorecard_readiness_warn_count: int = Field(default=0, ge=0)
    baseline_scorecard_readiness_fail_count: int = Field(default=0, ge=0)
    baseline_scorecard_not_ready_candidate_ids: list[str] = Field(default_factory=list)
    candidate_scorecard_readiness_pass_count: int = Field(default=0, ge=0)
    candidate_scorecard_readiness_warn_count: int = Field(default=0, ge=0)
    candidate_scorecard_readiness_fail_count: int = Field(default=0, ge=0)
    candidate_scorecard_not_ready_candidate_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        for field_name in (
            "package_id",
            "baseline_run_package_path",
            "candidate_run_package_path",
            "out_dir",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        self.comparison_suite_paths = _dedupe_non_empty_strings(
            self.comparison_suite_paths,
            field_name="comparison_suite_paths",
        ) if self.comparison_suite_paths else []
        self.comparison_report_paths = _dedupe_non_empty_strings(
            self.comparison_report_paths,
            field_name="comparison_report_paths",
        ) if self.comparison_report_paths else []
        self.run_readiness_report_paths = _dedupe_non_empty_strings(
            self.run_readiness_report_paths,
            field_name="run_readiness_report_paths",
        ) if self.run_readiness_report_paths else []
        self.baseline_scorecard_not_ready_candidate_ids = (
            _dedupe_non_empty_strings(
                self.baseline_scorecard_not_ready_candidate_ids,
                field_name="baseline_scorecard_not_ready_candidate_ids",
            )
            if self.baseline_scorecard_not_ready_candidate_ids
            else []
        )
        self.candidate_scorecard_not_ready_candidate_ids = (
            _dedupe_non_empty_strings(
                self.candidate_scorecard_not_ready_candidate_ids,
                field_name="candidate_scorecard_not_ready_candidate_ids",
            )
            if self.candidate_scorecard_not_ready_candidate_ids
            else []
        )
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.baseline_run_package_path:
            raise ValueError("baseline_run_package_path is required")
        if not self.candidate_run_package_path:
            raise ValueError("candidate_run_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        return self


class EvidenceGroundingFixedGoldsetComparisonSuitePackageFromRunPackagesRequest(BaseModel):
    baseline_run_package_path: str = Field(..., min_length=1)
    candidate_run_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    package_id: str = "evidence-grounding-fixed-goldset-comparison-suite-package"
    suite_id_prefix: str = "evidence-grounding-fixed-goldset-comparison"
    tolerance: float = 0.0
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "all_comparable"
    threshold_preset: Literal["none", "p0_gold_minimum"] = "none"
    threshold_metric_values: dict[str, float] | None = None
    threshold_calibration_report_path: str | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "baseline_run_package_path",
            "candidate_run_package_path",
            "out_dir",
            "package_id",
            "suite_id_prefix",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.baseline_run_package_path:
            raise ValueError("baseline_run_package_path is required")
        if not self.candidate_run_package_path:
            raise ValueError("candidate_run_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.suite_id_prefix:
            raise ValueError("suite_id_prefix is required")
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        if self.threshold_calibration_report_path is not None:
            self.threshold_calibration_report_path = self.threshold_calibration_report_path.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingThresholdCalibrationRecommendation(BaseModel):
    name: str
    metric_group: Literal["runtime_proxy_metrics", "gold_scored_metrics"]
    direction: EvidenceGroundingMetricDirection
    threshold_kind: EvidenceGroundingThresholdKind
    status: Literal["available", "not_available"] = "not_available"
    observed_values: list[float] = Field(default_factory=list)
    report_count: int = 0
    available_count: int = 0
    recommended_threshold: float | None = None
    source_reports: list[str] = Field(default_factory=list)
    detail: str | None = None

    @model_validator(mode="after")
    def validate_recommendation(self):
        if self.status == "available" and self.recommended_threshold is None:
            raise ValueError("available calibration recommendations require recommended_threshold")
        if self.status == "not_available" and self.recommended_threshold is not None:
            raise ValueError("not_available calibration recommendations must not carry recommended_threshold")
        return self


class EvidenceGroundingThresholdCalibrationReport(BaseModel):
    schema_version: Literal["evidence_grounding_threshold_calibration.v1"] = (
        "evidence_grounding_threshold_calibration.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    calibration_id: str
    metric_preset: EvidenceGroundingThresholdCalibrationPreset
    report_count: int = 0
    recommendations: list[EvidenceGroundingThresholdCalibrationRecommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceGroundingThresholdCalibrationRequest(BaseModel):
    report_paths: list[str] = Field(..., min_length=1)
    calibration_id: str = "evidence-grounding-threshold-calibration"
    metric_names: list[str] | None = None
    metric_preset: EvidenceGroundingThresholdCalibrationPreset = "p0_gold"
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.report_paths = _dedupe_non_empty_strings(self.report_paths, field_name="report_paths")
        self.calibration_id = self.calibration_id.strip()
        if not self.calibration_id:
            raise ValueError("calibration_id is required")
        if self.metric_names is not None:
            self.metric_names = _dedupe_non_empty_strings(self.metric_names, field_name="metric_names")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingThresholdCalibrationFromComparisonSuiteRequest(BaseModel):
    comparison_suite_path: str = Field(..., min_length=1)
    calibration_id: str = "evidence-grounding-threshold-calibration"
    metric_names: list[str] | None = None
    metric_preset: EvidenceGroundingThresholdCalibrationPreset = "p0_gold"
    include_baseline_report: bool = False
    include_candidate_report: bool = True
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.comparison_suite_path = self.comparison_suite_path.strip()
        self.calibration_id = self.calibration_id.strip()
        if not self.comparison_suite_path:
            raise ValueError("comparison_suite_path is required")
        if not self.calibration_id:
            raise ValueError("calibration_id is required")
        if not self.include_baseline_report and not self.include_candidate_report:
            raise ValueError("at least one suite benchmark report must be selected")
        if self.metric_names is not None:
            self.metric_names = _dedupe_non_empty_strings(self.metric_names, field_name="metric_names")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingThresholdAdoptionReviewCheck(BaseModel):
    name: str
    status: EvidenceGroundingThresholdAdoptionReviewStatus
    evidence: list[str] = Field(default_factory=list)
    detail: str | None = None


class EvidenceGroundingThresholdAdoptionReviewReport(BaseModel):
    schema_version: Literal["evidence_grounding_threshold_adoption_review.v1"] = (
        "evidence_grounding_threshold_adoption_review.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    adoption_id: str
    calibration_report_path: str
    comparison_suite_path: str | None = None
    comparison_report_path: str
    run_readiness_report_path: str
    reviewer_approval_reference: str | None = None
    required_metric_names: list[str] = Field(default_factory=list)
    threshold_metric_values: dict[str, float] = Field(default_factory=dict)
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    production_threshold_ready: bool = False
    checks: list[EvidenceGroundingThresholdAdoptionReviewCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceGroundingThresholdAdoptionReviewRequest(BaseModel):
    calibration_report_path: str = Field(..., min_length=1)
    comparison_suite_path: str | None = None
    comparison_report_path: str | None = None
    run_readiness_report_path: str | None = None
    adoption_id: str = "evidence-grounding-threshold-adoption-review"
    required_metric_names: list[str] | None = None
    reviewer_approval_reference: str | None = None
    allow_production_threshold_ready: bool = False
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.calibration_report_path = self.calibration_report_path.strip()
        if self.comparison_suite_path is not None:
            self.comparison_suite_path = self.comparison_suite_path.strip() or None
        if self.comparison_report_path is not None:
            self.comparison_report_path = self.comparison_report_path.strip() or None
        if self.run_readiness_report_path is not None:
            self.run_readiness_report_path = self.run_readiness_report_path.strip() or None
        self.adoption_id = self.adoption_id.strip()
        if not self.calibration_report_path:
            raise ValueError("calibration_report_path is required")
        if not self.comparison_suite_path and not self.comparison_report_path:
            raise ValueError("comparison_report_path is required unless comparison_suite_path is provided")
        if not self.comparison_suite_path and not self.run_readiness_report_path:
            raise ValueError("run_readiness_report_path is required unless comparison_suite_path is provided")
        if not self.adoption_id:
            raise ValueError("adoption_id is required")
        if self.required_metric_names is not None:
            self.required_metric_names = _dedupe_non_empty_strings(
                self.required_metric_names,
                field_name="required_metric_names",
            )
        if self.reviewer_approval_reference is not None:
            self.reviewer_approval_reference = self.reviewer_approval_reference.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingThresholdAdoptionReviewFromComparisonSuiteRequest(BaseModel):
    comparison_suite_path: str = Field(..., min_length=1)
    calibration_report_out: str = Field(..., min_length=1)
    threshold_checked_comparison_report_out: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    calibration_id: str = "evidence-grounding-threshold-calibration"
    calibration_metric_names: list[str] | None = None
    calibration_metric_preset: EvidenceGroundingThresholdCalibrationPreset = "p0_gold"
    include_baseline_report: bool = False
    include_candidate_report: bool = True
    tolerance: float = Field(default=0.0, ge=0.0)
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "p0_gold"
    threshold_metric_values: dict[str, float] | None = None
    adoption_id: str = "evidence-grounding-threshold-adoption-review"
    required_metric_names: list[str] | None = None
    reviewer_approval_reference: str | None = None
    allow_production_threshold_ready: bool = False

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "comparison_suite_path",
            "calibration_report_out",
            "threshold_checked_comparison_report_out",
            "out",
            "calibration_id",
            "adoption_id",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.comparison_suite_path:
            raise ValueError("comparison_suite_path is required")
        if not self.calibration_report_out:
            raise ValueError("calibration_report_out is required")
        if not self.threshold_checked_comparison_report_out:
            raise ValueError("threshold_checked_comparison_report_out is required")
        if not self.out:
            raise ValueError("out is required")
        if not self.calibration_id:
            raise ValueError("calibration_id is required")
        if not self.adoption_id:
            raise ValueError("adoption_id is required")
        if not self.include_baseline_report and not self.include_candidate_report:
            raise ValueError("at least one suite benchmark report must be selected for calibration")
        if self.calibration_metric_names is not None:
            self.calibration_metric_names = _dedupe_non_empty_strings(
                self.calibration_metric_names,
                field_name="calibration_metric_names",
            )
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if self.required_metric_names is not None:
            self.required_metric_names = _dedupe_non_empty_strings(
                self.required_metric_names,
                field_name="required_metric_names",
            )
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        if self.reviewer_approval_reference is not None:
            self.reviewer_approval_reference = self.reviewer_approval_reference.strip() or None
        return self


class EvidenceGroundingThresholdAdoptionReviewPackage(BaseModel):
    schema_version: Literal["evidence_grounding_threshold_adoption_review_package.v1"] = (
        "evidence_grounding_threshold_adoption_review_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    package_id: str = Field(..., min_length=1)
    comparison_suite_package_path: str = Field(..., min_length=1)
    calibration_report_path: str = Field(..., min_length=1)
    threshold_checked_comparison_report_paths: list[str] = Field(default_factory=list)
    threshold_adoption_review_paths: list[str] = Field(default_factory=list)
    threshold_adoption_reviews: list[EvidenceGroundingThresholdAdoptionReviewReport] = Field(default_factory=list)
    comparison_suite_count: int = Field(ge=0)
    production_threshold_ready_count: int = Field(ge=0)
    production_threshold_blocked_count: int = Field(ge=0)
    comparison_suite_package_scorecard_context_fields_present: bool = True
    baseline_run_package_scorecard_readiness_fields_present: bool = True
    candidate_run_package_scorecard_readiness_fields_present: bool = True
    baseline_scorecard_readiness_pass_count: int = Field(default=0, ge=0)
    baseline_scorecard_readiness_warn_count: int = Field(default=0, ge=0)
    baseline_scorecard_readiness_fail_count: int = Field(default=0, ge=0)
    baseline_scorecard_not_ready_candidate_ids: list[str] = Field(default_factory=list)
    candidate_scorecard_readiness_pass_count: int = Field(default=0, ge=0)
    candidate_scorecard_readiness_warn_count: int = Field(default=0, ge=0)
    candidate_scorecard_readiness_fail_count: int = Field(default=0, ge=0)
    candidate_scorecard_not_ready_candidate_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        for field_name in ("package_id", "comparison_suite_package_path", "calibration_report_path"):
            setattr(self, field_name, getattr(self, field_name).strip())
        self.threshold_checked_comparison_report_paths = _dedupe_non_empty_strings(
            self.threshold_checked_comparison_report_paths,
            field_name="threshold_checked_comparison_report_paths",
        ) if self.threshold_checked_comparison_report_paths else []
        self.threshold_adoption_review_paths = _dedupe_non_empty_strings(
            self.threshold_adoption_review_paths,
            field_name="threshold_adoption_review_paths",
        ) if self.threshold_adoption_review_paths else []
        self.baseline_scorecard_not_ready_candidate_ids = (
            _dedupe_non_empty_strings(
                self.baseline_scorecard_not_ready_candidate_ids,
                field_name="baseline_scorecard_not_ready_candidate_ids",
            )
            if self.baseline_scorecard_not_ready_candidate_ids
            else []
        )
        self.candidate_scorecard_not_ready_candidate_ids = (
            _dedupe_non_empty_strings(
                self.candidate_scorecard_not_ready_candidate_ids,
                field_name="candidate_scorecard_not_ready_candidate_ids",
            )
            if self.candidate_scorecard_not_ready_candidate_ids
            else []
        )
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.comparison_suite_package_path:
            raise ValueError("comparison_suite_package_path is required")
        if not self.calibration_report_path:
            raise ValueError("calibration_report_path is required")
        return self


class EvidenceGroundingThresholdAdoptionReviewPackageFromComparisonSuitePackageRequest(BaseModel):
    comparison_suite_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    package_id: str = "evidence-grounding-threshold-adoption-review-package"
    calibration_report_out: str | None = None
    calibration_id: str = "evidence-grounding-threshold-calibration"
    calibration_metric_names: list[str] | None = None
    calibration_metric_preset: EvidenceGroundingThresholdCalibrationPreset = "p0_gold"
    include_baseline_report: bool = False
    include_candidate_report: bool = True
    tolerance: float = Field(default=0.0, ge=0.0)
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "p0_gold"
    threshold_metric_values: dict[str, float] | None = None
    adoption_id_prefix: str = "evidence-grounding-threshold-adoption-review"
    required_metric_names: list[str] | None = None
    reviewer_approval_reference: str | None = None
    allow_production_threshold_ready: bool = False
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "comparison_suite_package_path",
            "out_dir",
            "package_id",
            "calibration_id",
            "adoption_id_prefix",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.comparison_suite_package_path:
            raise ValueError("comparison_suite_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.calibration_id:
            raise ValueError("calibration_id is required")
        if not self.adoption_id_prefix:
            raise ValueError("adoption_id_prefix is required")
        if not self.include_baseline_report and not self.include_candidate_report:
            raise ValueError("at least one suite benchmark report must be selected for calibration")
        if self.calibration_report_out is not None:
            self.calibration_report_out = self.calibration_report_out.strip() or None
        if self.calibration_metric_names is not None:
            self.calibration_metric_names = _dedupe_non_empty_strings(
                self.calibration_metric_names,
                field_name="calibration_metric_names",
            )
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        if self.required_metric_names is not None:
            self.required_metric_names = _dedupe_non_empty_strings(
                self.required_metric_names,
                field_name="required_metric_names",
            )
        if self.reviewer_approval_reference is not None:
            self.reviewer_approval_reference = self.reviewer_approval_reference.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingContractCompatibilityItem(BaseModel):
    path: str
    schema_version: str | None = None
    task_export_csv_path: str | None = None
    layer: str | None = None
    canonical_status: str | None = None
    status: Literal["pass", "warn", "fail"]
    findings: list[str] = Field(default_factory=list)


class EvidenceGroundingContractCompatibilityReport(BaseModel):
    schema_version: Literal["evidence_grounding_contract_compatibility.v1"] = (
        "evidence_grounding_contract_compatibility.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    compatibility_id: str
    artifact_count: int = 0
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    external_contract_ready: bool = False
    items: list[EvidenceGroundingContractCompatibilityItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceGroundingContractCompatibilityAuditRequest(BaseModel):
    artifact_paths: list[str] = Field(..., min_length=1)
    compatibility_id: str = "evidence-grounding-contract-compatibility"
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.artifact_paths = _dedupe_non_empty_strings(self.artifact_paths, field_name="artifact_paths")
        self.compatibility_id = self.compatibility_id.strip()
        if not self.compatibility_id:
            raise ValueError("compatibility_id is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingContractCompatibilityFromComparisonSuiteRequest(BaseModel):
    comparison_suite_path: str = Field(..., min_length=1)
    threshold_calibration_report_path: str | None = None
    threshold_adoption_review_path: str | None = None
    compatibility_id: str = "evidence-grounding-contract-compatibility"
    include_embedded_scorecards: bool = True
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.comparison_suite_path = self.comparison_suite_path.strip()
        self.compatibility_id = self.compatibility_id.strip()
        if not self.comparison_suite_path:
            raise ValueError("comparison_suite_path is required")
        if not self.compatibility_id:
            raise ValueError("compatibility_id is required")
        if self.threshold_calibration_report_path is not None:
            self.threshold_calibration_report_path = self.threshold_calibration_report_path.strip() or None
        if self.threshold_adoption_review_path is not None:
            self.threshold_adoption_review_path = self.threshold_adoption_review_path.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingContractReadinessCheck(BaseModel):
    name: str
    status: EvidenceGroundingContractReadinessStatus
    evidence: list[str] = Field(default_factory=list)
    detail: str | None = None


class EvidenceGroundingContractReadinessReport(BaseModel):
    schema_version: Literal["evidence_grounding_contract_readiness.v1"] = (
        "evidence_grounding_contract_readiness.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    readiness_id: str
    compatibility_report_path: str
    migration_plan_path: str | None = None
    backfill_plan_path: str | None = None
    public_contract_doc_path: str | None = None
    reviewer_approval_reference: str | None = None
    artifact_count: int = 0
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    external_contract_ready: bool = False
    checks: list[EvidenceGroundingContractReadinessCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceGroundingContractReadinessAuditRequest(BaseModel):
    compatibility_report_path: str = Field(..., min_length=1)
    readiness_id: str = "evidence-grounding-contract-readiness"
    migration_plan_path: str | None = None
    backfill_plan_path: str | None = None
    public_contract_doc_path: str | None = None
    reviewer_approval_reference: str | None = None
    allow_external_contract_ready: bool = False
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.compatibility_report_path = self.compatibility_report_path.strip()
        self.readiness_id = self.readiness_id.strip()
        if not self.compatibility_report_path:
            raise ValueError("compatibility_report_path is required")
        if not self.readiness_id:
            raise ValueError("readiness_id is required")
        if self.migration_plan_path is not None:
            self.migration_plan_path = self.migration_plan_path.strip() or None
        if self.backfill_plan_path is not None:
            self.backfill_plan_path = self.backfill_plan_path.strip() or None
        if self.public_contract_doc_path is not None:
            self.public_contract_doc_path = self.public_contract_doc_path.strip() or None
        if self.reviewer_approval_reference is not None:
            self.reviewer_approval_reference = self.reviewer_approval_reference.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingContractReadinessFromComparisonSuiteRequest(BaseModel):
    comparison_suite_path: str = Field(..., min_length=1)
    compatibility_report_out: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    threshold_calibration_report_path: str | None = None
    threshold_adoption_review_path: str | None = None
    additional_artifact_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Additional review/contract artifacts to include in compatibility, such as "
            "evidence_grounding_scorecard.json / evidence_grounding_scorecard.v1, "
            "scorecard_input_backfill.json / evidence_grounding_scorecard_input_backfill.v1, "
            "evidence_grounding_benchmark.json / evidence_grounding_benchmark.v1, "
            "evidence_grounding_benchmark_manifest_package.json / "
            "evidence_grounding_benchmark_manifest_package.v1, "
            "evidence_grounding_benchmark_run_package.json / "
            "evidence_grounding_benchmark_run_package.v1, "
            "evidence_grounding_scorecard_comparison.json / "
            "evidence_grounding_scorecard_comparison.v1, "
            "evidence_grounding_fixed_goldset_comparison_suite.json / "
            "evidence_grounding_fixed_goldset_comparison_suite.v1, "
            "evidence_grounding_fixed_goldset_comparison_suite_package.json / "
            "evidence_grounding_fixed_goldset_comparison_suite_package.v1, "
            "evidence_grounding_fixed_goldset_run_readiness.json / "
            "evidence_grounding_fixed_goldset_run_readiness.v1, "
            "evidence_grounding_threshold_calibration.json / "
            "evidence_grounding_threshold_calibration.v1, "
            "evidence_grounding_threshold_adoption_review.json / "
            "evidence_grounding_threshold_adoption_review.v1, "
            "evidence_grounding_threshold_adoption_package.json / "
            "evidence_grounding_threshold_adoption_review_package.v1, "
            "claim_evidence_eval_candidates.json / claim_evidence_eval_candidate_export.v1, "
            "claim_evidence_correction_repair_plan.json / claim_evidence_correction_repair_plan.v1, "
            "claim_evidence_correction_repair_patch_template.json / "
            "claim_evidence_correction_repair_patch_template.v1, "
            "p0_overstatement_review_packet.json / evidence_grounding_p0_overstatement_review_packet.v1, "
            "p0_overstatement_review_summary.json / evidence_grounding_p0_overstatement_review_summary.v1, "
            "active_review_readiness.json / evidence_grounding_active_review_readiness.v1, "
            "active_reviewer_handoff_refresh.json / evidence_grounding_active_reviewer_handoff_refresh.v1, "
            "claim_evidence_reviewed_eval_fixtures.json / "
            "claim_evidence_reviewed_eval_fixtures_bundle.v1, "
            "paper_understanding_gold_release_package.json / paper_understanding_gold_release_package.v1, "
            "or paper_understanding_gold_release_readiness.json / paper_understanding_gold_release_readiness.v1."
        ),
    )
    compatibility_id: str = "evidence-grounding-contract-compatibility"
    readiness_id: str = "evidence-grounding-contract-readiness"
    include_embedded_scorecards: bool = True
    migration_plan_path: str | None = None
    backfill_plan_path: str | None = None
    public_contract_doc_path: str | None = None
    reviewer_approval_reference: str | None = None
    allow_external_contract_ready: bool = False

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "comparison_suite_path",
            "compatibility_report_out",
            "out",
            "compatibility_id",
            "readiness_id",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.comparison_suite_path:
            raise ValueError("comparison_suite_path is required")
        if not self.compatibility_report_out:
            raise ValueError("compatibility_report_out is required")
        if not self.out:
            raise ValueError("out is required")
        if not self.compatibility_id:
            raise ValueError("compatibility_id is required")
        if not self.readiness_id:
            raise ValueError("readiness_id is required")
        for field_name in (
            "threshold_calibration_report_path",
            "threshold_adoption_review_path",
            "migration_plan_path",
            "backfill_plan_path",
            "public_contract_doc_path",
            "reviewer_approval_reference",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        self.additional_artifact_paths = [
            path.strip() for path in self.additional_artifact_paths if path.strip()
        ]
        return self


class EvidenceGroundingContractReadinessFromThresholdAdoptionPackageRequest(BaseModel):
    threshold_adoption_package_path: str = Field(..., min_length=1)
    compatibility_report_out: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    additional_artifact_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Additional review/contract artifacts to include in compatibility, such as "
            "evidence_grounding_scorecard.json / evidence_grounding_scorecard.v1, "
            "scorecard_input_backfill.json / evidence_grounding_scorecard_input_backfill.v1, "
            "evidence_grounding_benchmark.json / evidence_grounding_benchmark.v1, "
            "evidence_grounding_benchmark_manifest_package.json / "
            "evidence_grounding_benchmark_manifest_package.v1, "
            "evidence_grounding_benchmark_run_package.json / "
            "evidence_grounding_benchmark_run_package.v1, "
            "evidence_grounding_scorecard_comparison.json / "
            "evidence_grounding_scorecard_comparison.v1, "
            "evidence_grounding_fixed_goldset_comparison_suite.json / "
            "evidence_grounding_fixed_goldset_comparison_suite.v1, "
            "evidence_grounding_fixed_goldset_comparison_suite_package.json / "
            "evidence_grounding_fixed_goldset_comparison_suite_package.v1, "
            "evidence_grounding_fixed_goldset_run_readiness.json / "
            "evidence_grounding_fixed_goldset_run_readiness.v1, "
            "evidence_grounding_threshold_calibration.json / "
            "evidence_grounding_threshold_calibration.v1, "
            "evidence_grounding_threshold_adoption_review.json / "
            "evidence_grounding_threshold_adoption_review.v1, "
            "evidence_grounding_threshold_adoption_package.json / "
            "evidence_grounding_threshold_adoption_review_package.v1, "
            "claim_evidence_eval_candidates.json / claim_evidence_eval_candidate_export.v1, "
            "claim_evidence_correction_repair_plan.json / claim_evidence_correction_repair_plan.v1, "
            "claim_evidence_correction_repair_patch_template.json / "
            "claim_evidence_correction_repair_patch_template.v1, "
            "p0_overstatement_review_packet.json / evidence_grounding_p0_overstatement_review_packet.v1, "
            "p0_overstatement_review_summary.json / evidence_grounding_p0_overstatement_review_summary.v1, "
            "active_review_readiness.json / evidence_grounding_active_review_readiness.v1, "
            "active_reviewer_handoff_refresh.json / evidence_grounding_active_reviewer_handoff_refresh.v1, "
            "claim_evidence_reviewed_eval_fixtures.json / "
            "claim_evidence_reviewed_eval_fixtures_bundle.v1, "
            "paper_understanding_gold_release_package.json / paper_understanding_gold_release_package.v1, "
            "or paper_understanding_gold_release_readiness.json / paper_understanding_gold_release_readiness.v1."
        ),
    )
    compatibility_id: str = "evidence-grounding-contract-compatibility"
    readiness_id: str = "evidence-grounding-contract-readiness"
    include_embedded_scorecards: bool = True
    migration_plan_path: str | None = None
    backfill_plan_path: str | None = None
    public_contract_doc_path: str | None = None
    reviewer_approval_reference: str | None = None
    allow_external_contract_ready: bool = False

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "threshold_adoption_package_path",
            "compatibility_report_out",
            "out",
            "compatibility_id",
            "readiness_id",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.threshold_adoption_package_path:
            raise ValueError("threshold_adoption_package_path is required")
        if not self.compatibility_report_out:
            raise ValueError("compatibility_report_out is required")
        if not self.out:
            raise ValueError("out is required")
        if not self.compatibility_id:
            raise ValueError("compatibility_id is required")
        if not self.readiness_id:
            raise ValueError("readiness_id is required")
        for field_name in (
            "migration_plan_path",
            "backfill_plan_path",
            "public_contract_doc_path",
            "reviewer_approval_reference",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        self.additional_artifact_paths = [
            path.strip() for path in self.additional_artifact_paths if path.strip()
        ]
        return self


class EvidenceGroundingFixedGoldsetRunReadinessItem(BaseModel):
    paper_id: str
    run_dir: str
    status: EvidenceGroundingFixedGoldsetRunReadinessStatus
    run_dir_exists: bool = False
    declared_paper_ids: list[str] = Field(default_factory=list)
    run_identity_match: bool | None = None
    run_identity_conflict: bool = False
    run_identity_metadata_error_count: int = 0
    present_required_artifacts: list[str] = Field(default_factory=list)
    missing_required_artifacts: list[str] = Field(default_factory=list)
    malformed_required_artifacts: list[str] = Field(default_factory=list)
    present_optional_artifacts: list[str] = Field(default_factory=list)
    missing_optional_artifacts: list[str] = Field(default_factory=list)
    gold_readiness_status: str | None = None
    gold_readiness_reason_codes: list[str] = Field(default_factory=list)


class EvidenceGroundingFixedGoldsetRunReadinessLaneSummary(BaseModel):
    lane: Literal["baseline", "candidate"]
    run_root: str
    item_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    missing_run_count: int = 0
    missing_required_artifact_count: int = 0
    malformed_required_artifact_count: int = 0
    identity_mismatch_count: int = 0
    identity_conflict_count: int = 0
    identity_metadata_error_count: int = 0
    items: list[EvidenceGroundingFixedGoldsetRunReadinessItem] = Field(default_factory=list)


class EvidenceGroundingFixedGoldsetRunReadinessReport(BaseModel):
    schema_version: Literal["evidence_grounding_fixed_goldset_run_readiness.v1"] = (
        "evidence_grounding_fixed_goldset_run_readiness.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    readiness_id: str
    goldset_manifest_path: str
    goldset_id: str | None = None
    goldset_split: str | None = None
    goldset_item_count: int = 0
    gold_validation_invalid_count: int = 0
    required_artifacts: list[str] = Field(default_factory=list)
    optional_artifacts: list[str] = Field(default_factory=list)
    lane_summaries: list[EvidenceGroundingFixedGoldsetRunReadinessLaneSummary] = Field(default_factory=list)
    pass_count: int = 0
    fail_count: int = 0
    comparison_run_ready: bool = False
    warnings: list[str] = Field(default_factory=list)


class EvidenceGroundingFixedGoldsetRunReadinessAuditRequest(BaseModel):
    goldset_manifest_path: str = Field(..., min_length=1)
    baseline_run_root: str = Field(..., min_length=1)
    candidate_run_root: str = Field(..., min_length=1)
    baseline_run_dir_map_path: str | None = None
    candidate_run_dir_map_path: str | None = None
    readiness_id: str = "evidence-grounding-fixed-goldset-run-readiness"
    run_dir_template: str = "{paper_id}"
    required_artifacts: list[str] | None = None
    optional_artifacts: list[str] | None = None
    require_ready: bool = True
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.goldset_manifest_path = self.goldset_manifest_path.strip()
        self.baseline_run_root = self.baseline_run_root.strip()
        self.candidate_run_root = self.candidate_run_root.strip()
        if self.baseline_run_dir_map_path is not None:
            self.baseline_run_dir_map_path = self.baseline_run_dir_map_path.strip() or None
        if self.candidate_run_dir_map_path is not None:
            self.candidate_run_dir_map_path = self.candidate_run_dir_map_path.strip() or None
        self.readiness_id = self.readiness_id.strip()
        self.run_dir_template = self.run_dir_template.strip()
        if not self.goldset_manifest_path:
            raise ValueError("goldset_manifest_path is required")
        if not self.baseline_run_root:
            raise ValueError("baseline_run_root is required")
        if not self.candidate_run_root:
            raise ValueError("candidate_run_root is required")
        if not self.readiness_id:
            raise ValueError("readiness_id is required")
        if not self.run_dir_template:
            raise ValueError("run_dir_template is required")
        if self.required_artifacts is not None:
            self.required_artifacts = _dedupe_non_empty_strings(
                self.required_artifacts,
                field_name="required_artifacts",
            )
        if self.optional_artifacts is not None:
            self.optional_artifacts = _dedupe_non_empty_strings(
                self.optional_artifacts,
                field_name="optional_artifacts",
            )
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class EvidenceGroundingRoadmapCompletionNextAction(BaseModel):
    requirement_id: str
    action: str
    phase: str | None = None
    kind: Literal[
        "human_review_with_command",
        "human_review_without_command",
        "nonhuman_without_command",
        "placeholder_command",
        "prerequisite_gated_command",
        "ready_to_run_command",
    ] | None = None
    requires_human_review: bool = False
    has_command_hint: bool = False
    has_unresolved_command_placeholder: bool = False
    command_hint: str | None = None
    unresolved_command_placeholders: list[str] = Field(default_factory=list)
    missing_metric_inputs: list[str] = Field(default_factory=list)
    human_review_open_task_ids: list[str] = Field(default_factory=list)
    blocked_by_requirement_ids: list[str] = Field(default_factory=list)
    blocker_reasons: list[str] = Field(default_factory=list)


class EvidenceGroundingRoadmapCompletionFrontierSummary(BaseModel):
    requirement_id: str
    phase: str | None = None
    action: str = ""
    command_hint: str | None = None
    kind: Literal[
        "human_review_with_command",
        "human_review_without_command",
        "nonhuman_without_command",
        "placeholder_command",
        "ready_to_run_command",
    ]
    requires_human_review: bool = False
    has_command_hint: bool = False
    has_unresolved_command_placeholder: bool = False
    unresolved_command_placeholders: list[str] = Field(default_factory=list)
    missing_metric_inputs: list[str] = Field(default_factory=list)
    human_review_open_csv_paths: list[str] = Field(default_factory=list)
    human_review_open_csv_row_count: int = Field(default=0, ge=0)
    human_review_open_csv_missing_value_counts_by_field: dict[str, int] = Field(default_factory=dict)
    human_review_open_csv_missing_suggestion_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_suggestion_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_context_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_context_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_keys_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_values_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_task_ids: list[str] = Field(default_factory=list)
    human_review_open_task_ids_by_field: dict[str, list[str]] = Field(default_factory=dict)
    blocker_reasons: list[str] = Field(default_factory=list)
    blocked_by_requirement_ids: list[str] = Field(default_factory=list)


class EvidenceGroundingRoadmapCompletionCheck(BaseModel):
    requirement_id: str
    requirement: str
    status: EvidenceGroundingRoadmapCompletionStatus
    evidence: list[str] = Field(default_factory=list)
    detail: str | None = None
    next_actions: list[str] = Field(default_factory=list)


class EvidenceGroundingRoadmapCompletionAuditReport(BaseModel):
    schema_version: Literal["evidence_grounding_roadmap_completion_audit.v1"] = (
        "evidence_grounding_roadmap_completion_audit.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    audit_id: str
    input_paths: dict[str, str] = Field(default_factory=dict)
    additional_artifact_paths: list[str] = Field(default_factory=list)
    additional_artifact_count: int = Field(default=0, ge=0)
    active_review_readiness_path: str | None = None
    active_review_readiness_ready_for_downstream_review_steps: bool | None = None
    active_review_readiness_blocker_count: int | None = Field(default=None, ge=0)
    active_review_readiness_blocker_ids: list[str] = Field(default_factory=list)
    active_review_readiness_structured_reviewed_csv_path: str | None = None
    active_review_readiness_structured_open_csv_path: str | None = None
    active_review_readiness_structured_open_record_csv_path: str | None = None
    active_review_readiness_p0_source_packet_path: str | None = None
    active_review_readiness_p0_source_reviewed_csv_path: str | None = None
    active_review_readiness_p0_open_issue_csv_path: str | None = None
    active_review_readiness_structured_missing_value_count: int | None = Field(default=None, ge=0)
    active_review_readiness_p0_missing_decision_count: int | None = Field(default=None, ge=0)
    active_review_readiness_structured_open_review_cell_count: int | None = Field(
        default=None, ge=0
    )
    active_review_readiness_structured_open_record_count: int | None = Field(
        default=None, ge=0
    )
    active_review_readiness_p0_open_decision_count: int | None = Field(
        default=None, ge=0
    )
    active_review_readiness_p0_open_paper_count: int | None = Field(default=None, ge=0)
    active_review_readiness_structured_expected_paper_reading: str | None = None
    active_review_readiness_structured_primary_review_source: str | None = None
    active_review_readiness_p0_expected_paper_reading: str | None = None
    active_review_readiness_p0_primary_review_source: str | None = None
    active_review_readiness_p0_original_paper_reading_condition: str | None = None
    active_review_readiness_reviewer_work_item_count: int = Field(default=0, ge=0)
    active_review_readiness_reviewer_work_items: list[
        EvidenceGroundingActiveReviewReadinessWorkItem
    ] = Field(default_factory=list)
    active_review_readiness_reviewer_work_item_ids_by_blocked_requirement: dict[
        str,
        list[str],
    ] = Field(default_factory=dict)
    active_review_readiness_reviewer_open_item_counts_by_blocked_requirement: dict[
        str,
        int,
    ] = Field(default_factory=dict)
    active_review_readiness_reviewer_open_item_counts_by_work_item_id: dict[
        str,
        int,
    ] = Field(default_factory=dict)
    active_review_readiness_reviewer_expected_paper_reading_by_work_item_id: dict[
        str,
        str,
    ] = Field(default_factory=dict)
    active_review_readiness_reviewer_primary_review_sources_by_work_item_id: dict[
        str,
        str,
    ] = Field(default_factory=dict)
    active_review_readiness_reviewer_verification_command_hints_by_work_item_id: dict[
        str,
        str,
    ] = Field(default_factory=dict)
    active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading: dict[
        str,
        int,
    ] = Field(default_factory=dict)
    active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading: dict[
        str,
        int,
    ] = Field(default_factory=dict)
    active_review_readiness_brief_audit_all_passed: bool | None = None
    active_reviewer_handoff_refresh_path: str | None = None
    active_reviewer_handoff_refresh_brief_audit_all_passed: bool | None = None
    active_reviewer_handoff_refresh_brief_audit_pass_count: int | None = Field(
        default=None, ge=0
    )
    active_reviewer_handoff_refresh_brief_audit_fail_count: int | None = Field(
        default=None, ge=0
    )
    active_reviewer_handoff_refresh_brief_audit_counts: dict[str, int] = Field(
        default_factory=dict
    )
    active_reviewer_handoff_refresh_structured_open_record_count: int | None = Field(
        default=None, ge=0
    )
    active_reviewer_handoff_refresh_structured_open_csv_row_count: int | None = Field(
        default=None, ge=0
    )
    active_reviewer_handoff_refresh_p0_open_issue_row_count: int | None = Field(
        default=None, ge=0
    )
    active_reviewer_handoff_refresh_p0_open_paper_count: int | None = Field(
        default=None, ge=0
    )
    active_reviewer_handoff_refresh_ready_for_downstream_review_steps: bool | None = None
    active_reviewer_handoff_refresh_readiness_blocker_count: int | None = Field(
        default=None, ge=0
    )
    claim_evidence_eval_review_queue_records_dir: str | None = None
    claim_evidence_eval_review_queue_records_dir_exists: bool | None = None
    claim_evidence_eval_review_queue_pending_count: int | None = Field(default=None, ge=0)
    claim_evidence_eval_review_queue_total_count: int | None = Field(default=None, ge=0)
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    roadmap_complete: bool = False
    roadmap_blocker_count: int = Field(default=0, ge=0)
    roadmap_blocker_ids: list[str] = Field(default_factory=list)
    roadmap_blocker_reason_counts: dict[str, int] = Field(default_factory=dict)
    roadmap_blocker_next_action_kind_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    roadmap_blocker_next_action_kind_counts: dict[str, int] = Field(default_factory=dict)
    roadmap_blocker_ready_to_run_unique_next_action_count: int = Field(default=0, ge=0)
    roadmap_blocker_placeholder_command_unique_next_action_count: int = Field(
        default=0,
        ge=0,
    )
    roadmap_blocker_prerequisite_gated_next_action_count: int = Field(default=0, ge=0)
    roadmap_blocker_blocked_without_next_action_count: int = Field(default=0, ge=0)
    next_actions: list[EvidenceGroundingRoadmapCompletionNextAction] = Field(default_factory=list)
    next_action_count: int = Field(default=0, ge=0)
    next_action_counts_by_requirement: dict[str, int] = Field(default_factory=dict)
    next_action_texts_by_requirement: dict[str, list[str]] = Field(default_factory=dict)
    next_action_command_hints_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    next_action_unresolved_command_placeholders_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    next_action_unresolved_command_placeholder_counts_by_requirement: dict[str, int] = Field(
        default_factory=dict
    )
    next_action_unresolved_command_placeholder_counts_by_placeholder: dict[str, int] = Field(
        default_factory=dict
    )
    next_action_kind_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    next_action_blocked_by_requirement_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    next_action_blocked_by_requirement_counts: dict[str, int] = Field(
        default_factory=dict
    )
    next_action_blocked_by_requirement_unique_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    next_action_blocked_by_requirement_unique_counts: dict[str, int] = Field(
        default_factory=dict
    )
    next_action_blocker_reasons_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    next_action_blocker_reason_counts: dict[str, int] = Field(default_factory=dict)
    next_action_blocker_reason_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    next_action_blocker_reason_counts_by_phase: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    next_action_phase_counts: dict[str, int] = Field(default_factory=dict)
    next_action_ids_by_phase: dict[str, list[str]] = Field(default_factory=dict)
    next_action_ids_by_kind: dict[str, list[str]] = Field(default_factory=dict)
    next_action_kind_counts: dict[str, int] = Field(default_factory=dict)
    frontier_next_actions: list[EvidenceGroundingRoadmapCompletionNextAction] = Field(default_factory=list)
    frontier_next_action_count: int = Field(default=0, ge=0)
    frontier_human_review_next_action_count: int = Field(default=0, ge=0)
    frontier_ready_to_run_next_action_count: int = Field(default=0, ge=0)
    frontier_placeholder_command_next_action_count: int = Field(default=0, ge=0)
    frontier_next_action_ids_by_kind: dict[str, list[str]] = Field(default_factory=dict)
    frontier_unblocked_next_action_count: int = Field(default=0, ge=0)
    frontier_unblocked_next_action_ids_by_kind: dict[str, list[str]] = Field(default_factory=dict)
    frontier_action_text_by_requirement: dict[str, str] = Field(default_factory=dict)
    frontier_command_hints_by_requirement: dict[str, str] = Field(default_factory=dict)
    frontier_next_action_summaries: list[EvidenceGroundingRoadmapCompletionFrontierSummary] = Field(
        default_factory=list
    )
    frontier_unresolved_command_placeholder_count: int = Field(default=0, ge=0)
    frontier_unresolved_command_placeholders_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unresolved_command_placeholder_counts_by_placeholder: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_missing_metric_input_count: int = Field(default=0, ge=0)
    frontier_missing_metric_inputs_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_missing_metric_input_counts_by_metric: dict[str, int] = Field(default_factory=dict)
    frontier_human_review_open_csv_paths_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_row_counts_by_requirement: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_field_names_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_value_count: int = Field(default=0, ge=0)
    frontier_human_review_open_csv_missing_value_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_value_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_suggestion_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_suggestion_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_suggestion_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_suggested_value_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_suggested_value_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_record_filled_patch_field_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_record_filled_patch_field_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_record_filled_patch_fields_by_record_ref_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_available_context_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_available_context_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_context_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_context_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_context_task_ids_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_missing_context_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_available_context_keys_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_available_context_keys_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_available_context_values_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_csv_available_context_values_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_task_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_open_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_manifest_path: str | None = None
    frontier_human_review_queue_split_source_csv_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_merged_review_row_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_merged_reviewed_value_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_merged_missing_value_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_merged_reviewed_evidence_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_merged_missing_evidence_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_reviewer_value_hint_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_reviewer_evidence_hint_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_reviewer_value_hint_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_value_with_hint_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_missing_value_without_hint_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_missing_value_with_hint_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_value_without_hint_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_ready_source_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_blocked_source_count: int = Field(default=0, ge=0)
    frontier_human_review_queue_split_ready_reviewed_csv_paths: list[str] = Field(
        default_factory=list
    )
    frontier_human_review_queue_split_blocked_reviewed_csv_paths: list[str] = Field(
        default_factory=list
    )
    frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_ready_fill_review_audit_command_hints: list[str] = Field(
        default_factory=list
    )
    frontier_human_review_queue_split_blocked_fill_review_audit_command_hints: dict[str, str] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_blocked_fill_task_apply_command_hints: dict[str, str] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path: dict[str, str] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path: dict[str, str] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_reviewer_value_hint_counts_by_reviewed_csv_path: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_reviewed_csv_path: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_value_with_hint_counts_by_reviewed_csv_path: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_value_without_hint_counts_by_reviewed_csv_path: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement: dict[str, int] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_blocker_reasons_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_blocker_reason_counts: dict[str, int] = Field(default_factory=dict)
    frontier_blocked_by_requirement_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_blocked_by_requirement_counts: dict[str, int] = Field(default_factory=dict)
    frontier_blocked_by_requirement_unique_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    frontier_blocked_by_requirement_unique_counts: dict[str, int] = Field(default_factory=dict)
    ready_to_run_next_action_count: int = Field(default=0, ge=0)
    ready_to_run_unique_next_actions: list[EvidenceGroundingRoadmapCompletionNextAction] = Field(
        default_factory=list
    )
    ready_to_run_unique_next_action_count: int = Field(default=0, ge=0)
    placeholder_command_next_action_ids: list[str] = Field(default_factory=list)
    placeholder_command_next_action_count: int = Field(default=0, ge=0)
    placeholder_command_unique_next_actions: list[EvidenceGroundingRoadmapCompletionNextAction] = Field(
        default_factory=list
    )
    placeholder_command_unique_next_action_count: int = Field(default=0, ge=0)
    placeholder_command_action_texts_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    placeholder_command_hints_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    placeholder_command_unresolved_placeholders_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    placeholder_command_unresolved_placeholder_counts_by_requirement: dict[str, int] = Field(
        default_factory=dict
    )
    placeholder_command_unresolved_placeholder_counts_by_placeholder: dict[str, int] = Field(
        default_factory=dict
    )
    placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder: dict[
        str,
        str,
    ] = Field(default_factory=dict)
    prerequisite_gated_next_action_ids: list[str] = Field(default_factory=list)
    prerequisite_gated_next_action_count: int = Field(default=0, ge=0)
    prerequisite_gated_action_texts_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    prerequisite_gated_command_hints_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_next_action_count: int = Field(default=0, ge=0)
    human_review_unique_next_actions: list[EvidenceGroundingRoadmapCompletionNextAction] = Field(
        default_factory=list
    )
    human_review_unique_next_action_count: int = Field(default=0, ge=0)
    human_review_action_texts_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_command_hints_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_paths: list[str] = Field(default_factory=list)
    human_review_open_record_csv_paths: list[str] = Field(default_factory=list)
    human_review_open_csv_row_count: int = Field(default=0, ge=0)
    human_review_open_record_count: int = Field(default=0, ge=0)
    human_review_open_csv_paths_by_requirement: dict[str, list[str]] = Field(default_factory=dict)
    human_review_open_record_csv_paths_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_row_counts_by_requirement: dict[str, int] = Field(default_factory=dict)
    human_review_open_record_counts_by_requirement: dict[str, int] = Field(default_factory=dict)
    human_review_open_record_refs_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_field_names_by_record_ref_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    human_review_open_field_names_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_task_ids_by_record_ref_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    human_review_open_record_filled_patch_field_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    human_review_open_record_filled_patch_field_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_record_filled_patch_fields_by_record_ref_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_value_count: int = Field(default=0, ge=0)
    human_review_open_csv_missing_value_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_value_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_suggestion_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_suggestion_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_suggestion_task_ids_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_suggestion_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_suggested_value_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    human_review_open_csv_suggested_value_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_context_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_context_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_context_task_ids_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    human_review_open_csv_missing_context_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_reviewer_evidence_hint_counts_by_requirement: dict[str, dict[str, int]] = Field(
        default_factory=dict
    )
    human_review_open_csv_reviewer_evidence_hint_counts_by_field: dict[str, int] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_keys_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_keys_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_values_by_requirement: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict
    )
    human_review_open_csv_available_context_values_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_task_ids_by_requirement: dict[str, list[str]] = Field(
        default_factory=dict
    )
    human_review_open_task_ids_by_field: dict[str, list[str]] = Field(
        default_factory=dict
    )
    blocked_without_next_action_ids: list[str] = Field(default_factory=list)
    blocked_without_next_action_count: int = Field(default=0, ge=0)
    checks: list[EvidenceGroundingRoadmapCompletionCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_next_action_count(self):
        expected_pass_count = sum(1 for check in self.checks if check.status == "pass")
        expected_warn_count = sum(1 for check in self.checks if check.status == "warn")
        expected_fail_count = sum(1 for check in self.checks if check.status == "fail")
        if self.pass_count != expected_pass_count:
            raise ValueError("pass_count must match checks")
        if self.warn_count != expected_warn_count:
            raise ValueError("warn_count must match checks")
        if self.fail_count != expected_fail_count:
            raise ValueError("fail_count must match checks")
        expected_blockers = [check.requirement_id for check in self.checks if check.status == "fail"]
        if self.blockers != expected_blockers:
            raise ValueError("blockers must match failed checks")
        if (
            "roadmap_blocker_count" in self.model_fields_set
            and self.roadmap_blocker_count != len(expected_blockers)
        ):
            raise ValueError("roadmap_blocker_count must match failed checks")
        if (
            "roadmap_blocker_ids" in self.model_fields_set
            and self.roadmap_blocker_ids != expected_blockers
        ):
            raise ValueError("roadmap_blocker_ids must match failed checks")
        if self.checks and self.roadmap_complete != (self.fail_count == 0):
            raise ValueError("roadmap_complete must match fail_count")
        if self.additional_artifact_count != len(self.additional_artifact_paths):
            raise ValueError("additional_artifact_count must match additional_artifact_paths length")
        if self.active_review_readiness_reviewer_work_item_count != len(
            self.active_review_readiness_reviewer_work_items
        ):
            raise ValueError(
                "active_review_readiness_reviewer_work_item_count must match "
                "active_review_readiness_reviewer_work_items length"
            )
        expected_work_item_ids_by_blocked_requirement: dict[str, list[str]] = {}
        expected_open_item_counts_by_blocked_requirement: dict[str, int] = {}
        expected_open_item_counts_by_work_item_id: dict[str, int] = {}
        expected_paper_reading_by_work_item_id: dict[str, str] = {}
        expected_primary_review_sources_by_work_item_id: dict[str, str] = {}
        expected_verification_command_hints_by_work_item_id: dict[str, str] = {}
        expected_open_item_counts_by_expected_paper_reading: dict[str, int] = {}
        expected_open_paper_counts_by_expected_paper_reading: dict[str, int] = {}
        for item in self.active_review_readiness_reviewer_work_items:
            expected_open_item_counts_by_work_item_id[item.item_id] = item.open_item_count
            expected_paper_reading_by_work_item_id[item.item_id] = item.expected_paper_reading
            expected_primary_review_sources_by_work_item_id[item.item_id] = (
                item.primary_review_source
            )
            if item.verification_command_hint:
                expected_verification_command_hints_by_work_item_id[item.item_id] = (
                    item.verification_command_hint
                )
            expected_open_item_counts_by_expected_paper_reading[item.expected_paper_reading] = (
                expected_open_item_counts_by_expected_paper_reading.get(
                    item.expected_paper_reading,
                    0,
                )
                + item.open_item_count
            )
            if item.open_paper_count is not None:
                expected_open_paper_counts_by_expected_paper_reading[
                    item.expected_paper_reading
                ] = (
                    expected_open_paper_counts_by_expected_paper_reading.get(
                        item.expected_paper_reading,
                        0,
                    )
                    + item.open_paper_count
                )
            for requirement_id in item.blocked_roadmap_requirement_ids:
                expected_work_item_ids_by_blocked_requirement.setdefault(
                    requirement_id,
                    [],
                ).append(item.item_id)
                expected_open_item_counts_by_blocked_requirement[requirement_id] = (
                    expected_open_item_counts_by_blocked_requirement.get(requirement_id, 0)
                    + item.open_item_count
                )
        if (
            "active_review_readiness_reviewer_work_item_ids_by_blocked_requirement"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_work_item_ids_by_blocked_requirement
            != expected_work_item_ids_by_blocked_requirement
        ):
            raise ValueError(
                "active_review_readiness_reviewer_work_item_ids_by_blocked_requirement "
                "must match active_review_readiness_reviewer_work_items"
            )
        if (
            "active_review_readiness_reviewer_open_item_counts_by_blocked_requirement"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_open_item_counts_by_blocked_requirement
            != expected_open_item_counts_by_blocked_requirement
        ):
            raise ValueError(
                "active_review_readiness_reviewer_open_item_counts_by_blocked_requirement "
                "must match active_review_readiness_reviewer_work_items"
            )
        if (
            "active_review_readiness_reviewer_open_item_counts_by_work_item_id"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_open_item_counts_by_work_item_id
            != expected_open_item_counts_by_work_item_id
        ):
            raise ValueError(
                "active_review_readiness_reviewer_open_item_counts_by_work_item_id "
                "must match active_review_readiness_reviewer_work_items"
            )
        if (
            "active_review_readiness_reviewer_expected_paper_reading_by_work_item_id"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_expected_paper_reading_by_work_item_id
            != expected_paper_reading_by_work_item_id
        ):
            raise ValueError(
                "active_review_readiness_reviewer_expected_paper_reading_by_work_item_id "
                "must match active_review_readiness_reviewer_work_items"
            )
        if (
            "active_review_readiness_reviewer_primary_review_sources_by_work_item_id"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_primary_review_sources_by_work_item_id
            != expected_primary_review_sources_by_work_item_id
        ):
            raise ValueError(
                "active_review_readiness_reviewer_primary_review_sources_by_work_item_id "
                "must match active_review_readiness_reviewer_work_items"
            )
        if (
            "active_review_readiness_reviewer_verification_command_hints_by_work_item_id"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_verification_command_hints_by_work_item_id
            != expected_verification_command_hints_by_work_item_id
        ):
            raise ValueError(
                "active_review_readiness_reviewer_verification_command_hints_by_work_item_id "
                "must match active_review_readiness_reviewer_work_items"
            )
        if (
            "active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading
            != expected_open_item_counts_by_expected_paper_reading
        ):
            raise ValueError(
                "active_review_readiness_reviewer_open_item_counts_by_expected_paper_reading "
                "must match active_review_readiness_reviewer_work_items"
            )
        if (
            "active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading"
            in self.model_fields_set
            and self.active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading
            != expected_open_paper_counts_by_expected_paper_reading
        ):
            raise ValueError(
                "active_review_readiness_reviewer_open_paper_counts_by_expected_paper_reading "
                "must match active_review_readiness_reviewer_work_items"
            )
        if self.fail_count > 0 and "roadmap_completion_blocked" not in self.warnings:
            raise ValueError("warnings must include roadmap_completion_blocked when failures are present")
        if self.fail_count == 0 and "roadmap_completion_blocked" in self.warnings:
            raise ValueError("warnings must not include roadmap_completion_blocked without failures")
        if self.warn_count > 0 and "roadmap_completion_warnings_present" not in self.warnings:
            raise ValueError("warnings must include roadmap_completion_warnings_present when warnings are present")
        if self.warn_count == 0 and "roadmap_completion_warnings_present" in self.warnings:
            raise ValueError("warnings must not include roadmap_completion_warnings_present without warn checks")
        if self.next_action_count != len(self.next_actions):
            raise ValueError("next_action_count must match next_actions length")
        expected_next_action_counts_by_requirement: dict[str, int] = {}
        expected_next_action_texts_by_requirement: dict[str, list[str]] = {}
        expected_next_action_command_hints_by_requirement: dict[str, list[str]] = {}
        expected_next_action_unresolved_placeholders_by_requirement: dict[str, list[str]] = {}
        expected_next_action_unresolved_placeholder_counts_by_requirement: dict[str, int] = {}
        expected_next_action_unresolved_placeholder_counts_by_placeholder: dict[str, int] = {}
        expected_next_action_kind_counts_by_requirement: dict[str, dict[str, int]] = {}
        expected_next_action_blocked_by_requirement_ids_by_requirement: dict[str, list[str]] = {}
        expected_next_action_blocked_by_requirement_counts: dict[str, int] = {}
        expected_next_action_blocked_by_requirement_unique_ids_by_requirement: dict[str, list[str]] = {}
        expected_next_action_blocked_by_requirement_unique_counts: dict[str, int] = {}
        expected_next_action_blocker_reasons_by_requirement: dict[str, list[str]] = {}
        expected_next_action_blocker_reason_counts: dict[str, int] = {}
        expected_next_action_blocker_reason_counts_by_requirement: dict[str, dict[str, int]] = {}
        expected_next_action_blocker_reason_counts_by_phase: dict[str, dict[str, int]] = {}
        expected_phase_counts: dict[str, int] = {}
        expected_next_action_ids_by_phase: dict[str, list[str]] = {}
        expected_next_action_ids_by_kind: dict[str, list[str]] = {}
        failed_requirement_ids = {
            check.requirement_id.strip()
            for check in self.checks
            if check.status == "fail" and check.requirement_id.strip()
        }
        missing_metric_inputs_by_requirement = _roadmap_missing_metric_inputs_by_requirement(
            self.checks
        )
        human_review_open_task_ids_by_requirement = (
            _roadmap_human_review_string_list_by_requirement(
                self.checks,
                "_fill_review_status_open_task_ids",
            )
        )
        seen_requirement_ids_with_prior_action: set[str] = set()
        inherited_blocked_by_requirement_ids_by_requirement: dict[str, list[str]] = {}
        for action in self.next_actions:
            phase = (action.phase or "unknown").strip() or "unknown"
            requirement_id = action.requirement_id.strip()
            if requirement_id:
                expected_phase = _roadmap_next_action_phase(requirement_id)
                if action.phase is not None and phase != expected_phase:
                    raise ValueError("next_actions phase must match requirement_id")
                phase = expected_phase
                expected_phase_counts[phase] = expected_phase_counts.get(phase, 0) + 1
                expected_next_action_counts_by_requirement[requirement_id] = (
                    expected_next_action_counts_by_requirement.get(requirement_id, 0) + 1
                )
                expected_next_action_ids_by_phase.setdefault(phase, []).append(requirement_id)
                action_text = action.action.strip()
                if action_text:
                    expected_next_action_texts_by_requirement.setdefault(
                        requirement_id,
                        [],
                    ).append(action_text)
            else:
                expected_phase_counts[phase] = expected_phase_counts.get(phase, 0) + 1
            if requirement_id:
                command_hint = (action.command_hint or "").strip()
                if command_hint:
                    expected_next_action_command_hints_by_requirement.setdefault(
                        requirement_id,
                        [],
                    ).append(command_hint)
                    placeholders = _roadmap_command_hint_unresolved_placeholders(command_hint)
                    if placeholders:
                        expected_next_action_unresolved_placeholders_by_requirement.setdefault(
                            requirement_id,
                            [],
                        ).extend(placeholders)
                        expected_next_action_unresolved_placeholder_counts_by_requirement[
                            requirement_id
                        ] = (
                            expected_next_action_unresolved_placeholder_counts_by_requirement.get(
                                requirement_id,
                                0,
                            )
                            + len(placeholders)
                        )
                        for placeholder in placeholders:
                            expected_next_action_unresolved_placeholder_counts_by_placeholder[
                                placeholder
                            ] = (
                                expected_next_action_unresolved_placeholder_counts_by_placeholder.get(
                                    placeholder,
                                    0,
                                )
                                + 1
                            )
                has_prior_prerequisite = requirement_id in seen_requirement_ids_with_prior_action
                if action_text:
                    seen_requirement_ids_with_prior_action.add(requirement_id)
                expected_requires_human_review = _roadmap_next_action_requires_human_review(
                    requirement_id,
                    action_text,
                )
                if (
                    "requires_human_review" in action.model_fields_set
                    and action.requires_human_review != expected_requires_human_review
                ):
                    raise ValueError(
                        "next_actions requires_human_review must match action text"
                    )
                if action.requires_human_review:
                    kind = "human_review_with_command" if command_hint else "human_review_without_command"
                elif not command_hint:
                    kind = "nonhuman_without_command"
                elif _roadmap_command_hint_has_unresolved_placeholder(command_hint):
                    kind = "placeholder_command"
                elif has_prior_prerequisite:
                    kind = "prerequisite_gated_command"
                else:
                    kind = "ready_to_run_command"
                if action.kind is not None and action.kind != kind:
                    raise ValueError("next_actions kind must match command and review metadata")
                expected_next_action_ids_by_kind.setdefault(kind, []).append(requirement_id)
                requirement_kind_counts = (
                    expected_next_action_kind_counts_by_requirement.setdefault(
                        requirement_id,
                        {},
                    )
                )
                requirement_kind_counts[kind] = requirement_kind_counts.get(kind, 0) + 1
                unresolved_placeholders = _roadmap_command_hint_unresolved_placeholders(
                    command_hint
                )
                if (
                    "has_command_hint" in action.model_fields_set
                    and action.has_command_hint != bool(command_hint)
                ):
                    raise ValueError("next_actions has_command_hint must match command_hint")
                if (
                    "has_unresolved_command_placeholder" in action.model_fields_set
                    and action.has_unresolved_command_placeholder
                    != bool(unresolved_placeholders)
                ):
                    raise ValueError(
                        "next_actions has_unresolved_command_placeholder must match "
                        "command_hint placeholders"
                    )
                observed_unresolved_placeholders = [
                    item.strip()
                    for item in action.unresolved_command_placeholders
                    if item.strip()
                ]
                if (
                    observed_unresolved_placeholders
                    and observed_unresolved_placeholders != unresolved_placeholders
                ):
                    raise ValueError(
                        "next_actions unresolved_command_placeholders must match "
                        "command_hint placeholders"
                    )
                expected_missing_metric_inputs = missing_metric_inputs_by_requirement.get(
                    requirement_id,
                    [],
                )
                observed_missing_metric_inputs = [
                    item.strip()
                    for item in action.missing_metric_inputs
                    if item.strip()
                ]
                if (
                    observed_missing_metric_inputs
                    and observed_missing_metric_inputs != expected_missing_metric_inputs
                ):
                    raise ValueError(
                        "next_actions missing_metric_inputs must match failed-check metric evidence"
                    )
                expected_blocked_by_requirement_ids = (
                    _roadmap_merge_requirement_id_lists(
                        inherited_blocked_by_requirement_ids_by_requirement.get(
                            requirement_id,
                            [],
                        ),
                        _roadmap_next_action_blocked_by_requirement_ids(
                            requirement_id=requirement_id,
                            action_text=action_text,
                            failed_requirement_ids=failed_requirement_ids,
                        ),
                    )
                )
                observed_blocked_by_requirement_ids = [
                    item.strip()
                    for item in action.blocked_by_requirement_ids
                    if item.strip()
                ]
                if observed_blocked_by_requirement_ids != expected_blocked_by_requirement_ids:
                    raise ValueError(
                        "next_actions blocked_by_requirement_ids must match failed checks"
                    )
                observed_human_review_open_task_ids = [
                    item.strip()
                    for item in action.human_review_open_task_ids
                    if item.strip()
                ]
                expected_human_review_open_task_ids = (
                    human_review_open_task_ids_by_requirement.get(
                        requirement_id,
                        [],
                    )
                )
                if (
                    observed_human_review_open_task_ids
                    and observed_human_review_open_task_ids
                    != expected_human_review_open_task_ids
                ):
                    raise ValueError(
                        "next_actions human_review_open_task_ids must match "
                        "fill-review open task evidence"
                    )
                if expected_blocked_by_requirement_ids:
                    inherited_blocked_by_requirement_ids_by_requirement[
                        requirement_id
                    ] = expected_blocked_by_requirement_ids
                    expected_next_action_blocked_by_requirement_ids_by_requirement.setdefault(
                        requirement_id,
                        [],
                    ).extend(expected_blocked_by_requirement_ids)
                    for blocked_requirement_id in expected_blocked_by_requirement_ids:
                        expected_next_action_blocked_by_requirement_counts[
                            blocked_requirement_id
                        ] = (
                            expected_next_action_blocked_by_requirement_counts.get(
                                blocked_requirement_id,
                                0,
                            )
                              + 1
                        )
                blocker_reasons = _roadmap_next_action_blocker_reasons(
                    kind=kind,
                    requires_human_review=action.requires_human_review,
                    has_command_hint=bool(command_hint),
                    has_prior_prerequisite=has_prior_prerequisite,
                    unresolved_command_placeholders=unresolved_placeholders,
                    missing_metric_inputs=expected_missing_metric_inputs,
                    human_review_open_task_ids=human_review_open_task_ids_by_requirement.get(
                        requirement_id,
                        [],
                    ),
                    blocked_by_requirement_ids=expected_blocked_by_requirement_ids,
                )
                observed_blocker_reasons = [
                    item.strip()
                    for item in action.blocker_reasons
                    if item.strip()
                ]
                if observed_blocker_reasons and observed_blocker_reasons != blocker_reasons:
                    raise ValueError(
                        "next_actions blocker_reasons must match command, review, metric, "
                        "and prerequisite metadata"
                    )
                if blocker_reasons:
                    expected_next_action_blocker_reasons_by_requirement.setdefault(
                        requirement_id,
                        [],
                    ).extend(blocker_reasons)
                    for reason in blocker_reasons:
                        expected_next_action_blocker_reason_counts[reason] = (
                            expected_next_action_blocker_reason_counts.get(reason, 0)
                            + 1
                        )
                        requirement_reason_counts = (
                            expected_next_action_blocker_reason_counts_by_requirement.setdefault(
                                requirement_id,
                                {},
                            )
                        )
                        requirement_reason_counts[reason] = (
                            requirement_reason_counts.get(reason, 0) + 1
                        )
                        phase_reason_counts = (
                            expected_next_action_blocker_reason_counts_by_phase.setdefault(
                                phase,
                                {},
                            )
                        )
                        phase_reason_counts[reason] = phase_reason_counts.get(reason, 0) + 1
        for requirement_id, blocked_requirement_ids in (
            expected_next_action_blocked_by_requirement_ids_by_requirement.items()
        ):
            seen_blocked_ids: set[str] = set()
            unique_blocked_ids: list[str] = []
            for blocked_requirement_id in blocked_requirement_ids:
                if blocked_requirement_id in seen_blocked_ids:
                    continue
                seen_blocked_ids.add(blocked_requirement_id)
                unique_blocked_ids.append(blocked_requirement_id)
            if unique_blocked_ids:
                expected_next_action_blocked_by_requirement_unique_ids_by_requirement[
                    requirement_id
                ] = unique_blocked_ids
                for blocked_requirement_id in unique_blocked_ids:
                    expected_next_action_blocked_by_requirement_unique_counts[
                        blocked_requirement_id
                    ] = (
                        expected_next_action_blocked_by_requirement_unique_counts.get(
                            blocked_requirement_id,
                            0,
                        )
                        + 1
                    )
        if self.next_action_counts_by_requirement != expected_next_action_counts_by_requirement:
            raise ValueError("next_action_counts_by_requirement must match next_actions")
        if self.next_action_texts_by_requirement != expected_next_action_texts_by_requirement:
            raise ValueError("next_action_texts_by_requirement must match next_actions")
        if (
            self.next_action_command_hints_by_requirement
            != expected_next_action_command_hints_by_requirement
        ):
            raise ValueError(
                "next_action_command_hints_by_requirement must match next_actions"
            )
        if (
            self.next_action_unresolved_command_placeholders_by_requirement
            != expected_next_action_unresolved_placeholders_by_requirement
        ):
            raise ValueError(
                "next_action_unresolved_command_placeholders_by_requirement must match "
                "next_actions"
            )
        if (
            self.next_action_unresolved_command_placeholder_counts_by_requirement
            != expected_next_action_unresolved_placeholder_counts_by_requirement
        ):
            raise ValueError(
                "next_action_unresolved_command_placeholder_counts_by_requirement "
                "must match next_actions"
            )
        if (
            self.next_action_unresolved_command_placeholder_counts_by_placeholder
            != dict(
                sorted(
                    expected_next_action_unresolved_placeholder_counts_by_placeholder.items()
                )
            )
        ):
            raise ValueError(
                "next_action_unresolved_command_placeholder_counts_by_placeholder "
                "must match next_actions"
            )
        if (
            self.next_action_kind_counts_by_requirement
            != expected_next_action_kind_counts_by_requirement
        ):
            raise ValueError("next_action_kind_counts_by_requirement must match next_actions")
        if (
            "roadmap_blocker_next_action_kind_counts_by_requirement" in self.model_fields_set
            and
            self.roadmap_blocker_next_action_kind_counts_by_requirement
            != expected_next_action_kind_counts_by_requirement
        ):
            raise ValueError(
                "roadmap_blocker_next_action_kind_counts_by_requirement must match "
                "next_actions"
            )
        if (
            self.next_action_blocked_by_requirement_ids_by_requirement
            != expected_next_action_blocked_by_requirement_ids_by_requirement
        ):
            raise ValueError(
                "next_action_blocked_by_requirement_ids_by_requirement must match next_actions"
            )
        if (
            self.next_action_blocked_by_requirement_counts
            != expected_next_action_blocked_by_requirement_counts
        ):
            raise ValueError(
                "next_action_blocked_by_requirement_counts must match next_actions"
            )
        if (
            self.next_action_blocked_by_requirement_unique_ids_by_requirement
            != expected_next_action_blocked_by_requirement_unique_ids_by_requirement
        ):
            raise ValueError(
                "next_action_blocked_by_requirement_unique_ids_by_requirement "
                "must match next_actions"
            )
        if (
            self.next_action_blocked_by_requirement_unique_counts
            != expected_next_action_blocked_by_requirement_unique_counts
        ):
            raise ValueError(
                "next_action_blocked_by_requirement_unique_counts must match next_actions"
            )
        if (
            self.next_action_blocker_reasons_by_requirement
            != expected_next_action_blocker_reasons_by_requirement
        ):
            raise ValueError("next_action_blocker_reasons_by_requirement must match next_actions")
        if self.next_action_blocker_reason_counts != expected_next_action_blocker_reason_counts:
            raise ValueError("next_action_blocker_reason_counts must match next_actions")
        if (
            self.next_action_blocker_reason_counts_by_requirement
            != expected_next_action_blocker_reason_counts_by_requirement
        ):
            raise ValueError(
                "next_action_blocker_reason_counts_by_requirement must match next_actions"
            )
        if (
            self.next_action_blocker_reason_counts_by_phase
            != expected_next_action_blocker_reason_counts_by_phase
        ):
            raise ValueError(
                "next_action_blocker_reason_counts_by_phase must match next_actions"
            )
        if self.next_action_phase_counts != expected_phase_counts:
            raise ValueError("next_action_phase_counts must match next_actions phases")
        if self.next_action_ids_by_phase != expected_next_action_ids_by_phase:
            raise ValueError("next_action_ids_by_phase must match next_actions phases")
        if self.next_action_ids_by_kind != expected_next_action_ids_by_kind:
            raise ValueError("next_action_ids_by_kind must match next_actions")
        expected_next_action_kind_counts = {
            kind: len(ids) for kind, ids in expected_next_action_ids_by_kind.items()
        }
        if self.next_action_kind_counts != expected_next_action_kind_counts:
            raise ValueError("next_action_kind_counts must match next_action_ids_by_kind")
        if (
            "roadmap_blocker_next_action_kind_counts" in self.model_fields_set
            and
            self.roadmap_blocker_next_action_kind_counts
            != expected_next_action_kind_counts
        ):
            raise ValueError(
                "roadmap_blocker_next_action_kind_counts must match next_action_ids_by_kind"
            )
        def _frontier_action_fingerprint(
            action: EvidenceGroundingRoadmapCompletionNextAction,
        ) -> tuple[
            str,
            str,
            str,
            bool,
            bool,
            bool,
            str,
            str,
            tuple[str, ...],
            tuple[str, ...],
            tuple[str, ...],
            tuple[str, ...],
            tuple[str, ...],
        ]:
            return (
                action.requirement_id.strip(),
                (action.phase or "").strip(),
                action.action.strip(),
                action.requires_human_review,
                action.has_command_hint,
                action.has_unresolved_command_placeholder,
                (action.command_hint or "").strip(),
                (action.kind or "").strip(),
                tuple(action.unresolved_command_placeholders),
                tuple(action.missing_metric_inputs),
                tuple(action.human_review_open_task_ids),
                tuple(action.blocked_by_requirement_ids),
                tuple(action.blocker_reasons),
            )

        expected_frontier_next_actions: list[
            tuple[
                str,
                str,
                str,
                bool,
                bool,
                bool,
                str,
                str,
                tuple[str, ...],
                tuple[str, ...],
                tuple[str, ...],
                tuple[str, ...],
                tuple[str, ...],
            ]
        ] = []
        seen_frontier_requirement_ids: set[str] = set()
        for action in self.next_actions:
            requirement_id = action.requirement_id.strip()
            action_text = action.action.strip()
            if not requirement_id or not action_text or requirement_id in seen_frontier_requirement_ids:
                continue
            seen_frontier_requirement_ids.add(requirement_id)
            expected_frontier_next_actions.append(_frontier_action_fingerprint(action))
        observed_frontier_next_actions = [
            _frontier_action_fingerprint(action) for action in self.frontier_next_actions
        ]
        if observed_frontier_next_actions != expected_frontier_next_actions:
            raise ValueError("frontier_next_actions must match first next_action per requirement")
        if self.frontier_next_action_count != len(self.frontier_next_actions):
            raise ValueError("frontier_next_action_count must match frontier_next_actions length")
        expected_frontier_human_review_count = sum(
            1 for action in self.frontier_next_actions if action.requires_human_review
        )
        expected_frontier_ready_to_run_count = sum(
            1
            for action in self.frontier_next_actions
            if not action.requires_human_review
            and not action.blocked_by_requirement_ids
            and (action.command_hint or "").strip()
            and not _roadmap_command_hint_has_unresolved_placeholder(action.command_hint or "")
        )
        expected_frontier_placeholder_count = sum(
            1
            for action in self.frontier_next_actions
            if not action.requires_human_review
            and not action.blocked_by_requirement_ids
            and (action.command_hint or "").strip()
            and _roadmap_command_hint_has_unresolved_placeholder(action.command_hint or "")
        )
        if self.frontier_human_review_next_action_count != expected_frontier_human_review_count:
            raise ValueError("frontier_human_review_next_action_count must match frontier_next_actions")
        if self.frontier_ready_to_run_next_action_count != expected_frontier_ready_to_run_count:
            raise ValueError("frontier_ready_to_run_next_action_count must match frontier_next_actions")
        if self.frontier_placeholder_command_next_action_count != expected_frontier_placeholder_count:
            raise ValueError("frontier_placeholder_command_next_action_count must match frontier_next_actions")
        expected_frontier_ids_by_kind: dict[str, list[str]] = {}
        expected_frontier_unblocked_ids_by_kind: dict[str, list[str]] = {}
        for action in self.frontier_next_actions:
            requirement_id = action.requirement_id.strip()
            if not requirement_id:
                continue
            kind = _roadmap_frontier_next_action_kind(action)
            expected_frontier_ids_by_kind.setdefault(kind, []).append(requirement_id)
            if not action.blocked_by_requirement_ids:
                expected_frontier_unblocked_ids_by_kind.setdefault(kind, []).append(requirement_id)
        if self.frontier_next_action_ids_by_kind != expected_frontier_ids_by_kind:
            raise ValueError("frontier_next_action_ids_by_kind must match frontier_next_actions")
        expected_frontier_unblocked_count = sum(
            len(ids) for ids in expected_frontier_unblocked_ids_by_kind.values()
        )
        expected_frontier_unblocked_requirement_ids = {
            requirement_id
            for requirement_ids in expected_frontier_unblocked_ids_by_kind.values()
            for requirement_id in requirement_ids
        }
        if self.frontier_unblocked_next_action_count != expected_frontier_unblocked_count:
            raise ValueError(
                "frontier_unblocked_next_action_count must match unblocked frontier_next_actions"
            )
        if self.frontier_unblocked_next_action_ids_by_kind != expected_frontier_unblocked_ids_by_kind:
            raise ValueError(
                "frontier_unblocked_next_action_ids_by_kind must match unblocked frontier_next_actions"
            )
        expected_frontier_action_text_by_requirement = {
            action.requirement_id.strip(): action.action.strip()
            for action in self.frontier_next_actions
            if action.requirement_id.strip() and action.action.strip()
        }
        if self.frontier_action_text_by_requirement != expected_frontier_action_text_by_requirement:
            raise ValueError("frontier_action_text_by_requirement must match frontier_next_actions")
        expected_frontier_command_hints_by_requirement = {
            action.requirement_id.strip(): (action.command_hint or "").strip()
            for action in self.frontier_next_actions
            if action.requirement_id.strip() and (action.command_hint or "").strip()
        }
        if self.frontier_command_hints_by_requirement != expected_frontier_command_hints_by_requirement:
            raise ValueError("frontier_command_hints_by_requirement must match frontier_next_actions")
        expected_placeholder_command_ids: list[str] = []
        expected_placeholder_command_unique_actions: list[tuple] = []
        expected_prerequisite_gated_ids: list[str] = []
        expected_prerequisite_gated_action_texts_by_requirement: dict[str, list[str]] = {}
        expected_prerequisite_gated_command_hints_by_requirement: dict[str, list[str]] = {}
        expected_ready_to_run_count = 0
        expected_ready_to_run_unique_actions: list[tuple] = []
        seen_placeholder_command_keys: set[tuple[str, str]] = set()
        seen_ready_to_run_keys: set[tuple[str, str]] = set()
        seen_requirement_ids_with_prior_action: set[str] = set()
        for action in self.next_actions:
            requirement_id = action.requirement_id.strip()
            action_text = action.action.strip()
            command_hint = (action.command_hint or "").strip()
            has_prior_prerequisite = requirement_id in seen_requirement_ids_with_prior_action
            if action_text:
                seen_requirement_ids_with_prior_action.add(requirement_id)
            if action.requires_human_review or not command_hint:
                continue
            if _roadmap_command_hint_has_unresolved_placeholder(command_hint):
                expected_placeholder_command_ids.append(action.requirement_id.strip())
                key = (action_text, command_hint)
                if action_text and key not in seen_placeholder_command_keys:
                    seen_placeholder_command_keys.add(key)
                    expected_placeholder_command_unique_actions.append(
                        _frontier_action_fingerprint(action)
                    )
            elif has_prior_prerequisite:
                expected_prerequisite_gated_ids.append(action.requirement_id.strip())
                if requirement_id and action_text:
                    expected_prerequisite_gated_action_texts_by_requirement.setdefault(
                        requirement_id,
                        [],
                    ).append(action_text)
                if requirement_id and command_hint:
                    expected_prerequisite_gated_command_hints_by_requirement.setdefault(
                        requirement_id,
                        [],
                    ).append(command_hint)
            else:
                expected_ready_to_run_count += 1
                key = (action_text, command_hint)
                if action_text and key not in seen_ready_to_run_keys:
                    seen_ready_to_run_keys.add(key)
                    expected_ready_to_run_unique_actions.append(
                        _frontier_action_fingerprint(action)
                    )
        if self.ready_to_run_next_action_count != expected_ready_to_run_count:
            raise ValueError("ready_to_run_next_action_count must match next_actions command hints")
        if self.ready_to_run_unique_next_action_count != len(self.ready_to_run_unique_next_actions):
            raise ValueError(
                "ready_to_run_unique_next_action_count must match ready_to_run_unique_next_actions length"
            )
        if (
            "roadmap_blocker_ready_to_run_unique_next_action_count" in self.model_fields_set
            and
            self.roadmap_blocker_ready_to_run_unique_next_action_count
            != len(self.ready_to_run_unique_next_actions)
        ):
            raise ValueError(
                "roadmap_blocker_ready_to_run_unique_next_action_count must match "
                "ready_to_run_unique_next_actions length"
            )
        observed_ready_to_run_unique_actions = [
            _frontier_action_fingerprint(action)
            for action in self.ready_to_run_unique_next_actions
        ]
        if observed_ready_to_run_unique_actions != expected_ready_to_run_unique_actions:
            raise ValueError("ready_to_run_unique_next_actions must match unique ready-to-run next_actions")
        if self.placeholder_command_next_action_count != len(self.placeholder_command_next_action_ids):
            raise ValueError(
                "placeholder_command_next_action_count must match placeholder_command_next_action_ids length"
            )
        if self.placeholder_command_next_action_ids != expected_placeholder_command_ids:
            raise ValueError("placeholder_command_next_action_ids must match unresolved command placeholders")
        if self.placeholder_command_unique_next_action_count != len(self.placeholder_command_unique_next_actions):
            raise ValueError(
                "placeholder_command_unique_next_action_count must match "
                "placeholder_command_unique_next_actions length"
            )
        if (
            "roadmap_blocker_placeholder_command_unique_next_action_count" in self.model_fields_set
            and
            self.roadmap_blocker_placeholder_command_unique_next_action_count
            != len(self.placeholder_command_unique_next_actions)
        ):
            raise ValueError(
                "roadmap_blocker_placeholder_command_unique_next_action_count must match "
                "placeholder_command_unique_next_actions length"
            )
        observed_placeholder_command_unique_actions = [
            _frontier_action_fingerprint(action)
            for action in self.placeholder_command_unique_next_actions
        ]
        if observed_placeholder_command_unique_actions != expected_placeholder_command_unique_actions:
            raise ValueError(
                "placeholder_command_unique_next_actions must match unique unresolved command placeholders"
            )
        expected_placeholder_command_action_texts_by_requirement: dict[str, list[str]] = {}
        expected_placeholder_command_hints_by_requirement: dict[str, list[str]] = {}
        expected_placeholder_command_unresolved_placeholders_by_requirement: dict[str, list[str]] = {}
        expected_placeholder_command_unresolved_placeholder_counts_by_requirement: dict[str, int] = {}
        expected_placeholder_command_unresolved_placeholder_counts_by_placeholder: dict[str, int] = {}
        expected_placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder: dict[
            str,
            str,
        ] = {}
        for action in self.placeholder_command_unique_next_actions:
            requirement_id = action.requirement_id.strip()
            action_text = action.action.strip()
            command_hint = (action.command_hint or "").strip()
            if requirement_id and action_text:
                expected_placeholder_command_action_texts_by_requirement.setdefault(
                    requirement_id,
                    [],
                ).append(action_text)
            if requirement_id and command_hint:
                expected_placeholder_command_hints_by_requirement.setdefault(
                    requirement_id,
                    [],
                ).append(command_hint)
            placeholders = _roadmap_command_hint_unresolved_placeholders(command_hint)
            if requirement_id and placeholders:
                expected_placeholder_command_unresolved_placeholders_by_requirement.setdefault(
                    requirement_id,
                    [],
                ).extend(placeholders)
                expected_placeholder_command_unresolved_placeholder_counts_by_requirement[
                    requirement_id
                ] = (
                    expected_placeholder_command_unresolved_placeholder_counts_by_requirement.get(
                        requirement_id,
                        0,
                    )
                    + len(placeholders)
                )
            for placeholder in placeholders:
                expected_placeholder_command_unresolved_placeholder_counts_by_placeholder[placeholder] = (
                    expected_placeholder_command_unresolved_placeholder_counts_by_placeholder.get(
                        placeholder,
                        0,
                    )
                    + 1
                )
                expected_placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder[
                    placeholder
                ] = _roadmap_placeholder_resolution_class(placeholder)
        expected_placeholder_command_action_texts_by_requirement = dict(
            sorted(expected_placeholder_command_action_texts_by_requirement.items())
        )
        expected_placeholder_command_hints_by_requirement = dict(
            sorted(expected_placeholder_command_hints_by_requirement.items())
        )
        expected_placeholder_command_unresolved_placeholders_by_requirement = dict(
            sorted(expected_placeholder_command_unresolved_placeholders_by_requirement.items())
        )
        expected_placeholder_command_unresolved_placeholder_counts_by_requirement = dict(
            sorted(expected_placeholder_command_unresolved_placeholder_counts_by_requirement.items())
        )
        expected_placeholder_command_unresolved_placeholder_counts_by_placeholder = dict(
            sorted(expected_placeholder_command_unresolved_placeholder_counts_by_placeholder.items())
        )
        expected_placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder = dict(
            sorted(
                expected_placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder.items()
            )
        )
        if (
            self.placeholder_command_action_texts_by_requirement
            != expected_placeholder_command_action_texts_by_requirement
        ):
            raise ValueError(
                "placeholder_command_action_texts_by_requirement must match "
                "placeholder_command_unique_next_actions"
            )
        if self.placeholder_command_hints_by_requirement != expected_placeholder_command_hints_by_requirement:
            raise ValueError(
                "placeholder_command_hints_by_requirement must match "
                "placeholder_command_unique_next_actions"
            )
        if (
            self.placeholder_command_unresolved_placeholders_by_requirement
            != expected_placeholder_command_unresolved_placeholders_by_requirement
        ):
            raise ValueError(
                "placeholder_command_unresolved_placeholders_by_requirement must match "
                "placeholder_command_unique_next_actions"
            )
        if (
            self.placeholder_command_unresolved_placeholder_counts_by_placeholder
            != expected_placeholder_command_unresolved_placeholder_counts_by_placeholder
        ):
            raise ValueError(
                "placeholder_command_unresolved_placeholder_counts_by_placeholder must match "
                "placeholder_command_unique_next_actions"
            )
        if (
            self.placeholder_command_unresolved_placeholder_counts_by_requirement
            != expected_placeholder_command_unresolved_placeholder_counts_by_requirement
        ):
            raise ValueError(
                "placeholder_command_unresolved_placeholder_counts_by_requirement must match "
                "placeholder_command_unique_next_actions"
            )
        if (
            "placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder"
            in self.model_fields_set
            and self.placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder
            != expected_placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder
        ):
            raise ValueError(
                "placeholder_command_unresolved_placeholder_resolution_classes_by_placeholder "
                "must match placeholder_command_unique_next_actions"
            )
        if self.prerequisite_gated_next_action_count != len(self.prerequisite_gated_next_action_ids):
            raise ValueError(
                "prerequisite_gated_next_action_count must match prerequisite_gated_next_action_ids length"
            )
        if (
            "roadmap_blocker_prerequisite_gated_next_action_count" in self.model_fields_set
            and
            self.roadmap_blocker_prerequisite_gated_next_action_count
            != len(self.prerequisite_gated_next_action_ids)
        ):
            raise ValueError(
                "roadmap_blocker_prerequisite_gated_next_action_count must match "
                "prerequisite_gated_next_action_ids length"
            )
        if self.prerequisite_gated_next_action_ids != expected_prerequisite_gated_ids:
            raise ValueError("prerequisite_gated_next_action_ids must match gated command next_actions")
        expected_prerequisite_gated_action_texts_by_requirement = dict(
            sorted(expected_prerequisite_gated_action_texts_by_requirement.items())
        )
        expected_prerequisite_gated_command_hints_by_requirement = dict(
            sorted(expected_prerequisite_gated_command_hints_by_requirement.items())
        )
        if (
            self.prerequisite_gated_action_texts_by_requirement
            != expected_prerequisite_gated_action_texts_by_requirement
        ):
            raise ValueError(
                "prerequisite_gated_action_texts_by_requirement must match gated command next_actions"
            )
        if (
            self.prerequisite_gated_command_hints_by_requirement
            != expected_prerequisite_gated_command_hints_by_requirement
        ):
            raise ValueError(
                "prerequisite_gated_command_hints_by_requirement must match gated command next_actions"
            )
        expected_human_review_count = sum(1 for action in self.next_actions if action.requires_human_review)
        if self.human_review_next_action_count != expected_human_review_count:
            raise ValueError("human_review_next_action_count must match next_actions")
        if self.human_review_unique_next_action_count != len(self.human_review_unique_next_actions):
            raise ValueError("human_review_unique_next_action_count must match human_review_unique_next_actions length")
        expected_unique_next_actions: list[tuple] = []
        seen_unique_action_keys: set[tuple[str, str]] = set()
        for action in self.next_actions:
            action_text = action.action.strip()
            if not action.requires_human_review or not action_text:
                continue
            command_hint = (action.command_hint or "").strip()
            key = (action_text, command_hint)
            if key in seen_unique_action_keys:
                continue
            seen_unique_action_keys.add(key)
            expected_unique_next_actions.append(_frontier_action_fingerprint(action))
        observed_unique_next_actions = [
            _frontier_action_fingerprint(action)
            for action in self.human_review_unique_next_actions
        ]
        if observed_unique_next_actions != expected_unique_next_actions:
            raise ValueError("human_review_unique_next_actions must match unique human-review next_actions")
        expected_human_review_action_texts_by_requirement: dict[str, list[str]] = {}
        expected_human_review_command_hints_by_requirement: dict[str, list[str]] = {}
        for action in self.human_review_unique_next_actions:
            requirement_id = action.requirement_id.strip()
            action_text = action.action.strip()
            command_hint = (action.command_hint or "").strip()
            if requirement_id and action_text:
                expected_human_review_action_texts_by_requirement.setdefault(
                    requirement_id,
                    [],
                ).append(action_text)
            if requirement_id and command_hint:
                expected_human_review_command_hints_by_requirement.setdefault(
                    requirement_id,
                    [],
                ).append(command_hint)
        expected_human_review_action_texts_by_requirement = dict(
            sorted(expected_human_review_action_texts_by_requirement.items())
        )
        expected_human_review_command_hints_by_requirement = dict(
            sorted(expected_human_review_command_hints_by_requirement.items())
        )
        if self.human_review_action_texts_by_requirement != expected_human_review_action_texts_by_requirement:
            raise ValueError(
                "human_review_action_texts_by_requirement must match human_review_unique_next_actions"
            )
        if self.human_review_command_hints_by_requirement != expected_human_review_command_hints_by_requirement:
            raise ValueError(
                "human_review_command_hints_by_requirement must match human_review_unique_next_actions"
            )
        if self.blocked_without_next_action_count != len(self.blocked_without_next_action_ids):
            raise ValueError("blocked_without_next_action_count must match blocked_without_next_action_ids length")
        if (
            "roadmap_blocker_blocked_without_next_action_count" in self.model_fields_set
            and
            self.roadmap_blocker_blocked_without_next_action_count
            != len(self.blocked_without_next_action_ids)
        ):
            raise ValueError(
                "roadmap_blocker_blocked_without_next_action_count must match "
                "blocked_without_next_action_ids length"
            )
        expected_blocked_without_next_action_ids = [
            check.requirement_id
            for check in self.checks
            if check.status == "fail" and not any(action.strip() for action in check.next_actions)
        ]
        if self.blocked_without_next_action_ids != expected_blocked_without_next_action_ids:
            raise ValueError("blocked_without_next_action_ids must match failed checks without next actions")
        expected_open_csv_paths = _roadmap_human_review_open_csv_paths(self.checks)
        expected_open_record_csv_paths = _roadmap_human_review_open_record_csv_paths(
            self.checks
        )
        expected_open_csv_row_count = _roadmap_human_review_open_csv_row_count(self.checks)
        expected_open_record_counts_by_requirement = (
            _roadmap_human_review_open_record_counts_by_requirement(self.checks)
        )
        expected_open_record_count = sum(expected_open_record_counts_by_requirement.values())
        expected_open_csv_paths_by_requirement = _roadmap_human_review_open_csv_paths_by_requirement(self.checks)
        expected_open_record_csv_paths_by_requirement = (
            _roadmap_human_review_open_record_csv_paths_by_requirement(self.checks)
        )
        expected_open_csv_row_counts_by_requirement = _roadmap_human_review_open_csv_row_counts_by_requirement(
            self.checks
        )
        expected_open_record_refs_by_requirement = _roadmap_human_review_string_list_by_requirement(
            self.checks,
            "_fill_review_status_open_record_refs",
        )
        expected_open_field_names_by_record_ref_by_requirement = (
            _roadmap_human_review_record_field_names_by_requirement(self.checks)
        )
        expected_open_field_names_by_requirement = (
            _roadmap_human_review_open_field_names_by_requirement(
                expected_open_field_names_by_record_ref_by_requirement
            )
        )
        expected_open_task_ids_by_record_ref_by_requirement = (
            _roadmap_human_review_record_task_ids_by_requirement(self.checks)
        )
        expected_open_record_filled_patch_field_counts_by_requirement = (
            _roadmap_human_review_count_map_by_requirement(
                self.checks,
                "_fill_review_status_open_record_filled_patch_field_counts_by_field",
            )
        )
        expected_open_record_filled_patch_field_counts_by_field = _sum_nested_count_map(
            expected_open_record_filled_patch_field_counts_by_requirement
        )
        expected_open_record_filled_patch_fields_by_record_ref_by_requirement = (
            _roadmap_human_review_record_field_list_map_by_requirement(
                self.checks,
                "_fill_review_status_open_record_filled_patch_fields_by_record_ref",
            )
        )
        expected_open_csv_missing_value_counts_by_requirement = (
            _roadmap_human_review_missing_value_counts_by_field_by_requirement(self.checks)
        )
        expected_open_csv_missing_value_count = sum(
            sum(counts.values())
            for counts in expected_open_csv_missing_value_counts_by_requirement.values()
        )
        expected_open_csv_missing_value_counts_by_field: dict[str, int] = {}
        for counts in expected_open_csv_missing_value_counts_by_requirement.values():
            for field_name, count in counts.items():
                expected_open_csv_missing_value_counts_by_field[field_name] = (
                    expected_open_csv_missing_value_counts_by_field.get(field_name, 0)
                    + count
                )
        expected_open_csv_missing_value_counts_by_field = dict(
            sorted(expected_open_csv_missing_value_counts_by_field.items())
        )
        expected_open_csv_missing_suggestion_counts_by_requirement = (
            _roadmap_human_review_count_map_by_requirement(
                self.checks,
                "_fill_review_status_missing_suggestion_count_by_field",
            )
        )
        expected_open_csv_missing_suggestion_counts_by_field = _sum_nested_count_map(
            expected_open_csv_missing_suggestion_counts_by_requirement
        )
        expected_open_csv_missing_suggestion_task_ids_by_requirement = (
            _roadmap_human_review_string_list_map_by_requirement(
                self.checks,
                "_fill_review_status_missing_suggestion_task_ids_by_field",
            )
        )
        expected_open_csv_missing_suggestion_task_ids_by_field = _merge_nested_string_list_map(
            expected_open_csv_missing_suggestion_task_ids_by_requirement
        )
        expected_open_csv_suggested_value_counts_by_requirement = (
            _roadmap_human_review_count_map_by_requirement(
                self.checks,
                "_fill_review_status_suggested_value_count_by_field",
            )
        )
        expected_open_csv_suggested_value_counts_by_field = _sum_nested_count_map(
            expected_open_csv_suggested_value_counts_by_requirement
        )
        expected_open_csv_available_context_counts_by_requirement = (
            _roadmap_human_review_count_map_by_requirement(
                self.checks,
                "_fill_review_status_available_context_count_by_field",
            )
        )
        expected_open_csv_available_context_counts_by_field = _sum_nested_count_map(
            expected_open_csv_available_context_counts_by_requirement
        )
        expected_open_csv_missing_context_counts_by_requirement = (
            _roadmap_human_review_count_map_by_requirement(
                self.checks,
                "_fill_review_status_missing_context_count_by_field",
            )
        )
        expected_open_csv_missing_context_counts_by_field = _sum_nested_count_map(
            expected_open_csv_missing_context_counts_by_requirement
        )
        expected_open_csv_missing_context_task_ids_by_requirement = (
            _roadmap_human_review_string_list_map_by_requirement(
                self.checks,
                "_fill_review_status_missing_context_task_ids_by_field",
            )
        )
        expected_open_csv_missing_context_task_ids_by_field = _merge_nested_string_list_map(
            expected_open_csv_missing_context_task_ids_by_requirement
        )
        expected_open_csv_available_context_keys_by_requirement = (
            _roadmap_human_review_string_list_map_by_requirement(
                self.checks,
                "_fill_review_status_available_context_keys_by_field",
            )
        )
        expected_open_csv_available_context_keys_by_field = _merge_nested_string_list_map(
            expected_open_csv_available_context_keys_by_requirement
        )
        expected_open_csv_available_context_values_by_requirement = (
            _roadmap_human_review_string_list_map_by_requirement(
                self.checks,
                "_fill_review_status_available_context_values_by_field",
            )
        )
        expected_open_csv_available_context_values_by_field = _merge_nested_string_list_map(
            expected_open_csv_available_context_values_by_requirement
        )
        expected_open_task_ids_by_requirement = _roadmap_human_review_string_list_by_requirement(
            self.checks,
            "_fill_review_status_open_task_ids",
        )
        expected_open_task_ids_by_field_by_requirement = (
            _roadmap_human_review_string_list_map_by_requirement(
                self.checks,
                "_fill_review_status_open_task_ids_by_field",
            )
        )
        expected_open_task_ids_by_field = _merge_nested_string_list_map(
            expected_open_task_ids_by_field_by_requirement
        )
        if self.human_review_open_csv_paths != expected_open_csv_paths:
            raise ValueError("human_review_open_csv_paths must match fill-review open CSV evidence")
        if self.human_review_open_record_csv_paths != expected_open_record_csv_paths:
            raise ValueError(
                "human_review_open_record_csv_paths must match fill-review open-record CSV evidence"
            )
        if self.human_review_open_csv_row_count != expected_open_csv_row_count:
            raise ValueError("human_review_open_csv_row_count must match fill-review open CSV evidence")
        if self.human_review_open_record_count != expected_open_record_count:
            raise ValueError(
                "human_review_open_record_count must match fill-review open-record evidence"
            )
        if self.human_review_open_csv_paths_by_requirement != expected_open_csv_paths_by_requirement:
            raise ValueError(
                "human_review_open_csv_paths_by_requirement must match fill-review open CSV evidence"
            )
        if (
            self.human_review_open_record_csv_paths_by_requirement
            != expected_open_record_csv_paths_by_requirement
        ):
            raise ValueError(
                "human_review_open_record_csv_paths_by_requirement must match "
                "fill-review open-record CSV evidence"
            )
        if self.human_review_open_csv_row_counts_by_requirement != expected_open_csv_row_counts_by_requirement:
            raise ValueError(
                "human_review_open_csv_row_counts_by_requirement must match fill-review open CSV evidence"
            )
        if (
            self.human_review_open_record_counts_by_requirement
            != expected_open_record_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_record_counts_by_requirement must match "
                "fill-review open-record evidence"
            )
        if (
            self.human_review_open_record_refs_by_requirement
            != expected_open_record_refs_by_requirement
        ):
            raise ValueError(
                "human_review_open_record_refs_by_requirement must match "
                "fill-review open-record evidence"
            )
        if (
            self.human_review_open_field_names_by_record_ref_by_requirement
            != expected_open_field_names_by_record_ref_by_requirement
        ):
            raise ValueError(
                "human_review_open_field_names_by_record_ref_by_requirement must match "
                "fill-review open-record evidence"
            )
        if (
            self.human_review_open_field_names_by_requirement
            != expected_open_field_names_by_requirement
        ):
            raise ValueError(
                "human_review_open_field_names_by_requirement must match "
                "fill-review open-record evidence"
            )
        if (
            self.human_review_open_task_ids_by_record_ref_by_requirement
            != expected_open_task_ids_by_record_ref_by_requirement
        ):
            raise ValueError(
                "human_review_open_task_ids_by_record_ref_by_requirement must match "
                "fill-review open-record evidence"
            )
        if (
            self.human_review_open_record_filled_patch_field_counts_by_requirement
            != expected_open_record_filled_patch_field_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_record_filled_patch_field_counts_by_requirement "
                "must match fill-review open-record prefilled evidence"
            )
        if (
            self.human_review_open_record_filled_patch_field_counts_by_field
            != expected_open_record_filled_patch_field_counts_by_field
        ):
            raise ValueError(
                "human_review_open_record_filled_patch_field_counts_by_field "
                "must match fill-review open-record prefilled evidence"
            )
        if (
            self.human_review_open_record_filled_patch_fields_by_record_ref_by_requirement
            != expected_open_record_filled_patch_fields_by_record_ref_by_requirement
        ):
            raise ValueError(
                "human_review_open_record_filled_patch_fields_by_record_ref_by_requirement "
                "must match fill-review open-record prefilled evidence"
            )
        if self.human_review_open_csv_missing_value_count != expected_open_csv_missing_value_count:
            raise ValueError(
                "human_review_open_csv_missing_value_count must match fill-review missing-value evidence"
            )
        if (
            self.human_review_open_csv_missing_value_counts_by_requirement
            != expected_open_csv_missing_value_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_missing_value_counts_by_requirement must match "
                "fill-review missing-value evidence"
            )
        if (
            self.human_review_open_csv_missing_value_counts_by_field
            != expected_open_csv_missing_value_counts_by_field
        ):
            raise ValueError(
                "human_review_open_csv_missing_value_counts_by_field must match "
                "fill-review missing-value evidence"
            )
        if (
            self.human_review_open_csv_missing_suggestion_counts_by_requirement
            != expected_open_csv_missing_suggestion_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_missing_suggestion_counts_by_requirement must match "
                "fill-review missing-suggestion evidence"
            )
        if (
            self.human_review_open_csv_missing_suggestion_counts_by_field
            != expected_open_csv_missing_suggestion_counts_by_field
        ):
            raise ValueError(
                "human_review_open_csv_missing_suggestion_counts_by_field must match "
                "fill-review missing-suggestion evidence"
            )
        if (
            self.human_review_open_csv_missing_suggestion_task_ids_by_requirement
            != expected_open_csv_missing_suggestion_task_ids_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_missing_suggestion_task_ids_by_requirement must match "
                "fill-review missing-suggestion task evidence"
            )
        if (
            self.human_review_open_csv_missing_suggestion_task_ids_by_field
            != expected_open_csv_missing_suggestion_task_ids_by_field
        ):
            raise ValueError(
                "human_review_open_csv_missing_suggestion_task_ids_by_field must match "
                "fill-review missing-suggestion task evidence"
            )
        if (
            self.human_review_open_csv_suggested_value_counts_by_requirement
            != expected_open_csv_suggested_value_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_suggested_value_counts_by_requirement must match "
                "fill-review suggested-value evidence"
            )
        if (
            self.human_review_open_csv_suggested_value_counts_by_field
            != expected_open_csv_suggested_value_counts_by_field
        ):
            raise ValueError(
                "human_review_open_csv_suggested_value_counts_by_field must match "
                "fill-review suggested-value evidence"
            )
        if (
            self.human_review_open_csv_available_context_counts_by_requirement
            != expected_open_csv_available_context_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_available_context_counts_by_requirement must match "
                "fill-review available-context evidence"
            )
        if (
            self.human_review_open_csv_available_context_counts_by_field
            != expected_open_csv_available_context_counts_by_field
        ):
            raise ValueError(
                "human_review_open_csv_available_context_counts_by_field must match "
                "fill-review available-context evidence"
            )
        if (
            self.human_review_open_csv_missing_context_counts_by_requirement
            != expected_open_csv_missing_context_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_missing_context_counts_by_requirement must match "
                "fill-review missing-context evidence"
            )
        if (
            self.human_review_open_csv_missing_context_counts_by_field
            != expected_open_csv_missing_context_counts_by_field
        ):
            raise ValueError(
                "human_review_open_csv_missing_context_counts_by_field must match "
                "fill-review missing-context evidence"
            )
        if (
            self.human_review_open_csv_missing_context_task_ids_by_requirement
            != expected_open_csv_missing_context_task_ids_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_missing_context_task_ids_by_requirement must match "
                "fill-review missing-context task evidence"
            )
        if (
            self.human_review_open_csv_missing_context_task_ids_by_field
            != expected_open_csv_missing_context_task_ids_by_field
        ):
            raise ValueError(
                "human_review_open_csv_missing_context_task_ids_by_field must match "
                "fill-review missing-context task evidence"
            )
        if (
            self.human_review_open_csv_reviewer_evidence_hint_counts_by_requirement
            != expected_open_csv_available_context_counts_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_reviewer_evidence_hint_counts_by_requirement must match "
                "fill-review available-context evidence"
            )
        if (
            self.human_review_open_csv_reviewer_evidence_hint_counts_by_field
            != expected_open_csv_available_context_counts_by_field
        ):
            raise ValueError(
                "human_review_open_csv_reviewer_evidence_hint_counts_by_field must match "
                "fill-review available-context evidence"
            )
        if (
            self.human_review_open_csv_available_context_keys_by_requirement
            != expected_open_csv_available_context_keys_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_available_context_keys_by_requirement must match "
                "fill-review available-context-key evidence"
            )
        if (
            self.human_review_open_csv_available_context_keys_by_field
            != expected_open_csv_available_context_keys_by_field
        ):
            raise ValueError(
                "human_review_open_csv_available_context_keys_by_field must match "
                "fill-review available-context-key evidence"
            )
        if (
            self.human_review_open_csv_available_context_values_by_requirement
            != expected_open_csv_available_context_values_by_requirement
        ):
            raise ValueError(
                "human_review_open_csv_available_context_values_by_requirement must match "
                "fill-review available-context-value evidence"
            )
        if (
            self.human_review_open_csv_available_context_values_by_field
            != expected_open_csv_available_context_values_by_field
        ):
            raise ValueError(
                "human_review_open_csv_available_context_values_by_field must match "
                "fill-review available-context-value evidence"
            )
        if self.human_review_open_task_ids_by_requirement != expected_open_task_ids_by_requirement:
            raise ValueError(
                "human_review_open_task_ids_by_requirement must match fill-review open task evidence"
            )
        if self.human_review_open_task_ids_by_field != expected_open_task_ids_by_field:
            raise ValueError(
                "human_review_open_task_ids_by_field must match fill-review open task evidence"
            )
        expected_frontier_summaries = _roadmap_frontier_next_action_summaries(
            self.frontier_next_actions,
            {
                check.requirement_id.strip()
                for check in self.checks
                if check.status == "fail" and check.requirement_id.strip()
            },
            expected_open_csv_paths_by_requirement,
            expected_open_csv_row_counts_by_requirement,
            _roadmap_missing_metric_inputs_by_requirement(self.checks),
            _roadmap_human_review_missing_value_counts_by_field_by_requirement(self.checks),
            expected_open_csv_missing_suggestion_counts_by_requirement,
            expected_open_csv_available_context_counts_by_requirement,
            expected_open_csv_missing_context_counts_by_requirement,
            expected_open_csv_missing_context_task_ids_by_requirement,
            expected_open_csv_available_context_keys_by_requirement,
            expected_open_csv_available_context_values_by_requirement,
            expected_open_task_ids_by_requirement,
            expected_open_task_ids_by_field_by_requirement,
        )
        observed_frontier_summaries = [
            (
                summary.requirement_id.strip(),
                (summary.phase or "").strip(),
                summary.kind,
                summary.requires_human_review,
                summary.has_command_hint,
                summary.has_unresolved_command_placeholder,
                [item.strip() for item in summary.unresolved_command_placeholders if item.strip()],
                [item.strip() for item in summary.missing_metric_inputs if item.strip()],
                [path.strip() for path in summary.human_review_open_csv_paths if path.strip()],
                summary.human_review_open_csv_row_count,
                {
                    key.strip(): value
                    for key, value in summary.human_review_open_csv_missing_value_counts_by_field.items()
                    if key.strip()
                },
                {
                    key.strip(): value
                    for key, value in summary.human_review_open_csv_missing_suggestion_counts_by_field.items()
                    if key.strip()
                },
                {
                    key.strip(): value
                    for key, value in summary.human_review_open_csv_available_context_counts_by_field.items()
                    if key.strip()
                },
                {
                    key.strip(): value
                    for key, value in summary.human_review_open_csv_missing_context_counts_by_field.items()
                    if key.strip()
                },
                {
                    key.strip(): [item.strip() for item in value if item.strip()]
                    for key, value in summary.human_review_open_csv_missing_context_task_ids_by_field.items()
                    if key.strip()
                },
                {
                    key.strip(): [item.strip() for item in value if item.strip()]
                    for key, value in summary.human_review_open_csv_available_context_keys_by_field.items()
                    if key.strip()
                },
                {
                    key.strip(): [item.strip() for item in value if item.strip()]
                    for key, value in summary.human_review_open_csv_available_context_values_by_field.items()
                    if key.strip()
                },
                [item.strip() for item in summary.human_review_open_task_ids if item.strip()],
                {
                    key.strip(): [item.strip() for item in value if item.strip()]
                    for key, value in summary.human_review_open_task_ids_by_field.items()
                    if key.strip()
                },
                summary.action.strip(),
                (summary.command_hint or "").strip(),
                [item.strip() for item in summary.blocker_reasons if item.strip()],
                [item.strip() for item in summary.blocked_by_requirement_ids if item.strip()],
            )
            for summary in self.frontier_next_action_summaries
        ]
        if observed_frontier_summaries != expected_frontier_summaries:
            raise ValueError("frontier_next_action_summaries must match frontier_next_actions")
        expected_frontier_unresolved_placeholder_count = sum(
            len(summary[6]) for summary in expected_frontier_summaries
        )
        expected_frontier_unresolved_placeholders_by_requirement = {
            summary[0]: summary[6] for summary in expected_frontier_summaries if summary[6]
        }
        expected_frontier_unresolved_placeholder_counts_by_placeholder: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for placeholder in summary[6]:
                expected_frontier_unresolved_placeholder_counts_by_placeholder[placeholder] = (
                    expected_frontier_unresolved_placeholder_counts_by_placeholder.get(placeholder, 0)
                    + 1
                )
        expected_frontier_missing_metric_input_count = sum(
            len(summary[7]) for summary in expected_frontier_summaries
        )
        expected_frontier_missing_metric_inputs_by_requirement = {
            summary[0]: summary[7] for summary in expected_frontier_summaries if summary[7]
        }
        expected_frontier_missing_metric_input_counts_by_metric: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for metric in summary[7]:
                expected_frontier_missing_metric_input_counts_by_metric[metric] = (
                    expected_frontier_missing_metric_input_counts_by_metric.get(metric, 0)
                    + 1
                )
        expected_frontier_open_csv_paths_by_requirement = {
            summary[0]: summary[8] for summary in expected_frontier_summaries if summary[8]
        }
        expected_frontier_open_csv_row_counts_by_requirement = {
            summary[0]: summary[9] for summary in expected_frontier_summaries if summary[9]
        }
        expected_frontier_open_csv_missing_value_count = sum(
            sum(summary[10].values()) for summary in expected_frontier_summaries
        )
        expected_frontier_open_field_names_by_requirement = {
            summary[0]: sorted(summary[10].keys())
            for summary in expected_frontier_summaries
            if summary[10]
        }
        expected_frontier_open_csv_missing_value_counts_by_requirement = {
            summary[0]: summary[10]
            for summary in expected_frontier_summaries
            if summary[10]
        }
        expected_frontier_open_csv_missing_value_counts_by_field: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for field_name, count in summary[10].items():
                expected_frontier_open_csv_missing_value_counts_by_field[field_name] = (
                    expected_frontier_open_csv_missing_value_counts_by_field.get(field_name, 0)
                    + count
                )
        expected_frontier_open_csv_missing_suggestion_counts_by_requirement = {
            summary[0]: summary[11]
            for summary in expected_frontier_summaries
            if summary[11]
        }
        expected_frontier_open_csv_missing_suggestion_counts_by_field: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for field_name, count in summary[11].items():
                expected_frontier_open_csv_missing_suggestion_counts_by_field[field_name] = (
                    expected_frontier_open_csv_missing_suggestion_counts_by_field.get(field_name, 0)
                    + count
                )
        expected_frontier_open_csv_missing_suggestion_task_ids_by_requirement = {
            summary[0]: expected_open_csv_missing_suggestion_task_ids_by_requirement[summary[0]]
            for summary in expected_frontier_summaries
            if summary[0] in expected_open_csv_missing_suggestion_task_ids_by_requirement
        }
        expected_frontier_open_csv_missing_suggestion_task_ids_by_field = (
            _merge_nested_string_list_map(
                expected_frontier_open_csv_missing_suggestion_task_ids_by_requirement
            )
        )
        expected_frontier_open_csv_suggested_value_counts_by_requirement = (
            _positive_count_difference_by_requirement(
                expected_frontier_open_csv_missing_value_counts_by_requirement,
                expected_frontier_open_csv_missing_suggestion_counts_by_requirement,
            )
        )
        expected_frontier_open_csv_suggested_value_counts_by_field = _sum_nested_count_map(
            expected_frontier_open_csv_suggested_value_counts_by_requirement
        )
        expected_frontier_open_record_filled_patch_field_counts_by_requirement = {
            summary[0]: expected_open_record_filled_patch_field_counts_by_requirement[summary[0]]
            for summary in expected_frontier_summaries
            if summary[0] in expected_open_record_filled_patch_field_counts_by_requirement
        }
        expected_frontier_open_record_filled_patch_field_counts_by_field = (
            _sum_nested_count_map(
                expected_frontier_open_record_filled_patch_field_counts_by_requirement
            )
        )
        expected_frontier_open_record_filled_patch_fields_by_record_ref_by_requirement = {
            summary[0]: expected_open_record_filled_patch_fields_by_record_ref_by_requirement[summary[0]]
            for summary in expected_frontier_summaries
            if summary[0] in expected_open_record_filled_patch_fields_by_record_ref_by_requirement
        }
        expected_frontier_open_csv_available_context_counts_by_requirement = {
            summary[0]: summary[12]
            for summary in expected_frontier_summaries
            if summary[12]
        }
        expected_frontier_open_csv_available_context_counts_by_field: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for field_name, count in summary[12].items():
                expected_frontier_open_csv_available_context_counts_by_field[field_name] = (
                    expected_frontier_open_csv_available_context_counts_by_field.get(field_name, 0)
                    + count
                )
        expected_frontier_open_csv_missing_context_counts_by_requirement = {
            summary[0]: summary[13]
            for summary in expected_frontier_summaries
            if summary[13]
        }
        expected_frontier_open_csv_missing_context_counts_by_field: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for field_name, count in summary[13].items():
                expected_frontier_open_csv_missing_context_counts_by_field[field_name] = (
                    expected_frontier_open_csv_missing_context_counts_by_field.get(field_name, 0)
                    + count
                )
        expected_frontier_open_csv_missing_context_task_ids_by_requirement = {
            summary[0]: summary[14]
            for summary in expected_frontier_summaries
            if summary[14]
        }
        expected_frontier_open_csv_missing_context_task_ids_by_field = _merge_nested_string_list_map(
            expected_frontier_open_csv_missing_context_task_ids_by_requirement
        )
        expected_frontier_open_csv_available_context_keys_by_requirement = {
            summary[0]: summary[15]
            for summary in expected_frontier_summaries
            if summary[15]
        }
        expected_frontier_open_csv_available_context_keys_by_field = _merge_nested_string_list_map(
            expected_frontier_open_csv_available_context_keys_by_requirement
        )
        expected_frontier_open_csv_available_context_values_by_requirement = {
            summary[0]: summary[16]
            for summary in expected_frontier_summaries
            if summary[16]
        }
        expected_frontier_open_csv_available_context_values_by_field = _merge_nested_string_list_map(
            expected_frontier_open_csv_available_context_values_by_requirement
        )
        expected_frontier_open_task_ids_by_requirement = {
            summary[0]: summary[17]
            for summary in expected_frontier_summaries
            if summary[17]
        }
        expected_frontier_open_task_ids_by_field = _merge_nested_string_list_map(
            {
                summary[0]: summary[18]
                for summary in expected_frontier_summaries
                if summary[18]
            }
        )
        expected_frontier_blocker_reasons_by_requirement = {
            summary[0]: summary[21]
            for summary in expected_frontier_summaries
            if summary[21]
        }
        expected_frontier_blocker_reason_counts: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for reason in summary[21]:
                expected_frontier_blocker_reason_counts[reason] = (
                    expected_frontier_blocker_reason_counts.get(reason, 0) + 1
                )
        expected_frontier_blocked_by_requirement_ids_by_requirement = {
            summary[0]: summary[22]
            for summary in expected_frontier_summaries
            if summary[22]
        }
        expected_frontier_blocked_by_requirement_counts: dict[str, int] = {}
        for summary in expected_frontier_summaries:
            for requirement_id in summary[22]:
                expected_frontier_blocked_by_requirement_counts[requirement_id] = (
                    expected_frontier_blocked_by_requirement_counts.get(requirement_id, 0)
                    + 1
                )
        expected_frontier_blocked_by_requirement_unique_ids_by_requirement: dict[str, list[str]] = {}
        expected_frontier_blocked_by_requirement_unique_counts: dict[str, int] = {}
        for requirement_id, blocked_requirement_ids in (
            expected_frontier_blocked_by_requirement_ids_by_requirement.items()
        ):
            seen_blocked_ids: set[str] = set()
            unique_blocked_ids: list[str] = []
            for blocked_requirement_id in blocked_requirement_ids:
                if blocked_requirement_id in seen_blocked_ids:
                    continue
                seen_blocked_ids.add(blocked_requirement_id)
                unique_blocked_ids.append(blocked_requirement_id)
            if unique_blocked_ids:
                expected_frontier_blocked_by_requirement_unique_ids_by_requirement[
                    requirement_id
                ] = unique_blocked_ids
                for blocked_requirement_id in unique_blocked_ids:
                    expected_frontier_blocked_by_requirement_unique_counts[
                        blocked_requirement_id
                    ] = (
                        expected_frontier_blocked_by_requirement_unique_counts.get(
                            blocked_requirement_id,
                            0,
                        )
                        + 1
                    )
        if self.frontier_unresolved_command_placeholder_count != expected_frontier_unresolved_placeholder_count:
            raise ValueError(
                "frontier_unresolved_command_placeholder_count must match frontier_next_action_summaries"
            )
        if (
            self.frontier_unresolved_command_placeholders_by_requirement
            != expected_frontier_unresolved_placeholders_by_requirement
        ):
            raise ValueError(
                "frontier_unresolved_command_placeholders_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_unresolved_command_placeholder_counts_by_placeholder
            != expected_frontier_unresolved_placeholder_counts_by_placeholder
        ):
            raise ValueError(
                "frontier_unresolved_command_placeholder_counts_by_placeholder must match "
                "frontier_next_action_summaries"
            )
        if self.frontier_missing_metric_input_count != expected_frontier_missing_metric_input_count:
            raise ValueError("frontier_missing_metric_input_count must match frontier_next_action_summaries")
        if self.frontier_missing_metric_inputs_by_requirement != expected_frontier_missing_metric_inputs_by_requirement:
            raise ValueError(
                "frontier_missing_metric_inputs_by_requirement must match frontier_next_action_summaries"
            )
        if self.frontier_missing_metric_input_counts_by_metric != expected_frontier_missing_metric_input_counts_by_metric:
            raise ValueError(
                "frontier_missing_metric_input_counts_by_metric must match frontier_next_action_summaries"
            )
        if self.frontier_human_review_open_csv_paths_by_requirement != expected_frontier_open_csv_paths_by_requirement:
            raise ValueError(
                "frontier_human_review_open_csv_paths_by_requirement must match frontier_next_action_summaries"
            )
        if self.frontier_human_review_open_csv_row_counts_by_requirement != expected_frontier_open_csv_row_counts_by_requirement:
            raise ValueError(
                "frontier_human_review_open_csv_row_counts_by_requirement must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_field_names_by_requirement
            != expected_frontier_open_field_names_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_field_names_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if self.frontier_human_review_open_csv_missing_value_count != expected_frontier_open_csv_missing_value_count:
            raise ValueError(
                "frontier_human_review_open_csv_missing_value_count must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_value_counts_by_requirement
            != expected_frontier_open_csv_missing_value_counts_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_value_counts_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_value_counts_by_field
            != expected_frontier_open_csv_missing_value_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_value_counts_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_suggestion_counts_by_requirement
            != expected_frontier_open_csv_missing_suggestion_counts_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_suggestion_counts_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_suggestion_counts_by_field
            != expected_frontier_open_csv_missing_suggestion_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_suggestion_counts_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement
            != expected_frontier_open_csv_missing_suggestion_task_ids_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_suggestion_task_ids_by_requirement "
                "must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_suggestion_task_ids_by_field
            != expected_frontier_open_csv_missing_suggestion_task_ids_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_suggestion_task_ids_by_field "
                "must match frontier_next_action_summaries"
            )
        if (
            self.roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_requirement
            != expected_frontier_open_csv_missing_suggestion_task_ids_by_requirement
        ):
            raise ValueError(
                "roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_requirement "
                "must match frontier_next_action_summaries"
            )
        if (
            self.roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_field
            != expected_frontier_open_csv_missing_suggestion_task_ids_by_field
        ):
            raise ValueError(
                "roadmap_blocker_human_review_open_csv_missing_suggestion_task_ids_by_field "
                "must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_suggested_value_counts_by_requirement
            != expected_frontier_open_csv_suggested_value_counts_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_suggested_value_counts_by_requirement "
                "must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_suggested_value_counts_by_field
            != expected_frontier_open_csv_suggested_value_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_suggested_value_counts_by_field "
                "must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_record_filled_patch_field_counts_by_requirement
            != expected_frontier_open_record_filled_patch_field_counts_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_record_filled_patch_field_counts_by_requirement "
                "must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_record_filled_patch_field_counts_by_field
            != expected_frontier_open_record_filled_patch_field_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_record_filled_patch_field_counts_by_field "
                "must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_record_filled_patch_fields_by_record_ref_by_requirement
            != expected_frontier_open_record_filled_patch_fields_by_record_ref_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_record_filled_patch_fields_by_record_ref_by_requirement "
                "must match frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_available_context_counts_by_requirement
            != expected_frontier_open_csv_available_context_counts_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_available_context_counts_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_available_context_counts_by_field
            != expected_frontier_open_csv_available_context_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_available_context_counts_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_context_counts_by_requirement
            != expected_frontier_open_csv_missing_context_counts_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_context_counts_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_context_counts_by_field
            != expected_frontier_open_csv_missing_context_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_context_counts_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_context_task_ids_by_requirement
            != expected_frontier_open_csv_missing_context_task_ids_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_context_task_ids_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_missing_context_task_ids_by_field
            != expected_frontier_open_csv_missing_context_task_ids_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_missing_context_task_ids_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement
            != expected_frontier_open_csv_available_context_counts_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field
            != expected_frontier_open_csv_available_context_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_reviewer_evidence_hint_counts_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_available_context_keys_by_requirement
            != expected_frontier_open_csv_available_context_keys_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_available_context_keys_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_available_context_keys_by_field
            != expected_frontier_open_csv_available_context_keys_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_available_context_keys_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_available_context_values_by_requirement
            != expected_frontier_open_csv_available_context_values_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_csv_available_context_values_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_csv_available_context_values_by_field
            != expected_frontier_open_csv_available_context_values_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_csv_available_context_values_by_field must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_task_ids_by_requirement
            != expected_frontier_open_task_ids_by_requirement
        ):
            raise ValueError(
                "frontier_human_review_open_task_ids_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_open_task_ids_by_field
            != expected_frontier_open_task_ids_by_field
        ):
            raise ValueError(
                "frontier_human_review_open_task_ids_by_field must match "
                "frontier_next_action_summaries"
            )
        if self.frontier_blocker_reasons_by_requirement != expected_frontier_blocker_reasons_by_requirement:
            raise ValueError(
                "frontier_blocker_reasons_by_requirement must match frontier_next_action_summaries"
            )
        if self.frontier_blocker_reason_counts != expected_frontier_blocker_reason_counts:
            raise ValueError(
                "frontier_blocker_reason_counts must match frontier_next_action_summaries"
            )
        if (
            "roadmap_blocker_reason_counts" in self.model_fields_set
            and
            self.roadmap_blocker_reason_counts
            != expected_frontier_blocker_reason_counts
        ):
            raise ValueError(
                "roadmap_blocker_reason_counts must match frontier_next_action_summaries"
            )
        if (
            self.frontier_blocked_by_requirement_ids_by_requirement
            != expected_frontier_blocked_by_requirement_ids_by_requirement
        ):
            raise ValueError(
                "frontier_blocked_by_requirement_ids_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if self.frontier_blocked_by_requirement_counts != expected_frontier_blocked_by_requirement_counts:
            raise ValueError(
                "frontier_blocked_by_requirement_counts must match frontier_next_action_summaries"
            )
        if (
            self.frontier_blocked_by_requirement_unique_ids_by_requirement
            != expected_frontier_blocked_by_requirement_unique_ids_by_requirement
        ):
            raise ValueError(
                "frontier_blocked_by_requirement_unique_ids_by_requirement must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_blocked_by_requirement_unique_counts
            != expected_frontier_blocked_by_requirement_unique_counts
        ):
            raise ValueError(
                "frontier_blocked_by_requirement_unique_counts must match "
                "frontier_next_action_summaries"
            )
        if (
            self.frontier_human_review_queue_split_ready_source_count
            + self.frontier_human_review_queue_split_blocked_source_count
            != self.frontier_human_review_queue_split_source_csv_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split source counts must match "
                "frontier_human_review_queue_split_source_csv_count"
            )
        if (
            self.frontier_human_review_queue_split_source_csv_count
            and not (
                self.frontier_human_review_queue_split_manifest_path
                and self.frontier_human_review_queue_split_manifest_path.strip()
            )
        ):
            raise ValueError(
                "frontier_human_review_queue_split_manifest_path is required when "
                "frontier_human_review_queue_split_source_csv_count is non-zero"
            )
        if (
            self.frontier_human_review_queue_split_merged_missing_value_count
            > self.frontier_human_review_queue_split_merged_review_row_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_missing_value_count cannot exceed "
                "frontier_human_review_queue_split_merged_review_row_count"
            )
        if (
            "frontier_human_review_queue_split_merged_reviewed_value_count"
            in self.model_fields_set
            and self.frontier_human_review_queue_split_merged_reviewed_value_count
            + self.frontier_human_review_queue_split_merged_missing_value_count
            != self.frontier_human_review_queue_split_merged_review_row_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split merged value counts must match "
                "frontier_human_review_queue_split_merged_review_row_count"
            )
        if (
            self.frontier_human_review_queue_split_merged_missing_evidence_count
            > self.frontier_human_review_queue_split_merged_review_row_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_missing_evidence_count cannot exceed "
                "frontier_human_review_queue_split_merged_review_row_count"
            )
        if (
            "frontier_human_review_queue_split_merged_reviewed_evidence_count"
            in self.model_fields_set
            and self.frontier_human_review_queue_split_merged_reviewed_evidence_count
            + self.frontier_human_review_queue_split_merged_missing_evidence_count
            != self.frontier_human_review_queue_split_merged_review_row_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split merged evidence counts must match "
                "frontier_human_review_queue_split_merged_review_row_count"
            )
        if (
            self.frontier_human_review_queue_split_reviewer_value_hint_count
            > self.frontier_human_review_queue_split_merged_review_row_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_reviewer_value_hint_count cannot exceed "
                "frontier_human_review_queue_split_merged_review_row_count"
            )
        if (
            self.frontier_human_review_queue_split_reviewer_evidence_hint_count
            > self.frontier_human_review_queue_split_merged_review_row_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_reviewer_evidence_hint_count cannot exceed "
                "frontier_human_review_queue_split_merged_review_row_count"
            )
        if (
            len(self.frontier_human_review_queue_split_ready_reviewed_csv_paths)
            != self.frontier_human_review_queue_split_ready_source_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_ready_reviewed_csv_paths must match "
                "frontier_human_review_queue_split_ready_source_count"
            )
        if (
            len(self.frontier_human_review_queue_split_blocked_reviewed_csv_paths)
            != self.frontier_human_review_queue_split_blocked_source_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_blocked_reviewed_csv_paths must match "
                "frontier_human_review_queue_split_blocked_source_count"
            )
        split_ready_reviewed_csv_paths = [
            path.strip()
            for path in self.frontier_human_review_queue_split_ready_reviewed_csv_paths
            if path.strip()
        ]
        split_blocked_reviewed_csv_paths = [
            path.strip()
            for path in self.frontier_human_review_queue_split_blocked_reviewed_csv_paths
            if path.strip()
        ]
        split_reviewed_csv_paths = (
            split_ready_reviewed_csv_paths + split_blocked_reviewed_csv_paths
        )
        split_reviewed_csv_path_set = set(split_reviewed_csv_paths)
        split_blocked_reviewed_csv_path_set = set(split_blocked_reviewed_csv_paths)
        if len(split_reviewed_csv_paths) != len(split_reviewed_csv_path_set):
            raise ValueError(
                "frontier_human_review_queue_split reviewed CSV paths must be unique"
            )

        def _stripped_key_set(values: dict[str, object]) -> set[str]:
            return {key.strip() for key in values if key.strip()}

        def _nested_string_values(values: dict[str, list[str]]) -> list[str]:
            nested_values: list[str] = []
            for value_list in values.values():
                nested_values.extend(
                    value.strip()
                    for value in value_list
                    if isinstance(value, str) and value.strip()
                )
            return nested_values

        def _split_count_map_by_requirement_from_reviewed_paths(
            paths_by_requirement: dict[str, list[str]],
            counts_by_reviewed_csv_path: dict[str, dict[str, int]],
        ) -> dict[str, dict[str, int]]:
            counts_by_requirement: dict[str, dict[str, int]] = {}
            for requirement_id, reviewed_csv_paths in paths_by_requirement.items():
                clean_requirement_id = requirement_id.strip()
                if not clean_requirement_id:
                    continue
                merged_counts: dict[str, int] = {}
                for reviewed_csv_path in reviewed_csv_paths:
                    for field_name, count in counts_by_reviewed_csv_path.get(
                        reviewed_csv_path,
                        {},
                    ).items():
                        clean_field_name = field_name.strip()
                        if not clean_field_name or count <= 0:
                            continue
                        merged_counts[clean_field_name] = (
                            merged_counts.get(clean_field_name, 0) + count
                        )
                if merged_counts:
                    counts_by_requirement[clean_requirement_id] = dict(
                        sorted(merged_counts.items())
                    )
            return dict(sorted(counts_by_requirement.items()))

        def _split_task_ids_by_requirement_from_reviewed_paths(
            paths_by_requirement: dict[str, list[str]],
            task_ids_by_reviewed_csv_path: dict[str, list[str]],
        ) -> dict[str, list[str]]:
            task_ids_by_requirement: dict[str, list[str]] = {}
            for requirement_id, reviewed_csv_paths in paths_by_requirement.items():
                clean_requirement_id = requirement_id.strip()
                if not clean_requirement_id:
                    continue
                seen_task_ids: set[str] = set()
                task_ids: list[str] = []
                for reviewed_csv_path in reviewed_csv_paths:
                    for task_id in task_ids_by_reviewed_csv_path.get(reviewed_csv_path, []):
                        clean_task_id = task_id.strip()
                        if not clean_task_id or clean_task_id in seen_task_ids:
                            continue
                        seen_task_ids.add(clean_task_id)
                        task_ids.append(clean_task_id)
                if task_ids:
                    task_ids_by_requirement[clean_requirement_id] = task_ids
            return dict(sorted(task_ids_by_requirement.items()))

        def _split_string_values_by_requirement_from_reviewed_paths(
            paths_by_requirement: dict[str, list[str]],
            values_by_reviewed_csv_path: dict[str, str],
        ) -> dict[str, list[str]]:
            values_by_requirement: dict[str, list[str]] = {}
            for requirement_id, reviewed_csv_paths in paths_by_requirement.items():
                clean_requirement_id = requirement_id.strip()
                if not clean_requirement_id:
                    continue
                seen_values: set[str] = set()
                values: list[str] = []
                for reviewed_csv_path in reviewed_csv_paths:
                    value = values_by_reviewed_csv_path.get(reviewed_csv_path, "").strip()
                    if not value or value in seen_values:
                        continue
                    seen_values.add(value)
                    values.append(value)
                if values:
                    values_by_requirement[clean_requirement_id] = values
            return dict(sorted(values_by_requirement.items()))

        if (
            "frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path
            )
            != split_blocked_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split_blocked_reviewed_csv_paths"
            )
        if (
            "frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path"
            in self.model_fields_set
            and any(
                not [reason.strip() for reason in reasons if reason.strip()]
                for reasons in (
                    self.frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path.values()
                )
            )
        ):
            raise ValueError(
                "frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path "
                "must include blocked source reasons"
            )
        if (
            "frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path
            )
            != split_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_requirement_ids_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split reviewed CSV paths"
            )
        if (
            "frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path
            )
            != split_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_source_task_export_paths_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split reviewed CSV paths"
            )
        if (
            "frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path
            )
            != split_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split reviewed CSV paths"
            )
        if (
            "frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path
            )
            != split_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split reviewed CSV paths"
            )
        if (
            "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path
            )
            != split_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split reviewed CSV paths"
            )
        if (
            "frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path
            )
            != split_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split reviewed CSV paths"
            )
        if (
            "frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and _stripped_key_set(
                self.frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path
            )
            != split_reviewed_csv_path_set
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split reviewed CSV paths"
            )
        if (
            "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and sum(
                self.frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path.values()
            )
            != self.frontier_human_review_queue_split_merged_review_row_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split_merged_review_row_count"
            )
        if (
            "frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and sum(
                self.frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path.values()
            )
            != self.frontier_human_review_queue_split_merged_reviewed_value_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split_merged_reviewed_value_count"
            )
        if (
            "frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and sum(
                self.frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path.values()
            )
            != self.frontier_human_review_queue_split_merged_reviewed_evidence_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split_merged_reviewed_evidence_count"
            )
        if (
            "frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path"
            in self.model_fields_set
            and "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path"
            in self.model_fields_set
        ):
            for reviewed_csv_path, merged_count in (
                self.frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path.items()
            ):
                source_count = (
                    self.frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path.get(
                        reviewed_csv_path,
                        0,
                    )
                )
                if merged_count > source_count:
                    raise ValueError(
                        "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path "
                        "cannot exceed frontier_human_review_queue_split_source_row_counts_by_reviewed_csv_path"
                    )
                missing_value_count = len(
                    self.frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path.get(
                        reviewed_csv_path,
                        [],
                    )
                )
                missing_evidence_count = len(
                    self.frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path.get(
                        reviewed_csv_path,
                        [],
                    )
                )
                if merged_count < missing_value_count:
                    raise ValueError(
                        "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path "
                        "cannot be less than missing value task count"
                    )
                if merged_count < missing_evidence_count:
                    raise ValueError(
                        "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path "
                        "cannot be less than missing evidence task count"
                    )
                if (
                    "frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path"
                    in self.model_fields_set
                ):
                    reviewed_value_count = (
                        self.frontier_human_review_queue_split_merged_reviewed_value_counts_by_reviewed_csv_path.get(
                            reviewed_csv_path,
                            0,
                        )
                    )
                    if reviewed_value_count + missing_value_count != merged_count:
                        raise ValueError(
                            "frontier_human_review_queue_split merged value source counts must match "
                            "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path"
                        )
                if (
                    "frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path"
                    in self.model_fields_set
                ):
                    reviewed_evidence_count = (
                        self.frontier_human_review_queue_split_merged_reviewed_evidence_counts_by_reviewed_csv_path.get(
                            reviewed_csv_path,
                            0,
                        )
                    )
                    if reviewed_evidence_count + missing_evidence_count != merged_count:
                        raise ValueError(
                            "frontier_human_review_queue_split merged evidence source counts must match "
                            "frontier_human_review_queue_split_merged_review_row_counts_by_reviewed_csv_path"
                        )
        expected_split_missing_value_counts_by_field = _sum_nested_count_map(
            self.frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path
        )
        if (
            sum(expected_split_missing_value_counts_by_field.values())
            != self.frontier_human_review_queue_split_merged_missing_value_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split_merged_missing_value_count"
            )
        expected_split_missing_evidence_counts_by_field = _sum_nested_count_map(
            self.frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path
        )
        if (
            sum(expected_split_missing_evidence_counts_by_field.values())
            != self.frontier_human_review_queue_split_merged_missing_evidence_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path "
                "must match frontier_human_review_queue_split_merged_missing_evidence_count"
            )
        expected_split_reviewer_value_hint_counts_by_field = _sum_nested_count_map(
            self.frontier_human_review_queue_split_reviewer_value_hint_counts_by_reviewed_csv_path
        )
        if (
            expected_split_reviewer_value_hint_counts_by_field
            != self.frontier_human_review_queue_split_reviewer_value_hint_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_queue_split_reviewer_value_hint_counts_by_field "
                "must match reviewed CSV path counts"
            )
        if (
            sum(self.frontier_human_review_queue_split_reviewer_value_hint_counts_by_field.values())
            != self.frontier_human_review_queue_split_reviewer_value_hint_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_reviewer_value_hint_counts_by_field "
                "must match frontier_human_review_queue_split_reviewer_value_hint_count"
            )
        expected_split_reviewer_evidence_hint_counts_by_field = _sum_nested_count_map(
            self.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_reviewed_csv_path
        )
        if (
            expected_split_reviewer_evidence_hint_counts_by_field
            != self.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field "
                "must match reviewed CSV path counts"
            )
        if (
            sum(self.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field.values())
            != self.frontier_human_review_queue_split_reviewer_evidence_hint_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_field "
                "must match frontier_human_review_queue_split_reviewer_evidence_hint_count"
            )
        expected_split_missing_value_with_hint_counts_by_field = _sum_nested_count_map(
            self.frontier_human_review_queue_split_missing_value_with_hint_counts_by_reviewed_csv_path
        )
        if (
            expected_split_missing_value_with_hint_counts_by_field
            != self.frontier_human_review_queue_split_missing_value_with_hint_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_queue_split_missing_value_with_hint_counts_by_field "
                "must match reviewed CSV path counts"
            )
        if (
            sum(self.frontier_human_review_queue_split_missing_value_with_hint_counts_by_field.values())
            != self.frontier_human_review_queue_split_missing_value_with_hint_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_missing_value_with_hint_counts_by_field "
                "must match frontier_human_review_queue_split_missing_value_with_hint_count"
            )
        expected_split_missing_value_without_hint_counts_by_field = _sum_nested_count_map(
            self.frontier_human_review_queue_split_missing_value_without_hint_counts_by_reviewed_csv_path
        )
        if (
            expected_split_missing_value_without_hint_counts_by_field
            != self.frontier_human_review_queue_split_missing_value_without_hint_counts_by_field
        ):
            raise ValueError(
                "frontier_human_review_queue_split_missing_value_without_hint_counts_by_field "
                "must match reviewed CSV path counts"
            )
        if (
            sum(self.frontier_human_review_queue_split_missing_value_without_hint_counts_by_field.values())
            != self.frontier_human_review_queue_split_missing_value_without_hint_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split_missing_value_without_hint_counts_by_field "
                "must match frontier_human_review_queue_split_missing_value_without_hint_count"
            )
        if (
            self.frontier_human_review_queue_split_missing_value_with_hint_count
            + self.frontier_human_review_queue_split_missing_value_without_hint_count
            != self.frontier_human_review_queue_split_merged_missing_value_count
        ):
            raise ValueError(
                "frontier_human_review_queue_split missing value hint counts must match "
                "frontier_human_review_queue_split_merged_missing_value_count"
            )
        for (
            reviewed_csv_path,
            counts_by_field,
        ) in self.frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path.items():
            expected_task_count = sum(counts_by_field.values())
            actual_task_count = len(
                self.frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path.get(
                    reviewed_csv_path,
                    [],
                )
            )
            if actual_task_count != expected_task_count:
                raise ValueError(
                    "frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path "
                    "must match missing value counts"
                )
        for (
            reviewed_csv_path,
            counts_by_field,
        ) in self.frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path.items():
            expected_task_count = sum(counts_by_field.values())
            actual_task_count = len(
                self.frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path.get(
                    reviewed_csv_path,
                    [],
                )
            )
            if actual_task_count != expected_task_count:
                raise ValueError(
                    "frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path "
                    "must match missing evidence counts"
                )
        for field_name, values in (
            (
                "frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement",
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
            ),
            (
                "frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement",
                self.frontier_unblocked_human_review_queue_split_fill_review_audit_command_hints_by_requirement,
            ),
            (
                "frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement",
                self.frontier_unblocked_human_review_queue_split_fill_task_apply_command_hints_by_requirement,
            ),
            (
                "frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement",
                self.frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement,
            ),
            (
                "frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement",
                self.frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement,
            ),
        ):
            if field_name in self.model_fields_set:
                keys = _stripped_key_set(values)
                if not keys.issubset(expected_frontier_unblocked_requirement_ids):
                    raise ValueError(f"{field_name} must match unblocked frontier requirements")
                if any(not _nested_string_values({key: value}) for key, value in values.items()):
                    raise ValueError(f"{field_name} must include non-empty values")
        for field_name, values in (
            (
                "frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement",
                self.frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement,
            ),
            (
                "frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement",
                self.frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement,
            ),
        ):
            if field_name in self.model_fields_set:
                keys = _stripped_key_set(values)
                if not keys.issubset(expected_frontier_unblocked_requirement_ids):
                    raise ValueError(f"{field_name} must match unblocked frontier requirements")
                if any(not _nested_string_values({key: value}) for key, value in values.items()):
                    raise ValueError(f"{field_name} must include non-empty task ids")
        expected_unblocked_split_missing_value_counts_by_requirement = (
            _split_count_map_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_missing_value_counts_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement
            != expected_unblocked_split_missing_value_counts_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_missing_value_counts_by_requirement "
                "must match unblocked split reviewed CSV path counts"
            )
        expected_unblocked_split_missing_evidence_counts_by_requirement = (
            _split_count_map_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_missing_evidence_counts_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement
            != expected_unblocked_split_missing_evidence_counts_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_missing_evidence_counts_by_requirement "
                "must match unblocked split reviewed CSV path counts"
            )
        expected_unblocked_split_reviewer_value_hint_counts_by_requirement = (
            _split_count_map_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_reviewer_value_hint_counts_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement
            != expected_unblocked_split_reviewer_value_hint_counts_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_reviewer_value_hint_counts_by_requirement "
                "must match unblocked split reviewed CSV path reviewer value hint counts"
            )
        expected_unblocked_split_reviewer_evidence_hint_counts_by_requirement = (
            _split_count_map_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_reviewer_evidence_hint_counts_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement
            != expected_unblocked_split_reviewer_evidence_hint_counts_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_reviewer_evidence_hint_counts_by_requirement "
                "must match unblocked split reviewed CSV path reviewer evidence hint counts"
            )
        expected_unblocked_split_missing_value_task_ids_by_requirement = (
            _split_task_ids_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_missing_value_task_ids_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement
            != expected_unblocked_split_missing_value_task_ids_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_missing_value_task_ids_by_requirement "
                "must match unblocked split reviewed CSV path task ids"
            )
        expected_unblocked_split_missing_evidence_task_ids_by_requirement = (
            _split_task_ids_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_missing_evidence_task_ids_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement
            != expected_unblocked_split_missing_evidence_task_ids_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_missing_evidence_task_ids_by_requirement "
                "must match unblocked split reviewed CSV path task ids"
            )
        expected_unblocked_split_missing_value_task_id_counts_by_requirement = {
            requirement_id: len(task_ids)
            for requirement_id, task_ids in (
                expected_unblocked_split_missing_value_task_ids_by_requirement.items()
            )
        }
        if (
            "frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement
            != expected_unblocked_split_missing_value_task_id_counts_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_missing_value_task_id_counts_by_requirement "
                "must match unblocked split missing value task ids"
            )
        expected_unblocked_split_missing_evidence_task_id_counts_by_requirement = {
            requirement_id: len(task_ids)
            for requirement_id, task_ids in (
                expected_unblocked_split_missing_evidence_task_ids_by_requirement.items()
            )
        }
        if (
            "frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement
            != expected_unblocked_split_missing_evidence_task_id_counts_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_missing_evidence_task_id_counts_by_requirement "
                "must match unblocked split missing evidence task ids"
            )
        expected_unblocked_split_next_action_kinds_by_requirement = (
            _split_string_values_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_next_action_kind_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement
            != expected_unblocked_split_next_action_kinds_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_next_action_kinds_by_requirement "
                "must match unblocked split reviewed CSV path next action kinds"
            )
        expected_unblocked_split_blocker_reasons_by_requirement = (
            _split_task_ids_by_requirement_from_reviewed_paths(
                self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement,
                self.frontier_human_review_queue_split_blocked_source_reasons_by_reviewed_csv_path,
            )
        )
        if (
            "frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement"
            in self.model_fields_set
            and self.frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement
            != expected_unblocked_split_blocker_reasons_by_requirement
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_blocker_reasons_by_requirement "
                "must match unblocked split reviewed CSV path blocker reasons"
            )
        if (
            "frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement"
            in self.model_fields_set
            and not set(
                _nested_string_values(
                    self.frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement
                )
            ).issubset(split_reviewed_csv_path_set)
        ):
            raise ValueError(
                "frontier_unblocked_human_review_queue_split_reviewed_csv_paths_by_requirement "
                "must reference frontier_human_review_queue_split reviewed CSV paths"
            )
        return self


class EvidenceGroundingRoadmapCompletionAuditRequest(BaseModel):
    audit_id: str = "evidence-grounding-roadmap-completion-audit"
    scorecard_path: str | None = None
    comparison_suite_path: str | None = None
    baseline_benchmark_report_path: str | None = None
    candidate_benchmark_report_path: str | None = None
    comparison_report_path: str | None = None
    run_readiness_report_path: str | None = None
    threshold_calibration_report_path: str | None = None
    threshold_adoption_review_path: str | None = None
    threshold_adoption_package_path: str | None = None
    contract_readiness_report_path: str | None = None
    gold_release_package_path: str | None = None
    gold_release_readiness_report_path: str | None = None
    correction_log_path: str | None = Field(
        default=None,
        description=EVIDENCE_GROUNDING_CORRECTION_EVIDENCE_PATH_DESCRIPTION,
    )
    additional_artifact_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Additional non-canonical review/contract artifact paths to consider during completion audit, "
            "such as candidate_lineage_run_dir_map.json or "
            "evidence_grounding_candidate_lineage_patch_template.v1, including "
            "p0_overstatement_review_packet.json / evidence_grounding_p0_overstatement_review_packet.v1 "
            "or p0_overstatement_review_summary.json / evidence_grounding_p0_overstatement_review_summary.v1, "
            "active_review_readiness.json / evidence_grounding_active_review_readiness.v1, "
            "or active_reviewer_handoff_refresh.json / "
            "evidence_grounding_active_reviewer_handoff_refresh.v1."
        ),
    )
    goldset_root: str | None = None
    run_root: str | None = None
    required_ready_gold_count: int = Field(default=1, ge=1)
    required_ready_run_count: int = Field(default=1, ge=1)
    inventory_required_artifacts: list[str] | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.audit_id = self.audit_id.strip()
        if not self.audit_id:
            raise ValueError("audit_id is required")
        for field_name in (
            "scorecard_path",
            "comparison_suite_path",
            "baseline_benchmark_report_path",
            "candidate_benchmark_report_path",
            "comparison_report_path",
            "run_readiness_report_path",
            "threshold_calibration_report_path",
            "threshold_adoption_review_path",
            "threshold_adoption_package_path",
            "contract_readiness_report_path",
            "gold_release_package_path",
            "gold_release_readiness_report_path",
            "correction_log_path",
            "goldset_root",
            "run_root",
            "out",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if self.inventory_required_artifacts is not None:
            self.inventory_required_artifacts = _dedupe_non_empty_strings(
                self.inventory_required_artifacts,
                field_name="inventory_required_artifacts",
            )
        self.additional_artifact_paths = _dedupe_non_empty_strings(
            self.additional_artifact_paths,
            field_name="additional_artifact_paths",
        )
        return self


class EvidenceGroundingRoadmapCompletionAuditFromComparisonSuitePackageRequest(BaseModel):
    comparison_suite_path: str = Field(..., min_length=1)
    threshold_calibration_report_out: str = Field(..., min_length=1)
    threshold_checked_comparison_report_out: str = Field(..., min_length=1)
    threshold_adoption_review_out: str = Field(..., min_length=1)
    contract_compatibility_report_out: str = Field(..., min_length=1)
    contract_readiness_report_out: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    audit_id: str = "evidence-grounding-roadmap-completion-audit"
    calibration_id: str = "evidence-grounding-threshold-calibration"
    calibration_metric_names: list[str] | None = None
    calibration_metric_preset: EvidenceGroundingThresholdCalibrationPreset = "p0_gold"
    include_baseline_report: bool = False
    include_candidate_report: bool = True
    tolerance: float = Field(default=0.0, ge=0.0)
    gate_metric_names: list[str] | None = None
    gate_preset: Literal["all_comparable", "p0_gold"] = "p0_gold"
    threshold_metric_values: dict[str, float] | None = None
    adoption_id: str = "evidence-grounding-threshold-adoption-review"
    required_metric_names: list[str] | None = None
    threshold_reviewer_approval_reference: str | None = None
    allow_production_threshold_ready: bool = False
    compatibility_id: str = "evidence-grounding-contract-compatibility"
    readiness_id: str = "evidence-grounding-contract-readiness"
    include_embedded_scorecards: bool = True
    migration_plan_path: str | None = None
    backfill_plan_path: str | None = None
    public_contract_doc_path: str | None = None
    contract_reviewer_approval_reference: str | None = None
    allow_external_contract_ready: bool = False
    additional_artifact_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Additional review/contract artifacts to include in the generated contract compatibility report, "
            "such as claim_evidence_correction_repair_plan.json / claim_evidence_correction_repair_plan.v1, "
            "claim_evidence_correction_repair_patch_template.json / "
            "claim_evidence_correction_repair_patch_template.v1, "
            "p0_overstatement_review_packet.json / evidence_grounding_p0_overstatement_review_packet.v1, "
            "p0_overstatement_review_summary.json / evidence_grounding_p0_overstatement_review_summary.v1, "
            "active_review_readiness.json / evidence_grounding_active_review_readiness.v1, "
            "active_reviewer_handoff_refresh.json / evidence_grounding_active_reviewer_handoff_refresh.v1, "
            "scorecard_input_backfill.json / evidence_grounding_scorecard_input_backfill.v1, or "
            "claim_evidence_reviewed_eval_fixtures.json / claim_evidence_reviewed_eval_fixtures_bundle.v1."
        ),
    )
    gold_release_goldset_id: str | None = None
    gold_release_staged_split_manifests: list[PaperUnderstandingGoldReleaseManifestBuildItem] | None = None
    gold_release_split_plan_path: str | None = None
    gold_release_package_out: str | None = None
    gold_release_package_path: str | None = None
    gold_release_manifest_paths: list[str] | None = None
    gold_release_readiness_report_out: str | None = None
    gold_release_readiness_report_path: str | None = None
    gold_release_required_splits: list[str] | None = None
    gold_release_min_ready_per_split: int = Field(default=1, ge=1)
    gold_release_require_single_goldset_id: bool = True
    correction_log_path: str | None = Field(
        default=None,
        description=EVIDENCE_GROUNDING_CORRECTION_EVIDENCE_PATH_DESCRIPTION,
    )
    goldset_root: str | None = None
    run_root: str | None = None
    required_ready_gold_count: int = Field(default=1, ge=1)
    required_ready_run_count: int = Field(default=1, ge=1)
    inventory_required_artifacts: list[str] | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "comparison_suite_path",
            "threshold_calibration_report_out",
            "threshold_checked_comparison_report_out",
            "threshold_adoption_review_out",
            "contract_compatibility_report_out",
            "contract_readiness_report_out",
            "out",
            "audit_id",
            "calibration_id",
            "adoption_id",
            "compatibility_id",
            "readiness_id",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        if not self.include_baseline_report and not self.include_candidate_report:
            raise ValueError("at least one suite benchmark report must be selected for calibration")
        if self.calibration_metric_names is not None:
            self.calibration_metric_names = _dedupe_non_empty_strings(
                self.calibration_metric_names,
                field_name="calibration_metric_names",
            )
        if self.gate_metric_names is not None:
            self.gate_metric_names = _dedupe_non_empty_strings(
                self.gate_metric_names,
                field_name="gate_metric_names",
            )
        if self.required_metric_names is not None:
            self.required_metric_names = _dedupe_non_empty_strings(
                self.required_metric_names,
                field_name="required_metric_names",
            )
        if self.inventory_required_artifacts is not None:
            self.inventory_required_artifacts = _dedupe_non_empty_strings(
                self.inventory_required_artifacts,
                field_name="inventory_required_artifacts",
            )
        if self.gold_release_manifest_paths is not None:
            self.gold_release_manifest_paths = _dedupe_non_empty_strings(
                self.gold_release_manifest_paths,
                field_name="gold_release_manifest_paths",
            )
        if self.gold_release_required_splits is not None:
            self.gold_release_required_splits = _dedupe_non_empty_strings(
                self.gold_release_required_splits,
                field_name="gold_release_required_splits",
            )
        if self.threshold_metric_values is not None:
            self.threshold_metric_values = {
                str(name).strip(): float(value)
                for name, value in self.threshold_metric_values.items()
                if str(name).strip()
            }
        for field_name in (
            "threshold_reviewer_approval_reference",
            "migration_plan_path",
            "backfill_plan_path",
            "public_contract_doc_path",
            "contract_reviewer_approval_reference",
            "gold_release_goldset_id",
            "gold_release_split_plan_path",
            "gold_release_package_out",
            "gold_release_package_path",
            "gold_release_readiness_report_out",
            "gold_release_readiness_report_path",
            "correction_log_path",
            "goldset_root",
            "run_root",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if self.gold_release_manifest_paths and not self.gold_release_readiness_report_out:
            raise ValueError("gold_release_readiness_report_out is required when gold_release_manifest_paths are provided")
        if self.gold_release_staged_split_manifests:
            if not self.gold_release_goldset_id:
                raise ValueError("gold_release_goldset_id is required when gold_release_staged_split_manifests are provided")
            if not self.gold_release_package_out:
                raise ValueError("gold_release_package_out is required when gold_release_staged_split_manifests are provided")
            if not self.gold_release_readiness_report_out:
                raise ValueError(
                    "gold_release_readiness_report_out is required when gold_release_staged_split_manifests are provided"
                )
        if self.gold_release_split_plan_path:
            if not self.gold_release_goldset_id:
                raise ValueError("gold_release_goldset_id is required when gold_release_split_plan_path is provided")
            if not self.gold_release_package_out:
                raise ValueError("gold_release_package_out is required when gold_release_split_plan_path is provided")
            if not self.gold_release_readiness_report_out:
                raise ValueError(
                    "gold_release_readiness_report_out is required when gold_release_split_plan_path is provided"
                )
        return self


class EvidenceGroundingRoadmapCompletionAuditFromThresholdAdoptionPackageRequest(BaseModel):
    threshold_adoption_package_path: str = Field(..., min_length=1)
    contract_compatibility_report_out: str = Field(..., min_length=1)
    contract_readiness_report_out: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    representative_split: str | None = None
    audit_id: str = "evidence-grounding-roadmap-completion-audit"
    compatibility_id: str = "evidence-grounding-contract-compatibility"
    readiness_id: str = "evidence-grounding-contract-readiness"
    include_embedded_scorecards: bool = True
    migration_plan_path: str | None = None
    backfill_plan_path: str | None = None
    public_contract_doc_path: str | None = None
    contract_reviewer_approval_reference: str | None = None
    allow_external_contract_ready: bool = False
    additional_artifact_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Additional review/contract artifacts to include in the generated contract compatibility report, "
            "such as claim_evidence_correction_repair_plan.json / claim_evidence_correction_repair_plan.v1, "
            "claim_evidence_correction_repair_patch_template.json / "
            "claim_evidence_correction_repair_patch_template.v1, "
            "p0_overstatement_review_packet.json / evidence_grounding_p0_overstatement_review_packet.v1, "
            "p0_overstatement_review_summary.json / evidence_grounding_p0_overstatement_review_summary.v1, "
            "active_review_readiness.json / evidence_grounding_active_review_readiness.v1, "
            "active_reviewer_handoff_refresh.json / evidence_grounding_active_reviewer_handoff_refresh.v1, "
            "scorecard_input_backfill.json / evidence_grounding_scorecard_input_backfill.v1, or "
            "claim_evidence_reviewed_eval_fixtures.json / claim_evidence_reviewed_eval_fixtures_bundle.v1."
        ),
    )
    gold_release_goldset_id: str | None = None
    gold_release_staged_split_manifests: list[PaperUnderstandingGoldReleaseManifestBuildItem] | None = None
    gold_release_split_plan_path: str | None = None
    gold_release_package_out: str | None = None
    gold_release_package_path: str | None = None
    gold_release_manifest_paths: list[str] | None = None
    gold_release_readiness_report_out: str | None = None
    gold_release_readiness_report_path: str | None = None
    gold_release_required_splits: list[str] | None = None
    gold_release_min_ready_per_split: int = Field(default=1, ge=1)
    gold_release_require_single_goldset_id: bool = True
    correction_log_path: str | None = Field(
        default=None,
        description=EVIDENCE_GROUNDING_CORRECTION_EVIDENCE_PATH_DESCRIPTION,
    )
    goldset_root: str | None = None
    run_root: str | None = None
    required_ready_gold_count: int = Field(default=1, ge=1)
    required_ready_run_count: int = Field(default=1, ge=1)
    inventory_required_artifacts: list[str] | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        for field_name in (
            "threshold_adoption_package_path",
            "contract_compatibility_report_out",
            "contract_readiness_report_out",
            "out",
            "audit_id",
            "compatibility_id",
            "readiness_id",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        for field_name in (
            "representative_split",
            "migration_plan_path",
            "backfill_plan_path",
            "public_contract_doc_path",
            "contract_reviewer_approval_reference",
            "gold_release_goldset_id",
            "gold_release_split_plan_path",
            "gold_release_package_out",
            "gold_release_package_path",
            "gold_release_readiness_report_out",
            "gold_release_readiness_report_path",
            "correction_log_path",
            "goldset_root",
            "run_root",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if self.gold_release_manifest_paths is not None:
            self.gold_release_manifest_paths = _dedupe_non_empty_strings(
                self.gold_release_manifest_paths,
                field_name="gold_release_manifest_paths",
            )
        if self.gold_release_required_splits is not None:
            self.gold_release_required_splits = _dedupe_non_empty_strings(
                self.gold_release_required_splits,
                field_name="gold_release_required_splits",
            )
        if self.inventory_required_artifacts is not None:
            self.inventory_required_artifacts = _dedupe_non_empty_strings(
                self.inventory_required_artifacts,
                field_name="inventory_required_artifacts",
            )
        self.additional_artifact_paths = (
            _dedupe_non_empty_strings(
                self.additional_artifact_paths,
                field_name="additional_artifact_paths",
            )
            if self.additional_artifact_paths
            else []
        )
        if self.gold_release_manifest_paths and not self.gold_release_readiness_report_out:
            raise ValueError("gold_release_readiness_report_out is required when gold_release_manifest_paths are provided")
        if self.gold_release_staged_split_manifests:
            if not self.gold_release_goldset_id:
                raise ValueError("gold_release_goldset_id is required when gold_release_staged_split_manifests are provided")
            if not self.gold_release_package_out:
                raise ValueError("gold_release_package_out is required when gold_release_staged_split_manifests are provided")
            if not self.gold_release_readiness_report_out:
                raise ValueError(
                    "gold_release_readiness_report_out is required when gold_release_staged_split_manifests are provided"
                )
        if self.gold_release_split_plan_path:
            if not self.gold_release_goldset_id:
                raise ValueError("gold_release_goldset_id is required when gold_release_split_plan_path is provided")
            if not self.gold_release_package_out:
                raise ValueError("gold_release_package_out is required when gold_release_split_plan_path is provided")
            if not self.gold_release_readiness_report_out:
                raise ValueError(
                    "gold_release_readiness_report_out is required when gold_release_split_plan_path is provided"
                )
        return self


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


def _roadmap_command_hint_has_unresolved_placeholder(command_hint: str) -> bool:
    return bool(_UNRESOLVED_COMMAND_PLACEHOLDER_RE.search(command_hint))


def _roadmap_command_hint_unresolved_placeholders(command_hint: str) -> list[str]:
    placeholders: list[str] = []
    seen: set[str] = set()
    for match in _UNRESOLVED_COMMAND_PLACEHOLDER_RE.findall(command_hint):
        placeholder = match.strip()
        if not placeholder or placeholder in seen:
            continue
        seen.add(placeholder)
        placeholders.append(placeholder)
    return placeholders


def _roadmap_placeholder_resolution_class(placeholder: str) -> str:
    placeholder = placeholder.strip()
    if placeholder == "<repaired_or_replayable_claim_evidence_corrections.jsonl>":
        return "requires_repaired_or_replayable_claim_evidence_correction_log"
    if placeholder == "<comparison_suite_package_with_reviewed_fixtures.json>":
        return "requires_reviewed_fixture_comparison_suite_after_p0_review"
    if placeholder.startswith("<baseline_"):
        return "missing_baseline_candidate_config_in_current_baseline_manifest_package"
    if placeholder.startswith("<candidate_"):
        return "missing_candidate_config_or_reviewed_fixture_package"
    return "operator_supplied_placeholder"


def _roadmap_next_action_phase(requirement_id: str) -> str:
    if requirement_id in {"fixed_goldset_release_readiness", "workspace_evidence_inventory_ready"}:
        return "gold_curation_and_release"
    if requirement_id in {
        "fixed_goldset_candidate_run",
        "candidate_configuration_lineage",
        "per_run_and_aggregate_scorecards",
        "p0_metrics_reported",
        "p0_regression_gate",
        "stage_failure_attribution",
    }:
        return "fixed_goldset_run"
    if requirement_id == "structured_correction_log":
        return "correction_loop"
    if requirement_id == "production_threshold_adoption_reviewed":
        return "threshold_adoption"
    if requirement_id == "fixed_goldset_threshold_adoption_package_ready":
        return "threshold_package"
    if requirement_id == "external_contract_readiness_reviewed":
        return "contract_readiness"
    return "completion_evidence"


def _roadmap_next_action_requires_human_review(requirement_id: str, action: str) -> bool:
    normalized_action = action.lower()
    if requirement_id == "additive_noncanonical_artifacts":
        return False
    if "prefill the candidate lineage patch template" in normalized_action:
        return False
    if "prefill the claim/evidence correction repair patch template" in normalized_action:
        return False
    if (
        "fill the candidate lineage patch template" in normalized_action
        or "prefilled candidate lineage patch template" in normalized_action
        or "candidate lineage fill-task export" in normalized_action
        or "fix the candidate lineage reviewed fill-task csv" in normalized_action
    ):
        return True
    if "calibrate thresholds" in normalized_action or "re-run threshold calibration" in normalized_action:
        return False
    if "build a seed/eval/holdout comparison-suite package" in normalized_action:
        return False
    if "build a reviewed-fixture candidate benchmark manifest package" in normalized_action:
        return False
    if "build a reviewed-fixture candidate benchmark run package" in normalized_action:
        return False
    if "re-run the scorecard-aware fixed-goldset comparison suite package" in normalized_action:
        return False
    if "regenerate the seed/eval/holdout comparison-suite package" in normalized_action:
        return False
    if "rebuild the threshold-adoption package" in normalized_action:
        return False
    if "rebuild repaired baseline/candidate benchmark manifest packages" in normalized_action:
        return False
    if "build repaired baseline/candidate benchmark run packages" in normalized_action:
        return False
    if "export a candidate lineage run-dir map" in normalized_action:
        return False
    if "export a candidate lineage patch template" in normalized_action:
        return False
    if "apply the filled candidate lineage patch template" in normalized_action:
        return False
    if "resolve blocked threshold-adoption package splits" in normalized_action:
        return False
    if "repair or regenerate failing threshold-package scorecard source run sidecars" in normalized_action:
        return False
    if "repair or regenerate failing external-contract scorecard source run sidecars" in normalized_action:
        return False
    if "regenerate external-contract scorecard input backfill artifacts" in normalized_action:
        return False
    if "re-run scorecard input backfill for blocked threshold-adoption package splits" in normalized_action:
        return False
    if "create or identify run directories" in normalized_action:
        return False
    if "repair or regenerate failing scorecard source run sidecars" in normalized_action:
        return False
    if "build a ready seed/eval/holdout gold release package" in normalized_action:
        return False
    if "run the gold release-readiness audit" in normalized_action:
        return False
    if "repair failing required evidence-grounding artifacts" in normalized_action:
        return False
    if "re-run scorecard input backfill" in normalized_action:
        return False
    if "attach reviewed claim/evidence fixtures" in normalized_action:
        return False
    if "import replayable claim/evidence eval candidates into the reviewed-fixture intake queue" in normalized_action:
        return False
    if "list imported claim/evidence eval candidates in the reviewed-fixture intake queue" in normalized_action:
        return False
    if "export a claim/evidence correction repair plan" in normalized_action:
        return False
    if "export a claim/evidence correction repair patch template" in normalized_action:
        return False
    if "draft a repaired claim/evidence correction jsonl" in normalized_action:
        return False
    if "export replayable claim/evidence eval candidates" in normalized_action:
        return False
    if "run contract compatibility over" in normalized_action:
        return False
    if requirement_id == "structured_correction_log":
        return (
            normalized_action.startswith("fill the claim/evidence correction repair patch template")
            or normalized_action.startswith(
                "review and complete the prefilled claim/evidence correction repair patch template"
            )
            or normalized_action.startswith("review the claim/evidence correction repair fill-task export")
            or normalized_action.startswith("fix the claim/evidence correction repair reviewed fill-task csv")
            or normalized_action.startswith("repair the listed")
            or normalized_action.startswith("repair or re-export")
            or normalized_action.startswith("repair the source")
            or normalized_action.startswith("add at least one accepted")
            or normalized_action.startswith("use the claim/evidence correction repair plan")
        )
    if requirement_id in {
        "fixed_goldset_release_readiness",
        "workspace_evidence_inventory_ready",
        "production_threshold_adoption_reviewed",
        "fixed_goldset_threshold_adoption_package_ready",
        "external_contract_readiness_reviewed",
    }:
        return True
    return "approval" in normalized_action or "curate" in normalized_action or "review" in normalized_action


def _roadmap_frontier_next_action_kind(action: EvidenceGroundingRoadmapCompletionNextAction) -> str:
    command_hint = (action.command_hint or "").strip()
    if action.requires_human_review:
        return "human_review_with_command" if command_hint else "human_review_without_command"
    if not command_hint:
        return "nonhuman_without_command"
    if _roadmap_command_hint_has_unresolved_placeholder(command_hint):
        return "placeholder_command"
    return "ready_to_run_command"


def _roadmap_next_action_blocked_by_requirement_ids(
    *,
    requirement_id: str,
    action_text: str,
    failed_requirement_ids: set[str],
) -> list[str]:
    blocked_by: list[str] = []
    if (
        "candidate_configuration_lineage" in failed_requirement_ids
        and requirement_id
        in {
            "fixed_goldset_candidate_run",
            "per_run_and_aggregate_scorecards",
            "p0_metrics_reported",
            "p0_regression_gate",
            "stage_failure_attribution",
        }
        and (
            "baseline and candidate benchmarks" in action_text
            or "comparison_suite_path or the linked baseline benchmark" in action_text
            or "Regenerate benchmark reports" in action_text
            or "Resolve any embedded scorecard readiness failures" in action_text
            or "Attach ready paper_understanding_gold.v1 labels" in action_text
            or "Run the scorecard comparison" in action_text
            or "Regenerate the candidate benchmark" in action_text
        )
    ):
        blocked_by.append("candidate_configuration_lineage")
    if (
        requirement_id == "fixed_goldset_threshold_adoption_package_ready"
        and "fixed_goldset_candidate_run" in failed_requirement_ids
        and "Build a seed/eval/holdout comparison-suite package" in action_text
    ):
        blocked_by.append("fixed_goldset_candidate_run")
    if (
        requirement_id == "external_contract_readiness_reviewed"
        and "Run contract compatibility over the required evidence-grounding artifacts" in action_text
    ):
        if (
            "evidence_grounding_benchmark.v1" in action_text
            and "per_run_and_aggregate_scorecards" in failed_requirement_ids
        ):
            blocked_by.append("per_run_and_aggregate_scorecards")
        if (
            (
                "evidence_grounding_fixed_goldset_comparison_suite.v1" in action_text
                or "evidence_grounding_fixed_goldset_run_readiness.v1" in action_text
            )
            and "fixed_goldset_candidate_run" in failed_requirement_ids
        ):
            blocked_by.append("fixed_goldset_candidate_run")
        if (
            "evidence_grounding_scorecard_comparison.v1" in action_text
            and "p0_regression_gate" in failed_requirement_ids
        ):
            blocked_by.append("p0_regression_gate")
        if (
            (
                "evidence_grounding_threshold_adoption_review.v1" in action_text
                or "evidence_grounding_threshold_calibration.v1" in action_text
            )
            and "production_threshold_adoption_reviewed" in failed_requirement_ids
        ):
            blocked_by.append("production_threshold_adoption_reviewed")
    if (
        requirement_id
        in {
            "p0_metrics_reported",
            "production_threshold_adoption_reviewed",
            "fixed_goldset_threshold_adoption_package_ready",
        }
        and "Export replayable claim/evidence eval candidates from repaired or replayable claim/evidence corrections before intake import"
        in action_text
        and "structured_correction_log" in failed_requirement_ids
    ):
        blocked_by.append("structured_correction_log")
    if (
        requirement_id
        in {
            "p0_metrics_reported",
            "production_threshold_adoption_reviewed",
            "fixed_goldset_threshold_adoption_package_ready",
        }
        and (
            "Build a reviewed-fixture candidate benchmark manifest package" in action_text
            or "Rebuild repaired baseline/candidate benchmark manifest packages" in action_text
        )
        and "candidate_configuration_lineage" in failed_requirement_ids
    ):
        blocked_by.append("candidate_configuration_lineage")
    if (
        requirement_id == "production_threshold_adoption_reviewed"
        and "Resolve missing P0 threshold metric inputs before production-threshold adoption" in action_text
        and "p0_metrics_reported" in failed_requirement_ids
    ):
        blocked_by.append("p0_metrics_reported")
    if (
        requirement_id == "external_contract_readiness_reviewed"
        and "Repair failing audited evidence-grounding artifacts before external contract readiness review"
        in action_text
        and "claim_evidence_eval_candidate_export.v1" in action_text
        and "structured_correction_log" in failed_requirement_ids
    ):
        blocked_by.append("structured_correction_log")
    return blocked_by


def _roadmap_frontier_blocked_by_requirement_ids(
    *,
    requirement_id: str,
    action_text: str,
    failed_requirement_ids: set[str],
) -> list[str]:
    return _roadmap_next_action_blocked_by_requirement_ids(
        requirement_id=requirement_id,
        action_text=action_text,
        failed_requirement_ids=failed_requirement_ids,
    )


def _roadmap_merge_requirement_id_lists(*values: list[str]) -> list[str]:
    merged: list[str] = []
    for raw_values in values:
        for raw_value in raw_values:
            value = raw_value.strip()
            if value and value not in merged:
                merged.append(value)
    return merged


def _roadmap_frontier_blocker_reasons(
    *,
    kind: str,
    requires_human_review: bool,
    has_command_hint: bool,
    unresolved_command_placeholders: list[str],
    missing_metric_inputs: list[str],
    human_review_open_task_ids: list[str],
    blocked_by_requirement_ids: list[str],
) -> list[str]:
    reasons: list[str] = []
    if blocked_by_requirement_ids:
        reasons.append("blocked_by_requirement")
    if requires_human_review:
        reasons.append("human_review_required")
    if human_review_open_task_ids:
        reasons.append("human_review_open_tasks")
    if missing_metric_inputs:
        reasons.append("missing_metric_inputs")
    if unresolved_command_placeholders:
        reasons.append("unresolved_command_placeholders")
    if kind == "nonhuman_without_command" or (
        not has_command_hint and not requires_human_review
    ):
        reasons.append("missing_command_hint")
    return reasons


def _roadmap_next_action_blocker_reasons(
    *,
    kind: str,
    requires_human_review: bool,
    has_command_hint: bool,
    has_prior_prerequisite: bool,
    unresolved_command_placeholders: list[str],
    missing_metric_inputs: list[str],
    human_review_open_task_ids: list[str],
    blocked_by_requirement_ids: list[str],
) -> list[str]:
    reasons: list[str] = []
    if blocked_by_requirement_ids:
        reasons.append("blocked_by_requirement")
    if has_prior_prerequisite:
        reasons.append("prerequisite_gated")
    if requires_human_review:
        reasons.append("human_review_required")
    if human_review_open_task_ids:
        reasons.append("human_review_open_tasks")
    if missing_metric_inputs:
        reasons.append("missing_metric_inputs")
    if unresolved_command_placeholders:
        reasons.append("unresolved_command_placeholders")
    if kind == "nonhuman_without_command" or (
        not has_command_hint and not requires_human_review
    ):
        reasons.append("missing_command_hint")
    return reasons


def _roadmap_frontier_next_action_summaries(
    actions: list[EvidenceGroundingRoadmapCompletionNextAction],
    failed_requirement_ids: set[str],
    open_csv_paths_by_requirement: dict[str, list[str]],
    open_csv_row_counts_by_requirement: dict[str, int],
    missing_metric_inputs_by_requirement: dict[str, list[str]],
    missing_value_counts_by_field_by_requirement: dict[str, dict[str, int]],
    missing_suggestion_counts_by_field_by_requirement: dict[str, dict[str, int]],
    available_context_counts_by_field_by_requirement: dict[str, dict[str, int]],
    missing_context_counts_by_field_by_requirement: dict[str, dict[str, int]],
    missing_context_task_ids_by_field_by_requirement: dict[str, dict[str, list[str]]],
    available_context_keys_by_field_by_requirement: dict[str, dict[str, list[str]]],
    available_context_values_by_field_by_requirement: dict[str, dict[str, list[str]]],
    open_task_ids_by_requirement: dict[str, list[str]],
    open_task_ids_by_field_by_requirement: dict[str, dict[str, list[str]]],
) -> list[
    tuple[
        str,
        str,
        str,
        bool,
        bool,
        bool,
        list[str],
        list[str],
        list[str],
        int,
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, int],
        dict[str, list[str]],
        dict[str, list[str]],
        dict[str, list[str]],
        list[str],
        dict[str, list[str]],
        str,
        str,
        list[str],
        list[str],
    ]
]:
    summaries: list[
        tuple[
            str,
            str,
            str,
            bool,
            bool,
            bool,
            list[str],
            list[str],
            list[str],
            int,
            dict[str, int],
            dict[str, int],
            dict[str, int],
            dict[str, int],
            dict[str, list[str]],
            dict[str, list[str]],
            dict[str, list[str]],
            list[str],
            dict[str, list[str]],
            str,
            str,
            list[str],
            list[str],
        ]
    ] = []
    for action in actions:
        requirement_id = action.requirement_id.strip()
        if not requirement_id:
            continue
        command_hint = (action.command_hint or "").strip()
        kind = _roadmap_frontier_next_action_kind(action)
        unresolved_placeholders = _roadmap_command_hint_unresolved_placeholders(command_hint)
        missing_metric_inputs = list(
            missing_metric_inputs_by_requirement.get(requirement_id, [])
        )
        open_task_ids = list(open_task_ids_by_requirement.get(requirement_id, []))
        action_text = action.action.strip()
        blocked_by_requirement_ids = _roadmap_frontier_blocked_by_requirement_ids(
            requirement_id=requirement_id,
            action_text=action_text,
            failed_requirement_ids=failed_requirement_ids,
        )
        summaries.append(
            (
                requirement_id,
                (action.phase or "").strip(),
                kind,
                action.requires_human_review,
                bool(command_hint),
                _roadmap_command_hint_has_unresolved_placeholder(command_hint),
                unresolved_placeholders,
                missing_metric_inputs,
                list(open_csv_paths_by_requirement.get(requirement_id, [])),
                open_csv_row_counts_by_requirement.get(requirement_id, 0),
                dict(missing_value_counts_by_field_by_requirement.get(requirement_id, {})),
                dict(missing_suggestion_counts_by_field_by_requirement.get(requirement_id, {})),
                dict(available_context_counts_by_field_by_requirement.get(requirement_id, {})),
                dict(missing_context_counts_by_field_by_requirement.get(requirement_id, {})),
                dict(missing_context_task_ids_by_field_by_requirement.get(requirement_id, {})),
                dict(available_context_keys_by_field_by_requirement.get(requirement_id, {})),
                dict(available_context_values_by_field_by_requirement.get(requirement_id, {})),
                open_task_ids,
                dict(open_task_ids_by_field_by_requirement.get(requirement_id, {})),
                action_text,
                command_hint,
                _roadmap_frontier_blocker_reasons(
                    kind=kind,
                    requires_human_review=action.requires_human_review,
                    has_command_hint=bool(command_hint),
                    unresolved_command_placeholders=unresolved_placeholders,
                    missing_metric_inputs=missing_metric_inputs,
                    human_review_open_task_ids=open_task_ids,
                    blocked_by_requirement_ids=blocked_by_requirement_ids,
                ),
                blocked_by_requirement_ids,
            )
        )
    return summaries


def _roadmap_missing_metric_inputs_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, list[str]]:
    metrics_by_requirement: dict[str, list[str]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        seen: set[str] = set()
        metrics: list[str] = []
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            key = key.strip()
            if key not in {
                "missing_p0_metrics",
                "missing_p0_calibration_metrics",
                "missing_p0_adoption_metrics",
            }:
                continue
            for raw_metric in raw_value.split(","):
                metric = raw_metric.strip()
                if not metric or metric == "-" or metric in seen:
                    continue
                seen.add(metric)
                metrics.append(metric)
        if metrics:
            metrics_by_requirement[requirement_id] = metrics
    return metrics_by_requirement


def _roadmap_human_review_missing_value_counts_by_field_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, dict[str, int]]:
    return _roadmap_human_review_count_map_by_requirement(
        checks,
        "_fill_review_status_missing_value_count_by_field",
    )


def _roadmap_human_review_count_map_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
    evidence_key_suffix: str,
) -> dict[str, dict[str, int]]:
    counts_by_requirement: dict[str, dict[str, int]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        counts: dict[str, int] = {}
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith(evidence_key_suffix):
                continue
            for raw_pair in raw_value.split(","):
                if ":" not in raw_pair:
                    continue
                raw_field, raw_count = raw_pair.split(":", 1)
                field = raw_field.strip()
                if not field:
                    continue
                try:
                    count = int(raw_count.strip())
                except ValueError:
                    continue
                if count < 0:
                    continue
                counts[field] = counts.get(field, 0) + count
        if counts:
            counts_by_requirement[requirement_id] = counts
    return counts_by_requirement


def _sum_nested_count_map(counts_by_requirement: dict[str, dict[str, int]]) -> dict[str, int]:
    counts_by_field: dict[str, int] = {}
    for counts in counts_by_requirement.values():
        for field_name, count in counts.items():
            field = field_name.strip()
            if not field:
                continue
            counts_by_field[field] = counts_by_field.get(field, 0) + count
    return dict(sorted(counts_by_field.items()))


def _positive_count_difference_by_requirement(
    minuend_by_requirement: dict[str, dict[str, int]],
    subtrahend_by_requirement: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    values_by_requirement: dict[str, dict[str, int]] = {}
    requirement_ids = set(minuend_by_requirement) | set(subtrahend_by_requirement)
    for requirement_id in sorted(requirement_ids):
        fields = set(minuend_by_requirement.get(requirement_id, {})) | set(
            subtrahend_by_requirement.get(requirement_id, {})
        )
        values: dict[str, int] = {}
        for field_name in sorted(fields):
            value = (
                minuend_by_requirement.get(requirement_id, {}).get(field_name, 0)
                - subtrahend_by_requirement.get(requirement_id, {}).get(field_name, 0)
            )
            if value > 0:
                values[field_name] = value
        if values:
            values_by_requirement[requirement_id] = values
    return values_by_requirement


def _roadmap_human_review_string_list_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
    evidence_key_suffix: str,
) -> dict[str, list[str]]:
    values_by_requirement: dict[str, list[str]] = {}
    seen_by_requirement: dict[str, set[str]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith(evidence_key_suffix):
                continue
            for raw_value_item in raw_value.split(","):
                value = raw_value_item.strip()
                if not value or value == "-":
                    continue
                if value in seen_by_requirement.setdefault(requirement_id, set()):
                    continue
                seen_by_requirement[requirement_id].add(value)
                values_by_requirement.setdefault(requirement_id, []).append(value)
    return {
        requirement_id: values
        for requirement_id, values in sorted(values_by_requirement.items())
        if values
    }


def _roadmap_human_review_string_list_map_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
    evidence_key_suffix: str,
) -> dict[str, dict[str, list[str]]]:
    values_by_requirement: dict[str, dict[str, set[str]]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith(evidence_key_suffix):
                continue
            for raw_pair in raw_value.split(","):
                if ":" not in raw_pair:
                    continue
                raw_field, raw_values = raw_pair.split(":", 1)
                field = raw_field.strip()
                if not field:
                    continue
                for raw_value_item in raw_values.split("|"):
                    value = raw_value_item.strip()
                    if not value:
                        continue
                    values_by_requirement.setdefault(requirement_id, {}).setdefault(
                        field,
                        set(),
                    ).add(value)
    return {
        requirement_id: {
            field_name: sorted(values)
            for field_name, values in sorted(values_by_field.items())
            if values
        }
        for requirement_id, values_by_field in sorted(values_by_requirement.items())
        if values_by_field
    }


def _roadmap_human_review_record_field_list_map_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
    evidence_key_suffix: str,
) -> dict[str, dict[str, list[str]]]:
    values_by_requirement: dict[str, dict[str, set[str]]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith(evidence_key_suffix):
                continue
            for raw_pair in raw_value.split(","):
                if ":" not in raw_pair:
                    continue
                raw_record_ref, raw_fields = raw_pair.rsplit(":", 1)
                record_ref = raw_record_ref.strip()
                if not record_ref:
                    continue
                for raw_field in raw_fields.split("|"):
                    field_name = raw_field.strip()
                    if field_name:
                        values_by_requirement.setdefault(requirement_id, {}).setdefault(
                            record_ref,
                            set(),
                        ).add(field_name)
    return {
        requirement_id: {
            record_ref: sorted(field_names)
            for record_ref, field_names in sorted(values_by_record.items())
            if field_names
        }
        for requirement_id, values_by_record in sorted(values_by_requirement.items())
        if values_by_record
    }


def _merge_nested_string_list_map(
    values_by_requirement: dict[str, dict[str, list[str]]],
) -> dict[str, list[str]]:
    values_by_field: dict[str, set[str]] = {}
    for requirement_values in values_by_requirement.values():
        for field_name, values in requirement_values.items():
            field = field_name.strip()
            if not field:
                continue
            for raw_value in values:
                value = raw_value.strip()
                if value:
                    values_by_field.setdefault(field, set()).add(value)
    return {
        field_name: sorted(values)
        for field_name, values in sorted(values_by_field.items())
        if values
    }


def _roadmap_human_review_open_csv_paths(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for check in checks:
        if check.status != "fail":
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            value = raw_value.strip()
            if (
                key.strip().endswith("_fill_review_status_open_csv_path")
                and value
                and value != "-"
                and value not in seen
            ):
                seen.add(value)
                paths.append(value)
    return paths


def _roadmap_human_review_open_csv_row_count(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> int:
    total = 0
    for check in checks:
        if check.status != "fail":
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith("_fill_review_status_open_csv_row_count"):
                continue
            try:
                total += int(raw_value.strip())
            except ValueError:
                continue
    return total


def _roadmap_human_review_open_record_counts_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, int]:
    counts_by_requirement: dict[str, int] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith("_fill_review_status_open_record_count"):
                continue
            try:
                count = int(raw_value.strip())
            except ValueError:
                continue
            if count < 0:
                continue
            counts_by_requirement[requirement_id] = (
                counts_by_requirement.get(requirement_id, 0) + count
            )
    return dict(sorted(counts_by_requirement.items()))


def _roadmap_human_review_open_record_csv_paths(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for check in checks:
        if check.status != "fail":
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            value = raw_value.strip()
            if (
                key.strip().endswith("_fill_review_status_open_record_csv_path")
                and value
                and value != "-"
                and value not in seen
            ):
                seen.add(value)
                paths.append(value)
    return paths


def _roadmap_human_review_open_csv_paths_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, list[str]]:
    paths_by_requirement: dict[str, list[str]] = {}
    seen_by_requirement: dict[str, set[str]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            value = raw_value.strip()
            if (
                key.strip().endswith("_fill_review_status_open_csv_path")
                and value
                and value != "-"
                and value not in seen_by_requirement.setdefault(requirement_id, set())
            ):
                seen_by_requirement[requirement_id].add(value)
                paths_by_requirement.setdefault(requirement_id, []).append(value)
    return paths_by_requirement


def _roadmap_human_review_open_record_csv_paths_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, list[str]]:
    paths_by_requirement: dict[str, list[str]] = {}
    seen_by_requirement: dict[str, set[str]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            value = raw_value.strip()
            if (
                key.strip().endswith("_fill_review_status_open_record_csv_path")
                and value
                and value != "-"
                and value not in seen_by_requirement.setdefault(requirement_id, set())
            ):
                seen_by_requirement[requirement_id].add(value)
                paths_by_requirement.setdefault(requirement_id, []).append(value)
    return paths_by_requirement


def _roadmap_human_review_record_field_names_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, dict[str, list[str]]]:
    values_by_requirement: dict[str, dict[str, set[str]]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith(
                "_fill_review_status_open_field_names_by_record_ref"
            ):
                continue
            for raw_pair in raw_value.split(","):
                if ":" not in raw_pair:
                    continue
                raw_record_ref, raw_fields = raw_pair.rsplit(":", 1)
                record_ref = raw_record_ref.strip()
                if not record_ref:
                    continue
                for raw_field in raw_fields.split("|"):
                    field_name = raw_field.strip()
                    if not field_name:
                        continue
                    values_by_requirement.setdefault(requirement_id, {}).setdefault(
                        record_ref,
                        set(),
                    ).add(field_name)
    return {
        requirement_id: {
            record_ref: sorted(field_names)
            for record_ref, field_names in sorted(values_by_record.items())
            if field_names
        }
        for requirement_id, values_by_record in sorted(values_by_requirement.items())
        if values_by_record
    }


def _roadmap_human_review_open_field_names_by_requirement(
    values_by_record_ref_by_requirement: dict[str, dict[str, list[str]]],
) -> dict[str, list[str]]:
    values_by_requirement: dict[str, set[str]] = {}
    for requirement_id, values_by_record in values_by_record_ref_by_requirement.items():
        requirement = requirement_id.strip()
        if not requirement:
            continue
        for field_names in values_by_record.values():
            for raw_field in field_names:
                field = raw_field.strip()
                if field:
                    values_by_requirement.setdefault(requirement, set()).add(field)
    return {
        requirement_id: sorted(field_names)
        for requirement_id, field_names in sorted(values_by_requirement.items())
        if field_names
    }


def _roadmap_human_review_record_task_ids_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, dict[str, list[str]]]:
    record_refs_by_requirement = _roadmap_human_review_string_list_by_requirement(
        checks,
        "_fill_review_status_open_record_refs",
    )
    values_by_requirement: dict[str, dict[str, set[str]]] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        record_refs = sorted(
            record_refs_by_requirement.get(requirement_id, []),
            key=len,
            reverse=True,
        )
        if not record_refs:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith(
                "_fill_review_status_open_task_ids_by_record_ref"
            ):
                continue
            for raw_pair in raw_value.split(","):
                pair = raw_pair.strip()
                if not pair:
                    continue
                matched_record_ref = next(
                    (
                        record_ref
                        for record_ref in record_refs
                        if pair.startswith(f"{record_ref}:")
                    ),
                    None,
                )
                if matched_record_ref is None:
                    continue
                raw_task_ids = pair[len(matched_record_ref) + 1 :]
                for raw_task_id in raw_task_ids.split("|"):
                    task_id = raw_task_id.strip()
                    if not task_id:
                        continue
                    values_by_requirement.setdefault(requirement_id, {}).setdefault(
                        matched_record_ref,
                        set(),
                    ).add(task_id)
    return {
        requirement_id: {
            record_ref: sorted(task_ids)
            for record_ref, task_ids in sorted(values_by_record.items())
            if task_ids
        }
        for requirement_id, values_by_record in sorted(values_by_requirement.items())
        if values_by_record
    }


def _roadmap_human_review_open_csv_row_counts_by_requirement(
    checks: list[EvidenceGroundingRoadmapCompletionCheck],
) -> dict[str, int]:
    counts_by_requirement: dict[str, int] = {}
    for check in checks:
        if check.status != "fail":
            continue
        requirement_id = check.requirement_id.strip()
        if not requirement_id:
            continue
        for raw_item in check.evidence:
            if "=" not in raw_item:
                continue
            key, raw_value = raw_item.split("=", 1)
            if not key.strip().endswith("_fill_review_status_open_csv_row_count"):
                continue
            try:
                row_count = int(raw_value.strip())
            except ValueError:
                continue
            counts_by_requirement[requirement_id] = counts_by_requirement.get(requirement_id, 0) + row_count
    return counts_by_requirement


def _validate_failure_code(raw: str, *, field_name: str) -> EvidenceGroundingFailureCode:
    code = str(raw or "").strip()
    if not code:
        raise ValueError(f"{field_name} entries must be non-empty")
    if code not in KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES:
        raise ValueError(f"unknown evidence grounding failure code: {code}")
    return code  # type: ignore[return-value]
