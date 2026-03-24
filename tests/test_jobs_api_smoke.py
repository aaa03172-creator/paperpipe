from pathlib import Path
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.db_utils as db_utils
import src.jobs.worker as worker_mod
from backend.services.job_runner import _resolve_ingest_parser_backend
from src.jobs.queue import JobQueue
from backend import main as api_main


def test_jobs_deepread_enqueue_worker_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        # 1) Enqueue from API with extended fields.
        resp = client.post(
            "/jobs/deepread",
            json={
                "paper_id": "paper_smoke_001",
                "clean_reindex": False,
                "run_verify": True,
                "reasoning_persona": "researcher",
                "profile_id": "smoke-profile",
                "parser_backend": "docling",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        job_id = payload["job_id"]
        run_id = payload["run_id"]
        assert payload["status"] == "queued"
        assert run_id is not None

        conn = db_utils.get_db_connection()
        action_row = conn.execute(
            """
            SELECT paper_id, action_type, source, payload_json
            FROM user_actions
            WHERE paper_id = ?
            ORDER BY ts DESC, rowid DESC
            LIMIT 1
            """,
            ("paper_smoke_001",),
        ).fetchone()
        conn.close()
        assert action_row is not None
        assert action_row["action_type"] == "deepread_enqueued"
        assert action_row["source"] == "ui"
        action_payload = json.loads(action_row["payload_json"])
        assert action_payload["job_id"] == job_id
        assert action_payload["run_id"] == run_id
        assert action_payload["persona_id"] == "smoke-profile"
        assert action_payload["reasoning_persona"] == "researcher"
        assert action_payload["profile_id"] == "smoke-profile"
        assert action_payload["parser_backend"] == "docling"

        queued = client.get(f"/jobs/{job_id}")
        assert queued.status_code == 200
        queued_data = queued.json()
        assert queued_data["status"] == "queued"
        assert queued_data["run_id"] == run_id
        assert queued_data["persona_id"] == "smoke-profile"
        assert queued_data["reasoning_persona"] == "researcher"
        assert queued_data["profile_id"] == "smoke-profile"
        assert queued_data["requested_parser_backend"] == "docling"
        assert queued_data["parser_backend"] is None
        assert queued_data["run_verify"] == 1
        assert queued_data["clean_reindex"] == 0
        assert queued_data["bootstrap_meta_path"] is None
        assert queued_data["similar_feedback_count"] is None
        assert queued_data["persona_applied"] is None
        assert queued_data["artifact_document_written"] is None
        assert queued_data["artifact_index_written"] is None
        assert queued_data["artifact_claimset_written"] is None
        assert queued_data["artifact_stats_written"] is None
        assert queued_data["claimset_readiness"] is None
        assert queued_data["claimset_ready"] is None
        assert queued_data["claimset_claim_count"] is None
        assert queued_data["claimset_readiness_reason"] is None
        assert queued_data["claimset_readiness_badge"] is None
        assert queued_data["claimset_ops_action"] is None
        assert queued_data["claimset_ops_alert"] is None
        assert queued_data["claimset_ops_note"] is None

        run_queued = client.get(f"/runs/{run_id}")
        assert run_queued.status_code == 200
        run_queued_data = run_queued.json()
        assert run_queued_data["job_id"] == job_id
        assert run_queued_data["run_id"] == run_id
        assert run_queued_data["reasoning_persona"] == "researcher"
        assert run_queued_data["profile_id"] == "smoke-profile"
        assert run_queued_data["requested_parser_backend"] == "docling"
        assert run_queued_data["parser_backend"] is None
        assert run_queued_data["clean_reindex"] == 0

        # 2) Worker claims job and runs pipeline (patched to smoke implementation).
        queue = JobQueue()
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id
        assert claimed.status == "running"

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            reasoning_persona: str | None = None,
            profile_id: str | None = None,
            parser_backend: str | None = None,
            run_verify: bool = False,
            clean_reindex: bool = False,
            run_id: str = None,
            progress_callback=None,
            cancel_check=None,
        ):
            assert persona_id == "smoke-profile"
            assert reasoning_persona == "researcher"
            assert profile_id == "smoke-profile"
            assert parser_backend == "docling"
            assert clean_reindex is False
            if progress_callback:
                await progress_callback(
                    {
                        "job_id": job_id,
                        "run_id": run_id,
                        "stage": "ingest",
                        "progress": 25,
                        "message": "smoke ingest",
                        "level": "INFO",
                        "timestamp": "2026-02-19T00:00:00Z",
                    }
                )
                await progress_callback(
                    {
                        "job_id": job_id,
                        "run_id": run_id,
                        "stage": "read",
                        "progress": 75,
                        "message": "smoke read",
                        "level": "INFO",
                        "timestamp": "2026-02-19T00:00:01Z",
                    }
                )
            return {
                "status": "succeeded",
                "run_id": run_id,
                "artifact_dir": f"storage/artifacts/{paper_id}/{run_id}",
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        # 3) Validate API status/progress/artifact surface after worker execution.
        done = client.get(f"/jobs/{job_id}")
        assert done.status_code == 200
        done_data = done.json()

        assert done_data["status"] == "completed"
        assert done_data["progress"] == 100
        assert done_data["stage"] == "completed"
        assert done_data["reasoning_persona"] == "researcher"
        assert done_data["profile_id"] == "smoke-profile"
        assert done_data["requested_parser_backend"] == "docling"
        assert done_data["parser_backend"] is None
        assert done_data["artifact_dir"] is not None
        assert done_data["log_path"] is not None
        assert done_data["bootstrap_meta_path"] is not None
        assert done_data["bootstrap_meta_path"].endswith("bootstrap_meta.json")
        assert done_data["similar_feedback_count"] is None
        assert done_data["persona_applied"] is None
        assert done_data["artifact_document_written"] is None
        assert done_data["artifact_index_written"] is None
        assert done_data["artifact_claimset_written"] is None
        assert done_data["artifact_claimset_resolved_written"] is None
        assert done_data["artifact_stats_written"] is None
        assert done_data["claimset_readiness"] is None
        assert done_data["claimset_ready"] is None
        assert done_data["claimset_claim_count"] is None
        assert done_data["claimset_grounded_span_count"] is None
        assert done_data["claimset_unresolved_span_count"] is None
        assert done_data["claimset_readiness_reason"] is None
        assert done_data["claimset_readiness_badge"] is None
        assert done_data["claimset_ops_action"] is None
        assert done_data["claimset_ops_alert"] is None
        assert done_data["claimset_ops_note"] is None
        assert Path(done_data["log_path"]).exists()

        # bootstrap meta file is not generated in this fake runner path.
        meta_resp = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert meta_resp.status_code == 404
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_bootstrap_meta_endpoint_returns_file_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_boot_meta")

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_boot_meta" / "run_1"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        meta = {"paper_id": "paper_boot_meta", "run_id": "run_1", "persona_applied": True}
        meta["parser_backend"] = "fitz_pdfplumber"
        meta["similar_feedback_count"] = 2
        meta["artifact_document_written"] = True
        meta["artifact_index_written"] = True
        meta["artifact_claimset_written"] = True
        meta["artifact_claimset_resolved_written"] = True
        meta["artifact_stats_written"] = False
        meta["claimset_readiness"] = "ready"
        meta["claimset_ready"] = True
        meta["claimset_claim_count"] = 3
        meta["claimset_grounded_span_count"] = 2
        meta["claimset_unresolved_span_count"] = 1
        meta["claimset_readiness_reason"] = "claims_present"
        meta["claimset_readiness_badge"] = "READY"
        meta["claimset_ops_action"] = "none"
        meta["claimset_ops_alert"] = False
        meta["claimset_ops_note"] = "ready"
        (artifact_dir / "bootstrap_meta.json").write_text(json.dumps(meta), encoding="utf-8")

        queue.update_job(
            job_id,
            {
                "status": "completed",
                "artifact_dir": str(artifact_dir),
                "progress": 100,
                "stage": "completed",
            },
        )

        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["bootstrap_meta_path"] == str(artifact_dir / "bootstrap_meta.json")
        assert payload["requested_parser_backend"] is None
        assert payload["parser_backend"] == "fitz_pdfplumber"
        assert payload["similar_feedback_count"] == 2
        assert payload["persona_applied"] is True
        assert payload["artifact_document_written"] is True
        assert payload["artifact_index_written"] is True
        assert payload["artifact_claimset_written"] is True
        assert payload["artifact_claimset_resolved_written"] is True
        assert payload["artifact_stats_written"] is False
        assert payload["claimset_readiness"] == "ready"
        assert payload["claimset_ready"] is True
        assert payload["claimset_claim_count"] == 3
        assert payload["claimset_grounded_span_count"] == 2
        assert payload["claimset_unresolved_span_count"] == 1
        assert payload["claimset_readiness_reason"] == "claims_present"
        assert payload["claimset_readiness_badge"] == "READY"
        assert payload["claimset_ops_action"] == "none"
        assert payload["claimset_ops_alert"] is False
        assert payload["claimset_ops_note"] == "ready"

        meta_resp = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert meta_resp.status_code == 200
        assert meta_resp.json()["paper_id"] == "paper_boot_meta"
        assert meta_resp.json()["parser_backend"] == "fitz_pdfplumber"
        assert meta_resp.json()["persona_applied"] is True
        assert meta_resp.json()["artifact_document_written"] is True
        assert meta_resp.json()["artifact_claimset_resolved_written"] is True
        assert meta_resp.json()["claimset_readiness"] == "ready"
        assert meta_resp.json()["claimset_ready"] is True
        assert meta_resp.json()["claimset_grounded_span_count"] == 2
        assert meta_resp.json()["claimset_unresolved_span_count"] == 1
        assert meta_resp.json()["claimset_readiness_badge"] == "READY"
        assert meta_resp.json()["claimset_ops_action"] == "none"
        assert meta_resp.json()["claimset_ops_alert"] is False
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_status_distinguishes_requested_and_effective_parser_backend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_parser_resolution", parser_backend="docling")
        job = queue.get_job(job_id)
        assert job is not None

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_parser_resolution" / str(job.run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "paper_id": "paper_parser_resolution",
            "run_id": str(job.run_id),
            "parser_backend": "fitz_pdfplumber",
        }
        (artifact_dir / "bootstrap_meta.json").write_text(json.dumps(meta), encoding="utf-8")

        queue.update_job(
            job_id,
            {
                "status": "completed",
                "artifact_dir": str(artifact_dir),
                "progress": 100,
                "stage": "completed",
            },
        )

        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["requested_parser_backend"] == "docling"
        assert payload["parser_backend"] == "fitz_pdfplumber"

        run_detail = client.get(f"/runs/{job.run_id}")
        assert run_detail.status_code == 200
        run_payload = run_detail.json()
        assert run_payload["requested_parser_backend"] == "docling"
        assert run_payload["parser_backend"] == "fitz_pdfplumber"
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_runtime_path_preserves_requested_and_effective_parser_backend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        resp = client.post(
            "/jobs/deepread",
            json={
                "paper_id": "paper_runtime_parser_resolution",
                "parser_backend": "docling",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        job_id = payload["job_id"]
        run_id = payload["run_id"]
        assert run_id is not None

        queue = JobQueue()
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            reasoning_persona: str | None = None,
            profile_id: str | None = None,
            parser_backend: str | None = None,
            run_verify: bool = False,
            clean_reindex: bool = False,
            run_id: str | None = None,
            progress_callback=None,
            cancel_check=None,
        ):
            assert paper_id == "paper_runtime_parser_resolution"
            assert parser_backend == "docling"
            assert run_id is not None
            artifact_dir = tmp_path / "storage" / "artifacts" / paper_id / run_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "bootstrap_meta.json").write_text(
                json.dumps(
                    {
                        "paper_id": paper_id,
                        "run_id": run_id,
                        "parser_backend": "fitz_pdfplumber",
                    }
                ),
                encoding="utf-8",
            )
            return {
                "status": "succeeded",
                "run_id": run_id,
                "artifact_dir": str(artifact_dir),
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["status"] == "completed"
        assert detail_payload["requested_parser_backend"] == "docling"
        assert detail_payload["parser_backend"] == "fitz_pdfplumber"
        assert detail_payload["bootstrap_meta_path"] is not None

        run_detail = client.get(f"/runs/{run_id}")
        assert run_detail.status_code == 200
        run_payload = run_detail.json()
        assert run_payload["status"] == "completed"
        assert run_payload["requested_parser_backend"] == "docling"
        assert run_payload["parser_backend"] == "fitz_pdfplumber"

        meta_resp = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert meta_resp.status_code == 200
        assert meta_resp.json()["parser_backend"] == "fitz_pdfplumber"
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_runtime_path_uses_job_runner_parser_resolution_helper(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        resp = client.post(
            "/jobs/deepread",
            json={
                "paper_id": "paper_runtime_parser_helper",
                "parser_backend": "docling",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        job_id = payload["job_id"]
        run_id = payload["run_id"]
        assert run_id is not None

        queue = JobQueue()
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.job_id == job_id

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            reasoning_persona: str | None = None,
            profile_id: str | None = None,
            parser_backend: str | None = None,
            run_verify: bool = False,
            clean_reindex: bool = False,
            run_id: str | None = None,
            progress_callback=None,
            cancel_check=None,
        ):
            assert paper_id == "paper_runtime_parser_helper"
            effective_backend = _resolve_ingest_parser_backend(
                SimpleNamespace(ingest=SimpleNamespace(parser_backend="fitz_pdfplumber", enable_docling=False)),
                override_backend=parser_backend,
            )
            assert effective_backend == "fitz_pdfplumber"
            artifact_dir = tmp_path / "storage" / "artifacts" / paper_id / str(run_id)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "bootstrap_meta.json").write_text(
                json.dumps(
                    {
                        "paper_id": paper_id,
                        "run_id": run_id,
                        "parser_backend": effective_backend,
                    }
                ),
                encoding="utf-8",
            )
            return {
                "status": "succeeded",
                "run_id": run_id,
                "artifact_dir": str(artifact_dir),
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["status"] == "completed"
        assert detail_payload["requested_parser_backend"] == "docling"
        assert detail_payload["parser_backend"] == "fitz_pdfplumber"

        run_detail = client.get(f"/runs/{run_id}")
        assert run_detail.status_code == 200
        run_payload = run_detail.json()
        assert run_payload["status"] == "completed"
        assert run_payload["requested_parser_backend"] == "docling"
        assert run_payload["parser_backend"] == "fitz_pdfplumber"
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_deepread_clean_reindex_flag_reaches_worker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        resp = client.post(
            "/jobs/deepread",
            json={
                "paper_id": "paper_clean_reindex_001",
                "clean_reindex": True,
                "run_verify": False,
                "persona_id": "default",
            },
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        run_id = resp.json()["run_id"]

        queue = JobQueue()
        claimed = queue.claim_next_job()
        assert claimed is not None
        assert claimed.clean_reindex == 1

        async def fake_run_deepread_job(
            job_id: str,
            paper_id: str,
            persona_id: str = "default",
            run_verify: bool = False,
            clean_reindex: bool = False,
            run_id: str | None = None,
            progress_callback=None,
            cancel_check=None,
        ):
            assert clean_reindex is True
            return {
                "status": "succeeded",
                "run_id": run_id,
                "artifact_dir": f"storage/artifacts/{paper_id}/{run_id}",
            }

        monkeypatch.setattr(worker_mod, "run_deepread_job", fake_run_deepread_job)
        worker = worker_mod.Worker()
        worker.process_job(claimed)

        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["status"] == "completed"
        assert payload["run_id"] == run_id
        assert payload["clean_reindex"] == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_bootstrap_meta_endpoint_handles_malformed_json_boundary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_boot_meta_broken")

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_boot_meta_broken" / "run_1"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        broken_meta = artifact_dir / "bootstrap_meta.json"
        broken_meta.write_text("{invalid_json", encoding="utf-8")

        queue.update_job(
            job_id,
            {
                "status": "completed",
                "artifact_dir": str(artifact_dir),
                "progress": 100,
                "stage": "completed",
            },
        )

        # /jobs/{id} should stay resilient even if bootstrap_meta parsing fails.
        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["bootstrap_meta_path"] == str(broken_meta)
        assert payload["similar_feedback_count"] is None
        assert payload["persona_applied"] is None
        assert payload["claimset_readiness"] is None
        assert payload["claimset_readiness_badge"] is None

        # /bootstrap-meta should surface parse error clearly.
        meta_resp = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert meta_resp.status_code == 500
        assert "Failed to parse bootstrap_meta" in meta_resp.json()["detail"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_bootstrap_meta_endpoint_returns_404_for_unknown_job():
    client = TestClient(api_main.app)
    resp = client.get("/jobs/no_such_job/bootstrap-meta")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


def test_jobs_bootstrap_meta_endpoint_returns_404_when_not_available(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)
        queue = JobQueue()
        job_id = queue.enqueue(paper_id="paper_boot_meta_unavailable")

        # artifact_dir is absent for queued jobs, so bootstrap-meta must be unavailable.
        resp = client.get(f"/jobs/{job_id}/bootstrap-meta")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "bootstrap_meta not available"
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_deepread_rejects_duplicate_open_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        first = client.post("/jobs/deepread", json={"paper_id": "paper_duplicate_001"})
        assert first.status_code == 200
        first_job_id = first.json()["job_id"]

        second = client.post("/jobs/deepread", json={"paper_id": "paper_duplicate_001"})
        assert second.status_code == 409
        detail = second.json()["detail"]
        assert detail["error_code"] == "JOB_ALREADY_OPEN"
        assert detail["paper_id"] == "paper_duplicate_001"
        assert detail["job_id"] == first_job_id
        assert detail["status"] == "queued"
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_deepread_rejects_when_queue_is_full(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_MAX_QUEUED_JOBS", "1")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        client = TestClient(api_main.app)

        first = client.post("/jobs/deepread", json={"paper_id": "paper_queue_full_001"})
        assert first.status_code == 200

        second = client.post("/jobs/deepread", json={"paper_id": "paper_queue_full_002"})
        assert second.status_code == 429
        detail = second.json()["detail"]
        assert detail["error_code"] == "QUEUE_FULL"
        assert detail["limit"] == 1
        assert detail["queued_count"] == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_job_queue_allows_reenqueue_after_terminal_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()

        first_job_id = queue.enqueue(paper_id="paper_reenqueue_001")
        queue.update_job(first_job_id, {"status": "completed"})

        second_job_id = queue.enqueue(paper_id="paper_reenqueue_001")
        assert second_job_id != first_job_id
    finally:
        db_utils.DB_PATH = original_db_path


def test_job_queue_claim_respects_configurable_max_concurrency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_MAX_CONCURRENT_JOBS", "2")

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        queue = JobQueue()
        first = queue.enqueue(paper_id="paper_concurrency_001")
        second = queue.enqueue(paper_id="paper_concurrency_002")

        claimed_first = queue.claim_next_job()
        claimed_second = queue.claim_next_job()
        claimed_third = queue.claim_next_job()

        assert claimed_first is not None
        assert claimed_first.job_id == first
        assert claimed_second is not None
        assert claimed_second.job_id == second
        assert claimed_third is None
    finally:
        db_utils.DB_PATH = original_db_path
