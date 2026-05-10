# Test Coverage Gap and Weak-Test Review Report

## 1. Executive summary

Overall test confidence: Medium
Overall regression risk: High

- Which major behaviors are well tested? API auth/security, paper notes, jobs queue/state, event logs, Obsidian sync, DB compatibility, and many pack API roundtrips have meaningful tests.
- Which major behaviors are missing meaningful tests? Real browser-to-API-to-SQLite-to-real-worker-to-artifact execution, browser EventSource contract behavior, external scholarly API contracts, cross-pack path-safety matrix, and some Research DNA route failures.
- Which existing tests are weak or misleading? `tests/test_full_pipeline.py` and `tests/full_integration_test.py` overstate integration coverage; several worker/job-runner tests use stale or partial fakes; mock Playwright tests are useful but should not count as production E2E.
- Which tests are most likely to be flaky? Backend Playwright fixed sleeps/networkidle checks, E2E bootstrap shared artifact writes, dynamic port probing, broad inherited subprocess env, and worker heartbeat real sleeps.
- Which mocks or fixtures may hide production bugs? Fake E2E worker, old-signature runner fakes, partial `SimpleNamespace` configs, `SimpleNamespace` papers, partial paper-note index responses, and minimal external HTTP mocks.
- Which tests should be added first? P0 real worker deepread contract smoke, then P1 provider contract fixtures, browser SSE contract, real tmp_path integration assertions, pack path-safety matrix, and worker signature guard.

## 2. Scope reviewed

Reviewed:
- Python manifests, frontend manifest, CI workflows, smoke wrappers
- Backend API/security/job/paper-note/artifact pack tests
- Frontend Playwright configs and representative E2E specs
- Mocks/skips/flaky patterns via `rg`, targeted file reads, and subagent review

Partially reviewed:
- Research DNA route surface
- Full job-runner internals and LLM/provider boundaries
- Frontend route coverage beyond representative files
- Large eval/goldset fixture surface

Skipped:
- Full pytest suite
- Full Playwright suite
- Coverage generation
- Mutation/stress-repeat runs

Needs verification:
- Exact Research DNA route-level gaps
- Full provider contract fixture inventory
- Repeated-run confirmation of flaky risks
- Every JSON/CSV fixture against current Pydantic schemas

## 3. Test inventory summary

- Test frameworks found: pytest, FastAPI `TestClient`, Playwright, TypeScript/Vite/ESLint, bash smoke wrappers.
- Test commands found: `.venv314/bin/python -m pytest -q ...`, `./scripts/run_backend_api_smoke.sh`, `./scripts/run_agents_smoke.sh`, `./scripts/run_meeting_pack_verify.sh`, `cd frontend && npm run lint/build/e2e:*`.
- Test categories found: unit, API contract, integration-like, smoke, frontend E2E, visual snapshot, eval gates.
- CI test coverage: backend API smoke, agents smoke, meeting-pack verify, first-paper smoke, frontend mock/backend E2E, real smoke workflow-dispatch, deepread handoff gates.
- Skipped/flaky tests found: real smoke and parser worker env-gated, talk-pack runtime skips, fixed Playwright sleeps, networkidle usage, smoke wrapper note about aggregate pytest flakiness.

## 4. Behavior coverage summary

| behavior | production files | existing tests | test quality | risk level | recommended action |
|---|---|---|---|---|---|
| API auth/security/error envelopes | `backend/main.py` | auth/beta/CORS/security/header tests | Strong | High | Maintain; add audit permutations if touched |
| Job queue/state/SSE/cancel | `src/jobs/*`, `backend/main.py` | jobs smoke/events/stale/heartbeat | Partial | Critical | Add real worker and browser SSE contract |
| Deepread runner/artifacts | `backend/services/job_runner.py`, agents/ingest/services | runner slices | Partial | Critical | Add real-worker contract smoke |
| DB/event logs/migrations | `src/db_utils.py`, `src/services/event_log.py` | DB/event log tests | Strong | High | Keep schema tests with migrations |
| Paper notes/import/operator state | `backend/routers/paper_notes.py` | extensive paper notes tests | Strong | High | Replace partial index mocks |
| Obsidian sync/idempotency | `backend/routers/obsidian.py`, `src/obsidian.py` | obsidian/idempotency tests | Strong | High | Keep focused idempotency tests |
| Derived artifact packs | pack routers/stores/services | API/store/schema/E2E tests | Partial | High | Add path-safety matrix and contract checks |
| Research DNA/profile state | `backend/main.py`, `src/profiles/*` | service/API/profile tests | Partial | High | Add route failure matrix |
| External providers/download | `src/fetch/*`, `src/downloader/*` | downloader/fetch provider tests | Weak | High | Add fixture-backed provider contracts |
| Frontend API/routes/SSE | `frontend/src/**` | Playwright mock/backend/visual | Partial | High | Add SSE and OpenAPI/type contract tests |
| Skills policy/run | `src/skills/*`, router | skills API/contract tests | Partial | High | Maintain deny-by-default tests |

