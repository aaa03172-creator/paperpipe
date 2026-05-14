#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DB_UTILS_PATH = ROOT / "src" / "db_utils.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNTIME_INTAKE_OVERRIDE_PRODUCERS = {
    "processor_gate",
    "processor_daily_slots",
    "watcher_local_pdf",
}
REPAIR_INTAKE_OVERRIDE_PRODUCERS = {
    "backfill_analysis",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _compact_internal_data_readiness_text(summary: dict[str, Any]) -> str:
    category_status = summary.get("category_status") if isinstance(summary.get("category_status"), dict) else {}
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}

    parts = [
        f"bootstrap_ready={bool(decision.get('internal_data_bootstrap_ready'))}",
        f"runtime_promotion_ready={bool(decision.get('runtime_promotion_ready'))}",
    ]

    policy_mode = str(decision.get("policy_mode") or "").strip()
    if policy_mode:
        parts.append(f"policy={policy_mode}")

    classification_audit = str(category_status.get("classification_audit") or "").strip()
    if classification_audit:
        parts.append(f"classification_audit={classification_audit}")

    classification_runtime_producer = str(category_status.get("classification_runtime_producer") or "").strip()
    if classification_runtime_producer:
        parts.append(f"classification_runtime_producer={classification_runtime_producer}")

    classification_tuning_review = str(category_status.get("classification_tuning_review") or "").strip()
    if classification_tuning_review:
        parts.append(f"classification_tuning_review={classification_tuning_review}")

    blockers = decision.get("blockers")
    if isinstance(blockers, list) and blockers:
        parts.append(f"blockers={len(blockers)}")

    return " ".join(parts)


def _load_jsonl_dict_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_expected={path}")
    return payload


def _load_module(path: Path, *, module_name: str):
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_spec_unavailable={path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_research_dna_log_file_names() -> dict[str, str]:
    store_path = ROOT / "src" / "profiles" / "research_dna_store.py"
    tree = ast.parse(store_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "LOG_FILE_NAMES":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, dict):
                        return {str(key): str(val) for key, val in value.items()}
    raise RuntimeError(f"log_file_names_not_found={store_path}")


def _load_runtime_db_rows(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall()]
    finally:
        conn.close()


def _artifact_history_promotion_policy_path() -> Path:
    value = os.getenv("PAPERPIPE_ARTIFACT_HISTORY_PROMOTION_POLICY_PATH")
    if value:
        return Path(value).expanduser().resolve()
    return (ROOT / "config" / "artifact_history_promotion_policy.json").resolve()


def _slot_classification_tuning_review_root() -> Path:
    value = os.getenv("PAPERPIPE_SLOT_CLASSIFICATION_TUNING_REVIEW_ROOT")
    if value:
        return Path(value).expanduser().resolve()
    return (ROOT / "snapshots" / "slot_classification_tuning_review").resolve()


def _load_slot_classification_tuning_review_summary(path_or_dir: Path) -> dict[str, Any]:
    summary_path = path_or_dir.expanduser().resolve()
    if summary_path.is_dir():
        summary_path = summary_path / "summary.json"
    payload = _load_json_dict(summary_path)
    schema_version = str(payload.get("schema_version") or "").strip()
    if not schema_version.startswith("slot_classification_tuning_review.v"):
        raise ValueError(f"unsupported_slot_classification_tuning_review_schema={summary_path}")
    return payload


def _latest_slot_classification_tuning_review_run(root: Path | None = None) -> Path | None:
    review_root = (root or _slot_classification_tuning_review_root()).expanduser().resolve(strict=False)
    if not review_root.exists() or not review_root.is_dir():
        return None

    candidates: list[tuple[float, float, str, Path]] = []
    for candidate in review_root.iterdir():
        if not candidate.is_dir():
            continue
        summary_path = candidate / "summary.json"
        if not summary_path.exists():
            continue
        try:
            mtime = summary_path.stat().st_mtime
        except OSError:
            continue

        generated_sort_key = 0.0
        try:
            payload = _load_slot_classification_tuning_review_summary(candidate)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            generated_at_text = str(payload.get("generated_at") or "").strip()
            if generated_at_text:
                try:
                    generated_sort_key = datetime.fromisoformat(
                        generated_at_text.replace("Z", "+00:00")
                    ).timestamp()
                except ValueError:
                    generated_sort_key = 0.0

        candidates.append((generated_sort_key, mtime, candidate.name, candidate))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1], item[2]))[3]


