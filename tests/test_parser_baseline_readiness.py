from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.check_parser_baseline_readiness import (
    build_parser_baseline_readiness_summary,
    run_parser_baseline_readiness,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _compare_metrics(
    *,
    run_id: str = "compare_fixture",
    document_count: int = 2,
    decision_passed: bool = True,
    doi_loss_docs: int = 0,
    low_text_ratio_docs: int = 0,
    same_page_merge_docs: int = 0,
    candidate_error_count: int = 0,
) -> dict:
    candidate_success_count = document_count - candidate_error_count
    return {
        "schema_version": "ingest_backend_eval.v1",
        "generated_at": "2026-04-23T00:00:00Z",
        "run_id": run_id,
        "baseline_backend": "fitz_pdfplumber",
        "candidate_backend": "docling",
        "document_count": document_count,
        "backend_metrics": {
            "fitz_pdfplumber": {
                "document_count": document_count,
                "success_count": document_count,
                "error_count": 0,
                "backend_unavailable_count": 0,
                "docs_with_doi_count": document_count,
                "docs_with_tables_count": 1,
                "docs_with_meaningful_tables_count": 1,
                "docs_with_table_fallback_count": 0,
                "docs_with_text_count": document_count,
                "avg_text_char_count": 1000.0,
            },
            "docling": {
                "document_count": document_count,
                "success_count": candidate_success_count,
                "error_count": candidate_error_count,
                "backend_unavailable_count": 0,
                "docs_with_doi_count": document_count - doi_loss_docs,
                "docs_with_tables_count": 2,
                "docs_with_meaningful_tables_count": 2,
                "docs_with_table_fallback_count": 0,
                "docs_with_text_count": candidate_success_count,
                "avg_text_char_count": 1200.0,
            },
        },
        "comparison": {
            "compared_document_count": document_count,
            "backend_unavailable_docs": [],
            "error_increase_docs": [{} for _ in range(candidate_error_count)],
            "empty_text_increase_docs": [],
            "doi_loss_docs": [{} for _ in range(doi_loss_docs)],
            "meaningful_table_loss_docs": [],
            "meaningful_table_gain_docs": [{}],
            "same_page_merge_docs": [{} for _ in range(same_page_merge_docs)],
            "low_text_ratio_docs": [{} for _ in range(low_text_ratio_docs)],
            "decision": {
                "passed": decision_passed,
                "failed_checks": [] if decision_passed else ["doi_loss_docs"],
            },
        },
    }


def _section_summary(
    *,
    run_id: str = "section_fixture",
    document_count: int = 2,
    low_page_text_ratio_docs_count: int = 0,
    unclassified_docs: int = 0,
    missing_page_docs: int = 0,
    section_collapse_docs: int = 0,
) -> dict:
    return {
        "run_id": run_id,
        "status": "ok",
        "document_count": document_count,
        "page_coverage_preserved_count": document_count - missing_page_docs,
        "missing_page_docs_count": missing_page_docs,
        "low_page_text_ratio_docs_count": low_page_text_ratio_docs_count,
        "low_page_text_ratio_doc_bucket_counts": {},
        "low_page_text_ratio_page_bucket_counts": {},
        "low_page_text_ratio_unclassified_docs_count": unclassified_docs,
        "low_total_text_ratio_docs_count": 0,
        "section_collapse_docs_count": section_collapse_docs,
    }


def _table_summary(
    *,
    run_id: str = "table_fixture",
    document_count: int = 0,
    content_gap_count: int = 0,
) -> dict:
    return {
        "run_id": run_id,
        "status": "ok",
        "document_count": document_count,
        "semantic_merge_preserved_count": document_count - content_gap_count,
        "content_gap_count": content_gap_count,
    }


def test_build_parser_baseline_readiness_passes_but_keeps_default_change_blocked() -> None:
    payload = build_parser_baseline_readiness_summary(
        compare_metrics=[_compare_metrics(same_page_merge_docs=1)],
        compare_metrics_paths=[Path("/tmp/compare/metrics.json")],
        section_summaries=[_section_summary(low_page_text_ratio_docs_count=1)],
        section_summary_paths=[Path("/tmp/section/summary.json")],
        table_merge_summaries=[_table_summary(document_count=1)],
        table_merge_summary_paths=[Path("/tmp/table/summary.json")],
        run_id="parser_readiness_pass",
    )

    assert payload["decision"]["passed"] is True
    assert payload["decision"]["baseline_parser_usable"] is True
    assert payload["decision"]["docling_optional_pilot_supported"] is True
    assert payload["decision"]["default_parser_change_ready"] is False
    assert payload["decision"]["recommended_action"] == "keep_fitz_pdfplumber_default_and_docling_behind_flag"
    assert payload["aggregate"]["compare_document_count"] == 2
    assert payload["aggregate"]["same_page_merge_docs_count"] == 1
    assert payload["aggregate"]["section_low_page_text_ratio_docs_count"] == 1


def test_build_parser_baseline_readiness_blocks_candidate_regressions() -> None:
    payload = build_parser_baseline_readiness_summary(
        compare_metrics=[
            _compare_metrics(
                decision_passed=False,
                doi_loss_docs=1,
                low_text_ratio_docs=1,
                same_page_merge_docs=1,
                candidate_error_count=1,
            )
        ],
        compare_metrics_paths=[Path("/tmp/compare/metrics.json")],
        section_summaries=[
            _section_summary(
                low_page_text_ratio_docs_count=1,
                unclassified_docs=1,
                missing_page_docs=1,
                section_collapse_docs=1,
            )
        ],
        section_summary_paths=[Path("/tmp/section/summary.json")],
        table_merge_summaries=[_table_summary(document_count=1, content_gap_count=1)],
        table_merge_summary_paths=[Path("/tmp/table/summary.json")],
        run_id="parser_readiness_fail",
    )

    assert payload["decision"]["passed"] is False
    assert payload["decision"]["baseline_parser_usable"] is True
    assert payload["decision"]["docling_optional_pilot_supported"] is False
    assert payload["decision"]["blockers"] == [
        "compare_decision_failed",
        "candidate_errors_present",
        "candidate_doi_loss_docs_present",
        "candidate_low_text_ratio_docs_present",
        "section_missing_page_docs_present",
        "section_collapse_docs_present",
        "section_unclassified_low_ratio_docs_present",
        "table_merge_content_gap_docs_present",
    ]


def test_run_parser_baseline_readiness_accepts_run_directories_and_cli_prints_compact_line(
    tmp_path: Path,
) -> None:
    compare_root = tmp_path / "compare_run"
    section_root = tmp_path / "section_run"
    table_root = tmp_path / "table_run"
    _write_json(compare_root / "metrics.json", _compare_metrics(run_id="compare_cli"))
    _write_json(section_root / "summary.json", _section_summary(run_id="section_cli"))
    _write_json(table_root / "summary.json", _table_summary(run_id="table_cli"))

    run_root = run_parser_baseline_readiness(
        compare_metrics_paths=[compare_root],
        section_summary_paths=[section_root],
        table_merge_summary_paths=[table_root],
        out_dir=tmp_path / "out",
        run_id="parser_readiness_python",
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["passed"] is True
    assert payload["runs"]["compare_metrics"][0]["run_id"] == "compare_cli"

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eval"
        / "check_parser_baseline_readiness.py"
    )
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--compare-metrics",
            str(compare_root),
            "--section-summary",
            str(section_root),
            "--table-merge-summary",
            str(table_root),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "parser_readiness_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[check_parser_baseline_readiness] out=" in completed.stdout
    assert "[check_parser_baseline_readiness] summary=" in completed.stdout
    assert (
        "[check_parser_baseline_readiness] "
        "passed=True baseline_usable=True docling_pilot=True default_change_ready=False "
        "action=keep_fitz_pdfplumber_default_and_docling_behind_flag docs=2 section_docs=2 "
        "table_merge_gaps=0"
    ) in completed.stdout


def test_cli_allow_advisory_hold_returns_success_for_candidate_hold(tmp_path: Path) -> None:
    compare_root = tmp_path / "compare_run"
    section_root = tmp_path / "section_run"
    table_root = tmp_path / "table_run"
    _write_json(
        compare_root / "metrics.json",
        _compare_metrics(
            run_id="compare_hold",
            decision_passed=False,
            low_text_ratio_docs=1,
        ),
    )
    _write_json(
        section_root / "summary.json",
        _section_summary(
            run_id="section_hold",
            low_page_text_ratio_docs_count=1,
            unclassified_docs=1,
        ),
    )
    _write_json(table_root / "summary.json", _table_summary(run_id="table_hold"))

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eval"
        / "check_parser_baseline_readiness.py"
    )
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--compare-metrics",
            str(compare_root),
            "--section-summary",
            str(section_root),
            "--table-merge-summary",
            str(table_root),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "parser_readiness_cli_hold",
            "--allow-advisory-hold",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (cli_out_dir / "parser_readiness_cli_hold" / "summary.json").read_text(encoding="utf-8")
    )
    assert payload["decision"]["passed"] is False
    assert payload["decision"]["baseline_parser_usable"] is True
    assert payload["decision"]["docling_optional_pilot_supported"] is False
    assert "passed=False baseline_usable=True docling_pilot=False" in completed.stdout
