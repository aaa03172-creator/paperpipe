from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.schemas.evidence_grounding_scorecard import (
    EvidenceGroundingCandidateConfig,
    EvidenceGroundingScorecard,
    EvidenceGroundingScorecardBuildRequest,
)
from src.services.evidence_grounding_scorecard import (
    build_evidence_grounding_scorecard_from_run_dir,
    write_evidence_grounding_scorecard,
    write_evidence_grounding_scorecard_to_path,
)
from src.services.path_masking import mask_local_paths_in_text
from src.services.paper_understanding_gold_validation import validate_gold_path


logger = logging.getLogger("paperpipe.backend")
scorecard_router = APIRouter(prefix="/scorecards", tags=["evidence-grounding"])
router = APIRouter(prefix="/evidence-grounding", tags=["evidence-grounding"])


@scorecard_router.post("/build", response_model=EvidenceGroundingScorecard)
async def build_evidence_grounding_scorecard(
    payload: EvidenceGroundingScorecardBuildRequest,
):
    try:
        gold_path = (
            Path(payload.paper_understanding_gold_path).expanduser().resolve()
            if payload.paper_understanding_gold_path
            else None
        )
        gold = None
        if gold_path is not None:
            gold, error = validate_gold_path(gold_path)
            if gold is None:
                raise ValueError(
                    f"paper_understanding_gold_path is invalid: path={gold_path} error={error or 'unknown validation error'}"
                )
        run_dir = Path(payload.run_dir).expanduser().resolve()
        scorecard = build_evidence_grounding_scorecard_from_run_dir(
            run_dir,
            paper_understanding_gold=gold,
            paper_understanding_gold_source=str(gold_path) if gold_path is not None else None,
            candidate_config=_candidate_config_or_none(payload.candidate_config),
        )
        if payload.write:
            if payload.out:
                write_evidence_grounding_scorecard_to_path(
                    scorecard,
                    Path(payload.out).expanduser().resolve(),
                    run_dir=run_dir,
                )
            else:
                write_evidence_grounding_scorecard(scorecard, run_dir)
        return _mask_scorecard_response_paths(scorecard)
    except ValueError as exc:
        detail = mask_local_paths_in_text(str(exc))
        logger.warning("Rejected evidence-grounding scorecard build request: %s", detail)
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:
        detail = mask_local_paths_in_text(str(exc))
        logger.error("Failed to build evidence-grounding scorecard: %s", detail)
        raise HTTPException(status_code=500, detail=detail) from exc


def _candidate_config_or_none(
    config: EvidenceGroundingCandidateConfig | None,
) -> EvidenceGroundingCandidateConfig | None:
    if config is not None and config.has_lineage():
        return config
    return None


def _mask_scorecard_response_paths(scorecard: EvidenceGroundingScorecard) -> EvidenceGroundingScorecard:
    return EvidenceGroundingScorecard.model_validate(
        _mask_local_path_payload(scorecard.model_dump(mode="json"))
    )


def _mask_local_path_payload(value: Any) -> Any:
    if isinstance(value, str):
        return mask_local_paths_in_text(value)
    if isinstance(value, list):
        return [_mask_local_path_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _mask_local_path_payload(item) for key, item in value.items()}
    return value


router.include_router(scorecard_router)
