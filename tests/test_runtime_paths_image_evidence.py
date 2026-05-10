from src.services.runtime_paths import image_evidence_root, paperpipe_home


def test_image_evidence_root_defaults_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert image_evidence_root() == (tmp_path / "storage" / "image_evidence").resolve()


def test_image_evidence_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_image_evidence"
    monkeypatch.setenv("PAPERPIPE_IMAGE_EVIDENCE_DIR", str(custom_root))

    assert image_evidence_root() == custom_root.resolve()
