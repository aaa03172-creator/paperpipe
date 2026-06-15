import json
import logging
from pathlib import Path
from types import SimpleNamespace

import src.processor as processor
from src.schemas.core import BiomedicalClinicalExtraction, PaperTagging


def test_process_daily_slots_logs_output_failures(monkeypatch, caplog):
    fake_paper = SimpleNamespace(
        id="p_output_failure_001",
        doi="10.1000/output-failure",
        title="Output Failure Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/output-failure",
        local_pdf_path="/tmp/output-failure.pdf",
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
    monkeypatch.setattr(
        processor,
        "save_paper_to_obsidian",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("obsidian boom")),
    )
    monkeypatch.setattr(
        processor,
        "export_to_ris",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("ris boom")),
    )
    monkeypatch.setattr(
        processor,
        "save_paper_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db boom")),
    )

    with caplog.at_level(logging.WARNING, logger="src.processor"):
        rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Failed to save Obsidian note for p_output_failure_001" in messages
    assert "Failed to export RIS for p_output_failure_001" in messages
    assert "Failed to save paper state for p_output_failure_001" in messages


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
        system=SimpleNamespace(institutional_proxy_url="https://configured.proxy/_Lib_Proxy_Url/"),
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
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    saved_calls = []
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    rows = processor.process_daily_slots(ignore_db=True)
    assert len(rows) == 1
    row = rows[0]
    assert row["pdf_path"] is None
    assert row["pdf_status"] == "manual_required"
    assert "feedback_json" in row
    assert "institutional_proxy_url" in row["feedback_json"]
    assert "configured.proxy" in row["feedback_json"]
    payload = json.loads(row["feedback_json"])
    assert PaperTagging.model_validate(payload)
    assert payload["confidence"] == 0.0
    assert payload["soft_tags"] == []
    assert payload["hard_tags"] == {}
    assert payload["intake_override_log"]["producer"] == "processor_daily_slots"
    assert payload["intake_override_log"]["analysis_available"] is False
    assert payload["intake_override_log"]["issues_state"] == "unavailable"
    assert payload["intake_override_log"]["stored_slot"] == "mechanism"
    assert payload["intake_override_log"]["slot_changed"] is False
    assert len(saved_calls) == 1
    assert "download_attempts" in saved_calls[0][1]
    assert saved_calls[0][1]["download_attempts"] == []
    assert saved_calls[0][1]["pdf_status"] == "manual_required"
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

        def get_tagging_metrics(self):
            return {"adjudication_triggered": True, "adjudication_reason": "schema_invalid"}

        def get_slot_classification_metrics(self):
            return {"adjudication_triggered": True, "adjudication_reason": "signal_conflict"}

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
    assert PaperTagging.model_validate(payload)
    assert payload["confidence"] == 0.74
    assert payload["soft_tags"] == ["#flagged"]
    assert payload["hard_tags"] == {}
    assert payload["intake_override_log"]["input_slot"] == "mechanism"
    assert payload["intake_override_log"]["stored_slot"] == "clinical"
    assert payload["intake_override_log"]["slot_changed"] is True
    assert payload["intake_override_log"]["input_tags"] == ["#flagged"]
    assert payload["intake_override_log"]["stored_tags"] == ["#flagged"]
    assert payload["intake_override_log"]["tags_changed"] is False
    assert payload["intake_override_log"]["processing_status"] == "PENDING_REVIEW"
    assert payload["intake_override_log"]["issues_state"] == "flagged"
    assert payload["intake_override_log"]["llm_slot_classification_used"] is True
    assert payload["intake_override_log"]["llm_tagging_adjudication_used"] is True
    assert payload["intake_override_log"]["llm_tagging_adjudication_reason"] == "schema_invalid"
    assert payload["intake_override_log"]["llm_slot_adjudication_used"] is True
    assert payload["intake_override_log"]["llm_slot_adjudication_reason"] == "signal_conflict"
    assert len(saved_calls) == 1
    assert json.loads(saved_calls[0][1]["feedback_json"])["intake_override_log"]["slot_changed"] is True


def test_process_daily_slots_logs_slot_classification_failure(monkeypatch, caplog):
    fake_paper = SimpleNamespace(
        id="p_slot_failure_001",
        doi="10.1000/slot-failure",
        title="Slot Failure Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/paper",
        local_pdf_path="/tmp/p_slot_failure_001.pdf",
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
            raise RuntimeError("classifier boom")

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: FakeLLM())
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *_args, **_kwargs: None)

    with caplog.at_level(logging.WARNING, logger="src.processor"):
        rows = processor.process_daily_slots(ignore_db=True)

    assert rows[0]["slot"] == "mechanism"
    assert "Slot classification failed for p_slot_failure_001" in caplog.text


