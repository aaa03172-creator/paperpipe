import sys
import types
from unittest.mock import MagicMock, patch

stub_llm_provider = types.ModuleType("src.llm_provider")
stub_llm_provider.get_llm_provider = lambda *args, **kwargs: None
stub_llm_provider.LLMProvider = object
sys.modules.setdefault("src.llm_provider", stub_llm_provider)

from src.processor import PaperProcessor, STATE_GATED


@patch("src.processor.extract_text_from_pdf", return_value="FULL_TEXT_SAMPLE")
@patch("src.processor.get_llm_provider")
@patch("src.processor.load_config")
@patch("src.processor.update_paper_status")
def test_step_analyze_passes_full_text_to_tagger(
    mock_update_status, mock_load_config, mock_get_llm, _mock_extract_text, tmp_path
):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None
    mock_config.entity_aliases = {}
    mock_load_config.return_value = mock_config

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_provider.tag_paper.return_value = {
        "hard_tags": {"species": "human"},
        "soft_tags": ["#Clinical"],
        "evidence_span": "evidence",
        "confidence": 0.91,
    }
    mock_get_llm.return_value = mock_provider

    processor = PaperProcessor()
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    processor._step_analyze(
        {
            "paper_id": "p1",
            "title": "Paper Title",
            "summary": "Paper Summary",
            "pdf_path": str(pdf_path),
        }
    )

    paper_arg = mock_provider.tag_paper.call_args[0][0]
    assert paper_arg["full_text"] == "FULL_TEXT_SAMPLE"
    assert paper_arg["title"] == "Paper Title"
    assert paper_arg["summary"] == "Paper Summary"
    assert mock_update_status.call_args[0][1] == STATE_GATED
