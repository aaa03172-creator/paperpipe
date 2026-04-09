from unittest.mock import MagicMock, patch

from src.agents.reader_agent import ReaderAgent


@patch("src.agents.reader_agent.OllamaModelAdapter")
def test_reader_uses_boundary_aligned_base_prompt_and_runtime_overlay(mock_adapter):
    mock_adapter.return_value = MagicMock()

    reader = ReaderAgent(
        model_name="llama3:latest",
        persona_hint="reasoning_persona=librarian\nprofile_id=coglab",
    )

    assert "evidence-grounded Deep Read analyst" in reader.system_prompt
    assert "separate from optional reasoning persona, profile context, and feedback overlays" in reader.system_prompt
    assert "Runtime overlay:" in reader.system_prompt
    assert "reasoning_persona=librarian" in reader.system_prompt
