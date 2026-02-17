import json
import sqlite3

import src.db_utils as db_utils


def _init_test_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            status TEXT,
            gate_decision TEXT,
            gate_reason TEXT,
            feedback_json TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def test_reconcile_dry_run_does_not_modify_db(tmp_path):
    db_path = tmp_path / "state.db"
    _init_test_db(db_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO papers (paper_id, status, gate_decision, gate_reason, feedback_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("p1", "PENDING_REVIEW", "APPROVED", None, None),
        )
        conn.commit()
        conn.close()

        result = db_utils.reconcile_approved_decisions(dry_run=True)
        assert result["candidate_count"] == 1
        assert result["updated_count"] == 0

        conn = db_utils.get_db_connection()
        row = conn.execute("SELECT status FROM papers WHERE paper_id='p1'").fetchone()
        conn.close()
        assert row["status"] == "PENDING_REVIEW"
    finally:
        db_utils.DB_PATH = original_db_path


def test_reconcile_apply_updates_gate_decision_and_feedback_json_cases(tmp_path):
    db_path = tmp_path / "state.db"
    _init_test_db(db_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO papers (paper_id, status, gate_decision, gate_reason, feedback_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("p_gate", "FAILED", "APPROVED", None, None),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, status, gate_decision, gate_reason, feedback_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "p_feedback",
                "PENDING_REVIEW",
                None,
                None,
                json.dumps({"decision": "APPROVED", "reason": "manual"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, status, gate_decision, gate_reason, feedback_json, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("p_indexed", "INDEXED", "APPROVED", None, None),
        )
        conn.commit()
        conn.close()

        result = db_utils.reconcile_approved_decisions(dry_run=False)
        assert result["candidate_count"] == 2
        assert result["updated_count"] == 2

        conn = db_utils.get_db_connection()
        gate_row = conn.execute(
            "SELECT status FROM papers WHERE paper_id='p_gate'"
        ).fetchone()
        feedback_row = conn.execute(
            "SELECT status, gate_decision FROM papers WHERE paper_id='p_feedback'"
        ).fetchone()
        indexed_row = conn.execute(
            "SELECT status FROM papers WHERE paper_id='p_indexed'"
        ).fetchone()
        conn.close()

        assert gate_row["status"] == "APPROVED"
        assert feedback_row["status"] == "APPROVED"
        assert feedback_row["gate_decision"] == "APPROVED"
        assert indexed_row["status"] == "INDEXED"
    finally:
        db_utils.DB_PATH = original_db_path
