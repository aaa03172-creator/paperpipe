# Unused Code Candidates

## Unused candidate: U1 `src/test_download.py`

Status: Confirmed unused
Type: File / Script
File/line:
`src/test_download.py:2-10`
Evidence:
Imports `load_config` and `process_daily_slots`, defines `main()`, and only calls itself via `if __name__ == "__main__"`.
Searches performed:
`rg -n "test_download|src\.test_download|process_daily_slots" .`
Known references:
No imports, CLI registration, docs, or tests reference `src.test_download`; `process_daily_slots` itself is used elsewhere.
Potential dynamic usage:
Manual `python src/test_download.py` by an operator.
Production reachability:
Not reachable from FastAPI, CLI, worker, CI, package scripts, or frontend.
Removal risk: Low
Suggested action:
Remove or move to archived manual probes after checking local operator habits.
Suggested verification:
`rg -n "src.test_download|test_download.py"` and ask/inspect shell aliases outside repo if needed.
Suggested test/check after removal:
`pytest -q tests/test_cli_daily_slot_report.py tests/test_full_pipeline.py tests/test_processor_institutional_proxy.py`.

## Unused candidate: U2 `src/db.py` embedding helpers

Status: Confirmed unused
Type: Function
File/line:
`src/db.py:355`, `src/db.py:375`
Evidence:
`save_embedding()` and `get_all_embeddings()` have definition-only references. They operate on an `embeddings` table, but no runtime caller was found.
Searches performed:
`rg -n "save_embedding|get_all_embeddings|embeddings" src backend scripts tests docs`
Known references:
Definition-only for the functions; DB schema compatibility may still create/test related tables.
Potential dynamic usage:
External scripts importing legacy `src.db`.
Production reachability:
Not reached from current FastAPI, CLI, worker, indexer, or tests found.
Removal risk: Medium
Suggested action:
Deprecate or remove only after confirming `src.db` public compatibility policy.
Suggested verification:
Search packaged/user scripts and run import-health checks.
Suggested test/check after removal:
`pytest -q tests/test_db_schema_compat.py tests/test_indexer.py`.

## Unused candidate: U3 `src/db_utils.py::log_workflow_step`

Status: Confirmed unused
Type: Function
File/line:
`src/db_utils.py:831`
Evidence:
Function body is `pass`; no call sites found.
Searches performed:
`rg -n "log_workflow_step" .`
Known references:
Definition only.
Potential dynamic usage:
Low; public module helper could be imported externally.
Production reachability:
None found.
Removal risk: Low
Suggested action:
Remove in a small cleanup PR or replace with a documented no-op only if external API compatibility is desired.
Suggested verification:
Repo and package import search.
Suggested test/check after removal:
`pytest -q tests/test_jobs_events_persistence.py tests/test_db_utils_download_attempts.py`.

## Unused candidate: U4 `frontend/src/app/lib/ui.ts::lifecycleToPaperStatus`

Status: Confirmed unused
Type: Export
File/line:
`frontend/src/app/lib/ui.ts:22`
Evidence:
Neighbor helpers are used, but `lifecycleToPaperStatus` has no imports/call sites in frontend source.
Searches performed:
`rg -n "lifecycleToPaperStatus" frontend/src tests`
Known references:
Definition only.
Potential dynamic usage:
None expected after TypeScript build; public package boundary does not exist because frontend package is private.
Production reachability:
None found.
Removal risk: Low
Suggested action:
Remove export.
Suggested verification:
`cd frontend && npm run build`.
Suggested test/check after removal:
`cd frontend && npm run lint && npm run build`.

## Unused candidate: U5 Paper note ops frontend helpers

Status: Confirmed unused
Type: Export
File/line:
`frontend/src/app/lib/paperNoteOps.ts:30`, `frontend/src/app/lib/paperNoteOps.ts:56`
Evidence:
`buildPaperNoteOpsMap()` and `getPaperNoteOpsClassName()` are not imported by current components; related helpers remain used.
Searches performed:
`rg -n "buildPaperNoteOpsMap|getPaperNoteOpsClassName" frontend/src tests`
Known references:
Definition only.
Potential dynamic usage:
None expected in private Vite app.
Production reachability:
None found.
Removal risk: Low
Suggested action:
Remove unused exports.
Suggested verification:
`cd frontend && npm run build`.
Suggested test/check after removal:
`cd frontend && npm run lint && npm run build`.

## Unused candidate: U6 `src/fetchers.py::fetch_arxiv`

