# Dead Code, Unused Code, and Duplicate Logic Audit Report

## 1. Executive summary

Overall cleanup opportunity: Medium
Overall removal risk: Medium / High

Safest cleanup candidates originally identified:
`src/test_download.py`, no-op `log_workflow_step`, unused private frontend exports, root `inspect_*.py` probes, and `copy_case.py`.

Follow-up cleanup completed:
Phase 1 and most Phase 2 low-risk candidates were cleaned after the audit: U1, U2, U3, U4, U5, U6, U8, U10, U11, and L7. D1's frontend fallback drift was aligned with the backend completed-note issue-state rule. D2 was partially consolidated through shared backend/frontend identity helpers and route-level alias tests, and D3 now has focused golden tests for ops-summary derivation.

Unused-looking but risky:
`src/providers/*`, `/api/chat`, the paper-synthesis compatibility bundle route, global feedback/review-log endpoints, the retraction audit path, and the legacy trial extraction alias.

Highest-risk duplicate logic:
Artifact bundle rollback/persistence helpers remain the highest-risk duplicate logic, but failure-injection coverage was strengthened for the artifact stores reviewed: Meeting Pack, Protocol Card, Chart Pack, Image Evidence, Talk Pack, Method Comparison, Paper Synthesis, Project Memory, and Protocol Attachment. A D4 per-store difference review now records why helper extraction should happen by store family rather than as one broad rewrite; the first shared helper extraction has been applied only to simple text bundle stores. Paper/Zotero identity expansion now has shared helpers and focused route-level regression coverage; broader API alias-contract sweeps can still be added if more surfaces are changed.

Obsolete legacy code to investigate first, not remove directly:
The paper-synthesis compatibility route and root legacy instructions, followed by manual probe scripts.

Do not remove without manual verification:
Public routes, Typer command functions, FastAPI router handlers, skill registry actions, worker/job code, `src/providers/*`, and config aliases with scheduled removal dates.

Phase 4 follow-up:
High-risk candidates now have a dedicated manual-verification checklist in `phase4-manual-verification.md`. Current evidence reclassifies `/feedback` and `/artifact-feedback` as active runtime surfaces, `/api/chat` as a deliberate stub-only compatibility surface, Talk Pack as a bounded API/export surface without a first-party frontend route, and the legacy `trial-extraction` alias as blocked until the 2026-06-30 removal window.

## 2. Scope reviewed

Reviewed:
`backend/`, `src/`, `frontend/src/`, `frontend/package.json`, `scripts/`, `scripts/eval/`, `evals/paper_skill_gym/`, `.github/workflows/`, `docs/`, `config/`, targeted tests and package metadata.

Partially reviewed:
Large tests/docs/snapshots/goldsets and generated/runtime artifacts.

Skipped:
`node_modules`, virtualenvs, build outputs, caches, most runtime `storage/`, large generated snapshots except tracked oddities.

Needs verification:
External callers, private local scripts, cron/automation usage, runtime request logs, packaged-user imports, dynamic `getattr/importlib` cases.

## 3. Unused code summary

