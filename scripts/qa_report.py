
import sqlite3
import json
import logging
import os
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db_utils import get_db_connection
from src.config import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def _is_test_fixture_record(paper_id: str, pdf_path: str | None) -> bool:
    pid = str(paper_id or "")
    path = str(pdf_path or "").replace("\\", "/")
    return (
        pid.startswith("local--")
        or "_test_" in pid
        or pid.startswith("integration_test_")
        or pid == "phase0_test"
        or "/tests/" in path
    )

def _claimset_artifacts_root() -> Path:
    env_root = os.getenv("PAPERPIPE_ARTIFACTS_DIR")
    if env_root:
        return Path(env_root).expanduser()
    return Path(__file__).resolve().parents[1] / "storage" / "artifacts"

def _has_claimset_artifact(paper_id: str) -> bool:
    paper_dir = _claimset_artifacts_root() / paper_id
    if not paper_dir.exists():
        return False
    for candidate in sorted(paper_dir.glob("*/claimset.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            parsed = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("claims"), list):
            return True
    return False

def _has_valid_claimset(feedback_json: str | None) -> bool:
    if not feedback_json:
        return False
    try:
        parsed = json.loads(feedback_json)
    except Exception:
        return False
    if not isinstance(parsed, dict):
        return False
    claims = parsed.get("claims")
    if isinstance(claims, list):
        return True
    nested = parsed.get("ClaimSet")
    if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
        return True
    nested = parsed.get("claimset")
    if isinstance(nested, dict) and isinstance(nested.get("claims"), list):
        return True
    return False


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _collect_institutional_counters(cursor) -> dict:
    counters = {
        "manual_required": 0,
        "downloaded_missing_path": 0,
        "unmatched_review_open": 0,
    }
    try:
        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN lower(coalesce(pdf_status, '')) = 'manual_required' THEN 1 ELSE 0 END) AS manual_required,
                SUM(CASE WHEN lower(coalesce(pdf_status, '')) = 'downloaded' AND (pdf_path IS NULL OR trim(pdf_path) = '') THEN 1 ELSE 0 END) AS downloaded_missing_path
            FROM papers
            WHERE status IN ('APPROVED', 'INDEXED')
            """
        )
        row = cursor.fetchone()
        if row is not None:
            counters["manual_required"] = _safe_int(row[0])
            counters["downloaded_missing_path"] = _safe_int(row[1])
    except sqlite3.OperationalError:
        # Legacy schemas may not have pdf_status/pdf_path.
        pass

    try:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM review_queue
            WHERE decision = 'NEEDS_PDF_MATCH'
              AND resolved_at IS NULL
            """
        )
        row = cursor.fetchone()
        counters["unmatched_review_open"] = _safe_int(row[0] if row is not None else 0)
    except sqlite3.OperationalError:
        # review_queue may not exist in minimal/local schemas.
        pass
    return counters


