# Findings

## Finding 1: Workspace contains live provider secrets

Severity: P1
Confidence: High
Status: Confirmed
File/line: `.env:1-2`; `.gitignore:29`
Category: Security
Issue:
The local workspace contains real-looking provider API keys in `.env`. The file is ignored by git, but it is still present in the project directory.
Evidence:
The security review found `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` assignments in `.env:1-2`; `.gitignore` ignores `.env`, so the keys are not tracked but remain in the live workspace. Values were not copied into this report.
Why it matters:
Local archive creation, backup sync, debug bundle collection, terminal/session capture, or accidental sharing of the workspace can disclose production-capable secrets.
Suggested fix:
Rotate both keys, replace `.env` with `.env.example` placeholders, and load real secrets from the OS secret store or deployment secret manager.
Suggested test:
Add a secret-scanning check that fails on real-looking provider keys in non-example env/config files while allowing `.env.example` placeholders.
Related files/call sites:
`src/config.py`, README runtime setup sections, deployment secret configuration.

## Finding 2: Cloud table API key is persisted into run artifacts

Severity: P1
Confidence: High
Status: Confirmed
File/line: `backend/services/job_runner.py:410-422`; `backend/services/job_runner.py:1148-1152`
Category: Security
Issue:
`cloud_table_api_key` is copied into `ingest_runtime_options` and then persisted wholesale into `run_meta.json`.
Evidence:
`_resolve_ingest_runtime_options()` includes `cloud_table_api_key` in the returned dict. The deep-read runner later writes `run_meta["ingest_options"] = dict(ingest_runtime_options)` before writing `run_meta.json`.
Why it matters:
Raw runtime artifacts can contain a cloud API key. Even if API responses later sanitize metadata, filesystem artifacts, backups, bug reports, or manual support bundles can leak the secret.
Suggested fix:
Drop secret fields before persistence and store only non-secret state such as `cloud_table_api_key_configured: true`.
Suggested test:
Run a job with `cloud_table_api_key="sk-test-secret"` and assert raw `run_meta.json` does not contain the key or any secret-like value.
Related files/call sites:
`src/agents/ingest_agent.py`, `src/ingest/cloud_table_fallback.py`, `backend/main.py` run metadata endpoints.

## Finding 3: Run IDs can collide and merge unrelated job state

Severity: P1
Confidence: High
Status: Confirmed
File/line: `src/services/identity.py:72-74`; `src/jobs/queue.py:80-82`; `src/db_utils.py:111-123`; `src/services/event_log.py:182-192`
Category: Data integrity
Issue:
`new_run_id()` uses only UTC second precision, so two jobs enqueued in the same second can share one `run_id`.
Evidence:
The queue assigns `run_id = new_run_id()` per enqueue. `execution_runs.run_id` is the primary key. `record_execution_start()` handles conflicts by keeping the existing `paper_id`, trigger, profile, and params via `COALESCE`. A temp DB probe forced a collision and produced two job rows but one execution row for the first paper.
Why it matters:
Events, execution metadata, status, and artifact lookup can point at the wrong paper/run. This is especially risky for concurrent API use and worker recovery.
Suggested fix:
Make run IDs unique beyond seconds, for example `run_<timestamp>_<uuid8>` or UUID-backed IDs.
Suggested test:
Freeze the clock, enqueue two different papers, and assert distinct `jobs.run_id`, distinct `execution_runs` rows, and separated events.
Related files/call sites:
`src/services/runtime_paths.py`, `backend/services/job_runner.py`, job/artifact routes in `backend/main.py`.

## Finding 4: Fresh canonical schema breaks Zotero sync

Severity: P1
Confidence: High
Status: Confirmed
File/line: `scripts/init_db.py:28-55`; `src/db_utils.py:181-190`; `src/db_utils.py:530`; `src/db_utils.py:552-577`
Category: Correctness
Issue:
The canonical `papers` table created by `scripts/init_db.py` does not include `summary`, but `sync_zotero_to_db()` unconditionally selects and inserts `summary`.
Evidence:
`init_db.py` creates `papers` with identity, metadata, state, and asset columns but no `summary`. `db_utils.init_db()` migrates only `download_attempts` and `issues_state`. `sync_zotero_to_db()` then runs `SELECT paper_id, pdf_path, summary FROM papers` and inserts into `summary`. A temp DB probe confirmed `OperationalError: no such column: summary`.
Why it matters:
A freshly initialized runtime database cannot complete Zotero sync, so paper intake can fail before records are inserted.
Suggested fix:
Either add `summary TEXT` to the canonical schema and lightweight migration, or make Zotero sync column-aware like other DB helpers.
Suggested test:
Create an empty temp DB with `scripts.init_db.init_db()`, run `db_utils.init_db()`, then call `sync_zotero_to_db()` and assert it succeeds.
Related files/call sites:
`src/db_utils.py`, `scripts/migrate_legacy.py`, Zotero import paths.

