# Whole-Repository Risk Review Report

Review date: 2026-05-10

## 1. Executive Summary

Overall risk level: High

Ship posture: needs targeted fixes first. The project has a coherent local-first FastAPI/Vite architecture and many useful tests, but several P1/P2 issues affect secrets, external inference privacy, job/run data integrity, fresh DB bootstrap, CI release confidence, and frontend truthfulness under backend failure.

Top 5 risks:

1. Secrets can leak through the live workspace `.env` and cloud table keys can be written into raw run artifacts.
2. `run_id` values collide at second precision, allowing unrelated jobs to merge execution metadata/events.
3. Fresh DB initialization and Zotero sync disagree on the `papers.summary` column.
4. CI/release safety has gaps: Phase3 workflow uses unsupported Python, package installability tests are not clean, and macOS preflight accepts invalid artifacts.
5. The frontend defaults to mock fallback on read failures, so auth/backend/schema failures can render fixture data.

## 2. Review Scope

Reviewed:

- Repository guidance: `AGENTS.md`, README, canonical architecture/API docs, package/build/test configs, CI workflows, and runtime/release scripts.
- Backend: FastAPI app/middleware, private route boundary, error handlers, key routers, artifact routes, job APIs, Deep Read runner.
- State: SQLite schema/migrations, job queue, worker, event log, identity/run IDs, runtime paths, restore drill.
- Security/privacy: local secrets, API-key fail-open behavior, artifact path boundaries, cloud table fallback, link rendering.
- Frontend: Vite/React API client, mock fallback, paper-note list/detail, triage access links, build.
- Tests/release: packaging entrypoint tests, macOS release preflight tests, identity helpers, GitHub workflows.

Skimmed:

- Other artifact stores/generators, remaining backend routers, remaining frontend pages/stores, broader `src/agents/`, `src/downloader/`, and `src/providers/`.
- Supporting docs not directly tied to code contracts.

Skipped:

- Generated/vendor/build output, caches, snapshots, lockfiles, obvious fixtures, and historical runtime artifacts unless directly relevant.
- External deployment infrastructure, live production DB contents, and actual cloud/reverse-proxy controls.

## 3. Findings Summary Table

| ID | Severity | Confidence | Category | File/line | Short issue | Suggested owner/action |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 | High | Security | `.env:1-2` | Workspace contains live provider secrets | Rotate keys; replace with placeholders/secret manager |
| 2 | P1 | High | Security | `backend/services/job_runner.py:410-422` | Cloud table API key is persisted into run artifacts | Strip secrets before writing `run_meta.json` |
| 3 | P1 | High | Data integrity | `src/services/identity.py:72-74` | Run IDs can collide and merge unrelated job state | Add UUID/random suffix and collision regression |
| 4 | P1 | High | Correctness | `scripts/init_db.py:28-55` | Fresh schema breaks Zotero sync | Align `papers.summary` schema/migration or make sync column-aware |
| 5 | P1 | High | Testing | `.github/workflows/phase3-integration-optin.yml:23-31` | Phase3 integration workflow uses unsupported Python | Move workflow to Python 3.13 or support 3.11 |
| 6 | P1 | High | Data integrity | `frontend/src/app/lib/config.ts:12-15` | Frontend auto mock fallback can mask real backend/auth failures | Disable fallback for reached-backend HTTP errors |
| 7 | P2 | High | Security | `src/ingest/cloud_table_fallback.py:199-214` | Cloud table fallback lacks privacy preflight lane metadata | Add payload classification/preflight before request |
| 8 | P2 | High | Reliability | `backend/services/job_runner.py:1047-1082` | Failed Deep Read artifacts can become orphaned from job state | Persist `artifact_dir` on failure/cancel paths |
| 9 | P2 | High | Security | `backend/routers/paper_notes.py:1402-1424` | Rendered note/access links lack scheme allowlist | Add backend/frontend URL sanitizer |
| 10 | P2 | Medium | Security | `backend/main.py:5625` | Artifact route/store IDs lack proven root confinement | Add ID allowlist and resolved-path confinement tests |
| 11 | P2 | Medium | Security | `backend/main.py:268-273` | Private API auth is fail-open without configured key | Require explicit dev mode or fail closed |
| 12 | P2 | High | Data integrity | `src/db_utils.py:396-408` | `save_paper_state()` silently drops DB write failures | Surface/log/raise write failures |
| 13 | P2 | High | Reliability | `src/downloads_watcher.py:311-319` | Downloads watcher can move partial PDFs | Wait for file stability before moving |
| 14 | P2 | High | Testing | `src/agents/stats_agent.py:5` | `--verify` depends on undeclared `langgraph` | Declare dependency/extra and test clean install |
| 15 | P2 | High | Testing | `tests/test_packaging_entrypoints.py:121-150` | Packaging installability test is not clean | Use isolated venv and install deps from metadata |
| 16 | P2 | High | Reliability | `scripts/release_macos_personal_runtime.py:339-343` | macOS preflight accepts invalid artifacts as ready | Validate bundle structure and executable bits |
| 17 | P2 | High | Maintainability | `backend/main.py:917-932` | API error/write contracts diverge from canonical spec | Add schemas and normalize response envelopes |
| 18 | P3 | High | Testing | `scripts/check_sqlite_restore_drill.py:13-14` | Restore drill validates only `papers` by default | Expand required operational tables |

