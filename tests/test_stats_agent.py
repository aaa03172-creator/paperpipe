import unittest
from unittest.mock import MagicMock, patch
from src.agents.stats_agent import StatsVerificationAgent
from src.schemas.agent_artifacts import (
    DocumentArtifact,
    ClaimSet,
    SourceInfo,
    PaperMetadata,
    ScientificClaim,
    TableData,
)
from src.contracts.document_artifact_v2 import DocumentArtifactV2, ArtifactMetaV2, TableV2

class TestStatsAgent(unittest.TestCase):
    def setUp(self):
        table = TableData(
            table_id="T1",
            caption="Test table",
            data=[["group1", "group2"], ["1", "2"], ["3", "4"]],
            source_page=1,
        )
        self.doc = DocumentArtifact(
            doc_id="doc1",
            source=SourceInfo(type="text", ref="test"),
            metadata=PaperMetadata(title="Test", authors=[]),
            tables=[table]
        )
        self.claims = ClaimSet(
            doc_id="doc1",
            claims=[ScientificClaim(
                claim_id="c1", type="efficacy", statement="Drug A improved survival (p < 0.05).", confidence=0.9
            )]
        )
        self.doc_v2 = DocumentArtifactV2(
            document_id="doc1",
            meta=ArtifactMetaV2(
                title="Test",
                authors=[],
                source_ref="test.pdf",
            ),
            pages=[],
            tables=[
                TableV2(
                    table_id="T1",
                    caption="Test table",
                    data=[["group1", "group2"], ["1", "2"], ["3", "4"]],
                    source_page=1,
                )
            ],
        )

    @patch("src.agents.stats_agent.load_config")
    @patch("src.agents.stats_agent.OllamaModelAdapter")
    def test_graph_construction(self, _mock_adapter, mock_load_config):
        mock_load_config.return_value = MagicMock()
        agent = StatsVerificationAgent()
        self.assertIsNotNone(agent.workflow)

    @patch("src.agents.stats_agent.load_config")
    @patch("src.agents.stats_agent.OllamaModelAdapter")
    @patch("src.agents.stats_agent.DockerSandbox")
    def test_execution_flow(self, MockSandbox, MockAdapter, mock_load_config):
        mock_load_config.return_value = MagicMock()
        agent = StatsVerificationAgent()
        
        # Mock LLM responses
        mock_llm = MockAdapter.return_value
        mock_llm.generate.side_effect = [
            MagicMock(text='[{"test_type": "t-test", "reported_p": "0.05"}]'), # Extract
            MagicMock(text='Plan: Run t-test'), # Plan
            MagicMock(text='```python\nprint({"verdict": "verified"})\n```'), # Code
            MagicMock(text='[{"check_id": "c1", "test_type": "t-test", "verdict": "verified"}]'), # Reflect
            MagicMock(text='[{"test_type": "t-test", "reported_p": "0.05"}]'), # Extract (v2)
            MagicMock(text='Plan: Run t-test'), # Plan (v2)
            MagicMock(text='```python\nprint({"verdict": "verified"})\n```'), # Code (v2)
            MagicMock(text='[{"check_id": "c1", "test_type": "t-test", "verdict": "verified"}]') # Reflect (v2)
        ]
        
        # Mock Sandbox
        mock_box = MockSandbox.return_value
        mock_box.run_code.return_value = (0, 'JSON Output', '')

        # Run
        report = agent.run("job1", self.doc, self.claims)
        
        self.assertIsNotNone(report)
        self.assertEqual(len(report.checks), 1)
        self.assertEqual(report.checks[0].verdict, "verified")

        report_v2 = agent.run("job2", self.doc_v2, self.claims)
        self.assertIsNotNone(report_v2)
        self.assertEqual(report_v2.doc_id, "doc1")
        self.assertEqual(len(report_v2.checks), 1)
        self.assertEqual(report_v2.checks[0].verdict, "verified")

if __name__ == '__main__':
    unittest.main()
