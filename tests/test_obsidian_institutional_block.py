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
