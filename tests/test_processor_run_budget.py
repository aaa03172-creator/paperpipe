from unittest.mock import MagicMock

from src.processor import PaperProcessor, consume_budget


def _make_processor(monkeypatch):
    mock_config = MagicMock()
    mock_config.confidence_thresholds.high = 0.9
    mock_config.confidence_thresholds.low = 0.7
    mock_config.paths.upload_dir = None

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True

    monkeypatch.setattr("src.processor.load_config", lambda: mock_config)
    monkeypatch.setattr("src.processor.get_llm_provider", lambda *_args, **_kwargs: mock_provider)
    return PaperProcessor()


def test_consume_budget_counts_success_and_failure():
    assert consume_budget(5, success_count=2, failure_count=1) == 2
    assert consume_budget(2, success_count=0, failure_count=3) == 0


def test_run_consumes_budget_on_failures(monkeypatch):
    processor = _make_processor(monkeypatch)
    calls = {"count": 0}

    monkeypatch.setattr("src.processor.get_papers_by_status", lambda *_args, **_kwargs: [{"paper_id": "p1"}])

    def _mock_process_step(_papers, _handler):
        calls["count"] += 1
        return (0, 1)

    processor._process_step = _mock_process_step  # type: ignore[method-assign]
    processor.run(batch_size=2)

    assert calls["count"] == 2


def test_run_consumes_budget_on_mixed_results(monkeypatch):
    processor = _make_processor(monkeypatch)
    calls = {"count": 0}

    monkeypatch.setattr("src.processor.get_papers_by_status", lambda *_args, **_kwargs: [{"paper_id": "p1"}])

    def _mock_process_step(_papers, _handler):
        calls["count"] += 1
        return (1, 1)

    processor._process_step = _mock_process_step  # type: ignore[method-assign]
    processor.run(batch_size=2)

    assert calls["count"] == 1
