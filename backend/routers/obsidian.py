from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from pathlib import Path
import json

from src.config import load_config
from src.schemas.agent_artifacts import ClaimSet, StatsReport

logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/obsidian", tags=["obsidian"])

class SyncRequest(BaseModel):
    paper_id: str
    run_id: str

MARKER_START = "<!-- AI_AGENT_START -->"
MARKER_END = "<!-- AI_AGENT_END -->"

def _load_artifact(paper_id: str, run_id: str, filename: str):
    path = Path(f"storage/artifacts/{paper_id}/{run_id}/{filename}")
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)

def _format_markdown(claim_set_data: dict, stats_report_data: dict) -> str:
    """Format Agent Output into verified Markdown."""
    md = []
    md.append(f"{MARKER_START}\n")
    md.append("## 🤖 PaperPipe AI Analysis\n")
    
    # 1. Claims
    if claim_set_data:
        try:
            claims = ClaimSet(**claim_set_data)
            md.append(f"### 🧪 Scientific Claims ({len(claims.claims)})\n")
            for c in claims.claims:
                icon = "🟢" if c.confidence > 0.8 else "🟡" if c.confidence > 0.5 else "🔴"
                md.append(f"#### {icon} {c.type.title()}: {c.statement}\n")
                if c.evidence_spans:
                    quote = c.evidence_spans[0].quote or c.evidence_spans[0].raw_text
                    md.append(f"> \"*{quote}*\" (Page {c.evidence_spans[0].page})\n")
                if c.limitations:
                    md.append(f"**Limitations**: {', '.join(c.limitations)}\n")
                md.append("\n")
        except Exception as e:
            md.append(f"⚠️ Error formatting claims: {e}\n")

    # 2. Stats
    if stats_report_data:
        try:
            stats = StatsReport(**stats_report_data)
            if stats.checks:
                md.append(f"### 📊 Statistical Verification ({len(stats.checks)})\n")
                for check in stats.checks:
                    icon = "✅" if check.verdict == "verified" else "❌" if check.verdict == "inconsistent" else "⚠️"
                    md.append(f"- {icon} **{check.test_type}**: {check.verdict.upper()}\n")
                    if check.notes:
                        md.append(f"  - Note: {check.notes}\n")
        except Exception as e:
            md.append(f"⚠️ Error formatting stats: {e}\n")
            
    md.append(f"\n{MARKER_END}")
    return "".join(md)

@router.post("/sync")
async def sync_to_obsidian(req: SyncRequest):
    config = load_config()
    vault_path = config.paths.obsidian_vault
    
    # 1. Load Artifacts
    claim_set = _load_artifact(req.paper_id, req.run_id, "claimset.json")
    stats_report = _load_artifact(req.paper_id, req.run_id, "stats_report.json")
    
    if not claim_set and not stats_report:
        raise HTTPException(status_code=404, detail="No artifacts found for this run.")
        
    # 2. Generate Content
    new_content = _format_markdown(claim_set, stats_report)
    
    # 3. Find Note
    # Heuristic: Look for any .md file with paper_id in name in vault
    # Assuming paper_id is citekey-like
    target_file = None
    
    # Try exact match first
    # Or search
    candidates = list(vault_path.rglob(f"*{req.paper_id}*.md"))
    if not candidates and "/" in req.paper_id:
             clean_id = req.paper_id.replace("/", "_")
             candidates = list(vault_path.rglob(f"*{clean_id}*.md"))
             
    if not candidates:
        # Create new note in Inbox if not found
        inbox_dir = vault_path / "Inbox"
        inbox_dir.mkdir(exist_ok=True)
        target_file = inbox_dir / f"{req.paper_id}.md"
        with open(target_file, "w") as f:
            f.write(f"# {req.paper_id}\n\nCreated by PaperPipe.\n\n")
    else:
        target_file = candidates[0]
        
    # 4. Inject Content
    try:
        with open(target_file, "r") as f:
            original_content = f.read()
            
        if MARKER_START in original_content and MARKER_END in original_content:
            # Replace existing block
            pre = original_content.split(MARKER_START)[0]
            post = original_content.split(MARKER_END)[1]
            final_content = pre + new_content + post
        else:
            # Append
            final_content = original_content + "\n\n" + new_content
            
        with open(target_file, "w") as f:
            f.write(final_content)
            
        return {"status": "synced", "file": str(target_file), "message": "Obsidian note updated."}
        
    except Exception as e:
        logger.error(f"Failed to write markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))
