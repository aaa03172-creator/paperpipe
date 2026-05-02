import typer
import os
import shutil
import socket
import sqlite3
import sys
import time
import webbrowser
import json
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import requests
import yaml
from rich.console import Console
from src.config import load_config
from src.db_utils import (
    init_db as init_jobs_db,
    init_run_stats_table,
    DB_PATH as DB_UTILS_PATH,
    record_run_status,
)
from src.logger import setup_logging
from src.services.event_log import ensure_execution_run, update_execution_run
from src.services.identity import new_run_id
from src.services.runtime_paths import logs_root, meeting_packs_root as default_meeting_packs_root
from src.services.runtime_paths import config_file_path, paperpipe_home
from src.services.runtime_readiness import (
    LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
    LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
    collect_fixture_paper_hygiene_check,
    collect_meeting_pack_storage_hygiene_check,
    collect_runtime_readiness,
    collect_structured_state_hygiene_check,
)
from src.services.fixture_visibility import quarantine_hidden_fixture_structured_states
from src.services.intake_override_audit import (
    build_intake_override_audit_calibration_snapshot,
    build_intake_override_audit_viewer_command,
    build_intake_override_threshold_review_viewer_command,
    default_intake_override_audits_root,
    default_intake_override_threshold_review_root,
    latest_intake_override_audit_run,
    latest_intake_override_threshold_review_summary,
    latest_intake_override_threshold_review_run,
)
from src.services.processor_gate_replay_drift import (
    build_processor_gate_threshold_review_viewer_command,
    default_processor_gate_threshold_review_root,
    latest_processor_gate_threshold_review_run,
    load_processor_gate_threshold_review_summary,
    resolve_processor_gate_threshold_review_drift_artifacts,
)
from src.services.slot_classification_tuning_review import (
    default_slot_classification_tuning_review_root,
    latest_slot_classification_tuning_review_run,
    load_slot_classification_tuning_review_summary,
)
from src.meeting_packs.hygiene import (
    apply_archive as apply_meeting_pack_archive,
    default_archive_root as default_meeting_pack_archive_root,
    select_archive_candidates as select_meeting_pack_archive_candidates,
)
from scripts.archive_fixture_no_feedback_papers import (
    apply_archive as apply_fixture_paper_archive,
    backup_db as backup_fixture_paper_archive_db,
    default_backup_path as default_fixture_paper_archive_backup_path,
    select_archive_candidates as select_fixture_paper_archive_candidates,
)
from src.services.cli_workflows import (
    run_deepread_workflow,
    update_reading_status_workflow,
)
from dotenv import load_dotenv

load_dotenv()

# [Clean API Keys]
for _env_key_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
    if os.getenv(_env_key_name):
        clean_key = os.getenv(_env_key_name).strip().replace("\n", "").replace("\r", "")
        os.environ[_env_key_name] = clean_key

# Setup App & Logger
app = typer.Typer(no_args_is_help=True)
research_dna_app = typer.Typer(no_args_is_help=True)
artifact_history_app = typer.Typer(no_args_is_help=True)
console = Console()

# Initialize Centralized Logger
try:
    config_initial = load_config()
    log_level = config_initial.system.log_level
except Exception:
    log_level = "INFO"

logger = setup_logging(log_level=log_level)


class _LazySubprocessProxy:
    """Delay importing subprocess until a command actually needs it."""

    def __init__(self) -> None:
        self._module = None

    def _load(self):
        if self._module is None:
            import subprocess as subprocess_module

            self._module = subprocess_module
        return self._module

    def __getattr__(self, name: str):
        return getattr(self._load(), name)


subprocess = _LazySubprocessProxy()


