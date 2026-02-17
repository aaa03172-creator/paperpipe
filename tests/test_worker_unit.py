import pytest
from unittest.mock import MagicMock, ANY
from src.jobs.worker import Worker
from src.jobs.schemas import JobStatus
from datetime import datetime

@pytest.fixture
def mock_queue():
    return MagicMock()

@pytest.fixture
def mock_processor():
    return MagicMock()

@pytest.fixture
def worker(mock_queue, mock_processor):
    return Worker(queue=mock_queue, processor=mock_processor)

def test_process_job_success(worker, mock_queue, mock_processor):
    # Setup
    job = JobStatus(
        job_id="test_job", 
        paper_id="p1", 
        status="queued", 
        progress=0, 
        created_at=datetime.now(),
        stage="init"
    )
    mock_queue.get_job.return_value = job
    mock_processor.process_single_paper.return_value = True

    # Action
    worker.process_job(job)

    # Verify
    mock_processor.process_single_paper.assert_called_once_with("p1", on_progress=ANY)
    mock_queue.update_job.assert_any_call("test_job", {"status": "running", "started_at": ANY})
    mock_queue.update_job.assert_any_call("test_job", {"status": "completed", "finished_at": ANY, "progress": 100, "stage": "Done"})

def test_process_job_failure(worker, mock_queue, mock_processor):
    # Setup
    job = JobStatus(
        job_id="test_job_fail", 
        paper_id="p1", 
        status="queued", 
        progress=0, 
        created_at=datetime.now(),
        stage="init"
    )
    mock_processor.process_single_paper.side_effect = Exception("Processing Error")

    # Action
    worker.process_job(job)

    # Verify
    mock_queue.update_job.assert_any_call("test_job_fail", {"status": "failed", "error_message": "Processing Error", "finished_at": ANY})

def test_process_job_cancellation(worker, mock_queue, mock_processor):
    # Setup
    job = JobStatus(
        job_id="test_job_cancel", 
        paper_id="p1", 
        status="queued", 
        progress=0, 
        created_at=datetime.now(),
        stage="init"
    )
    
    # Mock callback to simulate check during progress
    def fake_process(pid, on_progress):
        # Simulate step 1
        on_progress(10, "Step 1")
        # Now simulate cancellation from outside
        # The worker checks queue.get_job inside the callback
        cancelled_job = JobStatus(
            job_id="test_job_cancel", 
            paper_id="p1", 
            status="cancelled", 
            progress=10, 
            created_at=datetime.now(),
            stage="Step 1"
        )
        mock_queue.get_job.return_value = cancelled_job
        # Call callback again triggers check
        on_progress(20, "Step 2") 
        return True

    mock_processor.process_single_paper.side_effect = fake_process
    # Initial get_job returns normal
    mock_queue.get_job.return_value = job

    # Action
    worker.process_job(job)

    # Verify
    # Should catch InterruptedError and update to cancelled
    mock_queue.update_job.assert_any_call("test_job_cancel", {"status": "cancelled", "finished_at": ANY})
