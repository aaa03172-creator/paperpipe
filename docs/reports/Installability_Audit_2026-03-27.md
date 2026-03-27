# Installability Audit (2026-03-27)

Status: active audit report  
Date: 2026-03-27  
Owner: Lattice runtime maintainers  
Purpose: capture the first installability/runtime-shell slice that makes the backend-served UI and runtime log handling behave more like an installable local app without reopening broader packaging or platform work.

## What this slice lands

- `/ui` now prefers the built frontend bundle under `frontend/dist`
- built `/assets/*` files are served by the FastAPI runtime
- `sample.pdf` and `vite.svg` are reachable through the backend-served UI path
- log path handling now uses a centralized `logs_root()` helper
- 2026-03-28 follow-up: config-root policy is now explicit through `config_root()`
- 2026-03-28 follow-up: `PAPERPIPE_CONFIG_DIR` and install-layout-aware config placement are recognized without broad runtime path migration
- 2026-03-28 follow-up: `/health/ready` and `lattice self-test` now report `config_root` writability separately from `config_file` readability

## Why this slice matters

Before this change, `lattice start` launched the backend and opened `/ui`, but the backend-first path could still fall back to source-oriented frontend assets. That was acceptable for development, but it was not a credible installability story for a launcher-first local runtime.

This slice closes the first blocker by making the backend prefer the built frontend shell and by normalizing where runtime logs live.

The 2026-03-28 follow-up keeps that same bounded installability posture. It does not reopen packaging or app-data migration. It only narrows config-root behavior enough that launcher-style runtime checks can distinguish "the config loads" from "the runtime can actually write to the intended config root".

## Included runtime paths

- [backend/main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [src/cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [src/jobs/worker.py](/Users/jangseongjin/paperpipe/src/jobs/worker.py)
- [src/logger.py](/Users/jangseongjin/paperpipe/src/logger.py)
- [src/services/runtime_paths.py](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)
- [src/services/runtime_readiness.py](/Users/jangseongjin/paperpipe/src/services/runtime_readiness.py)

## Verification

- `pytest -q tests/test_ui_shell_api.py tests/test_runtime_paths_logs.py`
- `python3 -m py_compile backend/main.py src/cli.py src/jobs/worker.py src/logger.py src/services/runtime_paths.py`
- 2026-03-28 follow-up:
  - `pytest -q tests/test_runtime_readiness_api.py tests/test_cli_self_test_command.py tests/test_runtime_paths_config.py`
  - PR `#183` CI: `agents-smoke`, `e2e-backend`, `e2e-mock`, `guard` passed

## Follow-up, explicitly out of scope

- cache and OCR path normalization
- RAG and feedback index path normalization
- packaging or installer work
- demo and release docs cleanup
