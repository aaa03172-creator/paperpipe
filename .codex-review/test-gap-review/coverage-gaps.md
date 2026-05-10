## Coverage gap: Real browser-to-worker-to-artifact deepread chain

Status: Confirmed gap
Risk level: Critical
Production behavior: Browser/API enqueues job, SQLite queue claims it, real worker calls `run_deepread_job`, and artifacts/job state/logs become visible.
Production files: `backend/main.py`, `src/jobs/queue.py`, `src/jobs/worker.py`, `backend/services/job_runner.py`, `frontend/scripts/run_fake_worker_for_e2e.py`
Existing tests checked: `tests/test_jobs_api_smoke.py`, `tests/test_worker_job_runner_chain.py`, `frontend/e2e/backend.spec.ts`, `frontend/scripts/run_backend_for_e2e.sh`
What is missing: One deterministic integration smoke that uses the real worker/job runner path with only model/network boundaries stubbed.
Why it matters: Current E2E can pass using fake artifacts and patched runners while real ingest/index/read/artifact handoff is broken.
Suggested test type: Integration / Contract / Regression
Suggested test file/location: `tests/test_deepread_worker_contract.py` or a quarantined backend smoke target
Suggested test scenario: Seed a tiny local PDF/state config, enqueue `/jobs/deepread`, claim/process via `Worker`, stub only LLM/provider calls with production-shaped objects, then fetch job/artifact APIs.
Suggested assertions: job reaches `completed`, execution run is terminal, log/events include expected stages, artifact directory contains `document_artifact.json`, `index_artifact.json` or expected sidecars, API masks local paths.
Required mocks/fixtures: tiny PDF fixture, `AppConfig` factory, deterministic LLM/provider fakes at network/model boundary only
Confidence: High

## Coverage gap: Browser EventSource/SSE replay contract

Status: Confirmed gap
Risk level: High
Production behavior: Frontend `connectJobStream` consumes `/api/jobs/{id}/events` as browser `EventSource` and handles status/log/artifact_ready/done/reconnect/mock fallback.
Production files: `frontend/src/app/lib/sse.ts`, `backend/main.py`, `tests/test_jobs_events_persistence.py`
Existing tests checked: `tests/test_jobs_events_persistence.py`, `frontend/e2e/backend.spec.ts`
What is missing: Browser-level test using native `EventSource`, not raw `TestClient` response text.
Why it matters: ASGI raw text can be correct while browser event names, proxy path, CORS, reconnect, or handler parsing regress.
Suggested test type: E2E / Contract
Suggested test file/location: `frontend/e2e/backend.spec.ts` or focused `frontend/e2e/sse.backend.spec.ts`
Suggested test scenario: Create/complete a job in backend fixture, open an in-browser EventSource to `/api/jobs/{id}/events`, collect events, reconnect with a cursor path where feasible.
Suggested assertions: receives status/log/done exactly once, artifact_ready payload is parsed, UI terminal drawer updates, reconnect does not duplicate done after `Last-Event-ID`.
Required mocks/fixtures: seeded job/log/artifact fixture through backend API or DB helper
Confidence: High

## Coverage gap: External scholarly API fixture-backed contracts

Status: Confirmed gap
Risk level: High
Production behavior: Fetch/download providers parse PubMed, arXiv/OpenAlex/fetcher metadata, Unpaywall/PMC/direct PDF candidates and failure classes.
Production files: `src/fetch/pubmed.py`, `src/fetch/arxiv.py`, `src/fetch/openalex.py`, `src/downloader/providers/unpaywall.py`, `src/downloader/router.py`
Existing tests checked: `tests/test_fetch_providers.py`, `tests/test_downloader.py`, `tests/test_cli_unpaywall_smoke.py`
What is missing: Contract tests with realistic provider response fixtures for success, malformed, empty, and rate-limited responses.
Why it matters: Intake/download flows are production-critical and can fail on upstream response shape drift while minimal mocks still pass.
Suggested test type: Contract / Unit
Suggested test file/location: `tests/test_external_provider_contracts.py`
Suggested test scenario: Patch `requests.get` with saved JSON/XML bodies for PubMed ESearch/EFetch, Unpaywall OA/no-OA/429/invalid JSON, arXiv edge cases.
Suggested assertions: normalized IDs/DOIs, title/authors/year/source, no crashes on malformed payloads, failure classes/retry flags, no HTML saved as PDF.
Required mocks/fixtures: realistic response fixture files under `tests/fixtures/provider_contracts/`
Confidence: High

## Coverage gap: Cross-pack encoded/dot-segment ID path safety

Status: Likely gap
Risk level: High
Production behavior: File-backed pack APIs resolve pack IDs and artifact subpaths under storage roots without traversal or encoded dot-segment escape.
Production files: `backend/routers/meeting_packs.py`, `backend/routers/chart_packs.py`, `backend/routers/protocol_cards.py`, `backend/routers/paper_syntheses.py`, stores under `src/*`
Existing tests checked: `tests/test_artifacts_runs_api.py`, `tests/test_image_evidence_api.py`, `tests/test_talk_packs_api.py`, pack API tests
What is missing: Uniform malicious ID tests for meeting/chart/protocol/paper-synthesis routes comparable to artifact/talk/image subpath tests.
Why it matters: These APIs read files from local storage roots. A gap here risks local file disclosure or corruption.
Suggested test type: Security / Contract / Regression
Suggested test file/location: existing pack API test files per family
Suggested test scenario: Request IDs/subpaths containing `..`, `%2e%2e`, slash-like encodings, absolute-path-looking strings, and malformed Unicode where route matching permits.
Suggested assertions: 400/404 without reading/writing outside configured root; no raw local path in response.
Required mocks/fixtures: temp storage roots only
Confidence: Medium

