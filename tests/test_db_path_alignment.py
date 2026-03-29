from pathlib import Path

import src.db as legacy_db
import src.db_utils as db_utils


def test_db_paths_are_aligned():
    assert Path(legacy_db.DB_PATH) == db_utils.DB_PATH


def test_legacy_db_honors_paperpipe_db_path_override_when_default_path_is_imported(tmp_path, monkeypatch):
    original_legacy_path = legacy_db.DB_PATH
    original_utils_path = db_utils.DB_PATH
    override_path = tmp_path / "override" / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(override_path))
    try:
        legacy_db.init_db()
        assert override_path.exists()
        assert db_utils.get_db_path() == override_path.resolve()
    finally:
        legacy_db.DB_PATH = original_legacy_path
        db_utils.DB_PATH = original_utils_path
