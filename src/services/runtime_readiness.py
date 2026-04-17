from __future__ import annotations

import importlib
import os
from pathlib import Path

from src.config import load_config
from src.db_utils import get_db_path
from src.schemas.ops import RuntimeReadinessCheck, RuntimeReadinessResponse
from src.services.runtime_paths import (
    cache_root,
    config_file_path,
    config_root,
    frontend_runtime_dir,
    logs_root,
    storage_root,
)


def _nearest_existing_parent(path: Path) -> Path:
    current = path.expanduser().resolve(strict=False)
    while not current.exists() and current.parent != current:
        current = current.parent
    return current


def _path_writable_target(path: Path) -> bool:
    target = path if path.exists() else _nearest_existing_parent(path)
    return os.access(target, os.W_OK)


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


def collect_runtime_readiness() -> RuntimeReadinessResponse:
    checks: list[RuntimeReadinessCheck] = []

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
            load_config()
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

    if any(check.status == "error" for check in checks):
        overall = "error"
    elif any(check.status == "warn" for check in checks):
        overall = "degraded"
    else:
        overall = "ok"

    return RuntimeReadinessResponse(status=overall, checks=checks)
