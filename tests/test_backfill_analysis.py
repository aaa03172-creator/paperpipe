import sqlite3
from pathlib import Path
import sys
import types

stub_llm_provider = types.ModuleType("src.llm_provider")
stub_llm_provider.get_llm_provider = lambda *args, **kwargs: None
stub_llm_provider.LLMProvider = object
sys.modules.setdefault("src.llm_provider", stub_llm_provider)

import scripts.backfill_analysis as backfill


def _init_db(path: Path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            status TEXT,
            pdf_path TEXT,
            confidence REAL,
            feedback_json TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, summary, status, pdf_path, confidence, feedback_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        ("p1", "Title 1", "", "APPROVED", None, None, None),
    )
    conn.commit()
    conn.close()


class _FakeLLM:
    def is_available(self):
        return True

    def tag_paper(self, paper_obj):
        return {
            "hard_tags": {"species": "human"},
            "soft_tags": ["#Clinical"],
            "evidence_span": "e",
            "confidence": 0.88,
        }

    def generate_one_liner(self, paper_obj):
        return "generated summary"


def _conn_with_row_factory(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def test_backfill_updates_candidate_rows(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    _init_db(db_path)

    fake_config = type("Cfg", (), {"llm": object(), "entity_aliases": {}, "paths": object()})()

    monkeypatch.setattr(backfill, "load_config", lambda: fake_config)
    monkeypatch.setattr(backfill, "get_llm_provider", lambda llm, aliases: _FakeLLM())
    monkeypatch.setattr(backfill, "get_db_connection", lambda: _conn_with_row_factory(db_path))
    monkeypatch.setattr(backfill, "extract_text_from_pdf", lambda p, max_pages=3: "")

    backfill.run_backfill(limit=10)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT summary, confidence, feedback_json FROM papers WHERE paper_id='p1'"
    ).fetchone()
    conn.close()

    assert row["summary"] == "generated summary"
    assert abs(float(row["confidence"]) - 0.88) < 1e-9
    assert '"soft_tags": ["#Clinical"]' in row["feedback_json"]
