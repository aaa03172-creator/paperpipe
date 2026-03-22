from src.services.runtime_paths import chart_packs_root, paperpipe_home


def test_chart_packs_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CHART_PACKS_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert chart_packs_root() == (tmp_path / "storage" / "chart_packs").resolve()


def test_chart_packs_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_chart_packs"
    monkeypatch.setenv("PAPERPIPE_CHART_PACKS_DIR", str(custom_root))

    assert chart_packs_root() == custom_root.resolve()
