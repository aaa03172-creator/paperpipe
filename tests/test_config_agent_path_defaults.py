from src.config import AgentConfig


def test_agent_config_defaults_follow_runtime_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    config = AgentConfig()

    assert config.rag_index_path == str((tmp_path / "storage" / "rag").resolve())
    assert config.feedback_index_path == str((tmp_path / "storage" / "feedback_index").resolve())
    assert config.logging.trace_file == str((tmp_path / "logs" / "agent_trace.jsonl").resolve())
