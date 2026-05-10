import json
from types import SimpleNamespace

from backend.services.job_runner import (
    _build_anchor_verify_log_entries,
    _build_anchor_verify_summary,
    _build_cloud_table_preflight_callback,
    _resolve_ingest_parser_backend,
    _resolve_ingest_runtime_options,
)


def test_resolve_ingest_backend_defaults_to_fitz_when_ingest_missing() -> None:
    config = SimpleNamespace()
    assert _resolve_ingest_parser_backend(config) == "fitz_pdfplumber"


def test_resolve_ingest_backend_docling_requires_enable_flag() -> None:
    config = SimpleNamespace(ingest=SimpleNamespace(parser_backend="docling", enable_docling=False))
    assert _resolve_ingest_parser_backend(config) == "fitz_pdfplumber"


def test_resolve_ingest_backend_docling_enabled() -> None:
    config = SimpleNamespace(ingest=SimpleNamespace(parser_backend="docling", enable_docling=True))
    assert _resolve_ingest_parser_backend(config) == "docling"


def test_resolve_ingest_backend_invalid_value_falls_back_to_fitz() -> None:
    config = SimpleNamespace(ingest=SimpleNamespace(parser_backend="invalid", enable_docling=True))
    assert _resolve_ingest_parser_backend(config) == "fitz_pdfplumber"


def test_resolve_ingest_backend_override_prefers_requested_backend_when_allowed() -> None:
    config = SimpleNamespace(ingest=SimpleNamespace(parser_backend="fitz_pdfplumber", enable_docling=True))
    assert _resolve_ingest_parser_backend(config, override_backend="docling") == "docling"


def test_resolve_ingest_backend_override_ignores_invalid_override() -> None:
    config = SimpleNamespace(ingest=SimpleNamespace(parser_backend="docling", enable_docling=True))
    assert _resolve_ingest_parser_backend(config, override_backend="invalid") == "docling"


def test_resolve_ingest_backend_override_still_respects_docling_gate() -> None:
    config = SimpleNamespace(ingest=SimpleNamespace(parser_backend="fitz_pdfplumber", enable_docling=False))
    assert _resolve_ingest_parser_backend(config, override_backend="docling") == "fitz_pdfplumber"


def test_build_anchor_verify_summary_maps_verdict_counts() -> None:
    checks = [
        SimpleNamespace(verdict="verified"),
        SimpleNamespace(verdict="partially_verified"),
        SimpleNamespace(verdict="inconsistent"),
        SimpleNamespace(verdict="unverifiable"),
    ]
    report = SimpleNamespace(checks=checks)
    summary = _build_anchor_verify_summary(report)
    assert summary == {"pass": 1, "warn": 1, "fail": 1, "no_api": 1}


def test_resolve_ingest_runtime_options_defaults() -> None:
    config = SimpleNamespace()
    options = _resolve_ingest_runtime_options(config)
    assert options["enable_ocr_fallback"] is False
    assert options["ocr_lang"] == "eng"
    assert options["ocr_min_text_chars"] == 200
    assert options["enable_table_pass2_ocr"] is False
    assert options["enable_cloud_table_fallback"] is False
    assert options["cloud_table_page_budget"] == 2
    assert options["cloud_table_model"] == "gpt-4o-mini"
    assert options["cloud_table_base_url"] is None
    assert options["cloud_table_api_key"] is None
    assert options["cloud_table_timeout_seconds"] == 30


def test_resolve_ingest_runtime_options_from_config() -> None:
    config = SimpleNamespace(
        ingest=SimpleNamespace(
            enable_ocr_fallback=True,
            ocr_lang="kor+eng",
            ocr_min_text_chars=123,
            enable_table_pass2_ocr=True,
            enable_cloud_table_fallback=True,
            cloud_table_page_budget=4,
            cloud_table_model="gpt-4.1-mini",
            cloud_table_base_url="https://example.com/v1",
            cloud_table_api_key="sk-test",
            cloud_table_timeout_seconds=15,
        )
    )
    options = _resolve_ingest_runtime_options(config)
    assert options == {
        "enable_ocr_fallback": True,
        "ocr_lang": "kor+eng",
        "ocr_min_text_chars": 123,
        "enable_table_pass2_ocr": True,
        "enable_cloud_table_fallback": True,
        "cloud_table_page_budget": 4,
        "cloud_table_model": "gpt-4.1-mini",
        "cloud_table_base_url": "https://example.com/v1",
        "cloud_table_api_key": "sk-test",
        "cloud_table_timeout_seconds": 15,
    }