## 4. Detailed Findings

Detailed entries are maintained in `.codex-review/findings.md`.

## 5. Test And Command Results

Commands run:

- `.venv314/bin/python --version`
  - Result: passed, Python 3.14.3.
- `.venv314/bin/python -m pytest -q tests/test_packaging_entrypoints.py tests/test_release_macos_personal_runtime.py tests/test_identity_helpers.py`
  - Result: failed: 3 failed, 13 passed.
  - Failure cause: all failures are in `tests/test_packaging_entrypoints.py`; wheel-building test helper invokes `python -m pip`, but the local `.venv314` interpreter has no `pip` module. This is an environment blocker for the packaging tests in this run, not a proof the package itself cannot build.
- `cd frontend && npm run build`
  - Result: passed. `tsc -b && vite build` completed successfully.

Additional verification evidence:

- Data review used temp DB probes to confirm run ID collision behavior and fresh-schema Zotero sync failure.
- Static line-level inspection confirmed the remaining findings.

Commands not run:

- Full pytest suite: not run because focused review already exposed packaging environment failure and the full suite would be expensive relative to this artifact-only review.
- Playwright/frontend e2e: not run; frontend build passed, but browser behavior should be covered in follow-up tests for mock fallback and unsafe links.
- Backend smoke script: not run in this pass to avoid widening runtime side effects beyond review artifacts.
- Live cloud/API tests: not run to avoid external calls and secrets exposure.

## 6. Coverage Summary

- Production modules/files discovered: 258 tracked files under `backend/**/*.py`, `src/**/*.py`, and `frontend/src/**/*`.
- High-risk areas reviewed directly: auth middleware, private route list, local secrets, cloud inference lane, job queue/worker/runner, SQLite schema/migrations, event log/run IDs, artifact path helpers/stores, frontend API/mock fallback, note/access link rendering, CI workflows, packaging/release tests.
- Detailed coverage table: `.codex-review/coverage.md`.

Remaining blind spots:

- No live production SQLite contents, historical artifacts, external deployment infra, reverse proxy rules, or secret manager configuration were inspected.
- Artifact path traversal is marked needs verification because static composition is risky but a quick encoded traversal probe did not confirm disclosure.
- API fail-open risk depends on actual deployment exposure; code is fail-open without a key, but local-only operation may be intended.
- Frontend e2e and full backend smoke were not run.
- Scientific/biomedical output correctness was outside this code-level risk review.

## 7. Recommended Next Actions

Fix first:

1. Rotate local provider secrets and prevent cloud table API keys from entering `run_meta.json`.
2. Make `run_id` unique and align fresh DB schema with Zotero sync.
3. Change frontend mock fallback so reached-backend auth/server/schema errors do not render fixture data.
4. Move Phase3 workflow to Python 3.13 and repair installability/release-preflight checks.
5. Add privacy preflight for cloud table fallback and URL sanitization for rendered links.

Tests to add first:

1. Run ID collision regression with a fixed clock and two distinct papers.
2. Fresh DB + Zotero sync bootstrap test.
3. Secret redaction test for raw `run_meta.json`.
4. Frontend 401/403 mock-fallback regression and unsafe-link rendering test.
5. Clean wheel install test without system site packages or `--no-deps`.

Refactors that would reduce future risk:

1. Centralize API response/error schemas under `src/schemas/` and enforce them via contract tests.
2. Centralize artifact ID validation and resolved-path confinement for all file-backed stores.
3. Make DB write helpers return explicit success/failure instead of silently swallowing operational errors.
4. Treat privacy preflight as a required wrapper for every external inference lane.
