from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.db_event_log import (
    create_job,
    create_run,
    finish_run,
    log_event,
    log_user_action,
    update_job_status,
)


def test_run_timeline_endpoint_returns_replay_payload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        run_id = create_run(
            paper_id="doi:10.1000/timeline",
            trigger_source="test",
            pipeline_profile="grounded_read",
            run_id="run_timeline_1",
            params={"source": "unit"},
        )
        job_id = create_job(
            run_id=run_id,
            paper_id="doi:10.1000/timeline",
            job_type="deepread",
            job_id="job_timeline_1",
            params={"stage": "ingest"},
        )
        update_job_status(job_id, "running")
        log_event(job_id, "info", "step_start", "ingest started", {"stage": "ingest"})
        update_job_status(job_id, "completed", result_ref="storage/artifacts/x")
        finish_run(run_id, "succeeded", metrics={"duration_sec": 1.2})
        log_user_action("doi:10.1000/timeline", "important", "test", {"origin": "unit"})

        detail = client.get(f"/runs/{run_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["run"]["run_id"] == run_id
        assert payload["run"]["status"] == "succeeded"
        assert isinstance(payload["run"]["params_json"], dict)
        assert len(payload["jobs"]) == 1
        assert payload["jobs"][0]["job_id"] == job_id

        timeline = client.get(f"/runs/{run_id}/timeline?limit=50")
        assert timeline.status_code == 200
        data = timeline.json()
        assert data["run"]["run_id"] == run_id
        assert len(data["jobs"]) == 1
        assert len(data["events"]) >= 1
        assert data["events"][0]["job_id"] == job_id
        assert isinstance(data["events"][0]["payload_json"], dict)
        assert len(data["user_actions"]) == 1
        assert data["user_actions"][0]["action_type"] == "important"
        assert isinstance(data["user_actions"][0]["payload_json"], dict)
    finally:
        db_utils.DB_PATH = original_db_path


def test_run_timeline_endpoint_returns_404_for_missing_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        resp = client.get("/runs/run_missing/timeline")
        assert resp.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path
