from pathlib import Path

import src.db as legacy_db
import src.db_utils as db_utils


def test_db_paths_are_aligned():
    assert Path(legacy_db.DB_PATH) == db_utils.DB_PATH
