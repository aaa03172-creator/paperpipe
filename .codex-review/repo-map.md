# Repository Map

Review date: 2026-05-10

## Repository Structure

- `backend/`: FastAPI application shell, middleware, root routes, SSE/static UI serving, and operational endpoints.
- `backend/routers/`: Bounded FastAPI routers for paper notes, feedback, artifact outcomes, meeting packs, chart packs, image evidence, protocol cards, skills, and related artifact lanes.
- `backend/services/`: Backend-only runtime worker integration, especially the Deep Read job runner.
- `src/`: Core PaperPipe/Lattice runtime logic, schemas, stores, services, agents, jobs, ingestion, downloader, artifact generation, and CLI.
- `src/schemas/`: Pydantic contracts for API and artifact inputs/outputs.
- `src/jobs/`: SQLite-backed job queue, job schemas, and worker loop.
- `src/services/`: Cross-cutting identity, runtime paths, event log, stale-job handling, readiness, masking, and evaluation services.
- `src/*_packs`, `src/*_cards`, `src/*_evidence`, `src/paper_syntheses`: Artifact-specific service/store/renderer modules.
- `frontend/`: Vite + React Router UI using same-origin `/api/*` calls.
- `frontend/src/app/lib/api.ts`: Browser API client, mock fallback, request helpers, and client-side caches.
- `frontend/src/app/pages/`: UI route pages for papers, paper notes, triage, artifacts, packs, and readiness.
- `tests/`: Backend, CLI, contract, packaging, release, and regression tests.
- `.github/workflows/`: CI and smoke gates.
- `scripts/`: Local verification, smoke, migration, evaluation, packaging, release, and operational scripts.
- `docs/`: Canonical and supporting runtime/product/architecture documentation.

## Stack

- Backend: Python, FastAPI, Pydantic, SQLite, Typer CLI.
- Frontend: Vite, React, React Router, TailwindCSS.
- Runtime state: local SQLite plus file-backed artifacts under configured runtime roots.
- External integrations: OpenAI/Anthropic style LLM providers, Zotero, Semantic Scholar/PubMed/OpenAlex/Crossref-style fetch paths, browser/download watcher flows, optional cloud table extraction.
- Tests/build: `pytest`, frontend `tsc -b && vite build`, GitHub Actions workflows, smoke scripts.

## Major Modules And Responsibilities

- FastAPI runtime: `backend/main.py` plus routers under `backend/routers/`.
- CLI/runtime launcher: `src/cli.py` exposes `paperpipe` and `lattice`.
- Persistent state: `src/db_utils.py`, `src/jobs/queue.py`, `src/services/event_log.py`, artifact stores under `src/*/store.py`, and runtime paths under `src/services/runtime_paths.py`.
- Background jobs: `src/jobs/queue.py`, `src/jobs/worker.py`, and `backend/services/job_runner.py`.
- Paper ingestion and note state: `backend/routers/paper_notes.py`, `src/processor.py`, `src/ingest/*`, `src/exporter.py`.
- Download/file intake: `src/downloads_watcher.py`, `src/downloader/`, `src/providers/`.
- External inference: `src/agents/*`, `src/providers/*`, `src/ingest/cloud_table_fallback.py`, Deep Read privacy preflight paths.
- Frontend surfaces: `/papers`, `/papers/:slug`, `/workbench/:paperId`, `/paper-notes`, `/meeting-packs`, `/method-comparisons`, `/chart-packs`, `/image-evidence`, `/protocol-cards`, `/ready`.

## Production Entry Points

- CLI scripts: `paperpipe = src.cli:entrypoint`, `lattice = src.cli:entrypoint`.
- Backend app: `backend/main.py` (`app = FastAPI(...)`).
- Backend routers: mounted from `backend/main.py`.
- Worker: `src/jobs/worker.py`.
- Frontend app: `frontend/src/main.tsx`, `frontend/src/App.tsx`.
- CI/release gates: `.github/workflows/*`, `scripts/run_backend_api_smoke.sh`, `scripts/run_agents_smoke.sh`, `frontend/package.json`, macOS release scripts.

## Data Stores And Artifacts

- Canonical DB/state: SQLite tables created/migrated in `src/db_utils.py` and `scripts/init_db.py`.
- Job state: `jobs`, `execution_runs`, `job_events`, `request_audits`.
- Paper/user state: `papers`, review queue and feedback-related state.
- File artifacts: Deep Read run directories, bootstrap/run metadata, handoff artifacts, meeting/chart/talk/method/paper synthesis stores.
- User-facing artifacts/exports: paper notes, packs, cards, chart/image evidence, method comparisons, meeting packs.
- Cache/generated outputs: excluded unless tied to findings.

## Auth Model And Trust Boundaries

- API-key middleware in `backend/main.py` protects private prefixes when `LATTICE_API_KEY` or `PAPERPIPE_API_KEY` is configured.
- Same-origin browser `/api/*` rewrite injects the server-side API key for protected calls.
- If no API key is configured, the middleware currently lets requests pass through; this is recorded as a needs-verification deployment risk.
- Frontend calls same-origin `/api/*` by default and has mock fallback paths that can replace failed reads with fixtures.
- Local file roots and artifact IDs are a major trust boundary because many routes expose local runtime files.

## High-Risk Areas

- Authentication and browser secret boundary in `backend/main.py`.
- Private data routes that expose PDFs, artifacts, notes, job logs, and local runtime metadata.
- Secrets in local `.env` and secret persistence into runtime artifacts.
- SQLite schema drift, migration coverage, and write-error handling.
- Job queue/run ID uniqueness, event log upserts, cancellation, stale running recovery, and worker heartbeat behavior.
- Artifact generation stores that perform multi-file writes and cleanup.
- External inference and cloud parser paths that may transmit paper/table content.
- Frontend mock fallback and API cache behavior around real backend failures.
- File upload/download and watcher behavior.
- CI/release packaging gates and installability checks.
- API schema compatibility and canonical error/write response contracts.

## Commands Discovered

- Backend install: `python -m pip install -e . && python -m pip install -r requirements.txt`
- Backend API smoke: `./scripts/run_backend_api_smoke.sh`
- Agents smoke: `./scripts/run_agents_smoke.sh`
- First paper smoke: `./scripts/run_first_paper_smoke.sh`
- Frontend lint: `cd frontend && npm run lint`
- Frontend build: `cd frontend && npm run build`
- Frontend mock verification: `cd frontend && npm run verify:frontend:mock`
- Frontend backend verification: `cd frontend && npm run verify:frontend:backend`
- Full frontend verification: `cd frontend && npm run verify:frontend`
- Focused pytest used in this review: `.venv314/bin/python -m pytest -q tests/test_packaging_entrypoints.py tests/test_release_macos_personal_runtime.py tests/test_identity_helpers.py`

## Subagent Review Allocation

- Architecture/API contracts: FastAPI routes, Pydantic response models, canonical docs, frontend type contract.
- Security/auth/secrets/privacy: `.env`, API key middleware, artifact ID path boundaries, external inference lanes.
- Data model/DB: SQLite schema, migrations, run IDs, event log, paper state writes, restore drill.
- Async/jobs/reliability: job queue, worker, Deep Read runner, cancellation/failure artifacts, downloads watcher.
- Frontend: API client, mock fallback, paper-note and triage link rendering, route state boundaries.
- Tests/CI/release: workflows, package metadata, README install path, packaging tests, release preflight.

## Notes

- Generated, vendored, build output, cache, snapshots, lockfiles, and obvious fixtures were excluded unless directly relevant to a finding.
- Review artifacts are the only files changed for this goal.
