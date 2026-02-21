from types import SimpleNamespace

import src.db_utils as db_utils
from src import exporter


def test_run_export_persists_obsidian_path(tmp_path, monkeypatch):
    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                status TEXT,
                confidence REAL,
                feedback_json TEXT,
                pdf_path TEXT,
                obsidian_path TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, summary, status, confidence, feedback_json, pdf_path, obsidian_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("paper_obs_path", "Paper Title", "Summary", "APPROVED", 0.95, "{}", None, None),
        )
        conn.commit()
        conn.close()

        vault = tmp_path / "vault"
        config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault))
        monkeypatch.setattr(exporter, "load_config", lambda: config)

        exporter.run_export(overwrite=True)

        conn = db_utils.get_db_connection()
        row = conn.execute(
            "SELECT obsidian_path FROM papers WHERE paper_id = ?",
            ("paper_obs_path",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Inbox/PaperPipe/paper_obs_path.md"
        assert (vault / row[0]).exists()
    finally:
        db_utils.DB_PATH = original_db_path
