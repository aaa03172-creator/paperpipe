from fastapi import APIRouter, HTTPException, Query
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.agent_artifacts import FeedbackCase
from src.agents.feedback_retriever import FeedbackRetriever

logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/feedback", tags=["feedback"])

FEEDBACK_FILE = Path("storage/feedback.jsonl")
_feedback_retriever: FeedbackRetriever | None = None


def _get_feedback_retriever() -> FeedbackRetriever:
    global _feedback_retriever
    if _feedback_retriever is None:
        _feedback_retriever = FeedbackRetriever()
    return _feedback_retriever

@router.post("")
async def submit_feedback(feedback: FeedbackCase):
    try:
        # timestamp
        if not feedback.timestamp:
            feedback.timestamp = datetime.now(timezone.utc).isoformat()
            
        # Ensure directory
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Append to JSONL (Golden Data Backup)
        with open(FEEDBACK_FILE, "a") as f:
            f.write(feedback.model_dump_json() + "\n")
            
        logger.info(f"Feedback saved for run {feedback.run_id}")

        # [NEW] Dynamic Few-Shot Injection: Index to ChromaDB if accepted
        if feedback.accepted:
            success = _get_feedback_retriever().add_feedback(feedback)
            if success:
                logger.info(f"Feedback {feedback.feedback_id} from run {feedback.run_id} indexed for future few-shot injection.")
            else:
                logger.warning(f"Feedback {feedback.feedback_id} was saved to file but failed to index in ChromaDB.")

        return {"status": "saved", "message": "Feedback recorded successfully."}
        
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[FeedbackCase])
async def list_feedback(
    paper_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    if not FEEDBACK_FILE.exists():
        return []

    try:
        rows = [
            line.strip()
            for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception as e:
        logger.error(f"Failed to read feedback file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    out: list[FeedbackCase] = []
    for raw in reversed(rows):
        try:
            payload = json.loads(raw)
            case = FeedbackCase.model_validate(payload)
        except Exception:
            continue

        if paper_id and case.paper_id != paper_id:
            continue
        if run_id and case.run_id != run_id:
            continue

        out.append(case)
        if len(out) >= limit:
            break

    return out
