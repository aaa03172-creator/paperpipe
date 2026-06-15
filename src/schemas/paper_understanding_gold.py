from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.paper_understanding_failures import PaperUnderstandingFailureCode


PaperUnderstandingGoldSchemaVersion = Literal["paper_understanding_gold.v1"]
PaperUnderstandingGoldManifestSchemaVersion = Literal["paper_understanding_gold_manifest.v1"]
PaperUnderstandingGoldValidationSchemaVersion = Literal["paper_understanding_gold_validation.v1"]
PaperUnderstandingGoldReadinessSchemaVersion = Literal["paper_understanding_gold_readiness.v1"]
PaperUnderstandingGoldCurationReportSchemaVersion = Literal["paper_understanding_gold_curation_report.v1"]
PaperUnderstandingGoldCandidateDraftSchemaVersion = Literal["paper_understanding_gold_candidate_draft.v1"]
PaperUnderstandingGoldCandidateDraftPatchResultSchemaVersion = Literal[
    "paper_understanding_gold_candidate_draft_patch_result.v1"
]
PaperUnderstandingGoldCandidateDraftPatchTemplateSchemaVersion = Literal[
    "paper_understanding_gold_candidate_draft_patch_template.v1"
]
PaperUnderstandingGoldCandidateDraftPatchTemplateManifestSchemaVersion = Literal[
    "paper_understanding_gold_candidate_draft_patch_template_manifest.v1"
]
PaperUnderstandingGoldCandidateDraftPatchResultManifestSchemaVersion = Literal[
    "paper_understanding_gold_candidate_draft_patch_result_manifest.v1"
]
PaperUnderstandingGoldCandidateDraftManifestSchemaVersion = Literal[
    "paper_understanding_gold_candidate_draft_manifest.v1"
]
PaperUnderstandingGoldCandidateDraftCurationReportSchemaVersion = Literal[
    "paper_understanding_gold_candidate_draft_curation_report.v1"
]
PaperUnderstandingGoldCandidateDraftCurationProgressSchemaVersion = Literal[
    "paper_understanding_gold_candidate_draft_curation_progress.v1"
]
PaperUnderstandingGoldCurationTaskExportSchemaVersion = Literal[
    "paper_understanding_gold_curation_task_export.v1"
]
PaperUnderstandingGoldTeacherVerificationCurationPackageSchemaVersion = Literal[
    "paper_understanding_gold_teacher_verification_curation_package.v1"
]
PaperUnderstandingGoldReviewerHandoffPackageSchemaVersion = Literal[
    "paper_understanding_gold_reviewer_handoff_package.v1"
]
PaperUnderstandingGoldReviewerHandoffApplyPackageSchemaVersion = Literal[
    "paper_understanding_gold_reviewer_handoff_apply_package.v1"
]
PaperUnderstandingGoldReviewerHandoffStagePackageSchemaVersion = Literal[
    "paper_understanding_gold_reviewer_handoff_stage_package.v1"
]
PaperUnderstandingGoldReviewerHandoffReleasePrepPackageSchemaVersion = Literal[
    "paper_understanding_gold_reviewer_handoff_release_prep_package.v1"
]
PaperUnderstandingGoldStagingManifestSchemaVersion = Literal["paper_understanding_gold_staging_manifest.v1"]
PaperUnderstandingGoldReleaseReadinessSchemaVersion = Literal[
    "paper_understanding_gold_release_readiness.v1"
]
PaperUnderstandingGoldReleaseSplitPlanSchemaVersion = Literal[
    "paper_understanding_gold_release_split_plan.v1"
]
PaperUnderstandingGoldReadinessStatus = Literal["pass", "warn", "fail"]
PaperUnderstandingGoldCandidateDraftCurationProgressStatus = Literal[
    "not_started",
    "templated",
    "patched_not_ready",
    "ready_to_stage",
    "staged",
]
PaperUnderstandingStatementKind = Literal["claim", "method", "result", "limitation", "gap"]
PaperUnderstandingPaperType = Literal[
    "primary_research",
    "review",
    "systematic_review",
    "meta_analysis",
    "methods",
    "case_report",
    "guideline",
    "other",
]


class PaperUnderstandingGoldEvidenceLocator(BaseModel):
    page: int | None = Field(default=None, ge=0)
    chunk_id: str | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    quote: str = Field(..., min_length=1)
    section: str | None = None
    figure_id: str | None = None
    table_id: str | None = None
    cell_id: str | None = None
    bbox_pdf: list[float] | None = None
    bbox_pct: dict[str, float] | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_locator(self):
        self.quote = self.quote.strip()
        if self.chunk_id is not None:
            self.chunk_id = self.chunk_id.strip() or None
        if self.section is not None:
            self.section = self.section.strip() or None
        if self.figure_id is not None:
            self.figure_id = self.figure_id.strip() or None
        if self.table_id is not None:
            self.table_id = self.table_id.strip() or None
        if self.cell_id is not None:
            self.cell_id = self.cell_id.strip() or None
        if self.note is not None:
            self.note = self.note.strip() or None
        if self.char_start is not None and self.char_end is not None and self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        if not any(
            value is not None
            for value in (
                self.page,
                self.chunk_id,
                self.char_start,
                self.figure_id,
                self.table_id,
                self.bbox_pdf,
                self.bbox_pct,
            )
        ):
            raise ValueError("evidence locator requires at least one page, chunk, span, figure, table, or bbox signal")
        return self


class PaperUnderstandingGoldStatement(BaseModel):
    statement_id: str = Field(..., min_length=1)
    kind: PaperUnderstandingStatementKind
    text: str = Field(..., min_length=1)
    evidence_refs: list[PaperUnderstandingGoldEvidenceLocator] = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    review_failure_codes: list[PaperUnderstandingFailureCode] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.statement_id = self.statement_id.strip()
        self.text = self.text.strip()
        self.tags = _dedupe_non_empty_strings(self.tags, field_name="tags")
        self.review_failure_codes = list(dict.fromkeys(self.review_failure_codes))
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class PaperUnderstandingGoldFigure(BaseModel):
    figure_id: str = Field(..., min_length=1)
    label: str | None = None
    page: int | None = Field(default=None, ge=0)
    caption: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.figure_id = self.figure_id.strip()
        if self.label is not None:
            self.label = self.label.strip() or None
        if self.caption is not None:
            self.caption = self.caption.strip() or None
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class PaperUnderstandingGoldTable(BaseModel):
    table_id: str = Field(..., min_length=1)
    label: str | None = None
    page: int | None = Field(default=None, ge=0)
    caption: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_values(self):
        self.table_id = self.table_id.strip()
        if self.label is not None:
            self.label = self.label.strip() or None
        if self.caption is not None:
            self.caption = self.caption.strip() or None
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class PaperUnderstandingGoldMetadata(BaseModel):
    doi: str | None = None
    pmid: str | None = None
    title: str = Field(..., min_length=1)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1600, le=3000)

    @model_validator(mode="after")
    def normalize_values(self):
        if self.doi is not None:
            self.doi = self.doi.strip() or None
        if self.pmid is not None:
            self.pmid = self.pmid.strip() or None
        self.title = self.title.strip()
        self.authors = _dedupe_non_empty_strings(self.authors, field_name="authors")
        return self