def test_process_daily_slots_logs_gate_feedback_parse_failure(monkeypatch, caplog):
    fake_paper = SimpleNamespace(
        id="p_gate_json_failure_001",
        doi="10.1000/gate-json-failure",
        title="Gate JSON Failure Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/paper",
        local_pdf_path="/tmp/p_gate_json_failure_001.pdf",
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
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        processor,
        "_feedback_json_from_tagging",
        lambda *_args, **_kwargs: "{not valid json",
    )

    with caplog.at_level(logging.WARNING, logger="src.processor"):
        rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    assert "Failed to parse feedback_json for daily slot gate evaluation on p_gate_json_failure_001" in caplog.text
    assert "Failed to parse feedback_json payload during merge" in caplog.text


def test_process_daily_slots_keeps_non_doi_identifier_out_of_doi_field(monkeypatch):
    fake_paper = SimpleNamespace(
        id="PMID:12345",
        doi=None,
        title="PubMed Only Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/paper",
        local_pdf_path="/tmp/pubmed-only.pdf",
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

    exported_rows = []
    saved_calls = []
    ris_path = Path("export/2026-02-24_import.ris")
    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda row, *_args, **_kwargs: exported_rows.append(row) or ris_path)
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: saved_calls.append((args, kwargs)))

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    row = rows[0]
    assert row["paper_id"] == "PMID:12345"
    assert row["doi"] == ""
    assert row["pdf_status"] == "downloaded"
    assert exported_rows[0]["doi"] == ""
    assert saved_calls[0][0][0] == "PMID:12345"
    assert saved_calls[0][1]["doi"] is None
    assert saved_calls[0][1]["pdf_status"] == "downloaded"
    assert saved_calls[0][1]["ris_path"] == ris_path


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