| ID | Item | Type | Status | File/line | Evidence strength | Removal risk | Suggested action |
|---|---|---|---|---|---|---|---|
| U1 | `src/test_download.py` | Script | Cleaned after audit | `src/test_download.py:2` | Strong | Low | No pending removal |
| U2 | `save_embedding`, `get_all_embeddings` | Functions | Cleaned after audit | `src/db.py:355`, `src/db.py:375` | Strong internal | Medium | Cleaned after audit; keep public import risk in review notes |
| U3 | `log_workflow_step` | Function | Cleaned after audit | `src/db_utils.py:831` | Strong | Low | Cleaned after audit |
| U4 | `lifecycleToPaperStatus` | Export | Cleaned after audit | `frontend/src/app/lib/ui.ts:22` | Strong | Low | Cleaned after audit |
| U5 | Paper-note ops helpers | Exports | Cleaned after audit | `frontend/src/app/lib/paperNoteOps.ts:30`, `:56` | Strong | Low | Cleaned after audit |
| U6 | `fetch_arxiv` legacy helper | Function | Cleaned after audit | `src/fetchers.py:23` | Good | Medium | Cleaned after audit; external/manual import risk remains review-only |
| U7 | Retraction audit path | Script/service | Needs operator confirmation | `src/audit_retractions.py:12`, `src/retraction.py:7` | Medium | Medium | Confirm operator workflow before any archive/remove proposal |
| U8 | `ChartValueKind`, `PaperSynthesisResponse` | Types | Cleaned after audit | `frontend/src/app/lib/types.ts:668`, `:1058` | Strong internal | Low/Medium | Cleaned after audit |
| U9 | `src/providers/*` | Modules | Do not remove yet | `src/providers/base.py:1` | Strong internal | High | Deprecate first; do not delete directly |
| U10 | `inspect_*.py` | Scripts | Cleaned after audit | `inspect_agent.py:2` etc. | Strong | Low | Cleaned after audit |
| U11 | `copy_case.py` | Script | Cleaned after audit | `copy_case.py:5` | Strong | Low | Cleaned after audit |

## 4. Unreachable code summary

| ID | Item | Expected entry point | Actual reachability | Status | Risk | Suggested action |
|---|---|---|---|---|---|---|
| R1 | Global feedback/review-log routers | First-party UI/API producers | Mounted API; no frontend caller found, but active runtime/admin surface | Do not remove | High | Keep; document producer if needed |
| R2 | Talk Pack API | Frontend Talk Pack route | Backend mounted/tested/documented, no UI route | Do not remove yet | High | Keep as bounded API/export surface; handle via roadmap/API governance |
| R3 | `/api/chat` behavior | Chat execution | Route reachable, useful behavior always 501 by design | Do not remove | High | Keep as stub-only compatibility surface |
| R4 | Retraction audit | Cron/CLI/scheduler | Only self-entry found | Needs operator confirmation | Medium | Confirm automation/manual use before any archive/remove proposal |
| R5 | `fetch_arxiv` | Legacy fetch path | No caller found | Cleaned after audit | Medium | No pending removal; external import risk remains review-only |

## 5. Duplicate logic summary

| ID | Duplicated logic | Files involved | Risk | Suggested consolidation | Tests needed first |
|---|---|---|---|---|---|
| D1 | Note-backed paper summary synthesis | `backend/main.py`, `frontend/src/app/lib/api.ts` | Medium | Frontend issue-state drift aligned; backend-owned contract still preferred | Frontend lint/build passed; note fallback contract tests still useful |
| D2 | Paper/Zotero ID candidates | `backend/main.py`, `backend/routers/paper_notes.py`, frontend helpers | Medium/High | Partially consolidated into shared helpers | Parameterized identity tests and route-level alias tests added |
| D3 | Ops-summary derivation | `src/services/paper_ops_summary.py`, `frontend/src/app/lib/paperNoteOps.ts` | Low/Medium | Prefer backend summary | Ops-summary golden cases added |
| D4 | Artifact bundle rollback | Multiple artifact stores | Medium/High | Simple text helper extracted; keep `d4-store-differences.md` as the gate for further extraction | Failure-injection preservation tests added for artifact stores reviewed |
| D5 | Rate-limit/audit response construction | `backend/main.py` middleware | Medium | Rate-limit response and audit payload helpers extracted; further middleware reshaping still open | Rate-limit response/audit contract tests strengthened |

## 6. Obsolete legacy code summary

