import sqlite3
from pathlib import Path
import sys
import types
import json

stub_llm_provider = types.ModuleType("src.llm_provider")
stub_llm_provider.get_llm_provider = lambda *args, **kwargs: None
stub_llm_provider.LLMProvider = object
_inserted_stub_llm_provider = "src.llm_provider" not in sys.modules
if _inserted_stub_llm_provider:
    sys.modules["src.llm_provider"] = stub_llm_provider

import scripts.backfill_analysis as backfill

if _inserted_stub_llm_provider:
    sys.modules.pop("src.llm_provider", None)


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


def test_backfill_dry_run_does_not_update_candidate_rows(tmp_path):
    db_path = tmp_path / "state.db"
    _init_db(db_path)

    result = backfill.run_backfill(limit=10, db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT summary, confidence, feedback_json FROM papers WHERE paper_id='p1'"
    ).fetchone()
    conn.close()

    assert result["dry_run"] is True
    assert result["candidate_count"] == 1
    assert result["would_require_llm_tagging"] == 1
    assert result["would_refresh_summary"] == 1
    assert row["summary"] == ""
    assert row["confidence"] is None
    assert row["feedback_json"] is None


def test_backfill_updates_candidate_rows(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    backup_path = tmp_path / "state.backup.db"
    _init_db(db_path)

    fake_config = type("Cfg", (), {"llm": object(), "entity_aliases": {}, "paths": object()})()

    monkeypatch.setattr(backfill, "load_config", lambda: fake_config)
    monkeypatch.setattr(backfill, "get_llm_provider", lambda llm, aliases: _FakeLLM())
    monkeypatch.setattr(backfill, "extract_text_from_pdf", lambda p, max_pages=3: "")

    result = backfill.run_backfill(limit=10, apply=True, db_path=db_path, backup_path=backup_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT summary, confidence, feedback_json FROM papers WHERE paper_id='p1'"
    ).fetchone()
    conn.close()

    assert result["dry_run"] is False
    assert result["updated_count"] == 1
    assert result["backup_path"] == str(backup_path)
    assert backup_path.exists()
    assert row["summary"] == "generated summary"
    assert abs(float(row["confidence"]) - 0.88) < 1e-9
    assert '"soft_tags": ["#Clinical"]' in row["feedback_json"]
    payload = json.loads(row["feedback_json"])
    assert payload["intake_override_log"]["producer"] == "backfill_analysis"
    assert payload["intake_override_log"]["processing_status"] == "APPROVED"
    assert payload["intake_override_log"]["llm_tagging_used"] is True


def test_backfill_adds_intake_override_log_without_reanalysis(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
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
            updated_at TEXT,
            slot TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, summary, status, pdf_path, confidence, feedback_json, updated_at, slot)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """,
        (
            "p2",
            "Title 2",
            "existing summary",
            "INDEXED",
            None,
            0.91,
            json.dumps(
                {
                    "hard_tags": {"species": "human"},
                    "soft_tags": ["#Clinical"],
                    "evidence_span": "e",
                    "confidence": 0.91,
                }
            ),
            "clinical",
        ),
    )
    conn.commit()
    conn.close()

    fake_config = type("Cfg", (), {"llm": object(), "entity_aliases": {}, "paths": object()})()

    class _UnavailableLLM:
        def is_available(self):
            return False

    monkeypatch.setattr(backfill, "load_config", lambda: fake_config)
    monkeypatch.setattr(backfill, "get_llm_provider", lambda llm, aliases: _UnavailableLLM())
    monkeypatch.setattr(backfill, "extract_text_from_pdf", lambda p, max_pages=3: "")

    backup_path = tmp_path / "state.backup.db"
    result = backfill.run_backfill(limit=10, apply=True, db_path=db_path, backup_path=backup_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT summary, confidence, feedback_json FROM papers WHERE paper_id='p2'"
    ).fetchone()
    conn.close()

    assert result["updated_count"] == 1
    assert result["backup_path"] == str(backup_path)
    assert backup_path.exists()
    assert row["summary"] == "existing summary"
    assert abs(float(row["confidence"]) - 0.91) < 1e-9
    payload = json.loads(row["feedback_json"])
    assert payload["soft_tags"] == ["#Clinical"]
    assert payload["intake_override_log"]["producer"] == "backfill_analysis"
    assert payload["intake_override_log"]["processing_status"] == "INDEXED"
    assert payload["intake_override_log"]["llm_tagging_used"] is False
    assert payload["intake_override_log"]["stored_slot"] == "clinical"
    assert payload["intake_override_log"]["issues_state"] == "clear"
