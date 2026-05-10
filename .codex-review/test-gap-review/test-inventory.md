## Test area: Python backend/API pytest suite

Test framework: pytest with FastAPI `TestClient`
Test files: `tests/test_*.py`, `tests/full_integration_test.py`, `tests/verify_*.py`, `tests/process_gold_paper.py`
Production files covered: `backend/main.py`, `backend/routers/*.py`, `backend/services/job_runner.py`, `src/**/*.py`, `scripts/**/*.py`
Command to run: `.venv314/bin/python -m pytest -q <target files>`; backend smoke wrapper: `./scripts/run_backend_api_smoke.sh`
Type: Unit / Integration / Contract / Regression / Smoke
Mocks used: heavy use of `monkeypatch`, `unittest.mock.patch`, `MagicMock`, fake LLM providers, fake fetchers, fake worker runners, fake config objects
Fixtures used: `tests/fixtures/**`, `tests/gold_set/**`, `tests/temp_rag_test/**`, many `tmp_path` runtime layouts
CI coverage: `backend-api-smoke.yml`, `agents-smoke.yml`, `meeting-pack-verify.yml`, `first-paper-smoke.yml`, `phase3-integration-optin.yml`, `deepread-handoff-gate.yml`
Known skipped/flaky tests: runtime-gated tests for talk-pack PPTX runtime; Phase 3 integration opt-in; parser worker/real smoke gated by env flags
Initial quality impression: Broad and behavior-oriented in many API/state areas, especially paper notes, jobs, artifacts, auth, event logs, and pack APIs. Risk remains where tests overpatch the real pipeline, use partial fake contracts, or call themselves integration while asserting mostly mocks.
Notes: No coverage percentage config found in primary manifests. `python` and system `python3` were not usable for pytest in this environment; repository resolver selected `.venv314/bin/python`.

## Test area: Frontend Playwright mock E2E

Test framework: Playwright
Test files: `frontend/e2e/*.mock.spec.ts`, including `mock.spec.ts`, `meeting-pack.mock.spec.ts`, `method-comparison.mock.spec.ts`, `chart-pack.mock.spec.ts`, `image-evidence.mock.spec.ts`, `protocol-card.mock.spec.ts`, `visual-mock.mock.spec.ts`
Production files covered: `frontend/src/App.tsx`, `frontend/src/app/pages/**`, `frontend/src/app/lib/api.ts`, `frontend/src/app/lib/mock.ts`
Command to run: `cd frontend && npm run e2e:mock`
Type: E2E / UI regression / Snapshot
Mocks used: forced mock mode via `VITE_FORCE_MOCK=1`; static frontend mock data returned before live fetches
Fixtures used: frontend mock data and visual snapshots
CI coverage: `frontend-e2e.yml` mock job; `soft-gate-master.yml` verify-mock
Known skipped/flaky tests: no skip markers observed in mock config, but mock mode can hide backend/API regressions
Initial quality impression: Useful for UI regression and fallback behavior, weak as evidence of production integration.
Notes: Mock tests should be counted as UI fallback coverage, not runtime/API/artifact contract coverage.

## Test area: Frontend backend-connected Playwright E2E

Test framework: Playwright
Test files: `frontend/e2e/backend.spec.ts`, `frontend/e2e/backend.gated.spec.ts`, `frontend/e2e/visual-backend.backend.spec.ts`, `frontend/e2e/workbench-debug.spec.ts`
Production files covered: frontend routes plus FastAPI backend and seeded E2E runtime under `frontend/.e2e-backend-runtime`
Command to run: `cd frontend && npm run e2e:backend`; gated/parser lanes: `npm run e2e:backend:gated`, `npm run e2e:backend:parser-worker`
Type: E2E / Integration / Visual snapshot / Smoke
Mocks used: optional fake worker from `frontend/scripts/run_fake_worker_for_e2e.py`; seeded fixture data; backend fixture bootstrap
Fixtures used: `.e2e-backend-runtime`, `tests/fixtures/image_evidence_case/**`, `frontend/public/sample.pdf`, visual snapshots
CI coverage: `frontend-e2e.yml` backend job, `soft-gate-master.yml` verify-backend, `frontend-e2e-canary.yml`
Known skipped/flaky tests: real-paper smoke gated by `PAPERPIPE_REAL_SMOKE`; parser-worker cases gated by `PAPERPIPE_E2E_ENABLE_PARSER_WORKER`; several fixed waits and `networkidle` patterns
Initial quality impression: Stronger than mock E2E for route wiring, but main deepread worker/artifact path is often simulated. Visual coverage is broad.
Notes: Backend launcher writes some artifacts under repo-root `storage/artifacts`, which creates shared-state and cleanup risk.

## Test area: Frontend build/lint/typecheck

Test framework: TypeScript, Vite, ESLint
Test files: no frontend unit test framework found
Production files covered: `frontend/src/**/*.ts(x)`
Command to run: `cd frontend && npm run lint`; `cd frontend && npm run build`
Type: Static / Build
Mocks used: none
Fixtures used: none
CI coverage: frontend workflows run lint/build before E2E
Known skipped/flaky tests: none
Initial quality impression: Good static gate, but no component/unit tests for API parsing, state transitions, or SSE client behavior.
Notes: `npm run lint -- --quiet` passed during this review.

## Test area: Smoke shell wrappers and evaluation gates

Test framework: bash wrappers plus pytest/script checks
Test files: `scripts/run_backend_api_smoke.sh`, `scripts/run_agents_smoke.sh`, `scripts/run_meeting_pack_verify.sh`, `scripts/run_first_paper_smoke.sh`, `scripts/test_phase3_integration.py`
Production files covered: selected backend/API/agent/eval surfaces
Command to run: wrapper-specific, e.g. `./scripts/run_backend_api_smoke.sh`
Type: Smoke / Regression / Eval gate
Mocks used: varies by underlying pytest/script
Fixtures used: temp output dirs, goldset/eval manifests, frontend E2E runtime fixtures
CI coverage: dedicated GitHub Actions workflows
Known skipped/flaky tests: comments in `run_backend_api_smoke.sh` note aggregate pytest execution was flaky, so it runs file-by-file
Initial quality impression: Useful release gates, but selective; not a substitute for broad meaningful coverage.
Notes: Some workflows still target `master` while repo guidance says default branch is currently `main`.

## Test area: Coverage tooling

Test framework: None found
Test files: no `coverage`, `pytest-cov`, Vitest, or Jest configuration found in manifests
Production files covered: N/A
Command to run: N/A
Type: Other
Mocks used: N/A
Fixtures used: N/A
CI coverage: no coverage upload/enforcement found
Known skipped/flaky tests: N/A
Initial quality impression: Coverage percentage is not currently a visible quality signal.
Notes: This review intentionally does not use file coverage as proof of behavior coverage.
