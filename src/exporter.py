import json
import logging
import sqlite3
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
from src.exporter_render import (
    build_markdown_content,
    should_write_markdown,
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
    content = build_markdown_content(paper, vault_path)

    safe_filename = "".join([c for c in pid if c.isalnum() or c in (" ", "-", "_")]).strip()
    if not safe_filename:
        safe_filename = "paper"

    inbox_dir = vault_path / "Inbox/PaperPipe"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    target_file = inbox_dir / f"{safe_filename}.md"

    if not should_write_markdown(target_file, paper, overwrite):
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
