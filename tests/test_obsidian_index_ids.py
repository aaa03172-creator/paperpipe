from __future__ import annotations

import csv
from types import SimpleNamespace

from src.obsidian_index import find_related_papers, update_csv_index


def _read_rows(path):
    with open(path, "r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_update_csv_index_uses_canonical_id_from_doi(tmp_path):
    index_path = tmp_path / "paper_collection.csv"
    paper = {
        "title": "Paper A",
        "doi": "10.1000/ABC",
        "slot": "A",
        "tags": ["#x"],
        "authors": ["Kim"],
    }

    update_csv_index(paper, index_path)
    rows = _read_rows(index_path)

    assert len(rows) == 1
    assert rows[0]["Paper_ID"] == "doi:10.1000/abc"


def test_update_csv_index_prefers_existing_paper_id(tmp_path):
    index_path = tmp_path / "paper_collection.csv"
    paper = {
        "paper_id": "manual:keep-this-id",
        "title": "Paper B",
        "doi": "10.2000/xyz",
        "slot": "B",
        "tags": ["#y"],
        "authors": ["Lee"],
    }

    update_csv_index(paper, index_path)
    rows = _read_rows(index_path)

    assert len(rows) == 1
    assert rows[0]["Paper_ID"] == "manual:keep-this-id"


def test_find_related_papers_skips_self_on_legacy_alias(tmp_path):
    vault = tmp_path / "Vault"
    index_dir = vault / "00_Index"
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / "paper_collection.csv"
    index_path.write_text(
        "Date,Slot,Paper_ID,Title,DOI,Source,URL,Score,Status,Note_Path,Tags,Authors\n"
        "2026-02-23,A,10.3000/test,Paper C,10.3000/test,PubMed,https://x,Top1,Inbox,Inbox/a.md,#one;#two,Kim\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault, index_all="00_Index/paper_collection.csv"))

    block = find_related_papers(
        {"doi": "10.3000/test", "slot": "A", "tags": ["#one", "#two"]},
        config,
    )
    assert block == ""
