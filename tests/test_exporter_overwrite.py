
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from src.exporter import export_paper_to_markdown

# Helper to create a sample paper with a specific updated_at time
def _sample_paper(updated_at=None):
    if updated_at is None:
        updated_at = datetime.now().isoformat()
    return {
        "paper_id": "paper_overwrite_test",
        "title": "Overwrite Test Paper",
        "summary": "Should include this summary.",
        "status": "APPROVED",
        "confidence": 0.95,
        "pdf_path": None,
        "feedback_json": '{"hard_tags":{}, "soft_tags":["#Test"]}',
        "updated_at": updated_at
    }

def test_new_file_creation(tmp_path):
    """Test that a new file is created when it doesn't exist."""
    paper = _sample_paper()
    vault_path = tmp_path
    
    # Run export
    updated = export_paper_to_markdown(paper, vault_path, overwrite=False)
    
    # Verify file created
    target_file = vault_path / "Inbox" / "PaperPipe" / "paper_overwrite_test.md"
    assert updated is True
    assert target_file.exists()
    assert "Overwrite Test Paper" in target_file.read_text(encoding="utf-8")

def test_overwrite_db_newer(tmp_path):
    """Test overwrite when DB is newer than file."""
    vault_path = tmp_path
    inbox = vault_path / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)
    target_file = inbox / "paper_overwrite_test.md"
    
    # 1. Create file with OLD content & OLD timestamp (2 hours ago)
    target_file.write_text("Old Content", encoding="utf-8")
    old_time = (datetime.now() - timedelta(hours=2)).timestamp()
    os.utime(target_file, (old_time, old_time))
    
    # 2. Prepare paper with CURRENT timestamp (Newer)
    paper = _sample_paper(updated_at=datetime.now().isoformat())
    
    # 3. Run export (overwrite=False)
    updated = export_paper_to_markdown(paper, vault_path, overwrite=False)
    
    # 4. Assert updated
    assert updated is True, "Should update when DB is newer"
    content = target_file.read_text(encoding="utf-8")
    assert "Overwrite Test Paper" in content
    assert "Old Content" not in content

def test_no_overwrite_db_older(tmp_path):
    """Test NO overwrite when DB is older than file (User edits preserved)."""
    vault_path = tmp_path
    inbox = vault_path / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)
    target_file = inbox / "paper_overwrite_test.md"
    
    # 1. Create file with NEW content (Current time)
    target_file.write_text("User Edited Content", encoding="utf-8")
    # Ensure file time is strictly NOW or slightly future relative to DB
    # We can rely on write() setting it to NOW.
    
    # 2. Prepare paper with OLD timestamp (1 hour ago)
    old_db_time = (datetime.now() - timedelta(hours=1)).isoformat()
    paper = _sample_paper(updated_at=old_db_time)
    
    # 3. Run export (overwrite=False)
    updated = export_paper_to_markdown(paper, vault_path, overwrite=False)
    
    # 4. Assert NOT updated
    assert updated is False, "Should NOT update when DB is older"
    content = target_file.read_text(encoding="utf-8")
    assert "User Edited Content" in content

def test_force_overwrite(tmp_path):
    """Test forced overwrite even if DB is older."""
    vault_path = tmp_path
    inbox = vault_path / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)
    target_file = inbox / "paper_overwrite_test.md"
    
    # 1. Create file with NEW content
    target_file.write_text("User Edited Content", encoding="utf-8")
    
    # 2. Prepare paper with OLD timestamp
    old_db_time = (datetime.now() - timedelta(hours=1)).isoformat()
    paper = _sample_paper(updated_at=old_db_time)
    
    # 3. Run export with overwrite=True
    updated = export_paper_to_markdown(paper, vault_path, overwrite=True)
    
    # 4. Assert Updated
    assert updated is True, "Force overwrite should trigger update"
    content = target_file.read_text(encoding="utf-8")
    assert "Overwrite Test Paper" in content

def test_no_overwrite_missing_updated_at(tmp_path):
    """Test NO overwrite when updated_at is missing (Safety fallback)."""
    vault_path = tmp_path
    inbox = vault_path / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)
    target_file = inbox / "paper_overwrite_test.md"
    
    # 1. Create file with User Content
    target_file.write_text("User Content", encoding="utf-8")
    
    # 2. Paper with None updated_at
    paper = _sample_paper(updated_at=None)
    paper['updated_at'] = None # Explicitly set None
    
    # 3. Export
    updated = export_paper_to_markdown(paper, vault_path, overwrite=False)
    
    # 4. Assert
    assert updated is False
    assert target_file.read_text(encoding="utf-8") == "User Content"

def test_no_overwrite_malformed_updated_at(tmp_path):
    """Test NO overwrite when updated_at is malformed string."""
    vault_path = tmp_path
    inbox = vault_path / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)
    target_file = inbox / "paper_overwrite_test.md"
    
    # 1. Create file with User Content
    target_file.write_text("User Content", encoding="utf-8")
    
    # 2. Paper with BAD updated_at
    paper = _sample_paper(updated_at="NOT-A-DATE")
    
    # 3. Export
    updated = export_paper_to_markdown(paper, vault_path, overwrite=False)
    
    # 4. Assert
    assert updated is False
    assert target_file.read_text(encoding="utf-8") == "User Content"
