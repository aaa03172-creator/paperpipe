import json
from types import SimpleNamespace

import src.processor as processor
from src.schemas.core import BiomedicalClinicalExtraction


def test_process_daily_slots_injects_institutional_proxy_when_pdf_missing(monkeypatch):
    fake_paper = SimpleNamespace(
        id="p_inst_001",
        doi="10.1000/inst001",
        title="Institutional Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/paper",
        local_pdf_path=None,
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="memory")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(slots={"mechanism": fake_slot}),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        def fetch(self, query, max_results=5):
            return [fake_paper]

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    saved_calls = []
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    rows = processor.process_daily_slots(ignore_db=True)
    assert len(rows) == 1
    row = rows[0]
    assert row["pdf_path"] is None
    assert "feedback_json" in row
    assert "institutional_proxy_url" in row["feedback_json"]
    assert "libproxy.knu.ac.kr" in row["feedback_json"]
    payload = json.loads(row["feedback_json"])
    assert payload["intake_override_log"]["producer"] == "processor_daily_slots"
    assert payload["intake_override_log"]["analysis_available"] is False
    assert payload["intake_override_log"]["issues_state"] == "unavailable"
    assert payload["intake_override_log"]["stored_slot"] == "mechanism"
    assert payload["intake_override_log"]["slot_changed"] is False
    assert len(saved_calls) == 1
    assert "download_attempts" in saved_calls[0][1]
    assert saved_calls[0][1]["download_attempts"] == []
    assert saved_calls[0][1]["issues_state"] == "unavailable"


def test_process_daily_slots_records_slot_override_logging(monkeypatch):
    fake_paper = SimpleNamespace(
        id="p_override_001",
        doi="10.1000/override001",
        title="Override Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/paper",
        local_pdf_path="/tmp/p_override_001.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="memory")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(slots={"mechanism": fake_slot}),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=True))),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        def fetch(self, query, max_results=5):
            return [fake_paper]

    class FakeLLM:
        def is_available(self):
            return True

        def tag_paper(self, _payload):
            return {"soft_tags": ["#flagged"], "confidence": 0.74}

        def classify_slot(self, _payload, _slot):
            return "clinical"

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: FakeLLM())
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    saved_calls = []
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    payload = json.loads(rows[0]["feedback_json"])
    assert payload["intake_override_log"]["input_slot"] == "mechanism"
    assert payload["intake_override_log"]["stored_slot"] == "clinical"
    assert payload["intake_override_log"]["slot_changed"] is True
    assert payload["intake_override_log"]["input_tags"] == ["#flagged"]
    assert payload["intake_override_log"]["stored_tags"] == ["#flagged"]
    assert payload["intake_override_log"]["tags_changed"] is False
    assert payload["intake_override_log"]["processing_status"] == "PENDING_REVIEW"
    assert payload["intake_override_log"]["issues_state"] == "flagged"
    assert payload["intake_override_log"]["llm_slot_classification_used"] is True
    assert len(saved_calls) == 1
    assert json.loads(saved_calls[0][1]["feedback_json"])["intake_override_log"]["slot_changed"] is True


def test_process_daily_slots_persists_flagged_issues_state_when_analysis_requires_review(monkeypatch):
    fake_paper = SimpleNamespace(
        id="p_flagged_001",
        doi="10.1000/flagged001",
        title="Flagged Producer Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/paper",
        local_pdf_path="/tmp/p_flagged_001.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="memory")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(slots={"mechanism": fake_slot}),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        def fetch(self, query, max_results=5):
            return [fake_paper]

    class FakeLLM:
        def is_available(self):
            return True

        def tag_paper(self, _payload):
            return {"soft_tags": ["#flagged"], "confidence": 0.74}

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: FakeLLM())
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    saved_calls = []
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    assert rows[0]["processing_status"].value == "PENDING_REVIEW"
    assert len(saved_calls) == 1
    assert saved_calls[0][1]["issues_state"] == "flagged"


def test_process_daily_slots_persists_generic_clinical_extraction_when_enabled(monkeypatch):
    fake_paper = SimpleNamespace(
        id="p_clinical_001",
        doi="10.1000/clinical001",
        title="Clinical Producer Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="Human trial in oncology.",
        link="https://publisher.example/clinical-paper",
        local_pdf_path="/tmp/p_clinical_001.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="oncology")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(slots={"clinical": fake_slot}),
        llm=SimpleNamespace(
            features=SimpleNamespace(
                slot_classification=SimpleNamespace(enabled=False),
                specialty_trial_extraction=SimpleNamespace(enabled=True),
            )
        ),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        def fetch(self, query, max_results=5):
            return [fake_paper]

    class FakeLLM:
        def is_available(self):
            return True

        def tag_paper(self, _payload):
            return {"soft_tags": ["#oncology"], "confidence": 0.95}

        def extract_biomedical_clinical_data(self, _payload):
            return BiomedicalClinicalExtraction(
                paper_id="p_clinical_001",
                citation={
                    "title": "Clinical Producer Paper",
                    "authors_first": "Kim",
                    "year": 2026,
                    "journal_or_server": "Test Journal",
                    "doi": None,
                    "url": None,
                },
                population={
                    "condition": "Metastatic non-small cell lung cancer",
                    "n_total": 72,
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

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: FakeLLM())
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    obsidian_calls = []
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *args, **kwargs: obsidian_calls.append((args, kwargs)))
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    saved_calls = []
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    assert rows[0]["clinical_data"]["population"]["condition"] == "Metastatic non-small cell lung cancer"
    payload = json.loads(rows[0]["feedback_json"])
    assert payload["clinical_data"]["population"]["condition"] == "Metastatic non-small cell lung cancer"
    assert len(obsidian_calls) == 1
    assert isinstance(obsidian_calls[0][1]["extraction"], BiomedicalClinicalExtraction)
    assert len(saved_calls) == 1
    saved_payload = json.loads(saved_calls[0][1]["feedback_json"])
    assert saved_payload["clinical_data"]["intervention"]["name"] == "Targeted therapy"
