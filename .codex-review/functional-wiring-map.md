# Functional Wiring Map

Review date: 2026-05-10

## Functional area: FastAPI application shell and API bridge

Purpose:
Serve the Lattice/PaperPipe API, static UI shell, auth/beta/private-route guards, `/api/*` browser bridge, request audit, and security headers.
Entry points:
`backend/main.py:920`, `backend/main.py:967`, `backend/main.py:4658`, `backend/main.py:5348`, `backend/main.py:5957`
Main files:
`backend/main.py`, `src/config.py`, `src/services/runtime_paths.py`, `tests/test_api_key_auth.py`, `tests/test_browser_security_headers_api.py`
Downstream dependencies:
FastAPI routers, `src.db_utils`, event log, runtime readiness, artifact helpers, frontend build output.
Upstream callers:
Browser via `frontend/src/app/lib/config.ts:26`, CLI `src/cli.py:2923`, tests and deployment scripts.
Database/schema dependencies:
`jobs`, `papers`, `execution_runs`, `job_events`, `user_actions`, `request_audits`.
External dependencies:
FastAPI, Starlette middleware, SSE, optional Ollama initialization on import.
Config/feature flags:
`LATTICE_API_KEY`, `PAPERPIPE_API_KEY`, beta auth/password/IP/rate-limit envs, CORS/allowed-host envs, `API_DOCS_ENABLED`.
Tests found:
`tests/test_api_key_auth.py`, `tests/test_browser_security_headers_api.py`, `tests/test_health_ready_api.py`, `tests/test_http_exception_sanitizer.py`.
Initial risk level: High
Reason:
The root private routes enforce API keys, but the `/api/*` bridge injects the server-side key after rewriting and can return protected data without caller credentials (`backend/main.py:1249`, `backend/main.py:1252`, `backend/main.py:1305`). Importing the backend also initializes the feedback/Ollama path before any request.

## Functional area: Papers, paper notes, and workbench

Purpose:
Expose paper indexes, note-backed paper details, PDFs, operator state, Obsidian mirror/sync, and frontend paper-note/workbench views.
Entry points:
`backend/main.py:5496`, `backend/main.py:5524`, `backend/main.py:5588`, `backend/routers/paper_notes.py:2140`, `backend/routers/paper_notes.py:2150`, `backend/routers/paper_notes.py:2302`, `frontend/src/App.tsx:86`
Main files:
`backend/main.py`, `backend/routers/paper_notes.py`, `backend/routers/obsidian.py`, `src/schemas/paper_notes.py`, `frontend/src/app/pages/PaperNotesListPage.tsx`, `frontend/src/app/pages/PaperNoteDetailPage.tsx`, `frontend/src/app/pages/AnalysisWorkbench.tsx`, `frontend/src/app/lib/api.ts`.
Downstream dependencies:
Obsidian vault, structured state under `.pp`, artifacts root, runtime DB, access-summary helpers.
Upstream callers:
Frontend routes `/papers`, `/papers/:slug`, `/workbench/:paperId`; API client calls in `frontend/src/app/lib/api.ts:821`, `frontend/src/app/lib/api.ts:981`, `frontend/src/app/lib/api.ts:1018`.
Database/schema dependencies:
`papers` columns are read defensively in `backend/main.py:1824`; operator state comes from artifacts/notes and DB-backed summaries.
External dependencies:
Filesystem vault/PDFs, optional institutional link generation.
Config/feature flags:
`paths.obsidian_vault`, `paths.library_dir`, path masking flags.
Tests found:
`tests/test_paper_notes_api.py`, `tests/test_papers_api.py`, `frontend/e2e/backend.spec.ts`, frontend mock/visual tests.
Initial risk level: Medium
Reason:
Core routes are wired and tested, but persisted note/access links lack a complete rendered URL scheme allowlist (`backend/routers/paper_notes.py:1402`, `frontend/src/app/pages/PaperNoteDetailPage.tsx:2360`), and frontend read fallback can display mock data after real backend failures (`frontend/src/app/lib/config.ts:12`).

## Functional area: Deep Read jobs, queue, worker, events, and artifacts

