import requests
import time
import subprocess
import sys
import os
from pathlib import Path
import pytest
import fitz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db_utils import get_db_connection, init_db

API_URL = "http://127.0.0.1:8000"

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PHASE3_INTEGRATION") != "1",
    reason="Set RUN_PHASE3_INTEGRATION=1 to run live API/worker integration test.",
)


def _wait_for_health(api_url: str, timeout_seconds: int = 20, interval_seconds: float = 0.5) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(f"{api_url}/health", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval_seconds)
    return False


def _terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _ensure_test_pdf_for_paper(paper_id: str) -> tuple[Path, bool]:
    """
    Ensure there is a valid PDF in library_dir discoverable by run_deepread_job.
    Returns (pdf_path, created_now).
    """
    config = load_config()
    library_dir = Path(config.paths.library_dir)
    library_dir.mkdir(parents=True, exist_ok=True)

    existing = list(library_dir.rglob(f"*{paper_id}*.pdf"))
    if existing:
        return existing[0], False

    pdf_path = library_dir / f"{paper_id}.pdf"
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), f"Integration test PDF for {paper_id}")
        doc.save(str(pdf_path))
    finally:
        doc.close()
    return pdf_path, True


def _cleanup_stale_jobs_for_paper(paper_id: str) -> int:
    """
    Cancel stale queued/running jobs for the same integration paper.
    If another paper is currently running, abort integration to avoid interference.
    """
    conn = get_db_connection()
    try:
        try:
            rows = conn.execute(
                "SELECT job_id, paper_id, status FROM jobs WHERE status IN ('queued','running')"
            ).fetchall()
        except Exception:
            return 0

        blocking = [
            dict(r) for r in rows if r["status"] == "running" and str(r["paper_id"] or "") != paper_id
        ]
        if blocking:
            raise RuntimeError(
                f"Cannot run integration test while other running jobs exist: {[b['job_id'] for b in blocking]}"
            )

        targets = [dict(r) for r in rows if str(r["paper_id"] or "") == paper_id]
        for row in targets:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'cancelled',
                    finished_at = CURRENT_TIMESTAMP,
                    error_message = COALESCE(error_message, 'stale integration cleanup')
                WHERE job_id = ?
                """,
                (row["job_id"],),
            )
        conn.commit()
        return len(targets)
    finally:
        conn.close()


def _ensure_test_paper_row(paper_id: str) -> None:
    """
    Ensure the integration test paper exists in papers table so jobs/runs
    produced by this script do not become orphan references.
    """
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, source, created_at, updated_at)
            VALUES (?, ?, 'NEW', 'integration_test', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(paper_id) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP
            """,
            (paper_id, "Phase3 Integration Test Paper"),
        )
        conn.commit()
    finally:
        conn.close()


def _wait_for_job_terminal_status(
    api_url: str,
    job_id: str,
    max_polls: int = 120,
    interval_seconds: float = 1.0,
) -> dict:
    last_status = {"status": "unknown", "progress": 0}
    for _ in range(max_polls):
        resp = requests.get(f"{api_url}/jobs/{job_id}", timeout=3)
        status = resp.json()
        last_status = status
        print(f"   Status: {status['status']} | Progress: {status['progress']}%")

        if status["status"] in {"completed", "failed", "cancelled"}:
            return status
        time.sleep(interval_seconds)

    raise TimeoutError(f"Timed out waiting for terminal job status. Last status={last_status}")


def _tail_log(log_path: str | None, lines: int = 30) -> str:
    if not log_path:
        return "<no log_path>"
    path = Path(log_path)
    if not path.exists():
        return f"<missing log file: {log_path}>"
    try:
        content = path.read_text(encoding="utf-8").splitlines()
        return "\n".join(content[-lines:]) or "<empty log>"
    except Exception as exc:
        return f"<failed to read log tail: {exc}>"


def test_api_worker_integration():
    print("🚀 Starting Integration Test...")
    
    # Ensure DB exists
    init_db()
    paper_id = "test_paper_001"
    _ensure_test_paper_row(paper_id)
    prepared_pdf, created_pdf = _ensure_test_pdf_for_paper(paper_id)
    cleaned = _cleanup_stale_jobs_for_paper(paper_id)
    if cleaned:
        print(f"🧹 Cleaned stale jobs for {paper_id}: {cleaned}")

    # 1. Start Server
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if not _wait_for_health(API_URL, timeout_seconds=30):
        stderr_output = ""
        if server_proc.stderr:
            try:
                stderr_output = server_proc.stderr.read().decode("utf-8", errors="replace")
            except Exception:
                stderr_output = "<unable to read server stderr>"
        _terminate_process(server_proc)
        raise RuntimeError(
            "Backend failed to become healthy at /health within timeout.\n"
            f"Server stderr:\n{stderr_output}"
        )
    
    worker_proc = None
    try:
        # 2. Check Health
        resp = requests.get(f"{API_URL}/health", timeout=3)
        assert resp.status_code == 200
        print("✅ API Health OK")
        
        # 3. Enqueue Job
        resp = requests.post(
            f"{API_URL}/jobs/deepread",
            json={"paper_id": paper_id, "clean_reindex": True},
            timeout=5,
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        print(f"✅ Job Enqueued: {job_id} (pdf={prepared_pdf})")
        
        # 4. Start Worker (in separate process)
        worker_proc = subprocess.Popen(
            [sys.executable, "-m", "src.jobs.worker"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("👷 Worker Started...")
        
        # 5. Poll Status
        max_polls = int(os.getenv("PHASE3_MAX_POLLS", "120"))
        poll_interval = float(os.getenv("PHASE3_POLL_INTERVAL", "1"))
        final_status = _wait_for_job_terminal_status(
            API_URL,
            job_id,
            max_polls=max_polls,
            interval_seconds=poll_interval,
        )
        if final_status["status"] != "completed":
            log_tail = _tail_log(final_status.get("log_path"))
            raise AssertionError(
                f"Job did not complete successfully: {final_status}\n--- log tail ---\n{log_tail}"
            )
        print("✅ Job Completed!")
            
    finally:
        _terminate_process(server_proc)
        if worker_proc is not None:
            _terminate_process(worker_proc)
        if created_pdf:
            prepared_pdf.unlink(missing_ok=True)
            
if __name__ == "__main__":
    test_api_worker_integration()