def test_process_daily_slots_checks_retraction_when_enabled(monkeypatch):
    fake_paper = SimpleNamespace(
        id="p_retracted_001",
        doi="10.1000/retracted",
        title="Retracted Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="s",
        link="https://publisher.example/retracted",
        local_pdf_path="/tmp/p_retracted_001.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="memory")
    fake_config = SimpleNamespace(
        system=SimpleNamespace(check_retraction_on_ingest=True, unpaywall_email="ops@example.test"),
        search=SimpleNamespace(slots={"mechanism": fake_slot}),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        def fetch(self, query, max_results=5):
            return [fake_paper]

    retraction_calls = []
    marked_retracted = []

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(processor, "mark_as_retracted", lambda identifier: marked_retracted.append(identifier) or True)
    monkeypatch.setattr(
        processor,
        "check_retraction",
        lambda doi, email=None: retraction_calls.append((doi, email))
        or {"is_retracted": True, "retraction_details": "Retraction Watch: IS_RETRACTED"},
    )

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    row = rows[0]
    assert retraction_calls == [("10.1000/retracted", "ops@example.test")]
    assert marked_retracted == ["p_retracted_001"]
    assert row["processing_status"].value == "QUARANTINED"
    assert row["gate_decision"] == "QUARANTINED"
    assert "RETRACTED" in row["gate_reason"]
    assert row["retraction_check"]["is_retracted"] is True
    payload = json.loads(row["feedback_json"])
    assert payload["retraction_check"]["retraction_details"] == "Retraction Watch: IS_RETRACTED"


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
    assert rows[0]["processing_status"].value == "PENDING_REVIEW"
    assert rows[0]["clinical_data"]["population"]["condition"] == "Metastatic non-small cell lung cancer"
    payload = json.loads(rows[0]["feedback_json"])
    assert payload["gate_decision"] == "PENDING_REVIEW"
    assert "EVIDENCE_MISSING" in payload["gate_reason"]
    assert payload["clinical_data"]["population"]["condition"] == "Metastatic non-small cell lung cancer"
    assert len(obsidian_calls) == 1
    assert isinstance(obsidian_calls[0][1]["extraction"], BiomedicalClinicalExtraction)
    assert len(saved_calls) == 1
    saved_payload = json.loads(saved_calls[0][1]["feedback_json"])
    assert saved_payload["clinical_data"]["intervention"]["name"] == "Targeted therapy"


def test_process_daily_slots_persists_structured_escalation_metadata_when_fast_lane_approved(monkeypatch):
    fake_paper = SimpleNamespace(
        id="p_escalate_approve_001",
        doi="10.1000/escalate-approve",
        title="Escalation Approve Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="Guideline paper",
        link="https://publisher.example/escalation-approve",
        local_pdf_path="/tmp/p_escalate_approve_001.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="oncology")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(slots={"clinical": fake_slot}),
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
            return {"soft_tags": ["#oncology"], "confidence": 0.74}

        def evaluate_escalation(self, _payload):
            return {
                "approved": True,
                "reason": "Authoritative biomedical guidance is explicit; safe to auto-approve.",
                "final_route": "FAST_LANE_APPROVE",
                "in_biomedical_scope": True,
                "reason_codes": ["FASTLANE_GUIDANCE"],
            }

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
    row = rows[0]
    assert row["processing_status"].value == "APPROVED"
    assert row["is_escalated"] is True
    assert row["escalation_final_route"] == "FAST_LANE_APPROVE"
    assert row["escalation_in_biomedical_scope"] is True
    assert row["escalation_reason_codes"] == ["FASTLANE_GUIDANCE"]
    payload = json.loads(row["feedback_json"])
    assert payload["escalation"]["approved"] is True
    assert payload["escalation"]["final_route"] == "FAST_LANE_APPROVE"
    assert payload["escalation"]["reason_codes"] == ["FASTLANE_GUIDANCE"]
    assert len(saved_calls) == 1
    assert saved_calls[0][1]["issues_state"] == "clear"
    saved_payload = json.loads(saved_calls[0][1]["feedback_json"])
    assert saved_payload["escalation"]["approved"] is True


def test_process_daily_slots_persists_structured_escalation_metadata_when_review_remains_pending(monkeypatch):
    fake_paper = SimpleNamespace(
        id="p_escalate_pending_001",
        doi="10.1000/escalate-pending",
        title="Escalation Pending Paper",
        authors=["A"],
        published="2026-02-21",
        source="test",
        summary="Broad review paper",
        link="https://publisher.example/escalation-pending",
        local_pdf_path="/tmp/p_escalate_pending_001.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="biomaterials")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(slots={"clinical": fake_slot}),
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
            return {"soft_tags": ["#biomaterials"], "confidence": 0.74}

        def evaluate_escalation(self, _payload):
            return {
                "approved": False,
                "reason": "Interesting but uncertain from metadata alone.",
                "final_route": "QUEUE_HUMAN_REVIEW",
                "in_biomedical_scope": True,
                "reason_codes": ["MODEL_REVIEW_REQUIRED"],
            }

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
    row = rows[0]
    assert row["processing_status"].value == "PENDING_REVIEW"
    assert row["is_escalated"] is False
    assert row["escalation_final_route"] == "QUEUE_HUMAN_REVIEW"
    assert row["escalation_in_biomedical_scope"] is True
    assert row["escalation_reason_codes"] == ["MODEL_REVIEW_REQUIRED"]
    payload = json.loads(row["feedback_json"])
    assert payload["escalation"]["approved"] is False
    assert payload["escalation"]["final_route"] == "QUEUE_HUMAN_REVIEW"
    assert payload["escalation"]["reason_codes"] == ["MODEL_REVIEW_REQUIRED"]
    assert len(saved_calls) == 1
    assert saved_calls[0][1]["issues_state"] == "flagged"


def test_process_daily_slots_filters_fetchers_by_slot_source(monkeypatch):
    pubmed_paper = SimpleNamespace(
        id="pmid:source-filter",
        doi="10.1000/source-filter",
        title="PubMed Candidate",
        authors=["A"],
        published="2026-02-21",
        source="PubMed",
        summary="s",
        link="https://pubmed.example/paper",
        local_pdf_path="/tmp/pubmed.pdf",
        download_attempts=[],
    )
    arxiv_paper = SimpleNamespace(
        id="arxiv:source-filter",
        doi="arxiv:source-filter",
        title="ArXiv Candidate",
        authors=["B"],
        published="2026-02-21",
        source="ArXiv",
        summary="s",
        link="https://arxiv.example/paper",
        local_pdf_path="/tmp/arxiv.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="oncology", source="pubmed")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(
            constraints=SimpleNamespace(min_pubmed=2, max_preprint=1),
            slots={"clinical": fake_slot},
        ),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        def __init__(self, source_name, papers):
            self.source_name = source_name
            self._papers = papers
            self.calls = 0

        def fetch(self, query, max_results=5):
            self.calls += 1
            return list(self._papers)

    pubmed_fetcher = FakeFetcher("PubMed", [pubmed_paper])
    arxiv_fetcher = FakeFetcher("ArXiv", [arxiv_paper])

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [pubmed_fetcher, arxiv_fetcher])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: None)

    rows = processor.process_daily_slots(ignore_db=True)

    assert [row["id"] for row in rows] == ["pmid:source-filter"]
    assert pubmed_fetcher.calls == 1
    assert arxiv_fetcher.calls == 0


def test_process_daily_slots_limits_all_source_candidates_by_constraints(monkeypatch):
    pubmed_papers = [
        SimpleNamespace(
            id=f"pmid:constraint-{idx}",
            doi=f"10.1000/constraint-{idx}",
            title=f"PubMed Candidate {idx}",
            authors=["A"],
            published="2026-02-21",
            source="PubMed",
            summary="s",
            link=f"https://pubmed.example/{idx}",
            local_pdf_path=f"/tmp/pubmed-{idx}.pdf",
            download_attempts=[],
        )
        for idx in range(1, 4)
    ]
    arxiv_papers = [
        SimpleNamespace(
            id=f"arxiv:constraint-{idx}",
            doi=f"arxiv:constraint-{idx}",
            title=f"ArXiv Candidate {idx}",
            authors=["B"],
            published="2026-02-21",
            source="ArXiv",
            summary="s",
            link=f"https://arxiv.example/{idx}",
            local_pdf_path=f"/tmp/arxiv-{idx}.pdf",
            download_attempts=[],
        )
        for idx in range(1, 3)
    ]

    fake_slot = SimpleNamespace(query="oncology", source="all")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(
            constraints=SimpleNamespace(min_pubmed=2, max_preprint=1),
            slots={"clinical": fake_slot},
        ),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        def __init__(self, source_name, papers):
            self.source_name = source_name
            self._papers = papers

        def fetch(self, query, max_results=5):
            return list(self._papers)

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(
        processor,
        "get_fetchers",
        lambda *_: [FakeFetcher("PubMed", pubmed_papers), FakeFetcher("ArXiv", arxiv_papers)],
    )
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: None)

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    assert rows[0]["id"] == "pmid:constraint-1"
    assert rows[0]["manual_rank_score"] is not None
    payload = json.loads(rows[0]["feedback_json"])
    assert payload["selection"]["candidate_count"] == 3
    assert payload["selection"]["source_counts"] == {"pubmed": 2, "arxiv": 1}
    assert payload["selection"]["constraints"]["slot_source"] == "all"
    assert payload["selection"]["constraints"]["applied_pubmed_budget"] == 2
    assert payload["selection"]["constraints"]["applied_preprint_budget"] == 1
    assert [candidate["source"] for candidate in payload["selection"]["top_candidates"]] == [
        "PubMed",
        "PubMed",
        "ArXiv",
    ]
    top_candidate = payload["selection"]["top_candidates"][0]
    assert top_candidate["title"] == "PubMed Candidate 1"
    assert top_candidate["score_breakdown"]["final_score"] == top_candidate["score"]
    assert top_candidate["score_breakdown"]["source_bonus"] == 0.25
    assert top_candidate["score_breakdown"]["metadata_components"]["doi_bonus"] == 0.08


def test_process_daily_slots_selects_top_ranked_slot_representative(monkeypatch):
    older_pubmed_paper = SimpleNamespace(
        id="pmid:rank-older",
        doi="10.1000/rank-older",
        title="Older PubMed Candidate",
        authors=["A"],
        published="2026-01-01",
        source="PubMed",
        summary="s",
        link="https://pubmed.example/older",
        local_pdf_path="/tmp/older.pdf",
        download_attempts=[],
    )
    newer_pubmed_paper = SimpleNamespace(
        id="pmid:rank-newer",
        doi="10.1000/rank-newer",
        title="Newer PubMed Candidate",
        authors=["B"],
        published="2026-02-21",
        source="PubMed",
        summary="s",
        link="https://pubmed.example/newer",
        local_pdf_path="/tmp/newer.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="oncology", source="pubmed")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(
            constraints=SimpleNamespace(min_pubmed=2, max_preprint=1),
            slots={"clinical": fake_slot},
        ),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        source_name = "PubMed"

        def fetch(self, query, max_results=5):
            return [older_pubmed_paper, newer_pubmed_paper]

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: None)

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    assert rows[0]["id"] == "pmid:rank-newer"
    assert rows[0]["manual_rank_score"] > 0
    payload = json.loads(rows[0]["feedback_json"])
    assert payload["selection"]["selected_rank"] == 1
    assert payload["selection"]["candidate_count"] == 2
    assert payload["selection"]["selected_paper_id"] == "pmid:rank-newer"
    assert payload["selection"]["selected_score_breakdown"]["final_score"] == rows[0]["manual_rank_score"]
    assert payload["selection"]["selected_score_breakdown"]["metadata_components"]["recency_bonus"] > 0


