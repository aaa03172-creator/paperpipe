from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.summarize_parser_readiness_blockers import (
    build_parser_readiness_blocker_triage_summary,
    run_parser_readiness_blocker_triage,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _readiness_summary() -> dict:
    return {
        "schema_version": "parser_baseline_readiness.v1",
        "run_id": "readiness_fixture",
        "decision": {
            "baseline_parser_usable": True,
            "docling_optional_pilot_supported": False,
            "blockers": [
                "section_missing_page_docs_present",
                "table_merge_content_gap_docs_present",
            ],
        },
    }


def _section_details() -> dict:
    return {
        "schema_version": "section_quality_audit.v1",
        "run_id": "section_fixture",
        "documents": [
            {
                "pdf_path": "/tmp/section-a.pdf",
                "classification": {
                    "missing_substantive_pages": [7],
                    "low_page_text_ratio_pages": [
                        {
                            "page": 3,
                            "baseline_char_count": 1942,
                            "candidate_char_count": 21,
                            "ratio": 0.0108,
                            "review_bucket": "needs_manual_review",
                            "review_signals": [],
                            "baseline_digit_ratio": 0.216,
                            "candidate_digit_ratio": 0.0,
                        }
                    ],
                    "baseline_section_count": 12,
                    "candidate_section_count": 11,
                    "baseline_total_text_chars": 10000,
                    "candidate_total_text_chars": 9500,
                    "total_text_ratio": 0.95,
                },
            },
            {
                "pdf_path": "/tmp/section-ok.pdf",
                "classification": {
                    "missing_substantive_pages": [],
                    "low_page_text_ratio_pages": [],
                },
            },
        ],
    }


def _table_merge_details() -> dict:
    return {
        "schema_version": "table_merge_semantics_audit.v1",
        "run_id": "table_fixture",
        "documents": [
            {
                "pdf_path": "/tmp/table-a.pdf",
                "classification": {
                    "semantic_merge_preserved": False,
                    "missing_pages": [],
                    "missing_cells_total": 2,
                    "extra_cells_total": 5,
                    "missing_cells_by_page": {
                        "16": {
                            "amyloidunknowntauunknown": 1,
                            "beta": 1,
                        }
                    },
                    "extra_cells_by_page": {
                        "16": {
                            "amyloidunknowntau": 1,
                            "gamma": 1,
                        }
                    },
                },
            },
            {
                "pdf_path": "/tmp/table-ok.pdf",
                "classification": {
                    "semantic_merge_preserved": True,
                    "missing_pages": [],
                    "missing_cells_total": 0,
                    "extra_cells_total": 1,
                    "missing_cells_by_page": {},
                },
            },
        ],
    }


def test_build_parser_readiness_blocker_triage_summary_groups_section_and_table_blockers() -> None:
    payload = build_parser_readiness_blocker_triage_summary(
        readiness_summary=_readiness_summary(),
        readiness_summary_path=Path("/tmp/readiness/summary.json"),
        section_details=_section_details(),
        section_details_path=Path("/tmp/section/details.json"),
        table_merge_details=_table_merge_details(),
        table_merge_details_path=Path("/tmp/table/details.json"),
        run_id="triage_fixture",
    )

    assert payload["aggregate"]["section_blocker_doc_count"] == 1
    assert payload["aggregate"]["section_missing_page_doc_count"] == 1
    assert payload["aggregate"]["section_unclassified_low_ratio_doc_count"] == 1
    assert payload["aggregate"]["section_page_triage_bucket_counts"] == {
        "numeric_dense_page_manual_review": 1,
    }
    assert payload["aggregate"]["table_merge_content_gap_doc_count"] == 1
    assert payload["aggregate"]["table_merge_missing_cell_count"] == 2
    assert payload["aggregate"]["table_candidate_truncation_pair_count"] == 1
    assert payload["aggregate"]["table_same_page_duplicate_risk_page_count"] == 1
    assert payload["decision"]["candidate_action"] == "hold_docling_pilot_pending_manual_review"
    assert (
        payload["decision"]["table_runtime_patch_action"]
        == "hold_same_page_table_fallback_pending_duplicate_safe_rescue"
    )
    assert payload["section_blockers"][0]["triage_recommendation"] == "manual_section_page_review_required"
    assert payload["table_merge_blockers"][0]["pages"][0]["extra_cell_count"] == 2
    assert payload["table_merge_blockers"][0]["pages"][0]["same_page_fallback_duplicate_risk"] is True
    assert (
        payload["table_merge_blockers"][0]["pages"][0]["fallback_patch_risk"]
        == "same_page_fallback_may_duplicate_candidate_table_cells"
    )
    assert payload["table_merge_blockers"][0]["pages"][0]["sample_missing_cells"] == [
        "amyloidunknowntauunknown",
        "beta",
    ]
    assert payload["table_merge_blockers"][0]["pages"][0]["sample_extra_cells"] == [
        "amyloidunknowntau",
        "gamma",
    ]
    assert payload["table_merge_blockers"][0]["pages"][0]["candidate_truncation_pairs"] == [
        {
            "missing_cell": "amyloidunknowntauunknown",
            "candidate_cell": "amyloidunknowntau",
            "missing_suffix": "unknown",
            "missing_count": 1,
            "candidate_count": 1,
            "candidate_length_ratio": 0.7083,
            "review_reason": "candidate_prefix_truncates_baseline_cell",
        }
    ]


def test_run_parser_readiness_blocker_triage_writes_summary_and_cli_prints_compact_line(
    tmp_path: Path,
) -> None:
    readiness_root = tmp_path / "readiness"
    section_root = tmp_path / "section"
    table_root = tmp_path / "table"
    _write_json(readiness_root / "summary.json", _readiness_summary())
    _write_json(section_root / "details.json", _section_details())
    _write_json(table_root / "details.json", _table_merge_details())

    run_root = run_parser_readiness_blocker_triage(
        readiness_summary_path=readiness_root,
        section_details_path=section_root,
        table_merge_details_path=table_root,
        out_dir=tmp_path / "out",
        run_id="triage_python",
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["inputs"]["readiness_run_id"] == "readiness_fixture"

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eval"
        / "summarize_parser_readiness_blockers.py"
    )
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--readiness-summary",
            str(readiness_root),
            "--section-details",
            str(section_root),
            "--table-merge-details",
            str(table_root),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "triage_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[summarize_parser_readiness_blockers] out=" in completed.stdout
    assert "[summarize_parser_readiness_blockers] summary=" in completed.stdout
    assert (
        "[summarize_parser_readiness_blockers] "
        "candidate_action=hold_docling_pilot_pending_manual_review "
        "table_runtime_patch_action=hold_same_page_table_fallback_pending_duplicate_safe_rescue section_docs=1 "
        "missing_page_docs=1 unclassified_low_ratio_docs=1 table_gap_docs=1 table_missing_cells=2 "
        "table_truncation_pairs=1 table_duplicate_risk_pages=1"
    ) in completed.stdout


def test_table_runtime_patch_action_allows_lower_risk_missing_page_review() -> None:
    table_details = {
        "schema_version": "table_merge_semantics_audit.v1",
        "run_id": "table_missing_page_fixture",
        "documents": [
            {
                "pdf_path": "/tmp/table-missing-page.pdf",
                "classification": {
                    "semantic_merge_preserved": False,
                    "missing_pages": [5],
                    "missing_cells_total": 1,
                    "extra_cells_total": 0,
                    "missing_cells_by_page": {"5": {"lostcell": 1}},
                    "extra_cells_by_page": {},
                },
            }
        ],
    }

    payload = build_parser_readiness_blocker_triage_summary(
        readiness_summary={
            "schema_version": "parser_baseline_readiness.v1",
            "run_id": "readiness_fixture",
            "decision": {"blockers": []},
        },
        readiness_summary_path=None,
        section_details={"schema_version": "section_quality_audit.v1", "documents": []},
        section_details_path=None,
        table_merge_details=table_details,
        table_merge_details_path=None,
        run_id="missing_page_review",
    )

    page = payload["table_merge_blockers"][0]["pages"][0]
    assert payload["aggregate"]["table_same_page_duplicate_risk_page_count"] == 0
    assert payload["decision"]["table_runtime_patch_action"] == "manual_table_gap_review_before_runtime_patch"
    assert page["same_page_fallback_duplicate_risk"] is False
    assert page["fallback_patch_risk"] == "missing_page_or_empty_candidate_page_lower_duplicate_risk"
