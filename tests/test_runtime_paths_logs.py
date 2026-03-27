from src.services.runtime_paths import logs_root, paperpipe_home


def test_logs_root_defaults_under_paperpipe_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_LOGS_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert logs_root() == (tmp_path / "logs").resolve()


def test_logs_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_logs"
    monkeypatch.setenv("PAPERPIPE_LOGS_DIR", str(custom_root))

    assert logs_root() == custom_root.resolve()
