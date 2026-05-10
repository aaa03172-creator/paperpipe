## Weak test: Full pipeline integration mostly verifies mocks

Status: Confirmed weak
Test file/line: `tests/test_full_pipeline.py:17`
Related production file/line: `src/processor.py:593`
Problem: Test claims end-to-end pipeline coverage but patches config, fetchers, LLM provider, bibliometric scorer, downloader, Obsidian writer, RIS export, DB save, and processed-state check.
Why this test may not catch real regressions: Real DB writes, Obsidian generation, export formatting, downloader behavior, config validation, and provider wiring can break while the mocks still satisfy call assertions.
What better test should assert: At least one thin integration path should run real persistence/artifact writers against `tmp_path` and assert concrete output/state, while this test is renamed as orchestration unit coverage.
Suggested replacement or improvement: Split into `test_process_daily_slots_orchestrates_provider_calls` and a new `test_process_daily_slots_persists_note_ris_and_state_with_tmp_runtime`.
Risk level: High
Confidence: High

## Weak test: Full integration test uses repo-relative state, print-only checks, and mocked persistence

Status: Confirmed weak
Test file/line: `tests/full_integration_test.py:10`
Related production file/line: `src/watcher.py:90`
Problem: Writes to `tests/integration_env`, mocks `save_paper_state`, uses print messages instead of assertions for note/RIS content, calls `exit(1)`, and cleanup occurs only at the end.
Why this test may not catch real regressions: Persistence can be broken, note/RIS content can be missing expected fields, and failures can leak filesystem state.
What better test should assert: Use `tmp_path`, assert markdown/RIS/PDF outputs and DB state, and rely on pytest assertions/fixtures for cleanup.
Suggested replacement or improvement: Convert to pytest-native fixture-based integration or remove from default collection if it is only a manual smoke.
Risk level: High
Confidence: High

## Weak test: Worker fakes can use stale run_deepread_job signatures

Status: Confirmed weak
Test file/line: `tests/test_worker_heartbeat.py:29`; `tests/test_jobs_api_smoke.py:543`
Related production file/line: `src/jobs/worker.py:108`; `backend/services/job_runner.py:989`
Problem: Production worker passes current kwargs, but tests still use older fake signatures and production code catches broad `TypeError` to retry with stripped kwargs.
Why this test may not catch real regressions: A real `TypeError` inside `run_deepread_job` can be mistaken for compatibility mismatch; tests can pass with fakes that do not match runtime contract.
What better test should assert: Fakes should implement the exact current signature and assert all contract arguments.
Suggested replacement or improvement: Add a signature guard test using `inspect.signature` or update fakes and narrow compatibility fallback.
Risk level: High
Confidence: High

## Weak test: Clinical job-runner tests use partial SimpleNamespace config instead of AppConfig

Status: Confirmed weak
Test file/line: `tests/test_job_runner_clinical_extraction.py:116`, `:247`, `:385`
Related production file/line: `src/config.py:329`; `src/config.py:343`
Problem: Tests monkeypatch `load_config()` with partial namespaces that bypass `AppConfig` validators/defaults.
Why this test may not catch real regressions: Production config validation, path defaults, required sections, and LLM feature defaults can change and break real runs while partial namespaces still work.
What better test should assert: Use a minimal valid `AppConfig` factory, only monkeypatching network/model boundaries deliberately.
Suggested replacement or improvement: Introduce `tests/helpers/config_factory.py` or local factory in the test module.
Risk level: High
Confidence: High

## Weak test: Candidate-selection tests use SimpleNamespace papers

Status: Likely weak
Test file/line: `tests/test_processor_candidate_selection.py:29`
Related production file/line: `src/processor.py:457`; `src/schemas/core.py:62`
Problem: Production scoring has a branch that applies bibliometric scoring only when all candidates are actual `Paper` instances, but fixtures use `SimpleNamespace`.
Why this test may not catch real regressions: Schema coercion, `Paper` defaults, and bibliometric-enabled ranking can drift unseen.
What better test should assert: Candidate factory returns `Paper` objects and includes one enabled-bibliometrics branch.
Suggested replacement or improvement: Replace synthetic candidates with `Paper` schema instances or add explicit tests for both schema and non-schema paths.
Risk level: Medium
Confidence: Medium

## Weak test: Paper listing tests patch _build_index with partial objects

Status: Likely weak
Test file/line: `tests/test_papers_api.py:1813`, `:5832`, `:6300`
Related production file/line: `backend/routers/paper_notes.py:1083`; `src/schemas/paper_notes.py:276`
Problem: Production `_build_index()` returns a full `PaperNoteListResponse`, but tests patch it with `SimpleNamespace(items=...)`.
Why this test may not catch real regressions: Route code can start relying on totals, pagination, filter metadata, generated time, or index path while mocks stay unrealistically minimal.
What better test should assert: Use a minimal valid `PaperNoteListResponse` helper.
Suggested replacement or improvement: Replace partial namespace fixtures with schema-backed factory objects.
Risk level: Medium
Confidence: Medium

## Weak test: Mock-mode Playwright flows can be mistaken for production E2E

Status: Confirmed weak
Test file/line: `frontend/e2e/mock.spec.ts:6`; `frontend/e2e/meeting-pack.mock.spec.ts:3`; `frontend/e2e/method-comparison.mock.spec.ts:3`
Related production file/line: `frontend/playwright.mock.config.ts:22`; `frontend/src/app/lib/api.ts:645`
Problem: Tests exercise forced mock mode and static synthetic data.
Why this test may not catch real regressions: Backend route changes, response shape drift, artifact storage failures, and auth/proxy issues are not exercised.
What better test should assert: Keep as UI fallback tests, but pair every high-risk mock journey with a backend-connected contract/E2E test.
Suggested replacement or improvement: Rename/label as mock UX regressions and add live contract coverage for corresponding APIs.
Risk level: Medium
Confidence: Medium

## Weak test: Runtime readiness coverage is duplicated and drift-prone

Status: Likely weak
Test file/line: `tests/test_health_ready_api.py:6`; `tests/test_runtime_readiness_api.py:14`; `frontend/e2e/backend.gated.spec.ts:3`
Related production file/line: `backend/main.py:4784`; `src/services/runtime_readiness.py:1837`
Problem: Multiple tests assert overlapping readiness contract at different depths; older/weaker assertions may drift from newer contract.
Why this test may not catch real regressions: A readiness field can be removed or changed while one duplicate still passes and gives false confidence.
What better test should assert: One backend canonical contract test, with frontend tests limited to browser-specific masking and UX behavior.
Suggested replacement or improvement: Consolidate expected check IDs and browser-safe summary expectations into shared helpers.
Risk level: Medium
Confidence: Medium