Status: Probably unused
Type: Function
File/line:
`src/fetchers.py:23`
Evidence:
`src.fetchers` is still used by `src/watcher.py:10` for `fetch_pubmed`, but `fetch_arxiv()` itself was only referenced by comments in `src/fetch/arxiv.py:35-39`.
Searches performed:
`rg -n "src\.fetchers|from src.fetchers|fetch_arxiv\(|fetch_pubmed\(" .`
Known references:
No functional call sites for `fetch_arxiv()`.
Potential dynamic usage:
Manual legacy scripts may import it from `src.fetchers`.
Production reachability:
Not reached by current processor, which uses `src.fetch.get_fetchers`.
Removal risk: Medium
Suggested action:
Remove only the function after a deprecation/search pass; keep `src.fetchers.fetch_pubmed` until watcher compatibility is addressed.
Suggested verification:
Search docs/operator scripts; run watcher tests.
Suggested test/check after removal:
`pytest -q tests/test_downloads_watcher.py tests/test_fetch_providers.py`.

## Unused candidate: U7 Retraction audit path

Status: Needs verification
Type: Script / Function / Service
File/line:
`src/audit_retractions.py:12`, `src/retraction.py:7`
Evidence:
`audit_retractions()` is only run by `src/audit_retractions.py` itself; no FastAPI, CLI, scheduler, or tests call it. `check_retraction()` is only called by that script.
Searches performed:
`rg -n "audit_retractions|check_retraction|Retraction" src backend scripts tests docs .github`
Known references:
Historical docs mention a retraction gate; config has `check_retraction_on_ingest`, but no active call path was found.
Potential dynamic usage:
Likely manual/weekly operator script.
Production reachability:
Not automatically scheduled from current repo.
Removal risk: Medium
Suggested action:
Decide whether this is an active operator workflow. If not, archive/remove with docs update.
Suggested verification:
Check crontab/automations/runbooks outside repo and any current policy for retraction checks.
Suggested test/check after removal:
`pytest -q tests/test_reporting.py tests/verify_config.py`.

## Unused candidate: U8 Frontend contract types

Status: Probably unused
Type: Type
File/line:
`frontend/src/app/lib/types.ts:668`, `frontend/src/app/lib/types.ts:1058`
Evidence:
`ChartValueKind` and `PaperSynthesisResponse` have no frontend imports. Paper synthesis frontend uses manifest/markdown split routes, not the deprecated bundle response.
Searches performed:
`rg -n "ChartValueKind|PaperSynthesisResponse" frontend/src tests`
Known references:
Definition only in frontend types.
Potential dynamic usage:
Low, but `types.ts` mirrors backend API contracts.
Production reachability:
None found in frontend runtime.
Removal risk: Low / Medium
Suggested action:
Remove only if frontend type mirror does not intentionally preserve deprecated API contract names.
Suggested verification:
`cd frontend && npm run build`.
Suggested test/check after removal:
`cd frontend && npm run lint && npm run build`.

## Unused candidate: U9 `src/providers/*` compatibility package

Status: Do not remove
Type: Module / Export package
File/line:
`src/providers/base.py:1`, `src/providers/__init__.py:1`
Evidence:
Wrappers re-export canonical `src.downloader.providers.*`; internal code and tests import `src.downloader.providers`, not `src.providers`.
Searches performed:
`rg -n "src\.providers|from src.providers|BaseDownloader" .`
Known references:
Only self-package references in repo.
Potential dynamic usage:
High for external packaged users or old scripts.
Production reachability:
Not used internally.
Removal risk: High
Suggested action:
Treat as public compatibility surface; deprecate before removal.
Suggested verification:
Search installed scripts/notebooks and release notes; run import-health check.
Suggested test/check after removal:
`pytest -q tests/test_downloader.py tests/test_cli_unpaywall_smoke.py`.

## Unused candidate: U10 root `inspect_*.py` effgen probes

Status: Probably unused
Type: Script
File/line:
`inspect_agent.py:2`, `inspect_basemodel.py:2`, `inspect_config.py:2`, `inspect_effgen.py:2`, `inspect_genresult.py:2`, `inspect_methods.py:2`
Evidence:
All import old `effgen` APIs and print reflection output; no first-party references found.
Searches performed:
`rg -n "inspect_agent|inspect_basemodel|inspect_config|inspect_effgen|inspect_genresult|inspect_methods" .`
Known references:
None.
Potential dynamic usage:
Manual ad hoc diagnostics only.
Production reachability:
None found; not package scripts or tests.
Removal risk: Low
Suggested action:
Remove or archive as historical probes.
Suggested verification:
Confirm `effgen` is not a supported runtime dependency.
Suggested test/check after removal:
`python3 -m compileall src backend scripts` or targeted import-health script.

## Unused candidate: U11 `copy_case.py`

Status: Probably unused
Type: Script
File/line:
`copy_case.py:5`
Evidence:
Hardcoded personal source path copies a docx into the repo; no references found.
Searches performed:
`rg -n "copy_case|PaperPipe_cases_only_checked_v3|PaperPipe_cases.docx" .`
Known references:
Script only.
Potential dynamic usage:
Manual one-off document copy.
Production reachability:
None.
Removal risk: Low
Suggested action:
Remove/archive; avoid keeping personal filesystem paths in tracked scripts.
Suggested verification:
Confirm `PaperPipe_cases.docx` is no longer generated by this path.
Suggested test/check after removal:
Not applicable beyond repo smoke/import checks.
