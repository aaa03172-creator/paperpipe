import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.config import load_config
from src.db_utils import get_db_connection
from src.exporter_claimset import (
    format_claimset_section,
    is_test_fixture_paper,
    resolve_claimset_claims,
)
from src.exporter_helpers import (
    build_institutional_download_block,
    build_pdf_links,
    build_zotero_links,
    expected_obsidian_relpath_for_paper_id,
    sanitize_frontmatter_tag,
)
from src.exporter_review_queue import (
    REVIEW_NEEDS_EVIDENCE_LINK,
    REVIEW_NEEDS_READER,
    REVIEW_NEEDS_STATS_CHECK,
    TEST_FIXTURE_OWNER,
    auto_skip_test_fixture_followups,
    enqueue_review_followups,
    resolve_review_followups,
)
from src.institutional_access import (
    generate_institutional_proxy_url,
    upsert_institutional_proxy_link,
)

logger = logging.getLogger(__name__)

# Backward-compatible aliases for existing call sites/tests.
_build_zotero_links = build_zotero_links
_build_pdf_links = build_pdf_links
_build_institutional_download_block = build_institutional_download_block
_sanitize_frontmatter_tag = sanitize_frontmatter_tag
_format_claimset_section = format_claimset_section
_is_test_fixture_paper = is_test_fixture_paper
_auto_skip_test_fixture_followups = auto_skip_test_fixture_followups
_expected_obsidian_relpath_for_paper_id = expected_obsidian_relpath_for_paper_id


def export_paper_to_markdown(paper: Dict[str, Any], vault_path: Path, overwrite: bool = False) -> bool:
    """
    Exports a single paper to an Obsidian Markdown file.
    Returns True if exported, False if skipped (exists and not overwrite).
    """
    pid = paper["paper_id"]
    title = paper["title"] or "Untitled"
    summary = paper["summary"] or "No summary available."

    try:
        feedback = json.loads(paper.get("feedback_json") or "{}")
    except Exception:
        feedback = {}
    if not isinstance(feedback, dict):
        feedback = {}

    hard_tags = feedback.get("hard_tags", {})
    soft_tags = feedback.get("soft_tags", [])
    confidence = paper.get("confidence")
    if confidence is None:
        confidence = feedback.get("confidence", 0.0)

    obsidian_tags = []

    study_type = hard_tags.get("study_type")
    if study_type:
        safe_type = str(study_type).replace(" ", "_")
        obsidian_tags.append(f"Type/{safe_type}")

    for tag in soft_tags:
        safe_tag = _sanitize_frontmatter_tag(tag)
        if safe_tag:
            obsidian_tags.append(safe_tag)

    verdict = "❓ Unknown"
    try:
        f_conf = float(confidence)
        if f_conf >= 0.9:
            verdict = "🌟 Strongly Approved"
        elif f_conf >= 0.7:
            verdict = "✅ Approved"
        else:
            verdict = "⚠️ Low Confidence"
    except (TypeError, ValueError):
        pass

    design_tag = hard_tags.get("design", "Unknown")

    evidence = feedback.get("evidence_snippets", [])
    findings_list = ""
    if evidence:
        for ev in evidence:
            loc = ev.get("location", "Text")
            txt = ev.get("snippet", "")
            sup = ev.get("supports", "")
            findings_list += f"* **[{loc}]**: {txt} (Supports: *{sup}*)\n"
    elif feedback.get("evidence_span"):
        span = feedback.get("evidence_span")
        findings_list = f"* **[Abstract/Text]**: {span} (Primary Evidence)\n"
    else:
        findings_list = "* *No granular findings extracted.*"

    links: List[str] = []
    links.extend(_build_zotero_links(paper))
    links.extend(_build_pdf_links(paper, vault_path))
    references_block = "\n".join([f"* {link}" for link in links]) if links else "*No external links available.*"
    institutional_block = _build_institutional_download_block(paper, feedback)
    claimset_claims = resolve_claimset_claims(paper, feedback)
    claimset_block = _format_claimset_section(paper, claimset_claims)

    today = datetime.now().strftime("%Y-%m-%d")

    content = f"""---
id: {pid}
aliases: [\"{title.replace('"', '')}\"]
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

{institutional_block}
"""

    safe_filename = "".join([c for c in pid if c.isalnum() or c in (" ", "-", "_")]).strip()
    if not safe_filename:
        safe_filename = "paper"

    inbox_dir = vault_path / "Inbox/PaperPipe"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    target_file = inbox_dir / f"{safe_filename}.md"

    should_write = False
    if overwrite:
        should_write = True
    elif not target_file.exists():
        should_write = True
    else:
        try:
            file_mtime = target_file.stat().st_mtime
            db_updated_str = paper.get("updated_at")
            if db_updated_str:
                dt_db = datetime.fromisoformat(db_updated_str)
                ts_db = dt_db.timestamp()
                if ts_db > file_mtime:
                    should_write = True
        except Exception:
            pass

    if not should_write and not overwrite:
        return False

    with open(target_file, "w", encoding="utf-8") as handle:
        handle.write(content)

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

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM papers WHERE status IN ('APPROVED', 'INDEXED')")
    rows = cursor.fetchall()

    papers = [dict(row) for row in rows]
    logger.info(f"Targeting {len(papers)} papers for export.")

    count = 0
    for paper in papers:
        try:
            if not paper.get("pdf_path"):
                proxy_url = generate_institutional_proxy_url(paper=paper)
                if proxy_url:
                    updated_feedback = upsert_institutional_proxy_link(
                        paper.get("feedback_json"), proxy_url
                    )
                    paper["feedback_json"] = updated_feedback
                    paper["pdf_status"] = "manual_required"
                    cursor.execute(
                        """
                        UPDATE papers
                        SET pdf_status = ?, feedback_json = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE paper_id = ?
                        """,
                        ("manual_required", updated_feedback, paper["paper_id"]),
                    )
        except sqlite3.OperationalError:
            pass

        if export_paper_to_markdown(paper, vault_path, overwrite):
            count += 1
            try:
                cursor.execute(
                    """
                    UPDATE papers
                    SET obsidian_path = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE paper_id = ?
                    """,
                    (_expected_obsidian_relpath_for_paper_id(str(paper["paper_id"])), paper["paper_id"]),
                )
            except sqlite3.OperationalError:
                pass

        if _is_test_fixture_paper(paper):
            _auto_skip_test_fixture_followups(conn, paper)
            continue

        try:
            feedback = json.loads(paper.get("feedback_json") or "{}")
        except Exception:
            feedback = {}
        if not isinstance(feedback, dict):
            feedback = {}

        claims = resolve_claimset_claims(paper, feedback)
        enqueue_review_followups(conn, paper, feedback, claims)
        resolve_review_followups(conn, paper, feedback, claims)

    conn.commit()
    conn.close()

    logger.info(f"✅ Exported {count} papers to {vault_path}/Inbox/PaperPipe")
