from __future__ import annotations

import csv
from types import SimpleNamespace

from src.obsidian import save_paper_to_obsidian
from src.schemas import BiomedicalClinicalExtraction, PaperStatus


def _config(vault):
    return SimpleNamespace(
        paths=SimpleNamespace(
            obsidian_vault=vault,
            index_all="00_Index/paper_collection.csv",
            index_clinical="00_Index/clinical_trials.csv",
        )
    )


def test_save_paper_to_obsidian_updates_main_and_clinical_indexes(tmp_path):
    vault = tmp_path / "vault"
    config = _config(vault)
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
    clinical_index = vault / "00_Index" / "clinical_trials.csv"

    assert note_path.exists()
    assert main_index.exists()
    assert clinical_index.exists()
    note_text = note_path.read_text(encoding="utf-8")

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
    assert "Clinical Quick Look" in note_text
    assert "Clinical Workspace Lane" in note_text
    assert "Specialty Extraction Lane" not in note_text


def test_save_paper_to_obsidian_writes_generic_clinical_fields_from_extraction(tmp_path):
    vault = tmp_path / "vault"
    config = _config(vault)
    paper = {
        "title": "Generic Clinical Export",
        "source": "PubMed",
        "link": "https://example.org/generic-clinical-export",
        "slot": "clinical",
        "doi": "10.1000/generic-clinical-export",
        "tags": ["#oncology", "#trial"],
        "authors": ["Lee J", "Garcia M"],
        "reading_status": "Inbox",
        "processing_status": PaperStatus.APPROVED,
        "summary": "Clinical abstract",
        "local_pdf_path": None,
    }
    extraction = BiomedicalClinicalExtraction(
        paper_id="p_generic_001",
        citation={
            "title": "Generic Clinical Export",
            "authors_first": "Lee",
            "year": 2026,
            "journal_or_server": "Journal of Translation",
            "doi": "10.1000/generic-clinical-export",
            "url": "https://example.org/generic-clinical-export",
        },
        population={
            "condition": "Metastatic non-small cell lung cancer",
            "cohort_description": "Previously treated adults",
            "n_total": 72,
        },
        intervention={
            "category": "small_molecule",
            "name": "Targeted therapy",
            "dose": "200 mg daily",
            "duration_weeks": 24,
        },
        outcomes={
            "primary": [
                {
                    "name": "Progression-free survival",
                    "domain": "primary",
                }
            ]
        },
        safety_adherence={
            "adverse_events_reported": True,
            "adverse_events_summary": "Grade 3 rash and diarrhea reported.",
        },
        eligibility_flags={"followup_tag": "therapeutic"},
    )

    save_paper_to_obsidian(
        paper,
        config,
        extraction=extraction,
        subfolder_override="Inbox/Test",
    )

    clinical_index = vault / "00_Index" / "clinical_trials.csv"
    with clinical_index.open("r", encoding="utf-8") as fh:
        clinical_rows = list(csv.DictReader(fh))

    assert len(clinical_rows) == 1
    assert clinical_rows[0]["Population"] == "Metastatic non-small cell lung cancer, Previously treated adults, n=72"
    assert clinical_rows[0]["Intervention"] == "Targeted therapy, Small Molecule, 200 mg daily, 24 weeks"
    assert clinical_rows[0]["Condition"] == "Metastatic non-small cell lung cancer"
    assert clinical_rows[0]["Primary_Outcome"] == "Progression-free survival"
    assert clinical_rows[0]["Safety"] == "Grade 3 rash and diarrhea reported."
    assert clinical_rows[0]["Followup_Tag"] == "Therapeutic"
    assert clinical_rows[0]["Outcome_Cognition"] == ""
    assert clinical_rows[0]["Outcome_ADL"] == ""
