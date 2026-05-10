## Priority 1: Real worker deepread contract smoke

Priority: P0
Test type: Integration / Contract / Regression
Risk addressed: Main production job path can pass E2E with fake worker while real worker/artifact generation is broken.
Production files: `backend/main.py`, `src/jobs/queue.py`, `src/jobs/worker.py`, `backend/services/job_runner.py`
Suggested test file: `tests/test_deepread_worker_contract.py`
Scenario: Enqueue a deepread job with a tiny local paper/PDF fixture, process it through `Worker.process_job`, and inspect DB/job/artifact APIs.
Setup: Temp DB/config/storage roots; minimal valid `AppConfig`; deterministic fake LLM/provider at model/network boundary only.
Action: POST `/jobs/deepread`, claim/process via real `Worker`, then GET `/jobs/{id}`, `/runs/{run_id}`, and artifact endpoint.
Assertions: terminal completed/failed state is consistent, run state updated, expected artifact sidecars exist or explicit bounded failure is recorded, paths masked, logs/events persisted.
Mocks/fixtures needed: tiny PDF, schema-valid config, fake LLM/model response objects.
Why this should be added before lower-priority tests: It protects the main product loop and catches regressions hidden by current fake-worker/browser flows.
Estimated implementation difficulty: High

## Priority 2: External provider contract fixtures

Priority: P1
Test type: Contract / Unit
Risk addressed: Scholarly intake/download can break on upstream response drift or failure classes.
Production files: `src/fetch/pubmed.py`, `src/fetch/arxiv.py`, `src/fetch/openalex.py`, `src/downloader/providers/unpaywall.py`, `src/downloader/router.py`
Suggested test file: `tests/test_external_provider_contracts.py`
Scenario: Parse realistic saved PubMed/Unpaywall/arXiv/OpenAlex success and failure payloads.
Setup: Fixture JSON/XML response files and patched `requests.get`.
Action: Call provider/fetcher functions with DOI/query inputs.
Assertions: normalized paper/PDF candidates match expected fields; malformed/empty/rate-limited payloads return bounded failures; no HTML/non-PDF content is accepted as PDF.
Mocks/fixtures needed: provider response fixtures under `tests/fixtures/provider_contracts/`.
Why this should be added before lower-priority tests: External contract drift has high production impact and current tests are thin.
Estimated implementation difficulty: Medium

## Priority 3: Browser EventSource job stream contract

Priority: P1
Test type: E2E / Contract
Risk addressed: Raw backend SSE tests do not prove browser `EventSource` integration, `/api` bridge, or frontend stream parsing.
Production files: `frontend/src/app/lib/sse.ts`, `backend/main.py`
Suggested test file: `frontend/e2e/sse.backend.spec.ts` or a focused block in `frontend/e2e/backend.spec.ts`
Scenario: Browser opens EventSource for a seeded completed job and receives status/log/artifact_ready/done.
Setup: Seed job/log/artifact via backend API or E2E runtime DB helper.
Action: In page context, create EventSource to `/api/jobs/{job_id}/events` and collect events.
Assertions: event names and payload fields parse correctly, terminal done occurs once, reconnect/cursor path does not duplicate done.
Mocks/fixtures needed: seeded job/log/artifact fixture.
Why this should be added before lower-priority tests: It protects the live progress UX and catches browser-only regressions.
Estimated implementation difficulty: Medium

## Priority 4: Convert misleading full integration tests into real tmp_path assertions

Priority: P1
Test type: Integration / Regression
Risk addressed: Existing “full integration” tests verify mocks and can leak repo-local state.
Production files: `src/processor.py`, `src/watcher.py`, `src/obsidian.py`, `src/exporter.py`, `src/db_utils.py`
Suggested test file: Replace/refactor `tests/full_integration_test.py`; add focused integration in `tests/test_full_pipeline.py`
Scenario: Run a local PDF/process flow that writes note/RIS/DB state under `tmp_path`.
Setup: `tmp_path` runtime dirs, valid `AppConfig`, deterministic metadata and LLM fakes.
Action: Process local PDF or daily slot with real save/export functions.
Assertions: note exists with expected frontmatter/tags/summary, RIS includes DOI/title/file link, DB state persisted, no repo-relative files left.
Mocks/fixtures needed: tiny PDF and metadata/LLM fakes; do not mock persistence/export writers.
Why this should be added before lower-priority tests: It turns a false-confidence test into actual regression protection.
Estimated implementation difficulty: Medium

## Priority 5: Pack ID path-safety regression matrix

