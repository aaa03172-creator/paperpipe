from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.generate_extraction_predictions import _build_paper_inputs, _repair_prediction_payload
from src.schemas.core import SpecialtyTrialExtraction


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_paper_inputs_extracts_summary_and_methods_from_document_artifact(tmp_path: Path) -> None:
    document_artifact = tmp_path / "document_artifact.json"
    _write_json(
        document_artifact,
        {
            "pages": [
                {
                    "blocks": [
                        {"lines": [{"text": "Trial Title"}]},
                        {
                            "lines": [
                                {
                                    "text": (
                                        "IMPORTANCE Background text. OBJECTIVE Trial objective. "
                                        "DESIGN, SETTING, AND PARTICIPANTS Randomized trial details. "
                                        "INTERVENTIONS Oral study drug. RESULTS No benefit. "
                                        "Author Affiliations: Placeholder"
                                    )
                                }
                            ]
                        },
                    ]
                }
            ]
        },
    )
    gold_payload = {
        "citation": {
            "title": "Gold Trial Title",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        }
    }

    paper = _build_paper_inputs(document_artifact, gold_payload, "paper-1")

    assert paper["title"] == "Gold Trial Title"
    assert "IMPORTANCE" in paper["summary"]
    assert "DESIGN, SETTING, AND PARTICIPANTS" in paper["methods_snippet"]


def test_build_paper_inputs_appends_followup_phrase_from_second_page(tmp_path: Path) -> None:
    document_artifact = tmp_path / "document_artifact.json"
    _write_json(
        document_artifact,
        {
            "pages": [
                {
                    "blocks": [
                        {
                            "lines": [
                                {
                                    "text": (
                                        "Abstract Methods: Participants with plasma biomarkers were included. "
                                        "Results: Clinical performance was assessed."
                                    )
                                }
                            ]
                        }
                    ]
                },
                {
                    "blocks": [
                        {
                            "lines": [
                                {
                                    "text": (
                                        "BioFINDER-1 participants were enrolled between January 2010 and December 2014 "
                                        "and were followed longitudinally for up to 8 years."
                                    )
                                }
                            ]
                        }
                    ]
                },
            ]
        },
    )
    gold_payload = {
        "citation": {
            "title": "Confounding factors of Alzheimer's disease plasma biomarkers and their impact on clinical performance",
            "authors_first": "Pichet Binette",
            "year": 2023,
            "journal_or_server": "Alzheimer's & Dementia",
        }
    }

    paper = _build_paper_inputs(document_artifact, gold_payload, "paper-1")

    assert "followed longitudinally for up to 8 years" in paper["methods_snippet"]


def test_build_paper_inputs_appends_over_period_phrase_from_second_page(tmp_path: Path) -> None:
    document_artifact = tmp_path / "document_artifact.json"
    _write_json(
        document_artifact,
        {
            "pages": [
                {
                    "blocks": [
                        {
                            "lines": [
                                {
                                    "text": (
                                        "Summary Background text. Methods We developed and validated a blood immunoassay. "
                                        "Findings The assay identified Alzheimer's disease."
                                    )
                                }
                            ]
                        }
                    ]
                },
                {
                    "blocks": [
                        {
                            "lines": [
                                {
                                    "text": (
                                        "Additionally, blood p-tau181 predicted cognitive decline and hippocampal atrophy "
                                        "over a period of 1 year in longitudinal analyses."
                                    )
                                }
                            ]
                        }
                    ]
                },
            ]
        },
    )
    gold_payload = {
        "citation": {
            "title": "Blood phosphorylated tau 181 as a biomarker for Alzheimer's disease",
            "authors_first": "Karikari",
            "year": 2020,
            "journal_or_server": "Lancet Neurology",
        }
    }

    paper = _build_paper_inputs(document_artifact, gold_payload, "paper-1")

    assert "over a period of 1 year" in paper["methods_snippet"]


