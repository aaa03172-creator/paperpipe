## Failure case: Invalid or unsupported upload

Expected safe behavior:
Reject before storage.
Actual behavior:
Empty payload and non-`%PDF-` payload are rejected; `%PDF-` minimal/corrupt payload can pass import and fail later.
Files involved:
`backend/routers/paper_notes.py`
Status handling:
No job status, import error only.
Data consistency behavior:
If accepted then later failure occurs, DB/file cleanup is partial.
User-visible behavior:
HTTP 400 for empty/non-PDF; later parser failure only when Deep Read is run.
Retry/recovery behavior:
User can re-import same bytes but may hit stale row risk.
Risk:
Malformed PDFs can enter as `NEW` papers.
Suggested fix:
Attempt lightweight PDF open during import before persisting, or mark parseability unknown.
Suggested test:
Upload `%PDF-1.4` truncated file and assert rejection or explicit unparseable state.
Evidence:
`backend/routers/paper_notes.py:937`, `backend/routers/paper_notes.py:939`.

## Failure case: Oversized PDF

Expected safe behavior:
Reject before storage.
Actual behavior:
Upload reader enforces configurable byte limit.
Files involved:
`backend/routers/paper_notes.py`
Status handling:
HTTP 413.
Data consistency behavior:
No file/DB write before full payload read completes.
User-visible behavior:
Error message includes configured limit.
Retry/recovery behavior:
User can retry with smaller file/config.
Risk:
Low for import; large but below-limit parsing/LLM time remains separate.
Suggested fix:
Add parse/run resource limits for page count and reader budget visibility.
Suggested test:
Existing oversized import test plus large valid PDF Deep Read smoke.
Evidence:
`backend/routers/paper_notes.py:233`, `backend/routers/paper_notes.py:241`.

## Failure case: Scanned PDF without OCR

Expected safe behavior:
Either OCR or explicit low-text/unparseable status.
Actual behavior:
OCR only runs when enabled; otherwise parser may produce sparse/empty sections.
Files involved:
`src/agents/ingest_agent.py`, `src/ingest/ocr_fallback.py`
Status handling:
May proceed to index/read with poor text unless ingest fails.
Data consistency behavior:
Artifacts may be created with low-quality content.
User-visible behavior:
OCR metadata exists only if enabled/attempted.
Retry/recovery behavior:
Rerun with OCR config.
Risk:
Real scanned papers require OCR to be enabled and OCRmyPDF/Tesseract installed; generated English image-only fixture now passes.
Suggested fix:
Record low-text detection in run metadata even when OCR disabled; fail or warn clearly.
Suggested test:
Real image-only scanned PDF fixture through ingest is covered; add full worker/Deep Read scanned fixture if runtime cost is acceptable.
Evidence:
`src/agents/ingest_agent.py:172`, `src/ingest/ocr_fallback.py:32`.

## Failure case: Missing PDF for Deep Read

Expected safe behavior:
Fail job with clear error and no partial artifacts beyond status/log.
Actual behavior:
Runner emits error and returns failed before artifact dir creation.
Files involved:
`backend/services/job_runner.py`, `src/jobs/worker.py`
Status handling:
Worker marks job failed.
Data consistency behavior:
No parser artifacts.
User-visible behavior:
Job error message.
Retry/recovery behavior:
Fix PDF path then re-enqueue after terminal status.
Risk:
Low.
Suggested fix:
None; add import-to-run integration test.
Suggested test:
Existing `tests/test_job_runner_pdf_lookup.py` plus missing path failure assertion.
Evidence:
`backend/services/job_runner.py:1105`, `backend/services/job_runner.py:1124`, `src/jobs/worker.py:186`.

## Failure case: Parser crash / malformed PDF during Deep Read

Expected safe behavior:
Job fails, records run metadata, no stale running job.
Actual behavior:
Ingest returns `None` on exception; runner raises and broad failure path writes metadata.
Files involved:
`src/agents/ingest_agent.py`, `backend/services/job_runner.py`
Status handling:
Failed job/run if failure path completes.
Data consistency behavior:
Partial run dir may exist.
User-visible behavior:
Job failed with sanitized error.
Retry/recovery behavior:
Re-enqueue after terminal failure.
Risk:
Failure-path handoff writer can itself fail.
Suggested fix:
Guard failure-path handoff writes.
Suggested test:
Mock parser and handoff writer failures together; assert terminal failed job.
Evidence:
`src/agents/ingest_agent.py:297`, `backend/services/job_runner.py:2023`, `backend/services/job_runner.py:2037`.

## Failure case: Duplicate upload / duplicate DOI

Expected safe behavior:
Same file should map to same import; same DOI policy should be explicit.
Actual behavior:
Same file content maps to same `userpdf-*`; new writes/imports guard normalized DOI duplicates, but existing duplicate rows can remain.
Files involved:
`backend/routers/paper_notes.py`, `scripts/init_db.py`, `src/db_utils.py`
Status handling:
Existing duplicate rows can have separate statuses/jobs until reconciled.
Data consistency behavior:
Fragmented canonical state.
User-visible behavior:
Duplicate papers may appear.
Retry/recovery behavior:
Read-only duplicate DOI reporting is available; manual/approved reconciliation still required.
Risk:
Medium for new writes; high for unreconciled existing duplicates.
Suggested fix:
Run read-only duplicate DOI audit, then define normalized DOI uniqueness/backfill policy.
Suggested test:
Different paper IDs, same DOI should not create two canonical rows without explicit conflict.
Evidence:
`backend/routers/paper_notes.py:947`, `scripts/init_db.py:75`, `src/db_utils.py:396`.