class PaperUnderstandingGold(BaseModel):
    schema_version: PaperUnderstandingGoldSchemaVersion = "paper_understanding_gold.v1"
    generated_at: datetime | None = None
    paper_id: str = Field(..., min_length=1)
    citation: PaperUnderstandingGoldMetadata
    paper_type: PaperUnderstandingPaperType = "other"
    domain_tags: list[str] = Field(default_factory=list)
    gold_claims: list[PaperUnderstandingGoldStatement] = Field(default_factory=list)
    gold_methods: list[PaperUnderstandingGoldStatement] = Field(default_factory=list)
    gold_results: list[PaperUnderstandingGoldStatement] = Field(default_factory=list)
    gold_limitations: list[PaperUnderstandingGoldStatement] = Field(default_factory=list)
    gold_gaps: list[PaperUnderstandingGoldStatement] = Field(default_factory=list)
    important_figures: list[PaperUnderstandingGoldFigure] = Field(default_factory=list)
    important_tables: list[PaperUnderstandingGoldTable] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_gold_record(self):
        self.paper_id = self.paper_id.strip()
        self.domain_tags = _dedupe_non_empty_strings(self.domain_tags, field_name="domain_tags")
        if self.notes is not None:
            self.notes = self.notes.strip() or None

        _validate_statement_kinds(self.gold_claims, expected="claim", field_name="gold_claims")
        _validate_statement_kinds(self.gold_methods, expected="method", field_name="gold_methods")
        _validate_statement_kinds(self.gold_results, expected="result", field_name="gold_results")
        _validate_statement_kinds(self.gold_limitations, expected="limitation", field_name="gold_limitations")
        _validate_statement_kinds(self.gold_gaps, expected="gap", field_name="gold_gaps")

        figure_ids = _unique_ids([figure.figure_id for figure in self.important_figures], field_name="important_figures")
        table_ids = _unique_ids([table.table_id for table in self.important_tables], field_name="important_tables")
        statement_ids = _unique_ids(
            [item.statement_id for item in self.iter_statements()],
            field_name="statement_ids",
        )
        if len(statement_ids) != len(list(self.iter_statements())):
            raise ValueError("statement_ids must be unique")

        for statement in self.iter_statements():
            for evidence in statement.evidence_refs:
                if evidence.figure_id and evidence.figure_id not in figure_ids:
                    raise ValueError(f"evidence references undeclared figure_id={evidence.figure_id}")
                if evidence.table_id and evidence.table_id not in table_ids:
                    raise ValueError(f"evidence references undeclared table_id={evidence.table_id}")
        return self

    def iter_statements(self):
        yield from self.gold_claims
        yield from self.gold_methods
        yield from self.gold_results
        yield from self.gold_limitations
        yield from self.gold_gaps


class PaperUnderstandingGoldManifestItem(BaseModel):
    paper_id: str = Field(..., min_length=1)
    gold_path: str = Field(..., min_length=1)
    paper_type: PaperUnderstandingPaperType | None = None
    domain_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_values(self):
        self.paper_id = self.paper_id.strip()
        self.gold_path = self.gold_path.strip()
        self.domain_tags = _dedupe_non_empty_strings(self.domain_tags, field_name="domain_tags")
        return self


class PaperUnderstandingGoldManifest(BaseModel):
    schema_version: PaperUnderstandingGoldManifestSchemaVersion = "paper_understanding_gold_manifest.v1"
    generated_at: datetime | None = None
    goldset_id: str = Field(..., min_length=1)
    goldset_split: str = Field(..., min_length=1)
    items: list[PaperUnderstandingGoldManifestItem] = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_manifest(self):
        self.goldset_id = self.goldset_id.strip()
        self.goldset_split = self.goldset_split.strip()
        self.notes = _dedupe_non_empty_strings(self.notes, field_name="notes") if self.notes else []
        _unique_ids([item.paper_id for item in self.items], field_name="manifest paper_id")
        _unique_ids([item.gold_path for item in self.items], field_name="manifest gold_path")
        return self


class PaperUnderstandingGoldValidationSummary(BaseModel):
    schema_version: PaperUnderstandingGoldValidationSchemaVersion = "paper_understanding_gold_validation.v1"
    checked_count: int = Field(ge=0)
    checked_gold_count: int = Field(ge=0)
    manifest_count: int = Field(ge=0)
    require_ready: bool = False
    valid_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    readiness: dict[str, Any] = Field(default_factory=dict)
    manifests: list[dict[str, Any]] = Field(default_factory=list)
    valid: list[dict[str, Any]] = Field(default_factory=list)
    invalid: list[dict[str, Any]] = Field(default_factory=list)


class PaperUnderstandingGoldValidationRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)
    require_ready: bool = False
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.paths = _dedupe_non_empty_strings(self.paths, field_name="paths")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class PaperUnderstandingGoldManifestBuildRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)
    goldset_id: str = Field(..., min_length=1)
    goldset_split: str = Field(..., min_length=1)
    out: str = Field(..., min_length=1)
    require_ready: bool = False

    @model_validator(mode="after")
    def normalize_request(self):
        self.paths = _dedupe_non_empty_strings(self.paths, field_name="paths")
        self.goldset_id = self.goldset_id.strip()
        self.goldset_split = self.goldset_split.strip()
        self.out = self.out.strip()
        if not self.goldset_id:
            raise ValueError("goldset_id is required")
        if not self.goldset_split:
            raise ValueError("goldset_split is required")
        if not self.out:
            raise ValueError("out is required")
        return self


class PaperUnderstandingGoldReadinessCheck(BaseModel):
    code: str = Field(..., min_length=1)
    status: PaperUnderstandingGoldReadinessStatus
    detail: str

    @model_validator(mode="after")
    def normalize_values(self):
        self.code = self.code.strip()
        self.detail = self.detail.strip()
        return self


class PaperUnderstandingGoldReadinessReport(BaseModel):
    schema_version: PaperUnderstandingGoldReadinessSchemaVersion = "paper_understanding_gold_readiness.v1"
    paper_id: str = Field(..., min_length=1)
    status: PaperUnderstandingGoldReadinessStatus
    checks: list[PaperUnderstandingGoldReadinessCheck] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.paper_id = self.paper_id.strip()
        self.reason_codes = _dedupe_non_empty_strings(self.reason_codes, field_name="reason_codes")
        return self


class PaperUnderstandingGoldCurationTarget(BaseModel):
    goldset_split: str | None = None
    domain_tag: str | None = None
    paper_type: PaperUnderstandingPaperType | None = None
    min_ready_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def normalize_target(self):
        if self.goldset_split is not None:
            self.goldset_split = self.goldset_split.strip() or None
        if self.domain_tag is not None:
            self.domain_tag = self.domain_tag.strip() or None
        if self.goldset_split is None and self.domain_tag is None and self.paper_type is None:
            raise ValueError("curation target requires at least one split, domain_tag, or paper_type selector")
        return self


class PaperUnderstandingGoldCurationBucket(BaseModel):
    goldset_split: str | None = None
    domain_tag: str | None = None
    paper_type: PaperUnderstandingPaperType | None = None
    total_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    warn_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    paper_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_bucket(self):
        if self.goldset_split is not None:
            self.goldset_split = self.goldset_split.strip() or None
        if self.domain_tag is not None:
            self.domain_tag = self.domain_tag.strip() or None
        self.paper_ids = _dedupe_non_empty_strings(self.paper_ids, field_name="paper_ids")
        return self