def _count_unmatched_files(config) -> int:
    try:
        storage_root = Path(getattr(config.paths, "pdf_storage_dir", "storage/pdfs")).expanduser()
    except Exception:
        storage_root = Path("storage/pdfs")
    unmatched_dir = storage_root / "_unmatched"
    if not unmatched_dir.exists():
        return 0
    try:
        return sum(1 for p in unmatched_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    except Exception:
        return 0

def run_qa_check(include_test_fixtures: bool = False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    config = load_config()
    vault_path_str = config.paths.obsidian_vault
    vault_path = Path(vault_path_str).expanduser() if vault_path_str else None
    
    print("=== PaperPipe QA Report ===")
    print(f"Time: {datetime.now()}")
    print("-" * 30)

    # 1. DB Integrity Check (operational view excludes test fixtures by default)
    cursor.execute(
        """
        SELECT paper_id, title, summary, feedback_json, pdf_path
        FROM papers
        WHERE status IN ('APPROVED', 'INDEXED')
        """
    )
    active_rows = [
        {
            "paper_id": row[0],
            "title": row[1],
            "summary": row[2],
            "feedback_json": row[3],
            "pdf_path": row[4],
        }
        for row in cursor.fetchall()
    ]
    filtered_rows = []
    for row in active_rows:
        if not include_test_fixtures and _is_test_fixture_record(row["paper_id"], row["pdf_path"]):
            continue
        filtered_rows.append(row)

    total = len(filtered_rows)
    missing_summary_ids = [
        str(row["paper_id"])
        for row in filtered_rows
        if row["summary"] is None or row["summary"] == "" or row["summary"] == "Abstract not available."
    ]
    missing_feedback_ids = [
        str(row["paper_id"])
        for row in filtered_rows
        if row["feedback_json"] is None or row["feedback_json"] == ""
    ]
    missing_summary = len(missing_summary_ids)
    missing_feedback = len(missing_feedback_ids)
    
    print(f"[DB] Total Active Papers (APPROVED/INDEXED): {total}")
    print(f"     (Definition: status IN ('APPROVED', 'INDEXED'))")
    print(f"[DB] Missing Summary: {missing_summary}")
    print(f"[DB] Missing Feedback JSON: {missing_feedback}")
    institutional_counters = _collect_institutional_counters(cursor)
    unmatched_files = _count_unmatched_files(config)
    print(f"[DB] manual_required: {institutional_counters['manual_required']}")
    print(f"[DB] downloaded_missing_path: {institutional_counters['downloaded_missing_path']}")
    print(f"[DB] unmatched_review_open: {institutional_counters['unmatched_review_open']}")
    print(f"[File] unmatched_files: {unmatched_files}")

    missing_or_invalid_claimset = 0
    missing_claimset_ids = []
    for row in filtered_rows:
        paper_id = row["paper_id"]
        feedback_json = row["feedback_json"]
        if _has_valid_claimset(feedback_json):
            continue
        if _has_claimset_artifact(paper_id):
            continue
        missing_or_invalid_claimset += 1
        missing_claimset_ids.append(paper_id)
    if include_test_fixtures:
        print(f"[DB] Missing/Invalid ClaimSet: {missing_or_invalid_claimset}")
    else:
        print(f"[DB] Missing/Invalid ClaimSet (Operational): {missing_or_invalid_claimset}")
    if missing_claimset_ids:
        print(f"   -> IDs: {missing_claimset_ids[:50]}")
    
    if missing_summary_ids:
        print(f"[DB] Missing Summary IDs: {missing_summary_ids}")
        
    print("-" * 30)
    
    # 1.5 FAILED Papers Report
    try:
        cursor.execute("SELECT paper_id, title, gate_reason FROM papers WHERE status='FAILED'")
    except sqlite3.OperationalError:
        cursor.execute("SELECT paper_id, title, NULL as gate_reason FROM papers WHERE status='FAILED'")
    failed_papers = cursor.fetchall()
    
    print(f"[DB] FAILED Papers (Excluded from Export): {len(failed_papers)}")
    if failed_papers:
        for fp in failed_papers:
            # fp: (id, title, reason)
            reason = fp[2] if fp[2] else "Unknown Reason"
            print(f"   -> {fp[0]} | Reason: {reason}")
            
    print("-" * 30)

    # 2. File Existence & Content Check
    missing_critical_review_section = 0
    if not vault_path or not vault_path.exists():
        print("[File] Obsidian Vault path not found or invalid.")
        print("=== End Report ===")
        conn.close()
        return {
            "total_active": total,
            "missing_summary": missing_summary,
            "missing_feedback": missing_feedback,
            "missing_or_invalid_claimset": missing_or_invalid_claimset,
            "manual_required": institutional_counters["manual_required"],
            "downloaded_missing_path": institutional_counters["downloaded_missing_path"],
            "unmatched": institutional_counters["unmatched_review_open"],
            "unmatched_files": unmatched_files,
            "unmatched_review_open": institutional_counters["unmatched_review_open"],
            "missing_critical_review_section": missing_critical_review_section,
            "missing_files": 0,
            "bad_content_files": 0,
        }

    inbox_dir = vault_path / "Inbox/PaperPipe"
    if not inbox_dir.exists():
         print(f"[File] Inbox dir not found: {inbox_dir}")
         print("=== End Report ===")
         conn.close()
         return {
             "total_active": total,
             "missing_summary": missing_summary,
             "missing_feedback": missing_feedback,
             "missing_or_invalid_claimset": missing_or_invalid_claimset,
             "manual_required": institutional_counters["manual_required"],
             "downloaded_missing_path": institutional_counters["downloaded_missing_path"],
            "unmatched": institutional_counters["unmatched_review_open"],
            "unmatched_files": unmatched_files,
            "unmatched_review_open": institutional_counters["unmatched_review_open"],
             "missing_critical_review_section": missing_critical_review_section,
             "missing_files": 0,
             "bad_content_files": 0,
         }

    print(f"[File] Checking exports in: {inbox_dir}")
    
    missing_files = []
    bad_content_files = []
    
    for row in filtered_rows:
        pid = str(row["paper_id"])
        # Heuristic for filename: same logic as exporter
        safe_filename = "".join([c for c in pid if c.isalnum() or c in (' ', '-', '_')]).strip()
        if not safe_filename: safe_filename = "paper"
        
        fpath = inbox_dir / f"{safe_filename}.md"
        
        if not fpath.exists():
            missing_files.append(pid)
        else:
            # Check content
            try:
                content = fpath.read_text(encoding='utf-8')
                if "No summary available" in content:
                    bad_content_files.append(f"{pid} (No summary)")
                if "tags:\n  - \n" in content: # Empty tag list check heuristic
                    bad_content_files.append(f"{pid} (Empty tags)")
                if "## Critical Review (ClaimSet)" not in content:
                    missing_critical_review_section += 1
            except Exception as e:
                bad_content_files.append(f"{pid} (Read Error: {e})")

    print(f"[File] Missing Critical Review section: {missing_critical_review_section}")

    print(f"[File] Missing Markdown Files: {len(missing_files)}")
    if missing_files:
        print(f"   -> IDs: {missing_files}")
        
    print(f"[File] potentially Bad Content (No Summary): {len(bad_content_files)}")
    if bad_content_files:
        print(f"   -> IDs: {bad_content_files}")

    print("=== End Report ===")
    conn.close()
    return {
        "total_active": total,
        "missing_summary": missing_summary,
        "missing_feedback": missing_feedback,
        "missing_or_invalid_claimset": missing_or_invalid_claimset,
        "manual_required": institutional_counters["manual_required"],
        "downloaded_missing_path": institutional_counters["downloaded_missing_path"],
        "unmatched": institutional_counters["unmatched_review_open"],
        "unmatched_files": unmatched_files,
        "unmatched_review_open": institutional_counters["unmatched_review_open"],
        "missing_critical_review_section": missing_critical_review_section,
        "missing_files": len(missing_files),
        "bad_content_files": len(bad_content_files),
    }

if __name__ == "__main__":
    run_qa_check()