## Finding 5: Phase3 integration workflow uses an unsupported Python version

Severity: P1
Confidence: High
Status: Confirmed
File/line: `.github/workflows/phase3-integration-optin.yml:23-31`; `pyproject.toml:10`
Category: Testing
Issue:
The opt-in Phase3 integration workflow sets up Python 3.11, while package metadata requires Python `>=3.13`.
Evidence:
The workflow uses `python-version: "3.11"` and then runs `pip install -e .`; `pyproject.toml` declares `requires-python = ">=3.13"`.
Why it matters:
The integration gate can fail during installation before exercising tests, making the release-safety lane unreliable.
Suggested fix:
Change the workflow to Python 3.13 or explicitly support and test Python 3.11 in package metadata.
Suggested test:
Dispatch the workflow with `run_phase3_integration=true` and confirm it reaches the test step.
Related files/call sites:
`.github/workflows/*`, `pyproject.toml`, CI status checks.

## Finding 6: Frontend auto mock fallback can mask real backend/auth failures

Severity: P1
Confidence: High
Status: Confirmed
File/line: `frontend/src/app/lib/config.ts:12-15`; `frontend/src/app/lib/api.ts:630-645`; `frontend/src/app/lib/api.ts:809-812`; `frontend/src/app/lib/api.ts:968-974`; `frontend/src/app/pages/PaperNotesListPage.tsx:697-704`
Category: Data integrity
Issue:
`VITE_AUTO_MOCK_FALLBACK` defaults to enabled, and the shared API helper returns mock data after any caught read failure.
Evidence:
`autoMockFallback` is `true` when the env var is unset. `withMockFallback()` catches the fetcher error and returns `mocker()` when fallback is allowed. Papers and paper-notes index calls use this helper, and the notes page installs `result.data` directly into UI state.
Why it matters:
401/403 auth failures, backend regressions, validation failures, and schema errors can become fixture-backed UI data. The banner helps, but the table still renders mock records in places where stale or fake data can mislead review workflows.
Suggested fix:
Only auto-fallback in development for connection/proxy-unavailable cases. Never fallback for reached-backend HTTP errors such as 401, 403, 422, or 5xx.
Suggested test:
Stub `/api/paper-notes` to return 401 and assert no mock notes render and an auth/backend error state is shown.
Related files/call sites:
`frontend/src/app/pages/PaperNotesListPage.tsx`, `frontend/src/app/pages/TriageDashboard.tsx`, API mock fixtures.

## Finding 7: Cloud table fallback sends PDF text without privacy preflight lane metadata

Severity: P2
Confidence: High
Status: Confirmed
File/line: `src/agents/ingest_agent.py:230-242`; `src/ingest/cloud_table_fallback.py:199-214`; `backend/services/job_runner.py:1243-1276`
Category: Security
Issue:
The cloud table fallback can send PDF page text to OpenAI, but the privacy preflight pattern used for clinical extraction is not applied to this lane.
Evidence:
Pass3 cloud fallback calls `_extract_tables_pass3_cloud()` when enabled. `CloudTableFallbackExtractor` sends `page_text` to `client.chat.completions.create()`. The later privacy preflight block only wraps clinical extraction.
Why it matters:
Potentially sensitive PDF text can leave the local runtime without payload classification, blocking behavior, or audit metadata required by the repo's inference payload boundary.
Suggested fix:
Classify selected page text before Pass3, call `build_privacy_preflight_response()`, block according to mode, and record an `inference_lanes.cloud_table_fallback` entry.
Suggested test:
Enable cloud table fallback with privacy preflight in blocking mode and assert no OpenAI request is made and run metadata records the blocked lane.
Related files/call sites:
`src/config.py`, `backend/services/job_runner.py`, `src/ingest/cloud_table_fallback.py`.

## Finding 8: Failed Deep Read artifacts can become orphaned from job state

