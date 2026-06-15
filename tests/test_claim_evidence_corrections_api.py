from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend import main as api_main
from src.schemas.claim_evidence_correction import ClaimEvidenceCorrectionCase
from src.schemas.evidence_grounding_scorecard import KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES
from src.schemas.paper_understanding_failures import (
    PAPER_UNDERSTANDING_FAILURE_DEFINITIONS,
    failure_definition_for,
)
from src.services.claim_evidence_corrections import (
    build_claim_evidence_correction_repaired_log_draft,
    build_claim_evidence_correction_repair_patch_template,
)


def _payload(**updates):
    payload = {
        "paper_id": "paper-correction-001",
        "run_id": "run-correction-001",
        "claim_id": "CLM-001",
        "field_path": "claims[0]",
        "before_claim_text": "The biomarker proves disease conversion.",
        "after_claim_text": "The biomarker was associated with disease conversion in this cohort.",
        "before_evidence_refs": [
            {
                "page": 4,
                "chunk_id": "p04_c01",
                "quote": "biomarker values differed by group",
                "rationale": "The old evidence was weaker than the claim.",
            }
        ],
        "after_evidence_refs": [
            {
                "page": 4,
                "chunk_id": "p04_c01",
                "char_start": 20,
                "char_end": 80,
                "quote": "biomarker values were associated with conversion",
                "rationale": "This supports association, not proof.",
            }
        ],
        "reason_codes": ["OVERSTATED_RESULT", "WRONG_EVIDENCE"],
        "reviewer_id": "reviewer-001",
        "parser_version": "parser-v1",
        "llm_provider": "local",
        "llm_model": "reader-model",
        "llm_model_version": "reader-model-2026-05-22",
        "prompt_version": "prompt-v1",
        "reader_profile_version": "reader-profile-v1",
        "accepted_for_eval": True,
        "related_feedback_id": "feedback-001",
        "metadata": {"source": "manual-review"},
    }
    payload.update(updates)
    return payload


def test_failure_taxonomy_definitions_cover_all_codes():
    assert "OVERSTATED_RESULT" in PAPER_UNDERSTANDING_FAILURE_DEFINITIONS
    definition = failure_definition_for("OVERSTATED_RESULT")
    assert definition.code == "OVERSTATED_RESULT"
    assert "stronger" in definition.definition
    assert definition.smallest_fix_direction
    assert set(KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES) == set(PAPER_UNDERSTANDING_FAILURE_DEFINITIONS)


def test_claim_evidence_correction_schema_links_feedback_status_when_feedback_id_present():
    correction = ClaimEvidenceCorrectionCase.model_validate(_payload(feedback_export_status="not_applicable"))

    assert correction.feedback_export_status == "linked"
    assert correction.related_feedback_id == "feedback-001"
    assert correction.accepted_for_eval is True


def test_claim_evidence_correction_schema_requires_feedback_id_for_linked_status():
    payload = _payload(related_feedback_id=None, feedback_export_status="linked")

    with pytest.raises(ValidationError, match="feedback_export_status=linked requires related_feedback_id"):
        ClaimEvidenceCorrectionCase.model_validate(payload)


def test_claim_evidence_correction_schema_requires_replay_lineage_when_accepted_for_eval():
    payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        accepted_for_eval=True,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
    )

    with pytest.raises(ValidationError, match="accepted_for_eval requires parser_version"):
        ClaimEvidenceCorrectionCase.model_validate(payload)


def test_claim_evidence_correction_post_rejects_eval_acceptance_without_replay_lineage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        accepted_for_eval=True,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
    )

    resp = client.post("/claim-evidence-corrections", json=payload)

    assert resp.status_code == 422
    assert not Path("storage/claim_evidence_corrections.jsonl").exists()


