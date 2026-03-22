from pathlib import Path

from src.timeout_policy import (
    BatchTimeoutPolicy,
    default_reader_timeout_base_seconds,
    default_stats_timeout_base_seconds,
    estimate_doc_timeout_seconds,
    estimate_reader_timeout_seconds,
    estimate_stats_timeout_seconds,
    is_timeout_exception,
    next_retry_timeout_seconds,
    StepTimeoutError,
)


def test_estimate_doc_timeout_fixed_policy(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"x" * 1024)

    policy = BatchTimeoutPolicy(strategy="fixed", base_timeout_sec=210)
    assert estimate_doc_timeout_seconds(pdf, policy) == 210


def test_estimate_doc_timeout_adaptive_policy_clamps(tmp_path: Path):
    pdf = tmp_path / "large.pdf"
    # 10 MiB
    pdf.write_bytes(b"x" * (10 * 1024 * 1024))

    policy = BatchTimeoutPolicy(
        strategy="adaptive",
        base_timeout_sec=120,
        min_timeout_sec=150,
        max_timeout_sec=300,
        size_weight_sec_per_mib=25.0,
    )
    # base + 10*25 = 370 -> clamp to max 300
    assert estimate_doc_timeout_seconds(pdf, policy) == 300


def test_estimate_doc_timeout_includes_page_bonus(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"x" * 1024)

    monkeypatch.setattr("src.timeout_policy.estimate_pdf_page_count", lambda _path: 12)
    policy = BatchTimeoutPolicy(
        strategy="adaptive",
        base_timeout_sec=120,
        min_timeout_sec=120,
        max_timeout_sec=400,
        size_weight_sec_per_mib=0.0,
        page_weight_sec_per_page=10.0,
    )
    assert estimate_doc_timeout_seconds(pdf, policy) == 240


def test_next_retry_timeout_respects_min_bump_and_cap():
    assert next_retry_timeout_seconds(120, retry_factor=1.2, min_bump_sec=60, hard_cap_sec=400) == 180
    assert next_retry_timeout_seconds(350, retry_factor=2.0, min_bump_sec=60, hard_cap_sec=400) == 400


def test_step_timeout_estimators_expand_with_complexity():
    reader = estimate_reader_timeout_seconds(
        30,
        page_count=40,
        table_count=5,
        adaptive=True,
        doc_timeout_sec=360,
        remaining_doc_budget_sec=240,
    )
    stats = estimate_stats_timeout_seconds(
        40,
        page_count=40,
        table_count=5,
        claim_count=8,
        adaptive=True,
        doc_timeout_sec=360,
        remaining_doc_budget_sec=260,
    )

    assert reader > 30
    assert stats > 40
    assert estimate_reader_timeout_seconds(30, page_count=40, table_count=5, adaptive=False) == 30
    assert estimate_stats_timeout_seconds(40, page_count=40, table_count=5, claim_count=8, adaptive=False) == 40


def test_step_timeout_estimators_respect_remaining_doc_budget():
    reader = estimate_reader_timeout_seconds(
        90,
        page_count=80,
        table_count=10,
        adaptive=True,
        doc_timeout_sec=600,
        remaining_doc_budget_sec=135,
    )
    stats = estimate_stats_timeout_seconds(
        120,
        page_count=80,
        table_count=10,
        claim_count=10,
        adaptive=True,
        doc_timeout_sec=600,
        remaining_doc_budget_sec=185,
    )

    assert reader == 135
    assert stats == 185


def test_default_timeout_bases_are_scaled_from_llm_timeout():
    assert default_reader_timeout_base_seconds(15) == 90
    assert default_stats_timeout_base_seconds(15) == 120
    assert default_reader_timeout_base_seconds(1) == 60
    assert default_stats_timeout_base_seconds(1) == 90


def test_is_timeout_exception_detects_common_timeout_types():
    class ReadTimeout(Exception):
        pass

    assert is_timeout_exception(StepTimeoutError("step_timeout:5s")) is True
    assert is_timeout_exception(ReadTimeout("read timeout")) is True
    assert is_timeout_exception(ValueError("oops")) is False
