from __future__ import annotations

import json
from pathlib import Path

from scripts.backfill_deepread_handoff_artifacts import resolve_run_dirs, run_backfill


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stale_run_payloads(*, paper_id: str, run_id: str) -> tuple[dict, dict]:
    run_meta = {
        "paper_id": paper_id,
        "run_id": run_id,
        "parser_backend": "fitz_pdfplumber",
        "status": "succeeded",
        "finished_at": "2026-04-08T13:00:00+00:00",
        "reader_timeout_triggered": False,
        "reader_analysis": {
            "configured_attempt_order": "current",
            "effective_attempt_order": ["primary", "focused"],
            "attempt_count": 1,
            "return_mode": "success",
            "selected_attempt": 1,
            "selected_attempt_label": "primary",
            "final_claim_count": 1,
            "used_heuristic_fallback": False,
            "attempts": [
                {
                    "attempt_idx": 1,
                    "label": "primary",
                    "status": "parsed",
                    "context_mode": "chunk_context",
                    "context_chars": 12000,
                    "prompt_chars": 15000,
                    "estimated_prompt_tokens": 3750,
                    "estimated_response_tokens": 200,
                    "included_chunk_count": 10,
                    "unique_section_count": 2,
                    "unique_page_hint_count": 2,
                    "sentence_focus_count": 0,
                    "truncated_chunk_count": 0,
                }
            ],
        },
    }
    bootstrap_meta = {
        "paper_id": paper_id,
        "run_id": run_id,
        "run_verify": True,
        "claimset_ready": True,
        "claimset_readiness": "ready",
        "claimset_ops_action": "none",
        "artifact_claimset_resolved_written": True,
        "artifact_reader_eval_written": True,
        "verifier_status": "failed",
        "reader_eval_bbox_span_count": 1,
        "reader_eval_text_match_span_count": 0,
        "reader_eval_approx_span_count": 0,
        "reader_eval_unresolved_span_count": 0,
        "reader_eval_ambiguous_span_count": 0,
        "reader_timeout_triggered": False,
        "reader_analysis": run_meta["reader_analysis"],
    }
    return run_meta, bootstrap_meta


def _write_stale_handoff_run(run_dir: Path, *, paper_id: str, run_id: str) -> None:
    run_meta, bootstrap_meta = _stale_run_payloads(paper_id=paper_id, run_id=run_id)
    _write_json(run_dir / "run_meta.json", run_meta)
    _write_json(run_dir / "bootstrap_meta.json", bootstrap_meta)
    _write_json(
        run_dir / "acceptance_contract.json",
        {
            "schema_version": "2026-03-27.deepread-handoff.v1",
            "workflow": "deep_read",
            "paper_id": paper_id,
            "run_id": run_id,
            "acceptance_checks": [],
        },
    )
    _write_json(
        run_dir / "quality_gate.json",
        {
            "schema_version": "2026-03-27.deepread-handoff.v1",
            "workflow": "deep_read",
            "paper_id": paper_id,
            "run_id": run_id,
            "overall_status": "warn",
            "current_promotion_candidate": True,
            "review_ready": False,
            "reason_codes": ["VERIFIER_FAILED"],
            "checks": [],
        },
    )
    _write_json(
        run_dir / "context_manifest.json",
        {
            "schema_version": "2026-04-01.deepread-context-manifest.v1",
            "workflow": "deep_read",
            "paper_id": paper_id,
            "run_id": run_id,
            "attempt_count": 1,
            "attempts": [],
        },
    )


def test_run_backfill_deepread_handoff_dry_run_and_apply(tmp_path: Path) -> None:
    run_dir = tmp_path / "artifacts" / "paper-a" / "run-1"
    _write_stale_handoff_run(run_dir, paper_id="paper-a", run_id="run-1")

    dry = run_backfill(run_dirs=[run_dir], apply_changes=False)
    assert dry.runs_scanned == 1
    assert dry.runs_needing_update == 1
    assert dry.runs_updated == 0
    assert dry.acceptance_contract_needing_update == 1
    assert dry.quality_gate_needing_update == 1
    assert dry.context_manifest_needing_update == 1
    quality_gate_after_dry = json.loads((run_dir / "quality_gate.json").read_text(encoding="utf-8"))
    assert quality_gate_after_dry["schema_version"] == "2026-03-27.deepread-handoff.v1"

    applied = run_backfill(run_dirs=[run_dir], apply_changes=True)
    assert applied.runs_updated == 1
    assert applied.acceptance_contract_updated == 1
    assert applied.quality_gate_updated == 1
    assert applied.context_manifest_updated == 1

    acceptance_contract = json.loads((run_dir / "acceptance_contract.json").read_text(encoding="utf-8"))
    quality_gate = json.loads((run_dir / "quality_gate.json").read_text(encoding="utf-8"))
    context_manifest = json.loads((run_dir / "context_manifest.json").read_text(encoding="utf-8"))

    assert acceptance_contract["hard_fail_conditions"] == [
        {
            "code": "RUN_NOT_SUCCEEDED",
            "source": "run_meta.status",
            "description": "The deep-read run did not reach succeeded state.",
        },
        {
            "code": "MISSING_CLAIMSET_RESOLVED",
            "source": "bootstrap_meta.artifact_claimset_resolved_written",
            "description": "Resolved claimset artifact is missing, so promotion cannot proceed.",
        },
    ]
    assert quality_gate["schema_version"] == "2026-04-08.deepread-handoff.v2"
    assert quality_gate["step_stability_summary"]["status"] == "warn"
    assert quality_gate["step_stability_summary"]["reason_codes"] == ["VERIFIER_FAILED"]
    assert quality_gate["failure_recovery_summary"]["status"] == "pass"
    assert context_manifest["schema_version"] == "2026-04-08.deepread-context-manifest.v2"
    assert context_manifest["goal_drift_summary"]["status"] == "pass"

    second = run_backfill(run_dirs=[run_dir], apply_changes=True)
    assert second.runs_needing_update == 0
    assert second.runs_updated == 0


def test_resolve_run_dirs_supports_manifest_and_filters(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_a = artifacts_root / "paper-a" / "run-1"
    run_b = artifacts_root / "paper-b" / "run-2"
    _write_stale_handoff_run(run_a, paper_id="paper-a", run_id="run-1")
    _write_stale_handoff_run(run_b, paper_id="paper-b", run_id="run-2")
    manifest_path = tmp_path / "manifests" / "deepread_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": "deepread_handoff_manifest.v1",
            "manifest_batch_id": "test_manifest",
            "runs": [
                {"run_dir": str(run_a), "paper_id": "paper-a", "run_id": "run-1"},
            ],
        },
    )

    resolved = resolve_run_dirs(
        artifacts_root=artifacts_root,
        manifest_paths=[manifest_path],
        explicit_run_dirs=[],
        paper_ids=None,
    )

    assert resolved == [run_a.resolve()]
