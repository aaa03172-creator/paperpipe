import logging
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from src.config import load_config
from src.db_utils import get_db_connection

logger = logging.getLogger(__name__)

def _build_zotero_links(paper: Dict[str, Any]) -> List[str]:
    links: List[str] = []
    zotero_key = (paper.get("zotero_key") or "").strip()
    if not zotero_key:
        return links

    links.append(f"[Zotero Item](zotero://select/library/items/{zotero_key})")

    page = paper.get("page")
    if page is not None:
        links.append(f"[Zotero PDF](zotero://open-pdf/library/items/{zotero_key}?page={page})")

    return links

def _build_pdf_links(paper: Dict[str, Any], vault_path: Path) -> List[str]:
    links: List[str] = []
    pdf_path_str = paper.get("pdf_path")
    if not pdf_path_str:
        return links

    pdf_path = Path(pdf_path_str).expanduser()
    if pdf_path.exists():
        try:
            rel = pdf_path.relative_to(vault_path)
            links.append(f"[[{rel.as_posix()}]]")
        except ValueError:
            links.append(f"[Open PDF](file://{pdf_path.absolute()})")
    else:
        links.append(f"[Open PDF](file://{pdf_path.absolute()})")

    return links

def export_paper_to_markdown(paper: Dict[str, Any], vault_path: Path, overwrite: bool = False) -> bool:
    """
    Exports a single paper to an Obsidian Markdown file.
    Returns True if exported, False if skipped (exists and not overwrite).
    """
    pid = paper['paper_id']
    title = paper['title'] or "Untitled"
    summary = paper['summary'] or "No summary available."
    
    # Parse feedback_json
    try:
        feedback = json.loads(paper.get('feedback_json') or '{}')
    except Exception:
        feedback = {}
        
    hard_tags = feedback.get('hard_tags', {})
    soft_tags = feedback.get('soft_tags', [])
    confidence = paper.get('confidence') # Use top-level confidence if available, else feedback
    if confidence is None:
        confidence = feedback.get('confidence', 0.0)
        
    # --- 1. Prepare Content ---
    
    # Tags
    obsidian_tags = []
    
    # Hard Tags as Type/Value
    study_type = hard_tags.get('study_type')
    if study_type:
        # Sanitize space -> _ or just remove
        safe_type = str(study_type).replace(" ", "_")
        obsidian_tags.append(f"Type/{safe_type}")
        
    # Soft Tags
    for tag in soft_tags:
        if tag.startswith("#"):
            obsidian_tags.append(tag[1:]) # Remove # for Frontmatter list
        else:
            obsidian_tags.append(tag)
            
    # Verdict text
    verdict = "❓ Unknown"
    try:
        f_conf = float(confidence)
        if f_conf >= 0.9: verdict = "🌟 Strongly Approved"
        elif f_conf >= 0.7: verdict = "✅ Approved"
        else: verdict = "⚠️ Low Confidence"
    except (TypeError, ValueError):
        pass

    # Design Tag
    design_tag = hard_tags.get('design', 'Unknown')
    
    # Key Findings (Simulation if not structured)
    # The snippet doesn't explicitly have 'key_findings' in feedback usually, 
    # but let's check deep_read or summary. 
    # For now, we will use evidence snippets if available as findings proxy.
    evidence = feedback.get('evidence_snippets', [])
    findings_list = ""
    if evidence:
        for ev in evidence:
            loc = ev.get('location', 'Text')
            txt = ev.get('snippet', '')
            sup = ev.get('supports', '')
            findings_list += f"* **[{loc}]**: {txt} (Supports: *{sup}*)\n"
    elif feedback.get('evidence_span'):
        # Fallback to single evidence span from tag_paper
        span = feedback.get('evidence_span')
        findings_list = f"* **[Abstract/Text]**: {span} (Primary Evidence)\n"
    else:
        findings_list = "* *No granular findings extracted.*"

    links: List[str] = []
    links.extend(_build_zotero_links(paper))
    links.extend(_build_pdf_links(paper, vault_path))
    references_block = "\n".join([f"* {link}" for link in links]) if links else "*No external links available.*"

    # Date
    today = datetime.now().strftime("%Y-%m-%d")

    # --- 2. Build Markdown ---
    content = f"""---
id: {pid}
aliases: ["{title.replace('"', '')}"]
tags:
{chr(10).join([f"  - {t}" for t in obsidian_tags])}
date_processed: {today}
confidence: {confidence}
status: {paper['status']}
---

# {title}

> **One-Line Summary**
> {summary}

## 📊 Critical Analysis
* **Study Design:** {design_tag}
* **Professor's Verdict:** {verdict} ({confidence})

### Key Findings & Evidence
{findings_list}

## 🔗 References
{references_block}
"""

    # --- 3. Save File ---
    # Safe filename
    safe_filename = "".join([c for c in pid if c.isalnum() or c in (' ', '-', '_')]).strip()
    if not safe_filename: safe_filename = "paper"
    
    # Check Inbox (or target folder)
    # Config might just say "obsidian_vault". We'll put in Inbox/PaperPipe per convention or root.
    # User said "OBSIDIAN_VAULT_PATH/Inbox (또는 지정된 폴더)"
    inbox_dir = vault_path / "Inbox/PaperPipe"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    target_file = inbox_dir / f"{safe_filename}.md"
    
    # [Smart Overwrite Logic]
    # If overwrite=True, we always write.
    # If overwrite=False, we check if DB is newer than File.
    should_write = False
    
    if overwrite:
        should_write = True
    elif not target_file.exists():
        should_write = True
    else:
        # File exists, check timestamps
            # File exists, check timestamps
        try:
            file_mtime = target_file.stat().st_mtime
            db_updated_str = paper.get('updated_at')
            
            if db_updated_str:
                # DB format: YYYY-MM-DD HH:MM:SS.ssssss
                # Simplified parsing: string comparison works for ISO-like if timezone matches (local).
                # But let's be safe: convert to timestamp if possible or just use strict overwrite policy.
                
                # Option A: If DB string > File timestamp string? No, encoding differs.
                # Option B: Parse DB string.
                dt_db = datetime.fromisoformat(db_updated_str)
                ts_db = dt_db.timestamp()
                
                if ts_db > file_mtime:
                    should_write = True
                    # logger.info(f"  -> Updating {pid} (DB newer)")
        except Exception:
            # If parsing fails, fall back to safe "don't overwrite unless flag set"
            pass
            
    if not should_write and not overwrite:
         return False

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    return True

def run_export(overwrite: bool = True):
    """
    Exports all APPROVED/INDEXED papers to Obsidian.
    """
    config = load_config()
    vault_path_str = config.paths.obsidian_vault
    if not vault_path_str:
        logger.error("obsidian_vault path not set in config.")
        return
        
    vault_path = Path(vault_path_str).expanduser()
    if not vault_path.exists():
        logger.warning(f"Obsidian Vault path does not exist: {vault_path}. Creating it.")
        vault_path.mkdir(parents=True, exist_ok=True)

    # 1. Fetch Targets
    # APPROVED or INDEXED
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM papers WHERE status IN ('APPROVED', 'INDEXED')")
    rows = cursor.fetchall()
    conn.close()
    
    papers = [dict(row) for row in rows]
    logger.info(f"Targeting {len(papers)} papers for export.")
    
    count = 0
    for p in papers:
        if export_paper_to_markdown(p, vault_path, overwrite):
            count += 1
            
    logger.info(f"✅ Exported {count} papers to {vault_path}/Inbox/PaperPipe")
