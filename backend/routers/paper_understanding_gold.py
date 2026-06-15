from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGoldCandidateDraftCurationAuditRequest,
    PaperUnderstandingGoldCandidateDraftCurationProgressReport,
    PaperUnderstandingGoldCandidateDraftCurationProgressRequest,
    PaperUnderstandingGoldCandidateDraftCurationReport,
    PaperUnderstandingGoldCandidateDraftManifest,
    PaperUnderstandingGoldCandidateDraftPatchRequest,
    PaperUnderstandingGoldCandidateDraftPatchResult,
    PaperUnderstandingGoldCandidateDraftPatchResultManifest,
    PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest,
    PaperUnderstandingGoldCandidateDraftPatchTemplate,
    PaperUnderstandingGoldCandidateDraftPatchTemplateManifest,
    PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest,
    PaperUnderstandingGoldCandidateDraftPatchTemplateRequest,
    PaperUnderstandingGoldCandidateDraftStagingRequest,
    PaperUnderstandingGoldCurationAuditRequest,
    PaperUnderstandingGoldCurationReport,
    PaperUnderstandingGoldCurationTaskExportReport,
    PaperUnderstandingGoldCurationTaskExportRequest,
    PaperUnderstandingGoldManifest,
    PaperUnderstandingGoldManifestBuildRequest,
    PaperUnderstandingGoldPatchResultStagingRequest,
    PaperUnderstandingGoldReleasePackageFromSplitPlanRequest,
    PaperUnderstandingGoldReleasePackageFromStagedGoldRequest,
    PaperUnderstandingGoldReleasePackageReport,
    PaperUnderstandingGoldReleaseReadinessReport,
    PaperUnderstandingGoldReleaseReadinessRequest,
    PaperUnderstandingGoldReleaseSplitPlanReport,
    PaperUnderstandingGoldReleaseSplitPlanRequest,
    PaperUnderstandingGoldReviewerHandoffApplyPackage,
    PaperUnderstandingGoldReviewerHandoffApplyRequest,
    PaperUnderstandingGoldReviewerHandoffPackage,
    PaperUnderstandingGoldReviewerHandoffPackageRequest,
    PaperUnderstandingGoldReviewerHandoffReleasePrepPackage,
    PaperUnderstandingGoldReviewerHandoffReleasePrepRequest,
    PaperUnderstandingGoldReviewerHandoffStagePackage,
    PaperUnderstandingGoldReviewerHandoffStageRequest,
    PaperUnderstandingGoldReviewedFixturesDraftRequest,
    PaperUnderstandingGoldStagingManifest,
    PaperUnderstandingGoldTeacherVerificationDraftRequest,
    PaperUnderstandingGoldTeacherVerificationCurationPackage,
    PaperUnderstandingGoldTeacherVerificationCurationPackageRequest,
    PaperUnderstandingGoldValidationRequest,
    PaperUnderstandingGoldValidationSummary,
)
from src.services.paper_understanding_gold_drafts import (
    ReviewerHandoffApplyRequiresEditedError,
    apply_paper_understanding_gold_reviewer_handoff_package,
    build_paper_understanding_gold_candidate_draft_curation_report,
    build_paper_understanding_gold_candidate_draft_curation_progress_report,
    build_paper_understanding_gold_candidate_draft_patch_template,
    build_paper_understanding_gold_curation_task_export_report,
    build_paper_understanding_gold_reviewer_handoff_release_prep_package,
    patch_paper_understanding_gold_candidate_draft,
    stage_paper_understanding_gold_reviewer_handoff_apply_package,
    stage_paper_understanding_gold_from_candidate_drafts,
    stage_paper_understanding_gold_from_patch_results,
    write_paper_understanding_gold_candidate_drafts,
    write_paper_understanding_gold_candidate_drafts_from_teacher_verification,
    write_paper_understanding_gold_candidate_draft_patch_template_manifest,
    write_paper_understanding_gold_candidate_draft_patch_result_manifest,
    write_paper_understanding_gold_reviewer_handoff_package,
    write_paper_understanding_gold_teacher_verification_curation_package,
)
from src.services.paper_understanding_gold_validation import (
    build_paper_understanding_gold_curation_report,
    build_paper_understanding_gold_manifest,
    build_paper_understanding_gold_release_package_from_split_plan,
    build_paper_understanding_gold_release_package_from_staged_gold,
    build_paper_understanding_gold_release_readiness_report,
    build_paper_understanding_gold_release_split_plan_from_staging_manifest,
    validate_gold_paths,
)
from src.skills.storage import atomic_write_text


logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/paper-understanding-gold", tags=["paper-understanding-gold"])


@router.post("/validate", response_model=PaperUnderstandingGoldValidationSummary)
async def validate_paper_understanding_gold(
    payload: PaperUnderstandingGoldValidationRequest,
):
    try:
        summary = PaperUnderstandingGoldValidationSummary.model_validate(
            validate_gold_paths(
                [Path(path).expanduser().resolve() for path in payload.paths],
                require_ready=payload.require_ready,
            )
        )
        if payload.out:
            atomic_write_text(Path(payload.out).expanduser().resolve(), summary.model_dump_json(indent=2))
        return summary
    except Exception as exc:
        logger.error("Failed to validate paper-understanding gold: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/manifests/build", response_model=PaperUnderstandingGoldManifest)
async def build_paper_understanding_goldset_manifest(
    payload: PaperUnderstandingGoldManifestBuildRequest,
):
    try:
        out = Path(payload.out).expanduser().resolve()
        manifest = build_paper_understanding_gold_manifest(
            [Path(path).expanduser().resolve() for path in payload.paths],
            goldset_id=payload.goldset_id,
            goldset_split=payload.goldset_split,
            manifest_path=out,
            require_ready=payload.require_ready,
        )
        atomic_write_text(out, manifest.model_dump_json(indent=2))
        validation = validate_gold_paths([out], require_ready=payload.require_ready)
        if validation["invalid_count"]:
            raise ValueError(f"built manifest did not validate: {validation['invalid']}")
        return manifest
    except Exception as exc:
        logger.error("Failed to build paper-understanding gold manifest: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/curation/audit", response_model=PaperUnderstandingGoldCurationReport)
