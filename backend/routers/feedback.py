from fastapi import APIRouter, HTTPException
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.agent_artifacts import FeedbackCase
from src.agents.feedback_retriever import FeedbackRetriever

logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/feedback", tags=["feedback"])

FEEDBACK_FILE = Path("storage/feedback.jsonl")

# Singleton or instantiated per request
feedback_retriever = FeedbackRetriever()

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
            success = feedback_retriever.add_feedback(feedback)
            if success:
                logger.info(f"Feedback {feedback.feedback_id} from run {feedback.run_id} indexed for future few-shot injection.")
            else:
                logger.warning(f"Feedback {feedback.feedback_id} was saved to file but failed to index in ChromaDB.")

        return {"status": "saved", "message": "Feedback recorded successfully."}
        
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