## 5. Coverage gaps summary

| ID | missing behavior | risk | suggested test type | suggested test file/location | priority |
|---|---|---|---|---|---|
| G1 | Real browser/API/queue/worker/artifact chain | Critical | Integration/Contract | `tests/test_deepread_worker_contract.py` | P0 |
| G2 | Browser EventSource/SSE contract | High | E2E/Contract | `frontend/e2e/sse.backend.spec.ts` | P1 |
| G3 | External scholarly provider contracts | High | Contract/Unit | `tests/test_external_provider_contracts.py` | P1 |
| G4 | Cross-pack encoded/dot-segment path safety | High | Security/Contract | pack API tests or `tests/test_pack_api_path_safety.py` | P1 |
| G5 | Research DNA route-level failure modes | High | Contract/Integration | `tests/test_research_dna_api.py` | P2 |
| G6 | Frontend/backend type contract drift | Medium | Contract | `tests/test_openapi_contract.py` | P2 |
| G7 | Parser fallback normal-lane coverage | Medium | Integration/Contract | `tests/test_jobs_api_smoke.py` | P2 |
| G8 | Real-smoke standard/scheduled lane | Medium | E2E/Smoke | existing real-smoke path/workflow | P2 |

## 6. Weak tests summary

| ID | test file | weakness | related production behavior | suggested improvement | risk |
|---|---|---|---|---|---|
| W1 | `tests/test_full_pipeline.py` | Integration claim but heavily mocked | daily processor pipeline | split orchestration unit vs real tmp_path integration | High |
| W2 | `tests/full_integration_test.py` | repo-relative state, print-only checks, mocked DB save | watcher local PDF flow | convert to pytest/tmp_path with real assertions | High |
| W3 | `tests/test_worker_heartbeat.py`, `tests/test_jobs_api_smoke.py` | stale runner fake signatures | worker runner contract | exact-signature fakes and TypeError guard | High |
| W4 | `tests/test_job_runner_clinical_extraction.py` | partial config namespaces | job-runner config/privacy | use valid `AppConfig` factory | High |
| W5 | `tests/test_processor_candidate_selection.py` | `SimpleNamespace` paper candidates | ranking/scoring | use `Paper` schema fixtures | Medium |
| W6 | `tests/test_papers_api.py` | partial `_build_index` mocks | paper note listing | schema-valid `PaperNoteListResponse` helper | Medium |
| W7 | frontend mock specs | mock UX counted as E2E | frontend/API routes | label as mock coverage and pair with live contracts | Medium |
| W8 | readiness tests | duplicate/drift-prone contract assertions | runtime readiness | consolidate backend contract helper | Medium |

## 7. Flaky risk summary

| ID | test file | flaky risk | suggested fix | confidence |
|---|---|---|---|---|
| F1 | `frontend/scripts/run_backend_for_e2e.sh` | repo-root artifact writes/deletes | isolate `PAPERPIPE_ARTIFACTS_DIR` under E2E runtime | High |
| F2 | `frontend/e2e/backend.spec.ts` | fixed 250ms sleeps | event-driven waits / `expect.poll` | High |
| F3 | `frontend/e2e/backend.spec.ts` | `networkidle` on backend pages | wait for semantic UI/API signals | Medium |
| F4 | `frontend/playwright.port-utils.ts` | free-port probe race | deterministic per-lane ports / no parallel defaults | Medium |
| F5 | subprocess smoke tests | broad inherited env | allowlist/scrub env | Medium |
| F6 | `tests/test_worker_heartbeat.py` | real sleeps/thread timing | synchronization primitives | Medium |
| F7 | runtime-gated tests | coverage appears/disappears | explicit CI skip reporting or always-on canary | High |

