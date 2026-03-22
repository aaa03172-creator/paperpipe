from src.services.runtime_paths import paperpipe_home, protocol_cards_root


def test_protocol_cards_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_PROTOCOL_CARDS_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert protocol_cards_root() == (tmp_path / "storage" / "protocol_cards").resolve()


def test_protocol_cards_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_protocol_cards"
    monkeypatch.setenv("PAPERPIPE_PROTOCOL_CARDS_DIR", str(custom_root))

    assert protocol_cards_root() == custom_root.resolve()