Purpose:
Enqueue deep-read jobs, claim and execute them in a worker, persist run/job/event state, write artifacts and progress logs, and stream SSE updates.
Entry points:
`backend/main.py:5682`, `src/jobs/queue.py:67`, `src/jobs/worker.py:29`, `backend/services/job_runner.py:989`, `backend/main.py:5895`
Main files:
`src/jobs/queue.py`, `src/jobs/worker.py`, `src/jobs/schemas.py`, `backend/services/job_runner.py`, `src/services/event_log.py`, `src/services/stale_jobs.py`, `src/db_utils.py`.
Downstream dependencies:
Ingest, indexer, reader, stats verifier, note writer, visual evidence ledger, claimset coverage focus, deepread handoff artifacts.
Upstream callers:
Frontend API client `frontend/src/app/lib/api.ts:1570`; worker CLI `src/cli.py:2935`; e2e fake worker.
Database/schema dependencies:
`jobs` from `src/db_utils.py:67`, `execution_runs` from `src/db_utils.py:111`, `job_events`, `user_actions`, `review_queue`.
External dependencies:
Ollama/local model adapter, optional cloud table fallback/OpenAI, filesystem artifacts/logs.
Config/feature flags:
`LATTICE_MAX_QUEUED_JOBS`, `LATTICE_MAX_CONCURRENT_JOBS`, `PAPERPIPE_E2E_ENABLE_PARSER_WORKER`, ingest/parser/cloud flags, LLM mode.
Tests found:
`tests/test_worker_job_runner_chain.py`, `tests/test_jobs_api_smoke.py`, `tests/test_jobs_events_persistence.py`, `tests/test_worker_heartbeat.py`, `tests/test_job_runner_ingest_backend.py`.
Initial risk level: Medium
Reason:
End-to-end worker smoke passed, but failed jobs can lose artifact discoverability unless `artifact_dir` is persisted, and cloud table fallback needs explicit privacy lane handling.

## Functional area: Artifact family routers and stores

Purpose:
Generate/list/fetch file-backed meeting packs, method comparisons, chart packs, image evidence, protocol cards/attachments, talk packs, and paper syntheses.
Entry points:
`backend/routers/meeting_packs.py:62`, `backend/routers/method_comparisons.py:43`, `backend/routers/chart_packs.py:28`, `backend/routers/image_evidence.py:34`, `backend/routers/protocol_cards.py:98`, `backend/routers/paper_syntheses.py:68`, `backend/routers/talk_packs.py:27`
Main files:
Feature routers under `backend/routers/`, schemas under `src/schemas/`, services/stores under `src/*_packs`, `src/image_evidence`, `src/protocol_cards`, `src/protocol_attachments`, `src/paper_syntheses`.
Downstream dependencies:
Runtime artifact roots, Obsidian vault, structured states, generated markdown/CSV/SVG/PPTX/source files.
Upstream callers:
Frontend routes in `frontend/src/App.tsx:88`, `frontend/src/App.tsx:90`, `frontend/src/App.tsx:92`, `frontend/src/App.tsx:94`, `frontend/src/App.tsx:96`; API client calls in `frontend/src/app/lib/api.ts:1201` through `frontend/src/app/lib/api.ts:1474`.
Database/schema dependencies:
Mostly file-backed; some flows read paper/note state from vault/DB.
External dependencies:
Local filesystem, optional MarkItDown/doc parsing for protocol attachments, chart rendering.
Config/feature flags:
Artifact root envs, protocol attachment max bytes, vault path.
Tests found:
`tests/test_meeting_packs_api.py`, `tests/test_method_comparisons_api.py`, `tests/test_chart_packs_api.py`, `tests/test_image_evidence_api.py`, `tests/test_protocol_attachments_api.py`, `tests/test_paper_syntheses_api.py`, frontend e2e specs.
Initial risk level: High
Reason:
Most routes are registered, but Image Evidence accepts caller-supplied path-like IDs and writes outside the configured root (`src/schemas/image_evidence.py:240`, `src/image_evidence/store.py:17`). Artifact run routes with non-final `{paper_id:path}` can also misparse slash-bearing paper IDs.

## Functional area: Skills API and approved local skills

