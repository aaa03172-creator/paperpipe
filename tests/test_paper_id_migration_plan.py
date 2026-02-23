import json
import sqlite3

from scripts.plan_paper_id_migration import build_plan, load_zotero_keys


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            pdf_path TEXT,
            status TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def test_load_zotero_keys_reads_citation_keys(tmp_path):
    zotero = tmp_path / "zotero.json"
    zotero.write_text(
        json.dumps({"items": [{"citationKey": "keyA"}, {"citationKey": "keyB"}, {"citationKey": ""}]}),
        encoding="utf-8",
    )
    keys = load_zotero_keys(zotero)
    assert keys == {"keyA", "keyB"}


def test_build_plan_prefers_zotero_when_key_is_known(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _make_db(db_path)
    try:
        conn.execute(
            "INSERT INTO papers (paper_id, doi, status) VALUES (?, ?, ?)",
            ("legacyKey", "10.1000/abc", "INDEXED"),
        )
        conn.commit()
    finally:
        conn.close()

    plan = build_plan(db_path, zotero_keys={"legacyKey"})
    assert len(plan) == 1
    assert plan[0]["paper_id_proposed"] == "zotero:legacyKey"


def test_build_plan_uses_doi_or_pdf_hash_without_zotero_key(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _make_db(db_path)
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nx\n")
    try:
        conn.execute(
            "INSERT INTO papers (paper_id, doi, pdf_path, status) VALUES (?, ?, ?, ?)",
            ("legacyA", "10.1000/abc", str(pdf_path), "INDEXED"),
        )
        conn.execute(
            "INSERT INTO papers (paper_id, doi, pdf_path, status) VALUES (?, ?, ?, ?)",
            ("legacyB", None, str(pdf_path), "INDEXED"),
        )
        conn.commit()
    finally:
        conn.close()

    plan = build_plan(db_path, zotero_keys=set())
    mapped = {item["paper_id_current"]: item["paper_id_proposed"] for item in plan}
    assert mapped["legacyA"] == "doi:10.1000/abc"
    assert mapped["legacyB"].startswith("pdfsha256:")
