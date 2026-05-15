from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.eval.inventory_parser_eval_artifacts import (
    build_parser_eval_artifact_inventory_summary,
    run_parser_eval_artifact_inventory,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_readiness_summary(
    *,
    default_change_ready: bool = False,
    passed: bool = True,
    advisory_only: bool = False,
) -> dict:
    return {
        "schema_version": "parser_baseline_readiness.v1",
        "run_id": "parser_baseline_readiness_fixture",
        "inputs": {
            "compare_metrics_paths": [
                "/tmp/expanded/metrics.json",
                "/tmp/broad/metrics.json",
                "/tmp/refresh/metrics.json",
            ]
        },
        "aggregate": {
            "compare_document_count": 53,
            "compare_run_count": 3,
            "compare_passed_count": 3,
            "same_page_merge_docs_count": 6,
            "table_merge_content_gap_count": 0,
        },
        "advisory": {
            "default_change_review_evidence": {
                "source_material_advisory_only": advisory_only,
                "document_count_floor_met": True,
                "freshness_floor_met": True,
            }
        },
        "decision": {
            "passed": passed,
            "baseline_parser_usable": True,
            "docling_optional_pilot_supported": True,
            "default_parser_change_ready": default_change_ready,
            "default_parser_change_blockers": [
                "current_reports_classify_docling_as_behind_flag_optional_pilot",
            ],
        },
    }


def _derived_rescue_readiness_summary(*, runtime_default_unchanged: bool = True) -> dict:
    return {
        "schema_version": "same_page_table_rescue_readiness.v1",
        "run_id": "same_page_table_rescue_readiness_fixture",
        "inputs": {
            "compare_metrics_path": "/tmp/derived/metrics.json",
            "compare_run_id": "derived_compare_fixture",
            "patched_prefix_truncation_count": 1,
            "post_patch_candidate_page_count": 0,
            "derived_table_content_gap_count": 0,
        },
        "decision": {
            "passed": True,
            "same_page_rescue_ready": True,
            "runtime_default_unchanged": runtime_default_unchanged,
        },
    }


def _derived_compare_metrics() -> dict:
    return {
        "schema_version": "ingest_backend_eval.v1",
        "run_id": "derived_compare_fixture",
        "candidate_backend": "docling",
        "document_count": 7,
        "backend_metrics": {
            "docling": {
                "success_count": 7,
                "docs_with_same_page_table_rescue_count": 1,
                "same_page_table_rescue_page_event_count": 1,
                "same_page_table_rescue_patched_cell_count": 1,
            }
        },
        "comparison": {"decision": {"passed": True}},
    }


def test_build_parser_eval_artifact_inventory_separates_source_and_derived_lanes() -> None:
    payload = build_parser_eval_artifact_inventory_summary(
        source_readiness=_source_readiness_summary(),
        source_readiness_path=Path("/tmp/source/summary.json"),
        derived_rescue_readiness=_derived_rescue_readiness_summary(),
        derived_rescue_readiness_path=Path("/tmp/rescue/summary.json"),
        derived_compare_metrics=_derived_compare_metrics(),
        derived_compare_metrics_path=Path("/tmp/derived/metrics.json"),
        run_id="parser_eval_inventory_fixture",
    )

    source = payload["lanes"]["source_pdf_readiness"]
    derived = payload["lanes"]["derived_ocr_repo_stress"]
    assert payload["decision"]["passed"] is True
    assert payload["decision"]["default_parser_change_supported"] is False
    assert payload["aggregate"]["default_change_review_document_count"] == 53
    assert payload["aggregate"]["derived_review_only_document_count"] == 7
    assert source["promotion_role"] == "canonical_source_readiness"
    assert source["default_change_review_eligible"] is True
    assert source["default_change_promotion_eligible"] is False
    assert derived["promotion_role"] == "derived_stress_review_only"
    assert derived["default_change_review_eligible"] is False
    assert derived["same_page_table_rescue_patched_cell_count"] == 1
    assert "Derived OCR/repo stress evidence is review-only" in payload["decision"]["promotion_boundary"]


def test_advisory_source_fixtures_do_not_count_as_default_change_review_evidence() -> None:
    payload = build_parser_eval_artifact_inventory_summary(
        source_readiness=_source_readiness_summary(advisory_only=True),
        source_readiness_path=Path("/tmp/smoke/source/summary.json"),
        derived_rescue_readiness=_derived_rescue_readiness_summary(),
        derived_rescue_readiness_path=Path("/tmp/smoke/rescue/summary.json"),
        derived_compare_metrics=_derived_compare_metrics(),
        derived_compare_metrics_path=Path("/tmp/smoke/derived/metrics.json"),
        run_id="parser_eval_inventory_smoke_advisory",
    )

    source = payload["lanes"]["source_pdf_readiness"]

    assert payload["decision"]["passed"] is True
    assert source["source_material_advisory_only"] is True
    assert source["default_change_review_eligible"] is False
    assert payload["aggregate"]["default_change_review_document_count"] == 0


def test_build_parser_eval_artifact_inventory_blocks_misclassified_promotion_evidence() -> None:
    payload = build_parser_eval_artifact_inventory_summary(
        source_readiness=_source_readiness_summary(default_change_ready=True),
        source_readiness_path=None,
        derived_rescue_readiness=_derived_rescue_readiness_summary(runtime_default_unchanged=False),
        derived_rescue_readiness_path=None,
        derived_compare_metrics=None,
        derived_compare_metrics_path=None,
        run_id="parser_eval_inventory_blocked",
    )

    assert payload["decision"]["passed"] is False
    assert payload["decision"]["blockers"] == [
        "source_readiness_unexpectedly_marks_default_change_ready",
        "derived_stress_changed_runtime_default",
        "derived_compare_metrics_missing_or_empty",
    ]


def test_run_parser_eval_artifact_inventory_writes_summary_and_cli_line(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    rescue_root = tmp_path / "rescue"
    derived_root = tmp_path / "derived"
    _write_json(source_root / "summary.json", _source_readiness_summary())
    _write_json(
        rescue_root / "summary.json",
        {
            **_derived_rescue_readiness_summary(),
            "inputs": {
                **_derived_rescue_readiness_summary()["inputs"],
                "compare_metrics_path": str(derived_root / "metrics.json"),
            },
        },
    )
    _write_json(derived_root / "metrics.json", _derived_compare_metrics())

    run_root = run_parser_eval_artifact_inventory(
        source_readiness_summary_path=source_root,
        derived_rescue_readiness_summary_path=rescue_root,
        derived_compare_metrics_path=None,
        out_dir=tmp_path / "out",
        run_id="parser_eval_inventory_python",
    )
    payload = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["inventory_valid"] is True
    assert payload["lanes"]["derived_ocr_repo_stress"]["compare_metrics_path"] == str(
        (derived_root / "metrics.json").resolve()
    )

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "eval"
        / "inventory_parser_eval_artifacts.py"
    )
    cli_out_dir = tmp_path / "cli_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-readiness-summary",
            str(source_root),
            "--derived-rescue-readiness-summary",
            str(rescue_root),
            "--out-dir",
            str(cli_out_dir),
            "--run-id",
            "parser_eval_inventory_cli",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[inventory_parser_eval_artifacts] out=" in completed.stdout
    assert "passed=True source_docs=53 derived_docs=7 default_review_docs=53" in completed.stdout
    assert "default_change_supported=False derived_review_only=True" in completed.stdout
