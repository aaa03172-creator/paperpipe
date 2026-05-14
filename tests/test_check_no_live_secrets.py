from pathlib import Path

from scripts.check_no_live_secrets import scan


def test_secret_scan_allows_empty_env_example(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=\nANTHROPIC_API_KEY=\n", encoding="utf-8")

    assert scan(tmp_path, extra_files=(".env.example",)) == []


def test_secret_scan_flags_live_local_env_assignment(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-live-provider-key-abcdef123456\n", encoding="utf-8")

    findings = scan(tmp_path, extra_files=(".env",))

    assert findings == [".env:1: live-looking secret assignment for OPENAI_API_KEY"]


def test_secret_scan_flags_provider_key_in_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("api_key: sk-ant-liveprovidersecret123456\n", encoding="utf-8")

    findings = scan(tmp_path, extra_files=("config.yaml",))

    assert findings == ["config.yaml:1: live-looking provider API key"]


def test_secret_scan_allows_env_references(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime.env"
    config_path.write_text("OPENAI_API_KEY=${OPENAI_API_KEY}\n", encoding="utf-8")

    assert scan(tmp_path, extra_files=("runtime.env",)) == []
