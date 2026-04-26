from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import src.db_utils as db_utils


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_capture_stale_incident_snapshots_script_captures_real_candidates(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    storage_dir = tmp_path / "storage"
    original_db_path = db_utils.DB_PATH
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    monkeypatch.setenv("PAPERPIPE_STORAGE_DIR", str(storage_dir))

    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO execution_runs (
                run_id, paper_id, trigger_source, pipeline_profile, status, created_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_script_incident_001",
                "paper_script_incident_001",
                "script_test",
                "deepread",
                "running",
                "2000-01-01T00:00:00+00:00",
                "2000-01-01T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, started_at, heartbeat_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_script_incident_001",
                "run_script_incident_001",
                "paper_script_incident_001",
                "running",
                12,
                "read",
                "2000-01-01 00:00:00",
                "2000-01-01 00:00:00",
                "2000-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        env = os.environ.copy()
        env["PAPERPIPE_DB_PATH"] = str(db_path)
        env["PAPERPIPE_STORAGE_DIR"] = str(storage_dir)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/capture_stale_incident_snapshots.py",
                "--stale-after-seconds",
                "900",
                "--limit",
                "5",
            ],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        assert payload["stale_candidates_total"] == 1
        assert payload["captured_total"] == 1
        assert payload["captured"][0]["job_id"] == "job_script_incident_001"
        assert payload["incidents_total"] == 1
        incident = payload["returned_incidents"][0]
        assert incident["job_id"] == "job_script_incident_001"
        assert incident["run_id"] == "run_script_incident_001"
        assert incident["paper_id"] == "paper_script_incident_001"
        assert Path(incident["incident_path"]).exists()

        conn = db_utils.get_db_connection()
        event_type = conn.execute(
            """
            SELECT event_type
            FROM job_events
            WHERE job_id = ?
            ORDER BY ts DESC
            LIMIT 1
            """,
            ("job_script_incident_001",),
        ).fetchone()["event_type"]
        conn.close()
        assert event_type == "job_stale_incident_snapshot_captured"
    finally:
        db_utils.DB_PATH = original_db_path
