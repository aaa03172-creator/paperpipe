from src.services.runtime_paths import cache_root, feedback_index_root, ocr_cache_root, paperpipe_home, rag_root


def test_cache_and_agent_roots_default_under_paperpipe_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CACHE_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_RAG_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_FEEDBACK_INDEX_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_OCR_CACHE_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert paperpipe_home() == tmp_path.resolve()
    assert cache_root() == (tmp_path / "cache").resolve()
    assert rag_root() == (tmp_path / "storage" / "rag").resolve()
    assert feedback_index_root() == (tmp_path / "storage" / "feedback_index").resolve()
    assert ocr_cache_root() == (tmp_path / "cache" / "ocr").resolve()


def test_cache_and_agent_roots_respect_env_override(tmp_path, monkeypatch):
    custom_cache = tmp_path / "custom_cache"
    custom_rag = tmp_path / "custom_rag"
    custom_feedback = tmp_path / "custom_feedback"
    custom_ocr = tmp_path / "custom_ocr"

    monkeypatch.setenv("PAPERPIPE_CACHE_DIR", str(custom_cache))
    monkeypatch.setenv("PAPERPIPE_RAG_DIR", str(custom_rag))
    monkeypatch.setenv("PAPERPIPE_FEEDBACK_INDEX_DIR", str(custom_feedback))
    monkeypatch.setenv("PAPERPIPE_OCR_CACHE_DIR", str(custom_ocr))

    assert cache_root() == custom_cache.resolve()
    assert rag_root() == custom_rag.resolve()
    assert feedback_index_root() == custom_feedback.resolve()
    assert ocr_cache_root() == custom_ocr.resolve()
