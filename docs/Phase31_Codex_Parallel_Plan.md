# Phase 3.1 Parallel Plan (Codex-first)

## Objective
Accelerate v3.1 by splitting work between Antigravity (integration/ops/GitHub) and Codex (testable core contracts + worker safety).

## Current Backend Reality
- FastAPI skeleton already exists in `backend/main.py`.
- `/jobs/deepread` + SSE endpoint already exist with in-memory queue.
- Routers exist (`/papers`, `/obsidian`, `/feedback`) but contract quality varies.

## Parallel Split
### Antigravity Track
1. Harden API contracts for `/papers`, `/jobs`.
2. Add persistent job queue (SQLite first).
3. Wire SSE events to persisted job lifecycle.
4. GitHub PR operations and merge sequencing.

### Codex Track
1. Worker wrapper contract for `src.processor` (done in this PR).
2. Unit tests for worker success/failure event behavior (done in this PR).
3. Review gate checklist for API/queue/SSE PRs.

## PR Sequence Recommendation
1. PR-A (Codex): `src/worker_runtime.py` + `tests/test_worker_runtime.py`
2. PR-B (Antigravity): Job table + repository layer + API wiring
3. PR-C (Antigravity): SSE endpoint reads persisted job events
4. PR-D (Codex review): end-to-end job flow tests and failure-path hardening

## Acceptance Gates
- Existing CLI path still works.
- Background execution path can call `run_processor_batch()` and receive deterministic result payload.
- Unit tests cover success and failure worker flows.
