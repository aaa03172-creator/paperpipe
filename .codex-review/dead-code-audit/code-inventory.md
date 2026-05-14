# Code Inventory

## Area: Backend FastAPI application

Purpose:
Serve Lattice/PaperPipe API, protected browser API facade, static UI, jobs, operational readiness, paper/run/artifact state, and mounted feature routers.
Main files:
`backend/main.py`, `backend/routers/*.py`, `backend/services/job_runner.py`.
Entry points:
`backend.main:app` at `backend/main.py:985`; CLI hidden `serve-backend` in `src/cli.py`; package scripts start via `paperpipe` / `lattice`.
Public exports:
FastAPI routes in `backend/main.py:4758-6070`; router modules included at `backend/main.py:6057-6070`.
Runtime registration mechanism:
FastAPI decorators, `app.include_router(...)`, middleware, static mounts at `backend/main.py:1441-1443`.
Likely dynamic usage:
Route handlers can look unused by name search because FastAPI decorators register them. `/api/*` paths are rewritten/protected by middleware. External callers may use deprecated compatibility routes.
Tests:
Large API coverage under `tests/test_*_api.py`, frontend e2e, backend smoke scripts.
Cleanup risk: High
Notes:
Do not remove route handlers solely because function names are unreferenced.

## Area: Frontend Vite React app

Purpose:
Single-page Lattice UI for triage dashboard, paper notes, workbench, runtime readiness, meeting/method/chart/image/protocol surfaces.
Main files:
`frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/app/pages/*`, `frontend/src/app/components/*`, `frontend/src/app/lib/*`.
Entry points:
`frontend/src/main.tsx:13`; route table in `frontend/src/App.tsx:84-100`.
Public exports:
Component and API/helper exports consumed by route pages and tests.
Runtime registration mechanism:
React Router routes and lazy imports in `frontend/src/App.tsx:5-53`.
Likely dynamic usage:
Page components may appear unused by direct imports because lazy `import(...)` wraps them.
Tests:
Playwright suites in `frontend/e2e`; build/lint scripts in `frontend/package.json`.
Cleanup risk: Medium
Notes:
Types in `frontend/src/app/lib/types.ts` mirror backend contracts; unused frontend types may still document API compatibility.

## Area: CLI and operator scripts

Purpose:
Typer CLI, local app startup, legacy daily slot processing, migration/backfill/eval/check scripts, smoke harnesses.
Main files:
`src/cli.py`, `scripts/*.py`, `scripts/eval/*.py`, `evals/paper_skill_gym/*`.
Entry points:
`pyproject.toml` console scripts `paperpipe` and `lattice`; Typer app at `src/cli.py:85`; many `if __name__ == "__main__"` script entry points.
Public exports:
CLI commands registered by decorators in `src/cli.py`.
Runtime registration mechanism:
Typer decorators, direct shell invocation, GitHub Actions, docs/runbooks.
Likely dynamic usage:
Manual operator scripts and CI workflows are not always imported by Python code.
Tests:
CLI tests under `tests/test_cli_*`, script-specific tests, `.github/workflows/*`.
Cleanup risk: Medium / High
Notes:
Manual probe scripts are safer candidates than documented check/backfill scripts.

## Area: Core runtime modules

Purpose:
Paper fetching, processing, indexing, downloader providers, DB/state, artifacts, LLM providers, personas, Obsidian export, quality gates.
Main files:
`src/processor.py`, `src/db_utils.py`, `src/downloader/*`, `src/fetch/*`, `src/agents/*`, `src/llm_provider.py`, `src/skills/*`.
Entry points:
Backend job runner imports agents/services; CLI imports processing/fetching; worker imports queue and job runner.
Public exports:
`src.downloader`, `src.fetch`, `src.schemas`, `src.skills`, and compatibility packages.
Runtime registration mechanism:
Imports, CLI commands, job worker loop, skill registry, config-driven feature flags.
Likely dynamic usage:
Compatibility packages such as `src/providers/*`, legacy `src/db.py`, and `src/fetchers.py` may be used by external/local scripts.
Tests:
Unit/integration tests across downloader, processor, indexer, jobs, skills, status normalization.
Cleanup risk: High
Notes:
Public modules need deprecation/packaged-user checks before deletion.

## Area: Pydantic schemas and contracts

Purpose:
Typed API payloads, artifact contracts, state models, eval sidecars, frontend mirror contracts.
Main files:
`src/schemas/*.py`, `src/contracts/*.py`, frontend `types.ts`.
Entry points:
Imported by FastAPI response models, services, tests, eval scripts, frontend API normalization.
Public exports:
`src/schemas/__init__.py`; typed frontend exports.
Runtime registration mechanism:
Pydantic validation, FastAPI response models, JSON artifact read/write.
Likely dynamic usage:
Model classes can be referenced through JSON schema, tests, or generated artifacts.
Tests:
Schema and route tests.
Cleanup risk: Medium / High
Notes:
Do not remove schema fields/types without migration impact.

## Area: Jobs and background worker

Purpose:
Queue and execute Deep Read jobs, persist job status/events, stream progress.
Main files:
`src/jobs/queue.py`, `src/jobs/worker.py`, `src/jobs/schemas.py`, `backend/services/job_runner.py`.
Entry points:
`POST /jobs/deepread`; worker loop in `src/jobs/worker.py`; `lattice start` / `serve-worker`.
Public exports:
Job queue classes and schemas.
Runtime registration mechanism:
SQLite queue polling and CLI-launched worker sidecar.
Likely dynamic usage:
Worker is live even though not imported by FastAPI app startup.
Tests:
`tests/test_jobs_*`, `tests/test_worker_job_runner_chain.py`, frontend backend parser worker e2e.
Cleanup risk: High
Notes:
Producer/consumer wiring crosses API, CLI, and worker processes.

## Area: Artifact feature families

Purpose:
Generate/store/serve meeting packs, chart packs, image evidence, method comparisons, paper syntheses, protocol cards, talk packs.
Main files:
`src/meeting_packs/*`, `src/chart_packs/*`, `src/image_evidence/*`, `src/method_comparisons/*`, `src/paper_syntheses/*`, `src/protocol_cards/*`, `src/talk_packs/*`, matching routers.
Entry points:
Mounted routers; frontend pages for all except Talk Pack; CLI for some paper synthesis/research lanes.
Public exports:
Feature service/store functions and schemas.
Runtime registration mechanism:
Router includes, API client calls, generated artifact manifests.
Likely dynamic usage:
Saved artifacts on disk depend on existing readers/writers.
Tests:
Feature API/store/service tests; smoke scripts for talk pack rendering.
Cleanup risk: Medium / High
Notes:
Talk Pack currently looks API/test-only by design.

## Area: Data, fixtures, generated, and vendored material

Purpose:
Goldsets, baselines, snapshots, runtime storage, docs, product/scientific rules, local cache/build outputs.
Main files:
`goldset/`, `baselines/`, `snapshots/`, `storage/`, `rules/`, `docs/`, `frontend/dist`, `node_modules`, `__pycache__`.
Entry points:
Mostly tests/evals/docs; some rules are policy inputs.
Public exports:
None as runtime code, except docs/policy files.
Runtime registration mechanism:
File reads by scripts/evals/tests.
Likely dynamic usage:
Fixtures and snapshots are intentionally low-ref. Generated/cache outputs should not be cleanup targets unless tracked and project-owned.
Tests:
Eval and regression scripts.
Cleanup risk: Medium
Notes:
Tracked `<MagicMock ...>/chroma.sqlite3` paths look like accidental generated artifacts, but are not production code.