Severity: P2
Confidence: High
Status: Confirmed
File/line: `backend/services/job_runner.py:1047-1082`; `backend/services/job_runner.py:1792-1820`; `src/jobs/worker.py:156-182`
Category: Reliability
Issue:
After the artifact directory is created, a failure writes failure metadata and handoff artifacts, but the worker persists `artifact_dir` only on success.
Evidence:
The runner creates and writes `run_meta.json` under `artifact_dir`. On exception, it marks run metadata failed and writes handoff artifacts, then returns only `status`, `error`, and `run_id`. The worker stores `artifact_dir` in the job row only for `status == "succeeded"`; the failed update omits it.
Why it matters:
Failed runs can leave useful diagnostics on disk that `/jobs/{id}/bootstrap-meta`, stale incident handling, and DB-based support tooling cannot discover through the job row.
Suggested fix:
Persist `jobs.artifact_dir` immediately after artifact directory creation, or return and store it on failed/cancelled results too.
Suggested test:
Force a failure after artifact creation and assert `jobs.artifact_dir` is populated and bootstrap metadata remains reachable.
Related files/call sites:
`backend/main.py` job bootstrap/artifact endpoints, `src/services/stale_jobs.py`.

## Finding 9: Rendered note and access links lack a URL scheme allowlist

Severity: P2
Confidence: High
Status: Confirmed
File/line: `backend/routers/paper_notes.py:1402-1424`; `backend/routers/paper_notes.py:1439-1450`; `frontend/src/app/pages/PaperNoteDetailPage.tsx:2360-2364`; `frontend/src/app/lib/accessSummary.ts:14-20`; `frontend/src/app/pages/TriageDashboard.tsx:972-978`
Category: Security
Issue:
Persisted note/reference URLs and access-summary URLs are normalized lightly, then rendered directly as browser anchor `href` values.
Evidence:
`_normalize_link_url()` returns most schemes unchanged. Extracted markdown links are appended to `PaperNoteReferenceLink`, and the frontend uses `href={reference.url}`. Access-summary `open_access_url` is also passed through to a link.
Why it matters:
A malicious or malformed note/reference value such as `javascript:...`, `data:...`, or an unexpected local/custom scheme can become clickable in the UI.
Suggested fix:
Add a shared URL sanitizer/allowlist for rendered links, allowing only `http:`, `https:`, approved internal paths, and explicitly approved schemes. Validate in backend schemas where possible.
Suggested test:
Use a note fixture containing `[bad](javascript:alert(1))` and assert it renders as inert text or is omitted.
Related files/call sites:
`frontend/src/app/pages/PaperNoteDetailPage.tsx`, `frontend/src/app/pages/TriageDashboard.tsx`, paper note parsers.

## Finding 10: Artifact routes and stores accept raw path-like IDs without root confinement

Severity: P2
Confidence: Medium
Status: Needs verification
File/line: `backend/main.py:5625`; `backend/main.py:5638`; `backend/main.py:3394-3411`; `src/services/runtime_paths.py:258-267`; `src/services/runtime_paths.py:291-300`; `src/meeting_packs/store.py:12-18`; `src/chart_packs/store.py:13-19`; `src/image_evidence/store.py:17-23`
Category: Security
Issue:
Several artifact APIs and stores compose storage paths from route IDs without a clear allowlist or `relative_to(root)` confinement check.
Evidence:
Some routes use `{paper_id:path}` or raw route values as artifact candidates. Runtime path helpers and store classes append IDs under artifact roots. Similar `base / id / file` construction appears across meeting packs, chart packs, image evidence, talk packs, method comparisons, and paper syntheses. A quick encoded `..` probe did not confirm disclosure, so this remains a needs-verification path-boundary risk.
Why it matters:
If encoded traversal or slash-like values reach a handler, reads can resolve outside the intended artifact root and probe for predictable filenames such as `run_meta.json`, `meeting_pack.json`, or `chart_pack.json`.
Suggested fix:
Normalize every route/store ID through an allowlist such as `^[A-Za-z0-9._-]+$`, reject `.` and `..`, and verify resolved paths remain under the configured root.
Suggested test:
Add API tests using `%2e%2e`, `%2e%2e%2f...`, and slash-containing IDs, asserting 400/404 and no filesystem access outside the configured root.
Related files/call sites:
`src/talk_packs/store.py`, `src/method_comparisons/store.py`, `src/paper_syntheses/store.py`, file-serving endpoints.

## Finding 11: Private API auth is fail-open when no API key is configured

