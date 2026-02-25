import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.db_utils as db_utils
from src.jobs.queue import JobQueue
from backend import main as api_main
from backend.routers import obsidian as obsidian_router


def _setup_temp_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()
    return original_db_path


def test_papers_endpoint_masks_absolute_pdf_path_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "true")
    original_db_path = _setup_temp_db(tmp_path, monkeypatch)
    try:
        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_mask_001", "Masked Paper", "INDEXED", str(pdf_file), "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        detail = client.get("/papers/paper_mask_001")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["pdf_exists"] is True
        assert payload["pdf_path"] is not None
        assert not Path(payload["pdf_path"]).is_absolute()
    finally:
        db_utils.DB_PATH = original_db_path


def test_jobs_endpoint_masks_absolute_runtime_paths_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "true")
    original_db_path = _setup_temp_db(tmp_path, monkeypatch)
    try:
        queue = JobQueue()
        job_id = queue.enqueue("paper_job_mask_001")
        job = queue.get_job(job_id)
        assert job is not None

        artifact_dir = tmp_path / "storage" / "artifacts" / "paper_job_mask_001" / str(job.run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "bootstrap_meta.json").write_text(
            json.dumps({"paper_id": "paper_job_mask_001", "run_id": job.run_id}),
            encoding="utf-8",
        )
        log_path = tmp_path / "logs" / "jobs" / f"{job_id}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("{}", encoding="utf-8")

        queue.update_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "artifact_dir": str(artifact_dir),
                "log_path": str(log_path),
            },
        )

        client = TestClient(api_main.app)
        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["artifact_dir"] is not None and not Path(payload["artifact_dir"]).is_absolute()
        assert payload["log_path"] is not None and not Path(payload["log_path"]).is_absolute()
        assert payload["bootstrap_meta_path"] is not None and not Path(payload["bootstrap_meta_path"]).is_absolute()
    finally:
        db_utils.DB_PATH = original_db_path


def test_obsidian_sync_masks_response_file_path_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "true")
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    target_note = vault_dir / "paper_sync_mask_001.md"
    target_note.write_text("# paper_sync_mask_001\n", encoding="utf-8")

    monkeypatch.setattr(
        obsidian_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    run_dir = tmp_path / "storage" / "artifacts" / "paper_sync_mask_001" / "run_sync_mask_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    claimset = {
        "doc_id": "paper_sync_mask_001",
        "claims": [
            {
                "claim_id": "c-mask",
                "type": "efficacy",
                "statement": "masked path claim",
                "confidence": 0.9,
                "evidence_spans": [{"raw_text": "masked path evidence"}],
            }
        ],
    }
    (run_dir / "claimset.resolved.json").write_text(json.dumps(claimset), encoding="utf-8")

    client = TestClient(api_main.app)
    response = client.post("/obsidian/sync", json={"paper_id": "paper_sync_mask_001", "run_id": "run_sync_mask_001"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["file"] is not None
    assert not Path(payload["file"]).is_absolute()
