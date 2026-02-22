from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import src.db_utils as db_utils
from src.db_event_log import (
    create_job,
    create_run,
    finish_run,
    log_event,
    log_user_action,
    update_job_status,
)


def _create_papers_table(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            paper_key TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, doi, title, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        ("doi:10.1000/event", "10.1000/event", "Event Paper"),
    )
    conn.commit()
    conn.close()


def test_event_log_lifecycle_and_user_action(tmp_path: Path):
    db_path = tmp_path / "state.db"
    _create_papers_table(db_path)

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    try:
        db_utils.init_db()

        run_id = create_run(
            paper_id="doi:10.1000/event",
            trigger_source="ui",
            pipeline_profile="grounded_read",
            params={"k": 1},
            run_id="run_fixed_1",
        )
        assert run_id == "run_fixed_1"

        job_id = create_job(
            run_id=run_id,
            paper_id="doi:10.1000/event",
            job_type="read",
            params={"x": 1},
            job_id="job_fixed_1",
        )
        assert job_id == "job_fixed_1"

        event_id = log_event(
            job_id=job_id,
            level="info",
            event_type="step_start",
            message="read started",
            payload={"stage": "read"},
        )
        assert isinstance(event_id, str)

        update_job_status(
            job_id=job_id,
            status="completed",
            result_ref="storage/artifacts/x",
            metrics={"latency_ms": 10},
        )
        finish_run(run_id=run_id, status="succeeded", metrics={"ok": True})

        action_id = log_user_action(
            paper_id="doi:10.1000/event",
            action_type="important",
            source="runtime",
            payload={"tag": "#important"},
        )
        assert isinstance(action_id, str)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert run_row is not None
        assert run_row["status"] == "succeeded"
        assert json.loads(run_row["params_json"])["k"] == 1

        job_row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert job_row is not None
        assert job_row["job_type"] == "read"
        assert job_row["status"] == "completed"
        assert json.loads(job_row["metrics_json"])["latency_ms"] == 10

        event_row = conn.execute("SELECT * FROM job_events WHERE event_id = ?", (event_id,)).fetchone()
        assert event_row is not None
        assert event_row["event_type"] == "step_start"

        action_row = conn.execute("SELECT * FROM user_actions WHERE action_id = ?", (action_id,)).fetchone()
        assert action_row is not None
        assert action_row["action_type"] == "important"

        paper_key = conn.execute(
            "SELECT paper_key FROM papers WHERE paper_id = ?",
            ("doi:10.1000/event",),
        ).fetchone()[0]
        conn.close()
        assert paper_key is not None
        assert paper_key
    finally:
        db_utils.DB_PATH = old_db
