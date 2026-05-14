from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3


def test_e2e_fake_worker_module_imports_without_optional_stats_agent_dependencies() -> None:
    module_path = Path("frontend/scripts/run_fake_worker_for_e2e.py").resolve()
    spec = importlib.util.spec_from_file_location("e2e_fake_worker_import_smoke", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.fake_run_deepread_job)


def test_e2e_fake_worker_detects_missing_runtime_db_jobs_table(monkeypatch, tmp_path) -> None:
    module_path = Path("frontend/scripts/run_fake_worker_for_e2e.py").resolve()
    spec = importlib.util.spec_from_file_location("e2e_fake_worker_import_smoke_missing_jobs", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE other_table (id TEXT PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()

    assert module._runtime_db_has_jobs_table() is False


def test_e2e_fake_worker_detects_runtime_db_jobs_table(monkeypatch, tmp_path) -> None:
    module_path = Path("frontend/scripts/run_fake_worker_for_e2e.py").resolve()
    spec = importlib.util.spec_from_file_location("e2e_fake_worker_import_smoke_with_jobs", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()

    assert module._runtime_db_has_jobs_table() is True
