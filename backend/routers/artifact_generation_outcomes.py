from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from src.schemas.artifact_generation_outcome import ArtifactGenerationOutcome
from src.services.artifact_generation_outcomes import (
    append_artifact_generation_outcome,
    load_artifact_generation_outcomes,
)
from src.services.runtime_paths import artifact_generation_outcome_log_path


logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/artifact-generation-outcomes", tags=["artifact-generation-outcomes"])

ARTIFACT_GENERATION_OUTCOME_FILE = None


def _artifact_generation_outcome_file():
    return ARTIFACT_GENERATION_OUTCOME_FILE or artifact_generation_outcome_log_path()


@router.post("")
async def submit_artifact_generation_outcome(payload: ArtifactGenerationOutcome):
    try:
        append_artifact_generation_outcome(
            payload,
            log_path=_artifact_generation_outcome_file(),
        )

        logger.info(
            "Artifact generation outcome saved for artifact_type=%s artifact_id=%s decision=%s",
            payload.artifact_type,
            payload.artifact_id,
            payload.decision,
        )
        return {"status": "saved", "message": "Artifact generation outcome recorded successfully."}
    except Exception as exc:
        logger.error("Failed to save artifact generation outcome: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=list[ArtifactGenerationOutcome])
async def list_artifact_generation_outcomes(
    artifact_type: str | None = Query(default=None),
    artifact_id: str | None = Query(default=None),
    paper_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    dna_id: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    downstream_use: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    try:
        rows = load_artifact_generation_outcomes(log_path=_artifact_generation_outcome_file())
    except Exception as exc:
        logger.error("Failed to read artifact generation outcomes file: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    out: list[ArtifactGenerationOutcome] = []
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
        if decision and case.decision != decision:
            continue
        if downstream_use and case.downstream_use != downstream_use:
            continue

        out.append(case)
        if len(out) >= limit:
            break

    return out
