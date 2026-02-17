import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure `src` package is importable in direct pytest runs.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep this test independent from optional runtime deps (e.g., numpy/openai).
stub_llm_provider = types.ModuleType("src.llm_provider")
stub_llm_provider.get_llm_provider = lambda *args, **kwargs: None
stub_llm_provider.LLMProvider = object
sys.modules.setdefault("src.llm_provider", stub_llm_provider)

from src.processor import (
    PaperProcessor,
    STATE_APPROVED,
    STATE_FAILED,
    STATE_PENDING,
    STATE_QUARANTINED,
)


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_maps_decisions(mock_update_status, mock_load_config, mock_get_llm):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_get_llm.return_value = mock_provider

    processor = PaperProcessor()

    processor._step_gate(
        {
            "paper_id": "p1",
            "confidence": 0.95,
            "feedback_json": '{"confidence": 0.95, "soft_tags": ["#a"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_APPROVED

    processor._step_gate(
        {
            "paper_id": "p2",
            "confidence": 0.75,
            "feedback_json": '{"confidence": 0.75, "soft_tags": ["#a"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_PENDING

    processor._step_gate(
        {
            "paper_id": "p3",
            "confidence": 0.55,
            "feedback_json": '{"confidence": 0.55, "soft_tags": ["#a"], "hard_tags": {"n": 10}, "evidence_span": "e"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_QUARANTINED


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_marks_failed_when_feedback_json_broken(
    mock_update_status, mock_load_config, mock_get_llm
):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_get_llm.return_value = mock_provider

    processor = PaperProcessor()
    processor._step_gate({"paper_id": "broken", "confidence": 0.95, "feedback_json": "{bad json"})
    assert mock_update_status.call_args[0][1] == STATE_FAILED


@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_gate_marks_failed_when_schema_invalid(
    mock_update_status, mock_load_config, mock_get_llm
):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_load_config.return_value = mock_config

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_get_llm.return_value = mock_provider

    processor = PaperProcessor()
    processor._step_gate(
        {
            "paper_id": "schema_bad",
            "confidence": 0.95,
            "feedback_json": '{"confidence": 0.95, "soft_tags": ["#a"], "hard_tags": "invalid_type"}',
        }
    )
    assert mock_update_status.call_args[0][1] == STATE_FAILED
