import json

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from backend import main as api_main
from src.jobs.queue import JobQueue
from src.services.identity import artifact_paper_segment


def _set_artifacts_root(monkeypatch, root):
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(root))


def test_artifacts_latest_and_run_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_artifacts_root(monkeypatch, tmp_path / "storage" / "artifacts")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_old",
                "run_old",
                "paper_artifacts_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:00:00",
                "2026-02-24 00:00:05",
                str(tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_old"),
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_new",
                "run_new",
                "paper_artifacts_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:01:00",
                "2026-02-24 00:01:05",
                str(tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_new"),
            ),
        )
        conn.commit()
        conn.close()

        old_dir = tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_old"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "old"}), encoding="utf-8")

        new_dir = tmp_path / "storage" / "artifacts" / "paper_artifacts_001" / "run_new"
        new_dir.mkdir(parents=True, exist_ok=True)
        (new_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "new"}), encoding="utf-8")
        (new_dir / "claimset.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
        (new_dir / "bootstrap_meta.json").write_text(
            json.dumps({"claimset_readiness_badge": "READY"}), encoding="utf-8"
        )

        client = TestClient(api_main.app)

        latest = client.get("/artifacts/paper_artifacts_001/latest")
        assert latest.status_code == 200
        latest_payload = latest.json()
        assert latest_payload["run_id"] == "run_new"
        assert latest_payload["files"]["document_artifact"]["exists"] is True
        assert latest_payload["files"]["document_artifact"]["data"]["doc_id"] == "new"

        old = client.get("/artifacts/paper_artifacts_001/run_old")
        assert old.status_code == 200
        old_payload = old.json()
        assert old_payload["run_id"] == "run_old"
        assert old_payload["files"]["document_artifact"]["data"]["doc_id"] == "old"

        claimset = client.get("/artifacts/paper_artifacts_001/run_new/claimset")
        assert claimset.status_code == 200
        claimset_payload = claimset.json()
        assert claimset_payload["exists"] is True
        assert claimset_payload["data"]["claims"] == []

        stats_missing = client.get("/artifacts/paper_artifacts_001/run_new/stats")
        assert stats_missing.status_code == 404

        unknown_artifact = client.get("/artifacts/paper_artifacts_001/run_new/nope")
        assert unknown_artifact.status_code == 404

        missing = client.get("/artifacts/paper_artifacts_001/run_missing")
        assert missing.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_latest_honors_artifacts_root_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_artifacts = tmp_path / "external-artifacts"
    _set_artifacts_root(monkeypatch, custom_artifacts)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_override",
                "run_override",
                "paper_override_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:02:00",
                "2026-02-24 00:02:05",
                None,
            ),
        )
        conn.commit()
        conn.close()

        run_dir = custom_artifacts / "paper_override_001" / "run_override"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "override"}), encoding="utf-8")
        (run_dir / "claimset.resolved.json").write_text(
            json.dumps(
                {
                    "claims": [
                        {"claim_id": "c1", "evidence_spans": [{"page": 0}]},
                        {"claim_id": "c2", "evidence_spans": [{"page": 2}]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        client = TestClient(api_main.app)
        latest = client.get("/artifacts/paper_override_001/latest")
        assert latest.status_code == 200
        payload = latest.json()
        assert payload["run_id"] == "run_override"
        assert payload["files"]["document_artifact"]["data"]["doc_id"] == "override"
        assert payload["files"]["claimset_resolved"]["exists"] is True
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_routes_support_unsafe_paper_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_artifacts = tmp_path / "external-artifacts"
    _set_artifacts_root(monkeypatch, custom_artifacts)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        paper_id = "doi:10.1000/test-paper"
        run_id = "run_override"
        run_dir = custom_artifacts / artifact_paper_segment(paper_id) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "document_artifact.json").write_text(json.dumps({"doc_id": "unsafe"}), encoding="utf-8")

        client = TestClient(api_main.app)

        latest = client.get(f"/artifacts/{paper_id}/latest")
        assert latest.status_code == 200
        latest_payload = latest.json()
        assert latest_payload["run_id"] == run_id
        assert latest_payload["files"]["document_artifact"]["data"]["doc_id"] == "unsafe"

        exact = client.get("/artifacts", params={"paper_id": paper_id, "run_id": run_id})
        assert exact.status_code == 200
        exact_payload = exact.json()
        assert exact_payload["run_id"] == run_id
        assert exact_payload["files"]["document_artifact"]["data"]["doc_id"] == "unsafe"
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_routes_do_not_resolve_traversal_ids_outside_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "storage" / "artifacts"
    _set_artifacts_root(monkeypatch, artifacts)

    outside_run = tmp_path / "outside" / "run_escape"
    outside_run.mkdir(parents=True, exist_ok=True)
    (outside_run / "document_artifact.json").write_text(json.dumps({"doc_id": "escaped"}), encoding="utf-8")

    client = TestClient(api_main.app)

    paper_escape = client.get("/artifacts/..%2Foutside/run_escape")
    assert paper_escape.status_code == 404
    assert "escaped" not in paper_escape.text

    run_escape = client.get("/artifacts/paper_safe_001/..%2F..%2Foutside%2Frun_escape")
    assert run_escape.status_code == 404
    assert "escaped" not in run_escape.text

    query_escape = client.get(
        "/artifacts",
        params={"paper_id": "paper_safe_001", "run_id": "../../outside/run_escape"},
    )
    assert query_escape.status_code == 404
    assert "escaped" not in query_escape.text


def test_artifacts_latest_does_not_serve_db_artifact_dir_outside_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "storage" / "artifacts"
    _set_artifacts_root(monkeypatch, artifacts)

    outside_run = tmp_path / "outside-artifacts" / "paper_db_pointer_001" / "run_outside"
    outside_run.mkdir(parents=True, exist_ok=True)
    (outside_run / "document_artifact.json").write_text(json.dumps({"doc_id": "outside"}), encoding="utf-8")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, run_id, paper_id, status, progress, stage, created_at, finished_at, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job_outside_pointer",
                "run_outside",
                "paper_db_pointer_001",
                "completed",
                100,
                "completed",
                "2026-02-24 00:03:00",
                "2026-02-24 00:03:05",
                str(outside_run),
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        response = client.get("/artifacts/paper_db_pointer_001/latest")

        assert response.status_code == 404
        assert "doc_id" not in response.text
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_bundle_reports_malformed_json_sidecar_without_breaking_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "storage" / "artifacts"
    _set_artifacts_root(monkeypatch, artifacts)

    run_dir = artifacts / "paper_malformed_sidecar" / "run_bad_json"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "document_artifact.json").write_text('{"doc_id": "ok"}', encoding="utf-8")
    (run_dir / "run_meta.json").write_text('{"selected_backend": ', encoding="utf-8")

    client = TestClient(api_main.app)

    bundle = client.get("/artifacts/paper_malformed_sidecar/run_bad_json")
    assert bundle.status_code == 200
    payload = bundle.json()
    assert payload["paper_id"] == "paper_malformed_sidecar"
    assert payload["run_id"] == "run_bad_json"
    assert payload["files"]["document_artifact"]["exists"] is True
    assert payload["files"]["document_artifact"]["data"]["doc_id"] == "ok"
    assert payload["files"]["run_meta"]["exists"] is True
    assert "_parse_error" in payload["files"]["run_meta"]["data"]

    run_meta = client.get("/artifacts/paper_malformed_sidecar/run_bad_json/meta")
    assert run_meta.status_code == 200
    assert run_meta.json()["exists"] is True
    assert "_parse_error" in run_meta.json()["data"]


def test_runs_status_and_timeline_from_job_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        job_id = queue.enqueue("paper_runs_001")
        run_id = queue.get_job(job_id).run_id

        log_path = tmp_path / "logs" / "jobs" / f"{job_id}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "job_id": job_id,
                            "run_id": run_id,
                            "stage": "read",
                            "progress": 70,
                            "message": "analysis running",
                            "level": "INFO",
                            "timestamp": "2026-02-24T00:00:01Z",
                        }
                    ),
                    "plain text line",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "log_path": str(log_path),
                "finished_at": "2026-02-24T00:00:03+00:00",
            },
        )

        client = TestClient(api_main.app)

        run_status = client.get(f"/runs/{run_id}")
        assert run_status.status_code == 200
        run_payload = run_status.json()
        assert run_payload["job_id"] == job_id
        assert run_payload["run_id"] == run_id
        assert run_payload["status"] == "completed"

        timeline = client.get(f"/runs/{run_id}/timeline", params={"limit": 10})
        assert timeline.status_code == 200
        timeline_payload = timeline.json()
        assert timeline_payload["run_id"] == run_id
        assert timeline_payload["job_id"] == job_id
        assert len(timeline_payload["events"]) >= 2
        assert any(evt["event"] == "log" and evt.get("message") == "analysis running" for evt in timeline_payload["events"])
        assert any(evt["event"] == "done" and evt.get("message") == "completed" for evt in timeline_payload["events"])

        no_run = client.get("/runs/no_such_run")
        assert no_run.status_code == 404
        no_timeline = client.get("/runs/no_such_run/timeline")
        assert no_timeline.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path
