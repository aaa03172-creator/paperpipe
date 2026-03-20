from src.services.runtime_paths import method_comparisons_root, paperpipe_home


def test_method_comparisons_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_METHOD_COMPARISONS_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert method_comparisons_root() == (tmp_path / "storage" / "method_comparisons").resolve()


def test_method_comparisons_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_method_comparisons"
    monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(custom_root))
    assert method_comparisons_root() == custom_root.resolve()
