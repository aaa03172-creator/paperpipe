from src.services.runtime_paths import paper_syntheses_root, paperpipe_home


def test_paper_syntheses_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_PAPER_SYNTHESES_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert paper_syntheses_root() == (tmp_path / "storage" / "paper_syntheses").resolve()


def test_paper_syntheses_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_paper_syntheses"
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(custom_root))

    assert paper_syntheses_root() == custom_root.resolve()