## Coverage gap: Research DNA route-level failure modes

Status: Likely gap
Risk level: High
Production behavior: Research DNA endpoints handle screening selectors, current/advance flows, guidance/history/recommendations, locks, profile projections, and sanitized errors.
Production files: `backend/main.py`, `src/profiles/*`, `src/schemas/research_dna.py`
Existing tests checked: `tests/test_research_dna_api.py`, `tests/test_research_dna_service.py`, `tests/test_research_dna_projection.py`, `tests/test_profile_store_concurrency.py`
What is missing: Route-level tests for every major subroute/failure mode, especially invalid selectors, lock conflicts, missing profiles, and guidance/history edge cases.
Why it matters: Profile/research state is canonical-ish user state; route drift can bypass service-level tests.
Suggested test type: Contract / Integration
Suggested test file/location: `tests/test_research_dna_api.py`
Suggested test scenario: Exercise negative/edge requests against FastAPI for screening advance/current/guidance/history/recommendation routes with temp profile/DNA roots.
Suggested assertions: response model shape, bounded 4xx errors, no raw paths/secrets, state file unchanged on rejected requests.
Required mocks/fixtures: temp profiles and DNA roots
Confidence: Medium

## Coverage gap: Frontend/backend type-contract drift

Status: Confirmed gap
Risk level: Medium
Production behavior: Frontend `types.ts` and API casts should stay aligned with FastAPI/Pydantic response models.
Production files: `frontend/src/app/lib/types.ts`, `frontend/src/app/lib/api.ts`, `src/schemas/*.py`, `src/jobs/schemas.py`, `backend/main.py`
Existing tests checked: OpenAPI check in `tests/test_paper_syntheses_api.py` only; frontend build/lint
What is missing: Shared OpenAPI contract snapshot or generated client/type validation for high-use routes.
Why it matters: Both sides can compile while runtime UI breaks on renamed/missing fields.
Suggested test type: Contract
Suggested test file/location: `tests/test_openapi_contract.py` and/or frontend type generation check
Suggested test scenario: Snapshot selected OpenAPI schemas for jobs, paper notes, pack APIs, runtime readiness; optionally validate frontend sample payloads against schema.
Suggested assertions: required fields and route names remain stable or intentional updates are reviewed.
Required mocks/fixtures: none beyond TestClient
Confidence: High

## Coverage gap: Parser fallback normal-lane coverage

Status: Confirmed gap
Risk level: Medium
Production behavior: Requested `docling` parser falls back to `fitz_pdfplumber` or records effective parser metadata in normal job status.
Production files: `backend/services/job_runner.py`, `src/jobs/worker.py`, frontend parser selection flow
Existing tests checked: `frontend/e2e/workbench-debug.spec.ts`, `frontend/e2e/backend.spec.ts`, `tests/test_jobs_api_smoke.py`
What is missing: Deterministic backend/API test that exercises fallback metadata without enabling parser-worker E2E.
Why it matters: Current browser tests for fallback are skipped unless `PAPERPIPE_E2E_ENABLE_PARSER_WORKER=1`.
Suggested test type: Integration / Contract
Suggested test file/location: `tests/test_jobs_api_smoke.py` or `tests/test_job_runner_ingest_backend.py`
Suggested test scenario: Force requested backend `docling`, make docling unavailable, run bounded runner slice, verify effective backend and bootstrap/run meta.
Suggested assertions: requested parser remains `docling`, effective parser is fallback, user-facing status explains fallback.
Required mocks/fixtures: parser availability monkeypatch, tiny config/PDF fixture
Confidence: Medium

## Coverage gap: Release-lane real smoke not part of normal verification

Status: Confirmed gap
Risk level: Medium
Production behavior: Closest-to-user runtime with non-fixture or runner-local candidate data loads real paper notes/workbench/artifacts.
Production files: `frontend/package.json`, `frontend/e2e/backend.spec.ts`, `.github/workflows/frontend-real-smoke.yml`
Existing tests checked: real-smoke Playwright tests gated by `PAPERPIPE_REAL_SMOKE`; workflow dispatch only
What is missing: Scheduled or release-required small real-smoke lane.
Why it matters: PRs can pass standard verification without exercising real operator-like data.
Suggested test type: E2E / Smoke
Suggested test file/location: CI workflow plus existing `frontend/e2e/backend.spec.ts`
Suggested test scenario: Nightly or pre-release run with one stable candidate and required preflight.
Suggested assertions: real candidate appears, detail/workbench loads, a derived artifact route opens, runtime readiness is not falsely green when preflight fails.
Required mocks/fixtures: runner-local config/storage, or explicitly seeded non-fixture candidate
Confidence: High