async def audit_paper_understanding_gold_curation(
    payload: PaperUnderstandingGoldCurationAuditRequest,
):
    try:
        return build_paper_understanding_gold_curation_report(
            [Path(path).expanduser().resolve() for path in payload.paths],
            report_id=payload.report_id,
            targets=payload.targets,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to audit paper-understanding gold curation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/release-readiness/audit", response_model=PaperUnderstandingGoldReleaseReadinessReport)
async def audit_paper_understanding_gold_release_readiness(
    payload: PaperUnderstandingGoldReleaseReadinessRequest,
):
    try:
        return build_paper_understanding_gold_release_readiness_report(
            [Path(path).expanduser().resolve() for path in payload.manifest_paths],
            readiness_id=payload.readiness_id,
            required_splits=payload.required_splits,
            min_ready_per_split=payload.min_ready_per_split,
            require_single_goldset_id=payload.require_single_goldset_id,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to audit paper-understanding gold release readiness: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/release-readiness/package-from-staged-gold",
    response_model=PaperUnderstandingGoldReleasePackageReport,
)
async def package_paper_understanding_gold_release_from_staged_gold(
    payload: PaperUnderstandingGoldReleasePackageFromStagedGoldRequest,
):
    try:
        return build_paper_understanding_gold_release_package_from_staged_gold(
            goldset_id=payload.goldset_id,
            split_manifests=payload.split_manifests,
            release_readiness_out=Path(payload.release_readiness_out).expanduser().resolve(),
            package_id=payload.package_id,
            package_out=Path(payload.package_out).expanduser().resolve() if payload.package_out else None,
            require_ready=payload.require_ready,
            required_splits=payload.required_splits,
            min_ready_per_split=payload.min_ready_per_split,
            require_single_goldset_id=payload.require_single_goldset_id,
        )
    except Exception as exc:
        logger.error("Failed to package paper-understanding gold release from staged gold: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/release-readiness/package-from-split-plan",
    response_model=PaperUnderstandingGoldReleasePackageReport,
)
async def package_paper_understanding_gold_release_from_split_plan(
    payload: PaperUnderstandingGoldReleasePackageFromSplitPlanRequest,
):
    try:
        return build_paper_understanding_gold_release_package_from_split_plan(
            goldset_id=payload.goldset_id,
            split_plan_path=Path(payload.split_plan_path).expanduser().resolve(),
            release_readiness_out=Path(payload.release_readiness_out).expanduser().resolve(),
            package_id=payload.package_id,
            package_out=Path(payload.package_out).expanduser().resolve() if payload.package_out else None,
            require_ready=payload.require_ready,
            required_splits=payload.required_splits,
            min_ready_per_split=payload.min_ready_per_split,
            require_single_goldset_id=payload.require_single_goldset_id,
        )
    except Exception as exc:
        logger.error("Failed to package paper-understanding gold release from split plan: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/release-readiness/split-plan-from-staged-gold",
    response_model=PaperUnderstandingGoldReleaseSplitPlanReport,
)
async def build_paper_understanding_gold_release_split_plan(
    payload: PaperUnderstandingGoldReleaseSplitPlanRequest,
):
    try:
        return build_paper_understanding_gold_release_split_plan_from_staging_manifest(
            staging_manifest_path=Path(payload.staging_manifest_path).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            manifest_out_dir=Path(payload.manifest_out_dir).expanduser().resolve()
            if payload.manifest_out_dir
            else None,
            plan_id=payload.plan_id,
            split_names=payload.split_names,
            min_ready_per_split=payload.min_ready_per_split,
            require_ready=payload.require_ready,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to build paper-understanding gold release split plan: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidate-drafts/from-reviewed-fixtures", response_model=PaperUnderstandingGoldCandidateDraftManifest)
async def draft_paper_understanding_gold_from_reviewed_fixtures(
    payload: PaperUnderstandingGoldReviewedFixturesDraftRequest,
):
    try:
        return write_paper_understanding_gold_candidate_drafts(
            reviewed_dir=Path(payload.reviewed_dir).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            paper_id=payload.paper_id,
            run_id=payload.run_id,
            claim_id=payload.claim_id,
        )
    except Exception as exc:
        logger.error("Failed to draft paper-understanding gold from reviewed fixtures: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidate-drafts/from-teacher-verification", response_model=PaperUnderstandingGoldCandidateDraftManifest)
async def draft_paper_understanding_gold_from_teacher_verification(
    payload: PaperUnderstandingGoldTeacherVerificationDraftRequest,
):
    try:
        return write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
            paths=[Path(path).expanduser().resolve() for path in payload.paths],
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            require_accepted=payload.require_accepted,
        )
    except Exception as exc:
        logger.error("Failed to draft paper-understanding gold from teacher verification: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/from-teacher-verification/curation-package",
    response_model=PaperUnderstandingGoldTeacherVerificationCurationPackage,
)
async def package_paper_understanding_gold_teacher_verification_curation(
    payload: PaperUnderstandingGoldTeacherVerificationCurationPackageRequest,
):
    try:
        return write_paper_understanding_gold_teacher_verification_curation_package(
            paths=[Path(path).expanduser().resolve() for path in payload.paths],
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            require_accepted=payload.require_accepted,
            report_id=payload.report_id,
            curation_report_out=(
                Path(payload.curation_report_out).expanduser().resolve()
                if payload.curation_report_out
                else None
            ),
            package_out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to package paper-understanding gold teacher verification curation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/from-teacher-verification/reviewer-handoff-package",
    response_model=PaperUnderstandingGoldReviewerHandoffPackage,
)
async def package_paper_understanding_gold_reviewer_handoff(
    payload: PaperUnderstandingGoldReviewerHandoffPackageRequest,
):
    try:
        return write_paper_understanding_gold_reviewer_handoff_package(
            paths=[Path(path).expanduser().resolve() for path in payload.paths],
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            require_accepted=payload.require_accepted,
            package_id=payload.package_id,
            report_id=payload.report_id,
            reviewer_id=payload.reviewer_id,
            review_notes=payload.review_notes,
            reviewer_guide_out=Path(payload.reviewer_guide_out).expanduser().resolve() if payload.reviewer_guide_out else None,
            package_out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to package paper-understanding gold reviewer handoff: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidate-drafts/patch", response_model=PaperUnderstandingGoldCandidateDraftPatchResult)
async def patch_paper_understanding_gold_candidate_draft_endpoint(
    payload: PaperUnderstandingGoldCandidateDraftPatchRequest,
):
    try:
        return patch_paper_understanding_gold_candidate_draft(payload)
    except Exception as exc:
        logger.error("Failed to patch paper-understanding gold candidate draft: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidate-drafts/patch-template", response_model=PaperUnderstandingGoldCandidateDraftPatchTemplate)
async def build_paper_understanding_gold_candidate_draft_patch_template_endpoint(
    payload: PaperUnderstandingGoldCandidateDraftPatchTemplateRequest,
):
    try:
        return build_paper_understanding_gold_candidate_draft_patch_template(payload)
    except Exception as exc:
        logger.error("Failed to build paper-understanding gold candidate draft patch template: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/patch-templates/build",
    response_model=PaperUnderstandingGoldCandidateDraftPatchTemplateManifest,
)
async def build_paper_understanding_gold_candidate_draft_patch_template_manifest_endpoint(
    payload: PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest,
):
    try:
        return write_paper_understanding_gold_candidate_draft_patch_template_manifest(payload)
    except Exception as exc:
        logger.error("Failed to build paper-understanding gold candidate draft patch templates: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/patch-templates/apply",
    response_model=PaperUnderstandingGoldCandidateDraftPatchResultManifest,
)
async def apply_paper_understanding_gold_candidate_draft_patch_templates_endpoint(
    payload: PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest,
):
    try:
        return write_paper_understanding_gold_candidate_draft_patch_result_manifest(payload)
    except Exception as exc:
        logger.error("Failed to apply paper-understanding gold candidate draft patch templates: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/reviewer-handoff/apply",
    response_model=PaperUnderstandingGoldReviewerHandoffApplyPackage,
)
async def apply_paper_understanding_gold_reviewer_handoff_endpoint(
    payload: PaperUnderstandingGoldReviewerHandoffApplyRequest,
):
    try:
        return apply_paper_understanding_gold_reviewer_handoff_package(payload)
    except ReviewerHandoffApplyRequiresEditedError as exc:
        logger.error("Blocked paper-understanding gold reviewer handoff apply package: %s", exc)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Reviewer handoff apply requires edited patch templates.",
                "findings": exc.findings,
            },
        ) from exc
    except ValueError as exc:
        logger.error("Blocked paper-understanding gold reviewer handoff apply package: %s", exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to apply paper-understanding gold reviewer handoff package: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/reviewer-handoff/stage",
    response_model=PaperUnderstandingGoldReviewerHandoffStagePackage,
)
async def stage_paper_understanding_gold_reviewer_handoff_endpoint(
    payload: PaperUnderstandingGoldReviewerHandoffStageRequest,
):
    try:
        return stage_paper_understanding_gold_reviewer_handoff_apply_package(payload)
    except Exception as exc:
        logger.error("Failed to stage paper-understanding gold reviewer handoff apply package: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/reviewer-handoff/release-prep",
    response_model=PaperUnderstandingGoldReviewerHandoffReleasePrepPackage,
)
async def prep_paper_understanding_gold_reviewer_handoff_release_endpoint(
    payload: PaperUnderstandingGoldReviewerHandoffReleasePrepRequest,
):
    try:
        return build_paper_understanding_gold_reviewer_handoff_release_prep_package(payload)
    except Exception as exc:
        logger.error("Failed to prep paper-understanding gold reviewer handoff release package: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidate-drafts/curation/audit", response_model=PaperUnderstandingGoldCandidateDraftCurationReport)