def test_build_paper_inputs_reads_section_based_document_artifact(tmp_path: Path) -> None:
    document_artifact = tmp_path / "document_artifact.json"
    _write_json(
        document_artifact,
        {
            "sections": [
                {
                    "name": "page_1",
                    "text": (
                        "Abstract INTRODUCTION: Blood tests have the potential to improve the accuracy of Alzheimer's disease "
                        "clinical diagnosis. METHODS: Plasma samples from ADNI were assayed with multiple blood tests. "
                        "RESULTS: Plasma p-tau217 had the strongest relationships with all AD outcomes."
                    ),
                },
                {
                    "name": "page_2",
                    "text": (
                        "METHODS Participants were selected for inclusion who had plasma samples collected within 6 months "
                        "of an amyloid PET scan for three distinct timepoints."
                    ),
                },
                {
                    "name": "page_3",
                    "text": (
                        "Based on these selection criteria, 393 ADNI participants had at least six plasma aliquots. "
                        "The assays were then compared head-to-head."
                    ),
                },
            ]
        },
    )
    gold_payload = {
        "citation": {
            "title": "Head-to-head comparison of leading blood tests for Alzheimer's disease pathology",
            "authors_first": "Schindler",
            "year": 2024,
            "journal_or_server": "Alzheimer's & Dementia",
        }
    }

    paper = _build_paper_inputs(document_artifact, gold_payload, "paper-1")

    assert "Blood tests have the potential" in paper["summary"]
    assert "393 ADNI participants had at least six plasma aliquots" in paper["methods_snippet"]


