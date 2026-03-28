from src.obsidian import get_template_trial
from src.schemas.core import BiomedicalClinicalExtraction, TrialExtraction


def _base_paper() -> dict:
    return {
        "title": "Clinical Trial X",
        "link": "https://example.org/paper",
        "slot": "clinical",
        "doi": "10.1000/x",
        "reading_status": "Inbox",
        "hard_tags": {"design": "rct"},
        "soft_tags": ["#mci"],
        "confidence": 0.85,
        "ai_summary": "summary",
        "feedback_json": '{"links":{"institutional_proxy_url":"https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/x"}}',
        "local_pdf_path": None,
    }


def test_template_trial_includes_institutional_block_when_pdf_missing():
    paper = _base_paper()
    md = get_template_trial(paper, extraction=None)
    assert "Institutional Access Available" in md
    assert "Download via KNU Libproxy" in md
    assert "Clinical Workspace Lane" in md
    assert "Clinical Extraction Pending" in md


def test_template_trial_omits_institutional_block_when_local_pdf_exists():
    paper = _base_paper()
    paper["local_pdf_path"] = "/tmp/already.pdf"
    md = get_template_trial(paper, extraction=None)
    assert "Institutional Access Available" not in md


def test_template_trial_uses_specialty_lane_for_trial_extraction():
    paper = _base_paper()
    extraction = TrialExtraction(
        paper_id="paper-1",
        citation={
            "title": "Clinical Trial X",
            "authors_first": "Kim",
            "year": 2026,
            "journal_or_server": "Test Journal",
            "doi": None,
            "url": None,
        },
    )

    md = get_template_trial(paper, extraction=extraction)

    assert "Specialty Extraction Lane" in md
    assert "Clinical Workspace Lane" not in md


def test_template_trial_uses_generic_lane_for_biomedical_clinical_extraction():
    paper = _base_paper()
    extraction = BiomedicalClinicalExtraction(
        paper_id="paper-2",
        citation={
            "title": "Clinical Trial X",
            "authors_first": "Lee",
            "year": 2026,
            "journal_or_server": "Test Journal",
            "doi": None,
            "url": None,
        },
        population={
            "condition": "Metastatic non-small cell lung cancer",
            "n_total": 88,
        },
        intervention={
            "category": "small_molecule",
            "name": "Targeted therapy",
        },
        outcomes={
            "primary": [
                {
                    "name": "Progression-free survival",
                    "domain": "primary",
                }
            ]
        },
    )

    md = get_template_trial(paper, extraction=extraction)

    assert "Clinical Workspace Lane" in md
    assert "Clinical Snapshot" in md
    assert "Metastatic non-small cell lung cancer" in md


def test_template_trial_shows_structured_escalation_metadata_for_fast_lane_approval():
    paper = _base_paper()
    paper["processing_status"] = "APPROVED"
    paper["is_escalated"] = True
    paper["escalation_reason"] = "Authoritative biomedical guidance is explicit; safe to auto-approve."
    paper["escalation_final_route"] = "FAST_LANE_APPROVE"
    paper["escalation_in_biomedical_scope"] = True
    paper["escalation_reason_codes"] = ["FASTLANE_GUIDANCE"]

    md = get_template_trial(paper, extraction=None)

    assert "Fast-Lane Approved (Escalation Judge)" in md
    assert "**Final Route**: FAST_LANE_APPROVE" in md
    assert "**Biomedical Scope**: In biomedical scope" in md
    assert "**Reason Codes**: FASTLANE_GUIDANCE" in md


def test_template_trial_shows_structured_escalation_metadata_for_pending_review():
    paper = _base_paper()
    paper["processing_status"] = "PENDING_REVIEW"
    paper["escalation_final_route"] = "QUEUE_HUMAN_REVIEW"
    paper["escalation_in_biomedical_scope"] = True
    paper["escalation_reason_codes"] = ["MODEL_REVIEW_REQUIRED"]

    md = get_template_trial(paper, extraction=None)

    assert "Requires Human Review" in md
    assert "**Final Route**: QUEUE_HUMAN_REVIEW" in md
    assert "**Reason Codes**: MODEL_REVIEW_REQUIRED" in md