class PaperUnderstandingGoldCurationTargetResult(BaseModel):
    target: PaperUnderstandingGoldCurationTarget
    status: Literal["pass", "fail"]
    ready_count: int = Field(ge=0)
    missing_ready_count: int = Field(ge=0)
    matching_paper_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_result(self):
        self.matching_paper_ids = _dedupe_non_empty_strings(
            self.matching_paper_ids,
            field_name="matching_paper_ids",
        )
        return self


class PaperUnderstandingGoldCurationReport(BaseModel):
    schema_version: PaperUnderstandingGoldCurationReportSchemaVersion = (
        "paper_understanding_gold_curation_report.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    report_id: str = Field(..., min_length=1)
    manifest_count: int = Field(ge=0)
    paper_count: int = Field(ge=0)
    ready_paper_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    curation_ready: bool = False
    buckets: list[PaperUnderstandingGoldCurationBucket] = Field(default_factory=list)
    target_results: list[PaperUnderstandingGoldCurationTargetResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.report_id = self.report_id.strip()
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCurationAuditRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)
    report_id: str = "paper-understanding-gold-curation"
    targets: list[PaperUnderstandingGoldCurationTarget] = Field(default_factory=list)
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.paths = _dedupe_non_empty_strings(self.paths, field_name="paths")
        self.report_id = self.report_id.strip()
        if not self.report_id:
            raise ValueError("report_id is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class PaperUnderstandingGoldReleaseSplitSummary(BaseModel):
    manifest_path: str
    goldset_id: str | None = None
    goldset_split: str | None = None
    item_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    warn_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    paper_ids: list[str] = Field(default_factory=list)
    status: Literal["pass", "fail"]
    detail: str | None = None

    @model_validator(mode="after")
    def normalize_summary(self):
        self.manifest_path = self.manifest_path.strip()
        if self.goldset_id is not None:
            self.goldset_id = self.goldset_id.strip() or None
        if self.goldset_split is not None:
            self.goldset_split = self.goldset_split.strip() or None
        self.paper_ids = _dedupe_non_empty_strings(self.paper_ids, field_name="paper_ids") if self.paper_ids else []
        if self.detail is not None:
            self.detail = self.detail.strip() or None
        return self


class PaperUnderstandingGoldReleaseReadinessReport(BaseModel):
    schema_version: PaperUnderstandingGoldReleaseReadinessSchemaVersion = (
        "paper_understanding_gold_release_readiness.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    readiness_id: str = Field(..., min_length=1)
    required_splits: list[str] = Field(default_factory=list)
    min_ready_per_split: int = Field(default=1, ge=1)
    manifest_count: int = Field(ge=0)
    goldset_ids: list[str] = Field(default_factory=list)
    item_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    missing_splits: list[str] = Field(default_factory=list)
    underfilled_splits: list[str] = Field(default_factory=list)
    duplicate_paper_ids: list[str] = Field(default_factory=list)
    split_summaries: list[PaperUnderstandingGoldReleaseSplitSummary] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    release_ready: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.readiness_id = self.readiness_id.strip()
        self.required_splits = _dedupe_non_empty_strings(self.required_splits, field_name="required_splits")
        self.goldset_ids = _dedupe_non_empty_strings(self.goldset_ids, field_name="goldset_ids") if self.goldset_ids else []
        self.missing_splits = (
            _dedupe_non_empty_strings(self.missing_splits, field_name="missing_splits")
            if self.missing_splits
            else []
        )
        self.underfilled_splits = (
            _dedupe_non_empty_strings(self.underfilled_splits, field_name="underfilled_splits")
            if self.underfilled_splits
            else []
        )
        self.duplicate_paper_ids = (
            _dedupe_non_empty_strings(self.duplicate_paper_ids, field_name="duplicate_paper_ids")
            if self.duplicate_paper_ids
            else []
        )
        self.blockers = _dedupe_non_empty_strings(self.blockers, field_name="blockers") if self.blockers else []
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldReleaseReadinessRequest(BaseModel):
    manifest_paths: list[str] = Field(..., min_length=1)
    readiness_id: str = "paper-understanding-gold-release-readiness"
    required_splits: list[str] = Field(default_factory=lambda: ["seed", "eval", "holdout"])
    min_ready_per_split: int = Field(default=1, ge=1)
    require_single_goldset_id: bool = True
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.manifest_paths = _dedupe_non_empty_strings(self.manifest_paths, field_name="manifest_paths")
        self.readiness_id = self.readiness_id.strip()
        self.required_splits = _dedupe_non_empty_strings(self.required_splits, field_name="required_splits")
        if not self.readiness_id:
            raise ValueError("readiness_id is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class PaperUnderstandingGoldReleaseManifestBuildItem(BaseModel):
    staging_manifest_path: str = Field(..., min_length=1)
    goldset_split: str = Field(..., min_length=1)
    manifest_out: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_item(self):
        self.staging_manifest_path = self.staging_manifest_path.strip()
        self.goldset_split = self.goldset_split.strip()
        self.manifest_out = self.manifest_out.strip()
        if not self.staging_manifest_path:
            raise ValueError("staging_manifest_path is required")
        if not self.goldset_split:
            raise ValueError("goldset_split is required")
        if not self.manifest_out:
            raise ValueError("manifest_out is required")
        return self


class PaperUnderstandingGoldReleaseSplitPlanItem(BaseModel):
    goldset_split: str = Field(..., min_length=1)
    staging_manifest_path: str = Field(..., min_length=1)
    manifest_out: str = Field(..., min_length=1)
    staged_count: int = Field(ge=0)
    paper_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_item(self):
        self.goldset_split = self.goldset_split.strip()
        self.staging_manifest_path = self.staging_manifest_path.strip()
        self.manifest_out = self.manifest_out.strip()
        self.paper_ids = _dedupe_non_empty_strings(self.paper_ids, field_name="paper_ids") if self.paper_ids else []
        if not self.goldset_split:
            raise ValueError("goldset_split is required")
        if not self.staging_manifest_path:
            raise ValueError("staging_manifest_path is required")
        if not self.manifest_out:
            raise ValueError("manifest_out is required")
        return self


class PaperUnderstandingGoldReleaseSplitPlanReport(BaseModel):
    schema_version: PaperUnderstandingGoldReleaseSplitPlanSchemaVersion = (
        "paper_understanding_gold_release_split_plan.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    plan_id: str = Field(..., min_length=1)
    source_staging_manifest_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    manifest_out_dir: str = Field(..., min_length=1)
    split_names: list[str] = Field(default_factory=list)
    min_ready_per_split: int = Field(default=1, ge=1)
    ready_input_count: int = Field(ge=0)
    invalid_input_count: int = Field(ge=0)
    release_ready_candidate: bool = False
    split_manifests: list[PaperUnderstandingGoldReleaseManifestBuildItem] = Field(default_factory=list)
    split_items: list[PaperUnderstandingGoldReleaseSplitPlanItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.plan_id = self.plan_id.strip()
        self.source_staging_manifest_path = self.source_staging_manifest_path.strip()
        self.out_dir = self.out_dir.strip()
        self.manifest_out_dir = self.manifest_out_dir.strip()
        self.split_names = _dedupe_non_empty_strings(self.split_names, field_name="split_names")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        if not self.plan_id:
            raise ValueError("plan_id is required")
        if not self.source_staging_manifest_path:
            raise ValueError("source_staging_manifest_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.manifest_out_dir:
            raise ValueError("manifest_out_dir is required")
        return self


class PaperUnderstandingGoldReleaseSplitPlanRequest(BaseModel):
    staging_manifest_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    manifest_out_dir: str | None = None
    plan_id: str = "paper-understanding-gold-release-split-plan"
    split_names: list[str] = Field(default_factory=lambda: ["seed", "eval", "holdout"])
    min_ready_per_split: int = Field(default=1, ge=1)
    require_ready: bool = True
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.staging_manifest_path = self.staging_manifest_path.strip()
        self.out_dir = self.out_dir.strip()
        self.plan_id = self.plan_id.strip()
        self.split_names = _dedupe_non_empty_strings(self.split_names, field_name="split_names")
        if not self.staging_manifest_path:
            raise ValueError("staging_manifest_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.plan_id:
            raise ValueError("plan_id is required")
        if not self.split_names:
            raise ValueError("split_names is required")
        if self.manifest_out_dir is not None:
            self.manifest_out_dir = self.manifest_out_dir.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class PaperUnderstandingGoldReleasePackageReport(BaseModel):
    schema_version: Literal["paper_understanding_gold_release_package.v1"] = (
        "paper_understanding_gold_release_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    package_id: str = Field(..., min_length=1)
    goldset_id: str = Field(..., min_length=1)
    source_split_manifests: list[PaperUnderstandingGoldReleaseManifestBuildItem] = Field(default_factory=list)
    manifest_paths: list[str] = Field(default_factory=list)
    release_readiness_report_path: str
    release_readiness: PaperUnderstandingGoldReleaseReadinessReport

    @model_validator(mode="after")
    def normalize_report(self):
        self.package_id = self.package_id.strip()
        self.goldset_id = self.goldset_id.strip()
        self.manifest_paths = _dedupe_non_empty_strings(self.manifest_paths, field_name="manifest_paths")
        self.release_readiness_report_path = self.release_readiness_report_path.strip()
        return self


class PaperUnderstandingGoldReleasePackageFromStagedGoldRequest(BaseModel):
    goldset_id: str = Field(..., min_length=1)
    split_manifests: list[PaperUnderstandingGoldReleaseManifestBuildItem] = Field(..., min_length=1)
    release_readiness_out: str = Field(..., min_length=1)
    package_id: str = "paper-understanding-gold-release-package"
    package_out: str | None = None
    require_ready: bool = True
    required_splits: list[str] = Field(default_factory=lambda: ["seed", "eval", "holdout"])
    min_ready_per_split: int = Field(default=1, ge=1)
    require_single_goldset_id: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        self.goldset_id = self.goldset_id.strip()
        self.release_readiness_out = self.release_readiness_out.strip()
        self.package_id = self.package_id.strip()
        self.required_splits = _dedupe_non_empty_strings(self.required_splits, field_name="required_splits")
        if not self.goldset_id:
            raise ValueError("goldset_id is required")
        if not self.release_readiness_out:
            raise ValueError("release_readiness_out is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if self.package_out is not None:
            self.package_out = self.package_out.strip() or None
        return self


class PaperUnderstandingGoldReleasePackageFromSplitPlanRequest(BaseModel):
    goldset_id: str = Field(..., min_length=1)
    split_plan_path: str = Field(..., min_length=1)
    release_readiness_out: str = Field(..., min_length=1)
    package_id: str = "paper-understanding-gold-release-package"
    package_out: str | None = None
    require_ready: bool = True
    required_splits: list[str] = Field(default_factory=lambda: ["seed", "eval", "holdout"])
    min_ready_per_split: int = Field(default=1, ge=1)
    require_single_goldset_id: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        self.goldset_id = self.goldset_id.strip()
        self.split_plan_path = self.split_plan_path.strip()
        self.release_readiness_out = self.release_readiness_out.strip()
        self.package_id = self.package_id.strip()
        self.required_splits = _dedupe_non_empty_strings(self.required_splits, field_name="required_splits")
        if not self.goldset_id:
            raise ValueError("goldset_id is required")
        if not self.split_plan_path:
            raise ValueError("split_plan_path is required")
        if not self.release_readiness_out:
            raise ValueError("release_readiness_out is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if self.package_out is not None:
            self.package_out = self.package_out.strip() or None
        return self


class PaperUnderstandingGoldCandidateDraft(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftSchemaVersion = (
        "paper_understanding_gold_candidate_draft.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_kind: Literal["claim_evidence_reviewed_eval_fixtures", "teacher_verification"] = (
        "claim_evidence_reviewed_eval_fixtures"
    )
    source_reviewed_dir: str
    paper_id: str = Field(..., min_length=1)
    fixture_count: int = Field(ge=0)
    readiness: PaperUnderstandingGoldReadinessReport
    draft: PaperUnderstandingGold

    @model_validator(mode="after")
    def validate_draft(self):
        self.source_reviewed_dir = self.source_reviewed_dir.strip()
        self.paper_id = self.paper_id.strip()
        if self.paper_id != self.draft.paper_id:
            raise ValueError("candidate draft paper_id must match nested draft.paper_id")
        if self.paper_id != self.readiness.paper_id:
            raise ValueError("candidate draft paper_id must match readiness.paper_id")
        return self


class PaperUnderstandingGoldCandidateDraftManifest(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftManifestSchemaVersion = (
        "paper_understanding_gold_candidate_draft_manifest.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_reviewed_dir: str
    out_dir: str
    draft_count: int = Field(ge=0)
    draft_paths: list[str] = Field(default_factory=list)
    readiness_summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_manifest(self):
        self.source_reviewed_dir = self.source_reviewed_dir.strip()
        self.out_dir = self.out_dir.strip()
        self.draft_paths = _dedupe_non_empty_strings(self.draft_paths, field_name="draft_paths")
        return self


class PaperUnderstandingGoldReviewedFixturesDraftRequest(BaseModel):
    reviewed_dir: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    paper_id: str | None = None
    run_id: str | None = None
    claim_id: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.reviewed_dir = self.reviewed_dir.strip()
        self.out_dir = self.out_dir.strip()
        if not self.reviewed_dir:
            raise ValueError("reviewed_dir is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        for field_name in ("paper_id", "run_id", "claim_id"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldTeacherVerificationDraftRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    require_accepted: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        self.paths = _dedupe_non_empty_strings(self.paths, field_name="paths")
        self.out_dir = self.out_dir.strip()
        if not self.out_dir:
            raise ValueError("out_dir is required")
        return self


class PaperUnderstandingGoldCandidateDraftPatchRequest(BaseModel):
    draft_path: str = Field(..., min_length=1)
    out: str | None = None
    reviewer_id: str | None = None
    review_notes: str | None = None
    citation: PaperUnderstandingGoldMetadata | None = None
    paper_type: PaperUnderstandingPaperType | None = None
    domain_tags: list[str] | None = None
    gold_claims: list[PaperUnderstandingGoldStatement] | None = None
    gold_methods: list[PaperUnderstandingGoldStatement] | None = None
    gold_results: list[PaperUnderstandingGoldStatement] | None = None
    gold_limitations: list[PaperUnderstandingGoldStatement] | None = None
    gold_gaps: list[PaperUnderstandingGoldStatement] | None = None
    important_figures: list[PaperUnderstandingGoldFigure] | None = None
    important_tables: list[PaperUnderstandingGoldTable] | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.draft_path = self.draft_path.strip()
        if not self.draft_path:
            raise ValueError("draft_path is required")
        for field_name in ("out", "reviewer_id", "review_notes", "notes"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if self.domain_tags is not None:
            self.domain_tags = _dedupe_non_empty_strings(self.domain_tags, field_name="domain_tags")
        return self


class PaperUnderstandingGoldCandidateDraftPatchResult(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftPatchResultSchemaVersion = (
        "paper_understanding_gold_candidate_draft_patch_result.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_draft_path: str
    patched_draft_path: str | None = None
    reviewer_id: str | None = None
    review_notes: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    before_readiness: PaperUnderstandingGoldReadinessReport
    after_readiness: PaperUnderstandingGoldReadinessReport
    curation_ready: bool = False
    patched_draft: PaperUnderstandingGoldCandidateDraft
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_result(self):
        self.source_draft_path = self.source_draft_path.strip()
        if self.patched_draft_path is not None:
            self.patched_draft_path = self.patched_draft_path.strip() or None
        if self.reviewer_id is not None:
            self.reviewer_id = self.reviewer_id.strip() or None
        if self.review_notes is not None:
            self.review_notes = self.review_notes.strip() or None
        self.changed_fields = _dedupe_non_empty_strings(self.changed_fields, field_name="changed_fields")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCandidateDraftPatchTemplate(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftPatchTemplateSchemaVersion = (
        "paper_understanding_gold_candidate_draft_patch_template.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_draft_path: str
    paper_id: str = Field(..., min_length=1)
    readiness: PaperUnderstandingGoldReadinessReport
    open_tasks: list[PaperUnderstandingGoldCandidateDraftCurationTask] = Field(default_factory=list)
    patch_request: PaperUnderstandingGoldCandidateDraftPatchRequest
    template_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_template(self):
        self.source_draft_path = self.source_draft_path.strip()
        self.paper_id = self.paper_id.strip()
        self.template_notes = (
            _dedupe_non_empty_strings(self.template_notes, field_name="template_notes")
            if self.template_notes
            else []
        )
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCandidateDraftPatchTemplateRequest(BaseModel):
    draft_path: str = Field(..., min_length=1)
    patched_draft_out: str | None = None
    reviewer_id: str | None = None
    review_notes: str | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.draft_path = self.draft_path.strip()
        if not self.draft_path:
            raise ValueError("draft_path is required")
        for field_name in ("patched_draft_out", "reviewer_id", "review_notes", "out"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldCandidateDraftPatchTemplateManifest(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftPatchTemplateManifestSchemaVersion = (
        "paper_understanding_gold_candidate_draft_patch_template_manifest.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    curation_package_path: str
    out_dir: str
    template_count: int = Field(ge=0)
    open_task_count: int = Field(ge=0)
    template_paths: list[str] = Field(default_factory=list)
    readiness_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_manifest(self):
        self.curation_package_path = self.curation_package_path.strip()
        self.out_dir = self.out_dir.strip()
        self.template_paths = _dedupe_non_empty_strings(self.template_paths, field_name="template_paths")
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(BaseModel):
    curation_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    patched_draft_out_dir: str | None = None
    reviewer_id: str | None = None
    review_notes: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.curation_package_path = self.curation_package_path.strip()
        self.out_dir = self.out_dir.strip()
        if not self.curation_package_path:
            raise ValueError("curation_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        for field_name in ("patched_draft_out_dir", "reviewer_id", "review_notes"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldCandidateDraftPatchResultManifest(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftPatchResultManifestSchemaVersion = (
        "paper_understanding_gold_candidate_draft_patch_result_manifest.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_patch_template_paths: list[str] = Field(default_factory=list)
    out_dir: str
    result_count: int = Field(ge=0)
    curation_ready_count: int = Field(ge=0)
    not_ready_count: int = Field(ge=0)
    edited_result_count: int = Field(default=0, ge=0)
    unedited_result_count: int = Field(default=0, ge=0)
    patch_result_paths: list[str] = Field(default_factory=list)
    readiness_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_manifest(self):
        self.source_patch_template_paths = _dedupe_non_empty_strings(
            self.source_patch_template_paths,
            field_name="source_patch_template_paths",
        ) if self.source_patch_template_paths else []
        self.out_dir = self.out_dir.strip()
        self.patch_result_paths = _dedupe_non_empty_strings(
            self.patch_result_paths,
            field_name="patch_result_paths",
        ) if self.patch_result_paths else []
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest(BaseModel):
    patch_template_paths: list[str] = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def normalize_request(self):
        self.patch_template_paths = _dedupe_non_empty_strings(
            self.patch_template_paths,
            field_name="patch_template_paths",
        )
        self.out_dir = self.out_dir.strip()
        if not self.out_dir:
            raise ValueError("out_dir is required")
        return self


class PaperUnderstandingGoldCandidateDraftCurationItem(BaseModel):
    paper_id: str = Field(..., min_length=1)
    draft_path: str = Field(..., min_length=1)
    source_kind: str
    readiness_status: PaperUnderstandingGoldReadinessStatus
    readiness_reason_codes: list[str] = Field(default_factory=list)
    claim_count: int = Field(ge=0)
    method_count: int = Field(ge=0)
    result_count: int = Field(ge=0)
    limitation_count: int = Field(ge=0)
    gap_count: int = Field(ge=0)
    figure_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    next_actions: list[str] = Field(default_factory=list)
    tasks: list["PaperUnderstandingGoldCandidateDraftCurationTask"] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_item(self):
        self.paper_id = self.paper_id.strip()
        self.draft_path = self.draft_path.strip()
        self.source_kind = self.source_kind.strip()
        self.readiness_reason_codes = _dedupe_non_empty_strings(
            self.readiness_reason_codes,
            field_name="readiness_reason_codes",
        ) if self.readiness_reason_codes else []
        self.next_actions = _dedupe_non_empty_strings(
            self.next_actions,
            field_name="next_actions",
        ) if self.next_actions else []
        return self


class PaperUnderstandingGoldCandidateDraftCurationTask(BaseModel):
    task_id: str = Field(..., min_length=1)
    reason_code: str = Field(..., min_length=1)
    target_field: str = Field(..., min_length=1)
    curation_stage: str | None = None
    review_priority: int = Field(default=100, ge=0)
    current_count: int | None = Field(default=None, ge=0)
    minimum_required: int | None = Field(default=None, ge=0)
    maximum_recommended: int | None = Field(default=None, ge=0)
    instruction: str = Field(..., min_length=1)
    evidence_hint: str | None = None

    @model_validator(mode="after")
    def normalize_task(self):
        self.task_id = self.task_id.strip()
        self.reason_code = self.reason_code.strip()
        self.target_field = self.target_field.strip()
        self.instruction = self.instruction.strip()
        if self.curation_stage is not None:
            self.curation_stage = self.curation_stage.strip() or None
        if self.evidence_hint is not None:
            self.evidence_hint = self.evidence_hint.strip() or None
        return self


class PaperUnderstandingGoldCandidateDraftCurationReport(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftCurationReportSchemaVersion = (
        "paper_understanding_gold_candidate_draft_curation_report.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    report_id: str = Field(..., min_length=1)
    draft_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    warn_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    reason_code_counts: dict[str, int] = Field(default_factory=dict)
    curation_ready: bool = False
    items: list[PaperUnderstandingGoldCandidateDraftCurationItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.report_id = self.report_id.strip()
        self.reason_code_counts = {
            str(code).strip(): int(count)
            for code, count in self.reason_code_counts.items()
            if str(code).strip()
        }
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCandidateDraftCurationAuditRequest(BaseModel):
    draft_paths: list[str] = Field(..., min_length=1)
    report_id: str = "paper-understanding-gold-candidate-draft-curation"
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.draft_paths = _dedupe_non_empty_strings(self.draft_paths, field_name="draft_paths")
        self.report_id = self.report_id.strip()
        if not self.report_id:
            raise ValueError("report_id is required")
        if self.out is not None:
                self.out = self.out.strip() or None
        return self


class PaperUnderstandingGoldTeacherVerificationCurationPackage(BaseModel):
    schema_version: PaperUnderstandingGoldTeacherVerificationCurationPackageSchemaVersion = (
        "paper_understanding_gold_teacher_verification_curation_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_paths: list[str] = Field(default_factory=list)
    draft_manifest_path: str
    curation_report_path: str
    draft_manifest: PaperUnderstandingGoldCandidateDraftManifest
    curation_report: PaperUnderstandingGoldCandidateDraftCurationReport
    curation_ready: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        self.source_paths = _dedupe_non_empty_strings(self.source_paths, field_name="source_paths")
        self.draft_manifest_path = self.draft_manifest_path.strip()
        self.curation_report_path = self.curation_report_path.strip()
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldTeacherVerificationCurationPackageRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    require_accepted: bool = True
    report_id: str = "paper-understanding-gold-teacher-verification-curation"
    curation_report_out: str | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.paths = _dedupe_non_empty_strings(self.paths, field_name="paths")
        self.out_dir = self.out_dir.strip()
        self.report_id = self.report_id.strip()
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.report_id:
            raise ValueError("report_id is required")
        if self.curation_report_out is not None:
            self.curation_report_out = self.curation_report_out.strip() or None
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class PaperUnderstandingGoldReviewerHandoffPackage(BaseModel):
    schema_version: PaperUnderstandingGoldReviewerHandoffPackageSchemaVersion = (
        "paper_understanding_gold_reviewer_handoff_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    package_id: str = Field(..., min_length=1)
    source_paths: list[str] = Field(default_factory=list)
    curation_package_path: str = Field(..., min_length=1)
    patch_template_manifest_path: str = Field(..., min_length=1)
    curation_progress_report_path: str = Field(..., min_length=1)
    curation_task_export_path: str = Field(..., min_length=1)
    curation_task_export_csv_path: str | None = None
    reviewer_guide_path: str | None = None
    curation_package: PaperUnderstandingGoldTeacherVerificationCurationPackage
    patch_template_manifest: PaperUnderstandingGoldCandidateDraftPatchTemplateManifest
    curation_progress_report: "PaperUnderstandingGoldCandidateDraftCurationProgressReport"
    curation_task_export: "PaperUnderstandingGoldCurationTaskExportReport"
    draft_count: int = Field(ge=0)
    open_task_count: int = Field(ge=0)
    curation_ready: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        self.package_id = self.package_id.strip()
        self.source_paths = _dedupe_non_empty_strings(self.source_paths, field_name="source_paths")
        for field_name in (
            "curation_package_path",
            "patch_template_manifest_path",
            "curation_progress_report_path",
            "curation_task_export_path",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        if self.curation_task_export_csv_path is not None:
            self.curation_task_export_csv_path = self.curation_task_export_csv_path.strip() or None
        if self.reviewer_guide_path is not None:
            self.reviewer_guide_path = self.reviewer_guide_path.strip() or None
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldReviewerHandoffPackageRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    require_accepted: bool = True
    package_id: str = "paper-understanding-gold-reviewer-handoff"
    report_id: str = "paper-understanding-gold-teacher-verification-curation"
    reviewer_id: str | None = None
    review_notes: str | None = None
    reviewer_guide_out: str | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.paths = _dedupe_non_empty_strings(self.paths, field_name="paths")
        self.out_dir = self.out_dir.strip()
        self.package_id = self.package_id.strip()
        self.report_id = self.report_id.strip()
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.report_id:
            raise ValueError("report_id is required")
        for field_name in ("reviewer_id", "review_notes", "reviewer_guide_out", "out"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldReviewerHandoffApplyPackage(BaseModel):
    schema_version: PaperUnderstandingGoldReviewerHandoffApplyPackageSchemaVersion = (
        "paper_understanding_gold_reviewer_handoff_apply_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    apply_id: str = Field(..., min_length=1)
    reviewer_handoff_package_path: str = Field(..., min_length=1)
    patch_result_manifest_path: str = Field(..., min_length=1)
    curation_progress_report_path: str = Field(..., min_length=1)
    curation_task_export_path: str = Field(..., min_length=1)
    curation_task_export_csv_path: str | None = None
    patch_result_manifest: PaperUnderstandingGoldCandidateDraftPatchResultManifest
    curation_progress_report: "PaperUnderstandingGoldCandidateDraftCurationProgressReport"
    curation_task_export: "PaperUnderstandingGoldCurationTaskExportReport"
    result_count: int = Field(ge=0)
    curation_ready_count: int = Field(ge=0)
    not_ready_count: int = Field(ge=0)
    ready_to_stage_count: int = Field(ge=0)
    remaining_task_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        self.apply_id = self.apply_id.strip()
        if not self.apply_id:
            raise ValueError("apply_id is required")
        for field_name in (
            "reviewer_handoff_package_path",
            "patch_result_manifest_path",
            "curation_progress_report_path",
            "curation_task_export_path",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        if self.curation_task_export_csv_path is not None:
            self.curation_task_export_csv_path = self.curation_task_export_csv_path.strip() or None
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldReviewerHandoffApplyRequest(BaseModel):
    reviewer_handoff_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    apply_id: str = "paper-understanding-gold-reviewer-handoff-apply"
    patch_results_dir: str | None = None
    curation_progress_report_out: str | None = None
    curation_task_export_out: str | None = None
    curation_task_export_csv_out: str | None = None
    out: str | None = None
    require_edited: bool = False

    @model_validator(mode="after")
    def normalize_request(self):
        self.reviewer_handoff_package_path = self.reviewer_handoff_package_path.strip()
        self.out_dir = self.out_dir.strip()
        self.apply_id = self.apply_id.strip()
        if not self.reviewer_handoff_package_path:
            raise ValueError("reviewer_handoff_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.apply_id:
            raise ValueError("apply_id is required")
        for field_name in (
            "patch_results_dir",
            "curation_progress_report_out",
            "curation_task_export_out",
            "curation_task_export_csv_out",
            "out",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldReviewerHandoffStagePackage(BaseModel):
    schema_version: PaperUnderstandingGoldReviewerHandoffStagePackageSchemaVersion = (
        "paper_understanding_gold_reviewer_handoff_stage_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    stage_id: str = Field(..., min_length=1)
    reviewer_handoff_apply_package_path: str = Field(..., min_length=1)
    reviewer_handoff_package_path: str = Field(..., min_length=1)
    staging_manifest_path: str = Field(..., min_length=1)
    curation_progress_report_path: str = Field(..., min_length=1)
    curation_task_export_path: str = Field(..., min_length=1)
    curation_task_export_csv_path: str | None = None
    staging_manifest: "PaperUnderstandingGoldStagingManifest"
    curation_progress_report: "PaperUnderstandingGoldCandidateDraftCurationProgressReport"
    curation_task_export: "PaperUnderstandingGoldCurationTaskExportReport"
    staged_count: int = Field(ge=0)
    curation_complete: bool = False
    remaining_task_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        self.stage_id = self.stage_id.strip()
        if not self.stage_id:
            raise ValueError("stage_id is required")
        for field_name in (
            "reviewer_handoff_apply_package_path",
            "reviewer_handoff_package_path",
            "staging_manifest_path",
            "curation_progress_report_path",
            "curation_task_export_path",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        if self.curation_task_export_csv_path is not None:
            self.curation_task_export_csv_path = self.curation_task_export_csv_path.strip() or None
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldReviewerHandoffStageRequest(BaseModel):
    reviewer_handoff_apply_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    stage_id: str = "paper-understanding-gold-reviewer-handoff-stage"
    staged_gold_out_dir: str | None = None
    curation_progress_report_out: str | None = None
    curation_task_export_out: str | None = None
    curation_task_export_csv_out: str | None = None
    require_ready: bool = True
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.reviewer_handoff_apply_package_path = self.reviewer_handoff_apply_package_path.strip()
        self.out_dir = self.out_dir.strip()
        self.stage_id = self.stage_id.strip()
        if not self.reviewer_handoff_apply_package_path:
            raise ValueError("reviewer_handoff_apply_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.stage_id:
            raise ValueError("stage_id is required")
        for field_name in (
            "staged_gold_out_dir",
            "curation_progress_report_out",
            "curation_task_export_out",
            "curation_task_export_csv_out",
            "out",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldReviewerHandoffReleasePrepPackage(BaseModel):
    schema_version: PaperUnderstandingGoldReviewerHandoffReleasePrepPackageSchemaVersion = (
        "paper_understanding_gold_reviewer_handoff_release_prep_package.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    release_prep_id: str = Field(..., min_length=1)
    reviewer_handoff_stage_package_path: str = Field(..., min_length=1)
    staging_manifest_path: str = Field(..., min_length=1)
    split_plan_path: str = Field(..., min_length=1)
    release_package_path: str | None = None
    release_readiness_report_path: str | None = None
    split_plan: PaperUnderstandingGoldReleaseSplitPlanReport
    release_package: PaperUnderstandingGoldReleasePackageReport | None = None
    release_ready_candidate: bool = False
    release_ready: bool = False
    staged_count: int = Field(ge=0)
    split_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_package(self):
        self.release_prep_id = self.release_prep_id.strip()
        if not self.release_prep_id:
            raise ValueError("release_prep_id is required")
        for field_name in (
            "reviewer_handoff_stage_package_path",
            "staging_manifest_path",
            "split_plan_path",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        for field_name in ("release_package_path", "release_readiness_report_path"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldReviewerHandoffReleasePrepRequest(BaseModel):
    reviewer_handoff_stage_package_path: str = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    goldset_id: str = Field(..., min_length=1)
    release_prep_id: str = "paper-understanding-gold-reviewer-handoff-release-prep"
    split_names: list[str] = Field(default_factory=lambda: ["seed", "eval", "holdout"])
    required_splits: list[str] | None = None
    min_ready_per_split: int = Field(default=1, ge=1)
    require_ready: bool = True
    require_single_goldset_id: bool = True
    build_release_package: bool = True
    split_staging_out_dir: str | None = None
    manifest_out_dir: str | None = None
    split_plan_out: str | None = None
    release_readiness_out: str | None = None
    release_package_out: str | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.reviewer_handoff_stage_package_path = self.reviewer_handoff_stage_package_path.strip()
        self.out_dir = self.out_dir.strip()
        self.goldset_id = self.goldset_id.strip()
        self.release_prep_id = self.release_prep_id.strip()
        self.split_names = _dedupe_non_empty_strings(self.split_names, field_name="split_names")
        if self.required_splits is not None:
            self.required_splits = _dedupe_non_empty_strings(self.required_splits, field_name="required_splits")
        if not self.reviewer_handoff_stage_package_path:
            raise ValueError("reviewer_handoff_stage_package_path is required")
        if not self.out_dir:
            raise ValueError("out_dir is required")
        if not self.goldset_id:
            raise ValueError("goldset_id is required")
        if not self.release_prep_id:
            raise ValueError("release_prep_id is required")
        if not self.split_names:
            raise ValueError("split_names is required")
        for field_name in (
            "split_staging_out_dir",
            "manifest_out_dir",
            "split_plan_out",
            "release_readiness_out",
            "release_package_out",
            "out",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldCandidateDraftCurationProgressItem(BaseModel):
    paper_id: str = Field(..., min_length=1)
    source_draft_path: str = Field(..., min_length=1)
    latest_patch_template_path: str | None = None
    latest_patch_result_path: str | None = None
    patched_draft_path: str | None = None
    staged_gold_path: str | None = None
    status: PaperUnderstandingGoldCandidateDraftCurationProgressStatus
    readiness_status: PaperUnderstandingGoldReadinessStatus
    readiness_reason_codes: list[str] = Field(default_factory=list)
    open_task_count: int = Field(ge=0)
    open_tasks: list[PaperUnderstandingGoldCandidateDraftCurationTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_item(self):
        self.paper_id = self.paper_id.strip()
        self.source_draft_path = self.source_draft_path.strip()
        for field_name in (
            "latest_patch_template_path",
            "latest_patch_result_path",
            "patched_draft_path",
            "staged_gold_path",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        self.readiness_reason_codes = _dedupe_non_empty_strings(
            self.readiness_reason_codes,
            field_name="readiness_reason_codes",
        ) if self.readiness_reason_codes else []
        return self


class PaperUnderstandingGoldCandidateDraftCurationProgressReport(BaseModel):
    schema_version: PaperUnderstandingGoldCandidateDraftCurationProgressSchemaVersion = (
        "paper_understanding_gold_candidate_draft_curation_progress.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    report_id: str = Field(..., min_length=1)
    curation_package_path: str
    draft_count: int = Field(ge=0)
    not_started_count: int = Field(ge=0)
    templated_count: int = Field(ge=0)
    patched_count: int = Field(ge=0)
    ready_to_stage_count: int = Field(ge=0)
    staged_count: int = Field(ge=0)
    remaining_task_count: int = Field(ge=0)
    curation_complete: bool = False
    items: list[PaperUnderstandingGoldCandidateDraftCurationProgressItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.report_id = self.report_id.strip()
        self.curation_package_path = self.curation_package_path.strip()
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCandidateDraftCurationProgressRequest(BaseModel):
    curation_package_path: str = Field(..., min_length=1)
    patch_template_paths: list[str] = Field(default_factory=list)
    patch_result_paths: list[str] = Field(default_factory=list)
    staged_paths: list[str] = Field(default_factory=list)
    report_id: str = "paper-understanding-gold-candidate-draft-curation-progress"
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.curation_package_path = self.curation_package_path.strip()
        self.patch_template_paths = _dedupe_non_empty_strings(
            self.patch_template_paths,
            field_name="patch_template_paths",
        ) if self.patch_template_paths else []
        self.patch_result_paths = _dedupe_non_empty_strings(
            self.patch_result_paths,
            field_name="patch_result_paths",
        ) if self.patch_result_paths else []
        self.staged_paths = _dedupe_non_empty_strings(
            self.staged_paths,
            field_name="staged_paths",
        ) if self.staged_paths else []
        self.report_id = self.report_id.strip()
        if not self.curation_package_path:
            raise ValueError("curation_package_path is required")
        if not self.report_id:
            raise ValueError("report_id is required")
        if self.out is not None:
            self.out = self.out.strip() or None
        return self


class PaperUnderstandingGoldCurationTaskExportItem(BaseModel):
    paper_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    status: PaperUnderstandingGoldCandidateDraftCurationProgressStatus
    readiness_status: PaperUnderstandingGoldReadinessStatus
    reason_code: str = Field(..., min_length=1)
    target_field: str = Field(..., min_length=1)
    curation_stage: str | None = None
    review_priority: int = Field(default=100, ge=0)
    current_count: int | None = Field(default=None, ge=0)
    minimum_required: int | None = Field(default=None, ge=0)
    maximum_recommended: int | None = Field(default=None, ge=0)
    instruction: str = Field(..., min_length=1)
    evidence_hint: str | None = None
    source_draft_path: str = Field(..., min_length=1)
    latest_patch_template_path: str | None = None
    latest_patch_result_path: str | None = None
    patched_draft_path: str | None = None

    @model_validator(mode="after")
    def normalize_item(self):
        for field_name in (
            "paper_id",
            "task_id",
            "reason_code",
            "target_field",
            "instruction",
            "source_draft_path",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        for field_name in (
            "curation_stage",
            "evidence_hint",
            "latest_patch_template_path",
            "latest_patch_result_path",
            "patched_draft_path",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldCurationTaskExportReport(BaseModel):
    schema_version: PaperUnderstandingGoldCurationTaskExportSchemaVersion = (
        "paper_understanding_gold_curation_task_export.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    export_id: str = Field(..., min_length=1)
    curation_progress_report_path: str | None = None
    curation_package_path: str = Field(..., min_length=1)
    paper_count: int = Field(ge=0)
    open_task_count: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    reason_code_counts: dict[str, int] = Field(default_factory=dict)
    target_field_counts: dict[str, int] = Field(default_factory=dict)
    curation_stage_counts: dict[str, int] = Field(default_factory=dict)
    review_priority_counts: dict[str, int] = Field(default_factory=dict)
    items: list[PaperUnderstandingGoldCurationTaskExportItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_report(self):
        self.export_id = self.export_id.strip()
        self.curation_package_path = self.curation_package_path.strip()
        if self.curation_progress_report_path is not None:
            self.curation_progress_report_path = self.curation_progress_report_path.strip() or None
        if not self.export_id:
            raise ValueError("export_id is required")
        if not self.curation_package_path:
            raise ValueError("curation_package_path is required")
        self.status_counts = _normalize_count_map(self.status_counts)
        self.reason_code_counts = _normalize_count_map(self.reason_code_counts)
        self.target_field_counts = _normalize_count_map(self.target_field_counts)
        self.curation_stage_counts = _normalize_count_map(self.curation_stage_counts)
        self.review_priority_counts = _normalize_count_map(self.review_priority_counts)
        self.warnings = _dedupe_non_empty_strings(self.warnings, field_name="warnings") if self.warnings else []
        return self


class PaperUnderstandingGoldCurationTaskExportRequest(BaseModel):
    curation_package_path: str = Field(..., min_length=1)
    patch_template_paths: list[str] = Field(default_factory=list)
    patch_result_paths: list[str] = Field(default_factory=list)
    staged_paths: list[str] = Field(default_factory=list)
    export_id: str = "paper-understanding-gold-curation-task-export"
    progress_report_out: str | None = None
    csv_out: str | None = None
    out: str | None = None

    @model_validator(mode="after")
    def normalize_request(self):
        self.curation_package_path = self.curation_package_path.strip()
        self.patch_template_paths = _dedupe_non_empty_strings(
            self.patch_template_paths,
            field_name="patch_template_paths",
        ) if self.patch_template_paths else []
        self.patch_result_paths = _dedupe_non_empty_strings(
            self.patch_result_paths,
            field_name="patch_result_paths",
        ) if self.patch_result_paths else []
        self.staged_paths = _dedupe_non_empty_strings(
            self.staged_paths,
            field_name="staged_paths",
        ) if self.staged_paths else []
        self.export_id = self.export_id.strip()
        if not self.curation_package_path:
            raise ValueError("curation_package_path is required")
        if not self.export_id:
            raise ValueError("export_id is required")
        for field_name in ("progress_report_out", "csv_out", "out"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class PaperUnderstandingGoldStagingManifest(BaseModel):
    schema_version: PaperUnderstandingGoldStagingManifestSchemaVersion = "paper_understanding_gold_staging_manifest.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_draft_paths: list[str] = Field(default_factory=list)
    out_dir: str
    require_ready: bool = True
    staged_count: int = Field(ge=0)
    staged_paths: list[str] = Field(default_factory=list)
    readiness_summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_manifest(self):
        self.source_draft_paths = _dedupe_non_empty_strings(
            self.source_draft_paths,
            field_name="source_draft_paths",
        )
        self.out_dir = self.out_dir.strip()
        self.staged_paths = _dedupe_non_empty_strings(self.staged_paths, field_name="staged_paths")
        return self


class PaperUnderstandingGoldCandidateDraftStagingRequest(BaseModel):
    draft_paths: list[str] = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    require_ready: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        self.draft_paths = _dedupe_non_empty_strings(self.draft_paths, field_name="draft_paths")
        self.out_dir = self.out_dir.strip()
        if not self.out_dir:
            raise ValueError("out_dir is required")
        return self


class PaperUnderstandingGoldPatchResultStagingRequest(BaseModel):
    patch_result_paths: list[str] = Field(..., min_length=1)
    out_dir: str = Field(..., min_length=1)
    require_ready: bool = True

    @model_validator(mode="after")
    def normalize_request(self):
        self.patch_result_paths = _dedupe_non_empty_strings(
            self.patch_result_paths,
            field_name="patch_result_paths",
        )
        self.out_dir = self.out_dir.strip()
        if not self.out_dir:
            raise ValueError("out_dir is required")
        return self


def _validate_statement_kinds(
    statements: list[PaperUnderstandingGoldStatement],
    *,
    expected: PaperUnderstandingStatementKind,
    field_name: str,
) -> None:
    for statement in statements:
        if statement.kind != expected:
            raise ValueError(f"{field_name} entries must use kind={expected}")


def _unique_ids(values: list[str], *, field_name: str) -> set[str]:
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            raise ValueError(f"{field_name} contains an empty id")
        if value in seen:
            raise ValueError(f"{field_name} contains duplicate id={value}")
        seen.add(value)
    return seen


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


def _normalize_count_map(values: dict[str, int]) -> dict[str, int]:
    return {
        str(key).strip(): int(value)
        for key, value in values.items()
        if str(key).strip()
    }
