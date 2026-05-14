# Unreachable or Disconnected Code Candidates

## Unreachable candidate: R1 Global feedback and review-log routers without first-party frontend callers

Status: Do not remove
File/line:
`backend/routers/feedback.py:35`, `backend/routers/artifact_feedback.py:22`, `backend/routers/artifact_generation_outcomes.py:25`, `backend/routers/project_context_links.py:51`
Expected entry point:
Frontend/API clients submitting feedback, artifact review feedback, generation outcomes, and project-context link decisions.
Actual reachability:
Routers are mounted by FastAPI. No first-party frontend caller was found in the current route graph/API client, but follow-up Phase 4 review found these are active runtime/API logging surfaces rather than deletion candidates.
Evidence:
Handlers exist and are protected/mounted; frontend API paths found cover jobs, skills, paper notes, packs, chart/method/image/protocol surfaces, but not these global endpoints. Follow-up evidence: `backend/main.py:6089` and `backend/main.py:6091` include the routers; `backend/routers/feedback.py:51` and `backend/routers/artifact_feedback.py:22` register write endpoints; `backend/services/job_runner.py:393` uses similar feedback retrieval.
Why it appears unreachable:
No route/page/API client call path found from `frontend/src/App.tsx` and `frontend/src/app/lib/api.ts`.
Possible hidden runtime usage:
External clients, admin scripts, future UI, direct operator curl, tests. Some runtime behavior is already explicit through feedback retrieval and documented API contracts.
Impact:
If first-party producers remain unclear, review/action telemetry ownership may be confusing. This does not make the mounted routes dead.
Removal risk: High
Suggested action:
Do not remove. Classify as active runtime/admin API surfaces; add producer documentation or smoke coverage if needed.
Suggested verification:
Search runtime request logs and docs; ask product owner whether these are public/admin surfaces.

## Unreachable candidate: R2 Talk Pack backend surface has no frontend route

Status: Do not remove yet
File/line:
`backend/routers/talk_packs.py:27`, `frontend/src/App.tsx:84`
Expected entry point:
Frontend Talk Pack page or API client flow.
Actual reachability:
Backend router is mounted, covered by API tests, and supported by docs/verification scripts, but the first-party frontend route graph has no `/talk-packs` route.
Evidence:
`backend/main.py:6095` includes `talk_packs.router`; `backend/routers/talk_packs.py:19` registers the bounded API surface; `tests/test_talk_packs_api.py` covers list/detail/artifact/preview/render-deck behavior; `scripts/run_talk_pack_verify.sh` and `scripts/check_talk_pack_render_smoke.py` provide focused verification; `docs/TALK_PACK.md` describes the bounded export lane.
Why it appears unreachable:
API/test/render seam exists without user-facing route.
Possible hidden runtime usage:
CLI, smoke scripts, future/manual API use.
Impact:
Users cannot discover/render talk packs in current UI.
Removal risk: High
Suggested action:
Do not remove yet. Treat as a bounded API/export surface and roadmap/API-governance item, not a dead-code deletion candidate.
Suggested verification:
Run talk pack render smoke and inspect docs for intended lifecycle.

## Unreachable candidate: R3 `/api/chat` enabled behavior

Status: Do not remove
File/line:
`backend/main.py:4804`
Expected entry point:
Chat API route.
Actual reachability:
Route is reachable, but useful chat behavior is intentionally unreachable; both disabled and enabled paths return HTTP 501. Follow-up Phase 4 review confirms this is a deliberate stub-only compatibility surface, not ordinary dead code.
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
Do not remove. Keep as reserved/stub compatibility contract unless a formal API deprecation replaces it.
Suggested verification:
Check docs/tests/API clients before changing route.

## Unreachable candidate: R4 Retraction audit is not scheduled

Status: Needs operator confirmation
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
Do not delete from repo-only evidence. Verify whether the audit is operational through operator cron/automation/runbook checks before any archive/remove proposal.
Suggested verification:
Check crontab/automations and runbooks outside repo.

## Unreachable candidate: R5 `src/fetchers.py::fetch_arxiv`

Status: Cleaned after audit (was probably unreachable)
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
No pending removal remains in this audit lane. Keep the external/manual import risk as review-only context if this helper is restored.
Suggested verification:
Search local scripts and run fetch/provider tests.
