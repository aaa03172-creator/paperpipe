
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from src.db_utils import get_db_connection
from src.config import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_qa_check():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    config = load_config()
    vault_path_str = config.paths.obsidian_vault
    vault_path = Path(vault_path_str).expanduser() if vault_path_str else None
    
    print("=== PaperPipe QA Report ===")
    print(f"Time: {datetime.now()}")
    print("-" * 30)

    try:
        # 1. DB Integrity Check
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN summary IS NULL OR summary = '' OR summary = 'Abstract not available.' THEN 1 ELSE 0 END) as missing_summary,
                SUM(CASE WHEN feedback_json IS NULL OR feedback_json = '' THEN 1 ELSE 0 END) as missing_feedback
            FROM papers 
            WHERE status IN ('APPROVED', 'INDEXED')
        """)
        stats = cursor.fetchone()
        total = stats[0]
        missing_summary = stats[1]
        missing_feedback = stats[2]
        
        print(f"[DB] Total Active Papers (APPROVED/INDEXED): {total}")
        print(f"     (Definition: status IN ('APPROVED', 'INDEXED'))")
        print(f"[DB] Missing Summary: {missing_summary}")
        print(f"[DB] Missing Feedback JSON: {missing_feedback}")
        
        if missing_summary > 0:
            cursor.execute("SELECT paper_id FROM papers WHERE status IN ('APPROVED', 'INDEXED') AND (summary IS NULL OR summary = '' OR summary = 'Abstract not available.')")
            ids = [row[0] for row in cursor.fetchall()]
            print(f"   -> IDs: {ids}")
            
        print("-" * 30)

        # 1.2 Decision/Status Mismatch Report
        cursor.execute("""
            SELECT paper_id, status, gate_decision 
            FROM papers 
            WHERE (gate_decision='FAILED' AND status!='FAILED')
               OR (status='FAILED' AND (gate_decision IS NULL OR gate_decision!='FAILED'))
        """)
        mismatches = cursor.fetchall()
        print(f"[DB] Decision/Status Mismatch: {len(mismatches)}")
        if mismatches:
            for m in mismatches:
                print(f"   -> {m[0]} | status={m[1]} | gate_decision={m[2]}")
        
        print("-" * 30)
        
        # 1.5 FAILED Papers Report
        cursor.execute("SELECT paper_id, title, gate_reason FROM papers WHERE status='FAILED'")
        failed_papers = cursor.fetchall()
        
        print(f"[DB] FAILED Papers (Excluded from Export): {len(failed_papers)}")
        if failed_papers:
            for fp in failed_papers:
                # fp: (id, title, reason)
                reason = fp[2] if fp[2] else "Unknown Reason"
                print(f"   -> {fp[0]} | Reason: {reason}")
                
        print("-" * 30)

        # 2. File Existence & Content Check
        if not vault_path or not vault_path.exists():
            print("[File] Obsidian Vault path not found or invalid.")
            return

        inbox_dir = vault_path / "Inbox/PaperPipe"
        if not inbox_dir.exists():
             print(f"[File] Inbox dir not found: {inbox_dir}")
             return

        print(f"[File] Checking exports in: {inbox_dir}")
        
        cursor.execute("SELECT paper_id, title FROM papers WHERE status IN ('APPROVED', 'INDEXED')")
        papers = cursor.fetchall()
        
        missing_files = []
        bad_content_files = []
        
        for row in papers:
            pid = row[0]
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
                except Exception as e:
                    bad_content_files.append(f"{pid} (Read Error: {e})")

        print(f"[File] Missing Markdown Files: {len(missing_files)}")
        if missing_files:
            print(f"   -> IDs: {missing_files}")
            
        print(f"[File] potentially Bad Content (No Summary): {len(bad_content_files)}")
        if bad_content_files:
            print(f"   -> IDs: {bad_content_files}")

        print("=== End Report ===")
    finally:
        conn.close()

if __name__ == "__main__":
    run_qa_check()