Severity: P2
Confidence: Medium
Status: Needs verification
File/line: `backend/main.py:268-273`; `backend/main.py:475-499`; `backend/main.py:1249-1263`
Category: Security
Issue:
If `LATTICE_API_KEY` and `PAPERPIPE_API_KEY` are unset, middleware bypasses API-key enforcement for private route prefixes.
Evidence:
`_resolve_api_key()` returns an empty string when no env key exists. The private prefix list includes artifacts, jobs, notes, papers, and other data routes. The middleware returns `call_next()` immediately when `expected_key` is empty. This may be intended for local-only use, so deployment exposure needs verification.
Why it matters:
If the backend is reachable beyond trusted loopback without beta auth or a reverse proxy, private read/write routes become unauthenticated.
Suggested fix:
Require an explicit local/dev flag for unauthenticated mode, or fail closed for private routes unless API key or beta auth is configured.
Suggested test:
Start the app with no API key and a non-loopback allowed host, then assert private routes such as `/papers`, `/jobs`, `/artifacts`, and `/paper-notes` return 401/403.
Related files/call sites:
README security setup, deployment/runtime configs, TrustedHost settings.

## Finding 12: `save_paper_state()` silently drops database write failures

Severity: P2
Confidence: High
Status: Confirmed
File/line: `src/db_utils.py:396-408`
Category: Data integrity
Issue:
`save_paper_state()` catches `sqlite3.OperationalError` and suppresses it after schema-dependent write logic.
Evidence:
The helper builds an `INSERT ... ON CONFLICT` statement, commits on success, and has `except sqlite3.OperationalError: pass`.
Why it matters:
Schema drift, migration mistakes, or malformed SQL can cause paper state, PDF paths, feedback JSON, or download attempts to be lost while callers proceed as if persistence succeeded.
Suggested fix:
Rollback and log with enough context at minimum; preferably return a success flag or raise for write paths that callers depend on.
Suggested test:
Use an incompatible `papers` schema and assert the failure is observable and no partial state is treated as success.
Related files/call sites:
Downloader status updates, paper import, review queue flows.

## Finding 13: Downloads watcher can move a partially written PDF

Severity: P2
Confidence: High
Status: Confirmed
File/line: `src/downloads_watcher.py:311-319`; `src/downloads_watcher.py:247-249`; `src/downloads_watcher.py:265-268`
Category: Reliability
Issue:
The filesystem watcher sleeps for a fixed one second after `on_created`, then moves the PDF.
Evidence:
`DownloadsFileHandler.on_created()` waits `time.sleep(1)` before calling `process_downloaded_pdf()`, which can immediately `shutil.move()` the source on DOI or title matches.
Why it matters:
Large or slow browser downloads can still be in progress after one second, resulting in truncated or corrupted files moved into canonical storage.
Suggested fix:
Wait until the file is stable by checking size/mtime across intervals, ignore browser temp extensions, and optionally verify PDF readability before moving.
Suggested test:
Simulate a file that grows after creation and assert the watcher does not move it until stable.
Related files/call sites:
Downloader storage paths, paper PDF status updates.

## Finding 14: `--verify` path depends on undeclared `langgraph`

Severity: P2
Confidence: High
Status: Confirmed
File/line: `src/agents/stats_agent.py:5`; `src/cli.py:4557-4560`; `pyproject.toml:11-39`; `requirements.txt:1`; `.github/workflows/agents-smoke.yml:33`
Category: Testing
Issue:
The stats verification agent imports `langgraph`, but `langgraph` is not declared in normal project dependencies or requirements. CI installs it ad hoc in the agents smoke workflow.
Evidence:
`src/agents/stats_agent.py` imports `from langgraph.graph import StateGraph, END`; the CLI exposes `deepread --verify`; `rg` found no `langgraph` dependency in `pyproject.toml` or `requirements.txt`, only a workflow-local install.
Why it matters:
A normal install can succeed but fail or degrade when verification is requested. CI can miss this because it patches the environment manually.
Suggested fix:
Declare `langgraph` as a runtime dependency or a `verify` optional extra, and make CI install from that declared path.
Suggested test:
Create a clean venv, install the package with the documented verify extra, and run a minimal `paperpipe deepread --verify` import/smoke.
Related files/call sites:
`scripts/run_agents_smoke.sh`, `tests/` verification coverage.

## Finding 15: Packaging installability test is not a clean installability proof

