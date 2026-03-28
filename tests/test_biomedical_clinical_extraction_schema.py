from __future__ import annotations

import pytest

from src.schemas.core import BiomedicalClinicalExtraction


@pytest.mark.parametrize(
    ("paper_id", "condition", "intervention_category", "followup_tag"),
    [
        ("oncology-nsclc", "Metastatic non-small cell lung cancer", "small_molecule", "therapeutic"),
        ("immunology-ibd", "Ulcerative colitis", "biologic", "therapeutic"),
        ("biomaterials-cartilage", "Focal cartilage defect", "biomaterial", "device"),
        ("neuroscience-epilepsy", "Drug-resistant focal epilepsy", "device", "therapeutic"),
    ],
)
def test_biomedical_clinical_extraction_accepts_multiple_biomedical_domains(
    paper_id: str,
    condition: str,
    intervention_category: str,
    followup_tag: str,
) -> None:
    payload = {
        "paper_id": paper_id,
        "citation": {
            "title": paper_id,
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
            "doi": None,
            "url": None,
        },
        "population": {
            "condition": condition,
            "n_total": 42,
            "cohort_description": "Adults enrolled at two hospitals.",
        },
        "intervention": {
            "category": intervention_category,
            "name": "Investigational intervention",
            "dose": "Per protocol",
        },
        "comparator": {
            "category": "active_control",
            "description": "Standard of care",
        },
        "outcomes": {
            "primary": [
                {
                    "name": "Primary endpoint",
                    "domain": "primary",
                    "effect_direction": "improved",
                }
            ],
            "safety": [
                {
                    "name": "Adverse events",
                    "domain": "safety",
                    "effect_direction": "not_applicable",
                }
            ],
        },
        "eligibility_flags": {
            "is_human_clinical_study": True,
            "fits_biomedical_scope": True,
            "followup_tag": followup_tag,
        },
        "extraction_quality": {
            "confidence": "medium",
            "missing_fields": [],
        },
    }

    validated = BiomedicalClinicalExtraction.model_validate(payload)

    assert validated.population.condition == condition
    assert validated.intervention.category == intervention_category
    assert validated.eligibility_flags.fits_biomedical_scope is True


def test_biomedical_clinical_extraction_scope_note_is_domain_neutral() -> None:
    note = BiomedicalClinicalExtraction.default_scope_note()

    assert "default biomedical clinical extraction contract" in note
    assert "must not assume neuroscience-, Alzheimer-, MCI-, or ketone-specific scope" in note
