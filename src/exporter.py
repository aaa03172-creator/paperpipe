import logging
import json
import sqlite3
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.config import load_config
from src.db_utils import get_db_connection

logger = logging.getLogger(__name__)

REVIEW_NEEDS_READER = "NEEDS_READER"
REVIEW_NEEDS_EVIDENCE_LINK = "NEEDS_EVIDENCE_LINK"
REVIEW_NEEDS_STATS_CHECK = "NEEDS_STATS_CHECK"
TEST_FIXTURE_OWNER = "TEST_FIXTURE"

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

def _sanitize_frontmatter_tag(tag: Any) -> Optional[str]:
    if tag is None:
        return None
    value = str(tag).strip()
    if not value:
        return None
    if value.startswith("#"):
        value = value[1:]
    value = value.replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_/-]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or None

def _extract_claimset_claims(feedback: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(feedback, dict):
        return None
    if isinstance(feedback.get("claims"), list):
        return feedback["claims"]
    claimset = feedback.get("ClaimSet")
    if isinstance(claimset, dict) and isinstance(claimset.get("claims"), list):
        return claimset["claims"]
    claimset = feedback.get("claimset")
    if isinstance(claimset, dict) and isinstance(claimset.get("claims"), list):
        return claimset["claims"]
    return None

def _claimset_artifacts_root() -> Path:
    env_root = os.getenv("PAPERPIPE_ARTIFACTS_DIR")
    if env_root:
        return Path(env_root).expanduser()
    return Path(__file__).resolve().parents[1] / "storage" / "artifacts"

def _is_test_fixture_paper(paper: Dict[str, Any]) -> bool:
    paper_id = str(paper.get("paper_id") or "")
    pdf_path = str(paper.get("pdf_path") or "")
    return (
        paper_id.startswith("local--")
        or "_test_" in paper_id
        or paper_id.startswith("integration_test_")
        or paper_id == "phase0_test"
        or "/tests/" in pdf_path.replace("\\", "/")
    )

def _extract_claimset_claims_from_file(path: Path) -> Optional[List[Dict[str, Any]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    claims = data.get("claims")
    if isinstance(claims, list):
        return claims
    return None

def _extract_claimset_claims_from_artifacts(paper_id: str) -> Optional[List[Dict[str, Any]]]:
    root = _claimset_artifacts_root()
    paper_dir = root / paper_id
    if not paper_dir.exists():
        return None
    candidates = sorted(paper_dir.glob("*/claimset.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        claims = _extract_claimset_claims_from_file(candidate)
        if claims is not None:
            return claims
    return None

def resolve_claimset_claims(paper: Dict[str, Any], feedback: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    claims = _extract_claimset_claims(feedback)
    if claims is not None:
        return claims
    paper_id = paper.get("paper_id")
    if not paper_id:
        return None
    return _extract_claimset_claims_from_artifacts(str(paper_id))

def _resolve_evidence_link(paper: Dict[str, Any], page_num: Optional[int]) -> Optional[str]:
    zotero_key = (paper.get("zotero_key") or "").strip()
    if not zotero_key or page_num is None:
        return None
    try:
        page = int(page_num)
    except (TypeError, ValueError):
        return None
    if page < 0:
        return None
    # EvidenceSpan.page is 0-indexed; Zotero open-pdf is page=1 style in this project UI.
    return f"zotero://open-pdf/library/items/{zotero_key}?page={page + 1}"

def _format_claimset_section(paper: Dict[str, Any], claims: Optional[List[Dict[str, Any]]]) -> str:
    if not claims:
        return "## Critical Review (ClaimSet)\nClaimSet: unavailable\n"

    lines = ["## Critical Review (ClaimSet)"]
    for idx, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            continue
        statement = claim.get("statement") or "N/A"
        limitations = claim.get("limitations")
        confidence = claim.get("confidence", "N/A")
        evidence_spans = claim.get("evidence_spans")
        evidence_line = "Evidence: unavailable"

        if isinstance(evidence_spans, list) and evidence_spans:
            span = evidence_spans[0] if isinstance(evidence_spans[0], dict) else {}
            quote = span.get("quote") or span.get("raw_text") or "N/A"
            page_num = span.get("page")
            page_hint = "N/A"
            if isinstance(page_num, int):
                page_hint = str(page_num)
            link = _resolve_evidence_link(paper, page_num if isinstance(page_num, int) else None)
            evidence_parts = [f'quote="{quote}"', f"page_num={page_hint}"]
            if link:
                evidence_parts.append(f"link={link}")
            evidence_line = "Evidence: " + ", ".join(evidence_parts)

        if isinstance(limitations, list):
            limitations_text = "; ".join([str(x) for x in limitations if str(x).strip()]) or "N/A"
        else:
            limitations_text = "N/A"

        lines.extend(
            [
                f"### Claim {idx}",
                f"- Claim: {statement}",
                f"- {evidence_line}",
                f"- Limitations: {limitations_text}",
                f"- Confidence: {confidence}",
            ]
        )

    if len(lines) == 1:
        lines.append("ClaimSet: unavailable")
    return "\n".join(lines) + "\n"

def _span_missing_location(span: Any) -> bool:
    if not isinstance(span, dict):
        return True
    page = span.get("page")
    has_page = isinstance(page, int) and page >= 0
    has_source_span = isinstance(span.get("source_span"), list) and len(span.get("source_span")) >= 2
    has_char = span.get("char_start") is not None and span.get("char_end") is not None
    return not (has_page or has_source_span or has_char)

def _feedback_needs_stats_check(feedback: Dict[str, Any]) -> bool:
    targets = {"unverifiable", "inconsistent"}

    def _walk(node: Any) -> bool:
        if isinstance(node, dict):
            verdict = node.get("verdict")
            if isinstance(verdict, str) and verdict.lower() in targets:
                return True
            for value in node.values():
                if _walk(value):
                    return True
        elif isinstance(node, list):
            for item in node:
                if _walk(item):
                    return True
        return False

    return _walk(feedback)

def enqueue_review_followups(conn: sqlite3.Connection, paper: Dict[str, Any], feedback: Dict[str, Any], claims: Optional[List[Dict[str, Any]]]) -> List[str]:
    paper_id = paper.get("paper_id")
    if not paper_id:
        return []

    decisions: List[tuple[str, str]] = []

    if not claims:
        decisions.append((REVIEW_NEEDS_READER, "ClaimSet missing or invalid in feedback_json"))
    else:
        missing_loc = False
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            spans = claim.get("evidence_spans")
            if isinstance(spans, list) and spans:
                if any(_span_missing_location(span) for span in spans):
                    missing_loc = True
                    break
        if missing_loc:
            decisions.append((REVIEW_NEEDS_EVIDENCE_LINK, "Evidence span missing location metadata (page/source span)"))

    if _feedback_needs_stats_check(feedback):
        decisions.append((REVIEW_NEEDS_STATS_CHECK, "Stats verdict includes unverifiable/inconsistent"))

    inserted: List[str] = []
    cur = conn.cursor()
    try:
        for decision, reason in decisions:
            cur.execute(
                """
                SELECT 1 FROM review_queue
                WHERE paper_id = ? AND decision = ? AND resolved_at IS NULL
                LIMIT 1
                """,
                (paper_id, decision),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO review_queue (paper_id, decision, reason)
                VALUES (?, ?, ?)
                """,
                (paper_id, decision, reason),
            )
            inserted.append(decision)
    except sqlite3.OperationalError as exc:
        logger.warning("review_queue unavailable; follow-up enqueue skipped: %s", exc)
        return []

    return inserted

def resolve_review_followups(conn: sqlite3.Connection, paper: Dict[str, Any], feedback: Dict[str, Any], claims: Optional[List[Dict[str, Any]]]) -> List[str]:
    paper_id = paper.get("paper_id")
    if not paper_id:
        return []

    should_have_reader = not claims
    should_have_evidence_link = False
    if claims:
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            spans = claim.get("evidence_spans")
            if isinstance(spans, list) and spans and any(_span_missing_location(span) for span in spans):
                should_have_evidence_link = True
                break
    should_have_stats = _feedback_needs_stats_check(feedback)

    resolve_targets: List[str] = []
    if not should_have_reader:
        resolve_targets.append(REVIEW_NEEDS_READER)
    if not should_have_evidence_link:
        resolve_targets.append(REVIEW_NEEDS_EVIDENCE_LINK)
    if not should_have_stats:
        resolve_targets.append(REVIEW_NEEDS_STATS_CHECK)

    if not resolve_targets:
        return []

    resolved: List[str] = []
    cur = conn.cursor()
    for decision in resolve_targets:
        cur.execute(
            """
            UPDATE review_queue
            SET resolved_at = CURRENT_TIMESTAMP,
                resolution = COALESCE(resolution, 'AUTO_RESOLVED')
            WHERE paper_id = ?
              AND decision = ?
              AND resolved_at IS NULL
            """,
            (paper_id, decision),
        )
        if cur.rowcount > 0:
            resolved.append(decision)
    return resolved

def _auto_skip_test_fixture_followups(conn: sqlite3.Connection, paper: Dict[str, Any]) -> int:
    paper_id = paper.get("paper_id")
    if not paper_id:
        return 0
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE review_queue
        SET owner = ?,
            resolved_at = CURRENT_TIMESTAMP,
            resolution = COALESCE(resolution, 'AUTO_SKIPPED_TEST_FIXTURE'),
            reason = CASE
                WHEN instr(COALESCE(reason, ''), '[auto-skip:test_fixture]') > 0 THEN reason
                ELSE COALESCE(reason, '') || ' [auto-skip:test_fixture]'
            END
        WHERE paper_id = ?
          AND decision = ?
          AND resolved_at IS NULL
        """,
        (TEST_FIXTURE_OWNER, paper_id, REVIEW_NEEDS_READER),
    )
    return cur.rowcount

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
    if not isinstance(feedback, dict):
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
        safe_tag = _sanitize_frontmatter_tag(tag)
        if safe_tag:
            obsidian_tags.append(safe_tag)
            
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
    claimset_claims = resolve_claimset_claims(paper, feedback)
    claimset_block = _format_claimset_section(paper, claimset_claims)

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

{claimset_block}

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
    
    papers = [dict(row) for row in rows]
    logger.info(f"Targeting {len(papers)} papers for export.")
    
    count = 0
    for p in papers:
        if export_paper_to_markdown(p, vault_path, overwrite):
            count += 1
        if _is_test_fixture_paper(p):
            _auto_skip_test_fixture_followups(conn, p)
            continue
        try:
            feedback = json.loads(p.get("feedback_json") or "{}")
        except Exception:
            feedback = {}
        if not isinstance(feedback, dict):
            feedback = {}
        claims = resolve_claimset_claims(p, feedback)
        enqueue_review_followups(conn, p, feedback, claims)
        resolve_review_followups(conn, p, feedback, claims)

    conn.commit()
    conn.close()
            
    logger.info(f"✅ Exported {count} papers to {vault_path}/Inbox/PaperPipe")
