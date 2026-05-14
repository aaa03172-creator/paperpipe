import json
import sqlite3
from pathlib import Path

from scripts.audit_papers_doi_identity import audit_papers_doi_identity, main


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def test_audit_papers_doi_identity_groups_duplicates_and_non_doi_values(tmp_path, capsys):
    db_path = tmp_path / "state.db"
    conn = _connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO papers (paper_id, doi, title, source, status) VALUES (?, ?, ?, ?, ?)",
        [
            ("paper-a", "https://doi.org/10.1000/ABC", "Alpha", "zotero", "NEW"),
            ("paper-b", "doi:10.1000/abc", "Alpha duplicate", "manual", "INDEXED"),
            ("paper-c", "zotero:NOT-A-DOI", "Legacy bad DOI", "zotero", "NEW"),
            ("paper-d", "", "No DOI", "manual", "NEW"),
            ("paper-e", None, "Null DOI", "manual", "NEW"),
        ],
    )
    conn.commit()

    payload = audit_papers_doi_identity(conn)
    conn.close()

    assert payload["schema_version"] == "papers_doi_identity_audit.v1"
    assert payload["rows_with_doi_count"] == 3
    assert payload["duplicate_group_count"] == 1
    assert payload["duplicate_groups"][0]["normalized_doi"] == "10.1000/abc"
    assert payload["duplicate_groups"][0]["paper_ids"] == ["paper-a", "paper-b"]
    assert payload["non_doi_value_count"] == 1
    assert payload["non_doi_values"][0]["paper_id"] == "paper-c"
    assert payload["unique_constraint_ready"] is False
    assert payload["blockers"] == ["duplicate_normalized_doi", "non_doi_values_in_doi_column"]

    assert main(["--db", str(db_path)]) == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["duplicate_group_count"] == 1


def test_audit_papers_doi_identity_reports_ready_when_clean(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO papers (paper_id, doi) VALUES (?, ?)",
        [
            ("paper-a", "10.1000/a"),
            ("paper-b", "10.1000/b"),
            ("paper-c", None),
        ],
    )
    conn.commit()

    payload = audit_papers_doi_identity(conn)
    conn.close()

    assert payload["rows_with_doi_count"] == 2
    assert payload["duplicate_groups"] == []
    assert payload["non_doi_values"] == []
    assert payload["unique_constraint_ready"] is True
    assert payload["blockers"] == []
