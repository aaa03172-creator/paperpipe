from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.check_same_page_table_rescue_readiness import (
    PATCH_TAXONOMY,
    SKIPPED_TAXONOMY,
    build_same_page_table_rescue_readiness_summary,
    run_same_page_table_rescue_readiness,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _compare_metrics(*, patched_count: int = 1, skipped_count: int = 3, decision_passed: bool = True) -> dict:
    return {
        "schema_version": "ingest_backend_eval.v1",
        "generated_at": "2026-04-24T00:00:00Z",
        "run_id": "compare_r32",
        "candidate_backend": "docling",
        "backend_metrics": {
            "docling": {
                "table_failure_taxonomy_counts": {
                    PATCH_TAXONOMY: patched_count,
                    SKIPPED_TAXONOMY: skipped_count,
                }
            }
        },
        "comparison": {
            "decision": {"passed": decision_passed},
        },
    }


def _table_merge_summary(*, content_gap_count: int = 0) -> dict:
    return {
        "run_id": "table_r32",
        "status": "ok",
        "document_count": 2,
        "semantic_merge_preserved_count": 2 - content_gap_count,
        "content_gap_count": content_gap_count,
    }


def _triage_summary(
    *,
    content_gap_docs: int = 0,
    truncation_pairs: int = 0,
    duplicate_risk_pages: int = 0,
    candidate_action: str = "no_candidate_blockers_detected",
    patch_action: str = "no_table_runtime_patch_needed",
) -> dict:
    return {
        "run_id": "triage_r15",
        "aggregate": {
            "table_merge_content_gap_doc_count": content_gap_docs,
            "table_candidate_truncation_pair_count": truncation_pairs,
            "table_same_page_duplicate_risk_page_count": duplicate_risk_pages,
        },
        "decision": {
            "candidate_action": candidate_action,
            "table_runtime_patch_action": patch_action,
        },
    }


def _rescue_candidate_summary(*, candidate_pages: int = 0, runtime_change_approved: bool = False) -> dict:
    return {
        "run_id": "rescue_r2",
        "candidate_page_count": candidate_pages,
        "runtime_change_approved": runtime_change_approved,
    }


def _parser_readiness_summary(
    *,
    passed: bool = True,
    docling_pilot: bool = True,
    default_change_ready: bool = False,
    document_count: int = 53,
    table_gaps: int = 0,
) -> dict:
    return {
        "run_id": "readiness_r8",
        "aggregate": {
            "compare_document_count": document_count,
            "table_merge_content_gap_count": table_gaps,
        },
        "decision": {
            "passed": passed,
            "docling_optional_pilot_supported": docling_pilot,
            "default_parser_change_ready": default_change_ready,
        },
    }


def test_build_same_page_table_rescue_readiness_passes_for_aligned_artifacts() -> None:
    payload = build_same_page_table_rescue_readiness_summary(
        compare_metrics=_compare_metrics(),
        table_merge_summary=_table_merge_summary(),
        blocker_triage_summary=_triage_summary(),
        rescue_candidate_summary=_rescue_candidate_summary(),
        parser_readiness_summary=_parser_readiness_summary(),
        compare_metrics_path=Path("/tmp/compare/metrics.json"),
        table_merge_summary_path=Path("/tmp/table/summary.json"),
        blocker_triage_summary_path=Path("/tmp/triage/summary.json"),
        rescue_candidate_summary_path=Path("/tmp/rescue/summary.json"),
        parser_readiness_summary_path=Path("/tmp/readiness/summary.json"),
        run_id="rescue_ready",
    )

    assert payload["decision"]["passed"] is True
    assert payload["decision"]["same_page_rescue_ready"] is True
    assert payload["decision"]["runtime_default_unchanged"] is True
    assert payload["decision"]["blockers"] == []
    assert payload["inputs"]["patched_prefix_truncation_count"] == 1
    assert payload["inputs"]["skipped_primary_page_fallback_count"] == 3


def test_build_same_page_table_rescue_readiness_fails_for_regressed_artifacts() -> None:
    payload = build_same_page_table_rescue_readiness_summary(
        compare_metrics=_compare_metrics(patched_count=0, decision_passed=False),
        table_merge_summary=_table_merge_summary(content_gap_count=1),
        blocker_triage_summary=_triage_summary(
            content_gap_docs=1,
            truncation_pairs=1,
            duplicate_risk_pages=1,
            candidate_action="hold_docling_pilot_pending_manual_review",
            patch_action="hold_same_page_table_fallback_pending_duplicate_safe_rescue",
        ),
        rescue_candidate_summary=_rescue_candidate_summary(candidate_pages=1, runtime_change_approved=True),
        parser_readiness_summary=_parser_readiness_summary(
            passed=False,
            docling_pilot=False,
            default_change_ready=True,
            document_count=12,
            table_gaps=1,
        ),
        compare_metrics_path=None,
        table_merge_summary_path=None,
        blocker_triage_summary_path=None,
        rescue_candidate_summary_path=None,
        parser_readiness_summary_path=None,
        run_id="rescue_regressed",
    )

    assert payload["decision"]["passed"] is False
    assert payload["decision"]["blockers"] == [
        "derived_compare_decision_failed",
        "same_page_rescue_patch_taxonomy_missing",
        "derived_table_content_gaps_present",
        "blocker_triage_table_gaps_present",
        "blocker_triage_truncation_pairs_present",
        "blocker_triage_duplicate_risk_pages_present",
        "blocker_triage_candidate_action_not_clear",
        "blocker_triage_runtime_patch_action_not_clear",
        "post_patch_rescue_candidates_remaining",
        "rescue_candidate_sidecar_must_not_approve_runtime_change",
        "source_parser_readiness_not_green",
        "source_docling_pilot_not_supported",
        "default_parser_change_unexpectedly_ready",
        "source_readiness_document_count_below_floor",
        "source_table_merge_gaps_present",
    ]


def test_run_same_page_table_rescue_readiness_writes_summary_and_cli_returns_nonzero(
    tmp_path: Path,
) -> None:
    compare_root = tmp_path / "compare"
    table_root = tmp_path / "table"
    triage_root = tmp_path / "triage"
    rescue_root = tmp_path / "rescue"
    readiness_root = tmp_path / "readiness"
    _write_json(compare_root / "metrics.json", _compare_metrics())
    _write_json(table_root / "summary.json", _table_merge_summary())
    _write_json(triage_root / "summary.json", _triage_summary())
    _write_json(rescue_root / "summary.json", _rescue_candidate_summary())
    _write_json(readiness_root / "summary.json", _parser_readiness_summary())

    run_root = run_same_page_table_rescue_readiness(
        compare_metrics_path=compare_root,
        table_merge_summary_path=table_root,
        blocker_triage_summary_path=triage_root,
        rescue_candidate_summary_path=rescue_root,
        parser_readiness_summary_path=readiness_root,
        out_dir=tmp_path / "out",
        run_id="rescue_ready_python",
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["passed"] is True

    _write_json(compare_root / "metrics.json", _compare_metrics(patched_count=0))
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eval"
        / "check_same_page_table_rescue_readiness.py"
    )
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--compare-metrics",
            str(compare_root),
            "--table-merge-summary",
            str(table_root),
            "--blocker-triage-summary",
            str(triage_root),
            "--rescue-candidate-summary",
            str(rescue_root),
            "--parser-readiness-summary",
            str(readiness_root),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "rescue_ready_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1, completed.stderr
    assert "[check_same_page_table_rescue_readiness] out=" in completed.stdout
    assert "[check_same_page_table_rescue_readiness] summary=" in completed.stdout
    assert "passed=False patches=0" in completed.stdout
    assert "blockers=same_page_rescue_patch_taxonomy_missing" in completed.stdout
