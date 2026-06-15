from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from src.schemas.artifact_review_feedback import ArtifactReviewFeedbackCase
from src.schemas.claim_evidence_correction import (
    ClaimEvidenceCorrectionCase,
    ClaimEvidenceCorrectionEvalCandidateExport,
    ClaimEvidenceCorrectionEvalReviewDecision,
    ClaimEvidenceCorrectionEvalReviewManifest,
    ClaimEvidenceCorrectionFeedbackExportStatus,
    ClaimEvidenceCorrectionRepairPlan,
    ClaimEvidenceCorrectionRepairPatchTemplate,
    ClaimEvidenceCorrectionRepairedLogDraft,
    ClaimEvidenceEvalReviewImportFromCorrectionsRequest,
    ClaimEvidenceEvalReviewImportRequest,
    ClaimEvidenceEvalReviewQueueItem,
    ClaimEvidenceEvalReviewQueueResponse,
    ClaimEvidenceEvalReviewResolveRequest,
    ClaimEvidenceReviewedFixturesPackageRequest,
    ClaimEvidenceReviewedFixturesPackageResponse,
)
from src.services.artifact_review_feedback import append_artifact_review_feedback
from src.services.claim_evidence_corrections import (
    append_claim_evidence_correction,
    build_claim_evidence_eval_candidate_export,
    build_claim_evidence_correction_repair_plan,
    build_claim_evidence_correction_repair_patch_template,
    build_claim_evidence_correction_repaired_log_draft,
    claim_evidence_eval_candidate_export_replayability_findings,
    list_claim_evidence_eval_review_queue,
    load_claim_evidence_eval_candidate_export_from_path,
    load_claim_evidence_corrections,
    load_claim_evidence_corrections_with_diagnostics,
    resolve_claim_evidence_eval_review_record,
    write_claim_evidence_eval_review_intake,
    write_claim_evidence_reviewed_eval_fixtures_sidecar,
)
from src.services.runtime_paths import artifact_review_feedback_log_path, claim_evidence_correction_log_path, goldset_root


logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/claim-evidence-corrections", tags=["claim-evidence-corrections"])

CLAIM_EVIDENCE_CORRECTION_FILE = None
CLAIM_EVIDENCE_ARTIFACT_FEEDBACK_FILE = None
CLAIM_EVIDENCE_REVIEWED_FIXTURES_DIR = None


def _correction_file():
    return CLAIM_EVIDENCE_CORRECTION_FILE or claim_evidence_correction_log_path()


def _resolved_path_text(path_like) -> str:
    path = Path(path_like).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return str(path.resolve())


def _artifact_feedback_file():
    return CLAIM_EVIDENCE_ARTIFACT_FEEDBACK_FILE or artifact_review_feedback_log_path()


def _reviewed_fixtures_dir(payload: ClaimEvidenceReviewedFixturesPackageRequest) -> Path:
    if payload.reviewed_dir:
        return Path(payload.reviewed_dir).expanduser().resolve()
    root = Path(payload.goldset_root).expanduser().resolve() if payload.goldset_root else goldset_root()
    return root / "reviews" / "claim_evidence_eval_candidates" / "reviewed"


def _review_records_dir(
    *,
    records_dir: str | None = None,
    goldset_root_override: str | None = None,
) -> Path:
    if records_dir:
        return Path(records_dir).expanduser().resolve()
    root = Path(goldset_root_override).expanduser().resolve() if goldset_root_override else goldset_root()
    return root / "reviews" / "claim_evidence_eval_candidates"


def _replayability_failure_detail(
    export: ClaimEvidenceCorrectionEvalCandidateExport,
    findings: list[str],
) -> dict:
    return {
        "message": "Claim/evidence eval candidate export is not replayable evidence.",
        "findings": findings,
        "source_correction_log_path": (
            _resolved_path_text(export.source_correction_log_path)
            if export.source_correction_log_path
            else None
        ),
        "source_invalid_record_count": export.source_invalid_record_count,
        "source_invalid_record_diagnostics": [
            item.model_dump(mode="json") for item in export.source_invalid_record_diagnostics
        ],
    }


