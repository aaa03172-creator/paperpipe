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


def test_exporter_writes_markdown_file(tmp_path):
    ok = export_paper_to_markdown(_sample_paper(), tmp_path, overwrite=True)
    assert ok is True
    target = tmp_path / "Inbox" / "PaperPipe" / "paper_001.md"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "Sample Paper" in content
    assert "A/B" in content
    assert "Consensus" in content


def test_exporter_skips_when_exists_and_no_overwrite(tmp_path):
    target = tmp_path / "Inbox" / "PaperPipe"
    target.mkdir(parents=True, exist_ok=True)
    f = target / "paper_001.md"
    f.write_text("old", encoding="utf-8")

    ok = export_paper_to_markdown(_sample_paper(), tmp_path, overwrite=False)
    assert ok is False
    assert f.read_text(encoding="utf-8") == "old"