Severity: P2
Confidence: High
Status: Confirmed
File/line: `tests/test_packaging_entrypoints.py:121-127`; `tests/test_packaging_entrypoints.py:143-150`
Category: Testing
Issue:
The “fresh venv” console-script test creates a venv with `--system-site-packages` and installs the wheel with `--no-deps`.
Evidence:
The test includes `--system-site-packages` during venv creation and passes `--no-deps` to `pip install`.
Why it matters:
The test can pass because the developer/CI environment already has dependencies, not because the wheel metadata can install in a clean environment.
Suggested fix:
Create an isolated venv without system site packages, install the wheel with dependencies from declared metadata, and run `paperpipe --help` plus a minimal import smoke.
Suggested test:
Update the existing test to use the clean install flow and fail if package metadata omits a required dependency.
Related files/call sites:
`pyproject.toml`, README install instructions, CI packaging jobs.

## Finding 16: macOS release preflight accepts invalid artifacts as ready

Severity: P2
Confidence: High
Status: Confirmed
File/line: `scripts/release_macos_personal_runtime.py:339-343`; `tests/test_release_macos_personal_runtime.py:34-53`
Category: Reliability
Issue:
Release preflight checks only whether expected artifact paths exist, and the test proves readiness with plain text files standing in for an app bundle and binary.
Evidence:
`evaluate_release_preflight()` sets `app_bundle`, `cli_binary`, and `support_dir` readiness from `Path.exists()`. The test writes `"bundle"` to the app bundle path and `"binary"` to the CLI path, then asserts `local_release_ready is True`.
Why it matters:
Prereq reports can call invalid release artifacts “ready,” delaying failure until codesign, packaging, or user launch.
Suggested fix:
Require `dist/Lattice.app` to be a directory with `Contents/MacOS/Lattice`, require `dist/lattice` to be executable, and validate support directory contents.
Suggested test:
Update tests to use a realistic bundle skeleton and add negative cases for file-not-directory and non-executable binary.
Related files/call sites:
macOS packaging docs, release scripts, CI release checks.

## Finding 17: API error and write-response contracts are inconsistent with the canonical spec

Severity: P2
Confidence: High
Status: Confirmed
File/line: `docs/Lattice_v3_Master_Spec.md:373-376`; `backend/main.py:917-932`; `backend/main.py:5407-5412`; `backend/main.py:5675-5680`; `backend/routers/feedback.py:35-36`; `backend/routers/artifact_generation_outcomes.py:25-26`; `backend/routers/meeting_packs.py:149-150`; `backend/routers/protocol_cards.py:242-243`
Category: Maintainability
Issue:
The canonical spec says errors use `{error_code, message, trace_id, details?}`, but exception handlers emit `{"detail": ...}` and route failures mix strings with structured objects. Several mutation routes also return ad-hoc dicts without response models.
Evidence:
Global HTTP and validation handlers return top-level `detail`. Some route errors put structured objects inside `detail`, while others use plain strings. Multiple write endpoints accept Pydantic request bodies but have no `response_model` or return annotation.
Why it matters:
Clients and generated SDKs must handle multiple incompatible envelopes, and schema drift is easy because OpenAPI cannot lock the write-response shapes.
Suggested fix:
Introduce shared `ErrorResponse` and write-ack schemas under `src/schemas/`, normalize exception handlers, and declare `response_model=` on mutation routes. Keep legacy `detail` temporarily if compatibility requires it.
Suggested test:
Add contract tests for 404, 409 duplicate job, 429 queue full, 422 validation, and mutation-route success responses.
Related files/call sites:
`src/schemas/ops.py`, frontend API error handling, OpenAPI consumers.

## Finding 18: Restore drill validates too little operational state by default

Severity: P3
Confidence: High
Status: Confirmed
File/line: `scripts/check_sqlite_restore_drill.py:13-14`
Category: Testing
Issue:
The default restore drill requires only the `papers` table.
Evidence:
`DEFAULT_REQUIRED_TABLES = ("papers",)`.
Why it matters:
A backup missing jobs, execution runs, job events, or review queue state can pass the default restore drill even though run history and operational recovery would be incomplete.
Suggested fix:
Expand the default required table set to include core canonical and operational tables such as `papers`, `jobs`, `execution_runs`, `job_events`, and `review_queue`.
Suggested test:
Use a fixture backup missing one operational table and assert the default drill fails.
Related files/call sites:
Backup/restore docs and operational runbooks.