Purpose:
Expose gated skill actions for note-local extraction, citation validation, and critical appraisal.
Entry points:
`backend/routers/skills.py:12`, `src/skills/router.py:7`, `src/skills/runner.py`
Main files:
`src/skills/policy.py`, `src/skills/runner.py`, `src/skills/storage.py`, `src/schemas/skills.py`, `config/skills_policy.yaml`.
Downstream dependencies:
Obsidian notes, structured state, artifacts, OpenAlex, Docker sandbox for configured appraisal actions.
Upstream callers:
Frontend API client `frontend/src/app/lib/api.ts:1532`; tests and future UI actions.
Database/schema dependencies:
`user_actions` best-effort logging; structured note state JSON.
External dependencies:
OpenAlex/network only when policy allows, optional Docker, optional MarkItDown.
Config/feature flags:
`PAPERPIPE_SKILLS_POLICY_PATH`, `config/skills_policy.yaml`, action policies.
Tests found:
`tests/test_skills_api.py`, `tests/test_skill_state_contract.py`, `tests/test_skill_state_contract.py`.
Initial risk level: Low
Reason:
The API is thin and policy-gated; no confirmed missing registration found in this pass.

## Functional area: Downloads watcher and paper intake

Purpose:
Watch downloads, match PDFs to candidate papers, move matched files into storage, and enqueue manual review for ambiguous/unmatched PDFs.
Entry points:
`src/downloads_watcher.py:347`, `src/downloads_watcher.py:373`, CLI watch commands in `src/cli.py`.
Main files:
`src/downloads_watcher.py`, `src/db_utils.py`, `scripts/init_db.py`, tests.
Downstream dependencies:
Runtime DB `papers` and `review_queue`, filesystem downloads/library paths.
Upstream callers:
CLI watch-downloads command and watchdog events.
Database/schema dependencies:
`review_queue` from `scripts/init_db.py:81`, `papers`, FK enforcement in `src/db_utils.py:233`.
External dependencies:
watchdog filesystem events.
Config/feature flags:
`paths.downloads_watch_dir`, `paths.pdf_storage_dir`, `paths.library_dir`.
Tests found:
`tests/test_downloads_watcher.py`, `tests/test_db_utils_download_attempts.py`, `tests/test_watcher_logic.py`.
Initial risk level: High
Reason:
Unmatched PDFs use a sentinel `paper_id` that conflicts with the canonical FK-backed review queue, and browser temp-file rename handling is only partially wired.

## Functional area: Frontend application shell and API client

Purpose:
Render Vite/React routes for triage, paper notes, workbench, artifact review pages, runtime readiness, and call backend endpoints through the `/api` prefix.
Entry points:
`frontend/src/main.tsx`, `frontend/src/App.tsx:74`, `frontend/src/app/lib/api.ts:387`
Main files:
`frontend/src/App.tsx`, `frontend/src/app/lib/api.ts`, `frontend/src/app/lib/types.ts`, page components under `frontend/src/app/pages`, `frontend/src/app/components/ArtifactPanel.tsx`.
Downstream dependencies:
Backend API, mock fixtures, SSE endpoint, PDF worker.
Upstream callers:
Browser users and Playwright tests.
Database/schema dependencies:
Backend response contracts only; no direct DB access.
External dependencies:
React, Vite, React Router, PDF viewer.
Config/feature flags:
`VITE_FORCE_MOCK`, `VITE_STRICT_API`, `VITE_AUTO_MOCK_FALLBACK`, `/api` prefix.
Tests found:
Frontend build, `frontend/e2e/*.spec.ts`, backend contract tests.
Initial risk level: Medium
Reason:
Build passes and routes match many backend endpoints, but the frontend paper synthesis contract omits `visual_evidence_ledger`, read mock fallback is too broad, and meeting-pack generation can return mock success for a write path despite docs requiring a live backend.

## Functional area: Research DNA and profiles

Purpose:
Manage research DNA/project-profile flows, screening queues, rerank/guidance artifacts, profile projection, and pilot runs.
Entry points:
`backend/main.py:4711`, `backend/main.py:4732`, `backend/main.py:4807`, `backend/main.py:4827`, `backend/main.py:5125`
Main files:
`backend/main.py`, `src/profiles/research_dna_service.py`, `src/profiles/research_dna_store.py`, `src/schemas/research_dna.py`.
Downstream dependencies:
Profile store, screening queue artifacts, fetch/ranking logic.
Upstream callers:
API clients and tests; no primary frontend route found in `frontend/src/App.tsx`.
Database/schema dependencies:
File-backed profile/research DNA state; may read papers/fetch sources.
External dependencies:
Search/fetch providers depending on configuration.
Config/feature flags:
Profile/research DNA config and source config.
Tests found:
`tests/test_research_dna_api.py`, `tests/test_research_dna_service.py`, `tests/test_research_dna_store.py`, `tests/test_research_dna_projection.py`.
Initial risk level: Medium
Reason:
Routes are registered and tests exist, but this was only partially traced because it is not currently a first-class frontend route in this app shell.