def _scorecard_artifact_id(correction: ClaimEvidenceCorrectionCase) -> str:
    return f"{correction.paper_id}:{correction.run_id}:evidence_grounding_scorecard"


def _build_artifact_feedback(correction: ClaimEvidenceCorrectionCase) -> ArtifactReviewFeedbackCase:
    payload = dict(
        artifact_type="evidence_grounding_scorecard",
        artifact_id=_scorecard_artifact_id(correction),
        paper_id=correction.paper_id,
        run_id=correction.run_id,
        decision="correct",
        reason_code="claim_evidence_correction",
        actor_id=correction.reviewer_id,
        note=correction.after_claim_text,
        metadata={
            "source": "claim_evidence_correction",
            "correction_id": correction.correction_id,
            "claim_id": correction.claim_id,
            "field_path": correction.field_path,
            "reason_codes": correction.reason_codes,
            "before_claim_text": correction.before_claim_text,
            "before_evidence_refs": [item.model_dump(mode="json") for item in correction.before_evidence_refs],
            "after_evidence_refs": [item.model_dump(mode="json") for item in correction.after_evidence_refs],
            "correction_metadata": correction.metadata,
        },
    )
    if correction.related_feedback_id:
        payload["feedback_id"] = correction.related_feedback_id
    return ArtifactReviewFeedbackCase(**payload)


def _maybe_link_artifact_feedback(correction: ClaimEvidenceCorrectionCase) -> ClaimEvidenceCorrectionCase:
    if not correction.accepted_for_eval:
        return correction
    if correction.related_feedback_id:
        return correction

    feedback = _build_artifact_feedback(correction)
    try:
        saved_feedback = append_artifact_review_feedback(feedback, log_path=_artifact_feedback_file())
    except Exception as exc:
        logger.warning(
            "Failed to export claim/evidence correction to artifact feedback for correction_id=%s: %s",
            correction.correction_id,
            exc,
        )
        return correction.model_copy(update={"feedback_export_status": "pending"})

    return correction.model_copy(
        update={
            "related_feedback_id": saved_feedback.feedback_id,
            "feedback_export_status": "linked",
        }
    )


@router.post("")
async def submit_claim_evidence_correction(correction: ClaimEvidenceCorrectionCase):
    try:
        correction = _maybe_link_artifact_feedback(correction)
        saved = append_claim_evidence_correction(correction, log_path=_correction_file())
        logger.info(
            "Claim/evidence correction saved for paper_id=%s run_id=%s claim_id=%s",
            saved.paper_id,
            saved.run_id,
            saved.claim_id,
        )
        return {
            "status": "saved",
            "message": "Claim/evidence correction recorded successfully.",
            "correction_id": saved.correction_id,
            "related_feedback_id": saved.related_feedback_id,
            "feedback_export_status": saved.feedback_export_status,
        }
    except Exception as exc:
        logger.error("Failed to save claim/evidence correction: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/eval-candidates", response_model=ClaimEvidenceCorrectionEvalCandidateExport)
async def export_claim_evidence_eval_candidates(
    paper_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    claim_id: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    feedback_export_status: ClaimEvidenceCorrectionFeedbackExportStatus | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    require_replayable: bool = Query(
        default=False,
        description="Fail if the export is not sufficient roadmap replay evidence.",
    ),
):
    try:
        (
            rows,
            source_record_count,
            source_invalid_record_count,
            source_invalid_record_diagnostics,
        ) = load_claim_evidence_corrections_with_diagnostics(
            log_path=_correction_file()
        )
        export = build_claim_evidence_eval_candidate_export(
            rows,
            paper_id=paper_id,
            run_id=run_id,
            claim_id=claim_id,
            reason_code=reason_code,
            feedback_export_status=feedback_export_status,
            limit=limit,
            source_correction_log_path=_resolved_path_text(_correction_file()),
            source_record_count=source_record_count,
            source_invalid_record_count=source_invalid_record_count,
            source_invalid_record_diagnostics=source_invalid_record_diagnostics,
        )
        if require_replayable:
            findings = claim_evidence_eval_candidate_export_replayability_findings(export)
            if findings:
                raise HTTPException(
                    status_code=409,
                    detail=_replayability_failure_detail(export, findings),
                )
        return export
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to export claim/evidence eval candidates: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/repair-plan", response_model=ClaimEvidenceCorrectionRepairPlan)
async def export_claim_evidence_correction_repair_plan(
    diagnostic_limit: int = Query(default=100, ge=1, le=500),
):
    try:
        return build_claim_evidence_correction_repair_plan(
            log_path=_correction_file(),
            diagnostic_limit=diagnostic_limit,
        )
    except Exception as exc:
        logger.error("Failed to build claim/evidence correction repair plan: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/repair-patch-template", response_model=ClaimEvidenceCorrectionRepairPatchTemplate)
