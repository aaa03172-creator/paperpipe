## Flaky risk: Backend E2E bootstrap writes/deletes repo-root runtime artifacts

Status: Confirmed
Test file/line: `frontend/scripts/run_backend_for_e2e.sh:50`, `frontend/scripts/run_backend_for_e2e.sh:319`, `frontend/scripts/run_backend_for_e2e.sh:2344`
Risk source: Filesystem state leakage and shared repo-root storage
Evidence: E2E exports several runtime dirs but not `PAPERPIPE_ARTIFACTS_DIR`; bootstrap deletes `root / "storage" / "artifacts"` entries and fake worker can write artifacts.
Why it may be flaky: Stale artifacts can affect later tests; cleanup can collide with developer/local runtime state; parallel runs can interfere.
Suggested fix: Export an E2E-specific artifacts root under `.e2e-backend-runtime/storage/artifacts` and cleanup only that root.
Suggested verification: Run backend E2E twice from a clean tree and verify no repo-root `storage/artifacts` churn.
Risk level: High
Confidence: High

## Flaky risk: Fixed sleeps around request-count assertions

Status: Likely
Test file/line: `frontend/e2e/backend.spec.ts:1250`, `:4560`, `:4569`, `:4632`, `:4681`, `:4742`, `:4821`, `:4904`
Risk source: Fixed `waitForTimeout(250)` timing
Evidence: Tests wait a fixed 250ms before asserting absence/presence of extra requests.
Why it may be flaky: Slow CI or delayed backend responses can arrive after the sleep and flip assertions.
Suggested fix: Replace fixed sleeps with event-driven waits, request promises, `expect.poll`, or explicit settled UI states.
Suggested verification: Repeat affected Playwright tests under CPU/network throttling or `--repeat-each`.
Risk level: Medium
Confidence: High

## Flaky risk: `networkidle` on backend-backed pages

Status: Likely
Test file/line: `frontend/e2e/backend.spec.ts:4680`, `:4741`, `:4820`, `:4903`, `:5795`, `:5849`
Risk source: Browser/network timing
Evidence: Backend-connected tests wait for `networkidle`.
Why it may be flaky: Polling, SSE, Vite dev-server behavior, or delayed backend calls can prevent a stable idle window.
Suggested fix: Wait for semantic UI elements or specific API responses instead of page-wide network idle.
Suggested verification: Repeat backend Playwright suite and inspect timeout traces.
Risk level: Medium
Confidence: Medium

## Flaky risk: Dynamic port probe race

Status: Likely
Test file/line: `frontend/playwright.port-utils.ts:8`; `frontend/playwright.backend.config.ts:20`
Risk source: Race between free-port probe and server bind
Evidence: Utility opens a port, closes it, then Playwright later starts servers using that port.
Why it may be flaky: Another local/parallel process can claim the port between probe and server start.
Suggested fix: Prefer deterministic per-lane ports in CI or let Playwright/server bind atomically where possible; avoid running configs in parallel on same defaults.
Suggested verification: Run multiple frontend E2E configs concurrently in local stress test.
Risk level: Medium
Confidence: Medium

## Flaky risk: Subprocess smoke tests inherit broad ambient environment

Status: Likely
Test file/line: `tests/test_frontend_real_smoke_backend_launcher.py:119`, `tests/test_frontend_real_smoke_preflight.py:118`, `tests/test_stale_reclaim_readiness_script.py:21`, `tests/test_talk_pack_render_smoke_script.py:59`
Risk source: Environment variable leakage
Evidence: Several tests build subprocess env from `os.environ.copy()`.
Why it may be flaky: Local `PAPERPIPE_*`, secrets, path overrides, or runtime flags can silently change subprocess behavior.
Suggested fix: Use allowlisted env with only required variables, or explicitly scrub PaperPipe/provider/auth variables.
Suggested verification: Run tests with deliberately noisy `PAPERPIPE_*` env values and confirm deterministic behavior.
Risk level: Medium
Confidence: Medium

## Flaky risk: Worker heartbeat timing uses real sleeps

Status: Likely
Test file/line: `tests/test_worker_heartbeat.py:136`, `tests/test_worker_heartbeat.py:160`
Risk source: Scheduler/thread timing
Evidence: Fake runner loops with `asyncio.sleep(0.01)` and test waits `time.sleep(0.05)` before reclaim.
Why it may be flaky: On slow CI, the worker may not reach the intended running/cancellable state within 50ms.
Suggested fix: Use synchronization primitives/events rather than fixed sleeps.
Suggested verification: Repeat test under load or with `pytest-repeat`.
Risk level: Low / Medium
Confidence: Medium

## Flaky risk: Runtime-gated tests silently skip important coverage

Status: Confirmed
Test file/line: `frontend/e2e/backend.spec.ts:3227`, `frontend/e2e/backend.spec.ts:4911`, `tests/test_talk_pack_render_smoke_script.py:32`
Risk source: Environment-gated coverage
Evidence: Real smoke, parser worker, and talk-pack rendering skip unless runtime flags/dependencies are available.
Why it may be flaky: Not classic nondeterministic flake, but coverage appears/disappears by environment, making regression signal inconsistent.
Suggested fix: Document lanes clearly; add a small always-on canary where possible; report skipped critical gates explicitly in CI summary.
Suggested verification: Review CI logs for skip counts and expected optional-lane status.
Risk level: Medium
Confidence: High
