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

## Why this slice matters

Before this change, `lattice start` launched the backend and opened `/ui`, but the backend-first path could still fall back to source-oriented frontend assets. That was acceptable for development, but it was not a credible installability story for a launcher-first local runtime.

This slice closes the first blocker by making the backend prefer the built frontend shell and by normalizing where runtime logs live.

## Included runtime paths

- [backend/main.py](/Users/jangseongjin/paperpipe/backend/main.py)
- [src/cli.py](/Users/jangseongjin/paperpipe/src/cli.py)
- [src/jobs/worker.py](/Users/jangseongjin/paperpipe/src/jobs/worker.py)
- [src/logger.py](/Users/jangseongjin/paperpipe/src/logger.py)
- [src/services/runtime_paths.py](/Users/jangseongjin/paperpipe/src/services/runtime_paths.py)

## Verification

- `pytest -q tests/test_ui_shell_api.py tests/test_runtime_paths_logs.py`
- `python3 -m py_compile backend/main.py src/cli.py src/jobs/worker.py src/logger.py src/services/runtime_paths.py`

## Follow-up, explicitly out of scope

- cache and OCR path normalization
- RAG and feedback index path normalization
- packaging or installer work
- demo and release docs cleanup
