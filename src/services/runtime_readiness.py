from __future__ import annotations

import importlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path
import sys
from typing import Mapping

from scripts.archive_fixture_no_feedback_papers import (
    select_archive_candidates as select_fixture_paper_archive_candidates,
)
from src.config import load_config
from src.db_utils import get_db_path
from src.meeting_packs.hygiene import select_archive_candidates as select_meeting_pack_archive_candidates
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse
from src.schemas.privacy_preflight import PRIVACY_PREFLIGHT_ROLLBACK_FLAG
from src.services.fixture_visibility import (
    fixture_structured_state_allowed,
    hidden_fixture_structured_state_paths,
)
from src.services.intake_override_audit import (
    build_intake_override_audit_calibration_snapshot,
    default_intake_override_audits_root,
    default_intake_override_threshold_review_root,
    latest_intake_override_audit_run,
    latest_intake_override_audit_summary,
    latest_intake_override_threshold_review_run,
    latest_intake_override_threshold_review_summary,
)
from src.services.processor_gate_replay_drift import (
    default_processor_gate_threshold_review_root,
    latest_processor_gate_threshold_review_run,
    load_processor_gate_threshold_review_summary,
    resolve_processor_gate_threshold_review_drift_artifacts,
)
from src.services.privacy_preflight import resolve_privacy_preflight_mode
from src.services.slot_classification_tuning_review import (
    default_slot_classification_tuning_review_root,
    latest_slot_classification_tuning_review_run,
    load_slot_classification_tuning_review_summary,
)
from src.services.stale_jobs import collect_queue_health
from src.services.runtime_paths import (
    cache_root,
    config_file_path,
    config_root,
    frontend_runtime_dir,
    logs_root,
    meeting_packs_root,
    storage_root,
)

# Intentional fixed threshold:
# keep this constant until we have stronger operator evidence that a configurable
# threshold is needed. The first observed local drift bucket was 11 fixture rows,
# which was large enough to materially distort classification-audit counts.
FIXTURE_PAPER_HYGIENE_ERROR_THRESHOLD = 10
CLI_ENTRYPOINT_HELP_TIMEOUT_SECONDS = 10
LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE = 0.25
LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS = 3
QUEUE_HEALTH_STALE_AFTER_SECONDS = 15 * 60
QUEUE_HEALTH_QUEUED_AGE_WARN_AFTER_SECONDS = 15 * 60
REPO_ROOT = Path(__file__).resolve().parents[2]


def _nearest_existing_parent(path: Path) -> Path:
    current = path.expanduser().resolve(strict=False)
    while not current.exists() and current.parent != current:
        current = current.parent
    return current


def _path_writable_target(path: Path) -> bool:
    target = path if path.exists() else _nearest_existing_parent(path)
    return os.access(target, os.W_OK)


def _safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _processor_gate_worksheet_compact_text(worksheet_summary: object) -> str | None:
    if not isinstance(worksheet_summary, dict):
        return None

    pending_count = _safe_int(worksheet_summary.get("pending_count"))
    primary_review_target = str(worksheet_summary.get("primary_review_target") or "").strip()
    excluded_count = _safe_int(worksheet_summary.get("excluded_count"))

    parts: list[str] = []
    if pending_count is not None:
        parts.append(f"pending={pending_count}")
    if primary_review_target:
        parts.append(f"target={primary_review_target}")
    if excluded_count is not None:
        parts.append(f"excluded={excluded_count}")
    return ", ".join(parts) or None


def _processor_gate_basis_compact_text(basis: object) -> str | None:
    if not isinstance(basis, dict):
        return None

    preliminary_call = str(basis.get("preliminary_call") or "").strip()
    policy_support = _safe_int(basis.get("mid_confidence_policy_support_count"))
    high_threshold_support = _safe_int(basis.get("high_threshold_support_count"))

    parts: list[str] = []
    if preliminary_call:
        parts.append(f"call={preliminary_call}")
    if policy_support is not None:
        parts.append(f"policy={policy_support}")
    if high_threshold_support is not None:
        parts.append(f"high={high_threshold_support}")
    return ", ".join(parts) or None


def _processor_gate_threshold_change_compact_text(decision: object) -> str | None:
    if not isinstance(decision, dict):
        return None

    parts: list[str] = []
    if "threshold_change_ready" in decision:
        parts.append("ready=yes" if bool(decision.get("threshold_change_ready")) else "ready=no")

    threshold_change_status = str(decision.get("threshold_change_status") or "").strip()
    if threshold_change_status:
        parts.append(f"status={threshold_change_status}")

    threshold_change_next_step = str(decision.get("threshold_change_next_step") or "").strip()
    if threshold_change_next_step:
        parts.append(f"next={threshold_change_next_step}")

    return ", ".join(parts) or None


def _processor_gate_manual_review_scope_compact_text(
    *,
    threshold_relevant_count: int | None,
    policy_edge_case_count: int | None,
    excluded_manual_override_count: int | None,
    excluded_indexed_pending_count: int | None,
    excluded_fixture_or_test_count: int | None,
    excluded_other_count: int | None,
) -> str | None:
    parts = [
        ("relevant", threshold_relevant_count),
        ("policy", policy_edge_case_count),
        ("excluded.manual_override", excluded_manual_override_count),
        ("excluded.indexed_pending", excluded_indexed_pending_count),
        ("excluded.fixture_or_test", excluded_fixture_or_test_count),
        ("excluded.other", excluded_other_count),
    ]
    text_parts = [f"{label}={value}" for label, value in parts if value is not None]
    return ", ".join(text_parts) or None


def _processor_gate_sample_ids_preview(bucket: object) -> str | None:
    if not isinstance(bucket, dict):
        return None

    paper_ids = [str(item).strip() for item in bucket.get("paper_ids", []) if str(item).strip()]
    if not paper_ids:
        return None

    preview = ", ".join(paper_ids[:3])
    if len(paper_ids) > 3:
        preview += f" (+{len(paper_ids) - 3} more)"
    return preview


def _processor_gate_manual_review_scope_samples_compact_text(
    *,
    threshold_relevant: object,
    excluded_manual_override: object,
    excluded_indexed_pending: object,
    excluded_fixture_or_test: object,
) -> str | None:
    parts: list[str] = []

    relevant_preview = _processor_gate_sample_ids_preview(threshold_relevant)
    if relevant_preview:
        parts.append(f"relevant={relevant_preview}")

    manual_override_preview = _processor_gate_sample_ids_preview(excluded_manual_override)
    if manual_override_preview:
        parts.append(f"excluded.manual_override={manual_override_preview}")

    indexed_pending_preview = _processor_gate_sample_ids_preview(excluded_indexed_pending)
    if indexed_pending_preview:
        parts.append(f"excluded.indexed_pending={indexed_pending_preview}")

    fixture_or_test_preview = _processor_gate_sample_ids_preview(excluded_fixture_or_test)
    if fixture_or_test_preview:
        parts.append(f"excluded.fixture_or_test={fixture_or_test_preview}")

    return " | ".join(parts) or None


def _intake_override_audit_calibration_metadata() -> dict[str, object]:
    try:
        snapshot = build_intake_override_audit_calibration_snapshot(
            root=default_intake_override_audits_root(),
            warn_threshold=LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
            min_audited_docs=LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
        )
    except Exception:
        return {}

    advice = None
    raw_recommendations = snapshot.get("recommendations")
    if isinstance(raw_recommendations, list):
        for candidate in raw_recommendations:
            text = str(candidate or "").strip()
            if text:
                advice = text
                break

    total_runs = int(snapshot.get("total_runs") or 0)
    eligible_runs = int(snapshot.get("eligible_runs") or 0)
    target_runs = int(snapshot.get("calibration_target_runs") or 0)
    warn_runs = int(snapshot.get("warn_runs") or 0)
    return {
        "total_runs": total_runs,
        "eligible_runs": eligible_runs,
        "warn_runs": warn_runs,
        "calibration_target_runs": target_runs,
        "target_met": bool(target_runs > 0 and eligible_runs >= target_runs),
        "advice": advice,
    }


def _resolved_optional_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        return path.expanduser().resolve(strict=False)
    except Exception:
        return None


def _paths_overlap(first: Path, second: Path) -> bool:
    if first == second:
        return True
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def _configured_external_root_check(name: str, path: Path) -> RuntimeReadinessCheck:
    resolved = path.expanduser().resolve(strict=False)
    if resolved.exists():
        return RuntimeReadinessCheck(
            name=name,
            status="ok",
            detail="configured external root exists",
            path=str(resolved),
        )
    return RuntimeReadinessCheck(
        name=name,
        status="warn",
        detail="configured external root is missing",
        path=str(resolved),
    )


