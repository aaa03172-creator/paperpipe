import unittest
from unittest.mock import MagicMock, patch
from src.agents.stats_agent import StatsVerificationAgent, StatsAgentState
from src.schemas.agent_artifacts import DocumentArtifact, ClaimSet, SourceInfo, PaperMetadata, ScientificClaim

class TestStatsAgent(unittest.TestCase):
    def setUp(self):
        self.doc = DocumentArtifact(
            doc_id="doc1",
            source=SourceInfo(type="text", ref="test"),
            metadata=PaperMetadata(title="Test", authors=[]),
            tables=[]
        )
        self.claims = ClaimSet(
            doc_id="doc1",
            claims=[ScientificClaim(
                claim_id="c1", type="efficacy", statement="Drug A improved survival (p < 0.05).", confidence=0.9
            )]
        )

    def test_graph_construction(self):
        agent = StatsVerificationAgent()
        self.assertIsNotNone(agent.workflow)

    @patch("src.agents.stats_agent.OllamaModelAdapter")
    @patch("src.agents.stats_agent.DockerSandbox")
    def test_execution_flow(self, MockSandbox, MockAdapter):
        agent = StatsVerificationAgent()
        
        # Mock LLM responses
        mock_llm = MockAdapter.return_value
        mock_llm.generate.side_effect = [
            MagicMock(text='[{"test_type": "t-test", "reported_p": "0.05"}]'), # Extract
            MagicMock(text='Plan: Run t-test'), # Plan
            MagicMock(text='```python\nprint({"verdict": "verified"})\n```'), # Code
            MagicMock(text='[{"check_id": "c1", "test_type": "t-test", "verdict": "verified"}]') # Reflect
        ]
        
        # Mock Sandbox
        mock_box = MockSandbox.return_value
        mock_box.run_code.return_value = (0, 'JSON Output', '')

        # Run
        report = agent.run("job1", self.doc, self.claims)
        
        self.assertIsNotNone(report)
        self.assertEqual(len(report.checks), 1)
        self.assertEqual(report.checks[0].verdict, "verified")

if __name__ == '__main__':
    unittest.main()
