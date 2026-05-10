# Functional Behavior, Conflict, and Wiring Review Report

## 1. Executive summary

Overall functional risk level: High

Major code paths that appear connected and working:
FastAPI route registration, paper notes/list/detail, job enqueue/worker happy path, SSE/job timeline, protocol attachments, paper synthesis backend split manifest/markdown routes, and the main Vite route/API structure. Targeted verification passed: `85 passed, 7 warnings`, and `npm run build` passed.

Code paths probably broken:
The `/api/*` protected-route bridge, Image Evidence caller-supplied IDs, unmatched-download review queue persistence, artifact run lookup for slash-bearing paper IDs, import-time feedback/Ollama initialization, frontend visual-evidence lineage display, meeting-pack write fallback, and downloads watcher rename handling.

Current-branch reconciliation:
Several issues from the underlying review have been addressed on `codex/deepread-soft-gate`: frontend mock fallback no longer falls back for reached-backend HTTP errors, cloud table fallback now has a privacy preflight callback, failed/cancelled Deep Read jobs now preserve `artifact_dir`, and rendered paper-note/access links now use URL scheme allowlists. The remaining high-priority unresolved items are the `/api/*` bridge trust boundary, Image Evidence ID/root validation, unmatched-download triage persistence, artifact route ambiguity, import-time Ollama initialization, frontend visual-evidence lineage display, meeting-pack write fallback, and watcher rename handling.

Modules that conflict:
API auth middleware vs `/api/*` bridge behavior; Image Evidence schema vs filesystem store; downloads watcher unmatched sentinel vs `review_queue` FK; artifact route patterns vs slash-bearing paper IDs; backend import health vs feedback router Ollama initialization; backend paper synthesis lineage vs frontend types/formatters; meeting-pack write behavior vs frontend docs.

Disconnected/partially wired code:
Research DNA appears backend/API-only in this frontend shell; downloads watcher lacks `on_moved`; visual evidence lineage is not fully connected to frontend display; meeting-pack generation can report mock success without a backend artifact.

Highest-value missing tests:
Unauthenticated `/api/*` private-route tests, Image Evidence traversal tests, canonical-schema unmatched-download tests, slash-bearing artifact route tests, backend import-without-Ollama tests, visual evidence ledger UI contract test, meeting-pack no-mock-write test, and watcher rename handling tests.

## 2. Scope reviewed

Reviewed:
FastAPI app/middleware, registered routes, paper notes/papers/workbench APIs, job queue/worker/runner, event/timeline path, artifact family routers, Image Evidence storage, paper synthesis contracts, protocol attachment API, downloads watcher, frontend route shell/API client/types, runtime schema/config.

Partially reviewed:
Research DNA/profile flows, skills internals, chart/meeting/method/talk pack deep service behavior, stale-job recovery, and scientific output quality sidecars.

Skipped:
Full pytest suite, live browser e2e, live external service calls, production DB contents, deployment reverse proxy, generated/vendor/cache files.

Needs verification:
Whether Research DNA is intentionally API-only; whether all artifact family stores share the Image Evidence path-boundary class; browser rename behavior in a real watchdog environment; the full default import-health command after removing import-time side effects.

## 3. Flow trace summary

| Flow name | Conclusion | Risk level | Key files | Main concern |
| --- | --- | --- | --- | --- |
| Frontend paper list and note detail | Probably working | Low | `frontend/src/app/lib/api.ts`, `backend/routers/paper_notes.py` | HTTP-error fallback risk resolved; continue browser regression coverage |
| Browser `/api/*` request to protected backend route | Broken | High | `backend/main.py` | server-side key injection bypasses root auth contract |
| Deep Read enqueue to worker completion | Probably working | Low | `src/jobs/queue.py`, `src/jobs/worker.py`, `backend/services/job_runner.py` | failed artifact_dir persistence resolved; continue smoke coverage |
| Job events and timeline | Working | Low | `backend/main.py`, `src/services/event_log.py` | no confirmed registration gap |
| Paper synthesis compiled knowledge | Probably working | Medium | `src/paper_syntheses/service.py`, `frontend/src/app/lib/types.ts` | visual evidence lineage omitted by frontend |
| Image Evidence registration/read | Broken | High | `src/schemas/image_evidence.py`, `src/image_evidence/store.py` | path-like ID escapes storage root |
| Protocol attachment draft | Working | Low | `backend/routers/protocol_cards.py`, `src/protocol_attachments/service.py` | targeted tests passed |
| Downloads watcher PDF handling | Broken | High | `src/downloads_watcher.py`, `scripts/init_db.py` | unmatched queue FK failure; rename event missing |
| Artifact pages | Probably working | Medium | feature routers/stores | route registration ok; standardize path confinement and write fallback |
| Artifact run bundle/file lookup | Broken | High | `backend/main.py` | slash-bearing paper IDs can hit wrong route |
| Feedback import/provider path | Broken | High | `backend/routers/feedback.py`, `src/llm_provider.py` | backend import initializes Ollama |
| Research DNA API | Needs verification | Medium | `backend/main.py`, `src/profiles/*` | no frontend route found |

