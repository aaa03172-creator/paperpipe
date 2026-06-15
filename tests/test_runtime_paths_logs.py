import src.services.runtime_paths as runtime_paths


def test_logs_root_defaults_under_paperpipe_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_LOGS_DIR", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert runtime_paths.paperpipe_home() == tmp_path.resolve()
    assert runtime_paths.logs_root() == (tmp_path / "logs").resolve()


def test_logs_root_respects_env_override(tmp_path, monkeypatch):
    custom_root = tmp_path / "custom_logs"
    monkeypatch.setenv("PAPERPIPE_LOGS_DIR", str(custom_root))

    assert runtime_paths.logs_root() == custom_root.resolve()


def test_claim_evidence_correction_log_path_defaults_under_storage(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_CLAIM_EVIDENCE_CORRECTION_LOG_PATH", raising=False)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path))

    assert runtime_paths.claim_evidence_correction_log_path() == (
        tmp_path / "storage" / "claim_evidence_corrections.jsonl"
    ).resolve()


def test_claim_evidence_correction_log_path_respects_env_override(tmp_path, monkeypatch):
    custom_path = tmp_path / "custom_corrections.jsonl"
    monkeypatch.setenv("PAPERPIPE_CLAIM_EVIDENCE_CORRECTION_LOG_PATH", str(custom_path))

    assert runtime_paths.claim_evidence_correction_log_path() == custom_path.resolve()


def test_logs_root_respects_install_layout_on_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERPIPE_LOGS_DIR", raising=False)
    monkeypatch.delenv("PAPERPIPE_HOME", raising=False)
    monkeypatch.setenv("PAPERPIPE_INSTALL_LAYOUT", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")

    assert runtime_paths.logs_root() == (
        tmp_path / "Library" / "Application Support" / "Lattice" / "logs"
    ).resolve()
