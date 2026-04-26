from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from src.schemas.artifact_review_feedback import ArtifactReviewFeedbackCase
from src.services.artifact_review_feedback import append_artifact_review_feedback, load_artifact_review_feedback
from src.services.runtime_paths import artifact_review_feedback_log_path


logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/artifact-feedback", tags=["artifact-feedback"])

ARTIFACT_FEEDBACK_FILE = None


def _artifact_feedback_file():
    return ARTIFACT_FEEDBACK_FILE or artifact_review_feedback_log_path()


@router.post("")
async def submit_artifact_feedback(feedback: ArtifactReviewFeedbackCase):
    try:
        append_artifact_review_feedback(
            feedback,
            log_path=_artifact_feedback_file(),
        )

        logger.info(
            "Artifact review feedback saved for artifact_type=%s artifact_id=%s",
            feedback.artifact_type,
            feedback.artifact_id,
        )
        return {"status": "saved", "message": "Artifact review feedback recorded successfully."}
    except Exception as exc:
        logger.error("Failed to save artifact review feedback: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=list[ArtifactReviewFeedbackCase])
async def list_artifact_feedback(
    artifact_type: str | None = Query(default=None),
    artifact_id: str | None = Query(default=None),
    paper_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    dna_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    try:
        rows = load_artifact_review_feedback(log_path=_artifact_feedback_file())
    except Exception as exc:
        logger.error("Failed to read artifact review feedback file: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    out: list[ArtifactReviewFeedbackCase] = []
    for case in reversed(rows):
        if artifact_type and case.artifact_type != artifact_type:
            continue
        if artifact_id and case.artifact_id != artifact_id:
            continue
        if paper_id and case.paper_id != paper_id:
            continue
        if run_id and case.run_id != run_id:
            continue
        if dna_id and case.dna_id != dna_id:
            continue

        out.append(case)
        if len(out) >= limit:
            break

    return out