def _machine_pickup_path_check(
    name: str,
    path: Path | None,
    *,
    ok_detail: str,
    warn_detail: str,
    dependency_check: RuntimeReadinessCheck | None = None,
    dependency_error_detail: str | None = None,
) -> RuntimeReadinessCheck:
    resolved_path = path.expanduser().resolve(strict=False) if path is not None else None

    if dependency_check is not None and dependency_check.status == "error":
        return RuntimeReadinessCheck(
            name=name,
            status="error",
            detail=dependency_error_detail or dependency_check.detail,
            path=str(resolved_path) if resolved_path is not None else None,
        )

    if path is None:
        return RuntimeReadinessCheck(
            name=name,
            status="warn",
            detail=warn_detail,
        )

    if resolved_path is not None and resolved_path.exists():
        return RuntimeReadinessCheck(
            name=name,
            status="ok",
            detail=ok_detail,
            path=str(resolved_path),
        )

    return RuntimeReadinessCheck(
        name=name,
        status="warn",
        detail=warn_detail,
        path=str(resolved_path) if resolved_path is not None else None,
    )


def _watch_folder_boundary_check(loaded_config) -> RuntimeReadinessCheck:
    watch_folder = _resolved_optional_path(getattr(loaded_config.paths, "watch_folder", None))
    if watch_folder is None:
        return RuntimeReadinessCheck(
            name="watch_folder_boundary",
            status="ok",
            detail="watch folder is not configured; no managed output overlap detected",
        )

    conflicts: list[str] = []
    for label, path_value in (
        ("upload_dir", getattr(loaded_config.paths, "upload_dir", None)),
        ("pdf_storage_dir", getattr(loaded_config.paths, "pdf_storage_dir", None)),
    ):
        resolved = _resolved_optional_path(path_value)
        if resolved is not None and _paths_overlap(watch_folder, resolved):
            conflicts.append(f"{label}={resolved}")

    if conflicts:
        return RuntimeReadinessCheck(
            name="watch_folder_boundary",
            status="warn",
            detail=(
                "watch folder overlaps managed output paths; "
                f"`paperpipe watch` will fail until this is separated: {', '.join(conflicts)}"
            ),
            path=str(watch_folder),
        )

    return RuntimeReadinessCheck(
        name="watch_folder_boundary",
        status="ok",
        detail="watch folder does not overlap managed output paths",
        path=str(watch_folder),
    )


def _downloads_watch_boundary_check(loaded_config) -> RuntimeReadinessCheck:
    downloads_watch_dir = _resolved_optional_path(getattr(loaded_config.paths, "downloads_watch_dir", None))
    if downloads_watch_dir is None:
        return RuntimeReadinessCheck(
            name="downloads_watch_dir_boundary",
            status="ok",
            detail="downloads watch folder is not configured; no managed output overlap detected",
        )

    pdf_storage_dir = _resolved_optional_path(getattr(loaded_config.paths, "pdf_storage_dir", None))
    if pdf_storage_dir is not None and _paths_overlap(downloads_watch_dir, pdf_storage_dir):
        return RuntimeReadinessCheck(
            name="downloads_watch_dir_boundary",
            status="warn",
            detail=(
                "downloads watch folder overlaps PDF storage; "
                f"`paperpipe watch-downloads` will fail until this is separated: pdf_storage_dir={pdf_storage_dir}"
            ),
            path=str(downloads_watch_dir),
        )

    return RuntimeReadinessCheck(
        name="downloads_watch_dir_boundary",
        status="ok",
        detail="downloads watch folder does not overlap PDF storage",
        path=str(downloads_watch_dir),
    )


def _summary_check_status(checks: list[RuntimeReadinessCheck]) -> str:
    if any(check.status == "error" for check in checks):
        return "error"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "ok"


def _overall_status_for_checks(checks: list[RuntimeReadinessCheck]) -> str:
    if any(check.status == "error" for check in checks):
        return "error"
    if any(check.status == "warn" for check in checks):
        return "degraded"
    return "ok"


def _browser_safe_summary_check(
    *,
    name: str,
    source_checks: list[RuntimeReadinessCheck],
    ok_detail: str,
    warn_detail: str,
    error_detail: str,
) -> RuntimeReadinessCheck | None:
    if not source_checks:
        return None

    status = _summary_check_status(source_checks)
    detail = ok_detail
    if status == "warn":
        detail = warn_detail
    elif status == "error":
        detail = error_detail
    return RuntimeReadinessCheck(name=name, status=status, detail=detail)


def _browser_safe_processor_gate_threshold_review_metadata(
    metadata: Mapping[str, object] | None,
) -> dict[str, object]:
    browser_metadata = dict(metadata or {})
    raw_replay_review_command = str(
        browser_metadata.pop("threshold_replay_review_command", "") or ""
    ).strip()
    raw_threshold_review_command = str(
        browser_metadata.pop("threshold_review_command", "") or ""
    ).strip()
    raw_threshold_change_validation_command = str(
        browser_metadata.pop("threshold_change_validation_replay_command_template", "")
        or ""
    ).strip()
    raw_validation_replay_command = str(
        browser_metadata.pop("validation_replay_command_template", "") or ""
    ).strip()
    if raw_replay_review_command or raw_threshold_review_command:
        browser_metadata["threshold_replay_review_command_available"] = True
    if raw_threshold_change_validation_command or raw_validation_replay_command:
        browser_metadata["threshold_change_validation_replay_command_available"] = True
    return browser_metadata


def _frontend_roots() -> tuple[Path, Path]:
    frontend_dir = frontend_runtime_dir()
    return frontend_dir / "dist" / "index.html", frontend_dir / "index.html"


def _looks_like_cli_launcher(path: Path) -> bool:
    name = path.name.lower()
    if name in {"paperpipe", "paperpipe.exe", "lattice", "lattice.exe"}:
        return True
    return len(path.parts) >= 3 and path.parts[-3:] == ("Contents", "MacOS", "Lattice")


def _resolved_cli_entrypoint_command() -> list[str] | None:
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add_candidate(path: Path | None) -> None:
        if path is None:
            return
        resolved = path.expanduser().resolve(strict=False)
        if not resolved.exists():
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        candidates.append(resolved)

    argv0 = sys.argv[0] if sys.argv else ""
    if argv0:
        argv0_path = Path(argv0)
        resolved_argv0 = argv0_path.expanduser().resolve(strict=False)
        if _looks_like_cli_launcher(resolved_argv0):
            _add_candidate(resolved_argv0)

    if os.name == "nt":
        _add_candidate(REPO_ROOT / ".venv" / "Scripts" / "paperpipe.exe")
        _add_candidate(REPO_ROOT / "dist" / "lattice.exe")
    else:
        _add_candidate(REPO_ROOT / ".venv" / "bin" / "paperpipe")
        _add_candidate(REPO_ROOT / "dist" / "lattice")
        _add_candidate(REPO_ROOT / "dist" / "Lattice.app" / "Contents" / "MacOS" / "Lattice")

    if not candidates:
        return None
    return [str(candidates[0])]


def _backend_entrypoint_check() -> RuntimeReadinessCheck:
    try:
        importlib.import_module("backend.main")
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        return RuntimeReadinessCheck(
            name="backend_entrypoint",
            status="error",
            detail=(
                f"backend entrypoint import failed: missing dependency '{missing}'. "
                "Install runtime dependencies with `python -m pip install -r requirements.txt`. "
                "If local repo verification is failing before tests really start, rebuild the bounded verification env with "
                "`python3 scripts/bootstrap_verification_env.py --run-id local_verification_bootstrap`."
            ),
        )
    except Exception as exc:
        return RuntimeReadinessCheck(
            name="backend_entrypoint",
            status="error",
            detail=f"backend entrypoint import failed: {exc}",
        )
    return RuntimeReadinessCheck(
        name="backend_entrypoint",
        status="ok",
        detail="backend entrypoint imports successfully",
    )


