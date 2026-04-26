import json
from pathlib import Path
from types import SimpleNamespace

import src.watcher as watcher
from src.schemas import Paper


def _make_config(base_dir: Path):
    return SimpleNamespace(
        llm=SimpleNamespace(),
        entity_aliases={},
        paths=SimpleNamespace(
            export_dir=base_dir / "export",
            upload_dir=base_dir / "uploads",
        ),
    )


def test_watcher_process_local_pdf_persists_clear_issues_state(monkeypatch, tmp_path):
    config = _make_config(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    paper = Paper(
        id="10.1000/watcher-clear",
        doi="10.1000/watcher-clear",
        title="Watcher Clear Paper",
        authors=["A"],
        published="2026-03-13",
        source="pubmed",
        summary="summary",
        link="https://example.org/paper",
    )

    class FakeLLM:
        def tag_paper(self, _payload):
            return {"soft_tags": ["#clear"], "confidence": 0.95}

        def classify_slot(self, _payload, slot):
            return slot

        def get_tagging_metrics(self):
            return {"adjudication_triggered": True, "adjudication_reason": "low_confidence"}

        def get_slot_classification_metrics(self):
            return {"adjudication_triggered": False, "adjudication_reason": None}

    saved_calls = []
    monkeypatch.setattr(watcher, "extract_doi_from_pdf", lambda _path: "10.1000/watcher-clear")
    monkeypatch.setattr(watcher, "fetch_pubmed", lambda *_a, **_k: [paper])
    monkeypatch.setattr(watcher, "get_llm_provider", lambda *_a, **_k: FakeLLM())
    monkeypatch.setattr(watcher, "save_paper_to_obsidian", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "export_to_ris", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    row = watcher.process_local_pdf(pdf_path, config)

    assert row["processing_status"].value == "APPROVED"
    assert row["pdf_status"] == "downloaded"
    payload = json.loads(row["feedback_json"])
    assert payload["intake_override_log"]["producer"] == "watcher_local_pdf"
    assert payload["intake_override_log"]["analysis_available"] is True
    assert payload["intake_override_log"]["issues_state"] == "clear"
    assert payload["intake_override_log"]["llm_slot_classification_used"] is True
    assert payload["intake_override_log"]["llm_tagging_adjudication_used"] is True
    assert payload["intake_override_log"]["llm_tagging_adjudication_reason"] == "low_confidence"
    assert payload["intake_override_log"]["llm_slot_adjudication_used"] is False
    assert len(saved_calls) == 1
    assert saved_calls[0][1]["pdf_status"] == "downloaded"
    assert saved_calls[0][1]["issues_state"] == "clear"
    assert saved_calls[0][1]["status"] == "APPROVED"
    assert json.loads(saved_calls[0][1]["feedback_json"])["intake_override_log"]["processing_status"] == "APPROVED"


def test_watcher_process_local_pdf_persists_unavailable_issues_state_without_llm(monkeypatch, tmp_path):
    config = _make_config(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    paper = Paper(
        id="10.1000/watcher-unavailable",
        doi="10.1000/watcher-unavailable",
        title="Watcher Unavailable Paper",
        authors=["A"],
        published="2026-03-13",
        source="pubmed",
        summary="summary",
        link="https://example.org/paper",
    )

    saved_calls = []
    monkeypatch.setattr(watcher, "extract_doi_from_pdf", lambda _path: "10.1000/watcher-unavailable")
    monkeypatch.setattr(watcher, "fetch_pubmed", lambda *_a, **_k: [paper])
    monkeypatch.setattr(watcher, "get_llm_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "save_paper_to_obsidian", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "export_to_ris", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    row = watcher.process_local_pdf(pdf_path, config)

    assert row["processing_status"].value == "PENDING_REVIEW"
    assert row["pdf_status"] == "downloaded"
    payload = json.loads(row["feedback_json"])
    assert payload["intake_override_log"]["analysis_available"] is False
    assert payload["intake_override_log"]["stored_slot"] == "manual"
    assert payload["intake_override_log"]["slot_changed"] is False
    assert len(saved_calls) == 1
    assert saved_calls[0][1]["pdf_status"] == "downloaded"
    assert saved_calls[0][1]["issues_state"] == "unavailable"
    assert saved_calls[0][1]["status"] == "PENDING_REVIEW"
    assert json.loads(saved_calls[0][1]["feedback_json"])["intake_override_log"]["issues_state"] == "unavailable"


def test_watcher_process_local_pdf_falls_back_to_local_metadata_when_lookup_missing(monkeypatch, tmp_path):
    config = _make_config(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    fallback_paper = Paper(
        id="local--123",
        doi=None,
        title="Local Fallback Paper",
        authors=[],
        published="2026-03-13",
        source="local_pdf",
        summary="",
        link=f"file://{pdf_path}",
    )

    saved_calls = []
    monkeypatch.setattr(watcher, "extract_doi_from_pdf", lambda _path: None)
    monkeypatch.setattr(watcher, "fetch_pubmed", lambda *_a, **_k: [])
    monkeypatch.setattr(watcher, "processor_process_local_pdf", lambda _path, config=None: fallback_paper)
    monkeypatch.setattr(watcher, "get_llm_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "save_paper_to_obsidian", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "export_to_ris", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    row = watcher.process_local_pdf(pdf_path, config)

    assert row["paper_id"] == "local--123"
    assert row["doi"] == ""
    assert row["pdf_status"] == "downloaded"
    assert row["processing_status"].value == "PENDING_REVIEW"
    assert len(saved_calls) == 1
    assert saved_calls[0][0][0] == "local--123"
    assert saved_calls[0][1]["doi"] is None
    assert saved_calls[0][1]["pdf_status"] == "downloaded"


def test_watcher_process_local_pdf_skips_same_file_upload_copy(monkeypatch, tmp_path):
    config = _make_config(tmp_path)
    config.paths.upload_dir = tmp_path
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    paper = Paper(
        id="10.1000/watcher-same-file",
        doi="10.1000/watcher-same-file",
        title="Watcher Same File Paper",
        authors=["A"],
        published="2026-03-13",
        source="pubmed",
        summary="summary",
        link="https://example.org/paper",
    )

    monkeypatch.setattr(watcher, "extract_doi_from_pdf", lambda _path: "10.1000/watcher-same-file")
    monkeypatch.setattr(watcher, "fetch_pubmed", lambda *_a, **_k: [paper])
    monkeypatch.setattr(watcher, "get_llm_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "save_paper_to_obsidian", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "export_to_ris", lambda *_a, **_k: None)
    monkeypatch.setattr(watcher, "save_paper_state", lambda *args, **kwargs: None)

    row = watcher.process_local_pdf(pdf_path, config)

    assert row["pdf_path"] == str(pdf_path)
    assert pdf_path.exists()
