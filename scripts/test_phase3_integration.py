import requests
import time
import subprocess
import sys
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db_utils import init_db

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


def _wait_for_job_terminal_status(
    api_url: str,
    job_id: str,
    max_polls: int = 15,
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


def test_api_worker_integration():
    print("🚀 Starting Integration Test...")
    
    # Ensure DB exists
    init_db()

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
            json={"paper_id": "test_paper_001", "clean_reindex": True},
            timeout=5,
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        print(f"✅ Job Enqueued: {job_id}")
        
        # 4. Start Worker (in separate process)
        worker_proc = subprocess.Popen(
            [sys.executable, "-m", "src.jobs.worker"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("👷 Worker Started...")
        
        # 5. Poll Status
        final_status = _wait_for_job_terminal_status(API_URL, job_id, max_polls=15, interval_seconds=1)
        if final_status["status"] != "completed":
            raise AssertionError(f"Job did not complete successfully: {final_status}")
        print("✅ Job Completed!")
            
    finally:
        _terminate_process(server_proc)
        if worker_proc is not None:
            _terminate_process(worker_proc)
            
if __name__ == "__main__":
    test_api_worker_integration()
