from src.services.runtime_paths import meeting_packs_root, paperpipe_home


def test_meeting_packs_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_MEETING_PACKS_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert meeting_packs_root() == (tmp_path / "storage" / "meeting_packs").resolve()


def test_meeting_packs_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_meeting_packs"
    monkeypatch.setenv("PAPERPIPE_MEETING_PACKS_DIR", str(custom_root))
    assert meeting_packs_root() == custom_root.resolve()