def _latest_slot_classification_tuning_review_summary() -> tuple[dict[str, Any] | None, Path | None, str | None]:
    latest_run = _latest_slot_classification_tuning_review_run()
    if latest_run is None:
        return None, None, None
    try:
        return _load_slot_classification_tuning_review_summary(latest_run), latest_run, None
    except Exception as exc:
        return None, latest_run, str(exc)


def _build_embedded_intake_override_coverage_gate(
    *,
    run_id: str,
    db_path: Path,
) -> dict[str, Any]:
    from scripts.eval.check_intake_override_coverage_gate import build_intake_override_coverage_gate_summary

    intake_override_log_module = _load_module(
        ROOT / "src" / "schemas" / "intake_override_log.py",
        module_name="intake_override_log_readiness",
    )
    IntakeOverrideLog = intake_override_log_module.IntakeOverrideLog

    rows = _load_runtime_db_rows(db_path)

    has_feedback_json_count = 0
    audited_document_count = 0
    missing_intake_override_log_count = 0
    invalid_feedback_json_count = 0
    invalid_intake_override_log_count = 0

    for row in rows:
        feedback_json = row.get("feedback_json")
        if feedback_json in (None, ""):
            continue
        has_feedback_json_count += 1
        try:
            payload = json.loads(str(feedback_json))
        except Exception:
            invalid_feedback_json_count += 1
            continue
        if not isinstance(payload, dict):
            invalid_feedback_json_count += 1
            continue
        raw_log = payload.get("intake_override_log")
        if raw_log is None:
            missing_intake_override_log_count += 1
            continue
        try:
            IntakeOverrideLog.model_validate(raw_log)
        except Exception:
            invalid_intake_override_log_count += 1
            continue
        audited_document_count += 1

    audit_summary = {
        "schema_version": "intake_override_audit_summary.v1",
        "generated_at": _utc_now_iso(),
        "run_id": f"{run_id}_embedded_intake_override_audit",
        "inputs": {
            "source": "runtime_db",
            "db_path": str(db_path),
            "rows_jsonl_path": None,
            "row_count": len(rows),
        },
        "metrics": {
            "document_count": len(rows),
            "has_feedback_json_count": has_feedback_json_count,
            "audited_document_count": audited_document_count,
            "missing_intake_override_log_count": missing_intake_override_log_count,
            "invalid_feedback_json_count": invalid_feedback_json_count,
            "invalid_intake_override_log_count": invalid_intake_override_log_count,
        },
    }
    return build_intake_override_coverage_gate_summary(
        audit_summary=audit_summary,
        audit_summary_path=None,
        run_id=f"{run_id}_intake_override_coverage_gate",
        min_feedback_json_rows_for_gate=1,
        min_audited_feedback_coverage=1.0,
        max_missing_log_count=0,
        max_invalid_feedback_json_count=0,
        max_invalid_intake_override_log_count=0,
    )


