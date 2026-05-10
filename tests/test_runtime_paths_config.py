import src.services.runtime_paths as runtime_paths


def test_config_root_defaults_under_paperpipe_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_CONFIG_PATH", raising=False)
    monkeypatch.delenv("PAPERPIPE_INSTALL_LAYOUT", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert runtime_paths.config_root() == (tmp_path / "config").resolve()


def test_config_file_prefers_config_dir_under_paperpipe_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CONFIG_PATH", raising=False)
    monkeypatch.delenv("PAPERPIPE_INSTALL_LAYOUT", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("system: {}\n", encoding="utf-8")

    assert runtime_paths.config_file_path() == config_file.resolve()


def test_config_file_keeps_legacy_home_root_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CONFIG_PATH", raising=False)
    monkeypatch.delenv("PAPERPIPE_INSTALL_LAYOUT", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))
    legacy_config = tmp_path / "config.yaml"
    legacy_config.write_text("system: {}\n", encoding="utf-8")

    assert runtime_paths.config_file_path() == legacy_config.resolve()


def test_config_root_respects_install_layout_on_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_HOME", raising=False)
    monkeypatch.delenv("PAPERPIPE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_CONFIG_PATH", raising=False)
    monkeypatch.setenv("PAPERPIPE_INSTALL_LAYOUT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")

    assert runtime_paths.config_root() == (
        tmp_path / "Library" / "Application Support" / "Lattice" / "config"
    ).resolve()
