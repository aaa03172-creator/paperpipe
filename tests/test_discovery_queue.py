from __future__ import annotations

import sqlite3
from pathlib import Path

import src.db_utils as db_utils
from src.discovery_queue import run_discovery_queue, upsert_related_queue_section


class _FakeFetcher:
    def fetch_related_works(self, seed: str, limit: int = 10):  # noqa: ARG002
        return [
            {
                "openalex_id": "https://openalex.org/W111",
                "doi": "10.1000/recommended",
                "title": "Recommended Work",
                "year": 2024,
                "venue": "Nature Medicine",
                "cited_by_count": 150,
                "is_oa": True,
                "relation": "referenced",
            },
            {
                "openalex_id": "https://openalex.org/W222",
                "doi": "10.1000/pending",
                "title": "Pending Work",
                "year": 2010,
                "venue": "Legacy Journal",
                "cited_by_count": 1,
                "is_oa": False,
                "relation": "cited_by",
            },
        ][:limit]


def _init_papers_table(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            year INTEGER,
            venue TEXT,
            source TEXT,
            slot TEXT,
            status TEXT NOT NULL DEFAULT 'NEW',
            confidence REAL,
            gate_reason TEXT,
            evidence_snippet TEXT,
            obsidian_path TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, doi, title, status, obsidian_path)
        VALUES ('seed-paper', '10.1000/seed', 'Seed Paper', 'INDEXED', 'Inbox/PaperPipe/seed-paper.md')
        """
    )
    conn.commit()
    conn.close()


def test_run_discovery_queue_persists_candidates_and_upserts_note(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    _init_papers_table(db_path)

    vault = tmp_path / "vault"
    note = vault / "Inbox/PaperPipe/seed-paper.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("# Seed Paper\n\n## Existing\n", encoding="utf-8")

    class _Paths:
        obsidian_vault = vault

    class _System:
        unpaywall_email = "test@example.com"

    class _Config:
        paths = _Paths()
        system = _System()

    old_db = db_utils.DB_PATH
    db_utils.DB_PATH = db_path
    monkeypatch.setattr("src.discovery_queue.load_config", lambda: _Config())
    try:
        result = run_discovery_queue(
            seed="seed-paper",
            limit=10,
            write_obsidian=True,
            fetcher=_FakeFetcher(),
        )

        assert result["saved"] == 2
        assert result["recommended"] == 1
        assert result["pending_queue"] == 1
        assert result["note_path"] == str(note)

        # Re-run to verify DB upsert + note upsert idempotency.
        result2 = run_discovery_queue(
            seed="seed-paper",
            limit=10,
            write_obsidian=True,
            fetcher=_FakeFetcher(),
        )
        assert result2["saved"] == 2

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT paper_id, status FROM papers WHERE paper_id LIKE 'doi:%' ORDER BY paper_id"
        ).fetchall()
        conn.close()

        assert len(rows) == 2
        statuses = {row[1] for row in rows}
        assert statuses == {"RECOMMENDED", "PENDING_QUEUE"}

        body = note.read_text(encoding="utf-8")
        assert body.count("## Related Works (Queue)") == 1
        assert "[RECOMMENDED] Recommended Work" in body
        assert "[PENDING_QUEUE] Pending Work" in body
    finally:
        db_utils.DB_PATH = old_db


def test_upsert_related_queue_section_replaces_existing_block():
    original = (
        "# Note\n\n"
        "## Related Works (Queue)\n"
        "- old item\n\n"
        "## Next\n"
        "- stable\n"
    )
    new_section = "## Related Works (Queue)\n- new item"
    updated = upsert_related_queue_section(original, new_section)

    assert updated.count("## Related Works (Queue)") == 1
    assert "- new item" in updated
    assert "- old item" not in updated
    assert "## Next" in updated
