from pathlib import Path

from scripts import check_windows_personal_runtime_smoke as smoke_script


def test_default_windows_config_path_uses_appdata_root(tmp_path: Path):
    assert smoke_script.default_windows_config_path(tmp_path) == (
        tmp_path / "config" / "config.yaml"
    ).resolve()


def test_ensure_smoke_config_copies_template_once(tmp_path: Path):
    template = tmp_path / "config.example.yaml"
    template.write_text("paths:\n  obsidian_vault: /tmp\n", encoding="utf-8")
    config_path = tmp_path / "AppData" / "Roaming" / "Lattice" / "config" / "config.yaml"

    created = smoke_script.ensure_smoke_config(config_path, template)
    created_again = smoke_script.ensure_smoke_config(config_path, template)

    assert created is True
    assert created_again is False
    assert config_path.read_text(encoding="utf-8") == template.read_text(encoding="utf-8")


def test_build_runtime_env_enables_install_layout(tmp_path: Path):
    env = smoke_script.build_runtime_env(tmp_path / "config.yaml")

    assert env["PAPERPIPE_INSTALL_LAYOUT"] == "1"
    assert env["PAPERPIPE_CONFIG_PATH"] == str((tmp_path / "config.yaml"))


def test_build_cli_command_uses_windows_packaged_binary(tmp_path: Path):
    binary = tmp_path / "dist" / "lattice.exe"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("stub", encoding="utf-8")

    assert smoke_script.build_cli_command("packaged", root=tmp_path) == [str(binary.resolve())]
