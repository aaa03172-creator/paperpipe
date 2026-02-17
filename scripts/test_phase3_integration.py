import requests
import time
import subprocess
import sys
import sqlite3
from src.db_utils import init_db

API_URL = "http://127.0.0.1:8000"

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
    time.sleep(3) # Wait for server
    
    # Initialize worker_proc variable
    worker_proc = None

    try:
        # 2. Check Health
        resp = requests.get(f"{API_URL}/health")
        assert resp.status_code == 200
        print("✅ API Health OK")
        
        # 3. Insert Dummy Paper for Testing
        print("📝 Inserting dummy paper...")
        conn = sqlite3.connect("storage/state.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO papers (paper_id, title, status, summary, pdf_path, created_at, updated_at)
            VALUES ('integration_test_paper', 'Integration Test Paper', 'NEW', 'Abstract', 'tests/fixtures/dummy.pdf', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)
        conn.commit()
        conn.close()

        # 4. Enqueue Job
        print("🚀 Enqueuing Job...")
        resp = requests.post(f"{API_URL}/jobs/deepread", json={"paper_id": "integration_test_paper", "clean_reindex": True})
        if resp.status_code != 200:
             raise AssertionError(f"Enqueue failed ({resp.status_code}): {resp.text}")
             
        job_id = resp.json()["job_id"]
        print(f"✅ Job Enqueued: {job_id}")
        
        # 5. Start Worker (in separate process)
        worker_proc = subprocess.Popen(
            [sys.executable, "-m", "src.jobs.worker"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("👷 Worker Started...")
        
        # 6. Poll Status
        for _ in range(30):
            resp = requests.get(f"{API_URL}/jobs/{job_id}")
            status = resp.json()
            print(f"   Status: {status['status']} | Progress: {status['progress']}%")
            
            if status['status'] == 'completed':
                print("✅ Job Completed!")
                break
            if status['status'] == 'failed':
                raise AssertionError(f"Job failed: {status.get('error_message')}")
            time.sleep(1)
        else:
            raise TimeoutError("Timeout waiting for job completion")
            
    except Exception as e:
        print(f"❌ Test Error: {e}")
        raise
            
    finally:
        print("🛑 Cleaning up processes...")
        server_proc.terminate()
        if worker_proc:
            worker_proc.terminate()
            
if __name__ == "__main__":
    test_api_worker_integration()