## 8. Mock and fixture risk summary

| ID | mock/fixture | mismatch or risk | related production behavior | suggested fix |
|---|---|---|---|---|
| M1 | fake E2E worker | synthetic artifacts hide real runner | job/artifact flow | add real-worker contract smoke |
| M2 | old-signature runner fakes | fake contract differs from runtime | worker | exact signatures/signature guard |
| M3 | partial config namespaces | bypass `AppConfig` validation | job runner | schema-valid config factory |
| M4 | `SimpleNamespace` paper candidates | bypass `Paper` schema/branch | ranking | `Paper` fixtures |
| M5 | partial paper-note index objects | not valid response shape | paper listing | `PaperNoteListResponse` factory |
| M6 | forced frontend mock data | can hide backend response drift | frontend/API | OpenAPI/mock payload validation |
| M7 | minimal provider mocks | not realistic upstream contracts | external fetch/download | fixture-backed provider contracts |

## 9. Prioritized high-value test plan

See `.codex-review/test-gap-review/high-value-test-plan.md`.

## 10. Commands and validation

Commands run:
- `rg --files` / `find` / `rg` scans over tests, source, CI, frontend configs
- `sed` / `nl` targeted source/test inspection
- `python3 scripts/resolve_verification_python.py --require-module pytest` -> resolved `.venv314/bin/python`
- `.venv314/bin/python -m pytest --collect-only -q tests/test_api_key_auth.py tests/test_jobs_api_smoke.py tests/test_paper_notes_api.py tests/test_meeting_packs_api.py tests/test_image_evidence_api.py tests/test_chart_packs_api.py tests/test_talk_packs_api.py tests/test_event_log_db.py` -> 135 tests collected
- `.venv314/bin/python -m pytest -q tests/test_api_key_auth.py tests/test_browser_security_headers_api.py tests/test_cors_policy.py tests/test_beta_gate_api.py` -> 25 passed, 5 warnings
- `cd frontend && npm run lint -- --quiet` -> passed
- Follow-up high-risk regression bundle after test additions -> 203 passed, 6 warnings
- Initial full-suite attempt with `.venv314/bin/python -m pytest -q` failed during collection because `tests/test_docker_runner.py` and `tests/test_docker_sandbox.py` imported missing Python package `docker`.
- Docker-excluded full-suite attempt passed most tests but exposed packaging failures caused by missing `pip` in `.venv314` and a deprecated-alias guard failure from review-artifact wording.
- `.venv314/bin/python -m ensurepip --upgrade` -> bootstrapped `pip` into `.venv314`
- `.venv314/bin/python -m pip install docker` -> installed workflow-documented Python `docker` package for local verification
- Focused blocker rerun for Docker, deprecated-alias guard, and packaging entrypoint tests -> 6 passed, 4 skipped
- Final full-suite rerun with `.venv314/bin/python -m pytest -q` -> 2047 passed, 5 skipped, 7 warnings

Failures:
- `python -m pytest ...` failed because `python` command was not found.
- `python3 -m pytest ...` failed because system Python 3.14 lacked pytest.
- Initial full-suite blockers were resolved by bootstrapping `pip`, installing the workflow-documented Python `docker` package, and avoiding the deprecated alias spelling in review artifacts.
- Final full-suite rerun had no failures.

Commands not run and why:
- Full Playwright suite/build: too expensive for this read-only review; lint was run as a lightweight frontend sanity check.
- Coverage command: no configured coverage tooling found, and coverage percentage is not the target signal.

Coverage output:
- None generated.

Focused test results:
- Auth/security focused pytest slice passed.

## 11. Remaining blind spots

- Behaviors that could not be fully traced to tests: every Research DNA subroute/failure mode, every schema validator, full LLM/provider payload boundary, every external provider edge case.
- Tests that could not be run: full backend suite, full frontend Playwright suite, optional real-smoke/parser-worker/talk-pack runtime lanes.
- External integrations that could not be verified: live PubMed/arXiv/OpenAlex/Unpaywall/PMC provider behavior; no network/live tests were run.
- Production-only behavior that could not be tested: real operator data, runner-local real-smoke candidates, self-hosted deepread handoff gates, production proxy/header combinations.
- Flaky risks that require repeated runs to confirm: fixed Playwright waits, `networkidle`, dynamic port races, worker heartbeat timing, E2E artifact-state leakage.