def _cli_entrypoint_check() -> RuntimeReadinessCheck:
    command = _resolved_cli_entrypoint_command()
    if command is None:
        return RuntimeReadinessCheck(
            name="cli_entrypoint",
            status="warn",
            detail="CLI entrypoint smoke skipped: no repo-local or packaged launcher detected",
        )

    launcher_path = command[0]
    try:
        completed = subprocess.run(
            [*command, "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=CLI_ENTRYPOINT_HELP_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return RuntimeReadinessCheck(
            name="cli_entrypoint",
            status="error",
            detail=(
                "CLI entrypoint did not respond to `--help` within "
                f"{CLI_ENTRYPOINT_HELP_TIMEOUT_SECONDS}s"
            ),
            path=launcher_path,
        )
    except Exception as exc:
        return RuntimeReadinessCheck(
            name="cli_entrypoint",
            status="error",
            detail=f"CLI entrypoint smoke failed: {exc}",
            path=launcher_path,
        )

    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()
        if len(tail) > 240:
            tail = tail[-240:]
        detail = f"CLI entrypoint failed for `--help` (exit {completed.returncode})"
        if tail:
            detail = f"{detail}: {tail}"
        return RuntimeReadinessCheck(
            name="cli_entrypoint",
            status="error",
            detail=detail,
            path=launcher_path,
        )

    return RuntimeReadinessCheck(
        name="cli_entrypoint",
        status="ok",
        detail="CLI entrypoint responds to `--help`",
        path=launcher_path,
    )


def _privacy_preflight_config_check() -> RuntimeReadinessCheck:
    configured = bool(os.getenv(PRIVACY_PREFLIGHT_ROLLBACK_FLAG, "").strip())
    metadata = {
        "rollback_flag": PRIVACY_PREFLIGHT_ROLLBACK_FLAG,
        "configured": configured,
        "mode_valid": True,
        "allowed_modes": ["off", "report_only", "block_on_review"],
        "pilot_scope": "clinical_extraction_external_payload",
        "mutation_allowed": False,
    }
    try:
        mode = resolve_privacy_preflight_mode()
    except ValueError:
        return RuntimeReadinessCheck(
            name="privacy_preflight_config",
            status="error",
            detail=(
                f"{PRIVACY_PREFLIGHT_ROLLBACK_FLAG} is invalid; "
                "set it to one of: off, report_only, block_on_review"
            ),
            metadata={**metadata, "mode_valid": False, "effective_mode": None},
        )

    if mode == "off":
        detail = "privacy preflight is disabled; off is the default rollback mode"
    elif mode == "report_only":
        detail = "privacy preflight is report-only for the clinical extraction external payload"
    else:
        detail = "privacy preflight blocks clinical extraction external payloads that require review"

    return RuntimeReadinessCheck(
        name="privacy_preflight_config",
        status="ok",
        detail=detail,
        metadata={**metadata, "effective_mode": mode},
    )


def _latest_intake_override_audit_check() -> RuntimeReadinessCheck:
    latest_run = latest_intake_override_audit_run()
    if latest_run is None:
        return RuntimeReadinessCheck(
            name="latest_intake_override_audit",
            status="ok",
            detail="no intake override audit runs found yet",
            path=str(default_intake_override_audits_root()),
            metadata={"available": False, "quality_signals": []},
        )
    metadata = {
        "available": True,
        "run_id": latest_run.name,
    }
    try:
        summary = latest_intake_override_audit_summary()
    except Exception:
        summary = None
    if summary is not None:
        quality_signals: list[str] = []
        if summary.metrics.slot_disagreement_rate > 0.0:
            quality_signals.append("slot_disagreement_present")
        if summary.metrics.selection_fallback_rate > 0.0:
            quality_signals.append("selection_fallback_present")
        if summary.metrics.triage_override_rate > 0.0:
            quality_signals.append("triage_override_present")
        if summary.metrics.llm_slot_adjudication_rate > 0.0:
            quality_signals.append("slot_adjudication_present")
        if summary.metrics.llm_tagging_adjudication_rate > 0.0:
            quality_signals.append("tagging_adjudication_present")
        if summary.metrics.analysis_unavailable_rate > 0.0:
            quality_signals.append("analysis_unavailable_present")
        if summary.metrics.issues_state_unavailable_rate > 0.0:
            quality_signals.append("issues_state_unavailable_present")
        metadata.update(
            {
                "generated_at": summary.generated_at.isoformat(),
                "source": summary.inputs.source,
                "row_count": summary.inputs.row_count,
                "audited_document_count": summary.metrics.audited_document_count,
                "triage_override_rate": summary.metrics.triage_override_rate,
                "slot_disagreement_rate": summary.metrics.slot_disagreement_rate,
                "selection_fallback_count": summary.metrics.selection_fallback_count,
                "selection_fallback_rate": summary.metrics.selection_fallback_rate,
                "slot_disagreement_count": summary.metrics.slot_disagreement_count,
                "llm_slot_adjudication_rate": summary.metrics.llm_slot_adjudication_rate,
                "llm_tagging_adjudication_rate": summary.metrics.llm_tagging_adjudication_rate,
                "analysis_unavailable_rate": summary.metrics.analysis_unavailable_rate,
                "issues_state_unavailable_rate": summary.metrics.issues_state_unavailable_rate,
                "quality_signals": quality_signals,
            }
        )
    return RuntimeReadinessCheck(
        name="latest_intake_override_audit",
        status="ok",
        detail=f"latest intake override audit is available ({latest_run.name})",
        path=str(latest_run / "audit.md"),
        metadata=metadata,
    )


def _latest_intake_override_audit_quality_check(
    latest_audit_check: RuntimeReadinessCheck | None = None,
) -> RuntimeReadinessCheck:
    latest_check = latest_audit_check or _latest_intake_override_audit_check()
    metadata = dict(latest_check.metadata or {})
    if not bool(metadata.get("available")):
        return RuntimeReadinessCheck(
            name="latest_intake_override_audit_quality",
            status="ok",
            detail="no intake override audit available for quality heuristic",
            metadata={
                "available": False,
                "warn_threshold": LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
                "min_audited_docs": LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
            },
        )

    audited_count = metadata.get("audited_document_count")
    audited_docs = None if audited_count in (None, "") else int(audited_count)
    quality_signals = metadata.get("quality_signals")
    base_metadata = {
        "available": True,
        "warn_threshold": LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
        "min_audited_docs": LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
        "audited_document_count": audited_docs,
        "sample_sufficient": bool(
            audited_docs is not None and audited_docs >= LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS
        ),
        "quality_signals": list(quality_signals) if isinstance(quality_signals, list) else [],
    }
    calibration_metadata = _intake_override_audit_calibration_metadata()
    if calibration_metadata:
        base_metadata["calibration"] = calibration_metadata
    if audited_docs is None:
        return RuntimeReadinessCheck(
            name="latest_intake_override_audit_quality",
            status="ok",
            detail="latest intake override audit summary is missing audited counts for quality heuristic",
            metadata=base_metadata,
        )
    if audited_docs < LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS:
        return RuntimeReadinessCheck(
            name="latest_intake_override_audit_quality",
            status="ok",
            detail=(
                "latest intake override audit sample is too small for the warning heuristic "
                f"(audited={audited_docs} < {LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS})"
            ),
            metadata=base_metadata,
        )

    concerns: list[str] = []
    for label, key in (
        ("triage", "triage_override_rate"),
        ("slot", "slot_disagreement_rate"),
        ("slot_adjudication", "llm_slot_adjudication_rate"),
        ("tagging_adjudication", "llm_tagging_adjudication_rate"),
        ("fallback", "selection_fallback_rate"),
        ("analysis", "analysis_unavailable_rate"),
        ("issues", "issues_state_unavailable_rate"),
    ):
        rate = _safe_float(metadata.get(key))
        if rate is None:
            continue
        if rate >= LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE:
            concerns.append(f"{label}={rate:.1%}")

    if concerns:
        detail = "latest intake override audit quality needs attention: " + ", ".join(concerns)
        status = "warn"
    elif isinstance(quality_signals, list) and quality_signals:
        detail = "latest intake override audit has minor quality signals below the warning threshold"
        status = "ok"
    else:
        detail = "latest intake override audit quality looks stable"
        status = "ok"

    return RuntimeReadinessCheck(
        name="latest_intake_override_audit_quality",
        status=status,
        detail=detail,
        metadata=base_metadata,
    )


def _latest_intake_override_threshold_review_check() -> RuntimeReadinessCheck:
    latest_run = latest_intake_override_threshold_review_run()
    if latest_run is None:
        return RuntimeReadinessCheck(
            name="latest_intake_override_threshold_review",
            status="ok",
            detail="no intake override threshold review runs found yet",
            path=str(default_intake_override_threshold_review_root()),
            metadata={"available": False},
        )

    metadata: dict[str, object] = {
        "available": True,
        "run_id": latest_run.name,
    }
    try:
        summary = latest_intake_override_threshold_review_summary()
    except Exception:
        summary = None

    if isinstance(summary, dict):
        raw_provenance = summary.get("provenance")
        if isinstance(raw_provenance, dict):
            metadata["provenance_kind"] = str(raw_provenance.get("kind") or "") or None
            if isinstance(raw_provenance.get("latest_eligible"), bool):
                metadata["latest_eligible"] = raw_provenance.get("latest_eligible")
        decision = summary.get("decision")
        inputs = summary.get("inputs")
        if isinstance(inputs, dict):
            metadata.update(
                {
                    "warn_threshold": _safe_float(inputs.get("warn_threshold")),
                    "min_audited_docs": _safe_int(inputs.get("min_audited_docs")),
                    "calibration_target_runs": _safe_int(inputs.get("calibration_target_runs")),
                }
            )
        if isinstance(decision, dict):
            raw_focus_signals = decision.get("focus_signals")
            raw_latest_warn_signals = decision.get("latest_warn_signals")
            raw_blocking_action = decision.get("blocking_action")
            raw_blocking_summary = decision.get("blocking_summary")
            raw_tuning_targets = decision.get("tuning_targets")
            raw_tuning_actions = decision.get("tuning_actions")
            raw_action_plan = decision.get("action_plan")
            raw_tuning_recommendations = decision.get("tuning_recommendations")
            metadata.update(
                {
                    "generated_at": str(summary.get("generated_at") or "") or None,
                    "recommended_action": str(decision.get("recommended_action") or "") or None,
                    "review_ready": bool(decision.get("review_ready")),
                    "decision_reason": str(decision.get("decision_reason") or "") or None,
                    "next_step": str(decision.get("next_step") or "") or None,
                    "latest_run_id": str(decision.get("latest_run_id") or "") or None,
                    "latest_run_status": str(decision.get("latest_run_status") or "") or None,
                    "focus_signals": (
                        [str(item) for item in raw_focus_signals if str(item)]
                        if isinstance(raw_focus_signals, list)
                        else []
                    ),
                    "latest_warn_signals": (
                        [str(item) for item in raw_latest_warn_signals if str(item)]
                        if isinstance(raw_latest_warn_signals, list)
                        else []
                    ),
                    "blocking_action": (
                        {
                            "order": int(raw_blocking_action.get("order") or 0),
                            "action": str(raw_blocking_action.get("action") or ""),
                            "target": str(raw_blocking_action.get("target") or ""),
                            "blocking": bool(raw_blocking_action.get("blocking")),
                            "signals": [
                                str(signal)
                                for signal in raw_blocking_action.get("signals", [])
                                if str(signal)
                            ],
                            "summary": str(raw_blocking_action.get("summary") or ""),
                            "evidence": str(raw_blocking_action.get("evidence") or ""),
                        }
                        if isinstance(raw_blocking_action, dict)
                        else None
                    ),
                    "blocking_summary": str(raw_blocking_summary or "") or None,
                    "tuning_targets": (
                        [str(item) for item in raw_tuning_targets if str(item)]
                        if isinstance(raw_tuning_targets, list)
                        else []
                    ),
                    "tuning_actions": (
                        [
                            {
                                "target": str(item.get("target") or ""),
                                "action": str(item.get("action") or ""),
                                "summary": str(item.get("summary") or ""),
                            }
                            for item in raw_tuning_actions
                            if isinstance(item, dict)
                        ]
                        if isinstance(raw_tuning_actions, list)
                        else []
                    ),
                    "action_plan": (
                        [
                            {
                                "order": int(item.get("order") or 0),
                                "action": str(item.get("action") or ""),
                                "target": str(item.get("target") or ""),
                                "blocking": bool(item.get("blocking")),
                                "signals": [
                                    str(signal)
                                    for signal in item.get("signals", [])
                                    if str(signal)
                                ],
                                "summary": str(item.get("summary") or ""),
                                "evidence": str(item.get("evidence") or ""),
                            }
                            for item in raw_action_plan
                            if isinstance(item, dict)
                        ]
                        if isinstance(raw_action_plan, list)
                        else []
                    ),
                    "tuning_recommendations": (
                        [str(item) for item in raw_tuning_recommendations if str(item)]
                        if isinstance(raw_tuning_recommendations, list)
                        else []
                    ),
                }
            )

    return RuntimeReadinessCheck(
        name="latest_intake_override_threshold_review",
        status="ok",
        detail=f"latest intake override threshold review is available ({latest_run.name})",
        path=str(latest_run / "summary.json"),
        metadata=metadata,
    )


def _latest_processor_gate_threshold_review_check() -> RuntimeReadinessCheck:
    latest_run = latest_processor_gate_threshold_review_run()
    if latest_run is None:
        return RuntimeReadinessCheck(
            name="latest_processor_gate_threshold_review",
            status="ok",
            detail="no processor gate threshold review runs found yet",
            path=str(default_processor_gate_threshold_review_root()),
            metadata={"available": False},
        )

    threshold_change_proposal_path = latest_run / "threshold_change_proposal.json"
    threshold_change_validation_replay_command_available = False
    if threshold_change_proposal_path.exists():
        try:
            threshold_change_proposal = json.loads(
                threshold_change_proposal_path.read_text(encoding="utf-8")
            )
            if isinstance(threshold_change_proposal, dict):
                threshold_change_validation_replay_command_available = bool(
                    str(
                        threshold_change_proposal.get(
                            "validation_replay_command_template"
                        )
                        or ""
                    ).strip()
                )
        except Exception:
            threshold_change_validation_replay_command_available = False

    metadata: dict[str, object] = {
        "available": True,
        "run_id": latest_run.name,
        "markdown_available": bool((latest_run / "audit.md").exists()),
        "manual_review_rows_available": bool((latest_run / "manual_review_rows.json").exists()),
        "manual_review_markdown_available": bool((latest_run / "manual_review.md").exists()),
        "manual_review_checklist_available": bool((latest_run / "manual_review_checklist.csv").exists()),
        "manual_review_basis_markdown_available": bool((latest_run / "manual_review_basis.md").exists()),
        "threshold_change_proposal_available": bool(threshold_change_proposal_path.exists()),
        "threshold_change_proposal_markdown_available": bool((latest_run / "threshold_change_proposal.md").exists()),
        "threshold_change_validation_replay_command_available": (
            threshold_change_validation_replay_command_available
        ),
    }
    try:
        summary = load_processor_gate_threshold_review_summary(latest_run)
    except Exception:
        summary = None

    if isinstance(summary, dict):
        decision = summary.get("decision")
        inputs = summary.get("inputs")
        signal_summary = summary.get("signal_summary")
        manual_review_scope = summary.get("manual_review_scope")
        manual_review_basis = (
            summary.get("manual_review_basis") if isinstance(summary.get("manual_review_basis"), dict) else {}
        )
        drift_artifacts = resolve_processor_gate_threshold_review_drift_artifacts(
            summary,
            threshold_change_proposal_path=threshold_change_proposal_path,
        )
        metadata.update(
            {
                "drift_summary_available": bool(drift_artifacts.get("drift_summary_available")),
                "drift_details_available": bool(drift_artifacts.get("drift_details_available")),
                "drift_markdown_available": bool(drift_artifacts.get("drift_markdown_available")),
                "threshold_replay_available": bool(drift_artifacts.get("threshold_replay_available")),
                "threshold_replay_markdown_available": bool(
                    drift_artifacts.get("threshold_replay_markdown_available")
                ),
                "threshold_replay_review_command_available": bool(
                    drift_artifacts.get("threshold_replay_review_command")
                ),
                "threshold_change_validation_replay_available": bool(
                    drift_artifacts.get("threshold_change_validation_replay_available")
                ),
                "threshold_change_validation_replay_matches_proposal": bool(
                    drift_artifacts.get(
                        "threshold_change_validation_replay_matches_proposal"
                    )
                ),
                "threshold_change_validation_replay_needs_rerun": bool(
                    drift_artifacts.get("threshold_change_validation_replay_needs_rerun")
                ),
                "threshold_change_validation_replay_status": drift_artifacts.get(
                    "threshold_change_validation_replay_status"
                ),
                "threshold_change_manual_decision_ready": bool(
                    drift_artifacts.get("threshold_change_manual_decision_ready")
                ),
                "threshold_change_manual_decision_status": drift_artifacts.get(
                    "threshold_change_manual_decision_status"
                ),
                "threshold_change_manual_decision_blocker": drift_artifacts.get(
                    "threshold_change_manual_decision_blocker"
                ),
                "threshold_replay_text": drift_artifacts.get("threshold_replay_text"),
                "threshold_replay_mode": drift_artifacts.get("threshold_replay_mode"),
                "threshold_replay_high_threshold": drift_artifacts.get(
                    "threshold_replay_high_threshold"
                ),
                "threshold_replay_low_threshold": drift_artifacts.get(
                    "threshold_replay_low_threshold"
                ),
                "threshold_replay_reviewed_high_threshold": drift_artifacts.get(
                    "threshold_replay_reviewed_high_threshold"
                ),
                "threshold_replay_proposal_run_id": drift_artifacts.get(
                    "threshold_replay_proposal_run_id"
                ),
            }
        )
        if isinstance(inputs, dict):
            metadata.update(
                {
                    "generated_at": str(summary.get("generated_at") or "") or None,
                    "high_threshold": _safe_float(inputs.get("high_threshold")),
                    "low_threshold": _safe_float(inputs.get("low_threshold")),
                    "min_candidate_rows": _safe_int(inputs.get("min_candidate_rows")),
                    "drift_warn_threshold": _safe_float(inputs.get("drift_warn_threshold")),
                }
            )
        if isinstance(decision, dict):
            raw_focus_areas = decision.get("focus_areas")
            raw_tuning_targets = decision.get("tuning_targets")
            raw_tuning_actions = decision.get("tuning_actions")
            raw_action_plan = decision.get("action_plan")
            metadata.update(
                {
                    "recommended_action": str(decision.get("recommended_action") or "") or None,
                    "review_ready": bool(decision.get("review_ready")),
                    "decision_reason": str(decision.get("decision_reason") or "") or None,
                    "next_step": str(decision.get("next_step") or "") or None,
                    "latest_run_id": str(decision.get("latest_run_id") or "") or None,
                    "latest_run_status": str(decision.get("latest_run_status") or "") or None,
                    "threshold_change_ready": bool(decision.get("threshold_change_ready"))
                    if "threshold_change_ready" in decision
                    else None,
                    "threshold_change_status": str(decision.get("threshold_change_status") or "")
                    or None,
                    "threshold_change_next_step": str(
                        decision.get("threshold_change_next_step") or ""
                    )
                    or None,
                    "threshold_change_blocker": str(decision.get("threshold_change_blocker") or "")
                    or None,
                    "threshold_change_text": _processor_gate_threshold_change_compact_text(
                        decision
                    ),
                    "focus_areas": (
                        [str(item) for item in raw_focus_areas if str(item)]
                        if isinstance(raw_focus_areas, list)
                        else []
                    ),
                    "tuning_targets": (
                        [str(item) for item in raw_tuning_targets if str(item)]
                        if isinstance(raw_tuning_targets, list)
                        else []
                    ),
                    "tuning_actions": (
                        [
                            {
                                "target": str(item.get("target") or "") or None,
                                "action": str(item.get("action") or "") or None,
                                "summary": str(item.get("summary") or "") or None,
                            }
                            for item in raw_tuning_actions
                            if isinstance(item, dict)
                        ]
                        if isinstance(raw_tuning_actions, list)
                        else []
                    ),
                    "action_plan": (
                        [
                            {
                                "order": _safe_int(item.get("order")),
                                "action": str(item.get("action") or "") or None,
                                "target": str(item.get("target") or "") or None,
                                "blocking": bool(item.get("blocking")),
                                "summary": str(item.get("summary") or "") or None,
                            }
                            for item in raw_action_plan
                            if isinstance(item, dict)
                        ]
                        if isinstance(raw_action_plan, list)
                        else []
                    ),
                }
            )
        if isinstance(signal_summary, dict):
            metadata.update(
                {
                    "candidate_count": _safe_int(signal_summary.get("candidate_count")),
                    "promotable_count": _safe_int(signal_summary.get("promotable_count")),
                    "drift_count": _safe_int(signal_summary.get("drift_count")),
                    "drift_rate": _safe_float(signal_summary.get("drift_rate")),
                }
            )
        if isinstance(manual_review_scope, dict):
            threshold_relevant = (
                manual_review_scope.get("threshold_relevant")
                if isinstance(manual_review_scope.get("threshold_relevant"), dict)
                else {}
            )
            policy_edge_cases = (
                manual_review_scope.get("policy_edge_cases")
                if isinstance(manual_review_scope.get("policy_edge_cases"), dict)
                else {}
            )
            excluded = (
                manual_review_scope.get("excluded")
                if isinstance(manual_review_scope.get("excluded"), dict)
                else {}
            )
            worksheet_summary = (
                manual_review_scope.get("worksheet_summary")
                if isinstance(manual_review_scope.get("worksheet_summary"), dict)
                else {}
            )
            threshold_relevant_paper_ids = (
                [str(item).strip() for item in threshold_relevant.get("paper_ids", []) if str(item).strip()][:3]
                if isinstance(threshold_relevant.get("paper_ids"), list)
                else []
            )
            manual_override_paper_ids = (
                [
                    str(item).strip()
                    for item in (excluded.get("manual_override") or {}).get("paper_ids", [])
                    if str(item).strip()
                ][:3]
                if isinstance((excluded.get("manual_override") or {}).get("paper_ids"), list)
                else []
            )
            indexed_pending_paper_ids = (
                [
                    str(item).strip()
                    for item in (excluded.get("indexed_pending") or {}).get("paper_ids", [])
                    if str(item).strip()
                ][:3]
                if isinstance((excluded.get("indexed_pending") or {}).get("paper_ids"), list)
                else []
            )
            fixture_or_test_paper_ids = (
                [
                    str(item).strip()
                    for item in (excluded.get("fixture_or_test") or {}).get("paper_ids", [])
                    if str(item).strip()
                ][:3]
                if isinstance((excluded.get("fixture_or_test") or {}).get("paper_ids"), list)
                else []
            )
            threshold_relevant_count = _safe_int(threshold_relevant.get("count"))
            policy_edge_case_count = _safe_int(policy_edge_cases.get("count"))
            excluded_manual_override_count = _safe_int(
                (excluded.get("manual_override") or {}).get("count")
                if isinstance(excluded.get("manual_override"), dict)
                else None
            )
            excluded_indexed_pending_count = _safe_int(
                (excluded.get("indexed_pending") or {}).get("count")
                if isinstance(excluded.get("indexed_pending"), dict)
                else None
            )
            excluded_fixture_or_test_count = _safe_int(
                (excluded.get("fixture_or_test") or {}).get("count")
                if isinstance(excluded.get("fixture_or_test"), dict)
                else None
            )
            excluded_other_count = _safe_int(
                (excluded.get("other") or {}).get("count")
                if isinstance(excluded.get("other"), dict)
                else None
            )
            metadata.update(
                {
                    "threshold_relevant_count": threshold_relevant_count,
                    "policy_edge_case_count": policy_edge_case_count,
                    "excluded_manual_override_count": excluded_manual_override_count,
                    "excluded_indexed_pending_count": excluded_indexed_pending_count,
                    "excluded_fixture_or_test_count": excluded_fixture_or_test_count,
                    "excluded_other_count": excluded_other_count,
                    "manual_review_scope_text": _processor_gate_manual_review_scope_compact_text(
                        threshold_relevant_count=threshold_relevant_count,
                        policy_edge_case_count=policy_edge_case_count,
                        excluded_manual_override_count=excluded_manual_override_count,
                        excluded_indexed_pending_count=excluded_indexed_pending_count,
                        excluded_fixture_or_test_count=excluded_fixture_or_test_count,
                        excluded_other_count=excluded_other_count,
                    ),
                    "manual_review_scope_samples_text": _processor_gate_manual_review_scope_samples_compact_text(
                        threshold_relevant=threshold_relevant,
                        excluded_manual_override=excluded.get("manual_override"),
                        excluded_indexed_pending=excluded.get("indexed_pending"),
                        excluded_fixture_or_test=excluded.get("fixture_or_test"),
                    ),
                    "threshold_relevant_sample_ids": threshold_relevant_paper_ids,
                    "excluded_manual_override_sample_ids": manual_override_paper_ids,
                    "excluded_indexed_pending_sample_ids": indexed_pending_paper_ids,
                    "excluded_fixture_or_test_sample_ids": fixture_or_test_paper_ids,
                    "manual_review_focus_recommendation": str(
                        manual_review_scope.get("focus_recommendation") or ""
                    )
                    or None,
                    "worksheet_pending_count": _safe_int(worksheet_summary.get("pending_count")),
                    "worksheet_primary_review_target": str(
                        worksheet_summary.get("primary_review_target") or ""
                    )
                    or None,
                    "worksheet_excluded_count": _safe_int(worksheet_summary.get("excluded_count")),
                    "worksheet_text": _processor_gate_worksheet_compact_text(worksheet_summary),
                    "worksheet_summary": str(worksheet_summary.get("summary") or "") or None,
                }
            )
        if isinstance(manual_review_basis, dict):
            metadata.update(
                {
                    "manual_review_basis_preliminary_call": str(
                        manual_review_basis.get("preliminary_call") or ""
                    )
                    or None,
                    "manual_review_basis_policy_support_count": _safe_int(
                        manual_review_basis.get("mid_confidence_policy_support_count")
                    ),
                    "manual_review_basis_high_threshold_support_count": _safe_int(
                        manual_review_basis.get("high_threshold_support_count")
                    ),
                    "manual_review_basis_text": _processor_gate_basis_compact_text(
                        manual_review_basis
                    ),
                    "manual_review_basis_summary": str(manual_review_basis.get("summary") or "")
                    or None,
                }
            )

    return RuntimeReadinessCheck(
        name="latest_processor_gate_threshold_review",
        status="ok",
        detail=f"latest processor gate threshold review is available ({latest_run.name})",
        path=str(latest_run / "summary.json"),
        metadata=metadata,
    )


def _latest_slot_classification_tuning_review_check() -> RuntimeReadinessCheck:
    latest_run = latest_slot_classification_tuning_review_run()
    if latest_run is None:
        return RuntimeReadinessCheck(
            name="latest_slot_classification_tuning_review",
            status="ok",
            detail="no slot classification tuning review runs found yet",
            path=str(default_slot_classification_tuning_review_root()),
            metadata={"available": False},
        )

    metadata: dict[str, object] = {
        "available": True,
        "run_id": latest_run.name,
        "markdown_available": bool((latest_run / "audit.md").exists()),
    }
    try:
        summary = load_slot_classification_tuning_review_summary(latest_run)
    except Exception:
        summary = None

    if isinstance(summary, dict):
        decision = summary.get("decision")
        signal_summary = summary.get("signal_summary")
        metadata["generated_at"] = str(summary.get("generated_at") or "") or None
        if isinstance(decision, dict):
            raw_tuning_targets = decision.get("tuning_targets")
            raw_tuning_actions = decision.get("tuning_actions")
            raw_action_plan = decision.get("action_plan")
            raw_tuning_recommendations = decision.get("tuning_recommendations")
            metadata.update(
                {
                    "recommended_action": str(decision.get("recommended_action") or "") or None,
                    "review_ready": bool(decision.get("review_ready")),
                    "decision_reason": str(decision.get("decision_reason") or "") or None,
                    "next_step": str(decision.get("next_step") or "") or None,
                    "latest_compare_run_id": str(decision.get("latest_compare_run_id") or "") or None,
                    "paired_compare_status": str(decision.get("paired_compare_status") or "") or None,
                    "default_rerun_status": str(decision.get("default_rerun_status") or "") or None,
                    "boundary_rerun_status": str(decision.get("boundary_rerun_status") or "") or None,
                    "prompt_change_ready": bool(decision.get("prompt_change_ready")),
                    "prompt_change_status": str(decision.get("prompt_change_status") or "") or None,
                    "prompt_change_blocker": str(decision.get("prompt_change_blocker") or "") or None,
                    "tuning_targets": (
                        [str(item) for item in raw_tuning_targets if str(item)]
                        if isinstance(raw_tuning_targets, list)
                        else []
                    ),
                    "tuning_actions": (
                        [
                            {
                                "target": str(item.get("target") or "") or None,
                                "action": str(item.get("action") or "") or None,
                                "summary": str(item.get("summary") or "") or None,
                            }
                            for item in raw_tuning_actions
                            if isinstance(item, dict)
                        ]
                        if isinstance(raw_tuning_actions, list)
                        else []
                    ),
                    "action_plan": (
                        [
                            {
                                "order": _safe_int(item.get("order")),
                                "action": str(item.get("action") or "") or None,
                                "target": str(item.get("target") or "") or None,
                                "blocking": bool(item.get("blocking")),
                                "summary": str(item.get("summary") or "") or None,
                                "evidence": str(item.get("evidence") or "") or None,
                            }
                            for item in raw_action_plan
                            if isinstance(item, dict)
                        ]
                        if isinstance(raw_action_plan, list)
                        else []
                    ),
                    "tuning_recommendations": (
                        [str(item) for item in raw_tuning_recommendations if str(item)]
                        if isinstance(raw_tuning_recommendations, list)
                        else []
                    ),
                }
            )
        if isinstance(signal_summary, dict):
            metadata.update(
                {
                    "paired_compare_failed_checks": [
                        str(item)
                        for item in signal_summary.get("paired_compare_failed_checks", [])
                        if str(item)
                    ]
                    if isinstance(signal_summary.get("paired_compare_failed_checks"), list)
                    else [],
                    "paired_compare_regressions": [
                        str(item)
                        for item in signal_summary.get("paired_compare_regressions", [])
                        if str(item)
                    ]
                    if isinstance(signal_summary.get("paired_compare_regressions"), list)
                    else [],
                    "paired_compare_error_migration_detected": bool(
                        signal_summary.get("paired_compare_error_migration_detected")
                    ),
                    "default_rerun_drift_rate": _safe_float(
                        signal_summary.get("default_rerun_drift_rate")
                    ),
                    "boundary_rerun_drift_rate": _safe_float(
                        signal_summary.get("boundary_rerun_drift_rate")
                    ),
                    "default_rerun_drift_count": _safe_int(
                        signal_summary.get("default_rerun_drift_count")
                    ),
                    "boundary_rerun_drift_count": _safe_int(
                        signal_summary.get("boundary_rerun_drift_count")
                    ),
                }
            )

    return RuntimeReadinessCheck(
        name="latest_slot_classification_tuning_review",
        status="ok",
        detail=f"latest slot classification tuning review is available ({latest_run.name})",
        path=str(latest_run / "summary.json"),
        metadata=metadata,
    )


def _module_dependency_check(
    *,
    name: str,
    module_name: str,
    ok_detail: str,
    error_detail: str,
) -> RuntimeReadinessCheck:
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name or module_name
        if missing == module_name or missing.startswith(f"{module_name}."):
            return RuntimeReadinessCheck(name=name, status="error", detail=error_detail)
        return RuntimeReadinessCheck(
            name=name,
            status="error",
            detail=f"dependency import failed while loading '{module_name}': missing '{missing}'",
        )
    except Exception as exc:
        return RuntimeReadinessCheck(
            name=name,
            status="error",
            detail=f"dependency import failed while loading '{module_name}': {exc}",
        )
    return RuntimeReadinessCheck(name=name, status="ok", detail=ok_detail)


def collect_structured_state_hygiene_check(vault_path: Path) -> RuntimeReadinessCheck:
    resolved_vault = vault_path.expanduser().resolve(strict=False)

    if fixture_structured_state_allowed(resolved_vault):
        return RuntimeReadinessCheck(
            name="structured_state_hygiene",
            status="ok",
            detail="isolated E2E runtime allows fixture structured states",
            path=str(resolved_vault),
        )

    hidden_paths = hidden_fixture_structured_state_paths(resolved_vault)
    sample_relpaths = [path.relative_to(resolved_vault).as_posix() for path in hidden_paths[:3]]
    hidden_count = len(hidden_paths)
    state_root = resolved_vault / ".pp"

    if hidden_count:
        detail = (
            f"hidden fixture structured states detected ({hidden_count}); "
            "clean or quarantine them before trusting this vault"
        )
        if sample_relpaths:
            detail = f"{detail}: {', '.join(sample_relpaths)}"
        first_path = resolved_vault / sample_relpaths[0] if sample_relpaths else state_root
        return RuntimeReadinessCheck(
            name="structured_state_hygiene",
            status="warn",
            detail=detail,
            path=str(first_path),
        )

    return RuntimeReadinessCheck(
        name="structured_state_hygiene",
        status="ok",
        detail="no hidden fixture structured states detected",
        path=str(state_root),
    )


def collect_meeting_pack_storage_hygiene_check(
    vault_path: Path,
    *,
    root: Path | None = None,
    keep_latest: int = 3,
) -> RuntimeReadinessCheck:
    meeting_pack_root = (root or meeting_packs_root()).expanduser().resolve(strict=False)
    candidates = select_meeting_pack_archive_candidates(
        meeting_pack_root,
        vault_path=vault_path.expanduser().resolve(strict=False),
        keep_latest=keep_latest,
    )
    if not candidates:
        return RuntimeReadinessCheck(
            name="meeting_pack_storage_hygiene",
            status="ok",
            detail="no low-value Meeting Pack archive candidates detected",
            path=str(meeting_pack_root),
        )

    reason_counts: dict[str, int] = {}
    for candidate in candidates:
        reason_counts[candidate.reason] = reason_counts.get(candidate.reason, 0) + 1
    reason_summary = ", ".join(f"{reason}={count}" for reason, count in sorted(reason_counts.items()))
    sample_ids = ", ".join(candidate.pack_id for candidate in candidates[:3])
    detail = (
        f"Meeting Pack archive candidates detected ({len(candidates)}; {reason_summary}); "
        "archive with `paperpipe archive-meeting-pack-noise` before trusting saved pack listings"
    )
    if sample_ids:
        detail = f"{detail}: {sample_ids}"
    return RuntimeReadinessCheck(
        name="meeting_pack_storage_hygiene",
        status="warn",
        detail=detail,
        path=str(meeting_pack_root),
    )


def collect_fixture_paper_hygiene_check(
    *,
    db_path: Path | None = None,
) -> RuntimeReadinessCheck:
    runtime_db_path = (db_path or get_db_path()).expanduser().resolve(strict=False)
    if not runtime_db_path.exists():
        return RuntimeReadinessCheck(
            name="fixture_paper_hygiene",
            status="ok",
            detail="runtime DB not initialized yet; no fixture paper cleanup candidates detected",
            path=str(runtime_db_path),
        )

    try:
        conn = sqlite3.connect(runtime_db_path)
        try:
            candidates = select_fixture_paper_archive_candidates(conn)
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return RuntimeReadinessCheck(
                name="fixture_paper_hygiene",
                status="ok",
                detail="runtime DB has no papers table yet; no fixture paper cleanup candidates detected",
                path=str(runtime_db_path),
            )
        return RuntimeReadinessCheck(
            name="fixture_paper_hygiene",
            status="warn",
            detail=f"fixture paper hygiene check failed: {exc}",
            path=str(runtime_db_path),
        )

    if not candidates:
        return RuntimeReadinessCheck(
            name="fixture_paper_hygiene",
            status="ok",
            detail="no fixture paper cleanup candidates detected",
            path=str(runtime_db_path),
        )

    reason_counts: dict[str, int] = {}
    for candidate in candidates:
        reason_counts[candidate.fixture_reason] = reason_counts.get(candidate.fixture_reason, 0) + 1
    reason_summary = ", ".join(f"{reason}={count}" for reason, count in sorted(reason_counts.items()))
    sample_ids = ", ".join(candidate.paper_id for candidate in candidates[:3])
    candidate_count = len(candidates)
    status = "error" if candidate_count >= FIXTURE_PAPER_HYGIENE_ERROR_THRESHOLD else "warn"
    detail = (
        f"fixture paper cleanup candidates detected ({candidate_count}; {reason_summary}); "
        "archive with `paperpipe archive-fixture-no-feedback-papers` before trusting local classification-audit counts"
    )
    if status == "error":
        detail = (
            f"fixture paper cleanup candidates detected ({candidate_count}; {reason_summary}); "
            "too many fixture rows are distorting local classification-audit counts, so archive them with "
            "`paperpipe archive-fixture-no-feedback-papers` before trusting this runtime DB"
        )
    if sample_ids:
        detail = f"{detail}: {sample_ids}"
    return RuntimeReadinessCheck(
        name="fixture_paper_hygiene",
        status=status,
        detail=detail,
        path=str(runtime_db_path),
    )


def collect_queue_health_check(
    *,
    db_path: Path | None = None,
) -> RuntimeReadinessCheck:
    runtime_db_path = (db_path or get_db_path()).expanduser().resolve(strict=False)
    snapshot = collect_queue_health(
        runtime_db_path,
        stale_after_seconds=QUEUE_HEALTH_STALE_AFTER_SECONDS,
        queued_age_warn_after_seconds=QUEUE_HEALTH_QUEUED_AGE_WARN_AFTER_SECONDS,
    )
    metadata = dict(snapshot)
    available = bool(metadata.get("available"))
    queued_jobs_total = _safe_int(metadata.get("queued_jobs_total")) or 0
    running_jobs_total = _safe_int(metadata.get("running_jobs_total")) or 0
    oldest_queued_age_seconds = _safe_int(metadata.get("oldest_queued_age_seconds"))
    stale_running_suspected_total = _safe_int(metadata.get("stale_running_suspected_total")) or 0
    stale_running_reclaimed_total = _safe_int(metadata.get("stale_running_reclaimed_total")) or 0
    last_stale_running_reclaimed_at = str(metadata.get("last_stale_running_reclaimed_at") or "").strip() or None
    stale_running_requeued_total = _safe_int(metadata.get("stale_running_requeued_total")) or 0
    last_stale_running_requeued_at = str(metadata.get("last_stale_running_requeued_at") or "").strip() or None
    queue_age_warn_triggered = bool(
        queued_jobs_total > 0
        and oldest_queued_age_seconds is not None
        and oldest_queued_age_seconds >= QUEUE_HEALTH_QUEUED_AGE_WARN_AFTER_SECONDS
    )
    metadata["queue_age_warn_triggered"] = queue_age_warn_triggered
    metadata["stale_running_warn_triggered"] = bool(stale_running_suspected_total > 0)

    if not available:
        detail = (
            "runtime DB has no jobs table yet; no queued or running jobs detected"
            if runtime_db_path.exists()
            else "runtime DB not initialized yet; no queued or running jobs detected"
        )
        return RuntimeReadinessCheck(
            name="queue_health",
            status="ok",
            detail=detail,
            path=str(runtime_db_path),
            metadata=metadata,
        )

    if queued_jobs_total == 0 and running_jobs_total == 0:
        return RuntimeReadinessCheck(
            name="queue_health",
            status="ok",
            detail="no queued or running jobs detected",
            path=str(runtime_db_path),
            metadata=metadata,
        )

    summary_parts = [
        f"queued={queued_jobs_total}",
        f"running={running_jobs_total}",
    ]
    if oldest_queued_age_seconds is not None:
        summary_parts.append(f"oldest_queued_age_seconds={oldest_queued_age_seconds}")
    if stale_running_suspected_total > 0:
        summary_parts.append(f"stale_running_suspected_total={stale_running_suspected_total}")
    if stale_running_reclaimed_total > 0:
        summary_parts.append(f"stale_running_reclaimed_total={stale_running_reclaimed_total}")
    if last_stale_running_reclaimed_at:
        summary_parts.append(f"last_stale_running_reclaimed_at={last_stale_running_reclaimed_at}")
    if stale_running_requeued_total > 0:
        summary_parts.append(f"stale_running_requeued_total={stale_running_requeued_total}")
    if last_stale_running_requeued_at:
        summary_parts.append(f"last_stale_running_requeued_at={last_stale_running_requeued_at}")

    status = "warn" if queue_age_warn_triggered or stale_running_suspected_total > 0 else "ok"
    detail_prefix = "queue health needs attention" if status == "warn" else "queue health looks stable"
    return RuntimeReadinessCheck(
        name="queue_health",
        status=status,
        detail=f"{detail_prefix}: {', '.join(summary_parts)}",
        path=str(runtime_db_path),
        metadata=metadata,
    )


def collect_runtime_readiness() -> RuntimeReadinessResponse:
    checks: list[RuntimeReadinessCheck] = []
    loaded_config = None
    watchdog_check = _module_dependency_check(
        name="watchdog_dependency",
        module_name="watchdog",
        ok_detail="watcher dependency is installed",
        error_detail="watcher dependency 'watchdog' is missing; automatic pickup commands cannot start",
    )

    config_path = config_file_path()
    if not config_path.exists():
        checks.append(
            RuntimeReadinessCheck(
                name="config_file",
                status="error",
                detail="config file is missing",
                path=str(config_path),
            )
        )
    else:
        try:
            loaded_config = load_config()
            checks.append(
                RuntimeReadinessCheck(
                    name="config_file",
                    status="ok",
                    detail="config loaded successfully",
                    path=str(config_path),
                )
            )
        except Exception as exc:
            checks.append(
                RuntimeReadinessCheck(
                    name="config_file",
                    status="error",
                    detail=f"config failed to load: {exc}",
                    path=str(config_path),
                )
            )

    checks.append(watchdog_check)

    if loaded_config is not None:
        checks.append(
            _configured_external_root_check("obsidian_vault", loaded_config.paths.obsidian_vault)
        )
        checks.append(collect_structured_state_hygiene_check(loaded_config.paths.obsidian_vault))
        checks.append(collect_meeting_pack_storage_hygiene_check(loaded_config.paths.obsidian_vault))
        checks.append(
            _configured_external_root_check("zotero_base_dir", loaded_config.paths.zotero_base_dir)
        )
        checks.append(
            _machine_pickup_path_check(
                "watch_folder",
                loaded_config.paths.watch_folder,
                ok_detail="watched folder exists for automatic PDF pickup",
                warn_detail="watched folder is missing or not configured; use Import PDF or set up automatic pickup on this machine",
                dependency_check=watchdog_check,
                dependency_error_detail="watcher dependency 'watchdog' is missing; managed watch pickup cannot start on this machine",
            )
        )
        checks.append(
            _machine_pickup_path_check(
                "downloads_watch_dir",
                loaded_config.paths.downloads_watch_dir,
                ok_detail="downloads pickup folder exists on this machine",
                warn_detail="downloads pickup folder is missing; automatic pickup from Downloads may not run on this machine",
                dependency_check=watchdog_check,
                dependency_error_detail="watcher dependency 'watchdog' is missing; Downloads pickup cannot start on this machine",
            )
        )
        checks.append(_watch_folder_boundary_check(loaded_config))
        checks.append(_downloads_watch_boundary_check(loaded_config))

        pdf_storage_dir = loaded_config.paths.pdf_storage_dir.expanduser().resolve(strict=False)
        pdf_storage_writable = _path_writable_target(pdf_storage_dir)
        checks.append(
            RuntimeReadinessCheck(
                name="pdf_storage_dir",
                status="ok" if pdf_storage_writable else "error",
                detail=(
                    "imported and collected PDFs can be written here"
                    if pdf_storage_writable
                    else "PDF storage directory is not writable; imports and automatic pickup will fail"
                ),
                path=str(pdf_storage_dir),
            )
        )

    config_root_path = config_root()
    config_root_writable = _path_writable_target(config_root_path)
    checks.append(
        RuntimeReadinessCheck(
            name="config_root",
            status="ok" if config_root_writable else "warn",
            detail="config root is writable" if config_root_writable else "config root is not writable",
            path=str(config_root_path),
        )
    )

    db_path = get_db_path()
    db_writable = _path_writable_target(db_path.parent)
    checks.append(
        RuntimeReadinessCheck(
            name="runtime_db",
            status="ok" if db_writable else "error",
            detail="database path is writable" if db_writable else "database path is not writable",
            path=str(db_path),
        )
    )
    checks.append(collect_queue_health_check(db_path=db_path))
    checks.append(collect_fixture_paper_hygiene_check(db_path=db_path))

    storage_path = storage_root()
    storage_writable = _path_writable_target(storage_path)
    checks.append(
        RuntimeReadinessCheck(
            name="storage_root",
            status="ok" if storage_writable else "error",
            detail="storage root is writable" if storage_writable else "storage root is not writable",
            path=str(storage_path),
        )
    )

    logs_path = logs_root()
    logs_writable = _path_writable_target(logs_path)
    checks.append(
        RuntimeReadinessCheck(
            name="logs_root",
            status="ok" if logs_writable else "error",
            detail="logs root is writable" if logs_writable else "logs root is not writable",
            path=str(logs_path),
        )
    )

    cache_path = cache_root()
    cache_writable = _path_writable_target(cache_path)
    checks.append(
        RuntimeReadinessCheck(
            name="cache_root",
            status="ok" if cache_writable else "warn",
            detail="cache root is writable" if cache_writable else "cache root is not writable",
            path=str(cache_path),
        )
    )

    built_ui_path, dev_ui_path = _frontend_roots()
    if built_ui_path.exists():
        checks.append(
            RuntimeReadinessCheck(
                name="ui_bundle",
                status="ok",
                detail="built frontend bundle is available",
                path=str(built_ui_path),
            )
        )
    elif dev_ui_path.exists():
        checks.append(
            RuntimeReadinessCheck(
                name="ui_bundle",
                status="warn",
                detail="built frontend bundle is missing; runtime will fall back to the dev frontend entry",
                path=str(dev_ui_path),
            )
        )
    else:
        checks.append(
            RuntimeReadinessCheck(
                name="ui_bundle",
                status="error",
                detail="no frontend entry is available",
            )
        )

    checks.append(_backend_entrypoint_check())
    checks.append(_cli_entrypoint_check())
    checks.append(_privacy_preflight_config_check())
    latest_audit_check = _latest_intake_override_audit_check()
    checks.append(latest_audit_check)
    checks.append(_latest_intake_override_audit_quality_check(latest_audit_check))
    checks.append(_latest_intake_override_threshold_review_check())
    checks.append(_latest_processor_gate_threshold_review_check())
    checks.append(_latest_slot_classification_tuning_review_check())

    return RuntimeReadinessResponse(status=_overall_status_for_checks(checks), checks=checks)


def summarize_browser_runtime_readiness(
    readiness: RuntimeReadinessResponse,
) -> RuntimeReadinessResponse:
    checks_by_name = {check.name: check for check in readiness.checks}
    summary_checks: list[RuntimeReadinessCheck] = []

    config_summary = _browser_safe_summary_check(
        name="config_file",
        source_checks=[check for check in [checks_by_name.get("config_file")] if check is not None],
        ok_detail="runtime config loaded successfully",
        warn_detail="runtime config needs attention",
        error_detail="runtime config is missing or invalid",
    )
    if config_summary is not None:
        summary_checks.append(config_summary)

    external_roots_summary = _browser_safe_summary_check(
        name="external_roots",
        source_checks=[
            check
            for check in [
                checks_by_name.get("obsidian_vault"),
                checks_by_name.get("structured_state_hygiene"),
                checks_by_name.get("meeting_pack_storage_hygiene"),
                checks_by_name.get("zotero_base_dir"),
            ]
            if check is not None
        ],
        ok_detail="external workspace roots look configured",
        warn_detail="one or more external workspace roots need attention",
        error_detail="external workspace roots are not ready",
    )
    if external_roots_summary is not None:
        summary_checks.append(external_roots_summary)

    for name, ok_detail, warn_detail, error_detail in (
        (
            "watch_folder",
            "managed watch folder is available on this machine",
            "managed watch folder is unavailable on this machine",
            "managed watch folder is unavailable on this machine",
        ),
        (
            "downloads_watch_dir",
            "downloads pickup folder is available on this machine",
            "downloads pickup folder is unavailable on this machine",
            "downloads pickup folder is unavailable on this machine",
        ),
        (
            "pdf_storage_dir",
            "pdf storage looks writable",
            "pdf storage needs attention",
            "pdf storage is not writable",
        ),
        (
            "ui_bundle",
            "frontend bundle is available",
            "frontend bundle is missing and the runtime is using the dev entry",
            "frontend bundle is unavailable",
        ),
        (
            "backend_runtime",
            "backend runtime and CLI entrypoint look healthy",
            "backend runtime or CLI entrypoint needs attention",
            "backend runtime or CLI entrypoint needs attention",
        ),
    ):
        source_name = "backend_entrypoint" if name == "backend_runtime" else name
        extra_source_checks: list[RuntimeReadinessCheck] = []
        if name == "watch_folder":
            extra_source_checks = [
                check for check in [checks_by_name.get("watch_folder_boundary")] if check is not None
            ]
        elif name == "downloads_watch_dir":
            extra_source_checks = [
                check for check in [checks_by_name.get("downloads_watch_dir_boundary")] if check is not None
            ]
        elif name == "backend_runtime":
            extra_source_checks = [
                check for check in [checks_by_name.get("cli_entrypoint")] if check is not None
            ]
        summary = _browser_safe_summary_check(
            name=name,
            source_checks=[check for check in [checks_by_name.get(source_name)] if check is not None] + extra_source_checks,
            ok_detail=ok_detail,
            warn_detail=warn_detail,
            error_detail=error_detail,
        )
        if summary is not None:
            summary_checks.append(summary)

    runtime_storage_summary = _browser_safe_summary_check(
        name="runtime_storage",
        source_checks=[
            check
            for check in [
                checks_by_name.get("config_root"),
                checks_by_name.get("runtime_db"),
                checks_by_name.get("fixture_paper_hygiene"),
                checks_by_name.get("storage_root"),
                checks_by_name.get("logs_root"),
                checks_by_name.get("cache_root"),
            ]
            if check is not None
        ],
        ok_detail="internal runtime storage looks writable",
        warn_detail="one or more internal runtime paths need attention",
        error_detail="internal runtime storage is not writable",
    )
    if runtime_storage_summary is not None:
        summary_checks.append(runtime_storage_summary)

    queue_health_check = checks_by_name.get("queue_health")
    if queue_health_check is not None:
        browser_queue_metadata = dict(queue_health_check.metadata or {})
        browser_queue_metadata.pop("recent_stale_running_reclaims", None)
        summary_checks.append(
            RuntimeReadinessCheck(
                name="queue_health",
                status=queue_health_check.status,
                detail=queue_health_check.detail,
                metadata=browser_queue_metadata,
            )
        )

    privacy_preflight_check = checks_by_name.get("privacy_preflight_config")
    if privacy_preflight_check is not None:
        summary_checks.append(
            RuntimeReadinessCheck(
                name="privacy_preflight_config",
                status=privacy_preflight_check.status,
                detail=privacy_preflight_check.detail,
                metadata=dict(privacy_preflight_check.metadata or {}),
            )
        )

    latest_audit_check = checks_by_name.get("latest_intake_override_audit")
    if latest_audit_check is not None:
        summary_checks.append(
            RuntimeReadinessCheck(
                name="latest_intake_override_audit",
                status="ok",
                detail=latest_audit_check.detail,
                metadata=dict(latest_audit_check.metadata or {}),
            )
        )
    latest_audit_quality_check = checks_by_name.get("latest_intake_override_audit_quality")
    if latest_audit_quality_check is not None:
        summary_checks.append(
            RuntimeReadinessCheck(
                name="latest_intake_override_audit_quality",
                status=latest_audit_quality_check.status,
                detail=latest_audit_quality_check.detail,
                metadata=dict(latest_audit_quality_check.metadata or {}),
            )
        )
    latest_threshold_review_check = checks_by_name.get("latest_intake_override_threshold_review")
    if latest_threshold_review_check is not None:
        summary_checks.append(
            RuntimeReadinessCheck(
                name="latest_intake_override_threshold_review",
                status="ok",
                detail=latest_threshold_review_check.detail,
                metadata=dict(latest_threshold_review_check.metadata or {}),
            )
        )
    latest_processor_gate_threshold_review_check = checks_by_name.get("latest_processor_gate_threshold_review")
    if latest_processor_gate_threshold_review_check is not None:
        browser_threshold_metadata = _browser_safe_processor_gate_threshold_review_metadata(
            latest_processor_gate_threshold_review_check.metadata
        )
        summary_checks.append(
            RuntimeReadinessCheck(
                name="latest_processor_gate_threshold_review",
                status="ok",
                detail=latest_processor_gate_threshold_review_check.detail,
                metadata=browser_threshold_metadata,
            )
        )
    latest_slot_classification_tuning_review_check = checks_by_name.get(
        "latest_slot_classification_tuning_review"
    )
    if latest_slot_classification_tuning_review_check is not None:
        summary_checks.append(
            RuntimeReadinessCheck(
                name="latest_slot_classification_tuning_review",
                status="ok",
                detail=latest_slot_classification_tuning_review_check.detail,
                metadata=dict(latest_slot_classification_tuning_review_check.metadata or {}),
            )
        )

    return RuntimeReadinessResponse(
        status=_overall_status_for_checks(summary_checks),
        checks=summary_checks,
    )
