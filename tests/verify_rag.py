
import unittest
import shutil
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure root is in path
sys.path.append(str(Path(__file__).parent.parent))

from src.cli import deepread, ask
from create_rag_pdf import create_dummy_pdf
import src.agents.indexer_agent
import src.agents.adapter

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEST_DIR = Path("tests/temp_rag_test")
LIBRARY_DIR = TEST_DIR / "Library"
VAULT_DIR = TEST_DIR / "Vault"
RAG_DIR = TEST_DIR / "rag_store"

class TestRAGPipeline(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Cleanup previous run
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
        
        LIBRARY_DIR.mkdir(parents=True)
        VAULT_DIR.mkdir(parents=True)
        RAG_DIR.mkdir(parents=True)
        (VAULT_DIR / "Inbox").mkdir()
        (VAULT_DIR / "00_Index").mkdir()
        
        # Create Dummy PDF
        # Note: create_dummy_pdf writes to absolute path or relative to CWD
        # We pass absolute path
        cls.pdf_path = create_dummy_pdf(str(LIBRARY_DIR.resolve() / "Test_ID.pdf"))
        
        # Create Note
        cls.note_path = VAULT_DIR / "Inbox/test_note.md"
        cls.note_path.write_text("# Test Paper\nStatus: Inbox\n\nAbstract\n...", encoding="utf-8")
        
        # Create Index
        index_path = VAULT_DIR / "00_Index/paper_collection.csv"
        index_path.write_text("Paper_ID,DOI,Title,Note_Path\nTest_ID,10.1234/rag,Test Paper,Inbox/test_note.md\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        # Optional: cleanup
        # shutil.rmtree(TEST_DIR)
        pass

    @patch("src.config.load_config")
    @patch("src.agents.indexer_agent.load_config")
    @patch("src.agents.adapter.load_config")
    @patch("src.agents.adapter.OllamaModelAdapter.generate")
    def test_pipeline(self, mock_generate, mock_conf1, mock_conf2, mock_conf3):
        # Mock Config Construction
        mock_config = MagicMock()
        mock_config.paths.library_dir = LIBRARY_DIR
        mock_config.paths.obsidian_vault = VAULT_DIR
        mock_config.paths.index_all = "00_Index/paper_collection.csv"
        mock_config.agents.enabled = True
        mock_config.agents.main_model = "llama3:latest"
        mock_config.agents.rag_index_path = str(RAG_DIR)
        
        # LLM Config structure
        # Need to structure it so mock_config.llm.local.base_url works
        mock_config.llm.mode = "local"
        mock_config.llm.local.base_url = "http://localhost:11434"
        mock_config.entity_aliases = {}
        
        # Return mock config
        mock_conf1.return_value = mock_config
        mock_conf2.return_value = mock_config
        mock_conf3.return_value = mock_config
        
        # Mock LLM Output
        valid_json = """
        {
            "doc_id": "doi:10.1234/rag",
            "claims": [
                {
                    "claim_id": "C1",
                    "type": "efficacy",
                    "statement": "Section-aware RAG improved retrieval accuracy by 30%.",
                    "confidence": 0.95,
                    "evidence_spans": [],
                    "limitations": []
                }
            ]
        }
        """
        mock_result = MagicMock()
        mock_result.text = valid_json
        mock_generate.return_value = mock_result
        
        print("\n--- Testing Deep Read ---")
        # 1. Run Deep Read
        try:
            deepread("Test_ID")
        except SystemExit:
            pass
            
        # Check Note
        content = self.note_path.read_text()
        self.assertIn("## 🤖 Agent Deep Read", content, "Deep Read section missing in note!")
        print("✅ Deep Read verified.")
        
        print("\n--- Testing Ask ---")
        # 2. Run Ask
        try:
            ask("What is the chunk size used?")
        except SystemExit:
            pass
            
        print("✅ Ask command executed.")

if __name__ == "__main__":
    unittest.main()
