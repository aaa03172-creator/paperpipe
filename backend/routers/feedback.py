from fastapi import APIRouter, HTTPException
import json
import logging
from datetime import datetime
from pathlib import Path

from src.schemas.agent_artifacts import FeedbackCase

logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/feedback", tags=["feedback"])

FEEDBACK_FILE = Path("storage/feedback.jsonl")

@router.post("")
async def submit_feedback(feedback: FeedbackCase):
    try:
        # timestamp
        if not feedback.timestamp:
            feedback.timestamp = datetime.utcnow().isoformat()
            
        # Ensure directory
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Append to JSONL
        with open(FEEDBACK_FILE, "a") as f:
            f.write(feedback.model_dump_json() + "\n")
            
        logger.info(f"Feedback saved for run {feedback.run_id}")
        return {"status": "saved", "message": "Feedback recorded successfully."}
        
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
