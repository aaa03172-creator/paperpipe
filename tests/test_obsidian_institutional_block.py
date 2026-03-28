from src.obsidian import get_template_trial


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
    assert "Specialty Extraction Lane" in md


def test_template_trial_omits_institutional_block_when_local_pdf_exists():
    paper = _base_paper()
    paper["local_pdf_path"] = "/tmp/already.pdf"
    md = get_template_trial(paper, extraction=None)
    assert "Institutional Access Available" not in md


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
