from pathlib import Path

from src.exporter import export_paper_to_markdown


def _sample_paper():
    return {
        "paper_id": "paper_001",
        "title": "Sample Paper",
        "summary": "Short summary",
        "status": "APPROVED",
        "confidence": 0.91,
        "pdf_path": None,
        "feedback_json": '{"hard_tags":{"study_type":"Review","design":"Consensus"},"soft_tags":["#A/B"],"evidence_span":"evidence"}',
    }


def _exported_target(vault_path: Path, paper: dict) -> Path:
    return vault_path / str(paper["obsidian_path"])


def test_exporter_writes_markdown_file(tmp_path):
    paper = _sample_paper()
    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True
    target = _exported_target(tmp_path, paper)
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "Sample Paper" in content
    assert "A/B" in content
    assert "Consensus" in content


def test_exporter_humanizes_deterministic_design_values_and_falls_back_to_study_type(tmp_path):
    paper = _sample_paper()
    paper["feedback_json"] = (
        '{"hard_tags":{"study_type":"Preclinical Study","design":"parallel_rct"},"soft_tags":["#A/B"],"evidence_span":"evidence"}'
    )

    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    target = _exported_target(tmp_path, paper)
    content = target.read_text(encoding="utf-8")
    assert "Parallel RCT" in content
    assert "parallel_rct" not in content

    paper["feedback_json"] = (
        '{"hard_tags":{"study_type":"Preclinical Study","design":null},"soft_tags":["#A/B"],"evidence_span":"evidence"}'
    )
    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    content = target.read_text(encoding="utf-8")
    assert "Preclinical Study" in content


def test_exporter_skips_when_exists_and_no_overwrite(tmp_path):
    target = tmp_path / "Inbox" / "PaperPipe"
    target.mkdir(parents=True, exist_ok=True)
    f = target / "Sample Paper.md"
    f.write_text("old", encoding="utf-8")

    paper = _sample_paper()
    ok = export_paper_to_markdown(paper, tmp_path, overwrite=False)
    assert ok is False
    assert f.read_text(encoding="utf-8") == "old"


def test_exporter_includes_zotero_and_pdf_deep_links(tmp_path):
    attachments = tmp_path / "attachments"
    attachments.mkdir(parents=True, exist_ok=True)
    pdf_file = attachments / "paper.pdf"
    pdf_file.write_text("pdf", encoding="utf-8")

    paper = _sample_paper()
    paper["zotero_key"] = "ABCD1234"
    paper["pdf_path"] = str(pdf_file)
    paper["page"] = 3

    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    target = _exported_target(tmp_path, paper)
    content = target.read_text(encoding="utf-8")

    assert "zotero://select/library/items/ABCD1234" in content
    assert "zotero://open-pdf/library/items/ABCD1234?page=3" in content
    assert "[[attachments/paper.pdf]]" in content


def test_exporter_omits_link_sections_when_values_missing(tmp_path):
    paper = _sample_paper()
    paper.pop("pdf_path", None)
    paper.pop("zotero_key", None)
    paper.pop("page", None)

    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    target = _exported_target(tmp_path, paper)
    content = target.read_text(encoding="utf-8")
    assert "zotero://select/library/items/" not in content
    assert "zotero://open-pdf/library/items/" not in content
    assert "file://" not in content


def test_exporter_includes_institutional_link_block_for_manual_required(tmp_path):
    paper = _sample_paper()
    paper["pdf_status"] = "manual_required"
    paper["doi"] = "10.1000/inst.test"
    paper["feedback_json"] = (
        '{"links":{"institutional_proxy_url":"https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/inst.test"}}'
    )

    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    target = _exported_target(tmp_path, paper)
    content = target.read_text(encoding="utf-8")
    assert "## Download (Institutional)" in content
    assert "Institutional Link" in content
    assert "Login once, download PDF, it will be auto-collected." in content


def test_exporter_includes_missing_pdf_block_when_pdf_unavailable(tmp_path):
    paper = _sample_paper()
    paper["pdf_status"] = "missing"
    paper["feedback_json"] = "{}"

    ok = export_paper_to_markdown(paper, tmp_path, overwrite=True)
    assert ok is True

    target = _exported_target(tmp_path, paper)
    content = target.read_text(encoding="utf-8")
    assert "## PDF Status" in content
    assert "PDF is currently unavailable." in content
    assert "No institutional access link is stored for this paper yet." in content
