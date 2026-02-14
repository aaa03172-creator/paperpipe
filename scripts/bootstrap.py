
import asyncio
import os
import json
import logging
import argparse
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

# Import Pydantic Models for Validation
from src.schemas.agent_artifacts import ClaimSet, ScientificClaim, EvidenceSpan, FeedbackCase
from src.config import load_config

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("bootstrap")

# Load Secrets
env_path = Path(__file__).parent.parent / ".env"
logger.info(f"Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    logger.warning("⚠️  ANTHROPIC_API_KEY not found in .env. Teacher mode will fail if not provided.")
else:
    logger.info(f"✅ ANTHROPIC_API_KEY loaded: {ANTHROPIC_API_KEY[:10]}...")

# Constants
BACKEND_URL = "http://127.0.0.1:8000"
SYSTEM_PROMPT_EDITOR = """You are an Elite Senior Biomedical Editor and Auditor. 
Your task is to review a preliminary "Claim Extraction" performed by a junior AI student.

STRICT RULES (ZERO HALLUCINATION):
1.  **Verification**: Every single claim MUST be supported by the provided text.
2.  **Evidence**: You must enforce that every claim has a precise `EvidenceSpan` with `quote` (exact substring) and `page`.
3.  **Correction**: 
    - If a claim is valid but the evidence is vague, FIX the evidence.
    - If a claim is unsupported or hallucinated, DELETE it.
    - If the confidence is high (>0.8) but evidence is missing, DOWNGRADE confidence or DELETE.
4.  **Formatting**: Output ONLY valid JSON matching the provided schema. Do not output markdown code blocks.
"""

async def run_student_job(paper_id: str) -> Dict[str, Any]:
    """
    Step 1: Student (Local Pipeline)
    Triggers the standard DeepRead job and waits for artifacts.
    """
    import requests
    
    logger.info(f"🎓 Student: Starting DeepRead for {paper_id}...")
    
    # Trigger Job
    try:
        resp = requests.post(f"{BACKEND_URL}/jobs/deepread?paper_id={paper_id}")
        resp.raise_for_status()
        data = resp.json()
        job_id = data['job_id']
        run_id = data['run_id']
        logger.info(f"   Job ID: {job_id}, Run ID: {run_id}")
    except Exception as e:
        logger.error(f"Failed to trigger job: {e}")
        return None

    # Poll for completion (Simple polling for bootstrapping script)
    # in production we might use SSE, but here polling status/artifacts is easier
    max_retries = 300  # Increased to 10 minutes (was 60/2min)
    for i in range(max_retries):
        await asyncio.sleep(2)
        # Check if artifacts exist
        artifact_path = Path(f"storage/artifacts/{paper_id}/{run_id}/claimset.json")
        if artifact_path.exists():
            logger.info("   Student finished. Artifacts found.")
            return {"run_id": run_id, "artifact_path": artifact_path}
            
    logger.error("Student timed out.")
    return None

async def run_teacher_review(student_claims: Dict, doc_text: str, context: str) -> Optional[ClaimSet]:
    """
    Step 2: Teacher (Claude 3.5 Sonnet)
    Reviews and corrects the student's work.
    """
    if not ANTHROPIC_API_KEY:
        logger.error("Cannot run Teacher without API Key.")
        return None

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    
    # Construct Payload
    student_json = json.dumps(student_claims, indent=2)
    
    user_message = f"""
CONTEXT:
{context}

PAPER TEXT (Excerpt):
{doc_text[:15000]} ... (truncated)

STUDENT'S EXTRACTED CLAIMS:
{student_json}

TASK:
Review the student's claims. 
- Remove hallucinations.
- Ensure every claim has valid evidence quotes from the text.
- Return the CORRECTED JSON object matching the Schema.
"""

    try:
        logger.info("👨‍🏫 Teacher: Claude is reviewing...")
        message = await client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=4096,
            temperature=0, # Deterministic
            system=SYSTEM_PROMPT_EDITOR,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        content = message.content[0].text
        # Clean JSON
        if "```json" in content:
             content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
             content = content.split("```")[1].split("```")[0].strip()
            
        data = json.loads(content)
        return ClaimSet(**data)
        
    except Exception as e:
        logger.error(f"Teacher failed: {e}")
        return None

def auditor_check(claims: ClaimSet) -> bool:
    """
    Step 3: Auditor (Deterministic Rules)
    """
    logger.info("🕵️ Auditor: Validating...")
    
    if not claims.claims:
        logger.warning("   Fail: No claims returned.")
        return False
        
    for c in claims.claims:
        # Rule 1: High confidence requires evidence
        if c.confidence > 0.8 and not c.evidence_spans:
            logger.warning(f"   Fail: High confidence claim {c.claim_id} lacks evidence.")
            return False
            
        # Rule 2: Evidence must have quote
        for ev in c.evidence_spans:
            if not ev.quote and not ev.raw_text:
                logger.warning(f"   Fail: Evidence in {c.claim_id} lacks quote/text.")
                return False
                
    logger.info("   Pass: All checks green.")
    return True

async def inject_golden_data(paper_id: str, run_id: str, golden_claims: ClaimSet):
    """
    Step 4: Feedback Injection
    """
    import requests
    logger.info("💉 Injecting Golden Data...")
    
    # usage: FeedbackCase(paper_id, run_id, user_correction, accepted)
    # We treat the Teacher's output as the "Correction" for the whole set
    
    correction_text = golden_claims.model_dump_json(indent=2)
    
    payload = {
        "paper_id": paper_id,
        "run_id": run_id,
        "user_correction": f"Golden Shot by Claude 3.5:\n{correction_text}",
        "accepted": False # It's a correction, so strictly speaking the Student's orginal was 'not accepted' fully, or we can say True if we replace it. 
                          # The prompt said "Set accepted=False".
    }
    
    try:
        resp = requests.post(f"{BACKEND_URL}/feedback", json=payload)
        if resp.status_code == 200:
            logger.info("   ✅ Success: Golden data saved to feedback DB.")
        else:
            logger.error(f"   ❌ Failed to save feedback: {resp.text}")
    except Exception as e:
        logger.error(f"   ❌ API Error: {e}")

async def process_paper(paper_id: str):
    logger.info(f"--- Processing {paper_id} ---")
    
    # 1. Student
    student_result = await run_student_job(paper_id)
    if not student_result:
        return
        
    run_id = student_result["run_id"]
    
    # Load Student Artifacts
    try:
        with open(student_result["artifact_path"], "r") as f:
            student_claims_dict = json.load(f)
            
        # Load Document Text (for Teacher Context)
        doc_artifact_path = student_result["artifact_path"].parent / "document_artifact.json"
        with open(doc_artifact_path, "r") as f:
            doc_data = json.load(f)
            # Reconstruct text
            doc_text = ""
            for sec in doc_data.get("sections", []):
                doc_text += f"\n## {sec['name']}\n{sec['text']}\n"
    except Exception as e:
        logger.error(f"Failed to load artifacts: {e}")
        return

    # 2. Teacher
    teacher_claims = await run_teacher_review(student_claims_dict, doc_text, "Biomedical Paper Analysis")
    
    if not teacher_claims:
        logger.warning("Teacher returned no result. Skipping.")
        return

    # 3. Auditor
    if auditor_check(teacher_claims):
        # 4. Feedback
        await inject_golden_data(paper_id, run_id, teacher_claims)
    else:
        logger.warning("Auditor rejected Teacher's output. Manual review needed.")

async def main():
    parser = argparse.ArgumentParser(description="PaperPipe Bootstrap Orchestrator")
    parser.add_argument("--papers", nargs="+", help="List of paper IDs to process", required=True)
    args = parser.parse_args()
    
    # Process sequentially to avoid rate limits
    for pid in args.papers:
        await process_paper(pid)

if __name__ == "__main__":
    # Ensure loop is handled correctly
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
