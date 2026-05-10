from pathlib import Path

from scripts import build_personal_runtime_user_kits as kit_script


def test_write_windows_helper_scripts_creates_expected_commands(tmp_path: Path):
    kit_script._write_windows_helper_scripts(tmp_path)

    install_text = (tmp_path / "install_and_smoke_windows.ps1").read_text(encoding="utf-8")
    start_text = (tmp_path / "start_lattice_windows.ps1").read_text(encoding="utf-8")

    assert "py -3 -m pip install -r requirements.txt" in install_text
    assert "check_windows_personal_runtime_smoke.py --mode source" in install_text
    assert "$env:PAPERPIPE_INSTALL_LAYOUT = \"1\"" in start_text
    assert "py -3 -m src.cli start" in start_text


def test_feedback_template_mentions_install_and_start_commands():
    content = kit_script._feedback_template("Windows", ".\\install.ps1", ".\\start.ps1")

    assert ".\\install.ps1" in content
    assert ".\\start.ps1" in content
    assert "앱이 실행되었나요?" in content


def test_kit_product_guide_includes_current_shape():
    content = kit_script._kit_product_guide("Windows", "from-source alpha", "source snapshot")

    assert "from-source alpha" in content
    assert "source snapshot" in content
    assert "개인별로 분리된 personal runtime" in content