## Failure case: Vector store/indexing failure

Expected safe behavior:
No loss of previous searchable index; job fails clearly.
Actual behavior:
Clean reindex now upserts replacement vectors before pruning stale vectors and skips prune when replacement vectors are partial or empty.
Local read-only audit initially confirmed legacy index contents: 15,846 unversioned vectors and 229 chunk-locator vector IDs. A guarded apply rebuild then reindexed 13,171 backed-by-artifact chunks and post-rebuild audit reported zero legacy/unversioned vectors.
Files involved:
`src/agents/indexer_agent.py`, `backend/services/job_runner.py`
Status handling:
Job fails if exception propagates.
Data consistency behavior:
New clean reindex preserves old vectors on partial replacement; local legacy unscoped vectors have been rebuilt, while production/remote stores remain unverified.
User-visible behavior:
Search/RAG quality for new writes is protected from the prior delete-first failure; local legacy index contents are now rebuilt.
Retry/recovery behavior:
Rerun without failure can rebuild; apply failures after backup/delete now restore `vector_root` from the backup and return non-zero status.
Risk:
Medium for new writes and local rebuilt Chroma; unknown for any production/remote Chroma copy not audited with the same tool.
Suggested fix:
Use the same backed-up rebuild flow for any non-local vector store, and document manual rollback steps for operators.
Suggested test:
Simulate partial replacement and assert previous vectors still exist; restore-from-backup after rebuild apply failure is now covered by `tests/test_rebuild_vector_index_script.py`.
Evidence:
`src/agents/indexer_agent.py:46`, `src/agents/indexer_agent.py:50`, `backend/services/job_runner.py:1442`.

## Failure case: Concurrent parsing of same paper

Expected safe behavior:
Only one open job per paper.
Actual behavior:
`BEGIN IMMEDIATE` plus open-job query blocks duplicate queued/running jobs.
Files involved:
`src/jobs/queue.py`
Status handling:
Second enqueue returns duplicate open job error.
Data consistency behavior:
Prevents simultaneous artifact writes for same paper.
User-visible behavior:
HTTP 409 through API.
Retry/recovery behavior:
Allowed after terminal status.
Risk:
Low for active jobs; stale running jobs are separate risk.
Suggested fix:
None for active concurrency.
Suggested test:
Existing duplicate job tests.
Evidence:
`src/jobs/queue.py:91`, `src/jobs/queue.py:103`, `backend/main.py:5826`.

## Failure case: Worker restart with running job

Expected safe behavior:
Stale job reclaimed or requeued automatically, or clear alert.
Actual behavior:
Worker counts running jobs and claims only queued jobs; ops endpoints exist for manual reclaim.
Files involved:
`src/jobs/worker.py`, `src/jobs/queue.py`, `backend/main.py`
Status handling:
Can remain `running`.
Data consistency behavior:
Open-job dedupe blocks re-enqueue.
User-visible behavior:
Job appears stuck unless ops diagnostics are used.
Retry/recovery behavior:
Manual reclaim/requeue.
Risk:
High for unattended worker crash.
Suggested fix:
Startup/periodic stale reclaim policy.
Suggested test:
Seed stale running job, restart worker, assert recovery path.
Evidence:
`src/jobs/worker.py:31`, `src/jobs/queue.py:213`, `src/jobs/queue.py:217`, `backend/main.py:5541`.

## Failure case: User cancellation during long phase

Expected safe behavior:
Stop before expensive work and before artifact writes.
Actual behavior:
Cancellation checks occur between major phases, not inside/after long calls before artifact writes.
Files involved:
`backend/services/job_runner.py`, `src/jobs/worker.py`
Status handling:
Worker preserves terminal cancellation if observed, but long work may continue.
Data consistency behavior:
Partial artifacts can be written after cancellation request.
User-visible behavior:
Cancel may lag.
Retry/recovery behavior:
Re-enqueue after terminal cancellation.
Risk:
Medium.
Suggested fix:
Check cancellation immediately after ingest/index/read calls and before writes; pass cancellation into agents where feasible.
Suggested test:
Cancel during mocked long index/read and assert no later artifact writes.
Evidence:
`backend/services/job_runner.py:1256`, `backend/services/job_runner.py:1452`, `backend/services/job_runner.py:1578`.

## Failure case: Downstream reads before extraction completes

Expected safe behavior:
Surface queued/running/not-ready state without pretending results exist.
Actual behavior:
Jobs and ops summaries expose status; note structured state may be absent until promotion.
Files involved:
`backend/main.py`, `backend/routers/paper_notes.py`, `src/services/paper_ops_summary.py`
Status handling:
Job status APIs available.
Data consistency behavior:
No partial structured state promotion until succeeded.
User-visible behavior:
Workbench/Paper Notes can show job status and guidance.
Retry/recovery behavior:
Wait or requeue after failure.
Risk:
Medium; paper row `status` can remain `NEW`, creating ambiguity.
Suggested fix:
Clarify lifecycle boundary and expose latest job parse status on paper summaries.
Suggested test:
Read paper detail while job running; assert parse status and no fake claimset.
Evidence:
`src/services/deepread_state_projection.py:41`, `backend/main.py:5924`.
