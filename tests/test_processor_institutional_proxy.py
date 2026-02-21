from types import SimpleNamespace

import src.processor as processor


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
    monkeypatch.setattr(processor, "save_paper_state", lambda *_: None)

    rows = processor.process_daily_slots(ignore_db=True)
    assert len(rows) == 1
    row = rows[0]
    assert row["pdf_path"] is None
    assert "feedback_json" in row
    assert "institutional_proxy_url" in row["feedback_json"]
    assert "libproxy.knu.ac.kr" in row["feedback_json"]

