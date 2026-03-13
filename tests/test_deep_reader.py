from unittest.mock import MagicMock, patch

from src.agents.deep_reader import DeepReadAgent


@patch("src.agents.deep_reader.load_config")
def test_deep_reader_disabled_agents_returns_not_initialized(mock_load_config):
    mock_config = MagicMock()
    mock_config.agents.enabled = False
    mock_load_config.return_value = mock_config

    agent = DeepReadAgent()

    assert agent.agent is None
    assert agent.run("paper body", {"title": "Paper"}) == "❌ Agent not initialized (Check config or dependencies)."


@patch("src.agents.deep_reader.load_config")
@patch("src.agents.deep_reader.Agent", None)
def test_deep_reader_missing_effgen_keeps_agent_uninitialized(mock_load_config):
    mock_config = MagicMock()
    mock_config.agents.enabled = True
    mock_load_config.return_value = mock_config

    agent = DeepReadAgent()

    assert agent.agent is None
