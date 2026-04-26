from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import src.db_utils as db_utils


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_readiness_script(
    *,
    db_path: Path,
    storage_dir: Path,
    extra_args: list[str] | None = None,
) -> dict:
    env = os.environ.copy()
    env["PAPERPIPE_DB_PATH"] = str(db_path)
    env["PAPERPIPE_STORAGE_DIR"] = str(storage_dir)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_stale_reclaim_readiness.py",
            "--stale-after-seconds",
            "900",
            "--limit",
            "50",
            *(extra_args or []),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _write_incident(
    *,
    storage_dir: Path,
    incident_id: str,
    job_id: str,
    captured_at: str,
    is_stale_candidate: bool = True,
) -> None:
    incident_dir = storage_dir / "stale_running_incidents" / incident_id
    incident_dir.mkdir(parents=True, exist_ok=True)
    (incident_dir / "incident.json").write_text(
        json.dumps(
            {
                "artifact_kind": "review_support",
                "layer": "review_gate_artifact",
                "incident_type": "stale_running_suspicion",
                "incident_id": incident_id,
                "captured_at": captured_at,
                "job_id": job_id,
                "run_id": f"run_{job_id}",
                "paper_id": f"paper_{job_id}",
                "status": "running",
                "is_stale_candidate": is_stale_candidate,
                "running_for_seconds": 1800,
                "stale_after_seconds": 900,
                "path_observations": {},
                "recent_job_events": [],
            }
        ),
        encoding="utf-8",
    )


def test_stale_reclaim_readiness_holds_when_no_incident_evidence(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    storage_dir = tmp_path / "storage"
    original_db_path = db_utils.DB_PATH
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    monkeypatch.setenv("PAPERPIPE_STORAGE_DIR", str(storage_dir))
    try:
        db_utils.init_db()
        payload = _run_readiness_script(db_path=db_path, storage_dir=storage_dir)

        assert payload["inputs"]["incidents_total"] == 0
        assert payload["inputs"]["current_stale_candidates_total"] == 0
        assert payload["decision"]["recommendation"] == "hold_no_incidents"
        assert payload["decision"]["auto_reclaim_ready"] is False
        assert "no_stale_incident_snapshots" in payload["decision"]["blockers"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_stale_reclaim_readiness_marks_clean_incident_set_review_ready(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    storage_dir = tmp_path / "storage"
    report_path = tmp_path / "readiness.json"
    original_db_path = db_utils.DB_PATH
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    monkeypatch.setenv("PAPERPIPE_STORAGE_DIR", str(storage_dir))
    try:
        db_utils.init_db()
        for index in range(3):
            _write_incident(
                storage_dir=storage_dir,
                incident_id=f"incident_{index}",
                job_id=f"job_script_ready_{index}",
                captured_at=f"2026-04-22T0{index}:00:00+00:00",
            )

        payload = _run_readiness_script(
            db_path=db_path,
            storage_dir=storage_dir,
            extra_args=["--output", str(report_path)],
        )

        assert payload["inputs"]["incidents_total"] == 3
        assert payload["inputs"]["stale_candidate_incidents_total"] == 3
        assert payload["inputs"]["unique_jobs_total"] == 3
        assert payload["decision"]["recommendation"] == "manual_review_ready"
        assert payload["decision"]["auto_reclaim_ready"] is False
        assert payload["decision"]["blockers"] == []
        assert report_path.exists()
        assert json.loads(report_path.read_text(encoding="utf-8"))["schema_version"] == (
            "stale_reclaim_readiness.v1"
        )
    finally:
        db_utils.DB_PATH = original_db_path