async def export_claim_evidence_correction_repair_patch_template(
    repair_plan_path: str = Query(..., min_length=1),
):
    try:
        return build_claim_evidence_correction_repair_patch_template(
            repair_plan_path=Path(repair_plan_path),
        )
    except Exception as exc:
        logger.error("Failed to build claim/evidence correction repair patch template: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/repaired-log-draft", response_model=ClaimEvidenceCorrectionRepairedLogDraft)
async def draft_claim_evidence_correction_repaired_log(
    patch_template_path: str = Query(..., min_length=1),
    out_log_path: str | None = Query(default=None),
    summary_out: str | None = Query(default=None),
):
    try:
        return build_claim_evidence_correction_repaired_log_draft(
            patch_template_path=Path(patch_template_path),
            out_log_path=Path(out_log_path) if out_log_path else None,
            summary_out=Path(summary_out) if summary_out else None,
        )
    except Exception as exc:
        logger.error("Failed to draft claim/evidence correction repaired log: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/reviewed-fixtures/package", response_model=ClaimEvidenceReviewedFixturesPackageResponse)
async def package_claim_evidence_reviewed_fixtures(
    payload: ClaimEvidenceReviewedFixturesPackageRequest,
):
    try:
        reviewed_dir = CLAIM_EVIDENCE_REVIEWED_FIXTURES_DIR or _reviewed_fixtures_dir(payload)
        path, fixture_count = write_claim_evidence_reviewed_eval_fixtures_sidecar(
            reviewed_dir=Path(reviewed_dir),
            run_dir=Path(payload.run_dir).expanduser().resolve(),
            paper_id=payload.paper_id,
            run_id=payload.run_id,
            claim_id=payload.claim_id,
        )
        return ClaimEvidenceReviewedFixturesPackageResponse(
            message="Claim/evidence reviewed eval fixtures packaged successfully.",
            path=str(path),
            fixture_count=fixture_count,
        )
    except Exception as exc:
        logger.error("Failed to package claim/evidence reviewed fixtures: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/eval-review-queue/import", response_model=ClaimEvidenceCorrectionEvalReviewManifest)