async def audit_paper_understanding_gold_candidate_drafts(
    payload: PaperUnderstandingGoldCandidateDraftCurationAuditRequest,
):
    try:
        return build_paper_understanding_gold_candidate_draft_curation_report(
            draft_paths=[Path(path).expanduser().resolve() for path in payload.draft_paths],
            report_id=payload.report_id,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to audit paper-understanding gold candidate drafts: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/curation/progress",
    response_model=PaperUnderstandingGoldCandidateDraftCurationProgressReport,
)
async def audit_paper_understanding_gold_candidate_draft_curation_progress(
    payload: PaperUnderstandingGoldCandidateDraftCurationProgressRequest,
):
    try:
        return build_paper_understanding_gold_candidate_draft_curation_progress_report(
            curation_package_path=Path(payload.curation_package_path).expanduser().resolve(),
            patch_template_paths=[Path(path).expanduser().resolve() for path in payload.patch_template_paths],
            patch_result_paths=[Path(path).expanduser().resolve() for path in payload.patch_result_paths],
            staged_paths=[Path(path).expanduser().resolve() for path in payload.staged_paths],
            report_id=payload.report_id,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to audit paper-understanding gold candidate draft curation progress: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/candidate-drafts/curation/tasks/export",
    response_model=PaperUnderstandingGoldCurationTaskExportReport,
)
async def export_paper_understanding_gold_curation_tasks(
    payload: PaperUnderstandingGoldCurationTaskExportRequest,
):
    try:
        return build_paper_understanding_gold_curation_task_export_report(
            curation_package_path=Path(payload.curation_package_path).expanduser().resolve(),
            patch_template_paths=[Path(path).expanduser().resolve() for path in payload.patch_template_paths],
            patch_result_paths=[Path(path).expanduser().resolve() for path in payload.patch_result_paths],
            staged_paths=[Path(path).expanduser().resolve() for path in payload.staged_paths],
            export_id=payload.export_id,
            progress_report_out=(
                Path(payload.progress_report_out).expanduser().resolve()
                if payload.progress_report_out
                else None
            ),
            csv_out=Path(payload.csv_out).expanduser().resolve() if payload.csv_out else None,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
    except Exception as exc:
        logger.error("Failed to export paper-understanding gold curation tasks: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidate-drafts/stage", response_model=PaperUnderstandingGoldStagingManifest)
async def stage_paper_understanding_gold_candidate_drafts(
    payload: PaperUnderstandingGoldCandidateDraftStagingRequest,
):
    try:
        return stage_paper_understanding_gold_from_candidate_drafts(
            draft_paths=[Path(path).expanduser().resolve() for path in payload.draft_paths],
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            require_ready=payload.require_ready,
        )
    except Exception as exc:
        logger.error("Failed to stage paper-understanding gold candidate drafts: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidate-drafts/stage-from-patch-results", response_model=PaperUnderstandingGoldStagingManifest)
async def stage_paper_understanding_gold_candidate_drafts_from_patch_results(
    payload: PaperUnderstandingGoldPatchResultStagingRequest,
):
    try:
        return stage_paper_understanding_gold_from_patch_results(
            patch_result_paths=[Path(path).expanduser().resolve() for path in payload.patch_result_paths],
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            require_ready=payload.require_ready,
        )
    except Exception as exc:
        logger.error("Failed to stage paper-understanding gold candidate drafts from patch results: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
