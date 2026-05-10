# Unreachable or Disconnected Code Candidates

## Unreachable candidate: R1 Global feedback and review-log routers without first-party frontend callers

Status: Needs verification
File/line:
`backend/routers/feedback.py:35`, `backend/routers/artifact_feedback.py:22`, `backend/routers/artifact_generation_outcomes.py:25`, `backend/routers/project_context_links.py:51`
Expected entry point:
Frontend/API clients submitting feedback, artifact review feedback, generation outcomes, and project-context link decisions.
Actual reachability:
Routers are mounted by FastAPI, but no first-party frontend caller was found in the current route graph/API client.
Evidence:
Handlers exist and are protected/mounted; frontend API paths found cover jobs, skills, paper notes, packs, chart/method/image/protocol surfaces, but not these global endpoints.
Why it appears unreachable:
No route/page/API client call path found from `frontend/src/App.tsx` and `frontend/src/app/lib/api.ts`.
Possible hidden runtime usage:
External clients, admin scripts, future UI, direct operator curl, tests.
Impact:
If not used, review/action telemetry may never be collected. If external-only, docs/smoke tests should name the producer.
Removal risk: Medium
Suggested action:
Do not remove yet. Classify as intentionally external/admin or add first-party producer coverage.
Suggested verification:
Search runtime request logs and docs; ask product owner whether these are public/admin surfaces.

## Unreachable candidate: R2 Talk Pack backend surface has no frontend route

Status: Needs verification
File/line:
`backend/routers/talk_packs.py:27`, `frontend/src/App.tsx:84`
Expected entry point:
Frontend Talk Pack page or API client flow.
Actual reachability:
Backend router is mounted, but `frontend/src/App.tsx:84-100` has no `/talk-packs` route.
Evidence:
`docs/TALK_PACK.md:54-60` says no active `talk_pack` runtime family exists yet and only a thin router/render seam may exist.
Why it appears unreachable:
API/test/render seam exists without user-facing route.
Possible hidden runtime usage:
CLI, smoke scripts, future/manual API use.
Impact:
Users cannot discover/render talk packs in current UI.
Removal risk: Medium
Suggested action:
Treat as API/test-only until a fuller runtime family is approved; do not delete without checking Talk Pack roadmap.
Suggested verification:
Run talk pack render smoke and inspect docs for intended lifecycle.

## Unreachable candidate: R3 `/api/chat` enabled behavior

Status: Confirmed unreachable
File/line:
`backend/main.py:4804`
Expected entry point:
Chat API route.
Actual reachability:
Route is reachable, but useful chat behavior is intentionally unreachable; both disabled and enabled paths return HTTP 501.
Evidence:
`backend/main.py:4807-4819` returns 501 when disabled; `backend/main.py:4819-4825` returns 501 when enabled. Docs describe stub-only behavior.
Why it appears unreachable:
No LLM/memory/RAG execution path is implemented behind this route.
Possible hidden runtime usage:
Clients may probe it as a reserved contract.
Impact:
Product/API scope confusion if consumers expect chat to work.
Removal risk: High
Suggested action:
Do not remove abruptly; keep as reserved contract or plan formal deprecation.
Suggested verification:
Check docs/tests/API clients before changing route.

## Unreachable candidate: R4 Retraction audit is not scheduled

Status: Probably unreachable
File/line:
`src/audit_retractions.py:12`, `src/retraction.py:7`
Expected entry point:
Cron/scheduled weekly audit, CLI command, or ingest retraction gate.
Actual reachability:
Only script self-entry found; no scheduler, CLI command, FastAPI path, or CI workflow.
Evidence:
`rg` found only script/self references plus historical docs/config.
Why it appears unreachable:
`config.system.check_retraction_on_ingest` exists, but no active caller was found.
Possible hidden runtime usage:
External cron or manual operator invocation.
Impact:
Retraction data may not update unless manually run.
Removal risk: Medium
Suggested action:
Verify whether the audit is operational. If inactive, archive or document as dormant.
Suggested verification:
Check crontab/automations and runbooks outside repo.

## Unreachable candidate: R5 `src/fetchers.py::fetch_arxiv`

Status: Probably unreachable
File/line:
`src/fetchers.py:23`
Expected entry point:
Legacy watcher/fetcher path.
Actual reachability:
No caller found; watcher imports only `fetch_pubmed`.
Evidence:
`src/watcher.py:10` imports `fetch_pubmed`; only comment references `fetch_arxiv`.
Why it appears unreachable:
Modern fetch path uses `src.fetch.get_fetchers`.
Possible hidden runtime usage:
External/manual legacy import.
Impact:
Duplicated ArXiv logic can drift from `src/fetch/arxiv.py`.
Removal risk: Medium
Suggested action:
Deprecate/remove after confirming no manual scripts import it.
Suggested verification:
Search local scripts and run fetch/provider tests.
