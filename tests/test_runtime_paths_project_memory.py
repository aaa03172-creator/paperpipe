from src.services.runtime_paths import paperpipe_home, project_memory_root


def test_project_memory_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_PROJECT_MEMORY_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert project_memory_root() == (tmp_path / "storage" / "project_memory").resolve()


def test_project_memory_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_project_memory"
    monkeypatch.setenv("PAPERPIPE_PROJECT_MEMORY_DIR", str(custom_root))

    assert project_memory_root() == custom_root.resolve()
