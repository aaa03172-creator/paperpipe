from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from scripts.audit_obsidian_index_ids import run_audit
from scripts.normalize_obsidian_index_ids import apply_plan, build_plan, write_rows


def _write_index(path: Path, rows: list[dict[str, str]]) -> None:
    headers = ["Date", "Slot", "Paper_ID", "Title", "DOI", "Source", "URL", "Score", "Status", "Note_Path"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_plan_promotes_legacy_doi_to_canonical(tmp_path: Path):
    index_path = tmp_path / "paper_collection.csv"
    _write_index(
        index_path,
        [
            {
                "Date": "2026-02-23",
                "Slot": "A",
                "Paper_ID": "10.3000/Test",
                "Title": "Paper A",
                "DOI": "https://doi.org/10.3000/Test",
                "Source": "PubMed",
                "URL": "",
                "Score": "Top1",
                "Status": "Inbox",
                "Note_Path": "Inbox/a.md",
            }
        ],
    )

    plan, _rows, _map = build_plan(index_path=index_path, db_path=tmp_path / "missing.db")
    assert len(plan) == 1
    assert plan[0]["paper_id_current"] == "10.3000/Test"
    assert plan[0]["paper_id_proposed"] == "doi:10.3000/test"
    assert plan[0]["reason"] == "doi"


def test_build_plan_uses_obsidian_path_fallback_when_doi_missing(tmp_path: Path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                obsidian_path TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO papers (paper_id, obsidian_path) VALUES (?, ?)",
            ("zotero:ABCD1234", "Inbox/2026-02-23/paper_a.md"),
        )
        conn.commit()
    finally:
        conn.close()

    index_path = tmp_path / "paper_collection.csv"
    _write_index(
        index_path,
        [
            {
                "Date": "2026-02-23",
                "Slot": "A",
                "Paper_ID": "legacy-paper-a",
                "Title": "Paper A",
                "DOI": "",
                "Source": "PubMed",
                "URL": "",
                "Score": "Top1",
                "Status": "Inbox",
                "Note_Path": "./Inbox/2026-02-23/paper_a.md",
            }
        ],
    )

    plan, _rows, _map = build_plan(index_path=index_path, db_path=db_path)
    assert len(plan) == 1
    assert plan[0]["paper_id_current"] == "legacy-paper-a"
    assert plan[0]["paper_id_proposed"] == "zotero:ABCD1234"
    assert plan[0]["reason"] == "obsidian_path"


def test_apply_plan_updates_only_target_rows(tmp_path: Path):
    index_path = tmp_path / "paper_collection.csv"
    _write_index(
        index_path,
        [
            {
                "Date": "2026-02-23",
                "Slot": "A",
                "Paper_ID": "doi:10.5000/keep",
                "Title": "Keep",
                "DOI": "10.5000/keep",
                "Source": "PubMed",
                "URL": "",
                "Score": "Top1",
                "Status": "Inbox",
                "Note_Path": "Inbox/keep.md",
            },
            {
                "Date": "2026-02-23",
                "Slot": "B",
                "Paper_ID": "10.5000/change",
                "Title": "Change",
                "DOI": "10.5000/change",
                "Source": "PubMed",
                "URL": "",
                "Score": "Top2",
                "Status": "Inbox",
                "Note_Path": "Inbox/change.md",
            },
        ],
    )

    plan, rows, _map = build_plan(index_path=index_path, db_path=tmp_path / "missing.db")
    assert len(plan) == 1
    apply_plan(rows, plan)
    write_rows(index_path, rows)

    out_rows = _read_rows(index_path)
    assert out_rows[0]["Paper_ID"] == "doi:10.5000/keep"
    assert out_rows[1]["Paper_ID"] == "doi:10.5000/change"


def test_audit_reports_migratable_candidates(tmp_path: Path, capsys):
    index_path = tmp_path / "paper_collection.csv"
    _write_index(
        index_path,
        [
            {
                "Date": "2026-02-23",
                "Slot": "A",
                "Paper_ID": "10.7777/legacy",
                "Title": "Legacy",
                "DOI": "10.7777/legacy",
                "Source": "PubMed",
                "URL": "",
                "Score": "Top1",
                "Status": "Inbox",
                "Note_Path": "Inbox/legacy.md",
            }
        ],
    )

    rc = run_audit(index_path=index_path, db_path=tmp_path / "missing.db", sample_limit=2)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "[AUDIT] canonical_count=0" in captured
    assert "[AUDIT] migratable_candidates=1" in captured