def test_process_daily_slots_skips_processed_top_candidate_and_uses_next_ranked(monkeypatch):
    top_candidate = SimpleNamespace(
        id="pmid:rank-top",
        doi="10.1000/rank-top",
        title="Top Candidate",
        authors=["A"],
        published="2026-02-21",
        source="PubMed",
        summary="s",
        link="https://pubmed.example/top",
        local_pdf_path="/tmp/top.pdf",
        download_attempts=[],
    )
    backup_candidate = SimpleNamespace(
        id="pmid:rank-backup",
        doi="10.1000/rank-backup",
        title="Backup Candidate",
        authors=["B"],
        published="2026-01-15",
        source="PubMed",
        summary="s",
        link="https://pubmed.example/backup",
        local_pdf_path="/tmp/backup.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="oncology", source="pubmed")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(
            constraints=SimpleNamespace(min_pubmed=1, max_preprint=1),
            slots={"clinical": fake_slot},
        ),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        source_name = "PubMed"

        def fetch(self, query, max_results=5):
            return [top_candidate, backup_candidate]

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda paper_id: paper_id == "pmid:rank-top")
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: None)

    rows = processor.process_daily_slots(ignore_db=False)

    assert len(rows) == 1
    assert rows[0]["id"] == "pmid:rank-backup"
    payload = json.loads(rows[0]["feedback_json"])
    assert payload["selection"]["selected_rank"] == 2
    assert payload["selection"]["skipped_processed_candidates"] == ["pmid:rank-top"]
    assert payload["selection"]["top_candidates"][0]["paper_id"] == "pmid:rank-top"


