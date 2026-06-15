from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, model_validator

from .paper_understanding_failures import PaperUnderstandingFailureCode


ClaimEvidenceCorrectionFeedbackExportStatus = Literal["not_applicable", "pending", "linked"]
ClaimEvidenceEvalReviewStatus = Literal["pending_review"]
ClaimEvidenceEvalReviewResolution = Literal["APPROVE_FOR_EVAL", "REJECT", "NEEDS_MORE_EVIDENCE"]


def _dedupe_non_empty_strings(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value or "").strip()
        if not value:
            raise ValueError(f"{field_name} entries must be non-empty")
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


class ClaimEvidenceCorrectionLocator(BaseModel):
    page: int | None = Field(default=None, ge=0)
    chunk_id: str | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    quote: str | None = None
    section: str | None = None
    figure_id: str | None = None
    table_id: str | None = None
    cell_id: str | None = None
    bbox_pdf: list[float] | None = None
    bbox_pct: dict[str, float] | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def normalize_and_validate(self):
        for field_name in ("chunk_id", "quote", "section", "figure_id", "table_id", "cell_id", "rationale"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if self.char_start is not None and self.char_end is not None and self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class ClaimEvidenceCorrectionCase(BaseModel):
    correction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    paper_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    claim_id: str = Field(..., min_length=1)
    field_path: str = Field(..., min_length=1)
    before_claim_text: str = Field(..., min_length=1)
    after_claim_text: str = Field(..., min_length=1)
    before_evidence_refs: list[ClaimEvidenceCorrectionLocator] = Field(default_factory=list)
    after_evidence_refs: list[ClaimEvidenceCorrectionLocator] = Field(default_factory=list)
    reason_codes: list[PaperUnderstandingFailureCode] = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    parser_version: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_model_version: str | None = None
    prompt_version: str | None = None
    reader_profile_version: str | None = None
    created_at: datetime | None = None
    accepted_for_eval: bool = False
    related_feedback_id: str | None = None
    feedback_export_status: ClaimEvidenceCorrectionFeedbackExportStatus = "not_applicable"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_and_validate(self):
        for field_name in (
            "correction_id",
            "paper_id",
            "run_id",
            "claim_id",
            "field_path",
            "before_claim_text",
            "after_claim_text",
            "reviewer_id",
            "parser_version",
            "llm_provider",
            "llm_model",
            "llm_model_version",
            "prompt_version",
            "reader_profile_version",
            "related_feedback_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)

        if not self.correction_id:
            raise ValueError("correction_id is required")
        for field_name in (
            "paper_id",
            "run_id",
            "claim_id",
            "field_path",
            "before_claim_text",
            "after_claim_text",
            "reviewer_id",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")

        if self.feedback_export_status == "linked" and not self.related_feedback_id:
            raise ValueError("feedback_export_status=linked requires related_feedback_id")
        if self.related_feedback_id and self.feedback_export_status != "linked":
            self.feedback_export_status = "linked"
        if self.accepted_for_eval and self.feedback_export_status == "not_applicable":
            self.feedback_export_status = "pending"
        if self.accepted_for_eval:
            if not self.before_evidence_refs:
                raise ValueError("accepted_for_eval requires before_evidence_refs")
            if not self.after_evidence_refs:
                raise ValueError("accepted_for_eval requires after_evidence_refs")
            for field_name in (
                "parser_version",
                "llm_provider",
                "llm_model",
                "llm_model_version",
                "prompt_version",
                "reader_profile_version",
            ):
                if not getattr(self, field_name):
                    raise ValueError(f"accepted_for_eval requires {field_name}")
        return self


class ClaimEvidenceCorrectionEvalCandidate(BaseModel):
    schema_version: Literal["claim_evidence_eval_candidate.v1"] = "claim_evidence_eval_candidate.v1"
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    source_correction_id: str
    source_feedback_id: str | None = None
    paper_id: str
    run_id: str
    claim_id: str
    field_path: str
    before_claim_text: str
    after_claim_text: str
    before_evidence_refs: list[ClaimEvidenceCorrectionLocator] = Field(default_factory=list)
    after_evidence_refs: list[ClaimEvidenceCorrectionLocator] = Field(default_factory=list)
    reason_codes: list[PaperUnderstandingFailureCode] = Field(default_factory=list)
    parser_version: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_model_version: str | None = None
    prompt_version: str | None = None
    reader_profile_version: str | None = None
    reviewer_id: str
    correction_created_at: datetime | None = None
    feedback_export_status: ClaimEvidenceCorrectionFeedbackExportStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimEvidenceCorrectionSourceRecordDiagnostic(BaseModel):
    line_number: int = Field(..., ge=1)
    status: Literal["invalid"] = "invalid"
    error_type: str = Field(..., min_length=1)
    detail: str | None = None
    source_correction_id: str | None = None
    paper_id: str | None = None
    run_id: str | None = None
    claim_id: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    available_replay_context: dict[str, str] = Field(default_factory=dict)
    missing_replay_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.error_type = self.error_type.strip()
        if not self.error_type:
            raise ValueError("error_type is required")
        for field_name in ("detail", "source_correction_id", "paper_id", "run_id", "claim_id"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        normalized_reason_codes: list[str] = []
        seen_reason_codes: set[str] = set()
        for raw_code in self.reason_codes:
            code = str(raw_code or "").strip()
            if not code:
                raise ValueError("reason_codes entries must be non-empty")
            if code in seen_reason_codes:
                continue
            seen_reason_codes.add(code)
            normalized_reason_codes.append(code)
        self.reason_codes = normalized_reason_codes

        normalized_context: dict[str, str] = {}
        for raw_key, raw_value in self.available_replay_context.items():
            key = str(raw_key or "").strip()
            value = str(raw_value or "").strip()
            if key and value:
                normalized_context[key] = value
        self.available_replay_context = normalized_context

        normalized_fields: list[str] = []
        seen_fields: set[str] = set()
        for raw_field in self.missing_replay_fields:
            field = str(raw_field or "").strip()
            if not field:
                raise ValueError("missing_replay_fields entries must be non-empty")
            if field in seen_fields:
                continue
            seen_fields.add(field)
            normalized_fields.append(field)
        self.missing_replay_fields = normalized_fields
        return self


class ClaimEvidenceCorrectionEvalCandidateExport(BaseModel):
    schema_version: Literal["claim_evidence_eval_candidate_export.v1"] = (
        "claim_evidence_eval_candidate_export.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    candidate_count: int = Field(ge=0)
    source_correction_log_path: str | None = None
    source_record_count: int = Field(default=0, ge=0)
    source_valid_record_count: int = Field(default=0, ge=0)
    source_invalid_record_count: int = Field(default=0, ge=0)
    skipped_not_accepted_count: int = Field(default=0, ge=0)
    skipped_filter_count: int = Field(default=0, ge=0)
    skipped_limit_count: int = Field(default=0, ge=0)
    source_invalid_record_diagnostics: list[ClaimEvidenceCorrectionSourceRecordDiagnostic] = Field(default_factory=list)
    source_invalid_record_missing_replay_fields_by_line: dict[str, list[str]] = Field(default_factory=dict)
    source_invalid_record_repair_targets_by_line: dict[str, dict[str, str]] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    candidates: list[ClaimEvidenceCorrectionEvalCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_source_diagnostic_summaries(self):
        expected_missing_fields: dict[str, list[str]] = {}
        expected_repair_targets: dict[str, dict[str, str]] = {}
        for diagnostic in self.source_invalid_record_diagnostics:
            line_key = f"line_{diagnostic.line_number}"
            if diagnostic.missing_replay_fields:
                expected_missing_fields[line_key] = list(diagnostic.missing_replay_fields)
            repair_target = {
                key: value
                for key, value in {
                    "source_correction_id": diagnostic.source_correction_id,
                    "paper_id": diagnostic.paper_id,
                    "run_id": diagnostic.run_id,
                    "claim_id": diagnostic.claim_id,
                }.items()
                if value
            }
            if repair_target:
                expected_repair_targets[line_key] = repair_target

        normalized_missing_fields: dict[str, list[str]] = {}
        for raw_line, raw_fields in sorted(
            self.source_invalid_record_missing_replay_fields_by_line.items()
        ):
            line = str(raw_line or "").strip()
            if not line:
                continue
            normalized_missing_fields[line] = _dedupe_non_empty_strings(
                [str(field) for field in raw_fields],
                field_name=f"source_invalid_record_missing_replay_fields_by_line.{line}",
            )
        normalized_missing_fields = {
            line: fields
            for line, fields in normalized_missing_fields.items()
            if fields
        }

        normalized_repair_targets: dict[str, dict[str, str]] = {}
        for raw_line, raw_target in sorted(
            self.source_invalid_record_repair_targets_by_line.items()
        ):
            line = str(raw_line or "").strip()
            if not line:
                continue
            target = {
                str(key or "").strip(): str(value or "").strip()
                for key, value in sorted(raw_target.items())
                if str(key or "").strip() and str(value or "").strip()
            }
            if target:
                normalized_repair_targets[line] = target

        if not normalized_missing_fields:
            normalized_missing_fields = expected_missing_fields
        if not normalized_repair_targets:
            normalized_repair_targets = expected_repair_targets
        if normalized_missing_fields != expected_missing_fields:
            raise ValueError(
                "source_invalid_record_missing_replay_fields_by_line must match diagnostics"
            )
        if normalized_repair_targets != expected_repair_targets:
            raise ValueError("source_invalid_record_repair_targets_by_line must match diagnostics")
        self.source_invalid_record_missing_replay_fields_by_line = normalized_missing_fields
        self.source_invalid_record_repair_targets_by_line = normalized_repair_targets
        return self


class ClaimEvidenceCorrectionRepairPlanTarget(BaseModel):
    line_number: int = Field(..., ge=1)
    source_correction_id: str | None = None
    paper_id: str | None = None
    run_id: str | None = None
    claim_id: str | None = None
    detail: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    available_replay_context: dict[str, str] = Field(default_factory=dict)
    missing_replay_fields: list[str] = Field(default_factory=list)
    suggested_action: str = (
        "Repair the source correction row with evidence-backed replay lineage before exporting eval candidates."
    )

    @model_validator(mode="after")
    def normalize_fields(self):
        for field_name in (
            "source_correction_id",
            "paper_id",
            "run_id",
            "claim_id",
            "detail",
            "suggested_action",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        normalized_reason_codes: list[str] = []
        seen_reason_codes: set[str] = set()
        for raw_code in self.reason_codes:
            code = str(raw_code or "").strip()
            if not code:
                raise ValueError("reason_codes entries must be non-empty")
            if code in seen_reason_codes:
                continue
            seen_reason_codes.add(code)
            normalized_reason_codes.append(code)
        self.reason_codes = normalized_reason_codes

        normalized_context: dict[str, str] = {}
        for raw_key, raw_value in self.available_replay_context.items():
            key = str(raw_key or "").strip()
            value = str(raw_value or "").strip()
            if key and value:
                normalized_context[key] = value
        self.available_replay_context = normalized_context

        normalized_fields: list[str] = []
        seen_fields: set[str] = set()
        for raw_field in self.missing_replay_fields:
            field = str(raw_field or "").strip()
            if not field:
                raise ValueError("missing_replay_fields entries must be non-empty")
            if field in seen_fields:
                continue
            seen_fields.add(field)
            normalized_fields.append(field)
        self.missing_replay_fields = normalized_fields
        return self


class ClaimEvidenceCorrectionRepairPlan(BaseModel):
    schema_version: Literal["claim_evidence_correction_repair_plan.v1"] = (
        "claim_evidence_correction_repair_plan.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_correction_log_path: str
    source_record_count: int = Field(ge=0)
    source_valid_record_count: int = Field(ge=0)
    source_invalid_record_count: int = Field(ge=0)
    repair_target_count: int = Field(default=0, ge=0)
    targets: list[ClaimEvidenceCorrectionRepairPlanTarget] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.source_correction_log_path = self.source_correction_log_path.strip()
        if not self.source_correction_log_path:
            raise ValueError("source_correction_log_path is required")
        self.repair_target_count = len(self.targets)
        normalized_warnings: list[str] = []
        seen_warnings: set[str] = set()
        for raw_warning in self.warnings:
            warning = str(raw_warning or "").strip()
            if not warning:
                continue
            if warning in seen_warnings:
                continue
            seen_warnings.add(warning)
            normalized_warnings.append(warning)
        self.warnings = normalized_warnings
        return self


class ClaimEvidenceCorrectionRepairPatchTemplateRecord(BaseModel):
    line_number: int = Field(..., ge=1)
    source_correction_id: str | None = None
    paper_id: str | None = None
    run_id: str | None = None
    claim_id: str | None = None
    missing_replay_fields: list[str] = Field(default_factory=list)
    available_replay_context: dict[str, str] = Field(default_factory=dict)
    suggested_lineage_values: dict[str, str] = Field(default_factory=dict)
    patch_fields: dict[str, str] = Field(default_factory=dict)
    source_record: dict[str, Any] = Field(default_factory=dict)
    patch_record: dict[str, Any] = Field(default_factory=dict)
    review_required: bool = True
    notes: str = "Fill missing replay lineage from evidence-backed source context before applying."


class ClaimEvidenceCorrectionRepairPatchTemplate(BaseModel):
    schema_version: Literal["claim_evidence_correction_repair_patch_template.v1"] = (
        "claim_evidence_correction_repair_patch_template.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_repair_plan_path: str
    source_correction_log_path: str
    target_count: int = Field(default=0, ge=0)
    records: list[ClaimEvidenceCorrectionRepairPatchTemplateRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.source_repair_plan_path = self.source_repair_plan_path.strip()
        self.source_correction_log_path = self.source_correction_log_path.strip()
        if not self.source_repair_plan_path:
            raise ValueError("source_repair_plan_path is required")
        if not self.source_correction_log_path:
            raise ValueError("source_correction_log_path is required")
        self.target_count = len(self.records)
        normalized_warnings: list[str] = []
        seen_warnings: set[str] = set()
        for raw_warning in self.warnings:
            warning = str(raw_warning or "").strip()
            if not warning or warning in seen_warnings:
                continue
            seen_warnings.add(warning)
            normalized_warnings.append(warning)
        self.warnings = normalized_warnings
        return self


class ClaimEvidenceCorrectionRepairedLogDraft(BaseModel):
    schema_version: Literal["claim_evidence_correction_repaired_log_draft.v1"] = (
        "claim_evidence_correction_repaired_log_draft.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_patch_template_path: str
    source_correction_log_path: str
    repaired_log_path: str | None = None
    record_count: int = Field(default=0, ge=0)
    repaired_record_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self):
        self.source_patch_template_path = self.source_patch_template_path.strip()
        self.source_correction_log_path = self.source_correction_log_path.strip()
        if self.repaired_log_path is not None:
            self.repaired_log_path = self.repaired_log_path.strip() or None
        if not self.source_patch_template_path:
            raise ValueError("source_patch_template_path is required")
        if not self.source_correction_log_path:
            raise ValueError("source_correction_log_path is required")
        normalized_warnings: list[str] = []
        seen_warnings: set[str] = set()
        for raw_warning in self.warnings:
            warning = str(raw_warning or "").strip()
            if not warning or warning in seen_warnings:
                continue
            seen_warnings.add(warning)
            normalized_warnings.append(warning)
        self.warnings = normalized_warnings
        return self


class ClaimEvidenceCorrectionEvalReviewRecord(BaseModel):
    schema_version: Literal["claim_evidence_eval_review_intake.v1"] = (
        "claim_evidence_eval_review_intake.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    intake_id: str = Field(..., min_length=1)
    created_at: datetime
    review_status: ClaimEvidenceEvalReviewStatus = "pending_review"
    recommended_review_action: str = "review_before_gold_promotion"
    source_candidate: ClaimEvidenceCorrectionEvalCandidate


class ClaimEvidenceCorrectionEvalReviewManifest(BaseModel):
    schema_version: Literal["claim_evidence_eval_review_intake_manifest.v1"] = (
        "claim_evidence_eval_review_intake_manifest.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_export_path: str | None = None
    records_dir: str
    record_count: int = Field(ge=0)
    skipped_existing_count: int = Field(ge=0, default=0)
    record_paths: list[str] = Field(default_factory=list)


class ClaimEvidenceEvalReviewImportRequest(BaseModel):
    export_path: str = Field(..., min_length=1)
    records_dir: str | None = None
    goldset_root: str | None = None
    overwrite: bool = False
    require_replayable: bool = False

    @model_validator(mode="after")
    def normalize_fields(self):
        for field_name in ("export_path", "records_dir", "goldset_root"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if not self.export_path:
            raise ValueError("export_path is required")
        return self


class ClaimEvidenceEvalReviewImportFromCorrectionsRequest(BaseModel):
    records_dir: str | None = None
    goldset_root: str | None = None
    paper_id: str | None = None
    run_id: str | None = None
    claim_id: str | None = None
    reason_code: str | None = None
    feedback_export_status: ClaimEvidenceCorrectionFeedbackExportStatus | None = None
    limit: int = Field(default=500, ge=1, le=5000)
    overwrite: bool = False
    require_replayable: bool = False

    @model_validator(mode="after")
    def normalize_fields(self):
        for field_name in (
            "records_dir",
            "goldset_root",
            "paper_id",
            "run_id",
            "claim_id",
            "reason_code",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class ClaimEvidenceCorrectionEvalReviewDecision(BaseModel):
    schema_version: Literal["claim_evidence_eval_review_decision.v1"] = (
        "claim_evidence_eval_review_decision.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    decision_id: str = Field(..., min_length=1)
    intake_id: str = Field(..., min_length=1)
    reviewed_at: datetime
    reviewer_id: str = Field(..., min_length=1)
    resolution: ClaimEvidenceEvalReviewResolution
    approved_for_eval: bool = False
    notes: str = ""
    source_record_path: str
    reviewed_fixture_path: str | None = None
    source_record: ClaimEvidenceCorrectionEvalReviewRecord


class ClaimEvidenceCorrectionReviewedEvalFixture(BaseModel):
    schema_version: Literal["claim_evidence_reviewed_eval_fixture.v1"] = (
        "claim_evidence_reviewed_eval_fixture.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    source_decision_id: str
    intake_id: str
    reviewed_at: datetime
    reviewer_id: str
    source_candidate: ClaimEvidenceCorrectionEvalCandidate
    review_notes: str = ""


class ClaimEvidenceCorrectionReviewedEvalFixturesBundle(BaseModel):
    schema_version: Literal["claim_evidence_reviewed_eval_fixtures_bundle.v1"] = (
        "claim_evidence_reviewed_eval_fixtures_bundle.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    generated_at: datetime
    source_reviewed_dir: str = Field(..., min_length=1)
    paper_id: str | None = None
    run_id: str | None = None
    claim_id: str | None = None
    fixture_count: int = Field(ge=0)
    fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self):
        for field_name in ("source_reviewed_dir", "paper_id", "run_id", "claim_id"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if not self.source_reviewed_dir:
            raise ValueError("source_reviewed_dir is required")
        return self


class ClaimEvidenceReviewedFixturesPackageRequest(BaseModel):
    run_dir: str = Field(..., min_length=1)
    reviewed_dir: str | None = None
    goldset_root: str | None = None
    paper_id: str | None = None
    run_id: str | None = None
    claim_id: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self):
        for field_name in ("run_dir", "reviewed_dir", "goldset_root", "paper_id", "run_id", "claim_id"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if not self.run_dir:
            raise ValueError("run_dir is required")
        return self


class ClaimEvidenceReviewedFixturesPackageResponse(BaseModel):
    status: Literal["packaged"] = "packaged"
    message: str
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    path: str
    fixture_count: int = Field(ge=0)


class ClaimEvidenceEvalReviewQueueItem(BaseModel):
    intake_id: str
    paper_id: str
    run_id: str
    claim_id: str
    reason_codes: list[PaperUnderstandingFailureCode] = Field(default_factory=list)
    record_path: str
    reviewed: bool = False
    review_resolution: ClaimEvidenceEvalReviewResolution | None = None
    approved_for_eval: bool = False
    reviewed_at: str | None = None
    reviewed_fixture_path: str | None = None


class ClaimEvidenceEvalReviewQueueResponse(BaseModel):
    schema_version: Literal["claim_evidence_eval_review_queue.v1"] = (
        "claim_evidence_eval_review_queue.v1"
    )
    layer: Literal["review_gate_artifact"] = "review_gate_artifact"
    canonical_status: Literal["non_canonical"] = "non_canonical"
    records_dir: str
    item_count: int = Field(ge=0)
    items: list[ClaimEvidenceEvalReviewQueueItem] = Field(default_factory=list)


class ClaimEvidenceEvalReviewResolveRequest(BaseModel):
    intake_id: str = Field(..., min_length=1)
    resolution: ClaimEvidenceEvalReviewResolution
    reviewer_id: str = Field(default="human", min_length=1)
    notes: str = ""
    records_dir: str | None = None
    goldset_root: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self):
        for field_name in ("intake_id", "reviewer_id", "notes", "records_dir", "goldset_root"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        if not self.intake_id:
            raise ValueError("intake_id is required")
        if not self.reviewer_id:
            self.reviewer_id = "human"
        return self
