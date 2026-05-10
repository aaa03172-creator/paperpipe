import unittest
from unittest.mock import patch
from src.profiles.profile_schema import Profile, QuerySpec
from src.agents.profile_chat_agent import ProfileChatAgent

class TestProfileChat(unittest.TestCase):
    def setUp(self):
        self.profile = Profile(
            id="test_profile",
            title="Test Profile",
            query=QuerySpec(must=["brain"])
        )

    @patch("src.agents.profile_chat_agent.load_config")
    @patch("src.agents.profile_chat_agent.OllamaModelAdapter")
    def test_agent_generation(self, MockAdapter, mock_load_config):
        # Mock LLM Response
        mock_load_config.return_value = unittest.mock.MagicMock(agents=None)
        mock_instance = MockAdapter.return_value
        mock_instance.generate.return_value.text = """
        {
            "target_profile_id": "test_profile",
            "ops": [
                {
                    "op": "add",
                    "path": "query.must",
                    "value": "neuron",
                    "rationale": "User asked for neuron"
                }
            ],
            "meta": {}
        }
        """
        
        agent = ProfileChatAgent()
        patch = agent.generate_patch(self.profile, "Add neuron")
        prompt = mock_instance.generate.call_args[0][0]
        
        self.assertEqual(patch.target_profile_id, "test_profile")
        self.assertEqual(len(patch.ops), 1)
        self.assertEqual(patch.ops[0].value, "neuron")
        self.assertIn("biomaterial scaffold", prompt)
        self.assertIn("fibrosis", prompt)
        self.assertNotIn("microglia", prompt)

    @patch("src.agents.profile_chat_agent.load_config")
    @patch("src.agents.profile_chat_agent.OllamaModelAdapter")
    def test_agent_id_correction(self, MockAdapter, mock_load_config):
        # Test if agent fixes wrong ID
        mock_load_config.return_value = unittest.mock.MagicMock(agents=None)
        mock_instance = MockAdapter.return_value
        mock_instance.generate.return_value.text = """
        {
            "target_profile_id": "WRONG_ID",
            "ops": []
        }
        """
        
        agent = ProfileChatAgent()
        patch = agent.generate_patch(self.profile, "Do nothing")
        
        self.assertEqual(patch.target_profile_id, "test_profile") # Should be corrected

if __name__ == '__main__':
    unittest.main()