| ID | Item | Why obsolete | Current usage | Risk if kept | Risk if removed | Suggested action |
|---|---|---|---|---|---|---|
| L1 | Paper synthesis bundle route | Deprecated; split routes preferred | First-party ready, external deletion not confirmed | API bloat | External callers break | Keep until runtime/external proof |
| L2 | Legacy trial extraction alias | Scheduled rename | Active compatibility until 2026-06-30 | Naming ambiguity | Config break before date | Re-check after removal window opens |
| L3 | `src/providers/*` | Re-export wrappers | No internal use | Duplicate import surface | External import break | Deprecate first |
| L4 | `/api/chat` stub | Always 501 | Deliberate reserved/stub route | Confusion | Client/docs break | Keep unless formally deprecated |
| L5 | Root legacy instructions | Conflicts with AGENTS/current SSOT | No tooling refs found | Agent confusion | Historical loss | Archive/mark historical |
| L6 | Manual probe scripts | Stale/ad hoc | No refs found | Stale deps/noise | Manual diagnostics lost | Archive/remove |
| L7 | Tracked MagicMock Chroma artifacts | Generated/mock artifacts | No production refs expected | Repo noise | Fixture risk | Cleaned after targeted verification |

## 7. Removal risk matrix

See `removal-risk-matrix.md`.

## 8. Recommended cleanup order

See `cleanup-plan.md`.
For high-risk compatibility/public surfaces, see `phase4-manual-verification.md`.

## 9. Commands and validation

Commands run:
- `git status --short`
- `rg --files`, `find`, `git ls-files` inventory scans
- `rg` searches for route wiring, CLI entries, scripts, imports, symbol references, feedback endpoints, Talk Pack, paper synthesis compatibility, retraction audit, provider wrappers
- `nl -ba` targeted file reads for all cited candidates
- `python3 scripts/check_paper_synthesis_bundle_route_usage.py --root .`: passed with `offender_count: 0`; allowlisted compatibility references remain in docs/scripts/tests.
- Legacy trial extraction removal-readiness check for 2026-05-10 passed active-surface readiness, but `removal_window_open: false` and `ready_to_remove_alias_now: false` because the scheduled removal date is 2026-06-30.
- `cd frontend && npm run build`: passed.
- Artifact existence check for all eight requested markdown files: passed.
- Subagents ran additional static/runtime/duplicate/legacy review.
- Follow-up verification after cleanup: `python3 -m compileall src backend scripts` passed.
- Follow-up verification after cleanup: `.venv/bin/python -m pytest -q tests/test_identity_helpers.py tests/test_paper_ops_summary.py tests/test_db_utils_download_attempts.py tests/test_downloads_watcher.py` passed with 34 tests.
- Follow-up D2 alias verification: `.venv/bin/python -m pytest -q tests/test_paper_notes_api.py tests/test_artifacts_runs_api.py tests/test_identity_helpers.py` passed with 72 tests.
- Follow-up verification after cleanup: `cd frontend && npm run lint` passed.
- Follow-up verification after cleanup: `cd frontend && npm run build` passed.
- Follow-up D1 frontend fallback verification: `cd frontend && npm run lint` and `cd frontend && npm run build` passed after aligning completed note-backed fallback `issues_state`.
- Follow-up D4 rollback verification: `.venv/bin/python -m pytest -q tests/test_meeting_pack_store.py tests/test_protocol_card_store.py` passed with 12 tests after adding unrelated-file preservation checks.
- Follow-up D4 Chart Pack verification: `.venv/bin/python -m pytest -q tests/test_chart_pack_store.py` passed with 9 tests after adding unrelated-file preservation checks.
- Follow-up D4 Image Evidence/Talk Pack verification: `.venv/bin/python -m pytest -q tests/test_image_evidence_store.py tests/test_talk_pack_store.py tests/test_chart_pack_store.py tests/test_meeting_pack_store.py tests/test_protocol_card_store.py` passed with 40 tests after adding preservation checks.
- Follow-up D4 major-store verification: `.venv/bin/python -m pytest -q tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_image_evidence_store.py tests/test_talk_pack_store.py tests/test_chart_pack_store.py tests/test_meeting_pack_store.py tests/test_protocol_card_store.py` passed with 51 tests after adding Method Comparison and Paper Synthesis preservation checks.
- Follow-up D4 store-family review: `d4-store-differences.md` created to separate simple text bundles, managed text bundles, managed mixed/binary bundles, and fixed binary bundle risk before helper extraction.
- Follow-up D4 extended rollback verification: `.venv/bin/python -m pytest -q tests/test_project_memory_store.py tests/test_protocol_attachment_store.py` passed with 13 tests after adding Project Memory and Protocol Attachment preservation checks.
- Follow-up D4 full reviewed-store verification: `.venv/bin/python -m pytest -q tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_image_evidence_store.py tests/test_talk_pack_store.py tests/test_chart_pack_store.py tests/test_meeting_pack_store.py tests/test_protocol_card_store.py tests/test_project_memory_store.py tests/test_protocol_attachment_store.py` passed with 64 tests.
- Follow-up D4 helper extraction verification: `python3 -m py_compile src/services/artifact_transactions.py src/meeting_packs/store.py src/method_comparisons/store.py src/paper_syntheses/store.py src/project_memory/store.py` passed; `.venv/bin/python -m pytest -q tests/test_meeting_pack_store.py tests/test_method_comparison_store.py tests/test_paper_synthesis_store.py tests/test_project_memory_store.py` passed with 28 tests; the full reviewed-store D4 gate remained `64 passed`.
- Follow-up Phase 4 verification: paper-synthesis compatibility route usage audit reported `offender_count=0`; route removal readiness reported `active_surface_ready=true` but `ready_to_delete_api_bundle_route_now=false`; legacy trial alias audit reported `offender_count=0`; legacy trial alias readiness reported `removal_window_open=false` and `ready_to_remove_alias_now=false` for 2026-05-14.
- Final local evidence exhaustion pass: checked local crontab, macOS LaunchAgents/LaunchDaemons, Codex automations, local PKB references, and focused PaperPipe project/worktree references. No active local scheduler or independent operator script was found for `src/audit_retractions.py`; no independent local `src.providers` caller was found; Paper Synthesis compatibility route still lacks external-caller proof.
- Follow-up D5 middleware contract verification: `.venv/bin/python -m pytest -q tests/test_browser_request_audit_api.py` passed with 12 tests after strengthening rate-limit response and audit payload assertions.
- Follow-up D5 helper extraction verification: `python3 -m compileall backend/main.py` and `.venv/bin/python -m pytest -q tests/test_browser_request_audit_api.py` passed after extracting `_rate_limit_response` and `_rate_limit_audit_payload`.
- Follow-up reference check for removed/centralized symbols was run with `rg`; remaining matches are audit docs or unrelated backend schema names, not removed frontend symbols.

