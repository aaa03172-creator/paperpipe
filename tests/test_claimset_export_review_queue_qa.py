import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import qa_report
from src import db_utils
from src.core.paper_identity import make_paper_key
from src.exporter import (
    _auto_skip_test_fixture_followups,
    _is_test_fixture_paper,
    export_paper_to_markdown,
    enqueue_review_followups,
    resolve_claimset_claims,
    resolve_review_followups,
)


def _paper_with_claimset() -> dict:
    return {
        "paper_id": "claimset_001",
        "title": "ClaimSet Paper",
        "summary": "Summary",
        "status": "APPROVED",
        "confidence": 0.92,
        "zotero_key": "ABCD1234",
        "feedback_json": (
            '{"doc_id":"doi:10.1000/x","claims":[{"claim_id":"CLM-001",'
            '"statement":"Drug improves memory.",'
            '"evidence_spans":[{"page":2,"quote":"memory score improved"}],'
            '"limitations":["small N"],"confidence":0.88}]}'
        ),
    }


def _create_review_queue_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT,
            owner TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolution TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_review_queue_open_unique
        ON review_queue (paper_id, decision)
        WHERE resolved_at IS NULL
        """
    )


def test_exporter_renders_claimset_section(tmp_path: Path):
    paper = _paper_with_claimset()

    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    target = tmp_path / "Inbox" / "PaperPipe" / "claimset_001.md"
    content = target.read_text(encoding="utf-8")

    assert "## Critical Review (ClaimSet)" in content
    assert "- Claim: Drug improves memory." in content
    assert 'quote="memory score improved"' in content
    assert "page_num=2" in content
    assert "link=zotero://open-pdf/library/items/ABCD1234?page=3" in content
    assert "- Limitations: small N" in content
    assert "- Confidence: 0.88" in content


def test_exporter_invalid_json_falls_back_to_unavailable(tmp_path: Path):
    paper = {
        "paper_id": "bad_json_001",
        "title": "Broken",
        "summary": "Summary",
        "status": "APPROVED",
        "confidence": 0.4,
        "feedback_json": "{bad json",
    }

    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    target = tmp_path / "Inbox" / "PaperPipe" / "bad_json_001.md"
    content = target.read_text(encoding="utf-8")
    assert "## Critical Review (ClaimSet)" in content
    assert "ClaimSet: unavailable" in content


def test_review_queue_insertion_is_idempotent():
    conn = sqlite3.connect(":memory:")
    _create_review_queue_table(conn)

    paper = {"paper_id": "p1"}
    feedback = {"claims": [{"statement": "c1", "evidence_spans": [{"quote": "x"}]}]}
    claims = feedback["claims"]

    inserted_first = enqueue_review_followups(conn, paper, feedback, claims)
    conn.commit()
    inserted_second = enqueue_review_followups(conn, paper, feedback, claims)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM review_queue WHERE paper_id = 'p1' AND decision = 'NEEDS_EVIDENCE_LINK'").fetchone()[0]

    assert "NEEDS_EVIDENCE_LINK" in inserted_first
    assert inserted_second == []
    assert count == 1


def test_review_queue_unique_open_index_blocks_duplicate_insert():
    conn = sqlite3.connect(":memory:")
    _create_review_queue_table(conn)
    conn.execute(
        "INSERT INTO review_queue (paper_id, decision, reason) VALUES (?, ?, ?)",
        ("p_dup", "NEEDS_READER", "first"),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO review_queue (paper_id, decision, reason) VALUES (?, ?, ?)",
            ("p_dup", "NEEDS_READER", "duplicate"),
        )

def test_claimset_fallback_from_artifact_avoids_needs_reader(tmp_path: Path, monkeypatch):
    artifacts_root = tmp_path / "artifacts"
    claimset_file = artifacts_root / "p_art" / "run_001" / "claimset.json"
    claimset_file.parent.mkdir(parents=True, exist_ok=True)
    claimset_file.write_text(
        '{"doc_id":"d","claims":[{"claim_id":"c1","statement":"s","evidence_spans":[{"page":1,"quote":"q"}],"limitations":[],"confidence":0.7}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))

    paper = {"paper_id": "p_art"}
    feedback = {"soft_tags": ["#X"]}  # no claims in feedback_json
    claims = resolve_claimset_claims(paper, feedback)

    assert claims is not None
    assert len(claims) == 1

    conn = sqlite3.connect(":memory:")
    _create_review_queue_table(conn)
    inserted = enqueue_review_followups(conn, paper, feedback, claims)
    conn.commit()

    count_reader = conn.execute(
        "SELECT COUNT(*) FROM review_queue WHERE paper_id='p_art' AND decision='NEEDS_READER'"
    ).fetchone()[0]
    assert count_reader == 0
    assert "NEEDS_READER" not in inserted


def test_claimset_fallback_accepts_resolved_contract_artifact(tmp_path: Path, monkeypatch):
    artifacts_root = tmp_path / "artifacts"
    claimset_file = artifacts_root / "p_resolved" / "run_001" / "claimset.resolved.json"
    claimset_file.parent.mkdir(parents=True, exist_ok=True)
    claimset_file.write_text(
        '{"paper_id":"p_resolved","run_id":"run_001","stage":"resolved","schema_version":"1.0",'
        '"claims":[{"claim_id":"c1","claim_fingerprint":"abc","text":"s","type":"efficacy",'
        '"evidence":[{"chunk_id":"p01_c01","quote":"q","page":1,"grounded":true,"resolution":"OK"}]}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))

    paper = {"paper_id": "p_resolved"}
    feedback = {"soft_tags": ["#X"]}  # no claims in feedback_json
    claims = resolve_claimset_claims(paper, feedback)

    assert claims is not None
    assert len(claims) == 1
    assert claims[0]["statement"] == "s"
    assert claims[0]["evidence_spans"][0]["chunk_id"] == "p01_c01"

def test_resolve_review_followups_clears_stale_needs_reader():
    conn = sqlite3.connect(":memory:")
    _create_review_queue_table(conn)
    conn.execute(
        "INSERT INTO review_queue (paper_id, decision, reason) VALUES (?, ?, ?)",
        ("p1", "NEEDS_READER", "missing claimset"),
    )
    conn.commit()

    paper = {"paper_id": "p1"}
    feedback = {"claims": [{"statement": "x", "evidence_spans": [{"page": 1, "quote": "q"}]}]}
    claims = feedback["claims"]
    resolved = resolve_review_followups(conn, paper, feedback, claims)
    conn.commit()

    row = conn.execute(
        "SELECT resolved_at, resolution FROM review_queue WHERE paper_id='p1' AND decision='NEEDS_READER'"
    ).fetchone()
    assert "NEEDS_READER" in resolved
    assert row[0] is not None
    assert row[1] == "AUTO_RESOLVED"


def test_qa_counts_missing_claimset_correctly(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    vault = tmp_path / "vault"
    inbox = vault / "Inbox" / "PaperPipe"
    inbox.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT,
            feedback_json TEXT,
            pdf_path TEXT,
            gate_reason TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_path) VALUES (?, ?, ?, ?, ?, ?)",
        ("p_claims", "Has claims", "APPROVED", "s", '{"claims":[{"statement":"ok"}]}', "/tmp/a.pdf"),
    )
    conn.execute(
        "INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_path) VALUES (?, ?, ?, ?, ?, ?)",
        ("p_missing", "Missing claims", "APPROVED", "s", '{"soft_tags":["#A"]}', "/tmp/b.pdf"),
    )
    conn.execute(
        "INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_path) VALUES (?, ?, ?, ?, ?, ?)",
        ("p_invalid", "Invalid json", "INDEXED", "s", "{bad json", "/tmp/c.pdf"),
    )
    conn.commit()
    conn.close()

    (inbox / "p_claims.md").write_text("## Critical Review (ClaimSet)\n", encoding="utf-8")
    (inbox / "p_missing.md").write_text("no section", encoding="utf-8")
    (inbox / "p_invalid.md").write_text("no section", encoding="utf-8")

    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    monkeypatch.setattr(
        qa_report,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=str(vault))),
    )

    result = qa_report.run_qa_check()

    assert result["total_active"] == 3
    assert result["missing_or_invalid_claimset"] == 2
    assert result["missing_critical_review_section"] == 2


def test_qa_excludes_test_fixture_records_from_operational_claimset_count(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    vault = tmp_path / "vault"
    (vault / "Inbox" / "PaperPipe").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT,
            feedback_json TEXT,
            pdf_path TEXT,
            gate_reason TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_path) VALUES (?, ?, ?, ?, ?, ?)",
        ("local--x", "fixture", "APPROVED", "s", '{"soft_tags":["#A"]}', "tests/integration_env/watch_folder/test_paper.pdf"),
    )
    conn.execute(
        "INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_path) VALUES (?, ?, ?, ?, ?, ?)",
        ("real_missing", "real", "APPROVED", "s", '{"soft_tags":["#A"]}', "/tmp/real.pdf"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    monkeypatch.setattr(
        qa_report,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=str(vault))),
    )

    result = qa_report.run_qa_check()
    assert result["missing_or_invalid_claimset"] == 1


def test_qa_claimset_artifact_lookup_supports_paper_key_dir(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state.db"
    vault = tmp_path / "vault"
    (vault / "Inbox" / "PaperPipe").mkdir(parents=True, exist_ok=True)

    paper_id = "doi:10.1000/keydir"
    paper_key = make_paper_key(paper_id)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT,
            feedback_json TEXT,
            pdf_path TEXT,
            paper_key TEXT,
            gate_reason TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, title, status, summary, feedback_json, pdf_path, paper_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (paper_id, "keydir", "APPROVED", "s", '{"soft_tags":["#A"]}', "/tmp/keydir.pdf", paper_key),
    )
    conn.commit()
    conn.close()

    artifacts_root = tmp_path / "artifacts"
    claimset_file = artifacts_root / paper_key / "run_001" / "claimset.json"
    claimset_file.parent.mkdir(parents=True, exist_ok=True)
    claimset_file.write_text(
        '{"doc_id":"d","claims":[{"claim_id":"c1","statement":"s","evidence_spans":[{"page":1,"quote":"q"}],"limitations":[],"confidence":0.7}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))

    (vault / "Inbox" / "PaperPipe" / "doi101000keydir.md").write_text("no section", encoding="utf-8")

    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    monkeypatch.setattr(
        qa_report,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=str(vault))),
    )

    result = qa_report.run_qa_check()
    assert result["missing_or_invalid_claimset"] == 0


def test_exporter_auto_skips_test_fixture_needs_reader():
    conn = sqlite3.connect(":memory:")
    _create_review_queue_table(conn)
    conn.execute(
        "INSERT INTO review_queue (paper_id, decision, reason) VALUES (?, ?, ?)",
        ("local--x", "NEEDS_READER", "missing"),
    )
    conn.commit()

    paper = {"paper_id": "local--x", "pdf_path": "tests/integration_env/watch_folder/test_paper.pdf"}
    assert _is_test_fixture_paper(paper) is True

    updated = _auto_skip_test_fixture_followups(conn, paper)
    conn.commit()
    row = conn.execute(
        "SELECT owner, resolved_at, resolution, reason FROM review_queue WHERE paper_id='local--x'"
    ).fetchone()

    assert updated == 1
    assert row[0] == "TEST_FIXTURE"
    assert row[1] is not None
    assert row[2] == "AUTO_SKIPPED_TEST_FIXTURE"
    assert "[auto-skip:test_fixture]" in row[3]
