from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

from src.config import load_config
from src.db_utils import get_db_path
from src.meeting_packs.hygiene import select_archive_candidates as select_meeting_pack_archive_candidates
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse
from src.services.fixture_visibility import (
    fixture_structured_state_allowed,
    hidden_fixture_structured_state_paths,
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

QUEUE_HEALTH_STALE_AFTER_SECONDS = 15 * 60
QUEUE_HEALTH_QUEUED_AGE_WARN_AFTER_SECONDS = 15 * 60


def _nearest_existing_parent(path: Path) -> Path:
    current = path.expanduser().resolve(strict=False)
    while not current.exists() and current.parent != current:
        current = current.parent
    return current


def _path_writable_target(path: Path) -> bool:
    target = path if path.exists() else _nearest_existing_parent(path)
    return os.access(target, os.W_OK)


def _safe_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _frontend_roots() -> tuple[Path, Path]:
    frontend_dir = frontend_runtime_dir()
    return frontend_dir / "dist" / "index.html", frontend_dir / "index.html"


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
                "Install runtime dependencies with `python -m pip install -r requirements.txt`."
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
    stale_running_reclaimed_total = _safe_int(metadata.get("stale_running_reclaimed_total")) or 0
    if stale_running_reclaimed_total > 0:
        summary_parts.append(f"stale_running_reclaimed_total={stale_running_reclaimed_total}")
    stale_running_requeued_total = _safe_int(metadata.get("stale_running_requeued_total")) or 0
    if stale_running_requeued_total > 0:
        summary_parts.append(f"stale_running_requeued_total={stale_running_requeued_total}")

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
            "backend runtime imports cleanly",
            "backend runtime dependencies need attention",
            "backend runtime dependencies need attention",
        ),
    ):
        source_name = "backend_entrypoint" if name == "backend_runtime" else name
        summary = _browser_safe_summary_check(
            name=name,
            source_checks=[check for check in [checks_by_name.get(source_name)] if check is not None],
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

    return RuntimeReadinessResponse(
        status=_overall_status_for_checks(summary_checks),
        checks=summary_checks,
    )
