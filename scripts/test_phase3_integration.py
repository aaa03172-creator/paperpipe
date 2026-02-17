import requests
import time
import subprocess
import sys
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
    
    try:
        # 2. Check Health
        resp = requests.get(f"{API_URL}/health")
        assert resp.status_code == 200
        print("✅ API Health OK")
        
        # 3. Enqueue Job
        resp = requests.post(f"{API_URL}/jobs/deepread", json={"paper_id": "test_paper_001", "clean_reindex": True})
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
        for _ in range(15):
            resp = requests.get(f"{API_URL}/jobs/{job_id}")
            status = resp.json()
            print(f"   Status: {status['status']} | Progress: {status['progress']}%")
            
            if status['status'] == 'completed':
                print("✅ Job Completed!")
                break
            if status['status'] == 'failed':
                print("❌ Job Failed!")
                break
            time.sleep(1)
        else:
            print("❌ Timeout waiting for job completion")
            
    finally:
        server_proc.terminate()
        # worker_proc.terminate() # Variable might not be bound if earlier step fails, but handled in try/except usually. 
        # Adding check
        if 'worker_proc' in locals():
            worker_proc.terminate()
            
if __name__ == "__main__":
    test_api_worker_integration()