def test_process_daily_slots_pubmed_only_slot_is_not_capped_by_min_pubmed(monkeypatch):
    older_papers = [
        SimpleNamespace(
            id=f"pmid:older-{idx}",
            doi=f"10.1000/older-{idx}",
            title=f"Older Candidate {idx}",
            authors=["A"],
            published="2026-01-01",
            source="PubMed",
            summary="s",
            link=f"https://pubmed.example/older-{idx}",
            local_pdf_path=f"/tmp/older-{idx}.pdf",
            download_attempts=[],
        )
        for idx in range(1, 3)
    ]
    newest_paper = SimpleNamespace(
        id="pmid:newest-outside-min-pubmed",
        doi="10.1000/newest-outside-min-pubmed",
        title="Newest Outside Min PubMed",
        authors=["B"],
        published="2026-02-21",
        source="PubMed",
        summary="s",
        link="https://pubmed.example/newest",
        local_pdf_path="/tmp/newest.pdf",
        download_attempts=[],
    )

    fake_slot = SimpleNamespace(query="oncology", source="pubmed")
    fake_config = SimpleNamespace(
        search=SimpleNamespace(
            constraints=SimpleNamespace(min_pubmed=2, max_preprint=1),
            slots={"clinical": fake_slot},
        ),
        llm=SimpleNamespace(features=SimpleNamespace(slot_classification=SimpleNamespace(enabled=False))),
        ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=False)),
        entity_aliases={},
        confidence_thresholds=SimpleNamespace(high=0.9, low=0.7),
        paths=SimpleNamespace(export_dir="export"),
    )

    class FakeFetcher:
        source_name = "PubMed"

        def fetch(self, query, max_results=5):
            return older_papers + [newest_paper]

    monkeypatch.setattr(processor, "load_config", lambda: fake_config)
    monkeypatch.setattr(processor, "get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr(processor, "get_fetchers", lambda *_: [FakeFetcher()])
    monkeypatch.setattr(processor, "is_paper_processed", lambda *_: False)
    monkeypatch.setattr(processor, "download_paper", lambda paper, _cfg: paper)
    monkeypatch.setattr(processor, "save_paper_to_obsidian", lambda *_: None)
    monkeypatch.setattr(processor, "export_to_ris", lambda *_: None)
    monkeypatch.setattr(processor, "save_paper_state", lambda *args, **kwargs: None)

    rows = processor.process_daily_slots(ignore_db=True)

    assert len(rows) == 1
    assert rows[0]["id"] == "pmid:newest-outside-min-pubmed"
