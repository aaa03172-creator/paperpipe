from pathlib import PosixPath

import src.services.runtime_paths as runtime_paths


def test_user_config_base_dir_respects_windows_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(runtime_paths, "Path", PosixPath)
    monkeypatch.setattr(runtime_paths.os, "name", "nt")
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")

    assert runtime_paths.user_config_base_dir() == (
        tmp_path / "AppData" / "Roaming" / "Lattice"
    ).resolve()


def test_install_layout_roots_follow_windows_appdata(tmp_path, monkeypatch):
    roaming = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(runtime_paths, "Path", PosixPath)
    monkeypatch.delenv("PAPERPIPE_HOME", raising=False)
    monkeypatch.delenv("PAPERPIPE_STORAGE_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_LOGS_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_CACHE_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_CONFIG_PATH", raising=False)
    monkeypatch.setenv("PAPERPIPE_INSTALL_LAYOUT", "1")
    monkeypatch.setattr(runtime_paths.os, "name", "nt")
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")

    app_root = roaming / "Lattice"

    assert runtime_paths.config_root() == (app_root / "config").resolve()
    assert runtime_paths.config_file_path() == (app_root / "config" / "config.yaml").resolve()
    assert runtime_paths.storage_root() == (app_root / "storage").resolve()
    assert runtime_paths.logs_root() == (app_root / "logs").resolve()
    assert runtime_paths.cache_root() == (app_root / "cache").resolve()


def test_user_config_base_dir_falls_back_to_localappdata(tmp_path, monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.setattr(runtime_paths, "Path", PosixPath)
    monkeypatch.setattr(runtime_paths.os, "name", "nt")
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")

    assert runtime_paths.user_config_base_dir() == (
        tmp_path / "AppData" / "Local" / "Lattice"
    ).resolve()
