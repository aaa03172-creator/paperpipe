import json
import pytest
import os
import shutil
from pathlib import Path
from src.schemas.agent_artifacts import FeedbackCase
from src.agents.feedback_retriever import FeedbackRetriever
from src.config import AgentConfig, AppConfig

# Mock adapter for predictable embeddings
class MockAdapter:
    def embed(self, text: str, model: str):
        # Dummy matching 
        if "correct" in text.lower() or "efficacy" in text.lower():
            return [0.1, 0.9, 0.1]
        elif "error" in text.lower() or "safety" in text.lower():
            return [0.9, 0.1, 0.1]
        return [0.5, 0.5, 0.5]


@pytest.fixture
def mock_config(monkeypatch):
    class MockConfig:
        def __init__(self):
            # temp path for tests
            self.agents = AgentConfig(feedback_index_path="tests/test_data/feedback_index")
    
    config = MockConfig()
    monkeypatch.setattr("src.agents.feedback_retriever.load_config", lambda: config)
    return config

@pytest.fixture
def retriever(mock_config, monkeypatch):
    # Ensure clean slate
    test_db = Path("tests/test_data/feedback_index")
    if test_db.exists():
        shutil.rmtree(test_db)
        
    r = FeedbackRetriever(collection_name="test_feedback")
    # Replace real adapter with mock
    r.adapter = MockAdapter()
    
    yield r
    
    # Teardown
    if test_db.exists():
        shutil.rmtree(test_db)


def test_add_and_retrieve_feedback(retriever):
    # 1. Add some feedback cases
    cases = [
        FeedbackCase(
            paper_id="paper_1", run_id="run_1", accepted=True,
            user_correction="The efficacy measure was incorrectly extracted. It should focus on the primary endpoint."
        ),
        FeedbackCase(
            paper_id="paper_2", run_id="run_2", accepted=True,
            user_correction="Safety profile shows severe adverse events, fix the error."
        ),
        FeedbackCase(
            paper_id="paper_3", run_id="run_3", accepted=False, # Should be ignored in query
            user_correction="This correction was rejected but talks about efficacy."
        )
    ]
    
    for c in cases:
        success = retriever.add_feedback(c)
        assert success is True

    # 2. Query for efficacy (should match paper_1, ignore paper_3 because accepted=False)
    results = retriever.query_relevant_feedback("efficacy endpoint", limit=2)
    
    assert len(results) == 1
    assert results[0]["paper_id"] == "paper_1"
    assert "efficacy" in results[0]["preview"].lower()

    # 3. Query for safety/error (should match paper_2)
    results = retriever.query_relevant_feedback("safety error handling", limit=2)
    assert len(results) == 1
    assert results[0]["paper_id"] == "paper_2"


def test_add_feedback_sanitizes_secret_like_text_before_index(retriever):
    case = FeedbackCase(
        paper_id="paper_secret_feedback",
        run_id="run_secret_feedback",
        accepted=True,
        user_correction=(
            "Correct extraction, but never reuse Authorization: Bearer index-feedback-token-123 "
            "or sk-proj-index-feedback-secret-abcdef."
        ),
    )

    assert retriever.add_feedback(case) is True

    rows = [line for line in retriever._index_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    saved = json.loads(rows[-1])
    assert "index-feedback-token-123" not in saved["document"]
    assert "sk-proj-index-feedback-secret-abcdef" not in saved["document"]
    assert saved["document"] == "Correct extraction, but never reuse Authorization: <redacted> or <redacted>."
    assert saved["metadata"]["preview"] == saved["document"]