## 4. Conflict summary

| Conflict | Status | Files involved | Impact | Suggested fix |
| --- | --- | --- | --- | --- |
| `/api/*` bridge bypasses API-key behavior | Confirmed | `backend/main.py` | protected routes reachable via bridge | require caller auth or strong trusted UI proof |
| Image Evidence ID vs filesystem root | Confirmed | `src/schemas/image_evidence.py`, `src/image_evidence/store.py` | out-of-root writes | strict ID validation and path confinement |
| Paper synthesis lineage kind mismatch | Confirmed | `src/schemas/paper_synthesis.py`, `frontend/src/app/lib/types.ts` | mislabeled lineage | add frontend `visual_evidence_ledger` support |
| Downloads unmatched sentinel vs FK | Confirmed | `src/downloads_watcher.py`, `scripts/init_db.py` | no durable unmatched triage | separate store or valid sentinel row |
| Auto mock fallback vs live backend errors | Resolved in current branch | `frontend/src/app/lib/config.ts`, `frontend/src/app/lib/api.ts` | HTTP errors no longer fall back to fixtures | keep no-mock-on-401 coverage |
| Cloud table fallback vs privacy boundary | Resolved in current branch | `src/ingest/cloud_table_fallback.py`, `backend/services/job_runner.py` | preflight callback now blocks before LLM extraction | keep blocking preflight coverage |
| Artifact route shadowing | Confirmed | `backend/main.py`, `src/services/identity.py` | run artifacts unreachable for slash IDs | avoid non-final path IDs |
| Meeting-pack write fallback vs docs | Confirmed | `frontend/src/app/lib/api.ts`, `frontend/README.md` | fake write success | fail writes outside explicit mock mode |
| Backend import initializes Ollama | Confirmed | `backend/routers/feedback.py`, `src/llm_provider.py` | startup/import checks depend on Ollama | lazy provider initialization |

## 5. Disconnected code summary

| Item | Status | Expected connection | Actual connection | Impact | Suggested fix |
| --- | --- | --- | --- | --- | --- |
| Image Evidence ID validation | Confirmed | schema/store root validation | direct path segment | out-of-root writes | strict pattern and confinement |
| `/api/*` bridge trust proof | Confirmed | trusted UI/session or caller auth | key injected for bridge | protected API exposure | require auth before injection |
| Unmatched download queue item | Confirmed | durable triage record | FK failure swallowed | lost follow-up | separate unmatched store or valid row |
| Watcher rename handling | Needs verification | created/moved handling | created only | skipped downloads | add `on_moved` |
| Failed job artifact_dir | Resolved in current branch | artifact path persisted for all created runs | runner returns and worker persists failure/cancel artifact_dir | diagnostics discoverable | keep failure-path coverage |
| Visual evidence frontend display | Confirmed | backend lineage kind rendered | missing type/label | wrong UI lineage | update types/formatters |
| Research DNA frontend reachability | Needs verification | route if user-facing | no route found | possibly API-only | clarify/add route |
| Artifact run endpoint for slash IDs | Confirmed | valid paper IDs resolve to run/file artifacts | route parser splits paper ID | unreachable artifacts | query/hashed segment route |
| Feedback provider startup | Confirmed | initialize on route use | initializes on import | import/startup failures | lazy dependency factory |
| Meeting-pack write path | Confirmed | live backend write or explicit mock | fallback mock success | false persisted result | fail outside forced mock |

## 6. Findings summary