def test_claim_evidence_correction_post_persists_and_sanitizes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    payload = _payload(
        before_claim_text="Authorization: Bearer correction-token-123",
        after_claim_text="Use corrected claim without sk-proj-correction-secret-abcdef.",
        metadata={"api_key": "correction-metadata-key"},
    )

    resp = client.post("/claim-evidence-corrections", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "saved"
    assert body["feedback_export_status"] == "linked"

    correction_file = Path("storage/claim_evidence_corrections.jsonl")
    assert correction_file.exists()
    raw_file = correction_file.read_text(encoding="utf-8")
    assert "correction-token-123" not in raw_file
    assert "sk-proj-correction-secret-abcdef" not in raw_file
    assert "correction-metadata-key" not in raw_file

    saved = json.loads(raw_file.strip())
    assert saved["before_claim_text"] == "Authorization: <redacted>"
    assert saved["after_claim_text"] == "Use corrected claim without <redacted>."
    assert saved["metadata"]["api_key"] == "<redacted>"
    assert saved["feedback_export_status"] == "linked"
    assert saved["llm_model_version"] == "reader-model-2026-05-22"
    assert saved["reader_profile_version"] == "reader-profile-v1"
    assert isinstance(saved["created_at"], str)


def test_claim_evidence_correction_get_filters_latest_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    older = _payload(
        paper_id="paper-correction-002",
        run_id="run-older",
        claim_id="CLM-OLD",
        reason_codes=["WRONG_LOCATOR"],
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=False,
    )
    newer = _payload(
        paper_id="paper-correction-002",
        run_id="run-newer",
        claim_id="CLM-NEW",
        reason_codes=["LIMITATION_MISSED"],
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    other = _payload(paper_id="paper-correction-other", run_id="run-other", claim_id="CLM-OTHER")
    for item in (older, newer, other):
        resp = client.post("/claim-evidence-corrections", json=item)
        assert resp.status_code == 200

    listed = client.get(
        "/claim-evidence-corrections",
        params={"paper_id": "paper-correction-002", "reason_code": "LIMITATION_MISSED"},
    )

    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["claim_id"] == "CLM-NEW"
    assert items[0]["feedback_export_status"] == "linked"
    assert items[0]["related_feedback_id"]

    limited = client.get("/claim-evidence-corrections", params={"paper_id": "paper-correction-002", "limit": 1})
    assert limited.status_code == 200
    assert limited.json()[0]["run_id"] == "run-newer"

    linked_eval_candidates = client.get(
        "/claim-evidence-corrections",
        params={
            "paper_id": "paper-correction-002",
            "accepted_for_eval": True,
            "feedback_export_status": "linked",
        },
    )
    assert linked_eval_candidates.status_code == 200
    linked_items = linked_eval_candidates.json()
    assert len(linked_items) == 1
    assert linked_items[0]["run_id"] == "run-newer"

    invalid_status = client.get(
        "/claim-evidence-corrections",
        params={"feedback_export_status": "exported_elsewhere"},
    )
    assert invalid_status.status_code == 422


def test_claim_evidence_correction_accept_for_eval_exports_artifact_feedback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    payload = _payload(
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
        reason_codes=["UNSUPPORTED_CLAIM"],
    )
    resp = client.post("/claim-evidence-corrections", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["feedback_export_status"] == "linked"
    assert body["related_feedback_id"]

    correction_file = Path("storage/claim_evidence_corrections.jsonl")
    saved_correction = json.loads(correction_file.read_text(encoding="utf-8").strip())
    assert saved_correction["related_feedback_id"] == body["related_feedback_id"]
    assert saved_correction["feedback_export_status"] == "linked"

    feedback_file = Path("storage/artifact_review_feedback.jsonl")
    assert feedback_file.exists()
    saved_feedback = json.loads(feedback_file.read_text(encoding="utf-8").strip())
    assert saved_feedback["feedback_id"] == body["related_feedback_id"]
    assert saved_feedback["artifact_type"] == "evidence_grounding_scorecard"
    assert saved_feedback["artifact_id"] == "paper-correction-001:run-correction-001:evidence_grounding_scorecard"
    assert saved_feedback["decision"] == "correct"
    assert saved_feedback["reason_code"] == "claim_evidence_correction"
    assert saved_feedback["metadata"]["source"] == "claim_evidence_correction"
    assert saved_feedback["metadata"]["correction_id"] == body["correction_id"]
    assert saved_feedback["metadata"]["reason_codes"] == ["UNSUPPORTED_CLAIM"]


def test_claim_evidence_eval_candidates_export_route_only_returns_accepted_candidates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)

    accepted = _payload(
        paper_id="paper-correction-export",
        run_id="run-export-newer",
        claim_id="CLM-EXPORT-NEW",
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
        reason_codes=["WRONG_EVIDENCE"],
    )
    ignored = _payload(
        paper_id="paper-correction-export",
        run_id="run-export-ignored",
        claim_id="CLM-EXPORT-OLD",
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=False,
        reason_codes=["WRONG_EVIDENCE"],
    )
    for item in (ignored, accepted):
        resp = client.post("/claim-evidence-corrections", json=item)
        assert resp.status_code == 200
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    with correction_log.open("a", encoding="utf-8") as handle:
        handle.write("{not-json}\n")

    exported = client.get(
        "/claim-evidence-corrections/eval-candidates",
        params={
            "paper_id": "paper-correction-export",
            "reason_code": "WRONG_EVIDENCE",
            "feedback_export_status": "linked",
        },
    )

    assert exported.status_code == 200
    payload = exported.json()
    assert payload["schema_version"] == "claim_evidence_eval_candidate_export.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["candidate_count"] == 1
    assert payload["source_record_count"] == 3
    assert payload["source_valid_record_count"] == 2
    assert payload["source_invalid_record_count"] == 1
    assert payload["skipped_not_accepted_count"] == 1
    assert payload["skipped_filter_count"] == 0
    assert payload["skipped_limit_count"] == 0
    assert payload["source_invalid_record_diagnostics"][0]["line_number"] == 3
    assert payload["source_invalid_record_diagnostics"][0]["error_type"]
    assert payload["source_invalid_record_diagnostics"][0]["detail"]
    assert payload["source_invalid_record_diagnostics"][0]["missing_replay_fields"] == []
    assert payload["filters"]["accepted_for_eval"] is True
    assert payload["filters"]["feedback_export_status"] == "linked"
    candidate = payload["candidates"][0]
    assert candidate["schema_version"] == "claim_evidence_eval_candidate.v1"
    assert candidate["canonical_status"] == "non_canonical"
    assert candidate["paper_id"] == "paper-correction-export"
    assert candidate["run_id"] == "run-export-newer"
    assert candidate["claim_id"] == "CLM-EXPORT-NEW"
    assert candidate["reason_codes"] == ["WRONG_EVIDENCE"]
    assert candidate["llm_model_version"] == "reader-model-2026-05-22"
    assert candidate["reader_profile_version"] == "reader-profile-v1"
    assert candidate["source_feedback_id"]


def test_claim_evidence_eval_candidates_export_route_can_require_replayable_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    run_dir = tmp_path / "storage/artifacts/paper-correction-001/run-correction-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-from-run",
                "inference_lanes": {
                    "clinical_extraction": {
                        "provider_name": "openai",
                        "provider_model": "gpt-test",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    exported = client.get(
        "/claim-evidence-corrections/eval-candidates",
        params={"require_replayable": True},
    )

    assert exported.status_code == 409
    detail = exported.json()["detail"]
    assert detail["message"] == "Claim/evidence eval candidate export is not replayable evidence."
    assert "source_invalid_records" in detail["findings"]
    assert "no_replayable_candidates" in detail["findings"]
    assert detail["source_correction_log_path"].endswith("storage/claim_evidence_corrections.jsonl")
    assert detail["source_invalid_record_count"] == 1
    assert detail["source_invalid_record_diagnostics"][0]["line_number"] == 1
    assert detail["source_invalid_record_diagnostics"][0]["source_correction_id"] is None
    assert detail["source_invalid_record_diagnostics"][0]["paper_id"] == "paper-correction-001"
    assert detail["source_invalid_record_diagnostics"][0]["run_id"] == "run-correction-001"
    assert detail["source_invalid_record_diagnostics"][0]["claim_id"] == "CLM-001"
    assert detail["source_invalid_record_diagnostics"][0]["missing_replay_fields"] == [
        "parser_version",
        "llm_provider",
        "llm_model",
        "llm_model_version",
        "prompt_version",
        "reader_profile_version",
    ]


def test_claim_evidence_correction_repair_plan_route_exports_invalid_accepted_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
        metadata={
            "source": "manual-review",
            "eval_lineage_available": False,
            "private_note": "do not export",
        },
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    run_dir = tmp_path / "storage/artifacts/paper-correction-001/run-correction-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "parser_version": "parser-from-run",
                "status": "completed",
                "payload_class": "mixed",
                "redaction_applied": True,
                "inference_lanes": {
                    "clinical_extraction": {
                        "payload_class": "external_allowed",
                        "redaction_applied": True,
                        "provider_name": "openai",
                        "provider_model": "gpt-test",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    exported = client.get("/claim-evidence-corrections/repair-plan")

    assert exported.status_code == 200
    payload = exported.json()
    assert payload["schema_version"] == "claim_evidence_correction_repair_plan.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["source_correction_log_path"] == str(correction_log.resolve())
    assert payload["source_record_count"] == 1
    assert payload["source_valid_record_count"] == 0
    assert payload["source_invalid_record_count"] == 1
    assert payload["repair_target_count"] == 1
    assert payload["warnings"] == []
    target = payload["targets"][0]
    assert target["line_number"] == 1
    assert target["source_correction_id"] is None
    assert target["paper_id"] == "paper-correction-001"
    assert target["run_id"] == "run-correction-001"
    assert target["claim_id"] == "CLM-001"
    assert target["reason_codes"] == ["OVERSTATED_RESULT", "WRONG_EVIDENCE"]
    assert target["available_replay_context"] == {
        "run_meta.inference_lanes.clinical_extraction.provider_model": "gpt-test",
        "run_meta.inference_lanes.clinical_extraction.provider_name": "openai",
        "run_meta.inference_lanes.clinical_extraction.payload_class": "external_allowed",
        "run_meta.inference_lanes.clinical_extraction.redaction_applied": "true",
        "run_meta.payload_class": "mixed",
        "run_meta.parser_version": "parser-from-run",
        "run_meta.redaction_applied": "true",
        "run_meta.status": "completed",
        "source_record.metadata.eval_lineage_available": "false",
        "source_record.metadata.source": "manual-review",
    }
    assert "source_record.metadata.private_note" not in target["available_replay_context"]
    assert target["missing_replay_fields"] == [
        "parser_version",
        "llm_provider",
        "llm_model",
        "llm_model_version",
        "prompt_version",
        "reader_profile_version",
    ]
    assert "accepted_for_eval requires parser_version" in target["detail"]


def test_claim_evidence_correction_repair_patch_template_route_exports_from_repair_plan(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    run_dir = tmp_path / "storage/artifacts/paper-correction-001/run-correction-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "reader_profile_version": "reader-profile-from-run",
                "inference_lanes": {
                    "clinical_extraction": {
                        "provider_name": "openai",
                        "provider_model": "gpt-test",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    repair_plan_path = tmp_path / "repair_plan.json"
    repair_plan = client.get("/claim-evidence-corrections/repair-plan")
    assert repair_plan.status_code == 200
    repair_plan_path.write_text(json.dumps(repair_plan.json()), encoding="utf-8")

    exported = client.get(
        "/claim-evidence-corrections/repair-patch-template",
        params={"repair_plan_path": str(repair_plan_path)},
    )

    assert exported.status_code == 200
    payload = exported.json()
    assert payload["schema_version"] == "claim_evidence_correction_repair_patch_template.v1"
    assert payload["layer"] == "review_gate_artifact"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["source_repair_plan_path"] == str(repair_plan_path.resolve())
    assert payload["source_correction_log_path"] == str(correction_log.resolve())
    assert payload["target_count"] == 1
    record = payload["records"][0]
    assert record["source_record"]["paper_id"] == "paper-correction-001"
    assert record["patch_fields"]["parser_version"] == ""
    assert record["suggested_lineage_values"] == {
        "llm_provider": "openai",
        "llm_model": "gpt-test",
        "reader_profile_version": "reader-profile-from-run",
    }


def test_claim_evidence_eval_candidates_export_script_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    resp = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-cli-export",
            run_id="run-cli-export",
            claim_id="CLM-CLI-EXPORT",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["LIMITATION_MISSED"],
        ),
    )
    assert resp.status_code == 200

    out = tmp_path / "eval_candidates.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/export_claim_evidence_eval_candidates.py"),
            "--log-path",
            str(tmp_path / "storage/claim_evidence_corrections.jsonl"),
            "--out",
            str(out),
            "--jsonl",
            "--paper-id",
            "paper-correction-cli-export",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "[claim_evidence_eval_candidates] candidate_count=1" in result.stdout
    assert "[claim_evidence_eval_candidates] source_record_count=1" in result.stdout
    assert "[claim_evidence_eval_candidates] source_invalid_record_count=0" in result.stdout
    assert "[claim_evidence_eval_candidates] source_invalid_record_lines=" not in result.stdout
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["schema_version"] == "claim_evidence_eval_candidate.v1"
    assert rows[0]["claim_id"] == "CLM-CLI-EXPORT"
    assert rows[0]["reason_codes"] == ["LIMITATION_MISSED"]


def test_claim_evidence_eval_candidates_export_script_can_require_replayable_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    run_dir = tmp_path / "storage/artifacts/paper-correction-001/run-correction-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "reader_profile_version": "reader-profile-from-run",
                "inference_lanes": {
                    "reader": {"selected_backend": "local"},
                    "clinical_extraction": {
                        "provider_name": "openai",
                        "provider_model": "gpt-test",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "eval_candidates.json"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/export_claim_evidence_eval_candidates.py"),
            "--log-path",
            str(correction_log),
            "--out",
            str(out),
            "--require-replayable",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert out.exists()
    assert "[claim_evidence_eval_candidates] replayable_evidence=false" in result.stdout
    assert f"[claim_evidence_eval_candidates] source_correction_log_path={correction_log.resolve()}" in result.stdout
    assert "[claim_evidence_eval_candidates] blocking_findings=source_invalid_records,no_replayable_candidates" in result.stdout
    assert (
        "[claim_evidence_eval_candidates] source_invalid_record_missing_replay_fields="
        "line_1:parser_version,llm_provider,llm_model,llm_model_version,prompt_version,reader_profile_version"
        in result.stdout
    )
    assert (
        "[claim_evidence_eval_candidates] source_invalid_record_repair_targets="
        "line_1:paper_id=paper-correction-001,run_id=run-correction-001,claim_id=CLM-001"
        in result.stdout
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 0
    assert payload["source_correction_log_path"] == str(correction_log.resolve())
    assert payload["source_invalid_record_count"] == 1
    assert payload["source_invalid_record_missing_replay_fields_by_line"] == {
        "line_1": [
            "parser_version",
            "llm_provider",
            "llm_model",
            "llm_model_version",
            "prompt_version",
            "reader_profile_version",
        ]
    }
    assert payload["source_invalid_record_repair_targets_by_line"] == {
        "line_1": {
            "paper_id": "paper-correction-001",
            "run_id": "run-correction-001",
            "claim_id": "CLM-001",
        }
    }
    assert payload["source_invalid_record_diagnostics"][0]["source_correction_id"] is None
    assert payload["source_invalid_record_diagnostics"][0]["paper_id"] == "paper-correction-001"
    assert payload["source_invalid_record_diagnostics"][0]["run_id"] == "run-correction-001"
    assert payload["source_invalid_record_diagnostics"][0]["claim_id"] == "CLM-001"
    assert payload["source_invalid_record_diagnostics"][0]["missing_replay_fields"] == [
        "parser_version",
        "llm_provider",
        "llm_model",
        "llm_model_version",
        "prompt_version",
        "reader_profile_version",
    ]


def test_claim_evidence_correction_repair_plan_script_exports_successfully_with_targets(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    run_dir = tmp_path / "storage/artifacts/paper-correction-001/run-correction-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "reader_profile_version": "reader-profile-from-run",
                "inference_lanes": {
                    "reader": {"selected_backend": "local"},
                    "clinical_extraction": {
                        "provider_name": "openai",
                        "provider_model": "gpt-test",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "repair_plan.json"
    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_plan.py"
            ),
            "--log-path",
            str(correction_log),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "[claim_evidence_correction_repair_plan] source_record_count=1" in result.stdout
    assert "[claim_evidence_correction_repair_plan] source_invalid_record_count=1" in result.stdout
    assert "[claim_evidence_correction_repair_plan] repair_target_count=1" in result.stdout
    assert (
        "[claim_evidence_correction_repair_plan] repair_targets="
        "line_1:paper_id=paper-correction-001,run_id=run-correction-001,claim_id=CLM-001"
        in result.stdout
    )
    assert (
        "[claim_evidence_correction_repair_plan] missing_replay_fields="
        "line_1:parser_version,llm_provider,llm_model,llm_model_version,prompt_version,reader_profile_version"
        in result.stdout
    )
    assert (
        "[claim_evidence_correction_repair_plan] reason_codes="
        "line_1:OVERSTATED_RESULT,WRONG_EVIDENCE"
        in result.stdout
    )
    assert (
        "[claim_evidence_correction_repair_plan] available_replay_context="
        "line_1:run_meta.inference_lanes.clinical_extraction.provider_model=gpt-test,"
        "run_meta.inference_lanes.clinical_extraction.provider_name=openai,"
        "run_meta.inference_lanes.reader.selected_backend=local,"
        "run_meta.reader_profile_version=reader-profile-from-run"
        in result.stdout
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "claim_evidence_correction_repair_plan.v1"
    assert payload["repair_target_count"] == 1
    assert payload["targets"][0]["reason_codes"] == ["OVERSTATED_RESULT", "WRONG_EVIDENCE"]
    assert payload["targets"][0]["available_replay_context"] == {
        "run_meta.inference_lanes.clinical_extraction.provider_model": "gpt-test",
        "run_meta.inference_lanes.clinical_extraction.provider_name": "openai",
        "run_meta.inference_lanes.reader.selected_backend": "local",
        "run_meta.reader_profile_version": "reader-profile-from-run",
        "source_record.metadata.source": "manual-review",
    }
    assert payload["targets"][0]["missing_replay_fields"] == [
        "parser_version",
        "llm_provider",
        "llm_model",
        "llm_model_version",
        "prompt_version",
        "reader_profile_version",
    ]


def test_claim_evidence_correction_repair_patch_template_preserves_source_and_suggestions(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    run_dir = tmp_path / "storage/artifacts/paper-correction-001/run-correction-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "reader_profile_version": "reader-profile-from-run",
                "inference_lanes": {
                    "clinical_extraction": {
                        "provider_name": "openai",
                        "provider_model": "gpt-test",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    repair_plan = tmp_path / "repair_plan.json"
    subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_plan.py"
            ),
            "--log-path",
            str(correction_log),
            "--out",
            str(repair_plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    template = build_claim_evidence_correction_repair_patch_template(
        repair_plan_path=repair_plan,
    )

    assert template.schema_version == "claim_evidence_correction_repair_patch_template.v1"
    assert template.canonical_status == "non_canonical"
    assert template.target_count == 1
    record = template.records[0]
    assert record.review_required is True
    assert record.source_record["paper_id"] == "paper-correction-001"
    assert record.patch_fields == {
        "parser_version": "",
        "llm_provider": "",
        "llm_model": "",
        "llm_model_version": "",
        "prompt_version": "",
        "reader_profile_version": "",
    }
    assert record.patch_record["before_claim_text"] == legacy_payload["before_claim_text"]
    assert record.patch_record["parser_version"] == ""
    assert record.suggested_lineage_values == {
        "llm_provider": "openai",
        "llm_model": "gpt-test",
        "reader_profile_version": "reader-profile-from-run",
    }


def test_claim_evidence_correction_repair_patch_template_script_exports_successfully(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    repair_plan = tmp_path / "repair_plan.json"
    template_out = tmp_path / "repair_patch_template.json"
    subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_plan.py"
            ),
            "--log-path",
            str(correction_log),
            "--out",
            str(repair_plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_patch_template.py"
            ),
            "--repair-plan",
            str(repair_plan),
            "--out",
            str(template_out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "[claim_evidence_correction_repair_patch_template] target_count=1" in result.stdout
    assert f"out=./{template_out.name}" in result.stdout
    assert str(tmp_path) not in result.stdout
    payload = json.loads(template_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "claim_evidence_correction_repair_patch_template.v1"
    assert payload["target_count"] == 1


def test_claim_evidence_correction_repaired_log_draft_rejects_blank_patch_fields(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    repair_plan = tmp_path / "repair_plan.json"
    template_out = tmp_path / "repair_patch_template.json"
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/export_claim_evidence_correction_repair_plan.py"),
            "--log-path",
            str(correction_log),
            "--out",
            str(repair_plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_patch_template.py"
            ),
            "--repair-plan",
            str(repair_plan),
            "--out",
            str(template_out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    with pytest.raises(ValueError, match="repair_patch_fields_blank"):
        build_claim_evidence_correction_repaired_log_draft(
            patch_template_path=template_out,
            out_log_path=tmp_path / "repaired.jsonl",
        )

    assert not (tmp_path / "repaired.jsonl").exists()


def test_claim_evidence_correction_repaired_log_draft_writes_replayable_jsonl(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    repair_plan = tmp_path / "repair_plan.json"
    template_out = tmp_path / "repair_patch_template.json"
    repaired_log = tmp_path / "repaired_claim_evidence_corrections.jsonl"
    summary_out = tmp_path / "repaired_claim_evidence_corrections_summary.json"
    summary_out = tmp_path / "repaired_log_draft.json"
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/export_claim_evidence_correction_repair_plan.py"),
            "--log-path",
            str(correction_log),
            "--out",
            str(repair_plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_patch_template.py"
            ),
            "--repair-plan",
            str(repair_plan),
            "--out",
            str(template_out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    template_payload = json.loads(template_out.read_text(encoding="utf-8"))
    template_payload["records"][0]["patch_fields"] = {
        "parser_version": "parser-v1",
        "llm_provider": "openai",
        "llm_model": "gpt-test",
        "llm_model_version": "gpt-test-2026-05-25",
        "prompt_version": "prompt-v1",
        "reader_profile_version": "reader-profile-v1",
    }
    template_out.write_text(json.dumps(template_payload), encoding="utf-8")

    draft = build_claim_evidence_correction_repaired_log_draft(
        patch_template_path=template_out,
        out_log_path=repaired_log,
        summary_out=summary_out,
    )

    assert draft.schema_version == "claim_evidence_correction_repaired_log_draft.v1"
    assert draft.canonical_status == "non_canonical"
    assert draft.record_count == 1
    assert draft.repaired_record_count == 1
    assert repaired_log.exists()
    repaired_payload = json.loads(repaired_log.read_text(encoding="utf-8").strip())
    assert repaired_payload["paper_id"] == "paper-correction-001"
    assert repaired_payload["parser_version"] == "parser-v1"
    assert repaired_payload["feedback_export_status"] == "pending"
    assert json.loads(summary_out.read_text(encoding="utf-8"))["repaired_record_count"] == 1


def test_claim_evidence_correction_repaired_log_draft_script_writes_replayable_jsonl(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    repair_plan = tmp_path / "repair_plan.json"
    template_out = tmp_path / "repair_patch_template.json"
    repaired_log = tmp_path / "repaired_claim_evidence_corrections.jsonl"
    summary_out = tmp_path / "repaired_log_draft.json"
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/export_claim_evidence_correction_repair_plan.py"),
            "--log-path",
            str(correction_log),
            "--out",
            str(repair_plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_patch_template.py"
            ),
            "--repair-plan",
            str(repair_plan),
            "--out",
            str(template_out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    template_payload = json.loads(template_out.read_text(encoding="utf-8"))
    template_payload["records"][0]["patch_fields"] = {
        "parser_version": "parser-v1",
        "llm_provider": "openai",
        "llm_model": "gpt-test",
        "llm_model_version": "gpt-test-2026-05-25",
        "prompt_version": "prompt-v1",
        "reader_profile_version": "reader-profile-v1",
    }
    template_out.write_text(json.dumps(template_payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/draft_claim_evidence_correction_repaired_log.py"
            ),
            "--patch-template",
            str(template_out),
            "--out-log",
            str(repaired_log),
            "--summary-out",
            str(summary_out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "[claim_evidence_correction_repaired_log_draft] repaired_record_count=1" in result.stdout
    assert f".../{repaired_log.name}" in result.stdout or f"./{repaired_log.name}" in result.stdout
    assert str(tmp_path) not in result.stdout
    assert repaired_log.exists()
    assert json.loads(summary_out.read_text(encoding="utf-8"))["schema_version"] == (
        "claim_evidence_correction_repaired_log_draft.v1"
    )


def test_claim_evidence_correction_repaired_log_draft_script_reports_blank_fields_without_traceback(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    repair_plan = tmp_path / "repair_plan.json"
    template_out = tmp_path / "repair_patch_template.json"
    repaired_log = tmp_path / "repaired_claim_evidence_corrections.jsonl"
    summary_out = tmp_path / "repaired_claim_evidence_corrections_summary.json"
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/export_claim_evidence_correction_repair_plan.py"),
            "--log-path",
            str(correction_log),
            "--out",
            str(repair_plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/export_claim_evidence_correction_repair_patch_template.py"
            ),
            "--repair-plan",
            str(repair_plan),
            "--out",
            str(template_out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "scripts/eval/draft_claim_evidence_correction_repaired_log.py"
            ),
            "--patch-template",
            str(template_out),
            "--out-log",
            str(repaired_log),
            "--summary-out",
            str(summary_out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "[claim_evidence_correction_repaired_log_draft] error=repair_patch_fields_blank" in result.stderr
    assert "repair_patch_fields_blank" in result.stderr
    assert "Traceback" not in result.stderr
    assert not repaired_log.exists()
    assert not summary_out.exists()


def test_claim_evidence_correction_repaired_log_draft_api_writes_summary(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    repair_plan = client.get("/claim-evidence-corrections/repair-plan")
    repair_plan_path = tmp_path / "repair_plan.json"
    repair_plan_path.write_text(json.dumps(repair_plan.json()), encoding="utf-8")
    template = client.get(
        "/claim-evidence-corrections/repair-patch-template",
        params={"repair_plan_path": str(repair_plan_path)},
    )
    template_path = tmp_path / "repair_patch_template.json"
    template_payload = template.json()
    template_payload["records"][0]["patch_fields"] = {
        "parser_version": "parser-v1",
        "llm_provider": "openai",
        "llm_model": "gpt-test",
        "llm_model_version": "gpt-test-2026-05-25",
        "prompt_version": "prompt-v1",
        "reader_profile_version": "reader-profile-v1",
    }
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")
    repaired_log = tmp_path / "repaired_claim_evidence_corrections.jsonl"
    summary_out = tmp_path / "repaired_log_draft.json"

    response = client.get(
        "/claim-evidence-corrections/repaired-log-draft",
        params={
            "patch_template_path": str(template_path),
            "out_log_path": str(repaired_log),
            "summary_out": str(summary_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "claim_evidence_correction_repaired_log_draft.v1"
    assert payload["record_count"] == 1
    assert payload["repaired_record_count"] == 1
    assert repaired_log.exists()
    assert summary_out.exists()


def test_claim_evidence_eval_candidates_import_script_writes_review_intake_not_accepted_gold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    resp = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-intake",
            run_id="run-intake",
            claim_id="CLM-INTAKE",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["OVERSTATED_RESULT"],
        ),
    )
    assert resp.status_code == 200

    export_path = tmp_path / "eval_candidates.json"
    export_result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/export_claim_evidence_eval_candidates.py"),
            "--log-path",
            str(tmp_path / "storage/claim_evidence_corrections.jsonl"),
            "--out",
            str(export_path),
            "--paper-id",
            "paper-correction-intake",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert export_result.returncode == 0

    goldset_root = tmp_path / "goldset"
    import_result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert import_result.returncode == 0
    assert "[claim_evidence_eval_intake] record_count=1" in import_result.stdout
    intake_dir = goldset_root / "reviews" / "claim_evidence_eval_candidates"
    manifest = json.loads((intake_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "claim_evidence_eval_review_intake_manifest.v1"
    assert manifest["canonical_status"] == "non_canonical"
    assert manifest["record_count"] == 1
    assert manifest["source_export_path"] == str(export_path)
    record_path = Path(manifest["record_paths"][0])
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["schema_version"] == "claim_evidence_eval_review_intake.v1"
    assert record["review_status"] == "pending_review"
    assert record["canonical_status"] == "non_canonical"
    assert record["source_candidate"]["claim_id"] == "CLM-INTAKE"
    assert record["source_candidate"]["reason_codes"] == ["OVERSTATED_RESULT"]
    assert not (goldset_root / "accepted").exists()

    second_import = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert second_import.returncode == 0
    assert "[claim_evidence_eval_intake] record_count=0" in second_import.stdout
    assert "[claim_evidence_eval_intake] skipped_existing_count=1" in second_import.stdout


def test_claim_evidence_eval_candidates_import_api_writes_review_intake_not_accepted_gold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    resp = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-intake-api",
            run_id="run-intake-api",
            claim_id="CLM-INTAKE-API",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["WRONG_EVIDENCE"],
        ),
    )
    assert resp.status_code == 200
    export_resp = client.get(
        "/claim-evidence-corrections/eval-candidates",
        params={"paper_id": "paper-correction-intake-api"},
    )
    assert export_resp.status_code == 200
    export_path = tmp_path / "eval_candidates.json"
    export_path.write_text(json.dumps(export_resp.json()), encoding="utf-8")
    goldset_root = tmp_path / "goldset"

    imported = client.post(
        "/claim-evidence-corrections/eval-review-queue/import",
        json={
            "export_path": str(export_path),
            "goldset_root": str(goldset_root),
        },
    )

    assert imported.status_code == 200
    manifest = imported.json()
    assert manifest["schema_version"] == "claim_evidence_eval_review_intake_manifest.v1"
    assert manifest["canonical_status"] == "non_canonical"
    assert manifest["record_count"] == 1
    assert manifest["source_export_path"] == str(export_path.resolve())
    record = json.loads(Path(manifest["record_paths"][0]).read_text(encoding="utf-8"))
    assert record["schema_version"] == "claim_evidence_eval_review_intake.v1"
    assert record["canonical_status"] == "non_canonical"
    assert record["source_candidate"]["claim_id"] == "CLM-INTAKE-API"
    assert record["source_candidate"]["reason_codes"] == ["WRONG_EVIDENCE"]
    assert not (goldset_root / "accepted").exists()

    second_import = client.post(
        "/claim-evidence-corrections/eval-review-queue/import",
        json={
            "export_path": str(export_path),
            "goldset_root": str(goldset_root),
        },
    )
    assert second_import.status_code == 200
    assert second_import.json()["record_count"] == 0
    assert second_import.json()["skipped_existing_count"] == 1


def test_claim_evidence_eval_candidates_import_script_can_require_replayable_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    export_path = tmp_path / "eval_candidates_invalid_source.json"
    export_path.write_text(
        json.dumps(
            {
                "schema_version": "claim_evidence_eval_candidate_export.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": "2026-05-22T00:00:00Z",
                "candidate_count": 0,
                "source_record_count": 1,
                "source_valid_record_count": 0,
                "source_invalid_record_count": 1,
                "source_invalid_record_diagnostics": [
                    {
                        "line_number": 1,
                        "status": "invalid",
                        "error_type": "ValidationError",
                        "missing_replay_fields": ["parser_version"],
                    }
                ],
                "candidates": [],
            }
        ),
        encoding="utf-8",
    )
    goldset_root = tmp_path / "goldset"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
            "--require-replayable",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "[claim_evidence_eval_intake] replayable_evidence=false" in result.stdout
    assert "[claim_evidence_eval_intake] blocking_findings=source_invalid_records,no_replayable_candidates" in result.stdout
    assert not (goldset_root / "reviews" / "claim_evidence_eval_candidates" / "manifest.json").exists()


def test_claim_evidence_eval_candidates_import_script_rejects_export_without_reason_codes_when_replayable_required(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    export_path = tmp_path / "eval_candidates_missing_reason_codes.json"
    export_path.write_text(
        json.dumps(
            {
                "schema_version": "claim_evidence_eval_candidate_export.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": "2026-05-22T00:00:00Z",
                "candidate_count": 1,
                "source_record_count": 1,
                "source_valid_record_count": 1,
                "source_invalid_record_count": 0,
                "source_invalid_record_diagnostics": [],
                "candidates": [
                    {
                        "schema_version": "claim_evidence_eval_candidate.v1",
                        "layer": "review_gate_artifact",
                        "canonical_status": "non_canonical",
                        "source_correction_id": "correction-1",
                        "paper_id": "paper-1",
                        "run_id": "run-1",
                        "claim_id": "c1",
                        "field_path": "claims[0].text",
                        "before_claim_text": "Treatment proves broad benefit.",
                        "after_claim_text": "Treatment improved survival in the measured cohort.",
                        "before_evidence_refs": [{"page": 2, "quote": "Treatment improved survival."}],
                        "after_evidence_refs": [{"page": 2, "quote": "Treatment improved survival."}],
                        "reason_codes": [],
                        "parser_version": "parser-v2",
                        "llm_provider": "local",
                        "llm_model": "reader-model",
                        "llm_model_version": "reader-model-2026-05-22",
                        "prompt_version": "grounding-prompt-v2",
                        "reader_profile_version": "reader-profile-v2",
                        "reviewer_id": "reviewer-1",
                        "feedback_export_status": "pending",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    goldset_root = tmp_path / "goldset"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/eval/import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
            "--require-replayable",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "[claim_evidence_eval_intake] replayable_evidence=false" in result.stdout
    assert "[claim_evidence_eval_intake] blocking_findings=nonreplayable_candidates,no_replayable_candidates" in (
        result.stdout
    )
    assert not (goldset_root / "reviews" / "claim_evidence_eval_candidates" / "manifest.json").exists()


def test_claim_evidence_eval_candidates_import_api_can_require_replayable_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    export_path = tmp_path / "eval_candidates_invalid_source.json"
    export_path.write_text(
        json.dumps(
            {
                "schema_version": "claim_evidence_eval_candidate_export.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": "2026-05-22T00:00:00Z",
                "candidate_count": 0,
                "source_record_count": 1,
                "source_valid_record_count": 0,
                "source_invalid_record_count": 1,
                "source_invalid_record_diagnostics": [
                    {
                        "line_number": 1,
                        "status": "invalid",
                        "error_type": "ValidationError",
                        "missing_replay_fields": ["parser_version"],
                    }
                ],
                "candidates": [],
            }
        ),
        encoding="utf-8",
    )
    goldset_root = tmp_path / "goldset"

    imported = client.post(
        "/claim-evidence-corrections/eval-review-queue/import",
        json={
            "export_path": str(export_path),
            "goldset_root": str(goldset_root),
            "require_replayable": True,
        },
    )

    assert imported.status_code == 409
    detail = imported.json()["detail"]
    assert detail["message"] == "Claim/evidence eval candidate export is not replayable evidence."
    assert "source_invalid_records" in detail["findings"]
    assert "no_replayable_candidates" in detail["findings"]
    assert detail["source_invalid_record_count"] == 1
    assert detail["source_invalid_record_diagnostics"][0]["missing_replay_fields"] == ["parser_version"]
    assert not (goldset_root / "reviews" / "claim_evidence_eval_candidates" / "manifest.json").exists()


def test_claim_evidence_eval_candidates_import_api_rejects_export_without_reason_codes_when_replayable_required(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    export_path = tmp_path / "eval_candidates_missing_reason_codes.json"
    export_path.write_text(
        json.dumps(
            {
                "schema_version": "claim_evidence_eval_candidate_export.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": "2026-05-22T00:00:00Z",
                "candidate_count": 1,
                "source_record_count": 1,
                "source_valid_record_count": 1,
                "source_invalid_record_count": 0,
                "source_invalid_record_diagnostics": [],
                "candidates": [
                    {
                        "schema_version": "claim_evidence_eval_candidate.v1",
                        "layer": "review_gate_artifact",
                        "canonical_status": "non_canonical",
                        "source_correction_id": "correction-1",
                        "paper_id": "paper-1",
                        "run_id": "run-1",
                        "claim_id": "c1",
                        "field_path": "claims[0].text",
                        "before_claim_text": "Treatment proves broad benefit.",
                        "after_claim_text": "Treatment improved survival in the measured cohort.",
                        "before_evidence_refs": [{"page": 2, "quote": "Treatment improved survival."}],
                        "after_evidence_refs": [{"page": 2, "quote": "Treatment improved survival."}],
                        "reason_codes": [],
                        "parser_version": "parser-v2",
                        "llm_provider": "local",
                        "llm_model": "reader-model",
                        "llm_model_version": "reader-model-2026-05-22",
                        "prompt_version": "grounding-prompt-v2",
                        "reader_profile_version": "reader-profile-v2",
                        "reviewer_id": "reviewer-1",
                        "feedback_export_status": "pending",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    goldset_root = tmp_path / "goldset"

    imported = client.post(
        "/claim-evidence-corrections/eval-review-queue/import",
        json={
            "export_path": str(export_path),
            "goldset_root": str(goldset_root),
            "require_replayable": True,
        },
    )

    assert imported.status_code == 409
    detail = imported.json()["detail"]
    assert detail["message"] == "Claim/evidence eval candidate export is not replayable evidence."
    assert "nonreplayable_candidates" in detail["findings"]
    assert "no_replayable_candidates" in detail["findings"]
    assert not (goldset_root / "reviews" / "claim_evidence_eval_candidates" / "manifest.json").exists()


def test_claim_evidence_eval_candidates_import_from_corrections_api_skips_export_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    accepted = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-direct-intake",
            run_id="run-direct-intake",
            claim_id="CLM-DIRECT-INTAKE",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["LIMITATION_MISSED"],
        ),
    )
    ignored = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-direct-intake",
            run_id="run-direct-intake-ignored",
            claim_id="CLM-DIRECT-IGNORED",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=False,
            reason_codes=["LIMITATION_MISSED"],
        ),
    )
    assert accepted.status_code == 200
    assert ignored.status_code == 200
    goldset_root = tmp_path / "goldset"

    imported = client.post(
        "/claim-evidence-corrections/eval-review-queue/import-from-corrections",
        json={
            "goldset_root": str(goldset_root),
            "paper_id": "paper-correction-direct-intake",
            "reason_code": "LIMITATION_MISSED",
            "feedback_export_status": "linked",
        },
    )

    assert imported.status_code == 200
    manifest = imported.json()
    assert manifest["schema_version"] == "claim_evidence_eval_review_intake_manifest.v1"
    assert manifest["canonical_status"] == "non_canonical"
    assert manifest["source_export_path"] is None
    assert manifest["record_count"] == 1
    record = json.loads(Path(manifest["record_paths"][0]).read_text(encoding="utf-8"))
    assert record["source_candidate"]["claim_id"] == "CLM-DIRECT-INTAKE"
    assert record["source_candidate"]["reason_codes"] == ["LIMITATION_MISSED"]
    assert not (goldset_root / "accepted").exists()

    listed = client.get(
        "/claim-evidence-corrections/eval-review-queue",
        params={"goldset_root": str(goldset_root)},
    )
    assert listed.status_code == 200
    assert listed.json()["item_count"] == 1
    assert listed.json()["items"][0]["claim_id"] == "CLM-DIRECT-INTAKE"


def test_claim_evidence_eval_candidates_import_from_corrections_api_can_require_replayable(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    legacy_payload = _payload(
        parser_version=None,
        llm_provider=None,
        llm_model=None,
        llm_model_version=None,
        prompt_version=None,
        reader_profile_version=None,
        related_feedback_id=None,
        feedback_export_status="not_applicable",
        accepted_for_eval=True,
    )
    correction_log = tmp_path / "storage/claim_evidence_corrections.jsonl"
    correction_log.parent.mkdir(parents=True, exist_ok=True)
    correction_log.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    goldset_root = tmp_path / "goldset"

    imported = client.post(
        "/claim-evidence-corrections/eval-review-queue/import-from-corrections",
        json={
            "goldset_root": str(goldset_root),
            "require_replayable": True,
        },
    )

    assert imported.status_code == 409
    detail = imported.json()["detail"]
    assert detail["message"] == "Claim/evidence eval candidate export is not replayable evidence."
    assert "source_invalid_records" in detail["findings"]
    assert "no_replayable_candidates" in detail["findings"]
    assert detail["source_invalid_record_count"] == 1
    assert detail["source_invalid_record_diagnostics"][0]["line_number"] == 1
    assert detail["source_invalid_record_diagnostics"][0]["missing_replay_fields"] == [
        "parser_version",
        "llm_provider",
        "llm_model",
        "llm_model_version",
        "prompt_version",
        "reader_profile_version",
    ]
    assert not (goldset_root / "reviews" / "claim_evidence_eval_candidates" / "manifest.json").exists()


def test_claim_evidence_eval_candidates_review_script_creates_reviewed_fixture_not_accepted_gold(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    resp = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-review",
            run_id="run-review",
            claim_id="CLM-REVIEW",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["WRONG_LOCATOR"],
        ),
    )
    assert resp.status_code == 200

    scripts_root = Path(__file__).resolve().parents[1] / "scripts/eval"
    export_path = tmp_path / "eval_candidates.json"
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "export_claim_evidence_eval_candidates.py"),
            "--log-path",
            str(tmp_path / "storage/claim_evidence_corrections.jsonl"),
            "--out",
            str(export_path),
            "--paper-id",
            "paper-correction-review",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0

    goldset_root = tmp_path / "goldset"
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0

    list_result = subprocess.run(
        [
            sys.executable,
            str(scripts_root / "review_claim_evidence_eval_candidates.py"),
            "--goldset-root",
            str(goldset_root),
            "list",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert list_result.returncode == 0
    queue = json.loads(list_result.stdout)
    assert len(queue) == 1
    intake_id = queue[0]["intake_id"]
    assert queue[0]["claim_id"] == "CLM-REVIEW"
    assert queue[0]["reviewed"] is False

    resolve_result = subprocess.run(
        [
            sys.executable,
            str(scripts_root / "review_claim_evidence_eval_candidates.py"),
            "--goldset-root",
            str(goldset_root),
            "resolve",
            "--intake-id",
            intake_id,
            "--resolution",
            "APPROVE_FOR_EVAL",
            "--reviewer",
            "reviewer-eval",
            "--notes",
            "locator confirmed for eval fixture",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resolve_result.returncode == 0
    decision = json.loads(resolve_result.stdout)
    assert decision["schema_version"] == "claim_evidence_eval_review_decision.v1"
    assert decision["canonical_status"] == "non_canonical"
    assert decision["resolution"] == "APPROVE_FOR_EVAL"
    assert decision["approved_for_eval"] is True
    fixture_path = Path(decision["reviewed_fixture_path"])
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == "claim_evidence_reviewed_eval_fixture.v1"
    assert fixture["canonical_status"] == "non_canonical"
    assert fixture["source_candidate"]["claim_id"] == "CLM-REVIEW"
    assert fixture["review_notes"] == "locator confirmed for eval fixture"
    assert (goldset_root / "reviews" / "claim_evidence_eval_candidates" / "decisions" / "decisions.jsonl").exists()
    assert not (goldset_root / "accepted").exists()

    pending_after_resolve = subprocess.run(
        [
            sys.executable,
            str(scripts_root / "review_claim_evidence_eval_candidates.py"),
            "--goldset-root",
            str(goldset_root),
            "list",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert pending_after_resolve.returncode == 0
    assert json.loads(pending_after_resolve.stdout) == []


def test_claim_evidence_reviewed_fixtures_package_script_writes_run_sidecar_for_scorecard(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    resp = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-package",
            run_id="run-package",
            claim_id="CLM-PACKAGE",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["OVERSTATED_RESULT"],
        ),
    )
    assert resp.status_code == 200

    scripts_root = Path(__file__).resolve().parents[1] / "scripts/eval"
    export_path = tmp_path / "eval_candidates.json"
    goldset_root = tmp_path / "goldset"
    run_dir = tmp_path / "artifacts" / "paper-correction-package" / "run-package"
    run_dir.mkdir(parents=True)

    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "export_claim_evidence_eval_candidates.py"),
            "--log-path",
            str(tmp_path / "storage/claim_evidence_corrections.jsonl"),
            "--out",
            str(export_path),
            "--paper-id",
            "paper-correction-package",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0

    intake_dir = goldset_root / "reviews" / "claim_evidence_eval_candidates"
    manifest = json.loads((intake_dir / "manifest.json").read_text(encoding="utf-8"))
    intake_id = json.loads(Path(manifest["record_paths"][0]).read_text(encoding="utf-8"))["intake_id"]
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "review_claim_evidence_eval_candidates.py"),
            "--goldset-root",
            str(goldset_root),
            "resolve",
            "--intake-id",
            intake_id,
            "--resolution",
            "APPROVE_FOR_EVAL",
            "--reviewer",
            "reviewer-package",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0

    package_result = subprocess.run(
        [
            sys.executable,
            str(scripts_root / "package_claim_evidence_reviewed_fixtures.py"),
            "--goldset-root",
            str(goldset_root),
            "--run-dir",
            str(run_dir),
            "--paper-id",
            "paper-correction-package",
            "--run-id",
            "run-package",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert package_result.returncode == 0
    assert "[claim_evidence_reviewed_fixtures] fixture_count=1" in package_result.stdout
    sidecar = json.loads((run_dir / "claim_evidence_reviewed_eval_fixtures.json").read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == "claim_evidence_reviewed_eval_fixtures_bundle.v1"
    assert sidecar["canonical_status"] == "non_canonical"
    assert sidecar["fixture_count"] == 1
    assert sidecar["paper_id"] == "paper-correction-package"
    assert sidecar["run_id"] == "run-package"
    assert sidecar["fixtures"][0]["source_candidate"]["claim_id"] == "CLM-PACKAGE"


def test_claim_evidence_reviewed_fixtures_package_api_writes_run_sidecar(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    resp = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-package-api",
            run_id="run-package-api",
            claim_id="CLM-PACKAGE-API",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["WRONG_EVIDENCE"],
        ),
    )
    assert resp.status_code == 200

    scripts_root = Path(__file__).resolve().parents[1] / "scripts/eval"
    export_path = tmp_path / "eval_candidates.json"
    goldset_root = tmp_path / "goldset"
    run_dir = tmp_path / "artifacts" / "paper-correction-package-api" / "run-package-api"
    run_dir.mkdir(parents=True)

    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "export_claim_evidence_eval_candidates.py"),
            "--log-path",
            str(tmp_path / "storage/claim_evidence_corrections.jsonl"),
            "--out",
            str(export_path),
            "--paper-id",
            "paper-correction-package-api",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0
    intake_dir = goldset_root / "reviews" / "claim_evidence_eval_candidates"
    manifest = json.loads((intake_dir / "manifest.json").read_text(encoding="utf-8"))
    intake_id = json.loads(Path(manifest["record_paths"][0]).read_text(encoding="utf-8"))["intake_id"]
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "review_claim_evidence_eval_candidates.py"),
            "--goldset-root",
            str(goldset_root),
            "resolve",
            "--intake-id",
            intake_id,
            "--resolution",
            "APPROVE_FOR_EVAL",
            "--reviewer",
            "reviewer-package-api",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0

    packaged = client.post(
        "/claim-evidence-corrections/reviewed-fixtures/package",
        json={
            "goldset_root": str(goldset_root),
            "run_dir": str(run_dir),
            "paper_id": "paper-correction-package-api",
            "run_id": "run-package-api",
        },
    )

    assert packaged.status_code == 200
    body = packaged.json()
    assert body["status"] == "packaged"
    assert body["canonical_status"] == "non_canonical"
    assert body["fixture_count"] == 1
    sidecar = json.loads(Path(body["path"]).read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == "claim_evidence_reviewed_eval_fixtures_bundle.v1"
    assert sidecar["fixtures"][0]["source_candidate"]["claim_id"] == "CLM-PACKAGE-API"


def test_claim_evidence_eval_review_queue_api_lists_and_resolves_pending_intake(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_main.app)
    resp = client.post(
        "/claim-evidence-corrections",
        json=_payload(
            paper_id="paper-correction-review-api",
            run_id="run-review-api",
            claim_id="CLM-REVIEW-API",
            related_feedback_id=None,
            feedback_export_status="not_applicable",
            accepted_for_eval=True,
            reason_codes=["WRONG_LOCATOR"],
        ),
    )
    assert resp.status_code == 200

    scripts_root = Path(__file__).resolve().parents[1] / "scripts/eval"
    export_path = tmp_path / "eval_candidates.json"
    goldset_root = tmp_path / "goldset"
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "export_claim_evidence_eval_candidates.py"),
            "--log-path",
            str(tmp_path / "storage/claim_evidence_corrections.jsonl"),
            "--out",
            str(export_path),
            "--paper-id",
            "paper-correction-review-api",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0
    assert subprocess.run(
        [
            sys.executable,
            str(scripts_root / "import_claim_evidence_eval_candidates.py"),
            "--export",
            str(export_path),
            "--goldset-root",
            str(goldset_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0

    listed = client.get(
        "/claim-evidence-corrections/eval-review-queue",
        params={"goldset_root": str(goldset_root)},
    )
    assert listed.status_code == 200
    queue = listed.json()
    assert queue["schema_version"] == "claim_evidence_eval_review_queue.v1"
    assert queue["canonical_status"] == "non_canonical"
    assert queue["item_count"] == 1
    item = queue["items"][0]
    assert item["claim_id"] == "CLM-REVIEW-API"
    assert item["reviewed"] is False

    resolved = client.post(
        "/claim-evidence-corrections/eval-review-queue/resolve",
        json={
            "goldset_root": str(goldset_root),
            "intake_id": item["intake_id"],
            "resolution": "APPROVE_FOR_EVAL",
            "reviewer_id": "reviewer-api",
            "notes": "api-approved fixture",
        },
    )
    assert resolved.status_code == 200
    decision = resolved.json()
    assert decision["schema_version"] == "claim_evidence_eval_review_decision.v1"
    assert decision["canonical_status"] == "non_canonical"
    assert decision["resolution"] == "APPROVE_FOR_EVAL"
    assert decision["approved_for_eval"] is True
    assert Path(decision["reviewed_fixture_path"]).exists()
    assert not (goldset_root / "accepted").exists()

    pending = client.get(
        "/claim-evidence-corrections/eval-review-queue",
        params={"goldset_root": str(goldset_root)},
    )
    assert pending.status_code == 200
    assert pending.json()["items"] == []

    all_items = client.get(
        "/claim-evidence-corrections/eval-review-queue",
        params={"goldset_root": str(goldset_root), "include_resolved": True},
    )
    assert all_items.status_code == 200
    assert all_items.json()["items"][0]["reviewed"] is True
    assert all_items.json()["items"][0]["review_resolution"] == "APPROVE_FOR_EVAL"


def test_claim_evidence_correction_uses_runtime_storage_log_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paperpipe_home = tmp_path / "app-home"
    monkeypatch.setenv("PAPERPIPE_HOME", str(paperpipe_home))
    client = TestClient(api_main.app)

    resp = client.post("/claim-evidence-corrections", json=_payload(related_feedback_id=None))

    assert resp.status_code == 200
    correction_file = paperpipe_home / "storage" / "claim_evidence_corrections.jsonl"
    assert correction_file.exists()
