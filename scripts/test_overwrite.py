
import unittest
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime, timedelta
from src.exporter import export_paper_to_markdown

class TestSmartOverwrite(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vault_path = Path(self.test_dir)
        (self.vault_path / "Inbox/PaperPipe").mkdir(parents=True)
        
        # Mock paper object
        self.paper = {
            'paper_id': 'testPaper2026',
            'title': 'Test Paper',
            'summary': 'Test Summary',
            'feedback_json': '{"soft_tags": ["Test"], "study_design": "Test", "evidence_span": "Test"}',
            'gate_decision': 'APPROVED',
            'status': 'INDEXED',
            'updated_at': datetime.now().isoformat()
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_new_file_creation(self):
        """Test that a new file is created when it doesn't exist."""
        updated = export_paper_to_markdown(self.paper, self.vault_path, overwrite=False)
        self.assertTrue(updated)
        self.assertTrue((self.vault_path / "Inbox/PaperPipe/testPaper2026.md").exists())

    def test_overwrite_db_newer(self):
        """Test overwrite when DB is newer than file."""
        # Create file with OLD timestamp
        fpath = self.vault_path / "Inbox/PaperPipe/testPaper2026.md"
        fpath.write_text("Old Content")
        
        # Set mtime to 2 hours ago to ensure significant difference
        # Note: os.utime takes (atime, mtime)
        old_time = (datetime.now() - timedelta(hours=2)).timestamp()
        os.utime(fpath, (old_time, old_time))
        
        # Paper updated_at is NOW (newer)
        # Verify timestamps for debugging if automated test fails again
        # print(f"File: {old_time}, DB: {self.paper['updated_at']}")
        
        updated = export_paper_to_markdown(self.paper, self.vault_path, overwrite=False)
        
        self.assertTrue(updated, "Should update when DB is newer")
        self.assertIn("Test Summary", fpath.read_text())

    def test_no_overwrite_db_older(self):
        """Test NO overwrite when DB is older than file."""
        # Create file with NEW timestamp (Simulate user edit)
        fpath = self.vault_path / "Inbox/PaperPipe/testPaper2026.md"
        fpath.write_text("User Edited Content")
        
        # Paper updated_at is 1 hour ago
        self.paper['updated_at'] = (datetime.now() - timedelta(hours=1)).isoformat()
        
        updated = export_paper_to_markdown(self.paper, self.vault_path, overwrite=False)
        
        self.assertFalse(updated)
        self.assertEqual(fpath.read_text(), "User Edited Content")

    def test_force_overwrite(self):
        """Test forced overwrite flag."""
        fpath = self.vault_path / "Inbox/PaperPipe/testPaper2026.md"
        fpath.write_text("User Edited Content")
        
        # DB is older, but overwrite=True
        self.paper['updated_at'] = (datetime.now() - timedelta(hours=1)).isoformat()
        
        updated = export_paper_to_markdown(self.paper, self.vault_path, overwrite=True)
        
        self.assertTrue(updated)
        self.assertIn("Test Summary", fpath.read_text())

if __name__ == '__main__':
    unittest.main()