def _build_embedded_intake_override_producer_ownership_summary(
    *,
    run_id: str,
    db_path: Path,
) -> dict[str, Any]:
    intake_override_log_module = _load_module(
        ROOT / "src" / "schemas" / "intake_override_log.py",
        module_name="intake_override_log_producer_ownership",
    )
    IntakeOverrideLog = intake_override_log_module.IntakeOverrideLog

    rows = _load_runtime_db_rows(db_path)

    producer_counts: dict[str, int] = {}
    runtime_producer_counts: dict[str, int] = {}
    repair_producer_counts: dict[str, int] = {}
    unknown_producer_counts: dict[str, int] = {}
    has_feedback_json_count = 0
    audited_document_count = 0

    for row in rows:
        feedback_json = row.get("feedback_json")
        if feedback_json in (None, ""):
            continue
        has_feedback_json_count += 1
        try:
            payload = json.loads(str(feedback_json))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw_log = payload.get("intake_override_log")
        if raw_log is None:
            continue
        try:
            intake_log = IntakeOverrideLog.model_validate(raw_log)
        except Exception:
            continue

        audited_document_count += 1
        producer = str(intake_log.producer or "").strip() or "unknown"
        producer_counts[producer] = producer_counts.get(producer, 0) + 1
        if producer in RUNTIME_INTAKE_OVERRIDE_PRODUCERS:
            runtime_producer_counts[producer] = runtime_producer_counts.get(producer, 0) + 1
        elif producer in REPAIR_INTAKE_OVERRIDE_PRODUCERS:
            repair_producer_counts[producer] = repair_producer_counts.get(producer, 0) + 1
        else:
            unknown_producer_counts[producer] = unknown_producer_counts.get(producer, 0) + 1

    runtime_producer_present = bool(runtime_producer_counts)
    repair_only_mode = bool(audited_document_count and not runtime_producer_present and repair_producer_counts)
    runtime_producer_document_count = sum(runtime_producer_counts.values())
    repair_producer_document_count = sum(repair_producer_counts.values())
    runtime_producer_coverage_rate = (
        float(runtime_producer_document_count) / float(audited_document_count)
        if audited_document_count
        else 0.0
    )
    primary_runtime_producer = None
    if runtime_producer_counts:
        primary_runtime_producer = sorted(
            runtime_producer_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]

    decision_reason = "no audited intake override rows are available yet"
    if runtime_producer_present:
        decision_reason = (
            "one or more runtime producers are present in persisted intake_override_log rows"
        )
    elif repair_only_mode:
        decision_reason = (
            "persisted intake_override_log rows currently come only from repair/backfill producers; "
            "primary runtime producer ownership is not yet demonstrated on this runtime DB"
        )
    elif audited_document_count:
        decision_reason = (
            "persisted intake_override_log rows are present, but none belong to known runtime producers"
        )

    return {
        "schema_version": "intake_override_producer_ownership.v1",
        "generated_at": _utc_now_iso(),
        "run_id": f"{run_id}_intake_override_producer_ownership",
        "inputs": {
            "db_path": str(db_path),
            "row_count": len(rows),
            "runtime_producers": sorted(RUNTIME_INTAKE_OVERRIDE_PRODUCERS),
            "repair_producers": sorted(REPAIR_INTAKE_OVERRIDE_PRODUCERS),
        },
        "decision": {
            "has_feedback_json_count": has_feedback_json_count,
            "audited_document_count": audited_document_count,
            "producer_counts": dict(sorted(producer_counts.items())),
            "runtime_producer_counts": dict(sorted(runtime_producer_counts.items())),
            "repair_producer_counts": dict(sorted(repair_producer_counts.items())),
            "unknown_producer_counts": dict(sorted(unknown_producer_counts.items())),
            "runtime_producer_document_count": runtime_producer_document_count,
            "repair_producer_document_count": repair_producer_document_count,
            "runtime_producer_coverage_rate": runtime_producer_coverage_rate,
            "runtime_producer_present": runtime_producer_present,
            "repair_only_mode": repair_only_mode,
            "primary_runtime_producer": primary_runtime_producer,
            "decision_reason": decision_reason,
        },
    }


