import unittest
from unittest.mock import MagicMock, patch
import json
from src.agents.profile_chat_agent import ProfileChatAgent
from src.profiles.profile_schema import Profile, QuerySpec, Limits
from src.db_utils import init_run_stats_table, log_run_stat, get_profile_stats

class TestAdvancedLibrarian(unittest.TestCase):
    def setUp(self):
        self.profile = Profile(
            id="test_prof",
            title="Test Profile",
            enabled=True,
            schedule="daily",
            limits=Limits(max_results_per_run=100, date_window_days=365),
            query=QuerySpec(must=["brain"], should=[], must_not=[])
        )

    @patch("src.agents.profile_chat_agent.OllamaModelAdapter")
    def test_ontology_rule_in_prompt(self, MockAdapter):
        """Verify that the Ontology Expansion rule is present in the prompt."""
        agent = ProfileChatAgent()
        mock_instance = MockAdapter.return_value
        
        # Mock response to avoid actual generation error
        mock_instance.generate.return_value.text = json.dumps({
            "target_profile_id": "test_prof",
            "ops": []
        })

        agent.generate_patch(self.profile, "Search for sleep")
        
        # Check call args
        call_args = mock_instance.generate.call_args
        prompt_sent = call_args[0][0]
        
        self.assertIn("Ontology Expansion (Domain Expert)", prompt_sent)
        self.assertIn("AUTOMATICALLY expand it", prompt_sent)

    @patch("src.agents.profile_chat_agent.OllamaModelAdapter")
    def test_audit_fix_generation(self, MockAdapter):
        """Verify suggest_audit_fix constructs prompt and parses response."""
        agent = ProfileChatAgent()
        mock_instance = MockAdapter.return_value
        
        # Mock response
        expected_patch = {
            "target_profile_id": "test_prof",
            "ops": [
                {"op": "replace", "path": "limits.max_results_per_run", "value": 50, "rationale": "Reduce limit"}
            ]
        }
        mock_instance.generate.return_value.text = json.dumps(expected_patch)

        patch_req = agent.suggest_audit_fix(self.profile, hit_ratio=0.8, days=7)
        
        # Check Prompt
        call_args = mock_instance.generate.call_args
        prompt_sent = call_args[0][0]
        self.assertIn("Limit Hit Frequency: 80.0%", prompt_sent)
        self.assertIn("Current Limit: 100", prompt_sent)
        
        # Check Result
        self.assertEqual(patch_req.target_profile_id, "test_prof")
        self.assertEqual(patch_req.ops[0].value, 50)

    def test_run_stats_db(self):
        """Verify DB logging and retrieval."""
        # Use in-memory DB or temporary file?
        # Since src.db uses "state.db" constant, hard to mock without patching DB_PATH or creating temp db file.
        # We will mock sqlite3.connect in src.db
        
        with patch("src.db_utils.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            mock_cursor = mock_conn.cursor.return_value
            
            # Test Init
            init_run_stats_table()
            mock_cursor.execute.assert_called()
            self.assertIn("CREATE TABLE IF NOT EXISTS run_stats", mock_cursor.execute.call_args[0][0])
            
            # Test Log
            log_run_stat("test_prof", 50, True)
            self.assertIn("INSERT INTO run_stats", mock_cursor.execute.call_args[0][0])
            
            # Test Get
            # Mock fetchall return
            mock_cursor.fetchall.return_value = [
                {"profile_id": "test_prof", "items_fetched": 50, "limit_hit": 1, "timestamp": "2023-01-01"}
            ]
            stats = get_profile_stats("test_prof", days=7)
            self.assertEqual(len(stats), 1)
            self.assertEqual(stats[0]['items_fetched'], 50)

if __name__ == '__main__':
    unittest.main()