async def import_claim_evidence_eval_review_queue_api(
    payload: ClaimEvidenceEvalReviewImportRequest,
):
    try:
        export_path = Path(payload.export_path).expanduser().resolve()
        records_dir = _review_records_dir(
            records_dir=payload.records_dir,
            goldset_root_override=payload.goldset_root,
        )
        export = load_claim_evidence_eval_candidate_export_from_path(export_path)
        if payload.require_replayable:
            findings = claim_evidence_eval_candidate_export_replayability_findings(export)
            if findings:
                raise HTTPException(
                    status_code=409,
                    detail=_replayability_failure_detail(export, findings),
                )
        return write_claim_evidence_eval_review_intake(
            export,
            records_dir=records_dir,
            source_export_path=export_path,
            overwrite=payload.overwrite,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to import claim/evidence eval candidates into review queue: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/eval-review-queue/import-from-corrections", response_model=ClaimEvidenceCorrectionEvalReviewManifest)
async def import_claim_evidence_eval_review_queue_from_corrections_api(
    payload: ClaimEvidenceEvalReviewImportFromCorrectionsRequest,
):
    try:
        (
            rows,
            source_record_count,
            source_invalid_record_count,
            source_invalid_record_diagnostics,
        ) = load_claim_evidence_corrections_with_diagnostics(
            log_path=_correction_file()
        )
        export = build_claim_evidence_eval_candidate_export(
            rows,
            paper_id=payload.paper_id,
            run_id=payload.run_id,
            claim_id=payload.claim_id,
            reason_code=payload.reason_code,
            feedback_export_status=payload.feedback_export_status,
            limit=payload.limit,
            source_correction_log_path=_resolved_path_text(_correction_file()),
            source_record_count=source_record_count,
            source_invalid_record_count=source_invalid_record_count,
            source_invalid_record_diagnostics=source_invalid_record_diagnostics,
        )
        if payload.require_replayable:
            findings = claim_evidence_eval_candidate_export_replayability_findings(export)
            if findings:
                raise HTTPException(
                    status_code=409,
                    detail=_replayability_failure_detail(export, findings),
                )
        records_dir = _review_records_dir(
            records_dir=payload.records_dir,
            goldset_root_override=payload.goldset_root,
        )
        return write_claim_evidence_eval_review_intake(
            export,
            records_dir=records_dir,
            source_export_path=None,
            overwrite=payload.overwrite,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to import claim/evidence corrections into review queue: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/eval-review-queue", response_model=ClaimEvidenceEvalReviewQueueResponse)
async def list_claim_evidence_eval_review_queue_api(
    goldset_root_path: str | None = Query(default=None, alias="goldset_root"),
    records_dir: str | None = Query(default=None),
    include_resolved: bool = Query(default=False),
):
    try:
        resolved_records_dir = _review_records_dir(records_dir=records_dir, goldset_root_override=goldset_root_path)
        rows = list_claim_evidence_eval_review_queue(
            resolved_records_dir,
            include_resolved=include_resolved,
        )
        items = [ClaimEvidenceEvalReviewQueueItem.model_validate(row) for row in rows]
        return ClaimEvidenceEvalReviewQueueResponse(
            records_dir=str(resolved_records_dir),
            item_count=len(items),
            items=items,
        )
    except Exception as exc:
        logger.error("Failed to list claim/evidence eval review queue: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/eval-review-queue/resolve", response_model=ClaimEvidenceCorrectionEvalReviewDecision)
async def resolve_claim_evidence_eval_review_queue_api(
    payload: ClaimEvidenceEvalReviewResolveRequest,
):
    try:
        records_dir = _review_records_dir(
            records_dir=payload.records_dir,
            goldset_root_override=payload.goldset_root,
        )
        return resolve_claim_evidence_eval_review_record(
            records_dir=records_dir,
            intake_id=payload.intake_id,
            resolution=payload.resolution,
            reviewer_id=payload.reviewer_id,
            notes=payload.notes,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to resolve claim/evidence eval review queue item: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=list[ClaimEvidenceCorrectionCase])
async def list_claim_evidence_corrections(
    paper_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    claim_id: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    accepted_for_eval: bool | None = Query(default=None),
    related_feedback_id: str | None = Query(default=None),
    feedback_export_status: ClaimEvidenceCorrectionFeedbackExportStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    try:
        rows = load_claim_evidence_corrections(log_path=_correction_file())
    except Exception as exc:
        logger.error("Failed to read claim/evidence corrections: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    out: list[ClaimEvidenceCorrectionCase] = []
    for correction in reversed(rows):
        if paper_id and correction.paper_id != paper_id:
            continue
        if run_id and correction.run_id != run_id:
            continue
        if claim_id and correction.claim_id != claim_id:
            continue
        if reason_code and reason_code not in correction.reason_codes:
            continue
        if accepted_for_eval is not None and correction.accepted_for_eval != accepted_for_eval:
            continue
        if related_feedback_id and correction.related_feedback_id != related_feedback_id:
            continue
        if feedback_export_status and correction.feedback_export_status != feedback_export_status:
            continue

        out.append(correction)
        if len(out) >= limit:
            break
    return out