Priority: P1
Test type: Security / Contract / Regression
Risk addressed: File-backed pack APIs may not uniformly reject traversal-like IDs/subpaths.
Production files: pack routers and stores for meeting/chart/protocol/paper-syntheses/talk/image
Suggested test file: Existing pack API files, or `tests/test_pack_api_path_safety.py`
Scenario: Request malicious pack IDs/subpaths across all file-backed pack APIs.
Setup: Temp roots with one valid pack and a sentinel file outside root.
Action: GET detail/markdown/export/derivative routes with `..`, encoded dot segments, slash-like IDs, absolute-looking IDs.
Assertions: 400/404, sentinel not read, no local path disclosure, valid pack still works.
Mocks/fixtures needed: minimal saved bundle fixtures.
Why this should be added before lower-priority tests: Security/data exposure risk across repeated file-backed patterns.
Estimated implementation difficulty: Medium

## Priority 6: Worker runner signature guard

Priority: P1
Test type: Unit / Contract
Risk addressed: Stale fake signatures and broad TypeError compatibility can hide real runner contract regressions.
Production files: `src/jobs/worker.py`, `backend/services/job_runner.py`
Suggested test file: `tests/test_worker_job_runner_chain.py` or `tests/test_worker_contract.py`
Scenario: Ensure worker passes the current production runner kwargs and does not hide TypeError raised inside runner body.
Setup: Fake runner with exact signature that records kwargs; separate fake that raises TypeError internally.
Action: Process claimed job.
Assertions: all expected kwargs are passed; internal TypeError marks job failed rather than retrying stripped kwargs.
Mocks/fixtures needed: exact-signature fake runner and temp DB.
Why this should be added before lower-priority tests: Small, cheap test that reduces high-value mock drift.
Estimated implementation difficulty: Low

## Priority 7: Minimal AppConfig factory for job-runner tests

Priority: P2
Test type: Unit / Contract
Risk addressed: Partial namespace configs bypass production validation/defaults.
Production files: `src/config.py`, `backend/services/job_runner.py`
Suggested test file: helper plus updates to `tests/test_job_runner_clinical_extraction.py`
Scenario: Clinical/privacy job-runner tests use schema-valid config.
Setup: Minimal `AppConfig` factory rooted in `tmp_path`.
Action: Run existing clinical extraction scenarios with factory.
Assertions: Existing behavior still holds and config validators/defaults are active.
Mocks/fixtures needed: temp dirs, fake agents/providers.
Why this should be added before lower-priority tests: Improves reliability of important privacy/clinical coverage without huge new surface.
Estimated implementation difficulty: Low / Medium

## Priority 8: OpenAPI/frontend type contract check

Priority: P2
Test type: Contract
Risk addressed: Handwritten frontend types drift from Pydantic response models.
Production files: `frontend/src/app/lib/types.ts`, `frontend/src/app/lib/api.ts`, `src/schemas/*.py`, `backend/main.py`
Suggested test file: `tests/test_openapi_contract.py`
Scenario: Snapshot or assert selected OpenAPI schemas for jobs, paper notes, artifact packs, runtime readiness.
Setup: FastAPI TestClient.
Action: Fetch `/openapi.json`.
Assertions: selected routes and required schema fields remain stable.
Mocks/fixtures needed: none.
Why this should be added before lower-priority tests: Cheap guard against cross-stack runtime breakage.
Estimated implementation difficulty: Low

## Priority 9: Research DNA route edge-case matrix

Priority: P2
Test type: Contract / Integration
Risk addressed: Service-level Research DNA coverage may not cover all route/failure behavior.
Production files: `backend/main.py`, `src/profiles/*`, `src/schemas/research_dna.py`
Suggested test file: `tests/test_research_dna_api.py`
Scenario: Exercise invalid selectors, lock conflicts, missing profiles, guidance/history/recommendation edge cases.
Setup: Temp profile/DNA roots with minimal profile assets.
Action: Send FastAPI requests to each high-risk route.
Assertions: bounded 4xx responses, no raw paths/secrets, rejected writes leave state unchanged.
Mocks/fixtures needed: temp profile/DNA fixtures.
Why this should be added before lower-priority tests: Protects stateful user research workflows not fully covered by generic service tests.
Estimated implementation difficulty: Medium

## Priority 10: Promote one real-smoke canary into scheduled/release verification

Priority: P2
Test type: E2E / Smoke
Risk addressed: Real-paper/browser coverage is opt-in and not in standard verification.
Production files: `frontend/package.json`, `.github/workflows/frontend-real-smoke.yml`, `frontend/e2e/backend.spec.ts`
Suggested test file: existing real-smoke Playwright path and CI workflow
Scenario: Scheduled or release-gated run uses runner-local seeded candidate.
Setup: Known config/storage path or seeded non-fixture candidate.
Action: Run `npm run e2e:backend:real-smoke`.
Assertions: preflight passes, real candidate loads, detail/workbench/artifact route opens.
Mocks/fixtures needed: runner-local data or explicit seeded candidate.
Why this should be added before lower-priority tests: It keeps closest-to-production UX from becoming a manual-only confidence signal.
Estimated implementation difficulty: Medium / High