## Functional area: Database schema, runtime paths, and config

Purpose:
Own local runtime storage roots, SQLite tables/migrations, config defaults, and package entry points.
Entry points:
`src/db_utils.py:55`, `scripts/init_db.py:18`, `src/services/runtime_paths.py:74`, `src/config.py:343`
Main files:
`src/db_utils.py`, `scripts/init_db.py`, `src/db.py`, `src/services/runtime_paths.py`, `src/config.py`, `pyproject.toml`.
Downstream dependencies:
All backend and worker routes, CLI commands, frontend e2e runtime scripts.
Upstream callers:
API startup, CLI bootstrap, tests, scripts.
Database/schema dependencies:
Canonical `papers`, `review_queue`, jobs/events/user actions, optional operational columns.
External dependencies:
SQLite and local filesystem.
Config/feature flags:
`PAPERPIPE_HOME`, `PAPERPIPE_STORAGE_DIR`, `PAPERPIPE_DB_PATH`, `PAPERPIPE_CONFIG_PATH`, `PAPERPIPE_INSTALL_LAYOUT`.
Tests found:
`tests/test_db_schema_compat.py`, `tests/test_db_path_alignment.py`, `tests/test_runtime_paths_*.py`, `tests/test_config_*.py`.
Initial risk level: Medium
Reason:
Compatibility helpers are broad, but the watcher/review queue path exposes a canonical-schema mismatch.

## Functional area: Operational maintenance and backfill scripts

Purpose:
Provide dry-run-first local maintenance commands for operational repair, legacy cleanup, database backfills, artifact history review, parser/eval inventories, and release/runtime verification.
Entry points:
`scripts/backfill_operational_outputs.py:150`, `scripts/backfill_analysis.py:359`, `scripts/archive_legacy_failed_jobs.py:157`, `scripts/eval/check_artifact_history_promotion_gate.py:245`, `scripts/eval/check_artifact_history_capture_candidates.py:454`, `scripts/eval/inventory_parser_eval_artifacts.py:352`
Main files:
`scripts/backfill_operational_outputs.py`, `scripts/backfill_analysis.py`, `scripts/archive_legacy_failed_jobs.py`, `scripts/eval/check_artifact_history_promotion_gate.py`, `scripts/eval/check_artifact_history_capture_candidates.py`, `scripts/eval/inventory_parser_eval_artifacts.py`, `src/services/runtime_paths.py`.
Downstream dependencies:
SQLite state DB, Obsidian vault files, exporter, job queue, artifact review/outcome JSONL logs, snapshot output directories, runtime path helpers.
Upstream callers:
Operators invoking scripts manually or from smoke/verification lanes.
Database/schema dependencies:
`papers`, `jobs`, `job_failures_archive`, artifact review/outcome JSONL logs.
External dependencies:
Filesystem, optional LLM provider for `backfill_analysis.py`, optional frontend/runtime smoke prerequisites for some scripts.
Config/feature flags:
`PAPERPIPE_HOME`, `PAPERPIPE_STORAGE_DIR`, `PAPERPIPE_DB_PATH`, `PAPERPIPE_ARTIFACT_REVIEW_FEEDBACK_LOG_PATH`, `PAPERPIPE_ARTIFACT_GENERATION_OUTCOME_LOG_PATH`, Obsidian vault config.
Tests found:
`tests/test_artifact_history_promotion_gate.py`, `tests/test_artifact_history_capture_candidates.py`, `tests/test_parser_eval_artifact_inventory.py`, `tests/test_runtime_paths_cache.py`, `tests/test_config_install_layout_paths.py`, `tests/test_backfill_operational_outputs.py`.
Initial risk level: Low
Reason:
Most reviewed eval/runtime scripts are dry-run or snapshot-only and their tests pass. The operational markdown backfill path now resolves persisted `obsidian_path` values through `resolve_vault_relative_path()` and has regression coverage for escaping stored note paths.