def test_repair_prediction_payload_backfills_citation_and_normalizes_enums() -> None:
    gold_payload = {
        "citation": {
            "title": "Targeting Prodromal Alzheimer Disease With Avagacestat",
            "authors_first": "Coric",
            "year": 2015,
            "journal_or_server": "JAMA Neurology",
        }
    }
    raw_payload = {
        "citation": {"title": "", "authors_first": "", "year": "2015", "journal_or_server": ""},
        "study_design": {"design": "randomized clinical trial", "blinding": "double blinded", "setting": "multicenter"},
        "intervention": {"category": "intranasal", "route": "intranasal"},
        "outcomes": {"cognition": [{"name": "ADAS-Cog", "effect_direction": "no difference"}]},
        "extraction_quality": {"confidence": "MEDIUM", "missing_fields": "duration"},
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.paper_id == "paper-1"
    assert validated.citation.authors_first == "Coric"
    assert validated.study_design.design == "parallel_rct"
    assert validated.study_design.blinding == "double_blind"
    assert validated.study_design.setting == "multi_center"
    assert validated.intervention.route == "other"
    assert validated.outcomes.cognition[0].effect_direction == "no_change"
    assert validated.extraction_quality.confidence == "medium"
    assert validated.extraction_quality.missing_fields == []


def test_repair_prediction_payload_handles_null_nested_models_and_common_aliases() -> None:
    gold_payload = {
        "citation": {
            "title": "Targeting Prodromal Alzheimer Disease With Avagacestat",
            "authors_first": "Coric",
            "year": 2015,
            "journal_or_server": "JAMA Neurology",
        }
    }
    raw_payload = {
        "paper_id": "Targeting Prodromal Alzheimer Disease With Avagacestat",
        "citation": None,
        "study_design": {
            "design": "randomized, placebo-controlled phase 2 clinical trial with a parallel, untreated, nonrandomized observational cohort",
            "setting": "multicenter global population",
            "duration_weeks": 104,
        },
        "population": {
            "target_population": "MCI-only",
            "sample_size": 263,
        },
        "intervention": {
            "type": "oral",
            "product_name": "avagacestat",
            "category": "γ-secretase inhibitor",
        },
        "comparator": {
            "type": "placebo",
            "product_name": "placebo",
        },
        "ketone_confirmation": None,
        "outcomes": {
            "primary_outcomes": ["safety and tolerability of avagacestat"],
        },
        "safety_adherence": {
            "results": ["avagacestat was relatively well tolerated"],
            "dropout_n_total": None,
        },
        "risk_of_bias_hints": None,
        "eligibility_flags": {
            "include_for_mci_mct_review": True,
        },
        "extraction_quality": {
            "missing_fields": ["main outcomes and measure"],
        },
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.paper_id == "paper-1"
    assert validated.citation.title == "Targeting Prodromal Alzheimer Disease With Avagacestat"
    assert validated.population.n_total == 263
    assert validated.population.mci_only is True
    assert validated.intervention.route == "oral"
    assert validated.intervention.category == "unknown"
    assert validated.comparator.description == "placebo"
    assert validated.outcomes.cognition[0].name == "safety and tolerability of avagacestat"
    assert validated.ketone_confirmation.measured is False
    assert validated.risk_of_bias_hints.blinding_clear is False
    assert validated.safety_adherence.dropout_n_total == 0


def test_repair_prediction_payload_wraps_string_cognition_entries() -> None:
    gold_payload = {
        "citation": {
            "title": "Example",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        }
    }
    raw_payload = {
        "outcomes": {
            "cognition": ["MCI symptoms"],
        }
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.outcomes.cognition[0].name == "MCI symptoms"
    assert validated.outcomes.cognition[0].effect_direction == "unknown"


def test_repair_prediction_payload_recovers_alias_counts_duration_and_named_outcomes() -> None:
    gold_payload = {
        "citation": {
            "title": "Safety, Efficacy, and Feasibility of Intranasal Insulin for the Treatment of Mild Cognitive Impairment and Alzheimer Disease Dementia",
            "authors_first": "Craft",
            "year": 2020,
            "journal_or_server": "JAMA Neurology",
        }
    }
    raw_payload = {
        "citation": None,
        "study_design": {
            "type": "randomized controlled trial",
            "blinding": "double-blind",
            "duration": "12 months (blinded phase) + 6-month open-label extension phase",
        },
        "population": {
            "target_population": "MCI-only",
            "inclusion_criteria": [
                "diagnosis of amnestic mild cognitive impairment or Alzheimer disease",
            ],
            "diagnosis": ["amnestic mild cognitive impairment", "Alzheimer disease"],
            "number_of_participants": 289,
        },
        "intervention": {
            "type": "intranasal insulin",
            "dose": "40 IU daily",
            "product_name": "Humulin-RU-100; Lilly",
        },
        "comparator": {"type": "placebo", "dose": "diluent daily"},
        "outcomes": {
            "primary_outcome": "mean score change on the Alzheimer Disease Assessment Scale-cognitive subscale 12",
        },
        "eligibility_flags": {"include_for_mci_mct_review": True},
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.n_total == 289
    assert validated.population.mci_only is False
    assert validated.intervention.product_name == "Intranasal insulin"
    assert validated.intervention.route == "other"
    assert validated.intervention.dose_schedule == "40 IU daily"
    assert validated.study_design.duration_weeks == 52
    assert validated.outcomes.cognition[0].name == "ADAS-Cog-12"
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_uses_treatment_phase_counts_and_exclusion_reason() -> None:
    gold_payload = {
        "citation": {
            "title": "Targeting Prodromal Alzheimer Disease With Avagacestat",
            "authors_first": "Coric",
            "year": 2015,
            "journal_or_server": "JAMA Neurology",
        }
    }
    raw_payload = {
        "paper_id": "Targeting Prodromal Alzheimer Disease With Avagacestat",
        "study_design": {
            "type": "randomized, placebo-controlled phase 2 clinical trial with a parallel, untreated, nonrandomized observational cohort",
            "setting": "multicenter global population",
        },
        "population": {
            "target_population": "MCI-only",
            "total_participants": 1358,
            "participants_in_treatment_phase": 263,
        },
        "intervention": {
            "type": "oral avagacestat or placebo daily",
            "name": "avagacestat",
            "category": "γ-secretase inhibitor",
        },
        "comparator": "placebo",
        "outcomes": {
            "primary_outcomes": ["safety and tolerability of avagacestat"],
        },
        "eligibility_flags": {
            "include_for_mci_mct_review": False,
            "reason": "The study includes AD or mixed populations and MCI-specific results are not separable",
        },
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.n_total == 263
    assert validated.intervention.product_name == "Avagacestat"
    assert validated.intervention.category == "unknown"
    assert validated.intervention.route == "oral"
    assert validated.comparator.description == "placebo"
    assert validated.outcomes.cognition[0].name == "safety and tolerability of avagacestat"
    assert validated.eligibility_flags.reason_if_excluded == (
        "The study includes AD or mixed populations and MCI-specific results are not separable"
    )


def test_repair_prediction_payload_downshifts_nontrial_biomarker_stub_population() -> None:
    gold_payload = {
        "citation": {
            "title": "Biomarker modeling of Alzheimer's disease using PET-based Braak staging",
            "authors_first": "Therriault",
            "year": 2022,
            "journal_or_server": "JAMA Neurology",
        }
    }
    raw_payload = {
        "citation": {},
        "study_design": {"design": "observational"},
        "population": {"mci_only": True},
        "intervention": {"category": "unknown", "product_name": "unknown"},
        "outcomes": [{"outcome": "Braak tau staging system", "type": "primary"}],
        "eligibility_flags": {"include_for_mci_mct_review": True},
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.mci_only is False
    assert validated.eligibility_flags.include_for_mci_mct_review is False
    assert validated.outcomes.cognition[0].name == "PET-based Braak stage"


def test_repair_prediction_payload_joins_risk_of_bias_notes_lists() -> None:
    gold_payload = {
        "citation": {
            "title": "Example",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        }
    }
    raw_payload = {
        "risk_of_bias_hints": {
            "notes": ["No specific information on risk of bias provided"],
        }
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.risk_of_bias_hints.notes == "No specific information on risk of bias provided"


def test_repair_prediction_payload_downshifts_review_stub_with_generic_outcomes() -> None:
    gold_payload = {
        "citation": {
            "title": "Example review",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        }
    }
    raw_payload = {
        "study_design": {"design": "review"},
        "population": {"mci_only": True},
        "intervention": {"category": "MCT/ketone supplementation"},
        "outcomes": [{"name": "cognitive symptoms"}, {"name": "ADL/function"}],
        "eligibility_flags": {"include_for_mci_mct_review": True},
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.mci_only is False
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_accepts_n_mci_as_sample_size_alias() -> None:
    gold_payload = {
        "citation": {
            "title": "Example",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        }
    }
    raw_payload = {
        "population": {
            "mci_only": True,
            "n_mci": 324,
        }
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1")
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.n_total == 324


def test_repair_prediction_payload_uses_paper_context_for_sample_size_and_duration() -> None:
    gold_payload = {
        "citation": {
            "title": "Trial",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        }
    }
    raw_payload = {
        "population": {"mci_only": True},
        "study_design": {},
    }
    paper_context = {
        "title": "Trial",
        "summary": (
            "A total of 289 participants were randomized. "
            "Participants received treatment for 12 months during the blinded phase, "
            "followed by a 6-month open-label extension phase."
        ),
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.n_total == 289
    assert validated.study_design.duration_weeks == 52
    assert validated.study_design.followup_weeks == 26


def test_repair_prediction_payload_prefers_text_derived_main_phase_duration_over_oversized_raw_value() -> None:
    gold_payload = {
        "citation": {
            "title": "Trial",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
        }
    }
    raw_payload = {
        "study_design": {
            "duration_weeks": 104,
            "followup_weeks": 26,
        },
    }
    paper_context = {
        "title": "Trial",
        "summary": "Participants received treatment for 12 months during the blinded phase followed by a 6-month open-label extension phase.",
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.study_design.duration_weeks == 52
    assert validated.study_design.followup_weeks == 26


def test_repair_prediction_payload_uses_living_individuals_sample_size_and_braak_outcome_hint() -> None:
    gold_payload = {
        "citation": {
            "title": "Biomarker modeling of Alzheimer's disease using PET-based Braak staging",
            "authors_first": "Therriault",
            "year": 2022,
            "journal_or_server": "Nature Aging",
        }
    }
    raw_payload = {
        "population": {"mci_only": True},
        "outcomes": [{"name": "Braak stage"}],
        "eligibility_flags": {"include_for_mci_mct_review": True},
    }
    paper_context = {
        "title": "Biomarker modeling of Alzheimer's disease using PET-based Braak staging",
        "summary": "Using PET-based Braak staging, we applied the Braak tau staging system to 324 living individuals.",
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.n_total == 324
    assert validated.outcomes.cognition[0].name == "PET-based Braak stage"


def test_repair_prediction_payload_uses_paper_context_to_downshift_biomarker_review() -> None:
    gold_payload = {
        "citation": {
            "title": "Blood biomarkers for Alzheimer's disease in clinical practice and trials",
            "authors_first": "Hansson",
            "year": 2023,
            "journal_or_server": "Nature Aging",
        }
    }
    raw_payload = {
        "population": {"mci_only": True},
        "intervention": {"product_name": "MCT/ketone supplementation", "category": "ketone_ester_or_salt"},
        "outcomes": [{"name": "cognitive symptoms"}],
        "eligibility_flags": {"include_for_mci_mct_review": True},
    }
    paper_context = {
        "title": "Blood biomarkers for Alzheimer's disease in clinical practice and trials",
        "summary": "Several assays for measuring phosphorylated tau (p-tau) in plasma exhibit high diagnostic accuracy.",
        "methods_snippet": "Not available",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.mci_only is False
    assert validated.eligibility_flags.include_for_mci_mct_review is False
    assert validated.intervention.product_name is None
    assert validated.outcomes.cognition[0].name == "Plasma p-tau diagnostic accuracy"


def test_repair_prediction_payload_prunes_resolved_missing_fields_and_keeps_nontrial_design() -> None:
    gold_payload = {
        "citation": {
            "title": "Biomarker modeling of Alzheimer's disease using PET-based Braak staging",
            "authors_first": "Therriault",
            "year": 2022,
            "journal_or_server": "Nature Aging",
        }
    }
    raw_payload = {
        "study_design": {"design": "nonrandomized"},
        "population": {"mci_only": True},
        "outcomes": [{"name": "Braak stage"}],
        "eligibility_flags": {"include_for_mci_mct_review": True},
        "extraction_quality": {"missing_fields": ["sample_size", "study_duration"]},
    }
    paper_context = {
        "title": "Biomarker modeling of Alzheimer's disease using PET-based Braak staging",
        "summary": "Using PET-based Braak stage, we applied the Braak tau staging system to 324 living individuals.",
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.study_design.design == "observational"
    assert validated.population.n_total == 324
    assert validated.extraction_quality.missing_fields == ["study_duration"]


def test_repair_prediction_payload_prefers_key_clinical_outcome_measures_over_safety_stub() -> None:
    gold_payload = {
        "citation": {
            "title": "Targeting Prodromal Alzheimer Disease With Avagacestat",
            "authors_first": "Coric",
            "year": 2015,
            "journal_or_server": "JAMA Neurology",
        }
    }
    raw_payload = {
        "population": {"mci_only": True, "participants_in_treatment_phase": 263},
        "intervention": {"name": "Oral avagacestat or placebo daily"},
        "outcomes": [{"name": "Safety and tolerability of avagacestat"}],
        "extraction_quality": {"missing_fields": []},
    }
    paper_context = {
        "title": "Targeting Prodromal Alzheimer Disease With Avagacestat",
        "summary": (
            "At 2 years, progression to dementia was more frequent in the PDAD cohort. "
            "No significant treatment differences were observed in the avagacestat vs placebo arm "
            "in key clinical outcome measures."
        ),
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.outcomes.cognition[0].name == "Key clinical outcome measures"
    assert validated.study_design.duration_weeks == 104


def test_repair_prediction_payload_downshifts_review_concept_paper_and_uses_mci_title_outcome() -> None:
    gold_payload = {
        "citation": {
            "title": "Mild cognitive impairment: prevalence, prognosis, aetiology, and treatment",
            "authors_first": "DeCarli",
            "year": 2003,
            "journal_or_server": "Lancet Neurology",
        }
    }
    raw_payload = {
        "study_design": {"design": "review"},
        "population": {"mci_only": True},
        "intervention": {"category": "review"},
        "outcomes": [{"name": "cognitive impairment"}],
    }
    paper_context = {
        "title": "Mild cognitive impairment: prevalence, prognosis, aetiology, and treatment",
        "summary": "This review discusses the prevalence, prognosis, aetiology, and treatment of mild cognitive impairment.",
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.mci_only is False
    assert validated.eligibility_flags.include_for_mci_mct_review is False
    assert validated.outcomes.cognition[0].name == "Mild cognitive impairment"
    assert validated.intervention.product_name is None


def test_repair_prediction_payload_uses_clinical_diagnosis_title_outcome_for_recommendation_paper() -> None:
    gold_payload = {
        "citation": {
            "title": "Clinical diagnosis of Alzheimer's disease: recommendations of the International Working Group",
            "authors_first": "Dubois",
            "year": 2021,
            "journal_or_server": "Lancet Neurology",
        }
    }
    raw_payload = {
        "study_design": {"design": "other"},
        "population": {"mci_only": False},
        "intervention": {"product_name": "unknown"},
        "comparator": {"description": "unknown"},
        "outcomes": {"cognition": [{"name": "unknown"}]},
        "eligibility_flags": {"include_for_mci_mct_review": False},
    }
    paper_context = {
        "title": "Clinical diagnosis of Alzheimer's disease: recommendations of the International Working Group",
        "summary": "This personal view proposes recommendations for the clinical diagnosis of Alzheimer's disease in practice.",
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.mci_only is False
    assert validated.outcomes.cognition[0].name == "Clinical diagnosis of Alzheimer's disease"
    assert validated.eligibility_flags.include_for_mci_mct_review is False
    assert validated.intervention.product_name is None
    assert validated.comparator.description is None


def test_repair_prediction_payload_uses_cohort_sample_size_and_long_followup() -> None:
    gold_payload = {
        "citation": {
            "title": "Blood-based biomarkers of Alzheimer's disease and incident dementia in the community",
            "authors_first": "Grande",
            "year": 2025,
            "journal_or_server": "Nature Medicine",
        }
    }
    raw_payload = {
        "study_design": {"design": "observational"},
        "population": {"mci_only": True},
        "intervention": {"category": "biomarker", "product_name": "blood-based biomarkers"},
        "outcomes": [{"name": "incident dementia"}],
        "eligibility_flags": {"include_for_mci_mct_review": True},
        "extraction_quality": {"missing_fields": ["study_design.duration_weeks", "population.n_total"]},
    }
    paper_context = {
        "title": "Blood-based biomarkers of Alzheimer's disease and incident dementia in the community",
        "summary": (
            "We estimated the predictive performance of biomarkers in a cohort of 2,148 dementia-free older adults "
            "from Sweden, who were followed for up to 16 years."
        ),
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.n_total == 2148
    assert validated.study_design.duration_weeks == 832
    assert validated.population.mci_only is False
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_uses_gut_microbiome_title_outcome_for_ad_review() -> None:
    gold_payload = {
        "citation": {
            "title": "The gut microbiome in Alzheimer's disease: what we know and what remains to be explored",
            "authors_first": "Chandra",
            "year": 2023,
            "journal_or_server": "Molecular Neurodegeneration",
        }
    }
    raw_payload = {
        "study_design": {"design": "review"},
        "population": {"mci_only": True},
        "outcomes": {"cognition": [{"name": "senile plaques"}]},
        "eligibility_flags": {"include_for_mci_mct_review": True},
        "extraction_quality": {"missing_fields": ["sample_size", "duration_weeks"]},
    }
    paper_context = {
        "title": "The gut microbiome in Alzheimer's disease: what we know and what remains to be explored",
        "summary": "This review summarizes evidence that the gut microbiome may influence Alzheimer's disease progression and what remains to be explored.",
        "methods_snippet": "",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.mci_only is False
    assert validated.eligibility_flags.include_for_mci_mct_review is False
    assert validated.outcomes.cognition[0].name == "Gut microbiome in Alzheimer's disease"


def test_repair_prediction_payload_downshifts_plasma_biomarker_multicohort_article() -> None:
    gold_payload = {
        "citation": {
            "title": "Confounding factors of Alzheimer's disease plasma biomarkers and their impact on clinical performance",
            "authors_first": "Pichet Binette",
            "year": 2023,
            "journal_or_server": "Alzheimer's & Dementia",
        }
    }
    raw_payload = {
        "study_design": {},
        "population": {
            "mci_only": True,
            "n_total": 1169,
        },
        "intervention": {
            "category": "unknown",
            "product_name": None,
        },
        "outcomes": {
            "cognition": [
                {"name": "p-tau217"},
                {"name": "p-tau181"},
            ]
        },
        "eligibility_flags": {"include_for_mci_mct_review": True},
        "extraction_quality": {"missing_fields": ["study_design.duration_weeks"]},
    }
    paper_context = {
        "title": "Confounding factors of Alzheimer's disease plasma biomarkers and their impact on clinical performance",
        "summary": (
            "Methods: Participants with plasma and CSF biomarkers were included (BioFINDER-1: n = 748, "
            "BioFINDER-2: n = 421). Clinical performance of plasma biomarkers was assessed for conversion to dementia."
        ),
        "methods_snippet": (
            "BioFINDER-1 participants were followed longitudinally for up to identify key potential confounding factors "
            "8 years. No intervention was administered because this was an observational biomarker cohort."
        ),
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.study_design.design == "observational"
    assert validated.study_design.control_type == "none"
    assert validated.study_design.duration_weeks == 416
    assert validated.population.mci_only is False
    assert validated.population.n_total == 1169
    assert validated.outcomes.cognition[0].name == "Clinical performance of Alzheimer's disease plasma biomarkers"
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_uses_diagnostic_performance_title_for_ptau181_article() -> None:
    gold_payload = {
        "citation": {
            "title": "Blood phosphorylated tau 181 as a biomarker for Alzheimer's disease: a diagnostic performance and prediction modelling study using data from four prospective cohorts",
            "authors_first": "Karikari",
            "year": 2020,
            "journal_or_server": "Lancet Neurology",
        }
    }
    raw_payload = {
        "study_design": {"type": "prospective cohort study"},
        "population": {"mci_only": True, "n_total": 1131},
        "intervention": {"type": "blood immunoassay for p-tau181"},
        "outcomes": {"cognition": [{"name": "plasma p-tau181"}]},
        "eligibility_flags": {"include_for_mci_mct_review": True},
        "extraction_quality": {"missing_fields": ["study_design.duration_weeks"]},
    }
    paper_context = {
        "title": "Blood phosphorylated tau 181 as a biomarker for Alzheimer's disease: a diagnostic performance and prediction modelling study using data from four prospective cohorts",
        "summary": (
            "We aimed to assess whether blood p-tau181 could be used as a biomarker for Alzheimer's disease "
            "and for prediction of cognitive decline and hippocampal atrophy over a period of 1 year."
        ),
        "methods_snippet": "The findings were evaluated in four clinic-based prospective cohorts without an intervention arm.",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.study_design.design == "observational"
    assert validated.study_design.duration_weeks == 52
    assert validated.population.mci_only is False
    assert validated.outcomes.cognition[0].name == "Blood p-tau181 diagnostic performance and prediction modelling"
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_uses_longitudinal_cognitive_decline_title_for_prognostic_article() -> None:
    gold_payload = {
        "citation": {
            "title": "Prediction of Longitudinal Cognitive Decline in Preclinical Alzheimer Disease Using Plasma Biomarkers",
            "authors_first": "Mattsson-Carlgren",
            "year": 2023,
            "journal_or_server": "JAMA Neurology",
        }
    }
    raw_payload = {
        "study_design": {"type": "prospective population-based prognostic study"},
        "population": {"mci_only": False, "n_total": 171},
        "intervention": {"product_name": None},
        "outcomes": {"cognition": [{"name": "Mini-Mental State Examination (MMSE)"}]},
        "eligibility_flags": {"include_for_mci_mct_review": False},
        "extraction_quality": {"missing_fields": ["intervention"]},
    }
    paper_context = {
        "title": "Prediction of Longitudinal Cognitive Decline in Preclinical Alzheimer Disease Using Plasma Biomarkers",
        "summary": (
            "To evaluate combinations of different plasma biomarkers for predicting cognitive decline in "
            "Aβ-positive cognitively unimpaired individuals. Of those, 171 Aβ-positive participants were included "
            "in the main analyses."
        ),
        "methods_snippet": (
            "The primary outcome was longitudinal measures of cognition over a median of 6 years "
            "in a prospective prognostic cohort without an intervention arm."
        ),
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.study_design.design == "observational"
    assert validated.population.n_total == 171
    assert validated.study_design.duration_weeks == 312
    assert validated.outcomes.cognition[0].name == "Longitudinal cognitive decline"
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_handles_head_to_head_blood_test_article() -> None:
    gold_payload = {
        "citation": {
            "title": "Head-to-head comparison of leading blood tests for Alzheimer's disease pathology",
            "authors_first": "Schindler",
            "year": 2024,
            "journal_or_server": "Alzheimer's & Dementia",
        }
    }
    raw_payload = {
        "study_design": {"type": "observational", "duration_weeks": 52},
        "population": {"mci_only": False, "n_total": 1000},
        "intervention": {"product_name": None},
        "comparator": {"description": "plasma biomarkers"},
        "outcomes": {"cognition": [{"name": "amyloid and tau positivity"}]},
        "eligibility_flags": {"include_for_mci_mct_review": False},
        "extraction_quality": {"missing_fields": ["population.n_total"]},
    }
    paper_context = {
        "title": "Head-to-head comparison of leading blood tests for Alzheimer's disease pathology",
        "summary": (
            "This study compared leading commercial blood tests for amyloid pathology and other AD-related outcomes."
        ),
        "methods_snippet": (
            "Based on these selection criteria, 393 ADNI participants had at least six plasma aliquots. "
            "Participants were selected for inclusion who had plasma samples collected within 6 months of an amyloid PET scan."
        ),
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.study_design.design == "observational"
    assert validated.study_design.duration_weeks == 0
    assert validated.population.n_total == 393
    assert validated.outcomes.cognition[0].name == "Alzheimer's disease pathology test performance"
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_handles_preclinical_scfa_article() -> None:
    gold_payload = {
        "citation": {
            "title": "Microbiota-derived short chain fatty acids modulate microglia and promote Ab plaque deposition",
            "authors_first": "Colombo",
            "year": 2021,
            "journal_or_server": "eLife",
        }
    }
    raw_payload = {
        "study_design": {"type": "preclinical experimental study"},
        "population": {"mci_only": False},
        "intervention": {"product_name": "SCFA"},
        "outcomes": {"cognition": [{"name": "Ab plaque deposition"}]},
        "eligibility_flags": {"include_for_mci_mct_review": False},
        "extraction_quality": {"missing_fields": ["population.n_total", "study_design.duration_weeks"]},
    }
    paper_context = {
        "title": "Microbiota-derived short chain fatty acids modulate microglia and promote Ab plaque deposition",
        "summary": (
            "We identify microbiota-derived short chain fatty acids as microbial metabolites which promote Ab deposition."
        ),
        "methods_snippet": "SCFA supplementation to germ-free AD mice increased plaque load.",
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.population.mci_only is False
    assert validated.intervention.product_name is None
    assert validated.outcomes.cognition[0].name == "Amyloid-beta plaque deposition"
    assert validated.eligibility_flags.include_for_mci_mct_review is False


def test_repair_prediction_payload_handles_preclinical_therapeutic_gene_editing_article() -> None:
    gold_payload = {
        "citation": {
            "title": "Glia-to-Neuron Conversion by CRISPR-CasRx Alleviates Symptoms of Neurological Disease in Mice",
            "authors_first": "Zhou",
            "year": 2020,
            "journal_or_server": "Cell",
        }
    }
    raw_payload = {
        "study_design": {"type": "preclinical therapeutic study"},
        "population": {"mci_only": True},
        "intervention": {"product_name": "Ptbp1 knockdown"},
        "outcomes": {"cognition": [{"name": "Visual responses"}]},
        "eligibility_flags": {"include_for_mci_mct_review": True},
        "extraction_quality": {"missing_fields": ["study_design.duration_weeks", "comparator.product_name"]},
    }
    paper_context = {
        "title": "Glia-to-Neuron Conversion by CRISPR-CasRx Alleviates Symptoms of Neurological Disease in Mice",
        "summary": (
            "In vivo CasRx-mediated downregulation of Ptbp1 locally converts glia to neurons and shows promise "
            "for treating disorders due to neuronal loss in mice."
        ),
        "methods_snippet": (
            "Knockdown of Ptbp1 converts Muller glia into retinal ganglion cells and induced neurons alleviated "
            "motor dysfunctions in PD model mice."
        ),
    }

    repaired = _repair_prediction_payload(raw_payload, gold_payload, "paper-1", paper_context=paper_context)
    validated = SpecialtyTrialExtraction.model_validate(repaired)

    assert validated.study_design.design == "other"
    assert validated.population.mci_only is False
    assert validated.intervention.product_name == "CasRx-mediated Ptbp1 knockdown"
    assert validated.outcomes.cognition[0].name == "Neurological disease symptom alleviation"
    assert validated.eligibility_flags.include_for_mci_mct_review is False