def test_build_anchor_verify_log_entries_contains_contract_fields() -> None:
    span = SimpleNamespace(
        page=2,
        bbox_pdf=[1.0, 2.0, 3.0, 4.0],
        bbox_pct={"left": 1.0, "top": 2.0, "width": 3.0, "height": 4.0},
        table_id="T1",
        cell_id="R1C1",
        source_span=[10, 20],
        char_start=10,
        char_end=20,
    )
    checks = [
        SimpleNamespace(
            check_id="a1",
            verdict="verified",
            computed_p=0.01,
            reported_p="0.02",
            reported_stat=2.1,
            evidence=[span],
        ),
        SimpleNamespace(
            check_id="a2",
            verdict="unverifiable",
            computed_p=None,
            reported_p=None,
            reported_stat=None,
            evidence=[],
        ),
    ]
    report = SimpleNamespace(checks=checks)
    entries = _build_anchor_verify_log_entries(
        "run-1",
        "doc-1",
        report,
        api_provider="crossref",
        api_reason_codes=["CROSSREF_OK"],
    )
    assert len(entries) == 2
    assert entries[0]["run_id"] == "run-1"
    assert entries[0]["doc_id"] == "doc-1"
    assert entries[0]["anchor_id"] == "a1"
    assert entries[0]["result"] == "PASS"
    assert entries[0]["api_provider"] == "crossref"
    assert entries[0]["bbox_ref"]["table_id"] == "T1"
    assert "VERDICT_VERIFIED" in entries[0]["reason_codes"]
    assert "CROSSREF_OK" in entries[0]["reason_codes"]
    assert entries[1]["anchor_id"] == "a2"
    assert entries[1]["result"] == "NO_API"
    assert "VERDICT_UNVERIFIABLE" in entries[1]["reason_codes"]
    assert "NO_API" in entries[1]["reason_codes"]


def test_cloud_table_preflight_callback_records_and_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "block_on_review")
    artifact_dir = tmp_path / "run"
    artifact_dir.mkdir()
    run_meta = {"inference_lanes": {}}
    bootstrap_meta = {}

    callback = _build_cloud_table_preflight_callback(
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
        artifact_dir=artifact_dir,
        paper_id="paper-cloud-privacy",
        run_id="run-cloud-privacy",
        model="gpt-4o-mini",
    )

    allowed = callback("Alice's appointment and /Users/alice/private.pdf table text", 2)

    assert allowed is False
    assert bootstrap_meta["cloud_table_fallback_status"] == "privacy_preflight_blocked"
    assert run_meta["cloud_table_fallback_status"] == "privacy_preflight_blocked"
    lane = run_meta["inference_lanes"]["cloud_table_fallback"]
    assert lane["payload_class"] == "external_allowed"
    assert lane["provider_model"] == "gpt-4o-mini"
    preflight = lane["privacy_preflight"]
    assert preflight["mode"] == "block_on_review"
    assert preflight["status"] == "blocked"
    assert preflight["scope"] == "cloud_table_fallback_external_payload"
    assert preflight["source_surfaces"] == ["pdf_page_2_text"]
    assert "paper:paper-cloud-privacy" in preflight["input_refs"]

    persisted = json.loads((artifact_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert persisted["cloud_table_fallback_status"] == "privacy_preflight_blocked"


def test_cloud_table_preflight_callback_blocks_invalid_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LATTICE_PRIVACY_PREFLIGHT_MODE", "invalid")
    artifact_dir = tmp_path / "run"
    artifact_dir.mkdir()
    run_meta = {"inference_lanes": {}}
    bootstrap_meta = {}

    callback = _build_cloud_table_preflight_callback(
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
        artifact_dir=artifact_dir,
        paper_id="paper-cloud-privacy",
        run_id="run-cloud-privacy",
        model="gpt-4o-mini",
    )

    allowed = callback("ordinary table text", 1)

    assert allowed is False
    assert bootstrap_meta["cloud_table_fallback_status"] == "failed:invalid_privacy_preflight_mode"
    assert run_meta["cloud_table_fallback_status"] == "failed:invalid_privacy_preflight_mode"
    assert "invalid LATTICE_PRIVACY_PREFLIGHT_MODE" in run_meta["privacy_preflight_error"]