| ID | Severity | Confidence | Category | File/line | Short issue | Suggested action |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 | High | Conflict | `backend/main.py:1249` | `/api/*` bridge bypasses root API-key behavior | require auth/trusted UI proof |
| 2 | P1 | High | Missing wiring | `src/image_evidence/store.py:17` | Image Evidence ID escapes root | validate IDs and confine paths |
| 3 | P1 | High | Conflict | `src/downloads_watcher.py:295` | unmatched PDFs not queued under FK schema | repair unmatched triage storage |
| 4 | P1 | High | Functional behavior | `frontend/src/app/lib/config.ts:12` | mock fallback masks backend failures | resolved in current branch |
| 5 | P2 | High | Functional behavior | `src/ingest/cloud_table_fallback.py:199` | cloud table fallback lacks privacy preflight | resolved in current branch |
| 6 | P2 | High | Missing wiring | `src/jobs/worker.py:186` | failed artifacts can be orphaned | resolved in current branch |
| 7 | P2 | High | Contract mismatch | `frontend/src/app/lib/types.ts:995` | visual evidence lineage missing in frontend | add type/label/e2e coverage |
| 8 | P2 | Medium | Missing wiring | `src/downloads_watcher.py:347` | watcher likely misses rename completion | add `on_moved` |
| 9 | P2 | High | Functional behavior | `backend/routers/paper_notes.py:1402` | rendered links lack scheme allowlist | resolved in current branch |
| 10 | P1 | High | Conflict | `backend/main.py:5712` | artifact routes misparse slash-bearing paper IDs | use query/hashed IDs |
| 11 | P1 | High | Functional behavior | `backend/routers/feedback.py:33` | backend import initializes Ollama | lazy initialize feedback retriever |
| 12 | P2 | High | Contract mismatch | `frontend/src/app/lib/api.ts:1240` | meeting-pack write falls back to mock | fail outside forced mock mode |
| 13 | P2 | Medium | Test gap | `scripts/check_python_import_health.py:16` | import-health test misses default side effects | test defaults with external calls patched |
| 14 | P3 | Medium | Disconnected code | `backend/main.py:4711` | Research DNA lacks frontend route | clarify API-only vs add route |

## 7. Detailed findings

See `.codex-review/findings.md`.

## 8. Tests and commands

Commands run:
- `.venv/bin/python -m pytest -q tests/test_worker_job_runner_chain.py tests/test_jobs_api_smoke.py tests/test_db_schema_compat.py tests/test_paper_notes_api.py tests/test_paper_synthesis_frontend_contract.py tests/test_protocol_attachments_api.py`
  - Result: passed, `85 passed, 7 warnings in 203.02s`.
- `cd frontend && npm run build`
  - Result: passed, Vite production build completed.
- Route listing via `.venv/bin/python` importing `backend.main`.
  - Result: completed; noted Ollama connection side effect on import.
- Local Image Evidence root-escape reproduction.
  - Result: confirmed out-of-root write.
- Local `/api/jobs` auth bridge probe.
  - Result: `GET /jobs` 401; `GET /api/jobs` 200 without caller key.

Additional subagent verification:
- Jobs/events/downloads targeted set: `pytest tests/test_jobs_events_persistence.py tests/test_worker_heartbeat.py tests/test_downloads_watcher.py tests/test_jobs_api_smoke.py -q`
  - Result reported by subagent: `41 passed, 5 warnings`.
- Canonical-schema unmatched-download reproduction.
  - Result reported by subagent: `status=unmatched`, `review_queue_count=0`, FK failure.

Failures:
No command failures in the final targeted verification set.

Commands not run and why:
- Full pytest suite: expensive relative to this review and many targeted suites already ran.
- Full Playwright e2e: not run; frontend build passed, but browser contract tests should be added after fixes.
- Live external service calls: intentionally avoided.

## 9. Remaining blind spots

- Research DNA was route-mapped but not deeply behavior-traced across every service branch.
- Artifact path-boundary analysis outside Image Evidence is incomplete; standardizing store validation is still recommended.
- Real browser download rename behavior should be verified with watchdog or an integration test.
- Live deployment auth/reverse proxy assumptions were not inspected.
- Scientific correctness of biomedical outputs was out of scope.

## 10. Recommended next actions

1. Fix unresolved P1s first: `/api/*` bridge auth, Image Evidence ID/root validation, and unmatched-download triage persistence.
2. Repair remaining wiring P2s: visual evidence ledger frontend contract and watcher `on_moved`.
3. Add targeted tests before broad refactors: unauthenticated `/api/*`, Image Evidence traversal, canonical unmatched download, visual evidence ledger UI, and watcher rename handling.
4. Clarify Research DNA frontend intent and either mark API-only in docs or wire a route/navigation path.
