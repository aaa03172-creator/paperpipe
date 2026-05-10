import src.services.runtime_paths as runtime_paths


def test_cache_and_agent_roots_default_under_paperpipe_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CACHE_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_RAG_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_FEEDBACK_INDEX_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_OCR_CACHE_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert runtime_paths.paperpipe_home() == tmp_path.resolve()
    assert runtime_paths.cache_root() == (tmp_path / "cache").resolve()
    assert runtime_paths.rag_root() == (tmp_path / "storage" / "rag").resolve()
    assert runtime_paths.feedback_index_root() == (tmp_path / "storage" / "feedback_index").resolve()
    assert runtime_paths.ocr_cache_root() == (tmp_path / "cache" / "ocr").resolve()


def test_cache_and_agent_roots_respect_env_override(tmp_path, monkeypatch):
    custom_cache = tmp_path / "custom_cache"
    custom_rag = tmp_path / "custom_rag"
    custom_feedback = tmp_path / "custom_feedback"
    custom_ocr = tmp_path / "custom_ocr"

    monkeypatch.setenv("PAPERPIPE_CACHE_DIR", str(custom_cache))
    monkeypatch.setenv("PAPERPIPE_RAG_DIR", str(custom_rag))
    monkeypatch.setenv("PAPERPIPE_FEEDBACK_INDEX_DIR", str(custom_feedback))
    monkeypatch.setenv("PAPERPIPE_OCR_CACHE_DIR", str(custom_ocr))

    assert runtime_paths.cache_root() == custom_cache.resolve()
    assert runtime_paths.rag_root() == custom_rag.resolve()
    assert runtime_paths.feedback_index_root() == custom_feedback.resolve()
    assert runtime_paths.ocr_cache_root() == custom_ocr.resolve()


def test_cache_and_agent_roots_follow_install_layout_on_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_HOME", raising=False)
    monkeypatch.delenv("PAPERPIPE_CACHE_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_RAG_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_FEEDBACK_INDEX_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_OCR_CACHE_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_INSTALL_LAYOUT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")

    install_root = tmp_path / "Library" / "Application Support" / "Lattice"
    assert runtime_paths.cache_root() == (install_root / "cache").resolve()
    assert runtime_paths.rag_root() == (install_root / "storage" / "rag").resolve()
    assert runtime_paths.feedback_index_root() == (install_root / "storage" / "feedback_index").resolve()
    assert runtime_paths.ocr_cache_root() == (install_root / "cache" / "ocr").resolve()