Failures:
- An initial broad Python source scan over the whole tree was stopped because runtime/storage trees made it too broad; scan was narrowed to tracked/source areas.

Commands not run and why:
- Full test suite was not run because this was an inspection-only audit and would be expensive/noisy for a no-production-code change.
- External caller and cron checks were not possible from repository source alone.

Manual searches performed:
FastAPI decorators/includes, React route table, frontend API path usage, Typer commands, worker/queue wiring, public exports, legacy aliases, duplicate artifact-store rollback patterns, status/identity/ops-summary logic.

## 10. Remaining blind spots

Dynamic usage that could not be fully verified:
Manual script invocation, `getattr/importlib`, shell aliases, local notebooks.

Public API usage that could not be fully verified:
External callers of deprecated paper-synthesis bundle route, `/api/chat`, global feedback/review endpoints, and `src.providers` imports.

Production-only usage that could not be fully verified:
Crons, launchd/systemd jobs, deployment scripts outside repo, runtime DB request history beyond local scripts.

Framework conventions that require manual confirmation:
FastAPI route registration, Typer command decorators, React lazy routes, skill registry actions, worker process startup.

External callers that cannot be checked from this repository:
Packaged users, private operator scripts, API clients, docs/bookmarks, and existing production deployments.

Final local closeout:
Local evidence has been exhausted for this lane. Remaining blockers require evidence outside this repository/local automation set: deployment request logs, packaged-user/import telemetry, or explicit operator confirmation.