def build_internal_data_readiness_summary(*, run_id: str) -> dict[str, Any]:
    from scripts.eval.check_artifact_history_promotion_gate import build_artifact_history_promotion_gate_summary
    from src.db_utils import get_db_path
    from src.services.runtime_paths import (
        artifact_generation_outcome_log_path,
        artifact_review_feedback_log_path,
        chart_packs_root,
        feedback_log_path,
        image_evidence_root,
        meeting_packs_root,
        method_comparisons_root,
        project_context_link_log_path,
        project_memory_root,
        protocol_cards_root,
        research_dna_root,
        search_eval_root,
        state_db_path,
    )

    agent_artifacts_module = _load_module(ROOT / "src" / "schemas" / "agent_artifacts.py", module_name="agent_artifacts_audit")
    artifact_generation_outcome_module = _load_module(
        ROOT / "src" / "schemas" / "artifact_generation_outcome.py",
        module_name="artifact_generation_outcome_audit",
    )
    artifact_history_policy_module = _load_module(
        ROOT / "src" / "schemas" / "artifact_history_promotion_policy.py",
        module_name="artifact_history_promotion_policy_audit",
    )
    artifact_review_feedback_module = _load_module(
        ROOT / "src" / "schemas" / "artifact_review_feedback.py",
        module_name="artifact_review_feedback_audit",
    )
    project_context_link_module = _load_module(
        ROOT / "src" / "schemas" / "project_context_link.py",
        module_name="project_context_link_audit",
    )
    project_memory_module = _load_module(ROOT / "src" / "schemas" / "project_memory.py", module_name="project_memory_audit")
    ArtifactGenerationOutcome = artifact_generation_outcome_module.ArtifactGenerationOutcome
    ArtifactHistoryPromotionPolicy = artifact_history_policy_module.ArtifactHistoryPromotionPolicy
    ArtifactReviewFeedbackCase = artifact_review_feedback_module.ArtifactReviewFeedbackCase
    ProjectContextLinkDecision = project_context_link_module.ProjectContextLinkDecision
    FeedbackCase = agent_artifacts_module.FeedbackCase
    ProjectMemoryItem = project_memory_module.ProjectMemoryItem
    ProjectMemoryWorkspace = project_memory_module.ProjectMemoryWorkspace
    log_file_names = _load_research_dna_log_file_names()

    feedback_fields = list(FeedbackCase.model_fields.keys())
    artifact_generation_outcome_fields = list(ArtifactGenerationOutcome.model_fields.keys())
    artifact_review_feedback_fields = list(ArtifactReviewFeedbackCase.model_fields.keys())
    project_context_link_fields = list(ProjectContextLinkDecision.model_fields.keys())
    project_workspace_fields = list(ProjectMemoryWorkspace.model_fields.keys())
    project_item_fields = list(ProjectMemoryItem.model_fields.keys())
    request_audit_table_present = "CREATE TABLE IF NOT EXISTS request_audits" in DB_UTILS_PATH.read_text(
        encoding="utf-8"
    )
    artifact_review_feedback_rows = _load_jsonl_dict_rows(artifact_review_feedback_log_path())
    artifact_generation_outcome_rows = _load_jsonl_dict_rows(artifact_generation_outcome_log_path())
    artifact_history_gate = build_artifact_history_promotion_gate_summary(
        review_feedback_rows=artifact_review_feedback_rows,
        generation_outcome_rows=artifact_generation_outcome_rows,
        required_families=["meeting_pack", "protocol_card"],
        min_review_feedback_events=2,
        min_generation_outcome_events=2,
        min_paired_artifacts=1,
        run_id=run_id,
    )
    policy_path = _artifact_history_promotion_policy_path()
    artifact_history_policy = None
    artifact_history_policy_error: str | None = None
    if policy_path.exists():
        try:
            artifact_history_policy = ArtifactHistoryPromotionPolicy.model_validate(_load_json_dict(policy_path))
        except Exception as exc:
            artifact_history_policy_error = str(exc)
    else:
        artifact_history_policy_error = f"policy_file_not_found={policy_path}"

    intake_override_db_path = get_db_path()
    intake_override_coverage_gate = None
    intake_override_coverage_gate_error: str | None = None
    intake_override_producer_ownership = None
    intake_override_producer_ownership_error: str | None = None
    if intake_override_db_path.exists():
        try:
            intake_override_coverage_gate = _build_embedded_intake_override_coverage_gate(
                run_id=run_id,
                db_path=intake_override_db_path,
            )
        except Exception as exc:
            intake_override_coverage_gate_error = str(exc)
        try:
            intake_override_producer_ownership = _build_embedded_intake_override_producer_ownership_summary(
                run_id=run_id,
                db_path=intake_override_db_path,
            )
        except Exception as exc:
            intake_override_producer_ownership_error = str(exc)
    else:
        intake_override_coverage_gate_error = f"db_path_not_found={intake_override_db_path}"
        intake_override_producer_ownership_error = f"db_path_not_found={intake_override_db_path}"

    (
        slot_classification_tuning_review,
        slot_classification_tuning_review_run,
        slot_classification_tuning_review_error,
    ) = _latest_slot_classification_tuning_review_summary()

    surfaces = {
        "feedback_corrections": {
            "status": "present",
            "storage_kind": "jsonl_log",
            "log_path": str(feedback_log_path()),
            "fields": feedback_fields,
            "claim_level_link_supported": "original_claim_id" in feedback_fields,
            "accepted_flag_supported": "accepted" in feedback_fields,
            "artifact_family_label_supported": False,
            "notes": [
                "accepted feedback can be indexed for later retrieval bootstrap",
                "feedback is linked to paper_id and run_id, with optional original_claim_id",
            ],
        },
        "project_memory": {
            "status": "present_noncanonical",
            "root_path": str(project_memory_root()),
            "workspace_json_example": str(project_memory_root() / "pmproj_example" / "project.json"),
            "items_jsonl_example": str(project_memory_root() / "pmproj_example" / "memory.jsonl"),
            "workspace_fields": project_workspace_fields,
            "item_fields": project_item_fields,
            "layer": ProjectMemoryWorkspace.model_fields["layer"].default,
            "canonical_status": ProjectMemoryWorkspace.model_fields["canonical_status"].default,
            "notes": [
                "project memory is explicitly raw_memory and non_canonical",
                "the current gate keeps this lane backend-only rather than product-visible",
            ],
        },
        "project_context_link_decisions": {
            "status": "present",
            "storage_kind": "jsonl_log",
            "log_path": str(project_context_link_log_path()),
            "fields": project_context_link_fields,
            "project_scoped_id_validation": True,
            "notes": [
                "project-context relevance decisions now live in a dedicated raw-log contract separate from Project Memory items",
                "writes are bounded to existing pmproj_* workspaces without opening a Project Memory API",
            ],
        },
        "research_dna_state_transition": {
            "status": "present",
            "root_path": str(research_dna_root()),
            "search_eval_root": str(search_eval_root()),
            "log_files": dict(log_file_names),
            "captures": [
                "interview log",
                "run log",
                "screening decision log",
                "approval audit",
                "run-local screening progress sidecars",
                "guidance follow summary",
            ],
            "notes": [
                "screening decisions are already actor-attributed and reason-coded",
                "progress/guidance sidecars are additive telemetry rather than canonical state",
            ],
        },
        "request_audits": {
            "status": "present" if request_audit_table_present else "missing",
            "db_path": str(state_db_path()),
            "table_name": "request_audits",
            "browser_request_audit_table_present": request_audit_table_present,
            "notes": [
                "request audits capture request/response metadata for viewer and browser-access observability",
                "they are useful for flow telemetry, not semantic biomedical judgments",
            ],
        },
        "artifact_review_feedback": {
            "status": "present",
            "storage_kind": "jsonl_log",
            "log_path": str(artifact_review_feedback_log_path()),
            "fields": artifact_review_feedback_fields,
            "artifact_roots": {
                "meeting_packs": str(meeting_packs_root()),
                "chart_packs": str(chart_packs_root()),
                "image_evidence": str(image_evidence_root()),
                "method_comparisons": str(method_comparisons_root()),
                "protocol_cards": str(protocol_cards_root()),
            },
            "artifact_family_label_supported": "artifact_type" in artifact_review_feedback_fields,
            "decision_label_supported": "decision" in artifact_review_feedback_fields,
            "notes": [
                "saved artifact families now share a dedicated artifact review feedback event contract",
                "artifact review feedback stays additive and raw-log-oriented instead of replacing artifact owners",
            ],
        },
        "artifact_generation_outcomes": {
            "status": "present",
            "storage_kind": "jsonl_log",
            "log_path": str(artifact_generation_outcome_log_path()),
            "fields": artifact_generation_outcome_fields,
            "artifact_roots": {
                "meeting_packs": str(meeting_packs_root()),
                "chart_packs": str(chart_packs_root()),
                "image_evidence": str(image_evidence_root()),
                "method_comparisons": str(method_comparisons_root()),
                "protocol_cards": str(protocol_cards_root()),
            },
            "artifact_family_label_supported": "artifact_type" in artifact_generation_outcome_fields,
            "decision_label_supported": "decision" in artifact_generation_outcome_fields,
            "downstream_use_label_supported": "downstream_use" in artifact_generation_outcome_fields,
            "notes": [
                "saved artifact families now share a dedicated downstream-use outcome contract",
                "artifact generation outcomes stay additive and raw-log-oriented instead of replacing artifact owners",
            ],
        },
        "artifact_history_promotion_gate": {
            "status": "present",
            "storage_kind": "derived_audit_summary",
            "advisory_only": artifact_history_gate["advisory_only"],
            "required_families": artifact_history_gate["thresholds"]["required_families"],
            "thresholds": dict(artifact_history_gate["thresholds"]),
            "inputs": dict(artifact_history_gate["inputs"]),
            "decision": dict(artifact_history_gate["decision"]),
            "notes": [
                "the advisory artifact-history gate is embedded here so internal-data readiness shows both contract presence and bounded history gaps",
                "promotion remains blocked until selected families accumulate enough paired review/outcome history",
            ],
        },
        "artifact_history_promotion_policy": {
            "status": "present" if artifact_history_policy is not None else "invalid" if policy_path.exists() else "missing",
            "storage_kind": "repo_policy_file",
            "policy_path": str(policy_path),
            "policy_mode": artifact_history_policy.policy_mode if artifact_history_policy is not None else None,
            "required_families": list(artifact_history_policy.required_families) if artifact_history_policy is not None else [],
            "thresholds": (
                artifact_history_policy.thresholds.model_dump(mode="json")
                if artifact_history_policy is not None
                else None
            ),
            "requires_real_operator_history": (
                artifact_history_policy.requires_real_operator_history if artifact_history_policy is not None else None
            ),
            "discussion_ready_when_gate_passes": (
                artifact_history_policy.discussion_ready_when_gate_passes if artifact_history_policy is not None else None
            ),
            "allows_default_owner_change": (
                artifact_history_policy.allows_default_owner_change if artifact_history_policy is not None else None
            ),
            "allows_automatic_runtime_promotion": (
                artifact_history_policy.allows_automatic_runtime_promotion if artifact_history_policy is not None else None
            ),
            "required_manual_actions": (
                list(artifact_history_policy.required_manual_actions) if artifact_history_policy is not None else []
            ),
            "notes": (
                list(artifact_history_policy.notes)
                if artifact_history_policy is not None
                else ["artifact-history promotion policy must be explicitly present and valid before gate-passing history can change posture"]
            ),
            "validation_error": artifact_history_policy_error,
        },
        "intake_override_coverage_gate": {
            "status": (
                "present"
                if intake_override_coverage_gate is not None
                else "invalid"
                if intake_override_db_path.exists()
                else "missing"
            ),
            "storage_kind": "derived_audit_summary",
            "db_path": str(intake_override_db_path),
            "thresholds": (
                dict(intake_override_coverage_gate["thresholds"])
                if intake_override_coverage_gate is not None
                else None
            ),
            "inputs": (
                dict(intake_override_coverage_gate["inputs"])
                if intake_override_coverage_gate is not None
                else None
            ),
            "decision": (
                dict(intake_override_coverage_gate["decision"])
                if intake_override_coverage_gate is not None
                else None
            ),
            "notes": [
                "the intake override coverage gate summarizes whether feedback-bearing paper rows remain auditable by persisted intake_override_log payloads",
                "this stays advisory and additive: it reuses the existing intake audit builder instead of creating a second runtime truth path",
            ],
            "validation_error": intake_override_coverage_gate_error,
        },
        "intake_override_producer_ownership": {
            "status": (
                "present"
                if intake_override_producer_ownership is not None
                else "invalid"
                if intake_override_db_path.exists()
                else "missing"
            ),
            "storage_kind": "derived_audit_summary",
            "db_path": str(intake_override_db_path),
            "inputs": (
                dict(intake_override_producer_ownership["inputs"])
                if intake_override_producer_ownership is not None
                else None
            ),
            "decision": (
                dict(intake_override_producer_ownership["decision"])
                if intake_override_producer_ownership is not None
                else None
            ),
            "notes": [
                "this producer-ownership surface shows whether persisted intake_override_log rows are coming from runtime paths or only from repair/backfill lanes",
                "backfill_analysis is treated as repair-only evidence rather than proof that the active runtime owner is persisting logs correctly",
            ],
            "validation_error": intake_override_producer_ownership_error,
        },
        "slot_classification_tuning_review": {
            "status": (
                "present"
                if slot_classification_tuning_review is not None
                else "invalid"
                if slot_classification_tuning_review_run is not None
                else "missing"
            ),
            "storage_kind": "derived_audit_summary",
            "summary_path": (
                str(slot_classification_tuning_review_run / "summary.json")
                if slot_classification_tuning_review_run is not None
                else None
            ),
            "markdown_path": (
                str(slot_classification_tuning_review_run / "audit.md")
                if slot_classification_tuning_review_run is not None
                and (slot_classification_tuning_review_run / "audit.md").exists()
                else None
            ),
            "decision": (
                dict(slot_classification_tuning_review["decision"])
                if slot_classification_tuning_review is not None
                and isinstance(slot_classification_tuning_review.get("decision"), dict)
                else None
            ),
            "signal_summary": (
                dict(slot_classification_tuning_review["signal_summary"])
                if slot_classification_tuning_review is not None
                and isinstance(slot_classification_tuning_review.get("signal_summary"), dict)
                else None
            ),
            "notes": [
                "this slot-tuning review stays advisory-only and summarizes whether paired benchmark plus rerun-drift evidence is strong enough to treat a slot prompt/policy change as durable",
                "it does not change runtime slot behavior and it should not be treated as a promotion gate for the classification lane",
            ],
            "validation_error": slot_classification_tuning_review_error,
        },
    }

    classification_audit_status = "missing"
    if intake_override_coverage_gate is not None:
        gate_decision = intake_override_coverage_gate["decision"]
        gate_applies = bool(gate_decision["gate_applies"])
        gate_passed = bool(gate_decision["passed"])
        classification_audit_status = "bootstrap_ready" if (not gate_applies or gate_passed) else "attention_needed"

    classification_runtime_producer_status = "missing"
    if intake_override_producer_ownership is not None:
        producer_decision = intake_override_producer_ownership["decision"]
        if bool(producer_decision["runtime_producer_present"]):
            classification_runtime_producer_status = "runtime_ready"
        elif bool(producer_decision["repair_only_mode"]):
            classification_runtime_producer_status = "repair_only"
        elif int(producer_decision["audited_document_count"] or 0) > 0:
            classification_runtime_producer_status = "attention_needed"

    classification_tuning_review_status = "missing"
    if slot_classification_tuning_review is not None:
        tuning_decision = (
            slot_classification_tuning_review.get("decision")
            if isinstance(slot_classification_tuning_review.get("decision"), dict)
            else {}
        )
        classification_tuning_review_status = (
            "review_ready" if bool(tuning_decision.get("review_ready")) else "advisory_hold"
        )
    elif slot_classification_tuning_review_run is not None:
        classification_tuning_review_status = "invalid"

    category_status = {
        "project_context_relevance": "bootstrap_ready",
        "state_transition": "bootstrap_ready",
        "artifact_generation": "bootstrap_ready",
        "human_correction": "bootstrap_ready",
        "logs_design": "bootstrap_ready",
        "classification_audit": classification_audit_status,
        "classification_runtime_producer": classification_runtime_producer_status,
        "classification_tuning_review": classification_tuning_review_status,
    }

    gate_promotion_ready = bool(artifact_history_gate["decision"]["promotion_ready"])
    policy_present = artifact_history_policy is not None
    runtime_promotion_discussion_ready = bool(
        gate_promotion_ready
        and policy_present
        and artifact_history_policy.discussion_ready_when_gate_passes
    )
    runtime_promotion_ready = bool(
        runtime_promotion_discussion_ready
        and artifact_history_policy is not None
        and artifact_history_policy.allows_default_owner_change
        and artifact_history_policy.allows_automatic_runtime_promotion
    )

    blockers = list(artifact_history_gate["decision"]["blockers"])
    if gate_promotion_ready and not policy_present:
        blockers.append("explicit_runtime_promotion_policy_missing")
    elif gate_promotion_ready and not runtime_promotion_ready:
        blockers.append("automatic_default_promotion_not_allowed_by_policy")

    minimum_next_events: list[str] = []
    runtime_promotion_reason = (
        "bounded raw-log contracts are present, but runtime promotion remains blocked until selected "
        "artifact families accumulate enough paired history and a promotion policy is explicitly adopted"
    )

    if not gate_promotion_ready:
        if policy_present:
            runtime_promotion_reason = (
                "bounded raw-log contracts and the explicit manual-review-only policy are present, but runtime "
                "promotion remains blocked until selected artifact families accumulate enough paired history"
            )
        minimum_next_events = [
            "collect_at_least_2_review_feedback_events_for_each_required_artifact_family",
            "collect_at_least_2_generation_outcome_events_for_each_required_artifact_family",
            "collect_at_least_1_paired_review_and_outcome_artifact_id_for_each_required_artifact_family",
        ]
    elif not policy_present:
        minimum_next_events = ["define_and_adopt_an_explicit_runtime_promotion_policy_for_selected_artifact_families"]
        runtime_promotion_reason = (
            "bounded history clears the advisory gate, but runtime promotion still requires an explicit "
            "repo-level promotion policy for the selected artifact families"
        )
    elif not runtime_promotion_ready:
        minimum_next_events = list(artifact_history_policy.required_manual_actions)
        runtime_promotion_reason = (
            "bounded history clears the advisory gate, but the active policy keeps runtime promotion "
            "manual-review-only and blocks automatic default owner changes"
        )

    return {
        "schema_version": "internal_data_readiness.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "surfaces": surfaces,
        "category_status": category_status,
        "decision": {
            "internal_data_bootstrap_ready": True,
            "runtime_promotion_discussion_ready": runtime_promotion_discussion_ready,
            "runtime_promotion_ready": runtime_promotion_ready,
            "policy_mode": artifact_history_policy.policy_mode if artifact_history_policy is not None else None,
            "default_owner_change_allowed_by_policy": (
                artifact_history_policy.allows_default_owner_change if artifact_history_policy is not None else False
            ),
            "automatic_runtime_promotion_allowed_by_policy": (
                artifact_history_policy.allows_automatic_runtime_promotion
                if artifact_history_policy is not None
                else False
            ),
            "blockers": blockers,
            "runtime_promotion_reason": runtime_promotion_reason,
        },
        "minimum_next_events": minimum_next_events,
    }


def run_internal_data_readiness(*, out_dir: Path, run_id: str) -> Path:
    summary = build_internal_data_readiness_summary(run_id=run_id)
    run_root = out_dir / run_id
    _write_json(run_root / "summary.json", summary)
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize the current repo-grounded readiness of internal data surfaces for the biomedical workspace."
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "snapshots" / "internal_data_readiness"),
        help="Output root directory for the summary.",
    )
    parser.add_argument("--run-id", required=True, help="Output run identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_root = run_internal_data_readiness(
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=str(args.run_id),
    )
    summary_path = run_root / "summary.json"
    payload = _load_json_dict(summary_path)
    print(f"[check_internal_data_readiness] out={run_root}")
    print(f"[check_internal_data_readiness] summary={summary_path}")
    print(
        "[check_internal_data_readiness] "
        + _compact_internal_data_readiness_text(payload)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
