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
        assert row[0] == "Inbox/PaperPipe/Paper Title.md"
        assert (vault / row[0]).exists()
    finally:
        db_utils.DB_PATH = original_db_path


def test_run_export_ignores_escaping_obsidian_path(tmp_path, monkeypatch):
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
            ("paper_escape_path", "Escaping Title", "Summary", "APPROVED", 0.95, "{}", None, "../outside.md"),
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
            ("paper_escape_path",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Inbox/PaperPipe/Escaping Title.md"
        assert not (tmp_path / "outside.md").exists()
        assert (vault / row[0]).exists()
    finally:
        db_utils.DB_PATH = original_db_path


def test_run_export_writes_related_papers_section(tmp_path, monkeypatch):
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
            (
                "paper_related_a",
                "Related A",
                "Summary A",
                "APPROVED",
                0.9,
                '{"soft_tags":["#Memory","#MCI"]}',
                None,
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, summary, status, confidence, feedback_json, pdf_path, obsidian_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "paper_related_b",
                "Related B",
                "Summary B",
                "APPROVED",
                0.91,
                '{"soft_tags":["#Memory","#Trial"]}',
                None,
                None,
            ),
        )
        conn.commit()
        conn.close()

        vault = tmp_path / "vault"
        config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault))
        monkeypatch.setattr(exporter, "load_config", lambda: config)

        exporter.run_export(overwrite=True)

        note_a = vault / "Inbox" / "PaperPipe" / "Related A.md"
        content = note_a.read_text(encoding="utf-8")

        assert "## 🔗 Related Papers" in content
        assert "[[Inbox/PaperPipe/Related B|Related B]]" in content
        assert "shared tags: Memory" in content
    finally:
        db_utils.DB_PATH = original_db_path


def test_run_export_avoids_title_collision_by_falling_back_to_clean_paper_id(tmp_path, monkeypatch):
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
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, summary, status, confidence, feedback_json, pdf_path, obsidian_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                ("zotero:firstCollisionPaper2026", "Collision Title", "Summary 1", "APPROVED", 0.95, "{}", None, None),
                ("zotero:secondCollisionPaper2026", "Collision Title", "Summary 2", "APPROVED", 0.94, "{}", None, None),
            ],
        )
        conn.commit()
        conn.close()

        vault = tmp_path / "vault"
        config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault))
        monkeypatch.setattr(exporter, "load_config", lambda: config)

        exporter.run_export(overwrite=True)

        conn = db_utils.get_db_connection()
        rows = conn.execute(
            "SELECT paper_id, obsidian_path FROM papers ORDER BY paper_id",
        ).fetchall()
        conn.close()

        path_map = {row[0]: row[1] for row in rows}
        assert path_map["zotero:firstCollisionPaper2026"] == "Inbox/PaperPipe/Collision Title.md"
        assert path_map["zotero:secondCollisionPaper2026"] == "Inbox/PaperPipe/secondCollisionPaper2026.md"
        assert (vault / path_map["zotero:firstCollisionPaper2026"]).exists()
        assert (vault / path_map["zotero:secondCollisionPaper2026"]).exists()
    finally:
        db_utils.DB_PATH = original_db_path