def _emit_json(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def _parse_feedback_json_object(raw_feedback_json):
    if isinstance(raw_feedback_json, dict):
        return raw_feedback_json
    if raw_feedback_json in (None, ""):
        return {}
    try:
        parsed = json.loads(str(raw_feedback_json))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _selection_summary_text(result) -> str | None:
    payload = _parse_feedback_json_object(result.get("feedback_json"))
    selection = payload.get("selection")
    if not isinstance(selection, dict):
        selection = {}

    rank = _coerce_optional_int(selection.get("selected_rank"))
    candidate_count = _coerce_optional_int(selection.get("candidate_count"))
    score = _coerce_optional_float(result.get("manual_rank_score"))
    if score is None:
        score = _coerce_optional_float(selection.get("selected_manual_rank_score"))

    skipped_processed = selection.get("skipped_processed_candidates")
    skipped_count = len(skipped_processed) if isinstance(skipped_processed, list) else 0

    parts: list[str] = []
    if rank is not None and candidate_count is not None and candidate_count > 0:
        parts.append(f"r{rank}/{candidate_count}")
    elif rank is not None:
        parts.append(f"r{rank}")
    if score is not None:
        parts.append(f"s={score:.2f}")
    if skipped_count > 0:
        parts.append(f"skip={skipped_count}")
    return ", ".join(parts) or None


def _format_percentage_text(value) -> str | None:
    numeric = _coerce_optional_float(value)
    if numeric is None:
        return None
    return f"{numeric:.1%}"


def _latest_audit_scope_summary(metadata: dict[str, object]) -> str | None:
    source = str(metadata.get("source") or "").strip()
    row_count = _coerce_optional_int(metadata.get("row_count"))
    audited_count = _coerce_optional_int(metadata.get("audited_document_count"))

    parts: list[str] = []
    if source:
        parts.append(f"source={source}")
    if row_count is not None:
        parts.append(f"rows={row_count}")
    if audited_count is not None:
        parts.append(f"audited={audited_count}")
    return ", ".join(parts) or None


def _latest_audit_quality_summary(metadata: dict[str, object]) -> str | None:
    triage_rate = _format_percentage_text(metadata.get("triage_override_rate"))
    slot_rate = _format_percentage_text(metadata.get("slot_disagreement_rate"))
    slot_adjudication_rate = _format_percentage_text(metadata.get("llm_slot_adjudication_rate"))
    tagging_adjudication_rate = _format_percentage_text(metadata.get("llm_tagging_adjudication_rate"))
    fallback_rate = _format_percentage_text(metadata.get("selection_fallback_rate"))

    parts: list[str] = []
    if triage_rate is not None:
        parts.append(f"triage={triage_rate}")
    if slot_rate is not None:
        parts.append(f"slot={slot_rate}")
    if slot_adjudication_rate is not None:
        parts.append(f"slot_adj={slot_adjudication_rate}")
    if tagging_adjudication_rate is not None:
        parts.append(f"tag_adj={tagging_adjudication_rate}")
    if fallback_rate is not None:
        parts.append(f"fallback={fallback_rate}")
    return ", ".join(parts) or None


def _latest_audit_quality_signals_text(metadata: dict[str, object]) -> str | None:
    raw = metadata.get("quality_signals")
    if not isinstance(raw, list):
        return None
    signals = [str(item).strip() for item in raw if str(item).strip()]
    return ", ".join(signals) or None


def _processor_gate_worksheet_compact_text(worksheet_summary: object) -> str | None:
    if not isinstance(worksheet_summary, dict):
        return None
    pending_count = _coerce_optional_int(worksheet_summary.get("pending_count"))
    primary_review_target = str(worksheet_summary.get("primary_review_target") or "").strip()
    excluded_count = _coerce_optional_int(worksheet_summary.get("excluded_count"))

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
    policy_support = _coerce_optional_int(basis.get("mid_confidence_policy_support_count"))
    high_threshold_support = _coerce_optional_int(basis.get("high_threshold_support_count"))

    parts: list[str] = []
    if preliminary_call:
        parts.append(f"call={preliminary_call}")
    if policy_support is not None:
        parts.append(f"policy={policy_support}")
    if high_threshold_support is not None:
        parts.append(f"high={high_threshold_support}")
    return ", ".join(parts) or None


def _processor_gate_prefill_compact_text(prefill_summary: object) -> str | None:
    if not isinstance(prefill_summary, dict):
        return None

    policy_only_review_count = _coerce_optional_int(prefill_summary.get("policy_only_review_count"))
    boundary_review_count = _coerce_optional_int(prefill_summary.get("boundary_review_count"))
    manual_triage_count = _coerce_optional_int(prefill_summary.get("manual_triage_count"))
    priority_review_now_count = _coerce_optional_int(prefill_summary.get("priority_review_now_count"))
    priority_review_first_count = _coerce_optional_int(prefill_summary.get("priority_review_first_count"))
    priority_review_later_count = _coerce_optional_int(prefill_summary.get("priority_review_later_count"))

    parts: list[str] = []
    if policy_only_review_count is not None:
        parts.append(f"policy_only={policy_only_review_count}")
    if boundary_review_count is not None:
        parts.append(f"boundary={boundary_review_count}")
    if manual_triage_count is not None:
        parts.append(f"triage={manual_triage_count}")
    if priority_review_now_count is not None:
        parts.append(f"now={priority_review_now_count}")
    if priority_review_first_count is not None:
        parts.append(f"first={priority_review_first_count}")
    if priority_review_later_count is not None:
        parts.append(f"later={priority_review_later_count}")
    return ", ".join(parts) or None


def _processor_gate_manual_review_outcome_compact_text(outcome: object) -> str | None:
    if not isinstance(outcome, dict):
        return None

    status = str(outcome.get("status") or "").strip()
    completed_row_count = _coerce_optional_int(outcome.get("completed_row_count"))
    total_row_count = _coerce_optional_int(outcome.get("total_row_count"))
    supports_high_threshold_change_count = _coerce_optional_int(
        outcome.get("supports_high_threshold_change_count")
    )
    default_divergence_count = _coerce_optional_int(outcome.get("default_divergence_count"))

    parts: list[str] = []
    if status:
        parts.append(f"status={status}")
    if completed_row_count is not None and total_row_count is not None:
        parts.append(f"completed={completed_row_count}/{total_row_count}")
    elif completed_row_count is not None:
        parts.append(f"completed={completed_row_count}")
    if supports_high_threshold_change_count is not None:
        parts.append(f"high={supports_high_threshold_change_count}")
    if default_divergence_count is not None:
        parts.append(f"diverged={default_divergence_count}")
    return ", ".join(parts) or None


def _processor_gate_threshold_change_decision_compact_text(decision: object) -> str | None:
    if not isinstance(decision, dict):
        return None

    final_status = str(decision.get("final_status") or "").strip()
    recommended_action = str(decision.get("recommended_action") or "").strip()
    counts = decision.get("manual_review_counts") if isinstance(decision.get("manual_review_counts"), dict) else {}
    supports_high = _coerce_optional_int(counts.get("supports_high_threshold_change"))
    completed = _coerce_optional_int(counts.get("completed"))
    total = _coerce_optional_int(counts.get("total"))
    preflight = (
        decision.get("threshold_change_preflight")
        if isinstance(decision.get("threshold_change_preflight"), dict)
        else {}
    )
    preflight_status = str(preflight.get("status") or "").strip()
    preflight_blocker = str(preflight.get("blocker") or "").strip()

    parts: list[str] = []
    if final_status:
        parts.append(f"status={final_status}")
    if recommended_action:
        parts.append(f"action={recommended_action}")
    if completed is not None and total is not None:
        parts.append(f"reviewed={completed}/{total}")
    if supports_high is not None:
        parts.append(f"high={supports_high}")
    if preflight_status and preflight_status != "not_applicable":
        parts.append(f"preflight={preflight_status}")
    if preflight_blocker:
        parts.append(f"blocker={preflight_blocker}")
    return ", ".join(parts) or None


def _processor_gate_mid_confidence_policy_decision_compact_text(decision: object) -> str | None:
    if not isinstance(decision, dict):
        return None

    final_status = str(decision.get("final_status") or "").strip()
    recommended_action = str(decision.get("recommended_action") or "").strip()
    counts = decision.get("manual_review_counts") if isinstance(decision.get("manual_review_counts"), dict) else {}
    supports_mid = _coerce_optional_int(counts.get("supports_mid_confidence_policy_review"))
    supports_high = _coerce_optional_int(counts.get("supports_high_threshold_change"))

    parts: list[str] = []
    if final_status:
        parts.append(f"status={final_status}")
    if recommended_action:
        parts.append(f"action={recommended_action}")
    if supports_mid is not None:
        parts.append(f"mid={supports_mid}")
    if supports_high is not None:
        parts.append(f"high={supports_high}")
    return ", ".join(parts) or None


def _processor_gate_policy_debt_reconciliation_compact_text(reconciliation: object) -> str | None:
    if not isinstance(reconciliation, dict):
        return None

    final_status = str(reconciliation.get("final_status") or "").strip()
    recommended_action = str(reconciliation.get("recommended_action") or "").strip()
    counts = (
        reconciliation.get("manual_review_counts")
        if isinstance(reconciliation.get("manual_review_counts"), dict)
        else {}
    )
    completed = _coerce_optional_int(counts.get("completed"))
    total = _coerce_optional_int(counts.get("total"))
    historical_mutation_ready = bool(reconciliation.get("historical_mutation_ready"))

    parts: list[str] = []
    if final_status:
        parts.append(f"status={final_status}")
    if recommended_action:
        parts.append(f"action={recommended_action}")
    if completed is not None and total is not None:
        parts.append(f"debt={completed}/{total}")
    elif completed is not None:
        parts.append(f"debt={completed}")
    parts.append(f"mutate={'yes' if historical_mutation_ready else 'no'}")
    return ", ".join(parts) or None


def _processor_gate_manual_override_policy_decision_compact_text(decision: object) -> str | None:
    if not isinstance(decision, dict):
        return None

    final_status = str(decision.get("final_status") or "").strip()
    recommended_action = str(decision.get("recommended_action") or "").strip()
    manual_override_count = _coerce_optional_int(decision.get("manual_override_count"))
    historical_mutation_ready = bool(decision.get("historical_mutation_ready"))

    parts: list[str] = []
    if final_status:
        parts.append(f"status={final_status}")
    if recommended_action:
        parts.append(f"action={recommended_action}")
    if manual_override_count is not None:
        parts.append(f"manual={manual_override_count}")
    parts.append(f"mutate={'yes' if historical_mutation_ready else 'no'}")
    return ", ".join(parts) or None


def _processor_gate_indexed_pending_policy_decision_compact_text(decision: object) -> str | None:
    if not isinstance(decision, dict):
        return None

    final_status = str(decision.get("final_status") or "").strip()
    recommended_action = str(decision.get("recommended_action") or "").strip()
    indexed_pending_count = _coerce_optional_int(decision.get("indexed_pending_count"))
    historical_mutation_ready = bool(decision.get("historical_mutation_ready"))

    parts: list[str] = []
    if final_status:
        parts.append(f"status={final_status}")
    if recommended_action:
        parts.append(f"action={recommended_action}")
    if indexed_pending_count is not None:
        parts.append(f"indexed={indexed_pending_count}")
    parts.append(f"mutate={'yes' if historical_mutation_ready else 'no'}")
    return ", ".join(parts) or None


def _processor_gate_fixture_or_test_policy_decision_compact_text(decision: object) -> str | None:
    if not isinstance(decision, dict):
        return None

    final_status = str(decision.get("final_status") or "").strip()
    recommended_action = str(decision.get("recommended_action") or "").strip()
    fixture_or_test_count = _coerce_optional_int(decision.get("fixture_or_test_count"))
    archive_action_ready = bool(decision.get("archive_action_ready"))
    historical_mutation_ready = bool(decision.get("historical_mutation_ready"))

    parts: list[str] = []
    if final_status:
        parts.append(f"status={final_status}")
    if recommended_action:
        parts.append(f"action={recommended_action}")
    if fixture_or_test_count is not None:
        parts.append(f"fixture={fixture_or_test_count}")
    parts.append(f"archive={'yes' if archive_action_ready else 'no'}")
    parts.append(f"mutate={'yes' if historical_mutation_ready else 'no'}")
    return ", ".join(parts) or None


def _audit_calibration_status_text(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "warn":
        return "warn"
    if normalized == "small_sample":
        return "small"
    return "ok"


def _audit_calibration_summary_text(snapshot: dict[str, object]) -> str | None:
    total_runs = _coerce_optional_int(snapshot.get("total_runs"))
    eligible_runs = _coerce_optional_int(snapshot.get("eligible_runs"))
    warn_runs = _coerce_optional_int(snapshot.get("warn_runs"))
    target_runs = _coerce_optional_int(snapshot.get("calibration_target_runs"))
    min_audited_docs = _coerce_optional_int(snapshot.get("min_audited_docs"))
    warn_threshold = _coerce_optional_float(snapshot.get("warn_threshold"))

    parts: list[str] = []
    if total_runs is not None:
        parts.append(f"runs={total_runs}")
    if eligible_runs is not None and target_runs is not None:
        parts.append(f"sufficient={eligible_runs}/{target_runs}")
    elif eligible_runs is not None:
        parts.append(f"sufficient={eligible_runs}")
    if warn_runs is not None:
        parts.append(f"warn={warn_runs}")
    if warn_threshold is not None:
        parts.append(f"threshold={warn_threshold:.1%}")
    if min_audited_docs is not None:
        parts.append(f"sample>={min_audited_docs}")
    return ", ".join(parts) or None


def _resolve_audit_json_path(path_value: Path | str, filename: str) -> Path:
    candidate = Path(path_value).expanduser().resolve()
    if candidate.is_dir():
        candidate = candidate / filename
    return candidate


def _load_json_dict(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _coerce_rate_text(value) -> str:
    numeric = _coerce_optional_float(value)
    if numeric is None:
        return "-"
    return f"{numeric:.1%}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_run_status_value(value) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().upper()


def _build_legacy_run_metrics(*, results: list[dict], config, report_path: Path | None) -> dict:
    approved_count = 0
    pending_review_count = 0
    quarantined_count = 0

    for row in results:
        status_value = _legacy_run_status_value(row.get("processing_status"))
        if status_value == "APPROVED":
            approved_count += 1
        elif status_value == "PENDING_REVIEW":
            pending_review_count += 1
        elif status_value == "QUARANTINED":
            quarantined_count += 1

    slots = getattr(getattr(config, "search", None), "slots", {}) or {}
    return {
        "processed_count": len(results),
        "approved_count": approved_count,
        "pending_review_count": pending_review_count,
        "quarantined_count": quarantined_count,
        "slot_count": len(slots),
        "report_generated": bool(report_path),
        "report_path": str(report_path) if report_path else None,
    }


def _start_legacy_cli_run_tracking(*, config) -> tuple[str | None, str | None]:
    run_id = new_run_id()
    started_at = _utc_now_iso()
    slots = getattr(getattr(config, "search", None), "slots", {}) or {}
    try:
        ensure_execution_run(
            run_id=run_id,
            trigger_source="cli_run",
            pipeline_profile="legacy_daily_slots",
            status="running",
            params={
                "command": "paperpipe run",
                "ignore_db": False,
                "slot_names": sorted(str(name) for name in slots.keys()),
            },
        )
        update_execution_run(
            run_id=run_id,
            status="running",
            started_at=started_at,
        )
        return run_id, started_at
    except Exception as exc:
        logger.warning("Failed to start legacy CLI run tracking: %s", exc)
        return None, None


def _finish_legacy_cli_run_tracking(
    run_id: str | None,
    *,
    status: str,
    metrics: dict | None = None,
) -> None:
    if not run_id:
        return
    try:
        update_execution_run(
            run_id=run_id,
            status=status,
            finished_at=_utc_now_iso(),
            metrics=metrics,
        )
    except Exception as exc:
        logger.warning("Failed to finish legacy CLI run tracking for %s: %s", run_id, exc)


def _resolved_optional_path(value) -> Path | None:
    if value in (None, ""):
        return None
    try:
        return Path(value).expanduser().resolve(strict=False)
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


def _watch_output_conflicts(config) -> list[tuple[str, Path]]:
    watch_folder = _resolved_optional_path(getattr(getattr(config, "paths", None), "watch_folder", None))
    if watch_folder is None:
        return []

    conflicts: list[tuple[str, Path]] = []
    for label, raw_path in (
        ("upload_dir", getattr(getattr(config, "paths", None), "upload_dir", None)),
        ("pdf_storage_dir", getattr(getattr(config, "paths", None), "pdf_storage_dir", None)),
    ):
        resolved = _resolved_optional_path(raw_path)
        if resolved is not None and _paths_overlap(resolved, watch_folder):
            conflicts.append((label, resolved))
    return conflicts


def _downloads_watch_output_conflicts(config) -> list[tuple[str, Path]]:
    downloads_watch_dir = _resolved_optional_path(getattr(getattr(config, "paths", None), "downloads_watch_dir", None))
    if downloads_watch_dir is None:
        return []

    conflicts: list[tuple[str, Path]] = []
    resolved_storage = _resolved_optional_path(getattr(getattr(config, "paths", None), "pdf_storage_dir", None))
    if resolved_storage is not None and _paths_overlap(resolved_storage, downloads_watch_dir):
        conflicts.append(("pdf_storage_dir", resolved_storage))
    return conflicts


def _emit_paper_synthesis_cli_result(
    *,
    result,
    markdown_only: bool,
    manifest_only: bool,
    bundle_payload: dict,
) -> None:
    if markdown_only and manifest_only:
        raise typer.BadParameter("Choose only one of --manifest or --markdown")
    if markdown_only:
        typer.echo(result.markdown)
        return
    if manifest_only:
        _emit_json(result.synthesis.model_dump(mode="json"))
        return
    _emit_json(bundle_payload)


def _resolve_research_dna_run_id_for_cli(
    dna_id: str,
    *,
    run_id: str | None,
    latest: bool,
) -> str:
    from src.profiles.research_dna_service import (
        ResearchDNAStateError,
        resolve_research_dna_run_id,
    )

    try:
        return resolve_research_dna_run_id(
            dna_id,
            run_id=run_id,
            latest=latest,
        )
    except ResearchDNAStateError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _optional_dependency_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _ensure_watchdog_available(command_name: str) -> None:
    if _optional_dependency_installed("watchdog"):
        return
    console.print(
        "[bold red]❌ Watcher dependency missing.[/bold red] "
        f"Install project dependencies (for example `uv sync`) before using `{command_name}`."
    )
    raise typer.Exit(code=1)


def bootstrap_database() -> Path:
    """Initialize canonical runtime schema (papers/review_queue/jobs/run_stats)."""
    from scripts.init_db import init_db as init_core_db

    init_core_db()
    init_jobs_db()
    init_run_stats_table()
    return DB_UTILS_PATH


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _wait_for_health(base_url: str, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return False


def _terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def _build_backend_launch_command(host: str, port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "serve-backend",
            "--host",
            host,
            "--port",
            str(port),
        ]
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]


def _build_worker_launch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "serve-worker",
        ]
    return [
        sys.executable,
        "-m",
        "src.jobs.worker",
    ]


def _argv_with_frozen_app_default_command(argv: list[str]) -> list[str]:
    if not argv:
        return ["start"]
    if not getattr(sys, "frozen", False):
        return list(argv)
    if sys.platform != "darwin":
        return list(argv)
    if Path(argv[0]).stem != "Lattice":
        return list(argv)
    if len(argv) == 1 or argv[1].startswith("-"):
        return [argv[0], "start", *argv[1:]]
    return list(argv)


def _ensure_selected_artifact_history_target_exists(*, artifact_type: str, artifact_id: str) -> None:
    if artifact_type == "meeting_pack":
        from src.meeting_packs.service import get_meeting_pack

        get_meeting_pack(artifact_id)
        return
    if artifact_type == "protocol_card":
        from src.protocol_cards.service import get_protocol_card_bundle

        get_protocol_card_bundle(artifact_id)
        return
    raise typer.BadParameter(f"Unsupported artifact history target: {artifact_type}")


def _append_selected_artifact_review_feedback(
    *,
    artifact_type: str,
    artifact_id: str,
    paper_id: str | None,
    run_id: str | None,
    dna_id: str | None,
    decision: str,
    reason_code: str,
    actor_id: str,
    note: str,
):
    from src.schemas.artifact_review_feedback import ArtifactReviewFeedbackCase
    from src.services.artifact_review_feedback import append_artifact_review_feedback

    _ensure_selected_artifact_history_target_exists(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
    )
    return append_artifact_review_feedback(
        ArtifactReviewFeedbackCase(
            artifact_type=artifact_type,  # type: ignore[arg-type]
            artifact_id=artifact_id,
            paper_id=paper_id,
            run_id=run_id,
            dna_id=dna_id,
            decision=decision,  # type: ignore[arg-type]
            reason_code=reason_code,
            actor_id=actor_id,
            note=note,
        )
    )


def _append_selected_artifact_generation_outcome(
    *,
    artifact_type: str,
    artifact_id: str,
    paper_id: str | None,
    run_id: str | None,
    dna_id: str | None,
    review_feedback_id: str | None,
    decision: str,
    downstream_use: str,
    actor_id: str,
    note: str,
):
    from src.schemas.artifact_generation_outcome import ArtifactGenerationOutcome
    from src.services.artifact_generation_outcomes import append_artifact_generation_outcome

    _ensure_selected_artifact_history_target_exists(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
    )
    return append_artifact_generation_outcome(
        ArtifactGenerationOutcome(
            artifact_type=artifact_type,  # type: ignore[arg-type]
            artifact_id=artifact_id,
            paper_id=paper_id,
            run_id=run_id,
            dna_id=dna_id,
            review_feedback_id=review_feedback_id,
            decision=decision,  # type: ignore[arg-type]
            downstream_use=downstream_use,  # type: ignore[arg-type]
            actor_id=actor_id,
            note=note,
        )
    )


# 0. Main Entry
@app.callback()
def main():
    """PaperPipe Automation Tool"""
    pass


app.add_typer(research_dna_app, name="research-dna")
app.add_typer(artifact_history_app, name="artifact-history")


def _doctor_status_icon(status: str) -> str:
    return "✅" if status == "ok" else "⚠️" if status == "warn" else "❌"


def _print_first_paper_doctor_guidance(readiness_checks: dict[str, object]) -> None:
    pickup_checks = [
        readiness_checks.get("watch_folder_boundary"),
        readiness_checks.get("downloads_watch_dir_boundary"),
    ]
    pickup_blocked = any(str(getattr(check, "status", "")) in {"warn", "error"} for check in pickup_checks if check is not None)

    console.print("\n[bold]First paper path[/bold]")
    console.print("   - Web import: http://127.0.0.1:8000/ui/papers#import-pdf")
    console.print("   - CLI import: paperpipe import-pdf path/to/paper.pdf")
    if pickup_blocked:
        console.print("   - Automatic pickup: use Import PDF first; fix pickup setup later from /ready.")
    else:
        console.print("   - Automatic pickup: no blocking pickup boundary warning detected.")
    console.print("   - After import: open review, or run paperpipe deepread <paper_id>.")


def _starter_config_payload() -> dict:
    example_path = Path(__file__).resolve().parents[1] / "config.example.yaml"
    with example_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    paths = payload.setdefault("paths", {})
    paths.update(
        {
            "zotero_base_dir": "storage/zotero",
            "obsidian_vault": "storage/obsidian_vault",
            "upload_dir": "storage/uploads",
            "export_dir": "export",
            "watch_folder": "storage/watch",
            "library_dir": "Library",
            "downloads_watch_dir": "~/Downloads",
            "pdf_storage_dir": "storage/pdfs",
        }
    )
    payload.setdefault("system", {})["log_level"] = "INFO"
    return payload


def _ensure_starter_config() -> list[str]:
    target = config_file_path("config.yaml")
    if target.exists():
        return [f"Config already exists: {target}"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(_starter_config_payload(), sort_keys=False), encoding="utf-8")
    return [f"Created starter config: {target}"]


def _safe_to_create_doctor_path(path: Path) -> bool:
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        return True
    resolved = raw.resolve(strict=False)
    allowed_roots = {Path.cwd().resolve(), paperpipe_home().resolve()}
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _ensure_first_run_directories(config) -> list[str]:
    path_specs = [
        ("Zotero Dir", getattr(config.paths, "zotero_base_dir", None)),
        ("Obsidian Vault", getattr(config.paths, "obsidian_vault", None)),
        ("Upload Dir", getattr(config.paths, "upload_dir", None)),
        ("Export Dir", getattr(config.paths, "export_dir", None)),
        ("Watch Folder", getattr(config.paths, "watch_folder", None)),
        ("Library Dir", getattr(config.paths, "library_dir", None)),
        ("PDF Storage", getattr(config.paths, "pdf_storage_dir", None)),
    ]
    messages: list[str] = []
    for label, raw_path in path_specs:
        if raw_path is None:
            continue
        path = Path(raw_path).expanduser()
        if path.exists():
            continue
        if not _safe_to_create_doctor_path(path):
            messages.append(f"Skipped {label}: outside project-managed paths ({path})")
            continue
        path.mkdir(parents=True, exist_ok=True)
        messages.append(f"Created {label}: {path}")
    return messages


# 1. Environment Doctor
@app.command()
def doctor(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Create a starter config and safe local first-run directories before reporting.",
    )
):
    """Check environment, config, and dependencies."""
    console.print("[bold blue]🩺 Checking Environment...[/bold blue]")
    llm_mode = "local"
    if fix:
        console.print("[bold]Applying safe first-run fixes...[/bold]")
        for message in _ensure_starter_config():
            console.print(f"   - {message}")
    
    try:
        config = load_config()
        if fix:
            directory_messages = _ensure_first_run_directories(config)
            if directory_messages:
                for message in directory_messages:
                    console.print(f"   - {message}")
            else:
                console.print("   - First-run directories already present or externally managed.")
        console.print("✅ Config loaded successfully.")
        zotero_status = "✅ Found" if config.paths.zotero_base_dir.exists() else "⚠️ Missing"
        vault_status = "✅ Found" if config.paths.obsidian_vault.exists() else "⚠️ Missing"
        console.print(f"   - Zotero Dir: {zotero_status} ({config.paths.zotero_base_dir})")
        console.print(f"   - Obsidian Vault: {vault_status} ({config.paths.obsidian_vault})")
        console.print(f"   - Log Level: {config.system.log_level}")
        
        # [NEW] Check Watch Folder
        if config.paths.watch_folder:
            if config.paths.watch_folder.exists():
                console.print(f"   - Watch Folder: ✅ Found ({config.paths.watch_folder})")
            else:
                console.print(f"   - Watch Folder: ⚠️ Configured but missing ({config.paths.watch_folder})")
        else:
            console.print("   - Watch Folder: ⚪ Not configured")

        if _optional_dependency_installed("watchdog"):
            console.print("   - Watchdog: ✅ Installed (watch commands available)")
        else:
            console.print("   - Watchdog: ❌ Missing (run `uv sync` to enable watch commands)")

        fixture_hygiene = collect_structured_state_hygiene_check(config.paths.obsidian_vault)
        fixture_icon = "✅" if fixture_hygiene.status == "ok" else "⚠️" if fixture_hygiene.status == "warn" else "❌"
        console.print(f"   - Structured State Hygiene: {fixture_icon} {fixture_hygiene.detail}")
        if fixture_hygiene.path:
            console.print(f"     Path: {fixture_hygiene.path}")

        meeting_pack_hygiene = collect_meeting_pack_storage_hygiene_check(config.paths.obsidian_vault)
        meeting_pack_icon = (
            "✅" if meeting_pack_hygiene.status == "ok" else "⚠️" if meeting_pack_hygiene.status == "warn" else "❌"
        )
        console.print(f"   - Meeting Pack Storage Hygiene: {meeting_pack_icon} {meeting_pack_hygiene.detail}")
        if meeting_pack_hygiene.path:
            console.print(f"     Path: {meeting_pack_hygiene.path}")

        fixture_paper_hygiene = collect_fixture_paper_hygiene_check()
        fixture_paper_icon = (
            "✅" if fixture_paper_hygiene.status == "ok" else "⚠️" if fixture_paper_hygiene.status == "warn" else "❌"
        )
        console.print(f"   - Fixture Paper Hygiene: {fixture_paper_icon} {fixture_paper_hygiene.detail}")
        if fixture_paper_hygiene.path:
            console.print(f"     Path: {fixture_paper_hygiene.path}")

        # [NEW] Check Unpaywall
        if config.system.unpaywall_email and "example.com" not in config.system.unpaywall_email:
             console.print(f"   - Unpaywall: ✅ Email configured ({config.system.unpaywall_email})")
        else:
             console.print("   - Unpaywall: ⚠️ Email missing or default")

        # [NEW] Check Bibliometrics
        if config.ranking.bibliometrics.enabled:
             console.print("   - Bibliometrics: ✅ Enabled (OpenAlex)")
        else:
             console.print("   - Bibliometrics: ⚪ Disabled")

        # [NEW] Check LLM & Ollama
        try:
            llm_config = config.llm
            
            # Helper to check mode safely
            llm_mode = getattr(llm_config, "mode", "local")
            
            if llm_mode in ["local", "hybrid"]:
                 console.print(f"   - LLM Mode: [bold cyan]{llm_mode}[/bold cyan] (Ollama Active)")
                 if hasattr(llm_config, 'local') and llm_config.local:
                     url = llm_config.local.base_url
                     try:
                         import ollama
                         # Check basic connectivity
                         client = ollama.Client(host=url)
                         try:
                             client.list()
                             console.print(f"   - Ollama: ✅ Connected ({url})")
                         except Exception as conn_err:
                             console.print(f"   - Ollama: ❌ Connection Failed ({url}) - {conn_err}", style="red")
                     except ImportError:
                         console.print("   - Ollama: ⚠️ 'ollama' package not installed.", style="yellow")
            else:
                 console.print(f"   - LLM Mode: {llm_mode} (Cloud Only)")
                 
        except Exception as e:
            console.print(f"   - LLM Check: ⚠️ Error checking LLM config: {e}")

    except Exception as e:
        console.print(f"❌ Config Error: {e}", style="bold red")
        return

    try:
        db_path = bootstrap_database()
        console.print(f"✅ Database initialized ({db_path}).")
    except Exception as e:
        console.print(f"❌ Database Error: {e}", style="bold red")
    
    # Check cloud API key (mode-aware)
    cloud_provider = str(getattr(getattr(config.llm, "cloud", None), "provider", "openai") or "openai").strip().lower()
    cloud_provider_label = "Anthropic" if cloud_provider == "anthropic" else "OpenAI"
    cloud_env_var = "ANTHROPIC_API_KEY" if cloud_provider == "anthropic" else "OPENAI_API_KEY"
    cloud_api_key = os.getenv(cloud_env_var)
    if llm_mode == "cloud":
        if cloud_api_key:
            console.print(f"✅ {cloud_provider_label} API Key detected.")
        else:
            console.print(f"❌ {cloud_provider_label} API Key missing! (required for cloud mode)", style="bold red")
    elif llm_mode == "hybrid":
        if cloud_api_key:
            console.print(f"✅ {cloud_provider_label} API Key detected. (hybrid cloud path available)")
        else:
            console.print(f"⚠️ {cloud_provider_label} API Key missing. (hybrid cloud path disabled)", style="yellow")
    else:
        if cloud_api_key:
            console.print(f"✅ {cloud_provider_label} API Key detected. (optional in local mode)")
        else:
            console.print(f"ℹ️ {cloud_provider_label} API Key not required in local mode.")

    if (logs_root() / "paperpipe.log").exists():
        console.print("✅ Log file accessible.")
    else:
        console.print("⚠️ Log file not found yet (will be created on first log).")

    readiness = collect_runtime_readiness()
    readiness_checks = {check.name: check for check in readiness.checks}
    for label, check_name in (
        ("CLI Entrypoint", "cli_entrypoint"),
        ("Watch Folder Boundary", "watch_folder_boundary"),
        ("Downloads Watch Boundary", "downloads_watch_dir_boundary"),
        ("Latest Audit Quality", "latest_intake_override_audit_quality"),
    ):
        boundary_check = readiness_checks.get(check_name)
        if boundary_check is None:
            continue
        boundary_icon = _doctor_status_icon(boundary_check.status)
        console.print(f"   - {label}: {boundary_icon} {boundary_check.detail}")
        if boundary_check.path:
            console.print(f"     Path: {boundary_check.path}")
    _print_first_paper_doctor_guidance(readiness_checks)
    latest_audit_check = readiness_checks.get("latest_intake_override_audit")
    latest_audit_metadata = (
        dict(getattr(latest_audit_check, "metadata", {}) or {}) if latest_audit_check is not None else {}
    )
    latest_audit_available = bool(latest_audit_metadata.get("available"))
    latest_audit_path = getattr(latest_audit_check, "path", None) if latest_audit_check is not None else None
    latest_audit_run_id = str(latest_audit_metadata.get("run_id") or "").strip()

    if latest_audit_check is None:
        latest_intake_override_audit = latest_intake_override_audit_run()
        if latest_intake_override_audit is not None:
            latest_audit_available = True
            latest_audit_run_id = latest_intake_override_audit.name
            latest_audit_path = str(latest_intake_override_audit / "audit.md")
        else:
            latest_intake_override_audit = None
    else:
        latest_intake_override_audit = (
            Path(str(latest_audit_path)).expanduser().resolve(strict=False).parent
            if latest_audit_available and latest_audit_path
            else None
        )

    if not latest_audit_available or latest_intake_override_audit is None:
        console.print(
            "   - Latest Intake Override Audit: none found "
            f"({latest_audit_path or default_intake_override_audits_root()})"
        )
    else:
        console.print(f"   - Latest Intake Override Audit: {latest_audit_run_id or latest_intake_override_audit.name}")
        console.print(f"     Path: {latest_audit_path or (latest_intake_override_audit / 'audit.md')}")
        console.print(
            "     Open: "
            f"{build_intake_override_audit_viewer_command(latest_intake_override_audit)}"
        )
        scope_summary = _latest_audit_scope_summary(latest_audit_metadata)
        if scope_summary:
            console.print(f"     Scope: {scope_summary}")
        quality_summary = _latest_audit_quality_summary(latest_audit_metadata)
        if quality_summary:
            console.print(f"     Quality: {quality_summary}")
        quality_signals = _latest_audit_quality_signals_text(latest_audit_metadata)
        if quality_signals:
            console.print(f"     Signals: {quality_signals}")
        calibration_snapshot = build_intake_override_audit_calibration_snapshot(
            root=default_intake_override_audits_root(),
            warn_threshold=LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
            min_audited_docs=LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
        )
        calibration_summary = _audit_calibration_summary_text(calibration_snapshot)
        if calibration_summary:
            console.print(f"     Calibration: {calibration_summary}")
        calibration_recommendations = calibration_snapshot.get("recommendations")
        if isinstance(calibration_recommendations, list) and calibration_recommendations:
            first_recommendation = str(calibration_recommendations[0]).strip()
            if first_recommendation:
                console.print(f"     Advice: {first_recommendation}")
    latest_threshold_review = latest_intake_override_threshold_review_run()
    latest_threshold_review_path = (
        str(latest_threshold_review / "summary.json") if latest_threshold_review is not None else None
    )
    latest_threshold_review_markdown_path = (
        str(latest_threshold_review / "audit.md")
        if latest_threshold_review is not None and (latest_threshold_review / "audit.md").exists()
        else None
    )
    if latest_threshold_review is None:
        console.print(
            "   - Latest Intake Override Threshold Review: none found "
            f"({default_intake_override_threshold_review_root()})"
        )
    else:
        console.print(f"   - Latest Intake Override Threshold Review: {latest_threshold_review.name}")
        console.print(f"     Path: {latest_threshold_review_path}")
        if latest_threshold_review_markdown_path:
            console.print(f"     Markdown: {latest_threshold_review_markdown_path}")
        console.print(
            "     Open: "
            f"{build_intake_override_threshold_review_viewer_command(latest_threshold_review)}"
        )
        try:
            threshold_summary = _load_json_dict(latest_threshold_review / "summary.json")
        except Exception as exc:
            console.print(f"     Summary: unavailable ({exc})")
            threshold_summary = {}
        threshold_decision = (
            threshold_summary.get("decision")
            if isinstance(threshold_summary.get("decision"), dict)
            else {}
        )
        recommended_action = str(threshold_decision.get("recommended_action") or "").strip()
        next_step = str(threshold_decision.get("next_step") or "").strip()
        latest_run_id = str(threshold_decision.get("latest_run_id") or "").strip()
        latest_run_status = str(threshold_decision.get("latest_run_status") or "").strip()
        latest_warn_signals = (
            [str(item).strip() for item in threshold_decision.get("latest_warn_signals", []) if str(item).strip()]
            if isinstance(threshold_decision.get("latest_warn_signals"), list)
            else []
        )
        tuning_recommendations = (
            [str(item).strip() for item in threshold_decision.get("tuning_recommendations", []) if str(item).strip()]
            if isinstance(threshold_decision.get("tuning_recommendations"), list)
            else []
        )
        tuning_targets = (
            [str(item).strip() for item in threshold_decision.get("tuning_targets", []) if str(item).strip()]
            if isinstance(threshold_decision.get("tuning_targets"), list)
            else []
        )
        tuning_actions = (
            [
                {
                    "target": str(item.get("target") or "").strip(),
                    "action": str(item.get("action") or "").strip(),
                    "summary": str(item.get("summary") or "").strip(),
                }
                for item in threshold_decision.get("tuning_actions", [])
                if isinstance(item, dict)
            ]
            if isinstance(threshold_decision.get("tuning_actions"), list)
            else []
        )
        action_plan = (
            [
                {
                    "order": int(item.get("order") or 0),
                    "action": str(item.get("action") or "").strip(),
                    "target": str(item.get("target") or "").strip(),
                    "blocking": bool(item.get("blocking")),
                    "signals": [
                        str(signal).strip()
                        for signal in item.get("signals", [])
                        if str(signal).strip()
                    ],
                    "summary": str(item.get("summary") or "").strip(),
                    "evidence": str(item.get("evidence") or "").strip(),
                }
                for item in threshold_decision.get("action_plan", [])
                if isinstance(item, dict)
            ]
            if isinstance(threshold_decision.get("action_plan"), list)
            else []
        )
        blocking_action = (
            {
                "order": int(threshold_decision.get("blocking_action", {}).get("order") or 0),
                "action": str(threshold_decision.get("blocking_action", {}).get("action") or "").strip(),
                "target": str(threshold_decision.get("blocking_action", {}).get("target") or "").strip(),
                "signals": [
                    str(signal).strip()
                    for signal in threshold_decision.get("blocking_action", {}).get("signals", [])
                    if str(signal).strip()
                ],
                "summary": str(threshold_decision.get("blocking_action", {}).get("summary") or "").strip(),
                "evidence": str(threshold_decision.get("blocking_action", {}).get("evidence") or "").strip(),
            }
            if isinstance(threshold_decision.get("blocking_action"), dict)
            else None
        )
        blocking_summary = str(threshold_decision.get("blocking_summary") or "").strip()
        focus_signals = (
            [str(item).strip() for item in threshold_decision.get("focus_signals", []) if str(item).strip()]
            if isinstance(threshold_decision.get("focus_signals"), list)
            else []
        )
        decision_parts: list[str] = []
        if recommended_action:
            decision_parts.append(f"action={recommended_action}")
        decision_parts.append(
            "review_ready=yes" if bool(threshold_decision.get("review_ready")) else "review_ready=no"
        )
        if next_step:
            decision_parts.append(f"next={next_step}")
        if latest_run_id:
            latest_run_text = latest_run_id
            if latest_run_status:
                latest_run_text = f"{latest_run_text} ({latest_run_status})"
            decision_parts.append(f"latest={latest_run_text}")
        if decision_parts:
            console.print(f"     Decision: {', '.join(decision_parts)}")
        if focus_signals:
            console.print(f"     Focus: {', '.join(focus_signals)}")
        if latest_warn_signals:
            console.print(f"     Latest Warn Signals: {', '.join(latest_warn_signals)}")
        if blocking_action and blocking_action["action"]:
            blocking_text = (
                f"{blocking_action['order']}.{blocking_action['action']}"
                if blocking_action["order"]
                else blocking_action["action"]
            )
            if blocking_action["target"]:
                blocking_text = f"{blocking_text}->{blocking_action['target']}"
            console.print(f"     Blocking: {blocking_text}")
            if blocking_action["signals"]:
                console.print(f"     Blocking Signals: {', '.join(blocking_action['signals'])}")
            if blocking_action["evidence"]:
                console.print(f"     Blocking Why: {blocking_action['evidence']}")
        if blocking_summary:
            console.print(f"     Blocking Summary: {blocking_summary}")
        if tuning_targets:
            console.print(f"     Targets: {', '.join(tuning_targets)}")
        if tuning_actions:
            console.print(
                "     Actions: "
                + " | ".join(
                    f"{item['target']}:{item['action']}"
                    for item in tuning_actions
                    if item["target"] and item["action"]
                )
            )
        if action_plan:
            console.print(
                "     Plan: "
                + " | ".join(
                    f"{item['order']}.{item['action']}"
                    + (f"->{item['target']}" if item["target"] else "")
                    for item in action_plan
                    if item["order"] and item["action"]
                )
            )
            if any(item["signals"] for item in action_plan):
                console.print(
                    "     Plan Signals: "
                    + " | ".join(
                        f"{item['order']}.{','.join(item['signals'])}"
                        for item in action_plan
                        if item["order"] and item["signals"]
                    )
                )
            if any(item["evidence"] for item in action_plan):
                console.print(
                    "     Plan Why: "
                    + " | ".join(
                        f"{item['order']}.{item['evidence']}"
                        for item in action_plan
                        if item["order"] and item["evidence"]
                    )
                )
        if tuning_recommendations:
            console.print(f"     Tuning: {' | '.join(tuning_recommendations)}")
        decision_reason = str(threshold_decision.get("decision_reason") or "").strip()
        if decision_reason:
            console.print(f"     Reason: {decision_reason}")
    latest_processor_gate_threshold_review = latest_processor_gate_threshold_review_run()
    latest_processor_gate_threshold_review_path = (
        str(latest_processor_gate_threshold_review / "summary.json")
        if latest_processor_gate_threshold_review is not None
        else None
    )
    latest_processor_gate_threshold_review_markdown_path = (
        str(latest_processor_gate_threshold_review / "audit.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "audit.md").exists()
        else None
    )
    latest_processor_gate_manual_review_rows_path = (
        str(latest_processor_gate_threshold_review / "manual_review_rows.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_rows.json").exists()
        else None
    )
    latest_processor_gate_manual_review_markdown_path = (
        str(latest_processor_gate_threshold_review / "manual_review.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review.md").exists()
        else None
    )
    latest_processor_gate_manual_review_checklist_path = (
        str(latest_processor_gate_threshold_review / "manual_review_checklist.csv")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_checklist.csv").exists()
        else None
    )
    latest_processor_gate_manual_review_seed_path = (
        str(latest_processor_gate_threshold_review / "manual_review_seed.csv")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_seed.csv").exists()
        else None
    )
    latest_processor_gate_manual_review_frontier_path = (
        str(latest_processor_gate_threshold_review / "manual_review_frontier.csv")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_frontier.csv").exists()
        else None
    )
    latest_processor_gate_manual_review_frontier_notes_path = (
        str(latest_processor_gate_threshold_review / "manual_review_frontier_notes.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_frontier_notes.md").exists()
        else None
    )
    latest_processor_gate_manual_review_frontier_crosscheck_packet_path = (
        str(latest_processor_gate_threshold_review / "manual_review_frontier_crosscheck_packet.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_frontier_crosscheck_packet.md").exists()
        else None
    )
    latest_processor_gate_manual_review_frontier_claude_crosscheck_path = (
        str(latest_processor_gate_threshold_review / "manual_review_frontier_claude_crosscheck.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_frontier_claude_crosscheck.md").exists()
        else None
    )
    latest_processor_gate_manual_review_frontier_claude_crosscheck_json_path = (
        str(latest_processor_gate_threshold_review / "manual_review_frontier_claude_crosscheck.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_frontier_claude_crosscheck.json").exists()
        else None
    )
    latest_processor_gate_manual_review_basis_markdown_path = (
        str(latest_processor_gate_threshold_review / "manual_review_basis.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_basis.md").exists()
        else None
    )
    latest_processor_gate_manual_review_decision_markdown_path = (
        str(latest_processor_gate_threshold_review / "manual_review_decision.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_decision.md").exists()
        else None
    )
    latest_processor_gate_manual_review_outcome_path = (
        str(latest_processor_gate_threshold_review / "manual_review_outcome.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_outcome.json").exists()
        else None
    )
    latest_processor_gate_manual_review_outcome_markdown_path = (
        str(latest_processor_gate_threshold_review / "manual_review_outcome.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_review_outcome.md").exists()
        else None
    )
    latest_processor_gate_threshold_change_decision_path = (
        str(latest_processor_gate_threshold_review / "threshold_change_decision.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "threshold_change_decision.json").exists()
        else None
    )
    latest_processor_gate_threshold_change_decision_markdown_path = (
        str(latest_processor_gate_threshold_review / "threshold_change_decision.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "threshold_change_decision.md").exists()
        else None
    )
    latest_processor_gate_mid_confidence_policy_decision_path = (
        str(latest_processor_gate_threshold_review / "mid_confidence_policy_decision.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "mid_confidence_policy_decision.json").exists()
        else None
    )
    latest_processor_gate_mid_confidence_policy_decision_markdown_path = (
        str(latest_processor_gate_threshold_review / "mid_confidence_policy_decision.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "mid_confidence_policy_decision.md").exists()
        else None
    )
    latest_processor_gate_mid_confidence_policy_debt_reconciliation_path = (
        str(latest_processor_gate_threshold_review / "mid_confidence_policy_debt_reconciliation.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "mid_confidence_policy_debt_reconciliation.json").exists()
        else None
    )
    latest_processor_gate_mid_confidence_policy_debt_reconciliation_markdown_path = (
        str(latest_processor_gate_threshold_review / "mid_confidence_policy_debt_reconciliation.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "mid_confidence_policy_debt_reconciliation.md").exists()
        else None
    )
    latest_processor_gate_manual_override_policy_decision_path = (
        str(latest_processor_gate_threshold_review / "manual_override_policy_decision.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_override_policy_decision.json").exists()
        else None
    )
    latest_processor_gate_manual_override_policy_decision_markdown_path = (
        str(latest_processor_gate_threshold_review / "manual_override_policy_decision.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "manual_override_policy_decision.md").exists()
        else None
    )
    latest_processor_gate_indexed_pending_policy_decision_path = (
        str(latest_processor_gate_threshold_review / "indexed_pending_policy_decision.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "indexed_pending_policy_decision.json").exists()
        else None
    )
    latest_processor_gate_indexed_pending_policy_decision_markdown_path = (
        str(latest_processor_gate_threshold_review / "indexed_pending_policy_decision.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "indexed_pending_policy_decision.md").exists()
        else None
    )
    latest_processor_gate_fixture_or_test_policy_decision_path = (
        str(latest_processor_gate_threshold_review / "fixture_or_test_policy_decision.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "fixture_or_test_policy_decision.json").exists()
        else None
    )
    latest_processor_gate_fixture_or_test_policy_decision_markdown_path = (
        str(latest_processor_gate_threshold_review / "fixture_or_test_policy_decision.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "fixture_or_test_policy_decision.md").exists()
        else None
    )
    latest_processor_gate_threshold_change_proposal_path = (
        str(latest_processor_gate_threshold_review / "threshold_change_proposal.json")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "threshold_change_proposal.json").exists()
        else None
    )
    latest_processor_gate_threshold_change_proposal_markdown_path = (
        str(latest_processor_gate_threshold_review / "threshold_change_proposal.md")
        if latest_processor_gate_threshold_review is not None
        and (latest_processor_gate_threshold_review / "threshold_change_proposal.md").exists()
        else None
    )
    latest_processor_gate_threshold_validation_replay_command = None
    if latest_processor_gate_threshold_change_proposal_path:
        try:
            threshold_change_proposal = _load_json_dict(
                Path(latest_processor_gate_threshold_change_proposal_path)
            )
            latest_processor_gate_threshold_validation_replay_command = str(
                threshold_change_proposal.get("validation_replay_command_template") or ""
            ).strip() or None
        except Exception:
            latest_processor_gate_threshold_validation_replay_command = None
    if latest_processor_gate_threshold_review is None:
        console.print(
            "   - Latest Processor Gate Threshold Review: none found "
            f"({default_processor_gate_threshold_review_root()})"
        )
    else:
        console.print(
            f"   - Latest Processor Gate Threshold Review: "
            f"{latest_processor_gate_threshold_review.name}"
        )
        console.print(f"     Path: {latest_processor_gate_threshold_review_path}")
        if latest_processor_gate_threshold_review_markdown_path:
            console.print(f"     Markdown: {latest_processor_gate_threshold_review_markdown_path}")
        if latest_processor_gate_manual_review_rows_path:
            console.print(f"     Manual Review Rows: {latest_processor_gate_manual_review_rows_path}")
        if latest_processor_gate_manual_review_markdown_path:
            console.print(f"     Manual Review Markdown: {latest_processor_gate_manual_review_markdown_path}")
        if latest_processor_gate_manual_review_checklist_path:
            console.print(f"     Manual Review Checklist: {latest_processor_gate_manual_review_checklist_path}")
        if latest_processor_gate_manual_review_seed_path:
            console.print(f"     Manual Review Seed: {latest_processor_gate_manual_review_seed_path}")
        if latest_processor_gate_manual_review_frontier_path:
            console.print(f"     Manual Review Frontier: {latest_processor_gate_manual_review_frontier_path}")
        if latest_processor_gate_manual_review_frontier_notes_path:
            console.print(f"     Manual Review Frontier Notes: {latest_processor_gate_manual_review_frontier_notes_path}")
        if latest_processor_gate_manual_review_frontier_crosscheck_packet_path:
            console.print(
                f"     Manual Review Frontier Crosscheck Packet: {latest_processor_gate_manual_review_frontier_crosscheck_packet_path}"
            )
        if latest_processor_gate_manual_review_frontier_claude_crosscheck_path:
            console.print(
                f"     Manual Review Frontier Claude Crosscheck: {latest_processor_gate_manual_review_frontier_claude_crosscheck_path}"
            )
        if latest_processor_gate_manual_review_frontier_claude_crosscheck_json_path:
            console.print(
                f"     Manual Review Frontier Claude Crosscheck JSON: {latest_processor_gate_manual_review_frontier_claude_crosscheck_json_path}"
            )
        if latest_processor_gate_manual_review_basis_markdown_path:
            console.print(f"     Manual Review Basis: {latest_processor_gate_manual_review_basis_markdown_path}")
        if latest_processor_gate_manual_review_decision_markdown_path:
            console.print(f"     Manual Review Decision: {latest_processor_gate_manual_review_decision_markdown_path}")
        if latest_processor_gate_manual_review_outcome_path:
            console.print(f"     Manual Review Outcome: {latest_processor_gate_manual_review_outcome_path}")
        if latest_processor_gate_manual_review_outcome_markdown_path:
            console.print(
                "     Manual Review Outcome Markdown: "
                f"{latest_processor_gate_manual_review_outcome_markdown_path}"
            )
        if latest_processor_gate_threshold_change_decision_path:
            console.print(
                f"     Threshold Change Decision: {latest_processor_gate_threshold_change_decision_path}"
            )
        if latest_processor_gate_threshold_change_decision_markdown_path:
            console.print(
                "     Threshold Change Decision Markdown: "
                f"{latest_processor_gate_threshold_change_decision_markdown_path}"
            )
        if latest_processor_gate_mid_confidence_policy_decision_path:
            console.print(
                "     Mid-Confidence Policy Decision: "
                f"{latest_processor_gate_mid_confidence_policy_decision_path}"
            )
        if latest_processor_gate_mid_confidence_policy_decision_markdown_path:
            console.print(
                "     Mid-Confidence Policy Decision Markdown: "
                f"{latest_processor_gate_mid_confidence_policy_decision_markdown_path}"
            )
        if latest_processor_gate_mid_confidence_policy_debt_reconciliation_path:
            console.print(
                "     Mid-Confidence Policy Debt Reconciliation: "
                f"{latest_processor_gate_mid_confidence_policy_debt_reconciliation_path}"
            )
            console.print(
                "     Policy Debt Reconciliation File: "
                "mid_confidence_policy_debt_reconciliation.json"
            )
        if latest_processor_gate_mid_confidence_policy_debt_reconciliation_markdown_path:
            console.print(
                "     Mid-Confidence Policy Debt Reconciliation Markdown: "
                f"{latest_processor_gate_mid_confidence_policy_debt_reconciliation_markdown_path}"
            )
            console.print(
                "     Policy Debt Reconciliation Markdown File: "
                "mid_confidence_policy_debt_reconciliation.md"
            )
        if latest_processor_gate_manual_override_policy_decision_path:
            console.print(
                "     Manual Override Policy Decision: "
                f"{latest_processor_gate_manual_override_policy_decision_path}"
            )
            console.print(
                "     Manual Override Policy Decision File: "
                "manual_override_policy_decision.json"
            )
        if latest_processor_gate_manual_override_policy_decision_markdown_path:
            console.print(
                "     Manual Override Policy Decision Markdown: "
                f"{latest_processor_gate_manual_override_policy_decision_markdown_path}"
            )
            console.print(
                "     Manual Override Policy Decision Markdown File: "
                "manual_override_policy_decision.md"
            )
        if latest_processor_gate_indexed_pending_policy_decision_path:
            console.print(
                "     Indexed Pending Policy Decision: "
                f"{latest_processor_gate_indexed_pending_policy_decision_path}"
            )
            console.print(
                "     Indexed Pending Policy Decision File: "
                "indexed_pending_policy_decision.json"
            )
        if latest_processor_gate_indexed_pending_policy_decision_markdown_path:
            console.print(
                "     Indexed Pending Policy Decision Markdown: "
                f"{latest_processor_gate_indexed_pending_policy_decision_markdown_path}"
            )
            console.print(
                "     Indexed Pending Policy Decision Markdown File: "
                "indexed_pending_policy_decision.md"
            )
        if latest_processor_gate_fixture_or_test_policy_decision_path:
            console.print(
                "     Fixture/Test Policy Decision: "
                f"{latest_processor_gate_fixture_or_test_policy_decision_path}"
            )
            console.print(
                "     Fixture/Test Policy Decision File: "
                "fixture_or_test_policy_decision.json"
            )
        if latest_processor_gate_fixture_or_test_policy_decision_markdown_path:
            console.print(
                "     Fixture/Test Policy Decision Markdown: "
                f"{latest_processor_gate_fixture_or_test_policy_decision_markdown_path}"
            )
            console.print(
                "     Fixture/Test Policy Decision Markdown File: "
                "fixture_or_test_policy_decision.md"
            )
        if latest_processor_gate_threshold_change_proposal_path:
            console.print(
                f"     Threshold Change Proposal: {latest_processor_gate_threshold_change_proposal_path}"
            )
        if latest_processor_gate_threshold_validation_replay_command:
            console.print(
                "     Threshold Change Validation Replay: "
                f"{latest_processor_gate_threshold_validation_replay_command}"
            )
        if latest_processor_gate_threshold_change_proposal_markdown_path:
            console.print(
                "     Threshold Change Proposal Markdown: "
                f"{latest_processor_gate_threshold_change_proposal_markdown_path}"
            )
        console.print(
            "     Open: "
            f"{build_processor_gate_threshold_review_viewer_command(latest_processor_gate_threshold_review)}"
        )
        try:
            processor_gate_threshold_summary = load_processor_gate_threshold_review_summary(
                latest_processor_gate_threshold_review
            )
        except Exception as exc:
            console.print(f"     Summary: unavailable ({exc})")
            processor_gate_threshold_summary = {}
        try:
            processor_gate_manual_review_outcome = (
                _load_json_dict(Path(latest_processor_gate_manual_review_outcome_path))
                if latest_processor_gate_manual_review_outcome_path
                else {}
            )
        except Exception as exc:
            console.print(f"     Manual Review Outcome Summary: unavailable ({exc})")
            processor_gate_manual_review_outcome = {}
        try:
            processor_gate_threshold_change_decision = (
                _load_json_dict(Path(latest_processor_gate_threshold_change_decision_path))
                if latest_processor_gate_threshold_change_decision_path
                else {}
            )
        except Exception as exc:
            console.print(f"     Threshold Change Decision Summary: unavailable ({exc})")
            processor_gate_threshold_change_decision = {}
        try:
            processor_gate_mid_confidence_policy_decision = (
                _load_json_dict(Path(latest_processor_gate_mid_confidence_policy_decision_path))
                if latest_processor_gate_mid_confidence_policy_decision_path
                else {}
            )
        except Exception as exc:
            console.print(f"     Mid-Confidence Policy Decision Summary: unavailable ({exc})")
            processor_gate_mid_confidence_policy_decision = {}
        try:
            processor_gate_policy_debt_reconciliation = (
                _load_json_dict(
                    Path(latest_processor_gate_mid_confidence_policy_debt_reconciliation_path)
                )
                if latest_processor_gate_mid_confidence_policy_debt_reconciliation_path
                else {}
            )
        except Exception as exc:
            console.print(f"     Policy Debt Reconciliation Summary: unavailable ({exc})")
            processor_gate_policy_debt_reconciliation = {}
        try:
            processor_gate_manual_override_policy_decision = (
                _load_json_dict(Path(latest_processor_gate_manual_override_policy_decision_path))
                if latest_processor_gate_manual_override_policy_decision_path
                else {}
            )
        except Exception as exc:
            console.print(f"     Manual Override Policy Decision Summary: unavailable ({exc})")
            processor_gate_manual_override_policy_decision = {}
        try:
            processor_gate_indexed_pending_policy_decision = (
                _load_json_dict(Path(latest_processor_gate_indexed_pending_policy_decision_path))
                if latest_processor_gate_indexed_pending_policy_decision_path
                else {}
            )
        except Exception as exc:
            console.print(f"     Indexed Pending Policy Decision Summary: unavailable ({exc})")
            processor_gate_indexed_pending_policy_decision = {}
        try:
            processor_gate_fixture_or_test_policy_decision = (
                _load_json_dict(Path(latest_processor_gate_fixture_or_test_policy_decision_path))
                if latest_processor_gate_fixture_or_test_policy_decision_path
                else {}
            )
        except Exception as exc:
            console.print(f"     Fixture/Test Policy Decision Summary: unavailable ({exc})")
            processor_gate_fixture_or_test_policy_decision = {}
        processor_gate_threshold_drift_artifacts = (
            resolve_processor_gate_threshold_review_drift_artifacts(
                processor_gate_threshold_summary,
                threshold_change_proposal_path=(
                    Path(latest_processor_gate_threshold_change_proposal_path)
                    if latest_processor_gate_threshold_change_proposal_path
                    else None
                ),
            )
            if isinstance(processor_gate_threshold_summary, dict)
            else {}
        )
        replay_drift_summary_path = str(
            processor_gate_threshold_drift_artifacts.get("drift_summary_path") or ""
        ).strip()
        replay_drift_details_path = str(
            processor_gate_threshold_drift_artifacts.get("drift_details_path") or ""
        ).strip()
        replay_drift_markdown_path = str(
            processor_gate_threshold_drift_artifacts.get("drift_markdown_path") or ""
        ).strip()
        threshold_replay_path = str(
            processor_gate_threshold_drift_artifacts.get("threshold_replay_path") or ""
        ).strip()
        threshold_replay_markdown_path = str(
            processor_gate_threshold_drift_artifacts.get("threshold_replay_markdown_path") or ""
        ).strip()
        threshold_replay_text = str(
            processor_gate_threshold_drift_artifacts.get("threshold_replay_text") or ""
        ).strip()
        threshold_replay_review_command = str(
            processor_gate_threshold_drift_artifacts.get("threshold_replay_review_command")
            or ""
        ).strip()
        if replay_drift_summary_path:
            console.print(f"     Replay Drift Summary: {replay_drift_summary_path}")
        if replay_drift_details_path:
            console.print(f"     Replay Drift Details: {replay_drift_details_path}")
        if replay_drift_markdown_path:
            console.print(f"     Replay Drift Markdown: {replay_drift_markdown_path}")
        if threshold_replay_path:
            console.print(f"     Threshold Replay Context: {threshold_replay_path}")
        if threshold_replay_markdown_path:
            console.print(
                f"     Threshold Replay Context Markdown: {threshold_replay_markdown_path}"
            )
        if threshold_replay_text:
            console.print(f"     Threshold Replay: {threshold_replay_text}")
        if threshold_replay_review_command:
            console.print(
                "     Threshold Replay Review Command: "
                f"{threshold_replay_review_command}"
            )
        validation_replay_status = str(
            processor_gate_threshold_drift_artifacts.get(
                "threshold_change_validation_replay_status"
            )
            or ""
        ).strip()
        if validation_replay_status and validation_replay_status != "not_applicable":
            validation_available = bool(
                processor_gate_threshold_drift_artifacts.get(
                    "threshold_change_validation_replay_available"
                )
            )
            validation_matches = bool(
                processor_gate_threshold_drift_artifacts.get(
                    "threshold_change_validation_replay_matches_proposal"
                )
            )
            validation_needs_rerun = bool(
                processor_gate_threshold_drift_artifacts.get(
                    "threshold_change_validation_replay_needs_rerun"
                )
            )
            console.print(
                "     Threshold Change Validation Replay Status: "
                f"{validation_replay_status} "
                f"(available={'yes' if validation_available else 'no'}, "
                f"matches={'yes' if validation_matches else 'no'}, "
                f"needs_rerun={'yes' if validation_needs_rerun else 'no'})"
            )
        manual_decision_status = str(
            processor_gate_threshold_drift_artifacts.get(
                "threshold_change_manual_decision_status"
            )
            or ""
        ).strip()
        if manual_decision_status and manual_decision_status != "not_applicable":
            manual_decision_ready = bool(
                processor_gate_threshold_drift_artifacts.get(
                    "threshold_change_manual_decision_ready"
                )
            )
            manual_decision_blocker = str(
                processor_gate_threshold_drift_artifacts.get(
                    "threshold_change_manual_decision_blocker"
                )
                or ""
            ).strip()
            manual_decision_text = (
                "     Threshold Change Manual Decision: "
                f"ready={'yes' if manual_decision_ready else 'no'}, "
                f"status={manual_decision_status}"
            )
            if manual_decision_blocker:
                manual_decision_text = (
                    f"{manual_decision_text}, blocker={manual_decision_blocker}"
                )
            console.print(manual_decision_text)
        processor_gate_threshold_inputs = (
            processor_gate_threshold_summary.get("inputs")
            if isinstance(processor_gate_threshold_summary.get("inputs"), dict)
            else {}
        )
        processor_gate_threshold_decision = (
            processor_gate_threshold_summary.get("decision")
            if isinstance(processor_gate_threshold_summary.get("decision"), dict)
            else {}
        )
        processor_gate_threshold_signals = (
            processor_gate_threshold_summary.get("signal_summary")
            if isinstance(processor_gate_threshold_summary.get("signal_summary"), dict)
            else {}
        )
        processor_gate_manual_review_scope = (
            processor_gate_threshold_summary.get("manual_review_scope")
            if isinstance(processor_gate_threshold_summary.get("manual_review_scope"), dict)
            else {}
        )
        processor_gate_manual_review_basis = (
            processor_gate_threshold_summary.get("manual_review_basis")
            if isinstance(processor_gate_threshold_summary.get("manual_review_basis"), dict)
            else {}
        )
        processor_gate_worksheet_summary = (
            processor_gate_manual_review_scope.get("worksheet_summary")
            if isinstance(processor_gate_manual_review_scope.get("worksheet_summary"), dict)
            else {}
        )
        processor_gate_prefill_summary = (
            processor_gate_manual_review_scope.get("prefill_summary")
            if isinstance(processor_gate_manual_review_scope.get("prefill_summary"), dict)
            else {}
        )
        processor_gate_decision_parts: list[str] = []
        processor_gate_action = str(
            processor_gate_threshold_decision.get("recommended_action") or ""
        ).strip()
        processor_gate_next_step = str(
            processor_gate_threshold_decision.get("next_step") or ""
        ).strip()
        processor_gate_latest_run_id = str(
            processor_gate_threshold_decision.get("latest_run_id") or ""
        ).strip()
        processor_gate_latest_run_status = str(
            processor_gate_threshold_decision.get("latest_run_status") or ""
        ).strip()
        if processor_gate_action:
            processor_gate_decision_parts.append(f"action={processor_gate_action}")
        processor_gate_decision_parts.append(
            "review_ready=yes"
            if bool(processor_gate_threshold_decision.get("review_ready"))
            else "review_ready=no"
        )
        if processor_gate_next_step:
            processor_gate_decision_parts.append(f"next={processor_gate_next_step}")
        if processor_gate_latest_run_id:
            processor_gate_latest_text = processor_gate_latest_run_id
            if processor_gate_latest_run_status:
                processor_gate_latest_text = (
                    f"{processor_gate_latest_text} ({processor_gate_latest_run_status})"
                )
            processor_gate_decision_parts.append(f"latest={processor_gate_latest_text}")
        if processor_gate_decision_parts:
            console.print(f"     Decision: {', '.join(processor_gate_decision_parts)}")
        processor_gate_threshold_change_parts: list[str] = []
        if "threshold_change_ready" in processor_gate_threshold_decision:
            processor_gate_threshold_change_parts.append(
                "ready=yes"
                if bool(processor_gate_threshold_decision.get("threshold_change_ready"))
                else "ready=no"
            )
        processor_gate_threshold_change_status = str(
            processor_gate_threshold_decision.get("threshold_change_status") or ""
        ).strip()
        if processor_gate_threshold_change_status:
            processor_gate_threshold_change_parts.append(
                f"status={processor_gate_threshold_change_status}"
            )
        processor_gate_threshold_change_next_step = str(
            processor_gate_threshold_decision.get("threshold_change_next_step") or ""
        ).strip()
        if processor_gate_threshold_change_next_step:
            processor_gate_threshold_change_parts.append(
                f"next={processor_gate_threshold_change_next_step}"
            )
        if processor_gate_threshold_change_parts:
            console.print(
                f"     Threshold Change: {', '.join(processor_gate_threshold_change_parts)}"
            )
        processor_gate_threshold_change_blocker = str(
            processor_gate_threshold_decision.get("threshold_change_blocker") or ""
        ).strip()
        if processor_gate_threshold_change_blocker:
            console.print(f"     Threshold Blocker: {processor_gate_threshold_change_blocker}")
        processor_gate_focus_areas = (
            [str(item).strip() for item in processor_gate_threshold_decision.get("focus_areas", []) if str(item).strip()]
            if isinstance(processor_gate_threshold_decision.get("focus_areas"), list)
            else []
        )
        if processor_gate_focus_areas:
            console.print(f"     Focus: {', '.join(processor_gate_focus_areas)}")
        processor_gate_tuning_targets = (
            [str(item).strip() for item in processor_gate_threshold_decision.get("tuning_targets", []) if str(item).strip()]
            if isinstance(processor_gate_threshold_decision.get("tuning_targets"), list)
            else []
        )
        if processor_gate_tuning_targets:
            console.print(f"     Targets: {', '.join(processor_gate_tuning_targets)}")
        processor_gate_tuning_actions = (
            [
                {
                    "target": str(item.get("target") or "").strip(),
                    "action": str(item.get("action") or "").strip(),
                }
                for item in processor_gate_threshold_decision.get("tuning_actions", [])
                if isinstance(item, dict)
                and str(item.get("target") or "").strip()
                and str(item.get("action") or "").strip()
            ]
            if isinstance(processor_gate_threshold_decision.get("tuning_actions"), list)
            else []
        )
        if processor_gate_tuning_actions:
            console.print(
                "     Actions: "
                + " | ".join(
                    f"{item['target']}:{item['action']}" for item in processor_gate_tuning_actions
                )
            )
        processor_gate_action_plan = (
            [
                {
                    "order": int(item.get("order") or 0),
                    "action": str(item.get("action") or "").strip(),
                    "target": str(item.get("target") or "").strip(),
                }
                for item in processor_gate_threshold_decision.get("action_plan", [])
                if isinstance(item, dict)
                and int(item.get("order") or 0) > 0
                and str(item.get("action") or "").strip()
            ]
            if isinstance(processor_gate_threshold_decision.get("action_plan"), list)
            else []
        )
        if processor_gate_action_plan:
            console.print(
                "     Plan: "
                + " | ".join(
                    f"{item['order']}.{item['action']}"
                    + (f"->{item['target']}" if item["target"] else "")
                    for item in processor_gate_action_plan
                )
            )
        processor_gate_threshold_relevant = (
            processor_gate_manual_review_scope.get("threshold_relevant")
            if isinstance(processor_gate_manual_review_scope.get("threshold_relevant"), dict)
            else {}
        )
        processor_gate_policy_edge_cases = (
            processor_gate_manual_review_scope.get("policy_edge_cases")
            if isinstance(processor_gate_manual_review_scope.get("policy_edge_cases"), dict)
            else {}
        )
        processor_gate_excluded = (
            processor_gate_manual_review_scope.get("excluded")
            if isinstance(processor_gate_manual_review_scope.get("excluded"), dict)
            else {}
        )
        def _processor_gate_sample_ids_preview(bucket: object) -> str:
            if not isinstance(bucket, dict):
                return ""
            paper_ids = [str(item).strip() for item in bucket.get("paper_ids", []) if str(item).strip()]
            if not paper_ids:
                return ""
            preview = ", ".join(paper_ids[:3])
            if len(paper_ids) > 3:
                preview += f" (+{len(paper_ids) - 3} more)"
            return preview
        processor_gate_scope_parts = [
            f"relevant={int(processor_gate_threshold_relevant.get('count') or 0)}",
            f"policy={int(processor_gate_policy_edge_cases.get('count') or 0)}",
            f"excluded.manual_override={int(((processor_gate_excluded.get('manual_override') or {}) if isinstance(processor_gate_excluded.get('manual_override'), dict) else {}).get('count') or 0)}",
            f"excluded.indexed_pending={int(((processor_gate_excluded.get('indexed_pending') or {}) if isinstance(processor_gate_excluded.get('indexed_pending'), dict) else {}).get('count') or 0)}",
            f"excluded.fixture_or_test={int(((processor_gate_excluded.get('fixture_or_test') or {}) if isinstance(processor_gate_excluded.get('fixture_or_test'), dict) else {}).get('count') or 0)}",
            f"excluded.other={int(((processor_gate_excluded.get('other') or {}) if isinstance(processor_gate_excluded.get('other'), dict) else {}).get('count') or 0)}",
        ]
        console.print(f"     Scope: {', '.join(processor_gate_scope_parts)}")
        processor_gate_scope_preview_parts = []
        relevant_preview = _processor_gate_sample_ids_preview(processor_gate_threshold_relevant)
        if relevant_preview:
            processor_gate_scope_preview_parts.append(f"relevant={relevant_preview}")
        manual_preview = _processor_gate_sample_ids_preview(processor_gate_excluded.get("manual_override"))
        if manual_preview:
            processor_gate_scope_preview_parts.append(f"excluded.manual_override={manual_preview}")
        indexed_preview = _processor_gate_sample_ids_preview(processor_gate_excluded.get("indexed_pending"))
        if indexed_preview:
            processor_gate_scope_preview_parts.append(f"excluded.indexed_pending={indexed_preview}")
        fixture_preview = _processor_gate_sample_ids_preview(processor_gate_excluded.get("fixture_or_test"))
        if fixture_preview:
            processor_gate_scope_preview_parts.append(f"excluded.fixture_or_test={fixture_preview}")
        if processor_gate_scope_preview_parts:
            console.print(f"     Scope Samples: {' | '.join(processor_gate_scope_preview_parts)}")
        processor_gate_focus_recommendation = str(
            processor_gate_manual_review_scope.get("focus_recommendation") or ""
        ).strip()
        if processor_gate_focus_recommendation:
            console.print(f"     Review Basis: {processor_gate_focus_recommendation}")
        processor_gate_worksheet_text = _processor_gate_worksheet_compact_text(
            processor_gate_worksheet_summary
        )
        if processor_gate_worksheet_text:
            console.print(f"     Worksheet: {processor_gate_worksheet_text}")
        processor_gate_worksheet_summary_text = str(
            processor_gate_worksheet_summary.get("summary") or ""
        ).strip()
        if processor_gate_worksheet_summary_text:
            console.print(f"     Worksheet Summary: {processor_gate_worksheet_summary_text}")
        processor_gate_prefill_text = _processor_gate_prefill_compact_text(
            processor_gate_prefill_summary
        )
        if processor_gate_prefill_text:
            console.print(f"     Prefill: {processor_gate_prefill_text}")
        processor_gate_prefill_summary_text = str(
            processor_gate_prefill_summary.get("summary") or ""
        ).strip()
        if processor_gate_prefill_summary_text:
            console.print(f"     Prefill Summary: {processor_gate_prefill_summary_text}")
        processor_gate_basis_text = _processor_gate_basis_compact_text(
            processor_gate_manual_review_basis
        )
        if processor_gate_basis_text:
            console.print(f"     Basis: {processor_gate_basis_text}")
        processor_gate_basis_summary_text = str(
            processor_gate_manual_review_basis.get("summary") or ""
        ).strip()
        if processor_gate_basis_summary_text:
            console.print(f"     Basis Summary: {processor_gate_basis_summary_text}")
        processor_gate_outcome_text = _processor_gate_manual_review_outcome_compact_text(
            processor_gate_manual_review_outcome
        )
        if processor_gate_outcome_text:
            console.print(f"     Outcome: {processor_gate_outcome_text}")
        processor_gate_outcome_summary_text = str(
            processor_gate_manual_review_outcome.get("summary") or ""
        ).strip()
        if processor_gate_outcome_summary_text:
            console.print(f"     Outcome Summary: {processor_gate_outcome_summary_text}")
        processor_gate_threshold_decision_text = _processor_gate_threshold_change_decision_compact_text(
            processor_gate_threshold_change_decision
        )
        if processor_gate_threshold_decision_text:
            console.print(f"     Threshold Decision: {processor_gate_threshold_decision_text}")
        processor_gate_threshold_decision_summary_text = str(
            processor_gate_threshold_change_decision.get("summary") or ""
        ).strip()
        if processor_gate_threshold_decision_summary_text:
            console.print(
                f"     Threshold Decision Summary: {processor_gate_threshold_decision_summary_text}"
            )
        processor_gate_mid_policy_decision_text = (
            _processor_gate_mid_confidence_policy_decision_compact_text(
                processor_gate_mid_confidence_policy_decision
            )
        )
        if processor_gate_mid_policy_decision_text:
            console.print(f"     Mid-Confidence Policy: {processor_gate_mid_policy_decision_text}")
        processor_gate_mid_policy_summary_text = str(
            processor_gate_mid_confidence_policy_decision.get("summary") or ""
        ).strip()
        if processor_gate_mid_policy_summary_text:
            console.print(f"     Mid-Confidence Policy Summary: {processor_gate_mid_policy_summary_text}")
        processor_gate_policy_debt_text = _processor_gate_policy_debt_reconciliation_compact_text(
            processor_gate_policy_debt_reconciliation
        )
        if processor_gate_policy_debt_text:
            console.print(f"     Policy Debt: {processor_gate_policy_debt_text}")
        processor_gate_policy_debt_summary_text = str(
            processor_gate_policy_debt_reconciliation.get("summary") or ""
        ).strip()
        if processor_gate_policy_debt_summary_text:
            console.print(f"     Policy Debt Summary: {processor_gate_policy_debt_summary_text}")
        processor_gate_manual_override_policy_text = (
            _processor_gate_manual_override_policy_decision_compact_text(
                processor_gate_manual_override_policy_decision
            )
        )
        if processor_gate_manual_override_policy_text:
            console.print(f"     Manual Override Policy: {processor_gate_manual_override_policy_text}")
        processor_gate_manual_override_policy_summary_text = str(
            processor_gate_manual_override_policy_decision.get("summary") or ""
        ).strip()
        if processor_gate_manual_override_policy_summary_text:
            console.print(
                f"     Manual Override Policy Summary: {processor_gate_manual_override_policy_summary_text}"
            )
        processor_gate_indexed_pending_policy_text = (
            _processor_gate_indexed_pending_policy_decision_compact_text(
                processor_gate_indexed_pending_policy_decision
            )
        )
        if processor_gate_indexed_pending_policy_text:
            console.print(f"     Indexed Pending Policy: {processor_gate_indexed_pending_policy_text}")
        processor_gate_indexed_pending_policy_summary_text = str(
            processor_gate_indexed_pending_policy_decision.get("summary") or ""
        ).strip()
        if processor_gate_indexed_pending_policy_summary_text:
            console.print(
                f"     Indexed Pending Policy Summary: {processor_gate_indexed_pending_policy_summary_text}"
            )
        processor_gate_fixture_or_test_policy_text = (
            _processor_gate_fixture_or_test_policy_decision_compact_text(
                processor_gate_fixture_or_test_policy_decision
            )
        )
        if processor_gate_fixture_or_test_policy_text:
            console.print(f"     Fixture/Test Policy: {processor_gate_fixture_or_test_policy_text}")
        processor_gate_fixture_or_test_policy_summary_text = str(
            processor_gate_fixture_or_test_policy_decision.get("summary") or ""
        ).strip()
        if processor_gate_fixture_or_test_policy_summary_text:
            console.print(
                f"     Fixture/Test Policy Summary: {processor_gate_fixture_or_test_policy_summary_text}"
            )
        processor_gate_tuning_recommendations = (
            [str(item).strip() for item in processor_gate_threshold_decision.get("tuning_recommendations", []) if str(item).strip()]
            if isinstance(processor_gate_threshold_decision.get("tuning_recommendations"), list)
            else []
        )
        if processor_gate_tuning_recommendations:
            console.print(f"     Tuning: {' | '.join(processor_gate_tuning_recommendations)}")
        processor_gate_threshold_parts: list[str] = []
        high_threshold = _coerce_optional_float(processor_gate_threshold_inputs.get("high_threshold"))
        low_threshold = _coerce_optional_float(processor_gate_threshold_inputs.get("low_threshold"))
        drift_warn_threshold = _coerce_optional_float(
            processor_gate_threshold_inputs.get("drift_warn_threshold")
        )
        min_candidate_rows = _coerce_optional_int(
            processor_gate_threshold_inputs.get("min_candidate_rows")
        )
        if high_threshold is not None:
            processor_gate_threshold_parts.append(f"high={high_threshold:.2f}")
        if low_threshold is not None:
            processor_gate_threshold_parts.append(f"low={low_threshold:.2f}")
        if drift_warn_threshold is not None:
            processor_gate_threshold_parts.append(f"warn={drift_warn_threshold:.1%}")
        if min_candidate_rows is not None:
            processor_gate_threshold_parts.append(f"sample>={min_candidate_rows}")
        if processor_gate_threshold_parts:
            console.print(f"     Thresholds: {', '.join(processor_gate_threshold_parts)}")
        processor_gate_coverage_parts: list[str] = []
        candidate_count = _coerce_optional_int(processor_gate_threshold_signals.get("candidate_count"))
        promotable_count = _coerce_optional_int(processor_gate_threshold_signals.get("promotable_count"))
        drift_count = _coerce_optional_int(processor_gate_threshold_signals.get("drift_count"))
        drift_rate_text = _format_percentage_text(processor_gate_threshold_signals.get("drift_rate"))
        if candidate_count is not None:
            processor_gate_coverage_parts.append(f"candidates={candidate_count}")
        if promotable_count is not None:
            processor_gate_coverage_parts.append(f"promotable={promotable_count}")
        if drift_count is not None:
            processor_gate_coverage_parts.append(f"drift={drift_count}")
        if drift_rate_text is not None:
            processor_gate_coverage_parts.append(f"rate={drift_rate_text}")
        if processor_gate_coverage_parts:
            console.print(f"     Coverage: {', '.join(processor_gate_coverage_parts)}")
        processor_gate_decision_transitions = processor_gate_threshold_signals.get(
            "decision_transition_counts"
        )
        if isinstance(processor_gate_decision_transitions, dict) and processor_gate_decision_transitions:
            top_transitions = sorted(
                processor_gate_decision_transitions.items(),
                key=lambda item: (-int(item[1] or 0), str(item[0])),
            )[:3]
            console.print(
                "     Transitions: "
                + ", ".join(f"{key}={int(value or 0)}" for key, value in top_transitions)
            )
        processor_gate_probable_causes = processor_gate_threshold_signals.get(
            "probable_drift_cause_counts"
        )
        if isinstance(processor_gate_probable_causes, dict) and processor_gate_probable_causes:
            top_causes = sorted(
                processor_gate_probable_causes.items(),
                key=lambda item: (-int(item[1] or 0), str(item[0])),
            )[:4]
            console.print(
                "     Causes: "
                + ", ".join(f"{key}={int(value or 0)}" for key, value in top_causes)
            )
        processor_gate_reason = str(
            processor_gate_threshold_decision.get("decision_reason") or ""
        ).strip()
        if processor_gate_reason:
            console.print(f"     Reason: {processor_gate_reason}")
    latest_slot_tuning_review = latest_slot_classification_tuning_review_run()
    latest_slot_tuning_review_path = (
        str(latest_slot_tuning_review / "summary.json")
        if latest_slot_tuning_review is not None
        else None
    )
    latest_slot_tuning_review_markdown_path = (
        str(latest_slot_tuning_review / "audit.md")
        if latest_slot_tuning_review is not None and (latest_slot_tuning_review / "audit.md").exists()
        else None
    )
    if latest_slot_tuning_review is None:
        console.print(
            "   - Latest Slot Classification Tuning Review: none found "
            f"({default_slot_classification_tuning_review_root()})"
        )
    else:
        console.print(
            f"   - Latest Slot Classification Tuning Review: "
            f"{latest_slot_tuning_review.name}"
        )
        console.print(f"     Path: {latest_slot_tuning_review_path}")
        if latest_slot_tuning_review_markdown_path:
            console.print(f"     Markdown: {latest_slot_tuning_review_markdown_path}")
        try:
            slot_tuning_review_summary = load_slot_classification_tuning_review_summary(
                latest_slot_tuning_review
            )
        except Exception as exc:
            console.print(f"     Summary: unavailable ({exc})")
            slot_tuning_review_summary = {}
        slot_tuning_review_decision = (
            slot_tuning_review_summary.get("decision")
            if isinstance(slot_tuning_review_summary.get("decision"), dict)
            else {}
        )
        slot_tuning_review_signals = (
            slot_tuning_review_summary.get("signal_summary")
            if isinstance(slot_tuning_review_summary.get("signal_summary"), dict)
            else {}
        )
        slot_tuning_review_decision_parts: list[str] = []
        slot_tuning_review_action = str(
            slot_tuning_review_decision.get("recommended_action") or ""
        ).strip()
        slot_tuning_review_next_step = str(
            slot_tuning_review_decision.get("next_step") or ""
        ).strip()
        slot_tuning_review_latest_compare = str(
            slot_tuning_review_decision.get("latest_compare_run_id") or ""
        ).strip()
        if slot_tuning_review_action:
            slot_tuning_review_decision_parts.append(f"action={slot_tuning_review_action}")
        slot_tuning_review_decision_parts.append(
            "review_ready=yes"
            if bool(slot_tuning_review_decision.get("review_ready"))
            else "review_ready=no"
        )
        if slot_tuning_review_next_step:
            slot_tuning_review_decision_parts.append(f"next={slot_tuning_review_next_step}")
        if slot_tuning_review_latest_compare:
            slot_tuning_review_decision_parts.append(
                f"compare={slot_tuning_review_latest_compare}"
            )
        if slot_tuning_review_decision_parts:
            console.print(f"     Decision: {', '.join(slot_tuning_review_decision_parts)}")
        slot_tuning_review_compare_status = str(
            slot_tuning_review_decision.get("paired_compare_status") or ""
        ).strip()
        if slot_tuning_review_compare_status:
            console.print(f"     Compare: {slot_tuning_review_compare_status}")
        slot_tuning_review_rerun_parts: list[str] = []
        default_rerun_status = str(
            slot_tuning_review_decision.get("default_rerun_status") or ""
        ).strip()
        boundary_rerun_status = str(
            slot_tuning_review_decision.get("boundary_rerun_status") or ""
        ).strip()
        if default_rerun_status:
            slot_tuning_review_rerun_parts.append(f"default={default_rerun_status}")
        if boundary_rerun_status:
            slot_tuning_review_rerun_parts.append(f"boundary={boundary_rerun_status}")
        if slot_tuning_review_rerun_parts:
            console.print(f"     Reruns: {', '.join(slot_tuning_review_rerun_parts)}")
        slot_tuning_review_prompt_parts: list[str] = []
        if "prompt_change_ready" in slot_tuning_review_decision:
            slot_tuning_review_prompt_parts.append(
                "ready=yes"
                if bool(slot_tuning_review_decision.get("prompt_change_ready"))
                else "ready=no"
            )
        slot_tuning_review_prompt_status = str(
            slot_tuning_review_decision.get("prompt_change_status") or ""
        ).strip()
        if slot_tuning_review_prompt_status:
            slot_tuning_review_prompt_parts.append(f"status={slot_tuning_review_prompt_status}")
        if slot_tuning_review_prompt_parts:
            console.print(f"     Prompt Change: {', '.join(slot_tuning_review_prompt_parts)}")
        slot_tuning_review_prompt_blocker = str(
            slot_tuning_review_decision.get("prompt_change_blocker") or ""
        ).strip()
        if slot_tuning_review_prompt_blocker:
            console.print(f"     Prompt Blocker: {slot_tuning_review_prompt_blocker}")
        slot_tuning_review_targets = (
            [
                str(item).strip()
                for item in slot_tuning_review_decision.get("tuning_targets", [])
                if str(item).strip()
            ]
            if isinstance(slot_tuning_review_decision.get("tuning_targets"), list)
            else []
        )
        if slot_tuning_review_targets:
            console.print(f"     Targets: {', '.join(slot_tuning_review_targets)}")
        slot_tuning_review_actions = (
            [
                {
                    "target": str(item.get("target") or "").strip(),
                    "action": str(item.get("action") or "").strip(),
                }
                for item in slot_tuning_review_decision.get("tuning_actions", [])
                if isinstance(item, dict)
                and str(item.get("target") or "").strip()
                and str(item.get("action") or "").strip()
            ]
            if isinstance(slot_tuning_review_decision.get("tuning_actions"), list)
            else []
        )
        if slot_tuning_review_actions:
            console.print(
                "     Actions: "
                + " | ".join(
                    f"{item['target']}:{item['action']}" for item in slot_tuning_review_actions
                )
            )
        slot_tuning_review_action_plan = (
            [
                {
                    "order": int(item.get("order") or 0),
                    "action": str(item.get("action") or "").strip(),
                    "target": str(item.get("target") or "").strip(),
                    "evidence": str(item.get("evidence") or "").strip(),
                }
                for item in slot_tuning_review_decision.get("action_plan", [])
                if isinstance(item, dict)
                and int(item.get("order") or 0) > 0
                and str(item.get("action") or "").strip()
            ]
            if isinstance(slot_tuning_review_decision.get("action_plan"), list)
            else []
        )
        if slot_tuning_review_action_plan:
            console.print(
                "     Plan: "
                + " | ".join(
                    f"{item['order']}.{item['action']}"
                    + (f"->{item['target']}" if item["target"] else "")
                    for item in slot_tuning_review_action_plan
                )
            )
            if any(item["evidence"] for item in slot_tuning_review_action_plan):
                console.print(
                    "     Plan Why: "
                    + " | ".join(
                        f"{item['order']}.{item['evidence']}"
                        for item in slot_tuning_review_action_plan
                        if item["evidence"]
                    )
                )
        slot_tuning_review_signal_parts: list[str] = []
        paired_compare_failed_checks = (
            [
                str(item).strip()
                for item in slot_tuning_review_signals.get("paired_compare_failed_checks", [])
                if str(item).strip()
            ]
            if isinstance(slot_tuning_review_signals.get("paired_compare_failed_checks"), list)
            else []
        )
        paired_compare_regressions = (
            [
                str(item).strip()
                for item in slot_tuning_review_signals.get("paired_compare_regressions", [])
                if str(item).strip()
            ]
            if isinstance(slot_tuning_review_signals.get("paired_compare_regressions"), list)
            else []
        )
        if paired_compare_failed_checks:
            slot_tuning_review_signal_parts.append(
                "compare.failed=" + ",".join(paired_compare_failed_checks)
            )
        if paired_compare_regressions:
            slot_tuning_review_signal_parts.append(
                "compare.regressions=" + ",".join(paired_compare_regressions)
            )
        if "paired_compare_error_migration_detected" in slot_tuning_review_signals:
            slot_tuning_review_signal_parts.append(
                "compare.migration="
                + (
                    "yes"
                    if bool(slot_tuning_review_signals.get("paired_compare_error_migration_detected"))
                    else "no"
                )
            )
        default_rerun_drift_count = _coerce_optional_int(
            slot_tuning_review_signals.get("default_rerun_drift_count")
        )
        boundary_rerun_drift_count = _coerce_optional_int(
            slot_tuning_review_signals.get("boundary_rerun_drift_count")
        )
        default_rerun_drift_rate = _format_percentage_text(
            slot_tuning_review_signals.get("default_rerun_drift_rate")
        )
        boundary_rerun_drift_rate = _format_percentage_text(
            slot_tuning_review_signals.get("boundary_rerun_drift_rate")
        )
        if default_rerun_drift_count is not None or default_rerun_drift_rate is not None:
            default_signal = "default="
            signal_parts: list[str] = []
            if default_rerun_drift_count is not None:
                signal_parts.append(str(default_rerun_drift_count))
            if default_rerun_drift_rate is not None:
                signal_parts.append(default_rerun_drift_rate)
            default_signal += "/".join(signal_parts)
            slot_tuning_review_signal_parts.append(default_signal)
        if boundary_rerun_drift_count is not None or boundary_rerun_drift_rate is not None:
            boundary_signal = "boundary="
            signal_parts = []
            if boundary_rerun_drift_count is not None:
                signal_parts.append(str(boundary_rerun_drift_count))
            if boundary_rerun_drift_rate is not None:
                signal_parts.append(boundary_rerun_drift_rate)
            boundary_signal += "/".join(signal_parts)
            slot_tuning_review_signal_parts.append(boundary_signal)
        if slot_tuning_review_signal_parts:
            console.print(f"     Signals: {', '.join(slot_tuning_review_signal_parts)}")
        slot_tuning_review_recommendations = (
            [
                str(item).strip()
                for item in slot_tuning_review_decision.get("tuning_recommendations", [])
                if str(item).strip()
            ]
            if isinstance(slot_tuning_review_decision.get("tuning_recommendations"), list)
            else []
        )
        if slot_tuning_review_recommendations:
            console.print(f"     Tuning: {' | '.join(slot_tuning_review_recommendations)}")
        slot_tuning_review_reason = str(
            slot_tuning_review_decision.get("decision_reason") or ""
        ).strip()
        if slot_tuning_review_reason:
            console.print(f"     Reason: {slot_tuning_review_reason}")
    if readiness.status == "ok":
        console.print("[bold green]All systems go![/bold green]")
    elif readiness.status == "degraded":
        console.print("[bold yellow]Runtime is usable, but there are warnings to clean up.[/bold yellow]")
    else:
        console.print("[bold red]Runtime needs fixes before you should trust it.[/bold red]")
    logger.info("Doctor check completed with status=%s.", readiness.status)


@app.command("self-test")
def self_test(json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output.")):
    """Run a narrow installability-focused runtime readiness check."""
    readiness = collect_runtime_readiness()

    if json_output:
        _emit_json(readiness.model_dump())
    else:
        console.print("[bold blue]🧪 Runtime self-test[/bold blue]")
        for check in readiness.checks:
            icon = "✅" if check.status == "ok" else "⚠️" if check.status == "warn" else "❌"
            console.print(f"{icon} {check.name}: {check.detail}")
            if check.path:
                console.print(f"   - Path: {check.path}")
        console.print(f"Overall: [bold]{readiness.status}[/bold]")

    if readiness.status == "error":
        raise typer.Exit(code=1)


@app.command("quarantine-fixture-states")
def quarantine_fixture_states(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Actually move hidden fixture structured states into a quarantine folder.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Quarantine hidden fixture structured states from the configured vault."""
    config = load_config()
    moves = quarantine_hidden_fixture_structured_states(
        config.paths.obsidian_vault,
        apply=apply,
    )
    payload = {
        "vault_path": str(Path(config.paths.obsidian_vault).expanduser().resolve(strict=False)),
        "apply": bool(apply),
        "found": len(moves),
        "moves": [
            {
                "source_path": str(move.source_path),
                "destination_path": str(move.destination_path),
            }
            for move in moves
        ],
    }

    if json_output:
        _emit_json(payload)
        return

    console.print("[bold blue]🧹 Hidden Fixture State Cleanup[/bold blue]")
    if not moves:
        console.print("No hidden fixture structured states found.")
        return

    console.print(f"Found {len(moves)} hidden fixture structured state(s).")
    for move in moves:
        verb = "Moved" if apply else "Would move"
        console.print(f" - {verb}: {move.source_path} -> {move.destination_path}")

    if not apply:
        console.print("[yellow]Dry run only. Re-run with `--apply` to quarantine these files.[/yellow]")


@app.command("archive-fixture-no-feedback-papers")
def archive_fixture_no_feedback_papers(
    db: Path = typer.Option(
        Path(DB_UTILS_PATH),
        "--db",
        help="SQLite DB path to inspect and clean.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Actually archive+delete fixture rows with empty feedback_json.",
    ),
    sample: int = typer.Option(
        20,
        "--sample",
        min=0,
        help="Number of candidate rows to show in text output.",
    ),
    max_count: int = typer.Option(
        0,
        "--max-count",
        min=0,
        help="Limit candidates to archive (0 = all).",
    ),
    backup_path: Path | None = typer.Option(
        None,
        "--backup-path",
        help="Optional backup file path. Auto-generated when omitted under --apply.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Archive fixture-only paper rows that still have empty feedback_json."""
    db_path = Path(db).expanduser()
    if not db_path.exists():
        console.print(f"[bold red]❌ DB not found:[/bold red] {db_path}")
        raise typer.Exit(code=1)

    conn = sqlite3.connect(db_path)
    try:
        candidates = select_fixture_paper_archive_candidates(conn)
        if max_count and max_count > 0:
            candidates = candidates[:max_count]

        by_fixture_reason: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for candidate in candidates:
            by_fixture_reason[candidate.fixture_reason] = by_fixture_reason.get(candidate.fixture_reason, 0) + 1
            status = candidate.status or "unknown"
            by_status[status] = by_status.get(status, 0) + 1

        resolved_backup_path: Path | None = None
        archived_count = 0
        if apply:
            resolved_backup_path = (
                Path(backup_path).expanduser()
                if backup_path is not None
                else default_fixture_paper_archive_backup_path(db_path)
            )
            backup_fixture_paper_archive_db(db_path, resolved_backup_path)
            archived_count = apply_fixture_paper_archive(conn, candidates)

        payload = {
            "db_path": str(db_path),
            "apply": bool(apply),
            "sample": int(sample),
            "max_count": int(max_count),
            "candidate_count": len(candidates),
            "archived_count": archived_count,
            "backup_path": str(resolved_backup_path) if resolved_backup_path is not None else None,
            "by_fixture_reason": by_fixture_reason,
            "by_status": by_status,
            "candidates": [
                {
                    "paper_id": candidate.paper_id,
                    "title": candidate.title,
                    "status": candidate.status,
                    "fixture_reason": candidate.fixture_reason,
                    "archive_reason": candidate.archive_reason,
                }
                for candidate in candidates
            ],
        }
    finally:
        conn.close()

    if json_output:
        _emit_json(payload)
        return

    console.print("[bold blue]🧹 Fixture Paper Cleanup[/bold blue]")
    if not candidates:
        console.print("No fixture paper rows with empty feedback_json found.")
        return

    console.print(f"Found {len(candidates)} fixture paper candidate(s).")
    for candidate in candidates[:sample]:
        verb = "Archived" if apply else "Would archive"
        console.print(
            f" - {verb}: {candidate.paper_id} | {candidate.status or '-'} | "
            f"{candidate.fixture_reason} | {candidate.title or '-'}"
        )

    if by_fixture_reason:
        console.print(f"By fixture reason: {by_fixture_reason}")
    if by_status:
        console.print(f"By status: {by_status}")

    if apply:
        if resolved_backup_path is not None:
            console.print(f"Backup: {resolved_backup_path}")
        console.print(f"Archived {archived_count} fixture paper row(s).")
        return

    console.print("[yellow]Dry run only. Re-run with `--apply` to archive these rows.[/yellow]")


@app.command("archive-meeting-pack-noise")
def archive_meeting_pack_noise(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Actually move low-value Meeting Pack directories into a quarantine folder.",
    ),
    keep_latest: int = typer.Option(
        3,
        "--keep-latest",
        min=1,
        help="Keep this many newest healthy packs per selector/mode before archiving older duplicates.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Archive low-value Meeting Pack storage noise from the runtime root."""
    config = load_config()
    root = default_meeting_packs_root()
    archive_root = default_meeting_pack_archive_root(root)
    candidates = select_meeting_pack_archive_candidates(
        root,
        vault_path=config.paths.obsidian_vault,
        keep_latest=keep_latest,
    )
    payload = {
        "root": str(root),
        "archive_root": str(archive_root),
        "apply": bool(apply),
        "keep_latest": int(keep_latest),
        "candidate_count": len(candidates),
        "candidates": [
            {
                "pack_id": candidate.pack_id,
                "reason": candidate.reason,
                "selector_key": candidate.selector_key,
                "title": candidate.title,
                "source_dir": str(candidate.source_dir),
                "destination_dir": str(candidate.destination_dir),
            }
            for candidate in candidates
        ],
    }

    if apply:
        archived = apply_meeting_pack_archive(candidates, archive_root=archive_root)
        payload["archived"] = archived

    if json_output:
        _emit_json(payload)
        return

    console.print("[bold blue]🧹 Meeting Pack Noise Cleanup[/bold blue]")
    console.print(f"Root: {root}")
    console.print(f"Archive root: {archive_root}")
    if not candidates:
        console.print("No Meeting Pack archive candidates found.")
        return

    console.print(f"Found {len(candidates)} Meeting Pack archive candidate(s).")
    for candidate in candidates:
        verb = "Moved" if apply else "Would move"
        console.print(f" - {verb}: {candidate.pack_id} [{candidate.reason}]")

    if apply:
        console.print(f"[green]Archived {payload['archived']} Meeting Pack directories.[/green]")
    else:
        console.print("[yellow]Dry run only. Re-run with `--apply` to archive these packs.[/yellow]")


@app.command()
def start(
    host: str = typer.Option("127.0.0.1", "--host", help="Backend bind host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Backend bind port"),
    ui_url: str = typer.Option("", "--ui-url", help="UI URL to open. Empty means /ui."),
    health_timeout: int = typer.Option(15, "--health-timeout", min=3, max=120, help="Healthcheck timeout in seconds."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not auto-open browser."),
    worker: bool = typer.Option(True, "--worker/--no-worker", help="Start the background job worker."),
):
    """
    Start local runtime services and open Lattice UI/docs.
    """
    console.print("[bold green]🚀 Starting Lattice runtime...[/bold green]")

    try:
        load_config()
        db_path = bootstrap_database()
        console.print("   - Preflight config: ✅")
        console.print(f"   - Runtime DB: ✅ ({db_path})")
    except Exception as exc:
        console.print(f"[bold red]❌ Preflight failed: {exc}[/bold red]")
        raise typer.Exit(code=1)

    if not _is_port_available(host, port):
        console.print(f"[bold red]❌ Port already in use: {host}:{port}[/bold red]")
        console.print("   Try another port: --port 8001")
        raise typer.Exit(code=1)

    readiness = collect_runtime_readiness()
    backend_check = next((check for check in readiness.checks if check.name == "backend_entrypoint"), None)
    if backend_check and backend_check.status == "error":
        console.print(f"[bold red]❌ Backend preflight failed: {backend_check.detail}[/bold red]")
        console.print(f"[yellow]   Suggested fix: {sys.executable} -m pip install -r requirements.txt[/yellow]")
        raise typer.Exit(code=1)

    cmd = _build_backend_launch_command(host, port)
    worker_proc = None

    try:
        proc = subprocess.Popen(cmd)
    except Exception as exc:
        console.print(f"[bold red]❌ Failed to start backend: {exc}[/bold red]")
        raise typer.Exit(code=1)

    base_url = f"http://{host}:{port}"
    if not _wait_for_health(base_url, health_timeout):
        _terminate_process(proc)
        console.print(
            f"[bold red]❌ Healthcheck timeout after {health_timeout}s: {base_url}/health[/bold red]"
        )
        raise typer.Exit(code=1)

    entry_url = ui_url.strip() or f"{base_url}/ui"
    console.print(f"   - Backend: ✅ {base_url}")
    console.print(f"   - Entry: {entry_url}")

    if worker:
        worker_cmd = _build_worker_launch_command()
        try:
            worker_proc = subprocess.Popen(worker_cmd)
        except Exception as exc:
            _terminate_process(proc)
            console.print(f"[bold red]❌ Failed to start worker: {exc}[/bold red]")
            raise typer.Exit(code=1)
        console.print("   - Worker: ✅ started")
    else:
        console.print("   - Worker: ⚪ disabled (--no-worker)")

    if not no_open:
        try:
            webbrowser.open(entry_url, new=2)
        except Exception as exc:
            console.print(f"[yellow]⚠️ Failed to open browser automatically: {exc}[/yellow]")

    console.print("   (Press Ctrl+C to stop)")

    try:
        while True:
            backend_code = proc.poll()
            worker_code = worker_proc.poll() if worker_proc is not None else None
            if backend_code is None and worker_code is None:
                time.sleep(0.5)
                continue
            if backend_code is not None:
                if backend_code == 0:
                    console.print("[yellow]⚠️ Backend exited.[/yellow]")
                    raise typer.Exit(code=0)
                console.print(f"[bold red]❌ Backend exited with code {backend_code}[/bold red]")
                raise typer.Exit(code=backend_code)
            if worker_code is not None:
                console.print(f"[bold red]❌ Worker exited with code {worker_code}[/bold red]")
                raise typer.Exit(code=worker_code or 1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Stopping Lattice runtime...[/bold yellow]")
    finally:
        _terminate_process(proc)
        if worker_proc is not None:
            _terminate_process(worker_proc)


@app.command("serve-backend", hidden=True)
def serve_backend(
    host: str = typer.Option("127.0.0.1", "--host", help="Backend bind host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Backend bind port"),
):
    """Internal packaged-runtime backend launcher."""
    import uvicorn
    from backend.main import app as backend_app

    uvicorn.run(backend_app, host=host, port=port)


@app.command("serve-worker", hidden=True)
def serve_worker():
    """Internal packaged-runtime worker launcher."""
    from src.jobs.worker import Worker

    Worker().start()


# 2. Simple Fetch Test
@app.command()
def test_fetch():
    """Test Fetch (Provider Pattern)"""
    from src.fetch import get_fetchers
    
    config = load_config()
    keywords = [config.search.slots['mechanism'].query] # Keep it as list for logging, but fetch takes str
    query_str = keywords[0] # Simple test
    
    console.print(f"[bold cyan]🔍 Testing fetch with query: {query_str}[/bold cyan]")
    
    fetchers = get_fetchers(config)
    console.print(f"Loaded Fetchers: {[f.source_name for f in fetchers]}")
    
    for fetcher in fetchers:
        console.print(f"\n[bold]Testing {fetcher.source_name}...[/bold]")
        try:
            papers = fetcher.fetch(query_str, max_results=3)
            for p in papers:
                 console.print(f" - [{fetcher.source_name}] {p.title} ({p.published})")
        except Exception as e:
            console.print(f"[red]Error fetching from {fetcher.source_name}: {e}[/red]")

            console.print(f"[red]Error fetching from {fetcher.source_name}: {e}[/red]")

# 2.5 On-Demand Fetch
@app.command()
def fetch(
    query: str = typer.Option(..., "--query", "-q", help="Search query (e.g. 'CRISPR off-target')"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results per source"),
    save: bool = typer.Option(False, "--save", "-s", help="Save results to Obsidian/Database (Default: Dry Run)"),
):
    """[On-Demand] Search papers immediately. Default is Dry-Run (list only)."""
    from src.processor import process_on_demand_search
    
    console.print(f"[bold cyan]🚀 Fetching papers for: '{query}'[/bold cyan]")
    if save:
        console.print("[bold yellow]💾 Save Mode: ON (Will download & create notes)[/bold yellow]")
    else:
        console.print("[bold green]👀 Dry-Run Mode: List only[/bold green]")
        
    results = process_on_demand_search(query, limit, dry_run=not save)
    
    if not results:
        console.print("[bold red]❌ No results found.[/bold red]")
        return
        
    console.print(f"\n[bold]✅ Found {len(results)} papers:[/bold]")
    for idx, item in enumerate(results, 1):
        # Result can be Paper object (dry-run) or Dict (saved)
        if isinstance(item, dict):
             title = item.get('title', 'No Title')
             date = item.get('published', 'Unknown')
             source = item.get('source', 'Unknown')
             link = item.get('doi') or item.get('link')
             score_val = item.get('manual_rank_score')
        else:
             # Paper object
             title = item.title
             date = item.published
             source = item.source
             link = item.id
             score_val = item.manual_rank_score
             
        score_str = f" [bold magenta](Score: {score_val:.2f})[/bold magenta]" if score_val else ""
        console.print(f"{idx}. [{source}] {title} ({date}){score_str} - {link}")
    
    if save and results:
        console.print(f"\n[bold blue]✨ Saved {len(results)} papers to 'Inbox/OnDemand'[/bold blue]")

# 3. Process Test
# 3. Process Test
@app.command()
def process_test(force: bool = False):
    """Test Full Pipeline (Fetch -> Classify -> Tag). Use --force to ignore DB."""
    from src.processor import process_daily_slots
    
    if force:
        console.print("[bold yellow]⚠️ Running in FORCE mode: Ignoring DB duplicates.[/bold yellow]")
    
    results = process_daily_slots(ignore_db=force)
    _print_results(results)

@app.command()
def run():
    """[Production] Run Daily PaperPipe Routine."""
    from src.processor import process_daily_slots
    from src.reporting import generate_daily_report # [NEW]
    from src.config import load_config
    
    console.print("[bold green]🚀 Starting Production Run...[/bold green]")
    try:
        bootstrap_database()
    except Exception as exc:
        console.print(f"[bold red]❌ Failed to initialize runtime DB: {exc}[/bold red]")
        raise typer.Exit(code=1)
    config = load_config()
    run_id, _started_at = _start_legacy_cli_run_tracking(config=config)
    target_date = datetime.now().strftime("%Y-%m-%d")
    try:
        record_run_status(target_date, "RUNNING", processed_count=0)
    except Exception as exc:
        logger.warning("Failed to mirror legacy run status at start: %s", exc)

    try:
        results = process_daily_slots(ignore_db=False)
        report_path = None

        # [NEW] Generate SLA Report
        if results:
            report_path = generate_daily_report(results, config)
            if report_path:
                console.print(f"[bold blue]📊 SLA Report generated: {report_path}[/bold blue]")

        _finish_legacy_cli_run_tracking(
            run_id,
            status="completed",
            metrics=_build_legacy_run_metrics(results=results, config=config, report_path=report_path),
        )
        try:
            record_run_status(target_date, "SUCCESS", processed_count=len(results))
        except Exception as exc:
            logger.warning("Failed to mirror legacy run status on success: %s", exc)
        _print_results(results)
    except Exception as exc:
        _finish_legacy_cli_run_tracking(
            run_id,
            status="failed",
            metrics={"error": str(exc)},
        )
        try:
            record_run_status(target_date, "FAILED", processed_count=0)
        except Exception as mirror_exc:
            logger.warning("Failed to mirror legacy run status on failure: %s", mirror_exc)
        raise

def _print_results(results):
    console.print("\n[bold green]📊 Daily Slot Report[/bold green]")
    
    if not results:
        console.print("[bold red]❌ No papers selected.[/bold red]")
        return

    for p in results:
        icon = "🏥" if p.get('trial_data') or p.get('clinical_data') or str(p.get('slot', '')).lower() == 'clinical' else "📝"
        console.print(f"\n{icon} [{p['slot']}] {p['title']}")
        
        one_liner = p.get('ai_one_liner') or "⚠️ No AI Summary (Fallback)"
        console.print(f"   💡 One-Liner: {one_liner}")

        selection_text = _selection_summary_text(p)
        if selection_text:
            console.print(f"   🎯 Selection: {selection_text}")

        clinical_payload = p.get('trial_data') or p.get('clinical_data')
        if clinical_payload:
            console.print("   💊 [bold cyan]Clinical Data Extracted:[/bold cyan]")
            for key, val in clinical_payload.items():
                console.print(f"      - {key}: {val}")


# 4. Filter Test
@app.command()
def test_filter():
    """Test Title Filter Logic"""
    test_titles = [
        "Basic Science and Pathogenesis.",
        "Drug Development.",
        "Clinical Manifestations.",
        "Chapter 1: Introduction",
        "Section 5. Results",
        "Valid Paper Title About Neuroscience",
        "A very long title that should pass even if it ends with.",
        "Short title without dot"
    ]
    
    console.print("[bold]🧪 Testing Junk Title Filter Logic...[/bold]")
    
    for title in test_titles:
        title_clean = title.strip()
        word_count = len(title_clean.split())
        
        is_junk_short = (word_count <= 4 and title_clean.endswith('.'))
        junk_keywords = ["Chapter", "Section", "Part", "Index", "Preface", "Table of Contents"]
        is_junk_keyword = (word_count <= 5 and any(k in title_clean for k in junk_keywords))
        
        if is_junk_short:
            console.print(f"❌ [red]FILTERED (Short)[/red]: '{title}'")
        elif is_junk_keyword:
            console.print(f"❌ [red]FILTERED (Keyword)[/red]: '{title}'")
        else:
            console.print(f"✅ [green]PASSED[/green]: '{title}'")

@app.command()
def clear_logs():
    """Clear log file"""
    log_path = logs_root() / "paperpipe.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    open(log_path, "w").close()
    console.print("✅ Logs cleared.")


@app.command()
def reconcile(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply updates. Default is dry-run (no DB writes).",
    )
):
    """
    Reconcile paper statuses from approved decisions.
    """
    from src.db_utils import reconcile_approved_decisions

    dry_run = not apply
    result = reconcile_approved_decisions(dry_run=dry_run)

    mode = "DRY-RUN" if dry_run else "APPLY"
    console.print(f"[bold cyan]🔧 Reconcile Mode: {mode}[/bold cyan]")
    console.print(f"   - Candidates: {result['candidate_count']}")
    console.print(f"   - Updated: {result['updated_count']}")

    if not result["candidates"]:
        console.print("[green]✅ No reconciliation needed.[/green]")
        return

    for item in result["candidates"]:
        console.print(
            f" - {item['paper_id']}: {item['old_status']} -> APPROVED "
            f"(source={item['source']})"
        )

    if dry_run:
        console.print("[yellow]ℹ️ Re-run with --apply to persist changes.[/yellow]")

@app.command()
def reset():
    """[DANGER] Reset DB, Logs, and Obsidian Data."""
    if not typer.confirm("⚠️  Are you sure you want to delete ALL data?"):
        console.print("❌ Cancelled.")
        raise typer.Abort()

    console.print("[bold red]🗑️  Resetting all data...[/bold red]")

    # 1. DB
    db_paths = [DB_UTILS_PATH, Path("state.db")]
    seen = set()
    for db_path in db_paths:
        db_path = Path(db_path)
        if str(db_path) in seen:
            continue
        seen.add(str(db_path))
        if db_path.exists():
            db_path.unlink()
            console.print(f"   - Deleted {db_path}")
    
    # 2. Logs
    log_path = logs_root() / "paperpipe.log"
    if log_path.exists():
        open(log_path, "w").close()
        console.print("   - Cleared logs")

    # 3. Obsidian
    try:
        config = load_config()
        vault_path = config.paths.obsidian_vault
        
        inbox_path = vault_path / "Inbox"
        if inbox_path.exists():
            shutil.rmtree(inbox_path)
            console.print(f"   - Deleted {inbox_path}")
            
        index_all = vault_path / config.paths.index_all
        if index_all.exists():
            index_all.unlink()
            console.print(f"   - Deleted {index_all}")
            
        index_clinical = vault_path / config.paths.index_clinical
        if index_clinical.exists():
            index_clinical.unlink()
            console.print(f"   - Deleted {index_clinical}")

    except Exception as e:
        console.print(f"   ⚠️  Failed to clean Obsidian vault: {e}")

    # 4. Re-init
    db_path = bootstrap_database()
    console.print(f"✅ Reset complete. System is clean. ({db_path})")

@app.command()
def test_unpaywall(doi: str = "10.1038/s41586-020-2165-8"):
    """Test Unpaywall API link fetching"""
    from src.downloader import _fetch_oa_link
    config = load_config()
    
    console.print(f"[bold cyan]🔍 Testing Unpaywall for DOI: {doi}[/bold cyan]")
    email = config.system.unpaywall_email
    console.print(f"   - Email: {email}")
    
    link = _fetch_oa_link(doi, email)
    if link:
        console.print(f"✅ Found OA Link: {link}")
    else:
        console.print("❌ No OA Link found (or API error).")

# 6. Watch Folder Service
@app.command()
def watch():
    """Start Watch Folder Service for auto-processing local PDFs."""
    _ensure_watchdog_available("watch")
    from src.watcher import WatcherService
    import src.watcher as watcher_module

    config = load_config()
    try:
        bootstrap_database()
    except Exception as exc:
        console.print(f"[bold red]❌ Failed to initialize runtime DB: {exc}[/bold red]")
        raise typer.Exit(code=1)
    conflicts = _watch_output_conflicts(config)
    if conflicts:
        conflict_text = ", ".join(f"{label}={path}" for label, path in conflicts)
        console.print(
            "[bold red]❌ Watch folder conflicts with managed output paths.[/bold red] "
            f"Adjust `watch_folder` so it does not overlap with {conflict_text}."
        )
        raise typer.Exit(code=1)
    
    console.print(f"[bold green]👀 Starting Watcher Service...[/bold green]")
    console.print(f"   - Folder: {config.paths.watch_folder}")
    console.print("   (Press Ctrl+C to stop)")
    
    service = WatcherService(config)
    try:
        service.start(watcher_module)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Watcher stopped by user.[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Watcher Error: {e}[/bold red]")


@app.command()
def watch_downloads():
    """Watch Downloads folder and auto-match manual-required PDFs into storage."""
    _ensure_watchdog_available("watch-downloads")
    from src.downloads_watcher import DownloadsWatcherService

    config = load_config()
    try:
        bootstrap_database()
    except Exception as exc:
        console.print(f"[bold red]❌ Failed to initialize runtime DB: {exc}[/bold red]")
        raise typer.Exit(code=1)
    conflicts = _downloads_watch_output_conflicts(config)
    if conflicts:
        conflict_text = ", ".join(f"{label}={path}" for label, path in conflicts)
        console.print(
            "[bold red]❌ Downloads watch folder conflicts with managed output paths.[/bold red] "
            f"Adjust `downloads_watch_dir` so it does not overlap with {conflict_text}."
        )
        raise typer.Exit(code=1)
    watch_dir = config.paths.downloads_watch_dir
    storage_dir = config.paths.pdf_storage_dir

    console.print("[bold green]👀 Starting Downloads Watcher...[/bold green]")
    console.print(f"   - Downloads Dir: {watch_dir}")
    console.print(f"   - PDF Storage Dir: {storage_dir}")
    console.print("   (Press Ctrl+C to stop)")

    service = DownloadsWatcherService(
        downloads_watch_dir=watch_dir,
        pdf_storage_dir=storage_dir,
        title_threshold=0.90,
    )
    try:
        service.start()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]🛑 Downloads watcher stopped by user.[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Downloads watcher error: {e}[/bold red]")

@app.command()
def organize(target_dir: str = "."):
    """
    Organize PDF files in a directory into the Library structure.
    Renames files to {Year}_{Author}_{ShortTitle}.pdf and moves them to Library/{Year}/.
    """
    import shutil
    import datetime
    from pathlib import Path
    from src.utils import create_paper_from_pdf, generate_filename
    from src.config import load_config
    
    config = load_config()
    target = Path(target_dir).expanduser()
    
    if not target.exists():
        console.print(f"[bold red]❌ Target directory not found: {target}[/bold red]")
        return
        
    pdfs = list(target.glob("*.pdf"))
    if not pdfs:
        console.print(f"[yellow]⚠️ No PDF files found in {target}[/yellow]")
        return
        
    console.print(f"[bold green]📦 Organizing {len(pdfs)} PDFs from: {target}[/bold green]")
    console.print(f"   -> Destination: {config.paths.library_dir}")
    
    success_count = 0
    fail_count = 0
    
    for pdf in pdfs:
        try:
            # 1. Create Paper (Extract Metadata)
            paper = create_paper_from_pdf(pdf)
            
            # 2. Generate Filename & Path
            new_name = generate_filename(paper)
            year = paper.published[:4] if paper.published and len(paper.published) >= 4 else "Unknown"
            
            year_dir = config.paths.library_dir / year
            year_dir.mkdir(parents=True, exist_ok=True)
            
            final_path = year_dir / new_name
            
            # Handle duplicates
            if final_path.exists() and final_path.resolve() != pdf.resolve():
                 # If same file content (size check for speed), skip?
                 # Better to just rename if unsure.
                 timestamp = datetime.datetime.now().strftime("%H%M%S")
                 final_path = year_dir / f"{final_path.stem}_{timestamp}{final_path.suffix}"
            
            if final_path.resolve() == pdf.resolve():
                console.print(f"   ⏭️  Already organized: {pdf.name}")
                continue
                
            shutil.move(pdf, final_path)
            console.print(f"   ✅ {pdf.name} -> {year}/{new_name}")
            success_count += 1
            
        except Exception as e:
            console.print(f"   ❌ Failed to organize {pdf.name}: {e}")
            fail_count += 1
            
    console.print(f"\n[bold]🎉 Done! Organized: {success_count}, Failed: {fail_count}[/bold]")

@app.command()
def stats():
    """
    Show statistics of papers in the library (Reading Status).
    Reads from All Indexes (Main, OnDemand, Manual).
    """
    import csv
    from collections import Counter
    from rich.table import Table
    from src.config import load_config
    
    config = load_config()
    vault_path = config.paths.obsidian_vault
    
    # Define potential indexes
    potential_indexes = [
        config.paths.index_all, # 00_Index/paper_collection.csv
        "00_Index/on_demand.csv",
        "00_Index/manual_collection.csv"
    ]
    
    status_counts = Counter()
    total = 0
    scanned_files = 0
    
    for relative_idx_path in potential_indexes:
        index_path = vault_path / relative_idx_path
        
        if not index_path.exists():
            continue
            
        scanned_files += 1
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    s = row.get('Status', 'Unknown').strip() or 'Unknown'
                    # Normalization
                    if s.lower() == 'to read': s = 'Inbox'
                    
                    status_counts[s] += 1
                    total += 1
        except Exception as e:
            console.print(f"[red]❌ Failed to read index {relative_idx_path}: {e}[/red]")

    if scanned_files == 0:
        console.print(f"[yellow]⚠️  No index files found in {vault_path}[/yellow]")
        return
        
    table = Table(title=f"📚 Library Stats (Total: {total})", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right", style="white")
    table.add_column("Percentage", justify="right", style="green")
    
    # Sort by predefined order
    order = ["Inbox", "Reading", "Done", "Unknown"]
    
    for s in order:
        if status_counts[s] > 0 or s in ["Inbox", "Reading", "Done"]: # Show zeros for main statuses
            count = status_counts[s]
            pct = (count / total * 100) if total > 0 else 0
            table.add_row(s, str(count), f"{pct:.1f}%")
            if s in status_counts: del status_counts[s]
            
    # Remaining
    for s, count in status_counts.items():
        pct = (count / total * 100) if total > 0 else 0
        table.add_row(s, str(count), f"{pct:.1f}%")
        
    console.print(table)


@app.command("show-intake-override-audit")
def show_intake_override_audit(
    run: Path = typer.Argument(..., help="Path to an intake override audit run directory or summary.json file."),
    limit: int = typer.Option(5, "--limit", min=0, help="Number of document rows to show per bucket."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Render a compact operator view of an intake override audit run."""
    from rich.table import Table

    summary_path = _resolve_audit_json_path(run, "summary.json")
    if not summary_path.exists():
        console.print(f"[bold red]❌ Audit summary not found:[/bold red] {summary_path}")
        raise typer.Exit(code=1)

    details_path = summary_path.parent / "details.json"
    summary = _load_json_dict(summary_path)
    details = _load_json_dict(details_path) if details_path.exists() else {}

    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), dict) else {}
    detail_docs = details.get("documents") if isinstance(details.get("documents"), list) else []
    docs_by_id = {
        str(doc.get("paper_id") or ""): doc
        for doc in detail_docs
        if isinstance(doc, dict) and str(doc.get("paper_id") or "")
    }

    payload = {
        "run_id": summary.get("run_id"),
        "summary_path": str(summary_path),
        "details_path": str(details_path) if details_path.exists() else None,
        "inputs": inputs,
        "metrics": metrics,
        "documents_with_slot_disagreement": summary.get("documents_with_slot_disagreement", []),
        "documents_with_missing_log": summary.get("documents_with_missing_log", []),
        "documents_with_invalid_log": summary.get("documents_with_invalid_log", []),
        "documents_with_selection_context": summary.get("documents_with_selection_context", []),
        "documents_with_selection_fallback": summary.get("documents_with_selection_fallback", []),
    }
    if json_output:
        _emit_json(payload)
        return

    console.print("[bold blue]🧾 Intake Override Audit[/bold blue]")
    console.print(f"Run: {summary.get('run_id') or '-'}")
    console.print(f"Summary: {summary_path}")
    if details_path.exists():
        console.print(f"Details: {details_path}")
    if inputs:
        source = inputs.get("source") or "-"
        row_count = inputs.get("row_count")
        console.print(f"Source: {source} | Rows: {row_count}")

    metrics_table = Table(title="Audit Metrics", show_header=True, header_style="bold magenta")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Count", justify="right", style="white")
    metrics_table.add_column("Rate", justify="right", style="green")
    metric_rows = [
        ("Audited documents", metrics.get("audited_document_count"), None),
        ("Missing logs", metrics.get("missing_intake_override_log_count"), None),
        ("Invalid feedback JSON", metrics.get("invalid_feedback_json_count"), None),
        ("Invalid intake logs", metrics.get("invalid_intake_override_log_count"), None),
        ("Slot disagreements", metrics.get("slot_disagreement_count"), metrics.get("slot_disagreement_rate")),
        ("Tag disagreements", metrics.get("tag_disagreement_count"), metrics.get("tag_disagreement_rate")),
        ("Selection context", metrics.get("selection_context_count"), metrics.get("selection_context_rate")),
        ("Selection fallback", metrics.get("selection_fallback_count"), metrics.get("selection_fallback_rate")),
    ]
    for label, count, rate in metric_rows:
        metrics_table.add_row(label, str(count or 0), _coerce_rate_text(rate) if rate is not None else "-")
    console.print(metrics_table)

    def _bucket_table(title: str, paper_ids: list[str], *, selection_bucket: bool = False, slot_bucket: bool = False) -> None:
        if not paper_ids:
            return
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Paper", style="white")
        table.add_column("Title", style="white")
        if selection_bucket:
            table.add_column("Selection", style="green")
        if slot_bucket:
            table.add_column("Slot", style="yellow")

        for paper_id in paper_ids[:limit] if limit > 0 else paper_ids:
            doc = docs_by_id.get(str(paper_id), {})
            title_text = str(doc.get("title") or "-")
            row = [str(paper_id), title_text]
            if selection_bucket:
                rank = doc.get("selection_selected_rank")
                candidate_count = doc.get("selection_candidate_count")
                score = _coerce_optional_float(doc.get("selection_score"))
                skipped = int(doc.get("selection_skipped_processed_count") or 0)
                parts = []
                if rank is not None and candidate_count is not None:
                    parts.append(f"r{rank}/{candidate_count}")
                elif rank is not None:
                    parts.append(f"r{rank}")
                if score is not None:
                    parts.append(f"s={score:.2f}")
                if skipped > 0:
                    parts.append(f"skip={skipped}")
                row.append(", ".join(parts) or "-")
            if slot_bucket:
                input_slot = str(doc.get("input_slot") or "-")
                stored_slot = str(doc.get("stored_slot") or "-")
                row.append(f"{input_slot} -> {stored_slot}")
            table.add_row(*row)
        console.print(table)

    _bucket_table(
        "Selection Fallback",
        summary.get("documents_with_selection_fallback", []) or [],
        selection_bucket=True,
    )
    _bucket_table(
        "Slot Disagreements",
        summary.get("documents_with_slot_disagreement", []) or [],
        slot_bucket=True,
    )
    _bucket_table("Missing Logs", summary.get("documents_with_missing_log", []) or [])
    _bucket_table("Invalid Logs", summary.get("documents_with_invalid_log", []) or [])


@app.command("show-intake-override-audit-calibration")
def show_intake_override_audit_calibration(
    root: Path = typer.Option(
        default_intake_override_audits_root(),
        "--root",
        help="Path to the intake override audit root directory.",
    ),
    limit: int = typer.Option(10, "--limit", min=0, help="Number of recent audit runs to display."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Render a compact calibration view across recent intake override audit runs."""
    from rich.table import Table

    snapshot = build_intake_override_audit_calibration_snapshot(
        root=root,
        warn_threshold=LATEST_INTAKE_OVERRIDE_AUDIT_WARN_RATE,
        min_audited_docs=LATEST_INTAKE_OVERRIDE_AUDIT_MIN_AUDITED_DOCS,
    )
    threshold_review_root = root.expanduser().resolve(strict=False).parent / "intake_override_threshold_review"
    latest_threshold_review = latest_intake_override_threshold_review_summary(threshold_review_root)
    if isinstance(latest_threshold_review, dict):
        decision = (
            latest_threshold_review.get("decision")
            if isinstance(latest_threshold_review.get("decision"), dict)
            else {}
        )
        snapshot["latest_threshold_review"] = {
            "run_id": str(latest_threshold_review.get("run_id") or "") or None,
            "blocking_summary": str(decision.get("blocking_summary") or "") or None,
            "recommended_action": str(decision.get("recommended_action") or "") or None,
        }
    if json_output:
        _emit_json(snapshot)
        return

    console.print("[bold blue]🧪 Intake Override Audit Calibration[/bold blue]")
    console.print(f"Root: {snapshot['root']}")
    console.print(
        "Heuristic: "
        f"warn >= {snapshot['warn_threshold']:.1%} | "
        f"sample >= {snapshot['min_audited_docs']} audited docs | "
        f"target >= {snapshot['calibration_target_runs']} sufficient runs"
    )
    console.print(
        "Coverage: "
        f"{snapshot['total_runs']} total run(s) | "
        f"{snapshot['eligible_runs']} sufficient | "
        f"{snapshot['warn_runs']} warn"
    )
    latest_threshold_review_meta = (
        snapshot.get("latest_threshold_review")
        if isinstance(snapshot.get("latest_threshold_review"), dict)
        else None
    )
    if latest_threshold_review_meta:
        run_id = str(latest_threshold_review_meta.get("run_id") or "").strip()
        recommended_action = str(latest_threshold_review_meta.get("recommended_action") or "").strip()
        blocking_summary = str(latest_threshold_review_meta.get("blocking_summary") or "").strip()
        if run_id:
            console.print(f"Latest Threshold Review: {run_id}")
        if recommended_action:
            console.print(f"Threshold Action: {recommended_action}")
        if blocking_summary:
            console.print(f"Threshold Blocker: {blocking_summary}")

    runs = snapshot.get("runs") if isinstance(snapshot.get("runs"), list) else []
    if runs:
        runs_table = Table(title="Recent Audit Runs", show_header=True, header_style="bold magenta")
        runs_table.add_column("Run", style="white")
        runs_table.add_column("Source", style="cyan")
        runs_table.add_column("Audited", justify="right", style="white")
        runs_table.add_column("Status", style="yellow")
        runs_table.add_column("Triage", justify="right", style="green")
        runs_table.add_column("Slot", justify="right", style="green")
        runs_table.add_column("Slot Adj", justify="right", style="green")
        runs_table.add_column("Tag Adj", justify="right", style="green")
        runs_table.add_column("Fallback", justify="right", style="green")
        runs_table.add_column("Analysis", justify="right", style="green")
        runs_table.add_column("Issues", justify="right", style="green")

        displayed_runs = runs[:limit] if limit > 0 else runs
        for run_entry in displayed_runs:
            rates = run_entry.get("rates") if isinstance(run_entry.get("rates"), dict) else {}
            runs_table.add_row(
                str(run_entry.get("run_id") or "-"),
                str(run_entry.get("source") or "-"),
                str(run_entry.get("audited_document_count") or 0),
                _audit_calibration_status_text(str(run_entry.get("status") or "")),
                _coerce_rate_text(rates.get("triage")),
                _coerce_rate_text(rates.get("slot")),
                _coerce_rate_text(rates.get("slot_adjudication")),
                _coerce_rate_text(rates.get("tagging_adjudication")),
                _coerce_rate_text(rates.get("fallback")),
                _coerce_rate_text(rates.get("analysis")),
                _coerce_rate_text(rates.get("issues")),
            )
        console.print(runs_table)

    signal_summary = snapshot.get("signal_summary") if isinstance(snapshot.get("signal_summary"), list) else []
    if signal_summary:
        signal_table = Table(title="Signal Summary", show_header=True, header_style="bold cyan")
        signal_table.add_column("Signal", style="white")
        signal_table.add_column("Latest", justify="right", style="green")
        signal_table.add_column("Max", justify="right", style="green")
        signal_table.add_column("Warn Runs", justify="right", style="white")

        for signal_entry in signal_summary:
            signal_table.add_row(
                str(signal_entry.get("signal") or "-"),
                _coerce_rate_text(signal_entry.get("latest_rate")),
                _coerce_rate_text(signal_entry.get("max_rate")),
                (
                    f"{int(signal_entry.get('warn_run_count') or 0)}/"
                    f"{int(snapshot.get('eligible_runs') or 0)}"
                ),
            )
        console.print(signal_table)

    recommendations = snapshot.get("recommendations") if isinstance(snapshot.get("recommendations"), list) else []
    if recommendations:
        console.print("Advice:")
        for item in recommendations:
            console.print(f" - {item}")


@app.command("show-intake-override-threshold-review")
def show_intake_override_threshold_review(
    run: Path = typer.Argument(..., help="Path to a threshold review run directory or summary.json file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Render a compact operator view of an intake override threshold review run."""
    from rich.table import Table

    summary_path = _resolve_audit_json_path(run, "summary.json")
    if not summary_path.exists():
        console.print(f"[bold red]❌ Threshold review summary not found:[/bold red] {summary_path}")
        raise typer.Exit(code=1)

    summary = _load_json_dict(summary_path)
    provenance = summary.get("provenance") if isinstance(summary.get("provenance"), dict) else {}
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), dict) else {}
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}
    snapshot = summary.get("snapshot") if isinstance(summary.get("snapshot"), dict) else {}

    payload = {
        "run_id": summary.get("run_id"),
        "summary_path": str(summary_path),
        "provenance": provenance,
        "inputs": inputs,
        "decision": decision,
        "snapshot": snapshot,
    }
    markdown_path = summary_path.parent / "audit.md"
    if markdown_path.exists():
        payload["markdown_path"] = str(markdown_path)
    if json_output:
        _emit_json(payload)
        return

    console.print("[bold blue]🧭 Intake Override Threshold Review[/bold blue]")
    console.print(f"Run: {summary.get('run_id') or '-'}")
    console.print(f"Summary: {summary_path}")
    if markdown_path.exists():
        console.print(f"Markdown: {markdown_path}")
    provenance_kind = str(provenance.get("kind") or "").strip()
    if provenance_kind:
        console.print(f"Provenance: {provenance_kind}")
    if isinstance(provenance.get("latest_eligible"), bool):
        console.print(f"Latest Eligible: {'yes' if provenance.get('latest_eligible') else 'no'}")

    audit_root = str(inputs.get("audit_root") or "").strip()
    warn_threshold = _coerce_optional_float(inputs.get("warn_threshold"))
    min_audited_docs = _coerce_optional_int(inputs.get("min_audited_docs"))
    calibration_target_runs = _coerce_optional_int(inputs.get("calibration_target_runs"))
    if audit_root:
        console.print(f"Audit Root: {audit_root}")
    heuristic_parts: list[str] = []
    if warn_threshold is not None:
        heuristic_parts.append(f"warn >= {warn_threshold:.1%}")
    if min_audited_docs is not None:
        heuristic_parts.append(f"sample >= {min_audited_docs} audited docs")
    if calibration_target_runs is not None:
        heuristic_parts.append(f"target >= {calibration_target_runs} sufficient runs")
    if heuristic_parts:
        console.print(f"Heuristic: {' | '.join(heuristic_parts)}")

    decision_table = Table(title="Threshold Review", show_header=True, header_style="bold magenta")
    decision_table.add_column("Field", style="cyan")
    decision_table.add_column("Value", style="white")
    decision_table.add_row("Recommended Action", str(decision.get("recommended_action") or "-"))
    decision_table.add_row("Review Ready", "yes" if bool(decision.get("review_ready")) else "no")
    decision_table.add_row("Next Step", str(decision.get("next_step") or "-"))
    latest_run_id = str(decision.get("latest_run_id") or "").strip()
    latest_run_status = str(decision.get("latest_run_status") or "").strip()
    latest_run_text = latest_run_id or "-"
    if latest_run_status:
        latest_run_text = f"{latest_run_text} ({latest_run_status})"
    decision_table.add_row("Latest Run", latest_run_text)
    focus_signals = decision.get("focus_signals")
    if isinstance(focus_signals, list) and focus_signals:
        decision_table.add_row("Focus Signals", ", ".join(str(item).strip() for item in focus_signals if str(item).strip()))
    latest_warn_signals = decision.get("latest_warn_signals")
    if isinstance(latest_warn_signals, list) and latest_warn_signals:
        decision_table.add_row(
            "Latest Warn Signals",
            ", ".join(str(item).strip() for item in latest_warn_signals if str(item).strip()),
        )
    tuning_targets = decision.get("tuning_targets")
    if isinstance(tuning_targets, list) and tuning_targets:
        decision_table.add_row(
            "Tuning Targets",
            ", ".join(str(item).strip() for item in tuning_targets if str(item).strip()),
        )
    tuning_actions = decision.get("tuning_actions")
    if isinstance(tuning_actions, list) and tuning_actions:
        decision_table.add_row(
            "Tuning Actions",
            " | ".join(
                f"{str(item.get('target') or '').strip()}:{str(item.get('action') or '').strip()}"
                for item in tuning_actions
                if isinstance(item, dict)
                and str(item.get("target") or "").strip()
                and str(item.get("action") or "").strip()
            ),
        )
    action_plan = decision.get("action_plan")
    if isinstance(action_plan, list) and action_plan:
        decision_table.add_row(
            "Action Plan",
            " | ".join(
                f"{int(item.get('order') or 0)}.{str(item.get('action') or '').strip()}"
                + (
                    f"->{str(item.get('target') or '').strip()}"
                    if str(item.get("target") or "").strip()
                    else ""
                )
                for item in action_plan
                if isinstance(item, dict)
                and int(item.get("order") or 0) > 0
                and str(item.get("action") or "").strip()
            ),
        )
        plan_signals = " | ".join(
            f"{int(item.get('order') or 0)}:{','.join(str(signal).strip() for signal in item.get('signals', []) if str(signal).strip())}"
            for item in action_plan
            if isinstance(item, dict)
            and int(item.get("order") or 0) > 0
            and any(str(signal).strip() for signal in item.get("signals", []))
        )
        if plan_signals:
            decision_table.add_row("Plan Signals", plan_signals)
        plan_evidence = " | ".join(
            f"{int(item.get('order') or 0)}:{str(item.get('evidence') or '').strip()}"
            for item in action_plan
            if isinstance(item, dict)
            and int(item.get("order") or 0) > 0
            and str(item.get("evidence") or "").strip()
        )
        if plan_evidence:
            decision_table.add_row("Plan Evidence", plan_evidence)
    blocking_action = decision.get("blocking_action")
    if isinstance(blocking_action, dict) and str(blocking_action.get("action") or "").strip():
        blocking_text = (
            f"{int(blocking_action.get('order') or 0)}.{str(blocking_action.get('action') or '').strip()}"
            if int(blocking_action.get("order") or 0) > 0
            else str(blocking_action.get("action") or "").strip()
        )
        if str(blocking_action.get("target") or "").strip():
            blocking_text = f"{blocking_text}->{str(blocking_action.get('target') or '').strip()}"
        decision_table.add_row("Blocking Action", blocking_text)
        blocking_signals = ", ".join(
            str(signal).strip() for signal in blocking_action.get("signals", []) if str(signal).strip()
        )
        if blocking_signals:
            decision_table.add_row("Blocking Signals", blocking_signals)
        blocking_evidence = str(blocking_action.get("evidence") or "").strip()
        if blocking_evidence:
            decision_table.add_row("Blocking Evidence", blocking_evidence)
    blocking_summary = str(decision.get("blocking_summary") or "").strip()
    if blocking_summary:
        decision_table.add_row("Blocking Summary", blocking_summary)
    tuning_recommendations = decision.get("tuning_recommendations")
    if isinstance(tuning_recommendations, list) and tuning_recommendations:
        decision_table.add_row(
            "Tuning Recommendations",
            " | ".join(str(item).strip() for item in tuning_recommendations if str(item).strip()),
        )
    if "threshold_change_ready" in decision:
        decision_table.add_row(
            "Threshold Change Ready",
            "yes" if bool(decision.get("threshold_change_ready")) else "no",
        )
    threshold_change_status = str(decision.get("threshold_change_status") or "").strip()
    if threshold_change_status:
        decision_table.add_row("Threshold Change Status", threshold_change_status)
    threshold_change_next_step = str(decision.get("threshold_change_next_step") or "").strip()
    if threshold_change_next_step:
        decision_table.add_row("Threshold Change Next", threshold_change_next_step)
    threshold_change_blocker = str(decision.get("threshold_change_blocker") or "").strip()
    if threshold_change_blocker:
        decision_table.add_row("Threshold Change Blocker", threshold_change_blocker)
    reason_text = str(decision.get("decision_reason") or "").strip()
    if reason_text:
        decision_table.add_row("Reason", reason_text)
    console.print(decision_table)

    total_runs = _coerce_optional_int(snapshot.get("total_runs"))
    eligible_runs = _coerce_optional_int(snapshot.get("eligible_runs"))
    warn_runs = _coerce_optional_int(snapshot.get("warn_runs"))
    coverage_parts: list[str] = []
    if total_runs is not None:
        coverage_parts.append(f"{total_runs} total")
    if eligible_runs is not None:
        coverage_parts.append(f"{eligible_runs} sufficient")
    if warn_runs is not None:
        coverage_parts.append(f"{warn_runs} warn")
    if coverage_parts:
        console.print(f"Coverage: {' | '.join(coverage_parts)}")

    signal_summary = snapshot.get("signal_summary") if isinstance(snapshot.get("signal_summary"), list) else []
    if signal_summary:
        signal_table = Table(title="Signal Summary", show_header=True, header_style="bold cyan")
        signal_table.add_column("Signal", style="white")
        signal_table.add_column("Latest", justify="right", style="green")
        signal_table.add_column("Max", justify="right", style="green")
        signal_table.add_column("Warn Runs", justify="right", style="white")
        for signal_entry in signal_summary:
            signal_table.add_row(
                str(signal_entry.get("signal") or "-"),
                _coerce_rate_text(signal_entry.get("latest_rate")),
                _coerce_rate_text(signal_entry.get("max_rate")),
                (
                    f"{int(signal_entry.get('warn_run_count') or 0)}/"
                    f"{int(eligible_runs or 0)}"
                ),
            )
        console.print(signal_table)

    recommendations = snapshot.get("recommendations") if isinstance(snapshot.get("recommendations"), list) else []
    if recommendations:
        console.print("Advice:")
        for item in recommendations:
            console.print(f" - {item}")


@app.command("show-processor-gate-threshold-review")
def show_processor_gate_threshold_review(
    run: Path = typer.Argument(..., help="Path to a processor gate threshold review run directory or summary.json file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Render a compact operator view of a processor gate threshold review run."""
    from rich.table import Table

    summary_path = _resolve_audit_json_path(run, "summary.json")
    if not summary_path.exists():
        console.print(f"[bold red]❌ Processor gate threshold review summary not found:[/bold red] {summary_path}")
        raise typer.Exit(code=1)

    summary = _load_json_dict(summary_path)
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), dict) else {}
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}
    signal_summary = summary.get("signal_summary") if isinstance(summary.get("signal_summary"), dict) else {}
    manual_review_scope = (
        summary.get("manual_review_scope") if isinstance(summary.get("manual_review_scope"), dict) else {}
    )
    manual_review_basis = (
        summary.get("manual_review_basis") if isinstance(summary.get("manual_review_basis"), dict) else {}
    )
    worksheet_summary = (
        manual_review_scope.get("worksheet_summary") if isinstance(manual_review_scope.get("worksheet_summary"), dict) else {}
    )
    prefill_summary = (
        manual_review_scope.get("prefill_summary") if isinstance(manual_review_scope.get("prefill_summary"), dict) else {}
    )
    recommendations = summary.get("recommendations") if isinstance(summary.get("recommendations"), list) else []
    markdown_path = summary_path.with_name("audit.md")
    manual_review_rows_path = summary_path.with_name("manual_review_rows.json")
    manual_review_markdown_path = summary_path.with_name("manual_review.md")
    manual_review_checklist_path = summary_path.with_name("manual_review_checklist.csv")
    manual_review_seed_path = summary_path.with_name("manual_review_seed.csv")
    manual_review_frontier_path = summary_path.with_name("manual_review_frontier.csv")
    manual_review_frontier_notes_path = summary_path.with_name("manual_review_frontier_notes.md")
    manual_review_frontier_crosscheck_packet_path = summary_path.with_name("manual_review_frontier_crosscheck_packet.md")
    manual_review_frontier_claude_crosscheck_path = summary_path.with_name("manual_review_frontier_claude_crosscheck.md")
    manual_review_frontier_claude_crosscheck_json_path = summary_path.with_name("manual_review_frontier_claude_crosscheck.json")
    manual_review_basis_markdown_path = summary_path.with_name("manual_review_basis.md")
    manual_review_decision_markdown_path = summary_path.with_name("manual_review_decision.md")
    manual_review_outcome_path = summary_path.with_name("manual_review_outcome.json")
    manual_review_outcome_markdown_path = summary_path.with_name("manual_review_outcome.md")
    threshold_change_decision_path = summary_path.with_name("threshold_change_decision.json")
    threshold_change_decision_markdown_path = summary_path.with_name("threshold_change_decision.md")
    mid_confidence_policy_decision_path = summary_path.with_name("mid_confidence_policy_decision.json")
    mid_confidence_policy_decision_markdown_path = summary_path.with_name("mid_confidence_policy_decision.md")
    mid_confidence_policy_debt_reconciliation_path = summary_path.with_name(
        "mid_confidence_policy_debt_reconciliation.json"
    )
    mid_confidence_policy_debt_reconciliation_markdown_path = summary_path.with_name(
        "mid_confidence_policy_debt_reconciliation.md"
    )
    manual_override_policy_decision_path = summary_path.with_name("manual_override_policy_decision.json")
    manual_override_policy_decision_markdown_path = summary_path.with_name(
        "manual_override_policy_decision.md"
    )
    indexed_pending_policy_decision_path = summary_path.with_name("indexed_pending_policy_decision.json")
    indexed_pending_policy_decision_markdown_path = summary_path.with_name(
        "indexed_pending_policy_decision.md"
    )
    fixture_or_test_policy_decision_path = summary_path.with_name("fixture_or_test_policy_decision.json")
    fixture_or_test_policy_decision_markdown_path = summary_path.with_name(
        "fixture_or_test_policy_decision.md"
    )
    threshold_change_proposal_path = summary_path.with_name("threshold_change_proposal.json")
    threshold_change_proposal_markdown_path = summary_path.with_name("threshold_change_proposal.md")
    drift_artifacts = resolve_processor_gate_threshold_review_drift_artifacts(
        summary,
        threshold_change_proposal_path=threshold_change_proposal_path,
    )
    manual_review_outcome = (
        _load_json_dict(manual_review_outcome_path) if manual_review_outcome_path.exists() else {}
    )
    threshold_change_decision = (
        _load_json_dict(threshold_change_decision_path) if threshold_change_decision_path.exists() else {}
    )
    mid_confidence_policy_decision = (
        _load_json_dict(mid_confidence_policy_decision_path)
        if mid_confidence_policy_decision_path.exists()
        else {}
    )
    mid_confidence_policy_debt_reconciliation = (
        _load_json_dict(mid_confidence_policy_debt_reconciliation_path)
        if mid_confidence_policy_debt_reconciliation_path.exists()
        else {}
    )
    manual_override_policy_decision = (
        _load_json_dict(manual_override_policy_decision_path)
        if manual_override_policy_decision_path.exists()
        else {}
    )
    indexed_pending_policy_decision = (
        _load_json_dict(indexed_pending_policy_decision_path)
        if indexed_pending_policy_decision_path.exists()
        else {}
    )
    fixture_or_test_policy_decision = (
        _load_json_dict(fixture_or_test_policy_decision_path)
        if fixture_or_test_policy_decision_path.exists()
        else {}
    )
    threshold_change_proposal = {}
    if threshold_change_proposal_path.exists():
        try:
            threshold_change_proposal = _load_json_dict(threshold_change_proposal_path)
        except (OSError, ValueError, json.JSONDecodeError):
            threshold_change_proposal = {}
    threshold_change_validation_replay_command = str(
        threshold_change_proposal.get("validation_replay_command_template") or ""
    ).strip()
    threshold_change_validation_replay_run_id = str(
        threshold_change_proposal.get("validation_replay_run_id") or ""
    ).strip()

    payload = {
        "run_id": summary.get("run_id"),
        "summary_path": str(summary_path),
        "markdown_path": str(markdown_path) if markdown_path.exists() else None,
        "manual_review_rows_path": str(manual_review_rows_path) if manual_review_rows_path.exists() else None,
        "manual_review_markdown_path": str(manual_review_markdown_path) if manual_review_markdown_path.exists() else None,
        "manual_review_checklist_path": str(manual_review_checklist_path) if manual_review_checklist_path.exists() else None,
        "manual_review_seed_path": str(manual_review_seed_path) if manual_review_seed_path.exists() else None,
        "manual_review_frontier_path": str(manual_review_frontier_path) if manual_review_frontier_path.exists() else None,
        "manual_review_frontier_notes_path": str(manual_review_frontier_notes_path) if manual_review_frontier_notes_path.exists() else None,
        "manual_review_frontier_crosscheck_packet_path": str(manual_review_frontier_crosscheck_packet_path) if manual_review_frontier_crosscheck_packet_path.exists() else None,
        "manual_review_frontier_claude_crosscheck_path": str(manual_review_frontier_claude_crosscheck_path) if manual_review_frontier_claude_crosscheck_path.exists() else None,
        "manual_review_frontier_claude_crosscheck_json_path": str(manual_review_frontier_claude_crosscheck_json_path) if manual_review_frontier_claude_crosscheck_json_path.exists() else None,
        "manual_review_basis_markdown_path": str(manual_review_basis_markdown_path) if manual_review_basis_markdown_path.exists() else None,
        "manual_review_decision_markdown_path": str(manual_review_decision_markdown_path) if manual_review_decision_markdown_path.exists() else None,
        "manual_review_outcome_path": str(manual_review_outcome_path) if manual_review_outcome_path.exists() else None,
        "manual_review_outcome_markdown_path": str(manual_review_outcome_markdown_path) if manual_review_outcome_markdown_path.exists() else None,
        "threshold_change_decision_path": str(threshold_change_decision_path) if threshold_change_decision_path.exists() else None,
        "threshold_change_decision_markdown_path": str(threshold_change_decision_markdown_path) if threshold_change_decision_markdown_path.exists() else None,
        "mid_confidence_policy_decision_path": str(mid_confidence_policy_decision_path) if mid_confidence_policy_decision_path.exists() else None,
        "mid_confidence_policy_decision_markdown_path": str(mid_confidence_policy_decision_markdown_path) if mid_confidence_policy_decision_markdown_path.exists() else None,
        "mid_confidence_policy_debt_reconciliation_path": str(mid_confidence_policy_debt_reconciliation_path) if mid_confidence_policy_debt_reconciliation_path.exists() else None,
        "mid_confidence_policy_debt_reconciliation_markdown_path": str(mid_confidence_policy_debt_reconciliation_markdown_path) if mid_confidence_policy_debt_reconciliation_markdown_path.exists() else None,
        "manual_override_policy_decision_path": str(manual_override_policy_decision_path) if manual_override_policy_decision_path.exists() else None,
        "manual_override_policy_decision_markdown_path": str(manual_override_policy_decision_markdown_path) if manual_override_policy_decision_markdown_path.exists() else None,
        "indexed_pending_policy_decision_path": str(indexed_pending_policy_decision_path) if indexed_pending_policy_decision_path.exists() else None,
        "indexed_pending_policy_decision_markdown_path": str(indexed_pending_policy_decision_markdown_path) if indexed_pending_policy_decision_markdown_path.exists() else None,
        "fixture_or_test_policy_decision_path": str(fixture_or_test_policy_decision_path) if fixture_or_test_policy_decision_path.exists() else None,
        "fixture_or_test_policy_decision_markdown_path": str(fixture_or_test_policy_decision_markdown_path) if fixture_or_test_policy_decision_markdown_path.exists() else None,
        "threshold_change_proposal_path": str(threshold_change_proposal_path) if threshold_change_proposal_path.exists() else None,
        "threshold_change_proposal_markdown_path": str(threshold_change_proposal_markdown_path) if threshold_change_proposal_markdown_path.exists() else None,
        "threshold_change_validation_replay_command_template": threshold_change_validation_replay_command or None,
        "threshold_change_validation_replay_run_id": threshold_change_validation_replay_run_id or None,
        "threshold_change_validation_replay_available": drift_artifacts.get(
            "threshold_change_validation_replay_available"
        ),
        "threshold_change_validation_replay_matches_proposal": drift_artifacts.get(
            "threshold_change_validation_replay_matches_proposal"
        ),
        "threshold_change_validation_replay_needs_rerun": drift_artifacts.get(
            "threshold_change_validation_replay_needs_rerun"
        ),
        "threshold_change_validation_replay_status": drift_artifacts.get(
            "threshold_change_validation_replay_status"
        ),
        "threshold_change_manual_decision_ready": drift_artifacts.get(
            "threshold_change_manual_decision_ready"
        ),
        "threshold_change_manual_decision_status": drift_artifacts.get(
            "threshold_change_manual_decision_status"
        ),
        "threshold_change_manual_decision_blocker": drift_artifacts.get(
            "threshold_change_manual_decision_blocker"
        ),
        "drift_summary_path": drift_artifacts.get("drift_summary_path"),
        "drift_details_path": drift_artifacts.get("drift_details_path"),
        "drift_markdown_path": drift_artifacts.get("drift_markdown_path"),
        "threshold_replay_path": drift_artifacts.get("threshold_replay_path"),
        "threshold_replay_markdown_path": drift_artifacts.get("threshold_replay_markdown_path"),
        "threshold_replay_text": drift_artifacts.get("threshold_replay_text"),
        "threshold_replay_review_command": drift_artifacts.get("threshold_replay_review_command"),
        "threshold_replay_mode": drift_artifacts.get("threshold_replay_mode"),
        "threshold_replay_high_threshold": drift_artifacts.get("threshold_replay_high_threshold"),
        "threshold_replay_low_threshold": drift_artifacts.get("threshold_replay_low_threshold"),
        "threshold_replay_reviewed_high_threshold": drift_artifacts.get("threshold_replay_reviewed_high_threshold"),
        "threshold_replay_proposal_run_id": drift_artifacts.get("threshold_replay_proposal_run_id"),
        "inputs": inputs,
        "decision": decision,
        "signal_summary": signal_summary,
        "manual_review_scope": manual_review_scope,
        "manual_review_basis": manual_review_basis,
        "manual_review_outcome": manual_review_outcome,
        "threshold_change_decision": threshold_change_decision,
        "mid_confidence_policy_decision": mid_confidence_policy_decision,
        "mid_confidence_policy_debt_reconciliation": mid_confidence_policy_debt_reconciliation,
        "manual_override_policy_decision": manual_override_policy_decision,
        "indexed_pending_policy_decision": indexed_pending_policy_decision,
        "fixture_or_test_policy_decision": fixture_or_test_policy_decision,
        "recommendations": recommendations,
    }
    if json_output:
        _emit_json(payload)
        return

    def _artifact_line(label: str, path: Path) -> str:
        return f"{label}: {path.name} ({path})"

    console.print("[bold blue]🧭 Processor Gate Threshold Review[/bold blue]")
    console.print(f"Run: {summary.get('run_id') or '-'}")
    console.print(f"Summary: {summary_path}")
    if markdown_path.exists():
        console.print(_artifact_line("Markdown", markdown_path))
    if manual_review_rows_path.exists():
        console.print(_artifact_line("Manual Review Rows", manual_review_rows_path))
    if manual_review_markdown_path.exists():
        console.print(_artifact_line("Manual Review Markdown", manual_review_markdown_path))
    if manual_review_checklist_path.exists():
        console.print(_artifact_line("Manual Review Checklist", manual_review_checklist_path))
    if manual_review_seed_path.exists():
        console.print(_artifact_line("Manual Review Seed", manual_review_seed_path))
    if manual_review_frontier_path.exists():
        console.print(_artifact_line("Manual Review Frontier", manual_review_frontier_path))
    if manual_review_frontier_notes_path.exists():
        console.print(_artifact_line("Manual Review Frontier Notes", manual_review_frontier_notes_path))
    if manual_review_frontier_crosscheck_packet_path.exists():
        console.print(
            _artifact_line("Manual Review Frontier Crosscheck Packet", manual_review_frontier_crosscheck_packet_path)
        )
    if manual_review_frontier_claude_crosscheck_path.exists():
        console.print(
            _artifact_line("Manual Review Frontier Claude Crosscheck", manual_review_frontier_claude_crosscheck_path)
        )
    if manual_review_frontier_claude_crosscheck_json_path.exists():
        console.print(
            _artifact_line(
                "Manual Review Frontier Claude Crosscheck JSON",
                manual_review_frontier_claude_crosscheck_json_path,
            )
        )
    if manual_review_basis_markdown_path.exists():
        console.print(_artifact_line("Manual Review Basis", manual_review_basis_markdown_path))
    if manual_review_decision_markdown_path.exists():
        console.print(_artifact_line("Manual Review Decision", manual_review_decision_markdown_path))
    if manual_review_outcome_path.exists():
        console.print(_artifact_line("Manual Review Outcome", manual_review_outcome_path))
    if manual_review_outcome_markdown_path.exists():
        console.print(_artifact_line("Manual Review Outcome Markdown", manual_review_outcome_markdown_path))
    if threshold_change_decision_path.exists():
        console.print(_artifact_line("Threshold Change Decision", threshold_change_decision_path))
    if threshold_change_decision_markdown_path.exists():
        console.print(
            _artifact_line("Threshold Change Decision Markdown", threshold_change_decision_markdown_path)
        )
    if mid_confidence_policy_decision_path.exists():
        console.print(_artifact_line("Mid-Confidence Policy Decision", mid_confidence_policy_decision_path))
    if mid_confidence_policy_decision_markdown_path.exists():
        console.print(
            _artifact_line(
                "Mid-Confidence Policy Decision Markdown",
                mid_confidence_policy_decision_markdown_path,
            )
        )
    if mid_confidence_policy_debt_reconciliation_path.exists():
        console.print(
            _artifact_line(
                "Mid-Confidence Policy Debt Reconciliation",
                mid_confidence_policy_debt_reconciliation_path,
            )
        )
    if mid_confidence_policy_debt_reconciliation_markdown_path.exists():
        console.print(
            _artifact_line(
                "Mid-Confidence Policy Debt Reconciliation Markdown",
                mid_confidence_policy_debt_reconciliation_markdown_path,
            )
        )
    if manual_override_policy_decision_path.exists():
        console.print(
            _artifact_line("Manual Override Policy Decision", manual_override_policy_decision_path)
        )
    if manual_override_policy_decision_markdown_path.exists():
        console.print(
            _artifact_line(
                "Manual Override Policy Decision Markdown",
                manual_override_policy_decision_markdown_path,
            )
        )
    if indexed_pending_policy_decision_path.exists():
        console.print(
            _artifact_line("Indexed Pending Policy Decision", indexed_pending_policy_decision_path)
        )
    if indexed_pending_policy_decision_markdown_path.exists():
        console.print(
            _artifact_line(
                "Indexed Pending Policy Decision Markdown",
                indexed_pending_policy_decision_markdown_path,
            )
        )
    if fixture_or_test_policy_decision_path.exists():
        console.print(
            _artifact_line("Fixture/Test Policy Decision", fixture_or_test_policy_decision_path)
        )
    if fixture_or_test_policy_decision_markdown_path.exists():
        console.print(
            _artifact_line("Fixture/Test Policy Decision Markdown", fixture_or_test_policy_decision_markdown_path)
        )
    if threshold_change_proposal_path.exists():
        console.print(f"Threshold Change Proposal: {threshold_change_proposal_path}")
    if threshold_change_validation_replay_command:
        console.print(
            "Threshold Change Validation Replay: "
            f"{threshold_change_validation_replay_command}"
        )
    validation_replay_status = str(
        drift_artifacts.get("threshold_change_validation_replay_status") or ""
    ).strip()
    if validation_replay_status and validation_replay_status != "not_applicable":
        console.print(
            "Threshold Change Validation Replay Status: "
            f"{validation_replay_status} "
            f"(available={'yes' if drift_artifacts.get('threshold_change_validation_replay_available') else 'no'}, "
            f"matches={'yes' if drift_artifacts.get('threshold_change_validation_replay_matches_proposal') else 'no'}, "
            f"needs_rerun={'yes' if drift_artifacts.get('threshold_change_validation_replay_needs_rerun') else 'no'})"
        )
    manual_decision_status = str(
        drift_artifacts.get("threshold_change_manual_decision_status") or ""
    ).strip()
    if manual_decision_status and manual_decision_status != "not_applicable":
        manual_decision_text = (
            "Threshold Change Manual Decision: "
            f"ready={'yes' if drift_artifacts.get('threshold_change_manual_decision_ready') else 'no'}, "
            f"status={manual_decision_status}"
        )
        manual_decision_blocker = str(
            drift_artifacts.get("threshold_change_manual_decision_blocker") or ""
        ).strip()
        if manual_decision_blocker:
            manual_decision_text = f"{manual_decision_text}, blocker={manual_decision_blocker}"
        console.print(manual_decision_text)
    if threshold_change_proposal_markdown_path.exists():
        console.print(f"Threshold Change Proposal Markdown: {threshold_change_proposal_markdown_path}")
    if drift_artifacts.get("drift_summary_path"):
        console.print(f"Replay Drift Summary: {drift_artifacts['drift_summary_path']}")
    if drift_artifacts.get("drift_details_path"):
        console.print(f"Replay Drift Details: {drift_artifacts['drift_details_path']}")
    if drift_artifacts.get("drift_markdown_path"):
        console.print(f"Replay Drift Markdown: {drift_artifacts['drift_markdown_path']}")
    if drift_artifacts.get("threshold_replay_path"):
        console.print(f"Threshold Replay Context: {drift_artifacts['threshold_replay_path']}")
    if drift_artifacts.get("threshold_replay_markdown_path"):
        console.print(
            "Threshold Replay Context Markdown: "
            f"{drift_artifacts['threshold_replay_markdown_path']}"
        )
    if drift_artifacts.get("threshold_replay_text"):
        console.print(f"Threshold Replay: {drift_artifacts['threshold_replay_text']}")
    if drift_artifacts.get("threshold_replay_review_command"):
        console.print(
            "Threshold Replay Review Command: "
            f"{drift_artifacts['threshold_replay_review_command']}"
        )

    heuristic_parts: list[str] = []
    drift_warn_threshold = _coerce_optional_float(inputs.get("drift_warn_threshold"))
    min_candidate_rows = _coerce_optional_int(inputs.get("min_candidate_rows"))
    if drift_warn_threshold is not None:
        heuristic_parts.append(f"warn >= {drift_warn_threshold:.1%}")
    if min_candidate_rows is not None:
        heuristic_parts.append(f"sample >= {min_candidate_rows} candidate rows")
    if heuristic_parts:
        console.print(f"Heuristic: {' | '.join(heuristic_parts)}")

    threshold_parts: list[str] = []
    high_threshold = _coerce_optional_float(inputs.get("high_threshold"))
    low_threshold = _coerce_optional_float(inputs.get("low_threshold"))
    if high_threshold is not None:
        threshold_parts.append(f"high={high_threshold:.2f}")
    if low_threshold is not None:
        threshold_parts.append(f"low={low_threshold:.2f}")
    if threshold_parts:
        console.print(f"Thresholds: {' | '.join(threshold_parts)}")

    decision_table = Table(title="Threshold Review", show_header=True, header_style="bold magenta")
    decision_table.add_column("Field", style="cyan")
    decision_table.add_column("Value", style="white")
    decision_table.add_row("Recommended Action", str(decision.get("recommended_action") or "-"))
    decision_table.add_row("Review Ready", "yes" if bool(decision.get("review_ready")) else "no")
    decision_table.add_row("Next Step", str(decision.get("next_step") or "-"))
    latest_run_id = str(decision.get("latest_run_id") or "").strip()
    latest_run_status = str(decision.get("latest_run_status") or "").strip()
    latest_run_text = latest_run_id or "-"
    if latest_run_status:
        latest_run_text = f"{latest_run_text} ({latest_run_status})"
    decision_table.add_row("Latest Drift Run", latest_run_text)
    focus_areas = decision.get("focus_areas")
    if isinstance(focus_areas, list) and focus_areas:
        decision_table.add_row("Focus Areas", ", ".join(str(item).strip() for item in focus_areas if str(item).strip()))
    tuning_targets = decision.get("tuning_targets")
    if isinstance(tuning_targets, list) and tuning_targets:
        decision_table.add_row(
            "Tuning Targets",
            ", ".join(str(item).strip() for item in tuning_targets if str(item).strip()),
        )
    tuning_actions = decision.get("tuning_actions")
    if isinstance(tuning_actions, list) and tuning_actions:
        decision_table.add_row(
            "Tuning Actions",
            " | ".join(
                f"{str(item.get('target') or '').strip()}:{str(item.get('action') or '').strip()}"
                for item in tuning_actions
                if isinstance(item, dict)
                and str(item.get("target") or "").strip()
                and str(item.get("action") or "").strip()
            ),
        )
    action_plan = decision.get("action_plan")
    if isinstance(action_plan, list) and action_plan:
        decision_table.add_row(
            "Action Plan",
            " | ".join(
                f"{int(item.get('order') or 0)}.{str(item.get('action') or '').strip()}"
                + (
                    f"->{str(item.get('target') or '').strip()}"
                    if str(item.get("target") or "").strip()
                    else ""
                )
                for item in action_plan
                if isinstance(item, dict)
                and int(item.get("order") or 0) > 0
                and str(item.get("action") or "").strip()
            ),
        )
    tuning_recommendations = decision.get("tuning_recommendations")
    if isinstance(tuning_recommendations, list) and tuning_recommendations:
        decision_table.add_row(
            "Tuning Recommendations",
            " | ".join(str(item).strip() for item in tuning_recommendations if str(item).strip()),
        )
    if "threshold_change_ready" in decision:
        decision_table.add_row(
            "Threshold Change Ready",
            "yes" if bool(decision.get("threshold_change_ready")) else "no",
        )
    threshold_change_status = str(decision.get("threshold_change_status") or "").strip()
    if threshold_change_status:
        decision_table.add_row("Threshold Change Status", threshold_change_status)
    threshold_change_next_step = str(decision.get("threshold_change_next_step") or "").strip()
    if threshold_change_next_step:
        decision_table.add_row("Threshold Change Next", threshold_change_next_step)
    threshold_change_blocker = str(decision.get("threshold_change_blocker") or "").strip()
    if threshold_change_blocker:
        decision_table.add_row("Threshold Change Blocker", threshold_change_blocker)
    reason_text = str(decision.get("decision_reason") or "").strip()
    if reason_text:
        decision_table.add_row("Reason", reason_text)
    console.print(decision_table)

    candidate_count = _coerce_optional_int(signal_summary.get("candidate_count"))
    promotable_count = _coerce_optional_int(signal_summary.get("promotable_count"))
    drift_count = _coerce_optional_int(signal_summary.get("drift_count"))
    drift_rate_text = _format_percentage_text(signal_summary.get("drift_rate"))
    coverage_parts: list[str] = []
    if candidate_count is not None:
        coverage_parts.append(f"{candidate_count} candidates")
    if promotable_count is not None:
        coverage_parts.append(f"{promotable_count} promotable")
    if drift_count is not None:
        coverage_parts.append(f"{drift_count} drift")
    if drift_rate_text is not None:
        coverage_parts.append(f"rate={drift_rate_text}")
    if coverage_parts:
        console.print(f"Coverage: {' | '.join(coverage_parts)}")

    def _render_count_table(title: str, counts: object) -> None:
        if not isinstance(counts, dict) or not counts:
            return
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Key", style="white")
        table.add_column("Count", justify="right", style="green")
        for key, value in sorted(counts.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
            table.add_row(str(key), str(int(value or 0)))
        console.print(table)

    _render_count_table("Decision Transitions", signal_summary.get("decision_transition_counts"))
    _render_count_table("Probable Drift Causes", signal_summary.get("probable_drift_cause_counts"))
    _render_count_table("Gate Reason Categories", signal_summary.get("gate_reason_category_counts"))
    _render_count_table("Confidence Bands", signal_summary.get("confidence_band_counts"))

    if manual_review_scope:
        scope_table = Table(title="Manual Review Scope", show_header=True, header_style="bold yellow")
        scope_table.add_column("Bucket", style="white")
        scope_table.add_column("Count", justify="right", style="green")
        scope_table.add_column("Sample IDs", style="cyan")

        def _sample_ids_text(bucket: object) -> str:
            if not isinstance(bucket, dict):
                return "-"
            paper_ids = [str(item).strip() for item in bucket.get("paper_ids", []) if str(item).strip()]
            if not paper_ids:
                return "-"
            preview = ", ".join(paper_ids[:3])
            if len(paper_ids) > 3:
                preview += f" (+{len(paper_ids) - 3} more)"
            return preview

        def _bucket_count(bucket: object) -> str:
            if not isinstance(bucket, dict):
                return "0"
            return str(int(_coerce_optional_int(bucket.get("count")) or 0))

        threshold_relevant = manual_review_scope.get("threshold_relevant")
        policy_edge_cases = manual_review_scope.get("policy_edge_cases")
        excluded = manual_review_scope.get("excluded") if isinstance(manual_review_scope.get("excluded"), dict) else {}

        scope_table.add_row("threshold_relevant", _bucket_count(threshold_relevant), _sample_ids_text(threshold_relevant))
        scope_table.add_row("policy_edge_cases", _bucket_count(policy_edge_cases), _sample_ids_text(policy_edge_cases))
        for label, bucket in [
            ("excluded.manual_override", excluded.get("manual_override")),
            ("excluded.indexed_pending", excluded.get("indexed_pending")),
            ("excluded.fixture_or_test", excluded.get("fixture_or_test")),
            ("excluded.other", excluded.get("other")),
        ]:
            scope_table.add_row(label, _bucket_count(bucket), _sample_ids_text(bucket))
        console.print(scope_table)

        focus_recommendation = str(manual_review_scope.get("focus_recommendation") or "").strip()
        if focus_recommendation:
            console.print(f"Review Basis: {focus_recommendation}")
        worksheet_text = _processor_gate_worksheet_compact_text(worksheet_summary)
        if worksheet_text:
            console.print(f"Worksheet: {worksheet_text}")
        worksheet_summary_text = str(worksheet_summary.get("summary") or "").strip()
        if worksheet_summary_text:
            console.print(f"Worksheet Summary: {worksheet_summary_text}")
        prefill_text = _processor_gate_prefill_compact_text(prefill_summary)
        if prefill_text:
            console.print(f"Prefill: {prefill_text}")
        prefill_summary_text = str(prefill_summary.get("summary") or "").strip()
        if prefill_summary_text:
            console.print(f"Prefill Summary: {prefill_summary_text}")
        basis_text = _processor_gate_basis_compact_text(manual_review_basis)
        if basis_text:
            console.print(f"Basis: {basis_text}")
        basis_summary_text = str(manual_review_basis.get("summary") or "").strip()
        if basis_summary_text:
            console.print(f"Basis Summary: {basis_summary_text}")
        outcome_text = _processor_gate_manual_review_outcome_compact_text(
            manual_review_outcome
        )
        if outcome_text:
            console.print(f"Outcome: {outcome_text}")
        outcome_summary_text = str(manual_review_outcome.get("summary") or "").strip()
        if outcome_summary_text:
            console.print(f"Outcome Summary: {outcome_summary_text}")
        threshold_decision_text = _processor_gate_threshold_change_decision_compact_text(
            threshold_change_decision
        )
        if threshold_decision_text:
            console.print(f"Threshold Decision: {threshold_decision_text}")
        threshold_decision_summary_text = str(threshold_change_decision.get("summary") or "").strip()
        if threshold_decision_summary_text:
            console.print(f"Threshold Decision Summary: {threshold_decision_summary_text}")
        mid_policy_text = _processor_gate_mid_confidence_policy_decision_compact_text(
            mid_confidence_policy_decision
        )
        if mid_policy_text:
            console.print(f"Mid-Confidence Policy: {mid_policy_text}")
        mid_policy_summary_text = str(mid_confidence_policy_decision.get("summary") or "").strip()
        if mid_policy_summary_text:
            console.print(f"Mid-Confidence Policy Summary: {mid_policy_summary_text}")
        policy_debt_text = _processor_gate_policy_debt_reconciliation_compact_text(
            mid_confidence_policy_debt_reconciliation
        )
        if policy_debt_text:
            console.print(f"Policy Debt: {policy_debt_text}")
        policy_debt_summary_text = str(
            mid_confidence_policy_debt_reconciliation.get("summary") or ""
        ).strip()
        if policy_debt_summary_text:
            console.print(f"Policy Debt Summary: {policy_debt_summary_text}")
        manual_override_policy_text = _processor_gate_manual_override_policy_decision_compact_text(
            manual_override_policy_decision
        )
        if manual_override_policy_text:
            console.print(f"Manual Override Policy: {manual_override_policy_text}")
        manual_override_policy_summary_text = str(
            manual_override_policy_decision.get("summary") or ""
        ).strip()
        if manual_override_policy_summary_text:
            console.print(f"Manual Override Policy Summary: {manual_override_policy_summary_text}")
        indexed_pending_policy_text = _processor_gate_indexed_pending_policy_decision_compact_text(
            indexed_pending_policy_decision
        )
        if indexed_pending_policy_text:
            console.print(f"Indexed Pending Policy: {indexed_pending_policy_text}")
        indexed_pending_policy_summary_text = str(
            indexed_pending_policy_decision.get("summary") or ""
        ).strip()
        if indexed_pending_policy_summary_text:
            console.print(f"Indexed Pending Policy Summary: {indexed_pending_policy_summary_text}")
        fixture_or_test_policy_text = _processor_gate_fixture_or_test_policy_decision_compact_text(
            fixture_or_test_policy_decision
        )
        if fixture_or_test_policy_text:
            console.print(f"Fixture/Test Policy: {fixture_or_test_policy_text}")
        fixture_or_test_policy_summary_text = str(
            fixture_or_test_policy_decision.get("summary") or ""
        ).strip()
        if fixture_or_test_policy_summary_text:
            console.print(f"Fixture/Test Policy Summary: {fixture_or_test_policy_summary_text}")

    if recommendations:
        console.print("Advice:")
        for item in recommendations:
            console.print(f" - {item}")


@app.command()
def read(
    identifier: str = typer.Argument(..., help="Paper ID, DOI, or Exact Title")
):
    """Mark a paper as 'Reading'."""
    update_reading_status_workflow(identifier, "Reading", console)

@app.command()
def done(
    identifier: str = typer.Argument(..., help="Paper ID, DOI, or Exact Title")
):
    """Mark a paper as 'Done'."""
    update_reading_status_workflow(identifier, "Done", console)

@app.command()
def deepread(
    identifier: str = typer.Argument(..., help="Paper ID or DOI"),
    verify: bool = typer.Option(False, "--verify", help="Run strict statistical verification on claims"),
    reader_timeout_sec: int = typer.Option(
        0,
        "--reader-timeout-sec",
        min=0,
        help="Reader step timeout seconds (0 = auto budget)",
    ),
    stats_timeout_sec: int = typer.Option(
        0,
        "--stats-timeout-sec",
        min=0,
        help="Stats verification step timeout seconds (0 = auto budget)",
    ),
    adaptive_step_timeout: bool = typer.Option(
        True,
        "--adaptive-step-timeout/--no-adaptive-step-timeout",
        help="Use page/table aware adaptive timeout budget.",
    ),
):
    """
    [v3.0] Run Agentic Deep Read pipeline: Ingest -> Index -> Read.
    Appends structured analysis to the Obsidian note.
    """
    run_deepread_workflow(
        identifier,
        verify,
        console,
        reader_timeout_sec=reader_timeout_sec,
        stats_timeout_sec=stats_timeout_sec,
        adaptive_step_timeout=adaptive_step_timeout,
    )


def _import_pdf_from_path(source_path: Path, *, json_output: bool, success_label: str) -> None:
    from fastapi import HTTPException
    from backend.routers.paper_notes import import_pdf_payload

    source_path = source_path.expanduser()
    if not source_path.exists():
        console.print(f"[bold red]❌ PDF not found: {source_path}[/bold red]")
        raise typer.Exit(code=1)
    if not source_path.is_file():
        console.print(f"[bold red]❌ Not a file: {source_path}[/bold red]")
        raise typer.Exit(code=1)
    try:
        payload = source_path.read_bytes()
        result = import_pdf_payload(filename=source_path.name, payload=payload)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
        if json_output:
            _emit_json({"status": "error", "detail": detail})
        else:
            console.print(f"[bold red]❌ Import failed: {detail}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        if json_output:
            _emit_json({"status": "error", "detail": str(exc)})
        else:
            console.print(f"[bold red]❌ Import failed: {exc}[/bold red]")
        raise typer.Exit(code=1)

    payload_out = result.model_dump()
    if json_output:
        _emit_json({"status": "ok", **payload_out})
        return

    console.print(f"[bold green]✅ {success_label}[/bold green]")
    console.print(f"   paper_id: {result.paper_id}")
    console.print(f"   slug: {result.slug}")
    console.print(f"   note_path: {result.note_path}")
    console.print(f"   pdf_url: {result.pdf_url}")
    console.print(f"   next: open /papers/{result.slug} or /workbench/{result.paper_id}")


@app.command("import-pdf")
def import_pdf(
    pdf_path: str = typer.Argument(..., help="Path to a local PDF file"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Import one local PDF into Paper Notes and print the generated paper id."""
    _import_pdf_from_path(
        Path(pdf_path),
        json_output=json_output,
        success_label="Imported PDF into Paper Notes.",
    )


@app.command("demo-first-paper")
def demo_first_paper(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
):
    """Import the bundled sample PDF so a first run can reach the paper-note flow."""
    sample_pdf_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sample.pdf"
    _import_pdf_from_path(
        sample_pdf_path,
        json_output=json_output,
        success_label="Imported bundled sample PDF into Paper Notes.",
    )


@app.command(name="repair-stats")
def repair_stats(
    paper_id: list[str] = typer.Option(
        [],
        "--paper-id",
        help="Target paper id (repeatable). Default uses a curated historical 3-paper repair seed set.",
    ),
    run_id: str = typer.Option("", "--run-id", help="Optional run id override."),
    artifacts_root: str = typer.Option(
        "storage/artifacts",
        "--artifacts-root",
        help="Artifacts root directory.",
    ),
    max_checks: int = typer.Option(6, "--max-checks", min=1, help="Max checks per paper."),
    write_bootstrap_meta: bool = typer.Option(
        True,
        "--write-bootstrap-meta/--no-write-bootstrap-meta",
        help="Update bootstrap_meta flags when writing stats_report.",
    ),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--overwrite-existing",
        help="Skip runs where stats_report.json already exists.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; do not write files."),
):
    """
    Seed missing stats_report.json from claimset artifacts.
    """
    from src.services.stats_repair import (
        DEFAULT_STATS_REPAIR_PAPER_IDS,
        seed_stats_reports_from_claimset,
    )

    target_ids = paper_id if paper_id else list(DEFAULT_STATS_REPAIR_PAPER_IDS)
    results = seed_stats_reports_from_claimset(
        paper_ids=[str(pid) for pid in target_ids],
        artifacts_root=Path(artifacts_root),
        run_id=(run_id or None),
        max_checks=max_checks,
        write_bootstrap_meta=write_bootstrap_meta,
        skip_existing=skip_existing,
        dry_run=dry_run,
    )

    for item in results:
        console.print(
            f"{item.paper_id} | run={item.run_id or '-'} | {item.status} | checks={item.checks} | {item.reason}"
        )

    seeded = sum(1 for item in results if item.status == "seeded")
    planned = sum(1 for item in results if item.status == "planned")
    skipped = sum(1 for item in results if item.status == "skipped")
    console.print(f"summary: seeded={seeded}, planned={planned}, skipped={skipped}, total={len(results)}")


@app.command(name="paper-synthesis-generate")
def paper_synthesis_generate(
    paper_slug: str = typer.Argument(..., help="Paper slug for the canonical structured state."),
    markdown_only: bool = typer.Option(
        False,
        "--markdown",
        help="Print compiled markdown only instead of the JSON bundle payload.",
    ),
    manifest_only: bool = typer.Option(
        False,
        "--manifest",
        help="Print structured manifest JSON only instead of the JSON bundle payload.",
    ),
):
    """
    Generate a bounded paper-scoped compiled-knowledge bundle from canonical state and selected run artifacts.
    """
    from src.paper_syntheses.service import generate_paper_synthesis, paper_synthesis_response_payload
    from src.schemas.paper_synthesis import PaperSynthesisGenerateRequest

    config = load_config()
    vault_path = Path(config.paths.obsidian_vault).expanduser()
    result = generate_paper_synthesis(
        request=PaperSynthesisGenerateRequest(paper_slug=paper_slug),
        vault_path=vault_path,
    )
    _emit_paper_synthesis_cli_result(
        result=result,
        markdown_only=markdown_only,
        manifest_only=manifest_only,
        bundle_payload=paper_synthesis_response_payload(result).model_dump(mode="json"),
    )


@app.command(name="paper-synthesis-show")
def paper_synthesis_show(
    synthesis_id: str = typer.Argument(..., help="Paper synthesis bundle id."),
    markdown_only: bool = typer.Option(
        False,
        "--markdown",
        help="Print compiled markdown only instead of the JSON bundle payload.",
    ),
    manifest_only: bool = typer.Option(
        False,
        "--manifest",
        help="Print structured manifest JSON only instead of the JSON bundle payload.",
    ),
):
    """
    Load an existing paper-scoped compiled-knowledge bundle.
    """
    from src.paper_syntheses.service import get_paper_synthesis, paper_synthesis_response_payload

    result = get_paper_synthesis(synthesis_id)
    _emit_paper_synthesis_cli_result(
        result=result,
        markdown_only=markdown_only,
        manifest_only=manifest_only,
        bundle_payload=paper_synthesis_response_payload(result).model_dump(mode="json"),
    )


@app.command(name="paper-synthesis-list")
def paper_synthesis_list():
    """
    List saved paper-scoped compiled-knowledge bundles.
    """
    from src.paper_syntheses.service import paper_synthesis_list_response

    _emit_json(paper_synthesis_list_response().model_dump(mode="json"))


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask the RAG agent")
):
    """
    [v3.0] Query the local RAG knowledge base (storage/rag/).
    """
    from src.config import load_config
    from src.agents.indexer_agent import IndexerAgent
    from src.agents.adapter import OllamaModelAdapter

    config = load_config()
    if not config.agents.enabled:
        console.print("[yellow]⚠️ Agents are disabled in config.[/yellow]")
        return
        
    console.print(f"[bold cyan]🤔 User: {question}[/bold cyan]")
    
    try:
        # 1. Retrieve
        indexer = IndexerAgent(collection_name="paperpipe_rag") 
        # Note: IndexerAgent initializes adapter internally too, careful with resource usage? 
        # Ollama is stateless HTTP, so it's fine.
        
        with console.status("[bold green]🔍 Searching Knowledge Base...[/bold green]"):
            docs = indexer.query(question, n_results=5)
        
        if not docs:
            console.print("[red]❌ No relevant documents found.[/red]")
            return
            
        console.print(f"   📄 Found {len(docs)} relevant chunks.")
        
        # 2. Generate
        context = "\n\n".join(docs)
        prompt = f"""
You are a helpful research assistant for the PaperPipe system.
Answer the user's question based ONLY on the provided context from scientific papers.
If the answer is not in the context, say "I cannot find the answer in the indexed papers."

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""
        
        adapter = OllamaModelAdapter(model_name=config.agents.main_model)
        
        with console.status("[bold green]🧠 Thinking...[/bold green]"):
            result = adapter.generate(prompt)
            
        console.print(f"\n[bold]🤖 Answer:[/bold]\n{result.text}\n")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()

# 7. Export Manager (Phase 2)
@app.command()
def export(
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="Overwrite existing files in Obsidian"),
):
    """
    [Phase 2] Export APPROVED/INDEXED papers to Obsidian Vault.
    Generates Markdown files with Frontmatter and Analysis.
    """
    from src.exporter import run_export
    
    console.print(f"[bold cyan]📤 Starting Export to Obsidian...[/bold cyan]")
    if overwrite:
        console.print("[yellow]⚠️  Overwrite Mode: ON[/yellow]")
        
    run_export(overwrite=overwrite)
    
    console.print("[bold green]✅ Export Complete.[/bold green]")


# 8. Profile Management (Milestone 4)
@app.command(name="profiles")
def profiles_chat(
    target_id: str = typer.Argument(None, help="Target Profile ID (optional, will ask if missing)"),
    prompt: str = typer.Argument(None, help="Natural language request (optional, will ask if missing)")
):
    """
    [v3.0] Chat with the profile patch assistant to update search profiles.
    """
    try:
        from src.profiles.profile_store import (
            ProfileRevisionConflictError,
            load_profiles,
            upsert_profile,
        )
        from src.profiles.profile_metadata import is_research_dna_projection_profile
        from src.profiles.patch_apply import apply_patch
        from src.profiles.risk_rules import validate_profile
        from src.agents.profile_chat_agent import ProfileChatAgent
        
        # 1. Load Profiles
        config = load_profiles()
        if not config.profiles:
            console.print("[yellow]⚠️ No profiles found. Please create one manually first in config/profiles.yaml[/yellow]")
            return

        # 2. Select Profile
        selected_profile = None
        if target_id:
            for p in config.profiles:
                if p.id == target_id:
                    selected_profile = p
                    break
        
        if not selected_profile:
            console.print("[bold cyan]📚 Select a Profile to Update:[/bold cyan]")
            for i, p in enumerate(config.profiles, 1):
                console.print(f" {i}. [bold]{p.id}[/bold] ({p.title})")
            
            choice = typer.prompt("Enter number or ID")
            try:
                # Try as index
                idx = int(choice) - 1
                if 0 <= idx < len(config.profiles):
                    selected_profile = config.profiles[idx]
            except ValueError:
                # Try as ID
                for p in config.profiles:
                    if p.id == choice.strip():
                        selected_profile = p
                        break
        
        if not selected_profile:
            console.print("[bold red]❌ Invalid profile selected.[/bold red]")
            return

        if is_research_dna_projection_profile(selected_profile):
            console.print(
                "[bold yellow]⚠️ This profile is a ResearchDNA compatibility projection and is read-only here.[/bold yellow]"
            )
            console.print("[dim]Update the source Research DNA and re-run `research-dna project-profile` instead.[/dim]")
            return

        console.print(f"\n[bold green]✅ Selected: {selected_profile.title} ({selected_profile.id})[/bold green]")
        
        # 3. Get User Request
        if not prompt:
            prompt = typer.prompt("💬 What would you like to change?")

        # 4. Agent Generation
        agent = ProfileChatAgent()
        with console.status("[bold green]🤖 Profile assistant is thinking...[/bold green]"):
            patch_request = agent.generate_patch(selected_profile, prompt)
            
        # 5. Dry Run & Validation
        try:
            new_profile = apply_patch(selected_profile, patch_request)
            risk_errors = validate_profile(new_profile)
        except Exception as e:
            console.print(f"[bold red]❌ Patch Application Failed:[/bold red] {e}")
            return

        # 6. Show Diff
        console.print("\n[bold]📝 Proposed Changes:[/bold]")
        
        # Simple Diff Display
        import difflib
        old_json = selected_profile.model_dump_json(indent=2)
        new_json = new_profile.model_dump_json(indent=2)
        
        diff = difflib.unified_diff(
            old_json.splitlines(), 
            new_json.splitlines(), 
            lineterm="",
            fromfile="Current",
            tofile="Proposed"
        )
        
        has_changes = False
        for line in diff:
            has_changes = True
            if line.startswith('+') and not line.startswith('+++'):
                console.print(line, style="green")
            elif line.startswith('-') and not line.startswith('---'):
                console.print(line, style="red")
            else:
                console.print(line, style="dim")
                
        if not has_changes:
            console.print("[yellow]⚠️ No changes proposed (Agent likely rejected request or request was trivial).[/yellow]")
            return

        # 7. Show Risks
        if risk_errors:
            console.print("\n[bold red]🚫 RISK VIOLATIONS DETECTED:[/bold red]")
            for err in risk_errors:
                console.print(f" - {err}")
            console.print("[bold red]The profile assistant refuses to save risky profiles.[/bold red]")
            return

        # 8. Confirmation
        if typer.confirm("\n🚀 Apply these changes?"):
            # Update in-memory list
            for i, p in enumerate(config.profiles):
                if p.id == selected_profile.id:
                    config.profiles[i] = new_profile
                    break
            
            # Save
            try:
                upsert_profile(new_profile, expected_revision=selected_profile.revision)
            except ProfileRevisionConflictError as exc:
                console.print("[bold red]❌ Profile changed on disk while you were editing it.[/bold red]")
                console.print(f"[dim]{exc}[/dim]")
                console.print("[dim]Reload the profile and retry so you review the latest diff first.[/dim]")
                return
            console.print("[bold green]✅ Profile Updated & Saved![/bold green]")
        else:
            console.print("[yellow]❌ Changes discarded.[/yellow]")

    except Exception as e:
         console.print(f"[bold red]❌ Error: {e}[/bold red]")
         import traceback
         traceback.print_exc()

@app.command(name="audit")
def profiles_audit(
    days: int = typer.Option(7, help="Lookback window in days")
):
    """
    [v3.0] Audit profiles for performance issues (limit hits) & Auto-Fix.
    """
    from src.profiles.profile_store import (
        ProfileRevisionConflictError,
        load_profiles,
        upsert_profile,
    )
    from src.profiles.profile_metadata import is_research_dna_projection_profile
    from src.profiles.patch_apply import apply_patch
    from src.profiles.risk_rules import validate_profile
    from src.agents.profile_chat_agent import ProfileChatAgent
    from src.db_utils import get_profile_stats
    
    config = load_profiles()
    if not config.profiles:
        console.print("[yellow]⚠️ No profiles to audit.[/yellow]")
        return
        
    console.print(f"[bold]🔍 Auditing {len(config.profiles)} profiles (Last {days} days)...[/bold]")
    agent = None # Lazy load
    
    issues_found = 0
    
    for profile in config.profiles:
        if is_research_dna_projection_profile(profile):
            console.print(f"[dim]Skipping ResearchDNA projection profile: {profile.id}[/dim]")
            continue
        stats = get_profile_stats(profile.id, days=days)
        if not stats:
            continue
            
        total_runs = len(stats)
        limit_hits = sum(1 for s in stats if s['limit_hit'])
        hit_ratio = limit_hits / total_runs
        avg_items = sum(s['items_fetched'] for s in stats) / total_runs
        
        # Threshold: > 50% runs hit limit
        if hit_ratio > 0.5:
            issues_found += 1
            console.print(f"\n[bold red]🚨 ISSUE: {profile.title} ({profile.id})[/bold red]")
            console.print(f"   - Limit Hit Rate: {hit_ratio:.1%} ({limit_hits}/{total_runs} runs)")
            console.print(f"   - Avg Fetched: {avg_items:.1f} (Limit: {profile.limits.max_results_per_run})")
            
            if typer.confirm("   🛠️  Ask profile assistant to fix this?"):
                if not agent: agent = ProfileChatAgent()
                
                with console.status("   🤖 Generating Fix..."):
                    patch = agent.suggest_audit_fix(profile, hit_ratio, days)
                    
                # Dry Run
                try:
                    new_profile = apply_patch(profile, patch)
                    validate_profile(new_profile) # Ignore return, just check assumption
                except Exception as e:
                    console.print(f"[red]   ❌ Fix generation failed: {e}[/red]")
                    continue
                    
                # Show Diff
                console.print("\n   [bold]Proposed Fix:[/bold]")
                import difflib
                old_json = profile.model_dump_json(indent=2)
                new_json = new_profile.model_dump_json(indent=2)
                diff = difflib.unified_diff(
                    old_json.splitlines(), new_json.splitlines(), lineterm="", fromfile="Current", tofile="Fix"
                )
                for line in diff:
                     color = "green" if line.startswith('+') else "red" if line.startswith('-') else "dim"
                     if not line.startswith('---') and not line.startswith('+++'):
                         console.print(f"   {line}", style=color)
                         
                if typer.confirm("   🚀 Apply Fix?"):
                    # Apply
                    for i, p in enumerate(config.profiles):
                        if p.id == profile.id:
                            config.profiles[i] = new_profile
                            break
                    try:
                        upsert_profile(new_profile, expected_revision=profile.revision)
                    except ProfileRevisionConflictError as exc:
                        console.print("   [red]❌ Fix not saved because the profile changed on disk.[/red]")
                        console.print(f"   [dim]{exc}[/dim]")
                        console.print("   [dim]Reload and rerun audit before applying another fix.[/dim]")
                        continue
                    console.print("   ✅ Fixed & Saved.")
                else:
                    console.print("   💨 Skipped.")
        else:
             # Healthy
             pass
             
    if issues_found == 0:
        console.print("\n[bold green]✅ All profiles healthy![/bold green]")


@artifact_history_app.command("meeting-pack-review")
def artifact_history_meeting_pack_review(
    pack_id: str = typer.Argument(..., help="Meeting Pack ID"),
    decision: str = typer.Option(..., "--decision", help="accept | reject | correct | escalate"),
    reason_code: str = typer.Option(..., "--reason-code", help="Structured review reason code"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    note: str = typer.Option(..., "--note", help="Human review note"),
    paper_id: str | None = typer.Option(None, "--paper-id", help="Optional linked paper ID"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional linked run ID"),
    dna_id: str | None = typer.Option(None, "--dna-id", help="Optional linked Research DNA ID"),
):
    try:
        feedback = _append_selected_artifact_review_feedback(
            artifact_type="meeting_pack",
            artifact_id=pack_id,
            paper_id=paper_id,
            run_id=run_id,
            dna_id=dna_id,
            decision=decision,
            reason_code=reason_code,
            actor_id=actor_id,
            note=note,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    _emit_json(
        {
            "status": "saved",
            "feedback": feedback.model_dump(mode="json", exclude_none=True),
        }
    )


@artifact_history_app.command("meeting-pack-outcome")
def artifact_history_meeting_pack_outcome(
    pack_id: str = typer.Argument(..., help="Meeting Pack ID"),
    decision: str = typer.Option(..., "--decision", help="reused | reused_after_correction | abandoned | escalated"),
    downstream_use: str = typer.Option(
        ...,
        "--downstream-use",
        help="final_deliverable | supporting_context | follow_on_artifact | human_review_queue | not_used | other",
    ),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    note: str = typer.Option(..., "--note", help="Human outcome note"),
    paper_id: str | None = typer.Option(None, "--paper-id", help="Optional linked paper ID"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional linked run ID"),
    dna_id: str | None = typer.Option(None, "--dna-id", help="Optional linked Research DNA ID"),
    review_feedback_id: str | None = typer.Option(None, "--review-feedback-id", help="Optional linked review feedback ID"),
):
    try:
        outcome = _append_selected_artifact_generation_outcome(
            artifact_type="meeting_pack",
            artifact_id=pack_id,
            paper_id=paper_id,
            run_id=run_id,
            dna_id=dna_id,
            review_feedback_id=review_feedback_id,
            decision=decision,
            downstream_use=downstream_use,
            actor_id=actor_id,
            note=note,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    _emit_json(
        {
            "status": "saved",
            "outcome": outcome.model_dump(mode="json", exclude_none=True),
        }
    )


@artifact_history_app.command("protocol-card-review")
def artifact_history_protocol_card_review(
    protocol_id: str = typer.Argument(..., help="Protocol Card ID"),
    decision: str = typer.Option(..., "--decision", help="accept | reject | correct | escalate"),
    reason_code: str = typer.Option(..., "--reason-code", help="Structured review reason code"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    note: str = typer.Option(..., "--note", help="Human review note"),
    paper_id: str | None = typer.Option(None, "--paper-id", help="Optional linked paper ID"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional linked run ID"),
    dna_id: str | None = typer.Option(None, "--dna-id", help="Optional linked Research DNA ID"),
):
    try:
        feedback = _append_selected_artifact_review_feedback(
            artifact_type="protocol_card",
            artifact_id=protocol_id,
            paper_id=paper_id,
            run_id=run_id,
            dna_id=dna_id,
            decision=decision,
            reason_code=reason_code,
            actor_id=actor_id,
            note=note,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    _emit_json(
        {
            "status": "saved",
            "feedback": feedback.model_dump(mode="json", exclude_none=True),
        }
    )


@artifact_history_app.command("protocol-card-outcome")
def artifact_history_protocol_card_outcome(
    protocol_id: str = typer.Argument(..., help="Protocol Card ID"),
    decision: str = typer.Option(..., "--decision", help="reused | reused_after_correction | abandoned | escalated"),
    downstream_use: str = typer.Option(
        ...,
        "--downstream-use",
        help="final_deliverable | supporting_context | follow_on_artifact | human_review_queue | not_used | other",
    ),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    note: str = typer.Option(..., "--note", help="Human outcome note"),
    paper_id: str | None = typer.Option(None, "--paper-id", help="Optional linked paper ID"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional linked run ID"),
    dna_id: str | None = typer.Option(None, "--dna-id", help="Optional linked Research DNA ID"),
    review_feedback_id: str | None = typer.Option(None, "--review-feedback-id", help="Optional linked review feedback ID"),
):
    try:
        outcome = _append_selected_artifact_generation_outcome(
            artifact_type="protocol_card",
            artifact_id=protocol_id,
            paper_id=paper_id,
            run_id=run_id,
            dna_id=dna_id,
            review_feedback_id=review_feedback_id,
            decision=decision,
            downstream_use=downstream_use,
            actor_id=actor_id,
            note=note,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    _emit_json(
        {
            "status": "saved",
            "outcome": outcome.model_dump(mode="json", exclude_none=True),
        }
    )


@research_dna_app.command("create")
def research_dna_create(
    topic: str = typer.Argument(..., help="Research topic"),
    intent: str = typer.Option(..., "--intent", help="explore | systematic_review | update"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why this DNA is being created"),
    dna_id: str | None = typer.Option(None, "--dna-id", help="Optional explicit DNA ID"),
    title: str | None = typer.Option(None, "--title", help="Optional explicit title"),
    recommended_db: list[str] = typer.Option(None, "--recommended-db", help="Recommended database"),
    available_db: list[str] = typer.Option(None, "--available-db", help="Available database"),
):
    from src.profiles.research_dna_service import create_research_dna

    dna = create_research_dna(
        topic=topic,
        intent=intent,  # type: ignore[arg-type]
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
        dna_id=dna_id,
        title=title,
        recommended_databases=recommended_db or [],
        available_databases=available_db or [],
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("show")
def research_dna_show(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
):
    from src.profiles.research_dna_store import load_research_dna

    dna = load_research_dna(dna_id)
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("runs")
def research_dna_runs(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    limit: int = typer.Option(20, "--limit", min=1, max=100, help="Maximum runs to return"),
):
    from src.profiles.research_dna_service import load_research_dna_run_index

    run_index = load_research_dna_run_index(
        dna_id,
        limit=limit,
    )
    _emit_json(
        run_index.model_dump(
            mode="json",
            exclude_none=False,
            exclude_defaults=False,
            exclude_unset=False,
        )
    )


@research_dna_app.command("resume")
def research_dna_resume(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    variant: str = typer.Option("original", "--variant", help="original | reranked"),
    recent_limit: int = typer.Option(5, "--recent-limit", min=1, max=20, help="Recent decisions to include"),
):
    from src.profiles.research_dna_service import load_research_dna_resume_snapshot

    normalized_variant = variant.strip().lower()
    if normalized_variant not in {"original", "reranked"}:
        raise typer.BadParameter("variant must be 'original' or 'reranked'")

    resume = load_research_dna_resume_snapshot(
        dna_id,
        variant=normalized_variant,  # type: ignore[arg-type]
        recent_limit=recent_limit,
    )
    _emit_json(
        resume.model_dump(
            mode="json",
            exclude_none=False,
            exclude_defaults=False,
            exclude_unset=False,
        )
    )


@research_dna_app.command("approve-pilot")
def research_dna_approve_pilot(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the pilot is approved"),
):
    from src.profiles.research_dna_service import approve_pilot

    dna = approve_pilot(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("update")
def research_dna_update(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    patch_file: Path = typer.Option(..., "--patch-file", exists=True, help="ResearchDNAUpdate JSON/YAML file"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the DNA is being updated"),
):
    from src.profiles.research_dna_schema import ResearchDNAUpdate
    from src.profiles.research_dna_service import update_research_dna

    payload = yaml.safe_load(patch_file.read_text(encoding="utf-8"))
    patch = ResearchDNAUpdate(**payload)
    dna = update_research_dna(
        dna_id,
        patch=patch,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("interview")
def research_dna_interview(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    round: str = typer.Option(..., "--round", help="researcher | librarian"),
    question_id: str = typer.Option(..., "--question-id", help="Stable question ID"),
    question: str = typer.Option(..., "--question", help="Interview question text"),
    answer: str = typer.Option(..., "--answer", help="Interview answer text"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
):
    from src.profiles.research_dna_service import log_interview_response

    dna, interview = log_interview_response(
        dna_id,
        round=round,  # type: ignore[arg-type]
        question_id=question_id,
        question=question,
        answer=answer,
        actor_type="human_cli",
        actor_id=actor_id,
    )
    _emit_json(
        {
            "dna": dna.model_dump(mode="json", exclude_none=True),
            "interview": interview.model_dump(mode="json", exclude_none=True),
        }
    )


@research_dna_app.command("refine")
def research_dna_refine(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    query_version_file: Path = typer.Option(..., "--query-version-file", exists=True, help="QueryVersion JSON/YAML file"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the query is refined"),
):
    from src.profiles.research_dna_schema import QueryVersion
    from src.profiles.research_dna_service import refine_query_version

    payload = yaml.safe_load(query_version_file.read_text(encoding="utf-8"))
    query_version = QueryVersion(**payload)
    dna = refine_query_version(
        dna_id,
        query_version=query_version,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("pilot")
def research_dna_run_pilot(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional explicit pilot run ID"),
):
    from src.profiles.research_dna_service import run_pilot

    pilot_run = run_pilot(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        run_id=run_id,
    )
    _emit_json(pilot_run.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("rerank")
def research_dna_rerank_screening_queue(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
):
    from src.profiles.research_dna_service import materialize_reranked_screening_queue

    rerank = materialize_reranked_screening_queue(
        dna_id,
        run_id=run_id,
        actor_type="human_cli",
        actor_id=actor_id,
    )
    _emit_json(rerank.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("materialize-guidance")
def research_dna_materialize_guidance(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
):
    from src.profiles.research_dna_service import materialize_screening_guidance_artifact

    guidance_artifact = materialize_screening_guidance_artifact(
        dna_id,
        run_id=run_id,
        actor_type="human_cli",
        actor_id=actor_id,
    )
    _emit_json(guidance_artifact.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("guidance-artifact")
def research_dna_screening_guidance_artifact(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
):
    from src.profiles.research_dna_service import load_latest_screening_guidance_artifact

    guidance_artifact = load_latest_screening_guidance_artifact(
        dna_id,
        run_id=run_id,
    )
    _emit_json(guidance_artifact.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("queue")
def research_dna_show_screening_queue(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    variant: str = typer.Option("original", "--variant", help="original | reranked"),
):
    from src.profiles.research_dna_service import load_screening_queue_artifact

    normalized_variant = variant.strip().lower()
    if normalized_variant not in {"original", "reranked"}:
        raise typer.BadParameter("variant must be 'original' or 'reranked'")

    screening_queue = load_screening_queue_artifact(
        dna_id,
        run_id=run_id,
        variant=normalized_variant,  # type: ignore[arg-type]
    )
    _emit_json(screening_queue.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("next")
def research_dna_next_screening_candidate(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    variant: str = typer.Option("original", "--variant", help="original | reranked"),
):
    from src.profiles.research_dna_service import load_next_screening_candidate

    normalized_variant = variant.strip().lower()
    if normalized_variant not in {"original", "reranked"}:
        raise typer.BadParameter("variant must be 'original' or 'reranked'")

    next_candidate = load_next_screening_candidate(
        dna_id,
        run_id=run_id,
        variant=normalized_variant,  # type: ignore[arg-type]
    )
    _emit_json(next_candidate.model_dump(mode="json"))


@research_dna_app.command("session")
def research_dna_screening_session(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    variant: str = typer.Option("original", "--variant", help="original | reranked"),
    recent_limit: int = typer.Option(5, "--recent-limit", min=1, max=20, help="Recent decisions to include"),
):
    from src.profiles.research_dna_service import (
        load_screening_operator_guidance,
        load_screening_session,
    )

    normalized_variant = variant.strip().lower()
    if normalized_variant not in {"original", "reranked"}:
        raise typer.BadParameter("variant must be 'original' or 'reranked'")

    session = load_screening_session(
        dna_id,
        run_id=run_id,
        variant=normalized_variant,  # type: ignore[arg-type]
        recent_limit=recent_limit,
    )
    recommendation, gate = load_screening_operator_guidance(
        dna_id,
        run_id=run_id,
    )
    _emit_json(
        {
            "session": session.model_dump(mode="json"),
            "recommendation": recommendation.model_dump(mode="json", exclude_none=True),
            "gate": gate.model_dump(mode="json", exclude_none=True),
        }
    )


@research_dna_app.command("progress")
def research_dna_screening_progress(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    variant: str = typer.Option("original", "--variant", help="original | reranked"),
):
    from src.profiles.research_dna_service import load_screening_progress_report

    normalized_variant = variant.strip().lower()
    if normalized_variant not in {"original", "reranked"}:
        raise typer.BadParameter("variant must be 'original' or 'reranked'")

    progress = load_screening_progress_report(
        dna_id,
        run_id=run_id,
        variant=normalized_variant,  # type: ignore[arg-type]
    )
    payload = progress.model_dump(
        mode="json",
        exclude_none=False,
        exclude_defaults=False,
        exclude_unset=False,
    )
    # Keep the CLI contract stable for completed sessions where the next candidate is intentionally null.
    payload.setdefault("next_candidate_id", None)
    _emit_json(payload)


@research_dna_app.command("recommend")
def research_dna_screening_recommendation(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
):
    from src.profiles.research_dna_service import load_screening_operator_guidance

    recommendation, _ = load_screening_operator_guidance(
        dna_id,
        run_id=run_id,
    )
    _emit_json(recommendation.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("guidance")
def research_dna_screening_guidance(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
):
    from src.profiles.research_dna_service import load_screening_operator_guidance

    recommendation, gate = load_screening_operator_guidance(
        dna_id,
        run_id=run_id,
    )
    _emit_json(
        {
            "recommendation": recommendation.model_dump(mode="json", exclude_none=True),
            "gate": gate.model_dump(mode="json", exclude_none=True),
        }
    )


@research_dna_app.command("guidance-history")
def research_dna_screening_guidance_history(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    limit: int = typer.Option(20, "--limit", min=1, max=100, help="Maximum guidance history entries to return"),
):
    from src.profiles.research_dna_service import load_screening_guidance_index_artifact

    guidance_index = load_screening_guidance_index_artifact(
        dna_id,
        run_id=run_id,
        limit=limit,
    )
    _emit_json(guidance_index.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("rerank-gate")
def research_dna_rerank_gate(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
):
    from src.profiles.research_dna_service import load_screening_operator_guidance

    _, gate = load_screening_operator_guidance(
        dna_id,
        run_id=run_id,
    )
    _emit_json(gate.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("screen-next")
def research_dna_screen_and_advance(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str | None = typer.Option(None, "--run-id", help="Pilot run ID"),
    latest: bool = typer.Option(False, "--latest", help="Use the latest pilot run for this DNA"),
    candidate_id: str = typer.Option(..., "--candidate-id", help="Screening candidate ID"),
    decision: str = typer.Option(..., "--decision", help="include | exclude | unclear"),
    reason_code: str = typer.Option(..., "--reason-code", help="Structured reason code"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    variant: str = typer.Option("original", "--variant", help="original | reranked"),
    recent_limit: int = typer.Option(5, "--recent-limit", min=1, max=20, help="Recent decisions to include"),
    note: str | None = typer.Option(None, "--note", help="Optional screening note"),
):
    from src.profiles.research_dna_service import (
        load_screening_operator_guidance,
        submit_screening_decision_and_load_session,
    )

    normalized_variant = variant.strip().lower()
    if normalized_variant not in {"original", "reranked"}:
        raise typer.BadParameter("variant must be 'original' or 'reranked'")
    resolved_run_id = _resolve_research_dna_run_id_for_cli(
        dna_id,
        run_id=run_id,
        latest=latest,
    )

    dna, next_candidate, session = submit_screening_decision_and_load_session(
        dna_id,
        run_id=resolved_run_id,
        candidate_id=candidate_id,
        decision=decision,  # type: ignore[arg-type]
        reason_code=reason_code,  # type: ignore[arg-type]
        actor_type="human_cli",
        actor_id=actor_id,
        variant=normalized_variant,  # type: ignore[arg-type]
        recent_limit=recent_limit,
        note=note,
    )
    recommendation, gate = load_screening_operator_guidance(
        dna_id,
        run_id=resolved_run_id,
    )
    _emit_json(
        {
            "dna": dna.model_dump(mode="json", exclude_none=True),
            "screened_candidate_id": candidate_id,
            "decision": decision,
            "reason_code": reason_code,
            "variant": normalized_variant,
            "next_candidate": next_candidate.model_dump(mode="json"),
            "session": session.model_dump(mode="json"),
            "recommendation": recommendation.model_dump(mode="json", exclude_none=True),
            "gate": gate.model_dump(mode="json", exclude_none=True),
        }
    )


@research_dna_app.command("screen-current")
def research_dna_screen_current(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str | None = typer.Option(None, "--run-id", help="Pilot run ID"),
    latest: bool = typer.Option(False, "--latest", help="Use the latest pilot run for this DNA"),
    decision: str = typer.Option(..., "--decision", help="include | exclude | unclear"),
    reason_code: str = typer.Option(..., "--reason-code", help="Structured reason code"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    variant: str = typer.Option("original", "--variant", help="original | reranked"),
    recent_limit: int = typer.Option(5, "--recent-limit", min=1, max=20, help="Recent decisions to include"),
    expected_candidate_id: str | None = typer.Option(None, "--expected-candidate-id", help="Optional current next-candidate guard"),
    note: str | None = typer.Option(None, "--note", help="Optional screening note"),
):
    from src.profiles.research_dna_service import (
        load_screening_operator_guidance,
        screen_current_candidate_and_load_session,
    )

    normalized_variant = variant.strip().lower()
    if normalized_variant not in {"original", "reranked"}:
        raise typer.BadParameter("variant must be 'original' or 'reranked'")
    resolved_run_id = _resolve_research_dna_run_id_for_cli(
        dna_id,
        run_id=run_id,
        latest=latest,
    )

    dna, screened_candidate_id, next_candidate, session = screen_current_candidate_and_load_session(
        dna_id,
        run_id=resolved_run_id,
        decision=decision,  # type: ignore[arg-type]
        reason_code=reason_code,  # type: ignore[arg-type]
        actor_type="human_cli",
        actor_id=actor_id,
        variant=normalized_variant,  # type: ignore[arg-type]
        recent_limit=recent_limit,
        expected_candidate_id=expected_candidate_id,
        note=note,
    )
    recommendation, gate = load_screening_operator_guidance(
        dna_id,
        run_id=resolved_run_id,
    )
    _emit_json(
        {
            "dna": dna.model_dump(mode="json", exclude_none=True),
            "screened_candidate_id": screened_candidate_id,
            "decision": decision,
            "reason_code": reason_code,
            "variant": normalized_variant,
            "next_candidate": next_candidate.model_dump(mode="json"),
            "session": session.model_dump(mode="json"),
            "recommendation": recommendation.model_dump(mode="json", exclude_none=True),
            "gate": gate.model_dump(mode="json", exclude_none=True),
        }
    )


@research_dna_app.command("screening")
def research_dna_submit_screening(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    run_id: str = typer.Option(..., "--run-id", help="Pilot run ID"),
    candidate_id: str = typer.Option(..., "--candidate-id", help="Screening candidate ID"),
    decision: str = typer.Option(..., "--decision", help="include | exclude | unclear"),
    reason_code: str = typer.Option(..., "--reason-code", help="Structured reason code"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    note: str | None = typer.Option(None, "--note", help="Optional screening note"),
):
    from src.profiles.research_dna_service import submit_screening_decision

    dna = submit_screening_decision(
        dna_id,
        run_id=run_id,
        candidate_id=candidate_id,
        decision=decision,  # type: ignore[arg-type]
        reason_code=reason_code,  # type: ignore[arg-type]
        note=note,
        actor_type="human_cli",
        actor_id=actor_id,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("lock")
def research_dna_lock(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the DNA is being locked"),
):
    from src.profiles.research_dna_service import lock_research_dna

    dna = lock_research_dna(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("unlock")
def research_dna_unlock(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the DNA is being unlocked"),
):
    from src.profiles.research_dna_service import unlock_research_dna

    dna = unlock_research_dna(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
    )
    _emit_json(dna.model_dump(mode="json", exclude_none=True))


@research_dna_app.command("project-profile")
def research_dna_project_profile(
    dna_id: str = typer.Argument(..., help="Research DNA ID"),
    actor_id: str = typer.Option(..., "--actor-id", help="Actor ID for audit"),
    reason: str = typer.Option(..., "--reason", help="Why the projection is being materialized"),
    query_version: str | None = typer.Option(None, "--query-version", help="Optional explicit query version"),
    database: str | None = typer.Option(None, "--database", help="Optional explicit database key"),
):
    from src.profiles.research_dna_projection import sync_research_dna_profile

    projection = sync_research_dna_profile(
        dna_id,
        actor_type="human_cli",
        actor_id=actor_id,
        reason=reason,
        query_version_name=query_version,
        database=database,
    )
    _emit_json(projection.model_dump(mode="json", exclude_none=True))


def entrypoint():
    sys.argv = _argv_with_frozen_app_default_command(sys.argv)
    app()


if __name__ == "__main__":
    entrypoint()
