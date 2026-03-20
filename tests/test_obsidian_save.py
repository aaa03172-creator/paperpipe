from __future__ import annotations

import csv
from types import SimpleNamespace

from src.obsidian import save_paper_to_obsidian
from src.schemas import PaperStatus


def test_save_paper_to_obsidian_updates_main_and_clinical_indexes(tmp_path):
    vault = tmp_path / "vault"
    config = SimpleNamespace(
        paths=SimpleNamespace(
            obsidian_vault=vault,
            index_all="00_Index/paper_collection.csv",
            index_clinical="00_Index/mct_mci_trials.csv",
        )
    )
    paper = {
        "title": "Clinical Trial Save Path",
        "source": "PubMed",
        "link": "https://example.org/clinical-trial-save-path",
        "slot": "clinical",
        "doi": "10.1000/clinical-save-path",
        "tags": ["#MCI", "#Trial"],
        "authors": ["Doe J", "Smith A"],
        "reading_status": "Inbox",
        "processing_status": PaperStatus.APPROVED,
        "summary": "Clinical abstract",
        "local_pdf_path": None,
    }

    note_path = save_paper_to_obsidian(
        paper,
        config,
        extraction=None,
        subfolder_override="Inbox/Test",
    )

    relative_note_path = note_path.relative_to(vault).as_posix()
    main_index = vault / "00_Index" / "paper_collection.csv"
    clinical_index = vault / "00_Index" / "mct_mci_trials.csv"

    assert note_path.exists()
    assert main_index.exists()
    assert clinical_index.exists()

    with main_index.open("r", encoding="utf-8") as fh:
        main_rows = list(csv.DictReader(fh))
    with clinical_index.open("r", encoding="utf-8") as fh:
        clinical_rows = list(csv.DictReader(fh))

    assert len(main_rows) == 1
    assert len(clinical_rows) == 1
    assert main_rows[0]["Paper_ID"] == "10.1000/clinical-save-path"
    assert clinical_rows[0]["Paper_ID"] == "10.1000/clinical-save-path"
    assert main_rows[0]["Note_Path"] == relative_note_path
    assert clinical_rows[0]["Note_Path"] == relative_note_path
