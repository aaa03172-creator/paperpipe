## Wiring item: PDF import route and frontend call

Status: Connected
Expected connection:
Frontend PDF picker posts to backend import endpoint and navigates to the created note.
Actual connection:
`PaperNotesListPage` calls `importPaperPdf`, which posts `/paper-notes/import-pdf`; backend router is included.
Files involved:
- `frontend/src/app/pages/PaperNotesListPage.tsx`
- `frontend/src/app/lib/api.ts`
- `backend/routers/paper_notes.py`
- `backend/main.py`
Evidence:
`frontend/src/app/pages/PaperNotesListPage.tsx:812`, `frontend/src/app/lib/api.ts:995`, `backend/routers/paper_notes.py:2255`, `backend/main.py:6088`.
Impact:
Manual paper entry is reachable.
Suggested fix:
None for registration.
Suggested test:
Existing import API tests plus frontend contract coverage for response shape.

## Wiring item: Import to parser/job creation

Status: Connected for new writes; legacy local index needs rebuild
Expected connection:
Imported PDF should be parseable by downstream Deep Read, or import should clearly say parsing is a separate action.
Actual connection:
Import stores PDF and paper row but does not enqueue parsing. Downstream UI can queue Deep Read separately.
Files involved:
- `backend/routers/paper_notes.py`
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `backend/main.py`
Evidence:
Import returns after `PaperNoteImportResponse` at `backend/routers/paper_notes.py:1019`; Deep Read queue is separate at `backend/main.py:5809`.
Impact:
End-to-end parsing depends on user/UI follow-up, not import completion.
Suggested fix:
Document/import UI state boundary or add explicit optional enqueue action.
Suggested test:
Import then enqueue/run Deep Read for the returned `paper_id`, asserting artifacts.

## Wiring item: Deep Read enqueue to worker

Status: Connected
Expected connection:
Frontend/backend enqueue creates a job that worker claims and processes.
Actual connection:
`POST /jobs/deepread` enqueues; worker claims queued jobs and calls `run_deepread_job`.
Files involved:
- `backend/main.py`
- `src/jobs/queue.py`
- `src/jobs/worker.py`
Evidence:
`backend/main.py:5809`, `src/jobs/queue.py:67`, `src/jobs/queue.py:236`, `src/jobs/worker.py:108`, `src/jobs/worker.py:123`.
Impact:
Core background processing is wired when worker is running.
Suggested fix:
None for basic wiring.
Suggested test:
Existing job smoke tests; add worker restart/stale recovery test.

## Wiring item: Parser backend selection

Status: Connected
Expected connection:
Requested/configured parser backend controls the ingest backend and is visible in job metadata.
Actual connection:
Parser backend override is stored in execution run params, worker passes it to runner, runner resolves configured/docling-gated backend.
Files involved:
- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `backend/services/job_runner.py`
- `src/ingest/parser_backends.py`
Evidence:
`src/jobs/queue.py:150`, `src/jobs/worker.py:115`, `backend/services/job_runner.py:395`, `backend/services/job_runner.py:1229`, `src/ingest/parser_backends.py:1129`.
Impact:
Parser selection works, with Docling gated by config.
Suggested fix:
None for wiring; improve parser behavior separately.
Suggested test:
Existing `tests/test_job_runner_ingest_backend.py`.

## Wiring item: Parser output to persistence

Status: Connected
Expected connection:
Parser output is persisted and visible to downstream stages.
Actual connection:
`doc_artifact` is written to `document_artifact.json`, then passed to indexer/reader/sidecars.
Files involved:
- `backend/services/job_runner.py`
- `src/agents/ingest_agent.py`
Evidence:
`backend/services/job_runner.py:1256`, `backend/services/job_runner.py:1280`, `backend/services/job_runner.py:1441`, `backend/services/job_runner.py:1578`.
Impact:
Parsed artifact is used downstream.
Suggested fix:
None for wiring; improve semantic extraction/provenance.
Suggested test:
Assert `document_artifact.json` fields after an imported PDF Deep Read.

## Wiring item: Chunks to vector index

Status: Partially connected
Expected connection:
Chunks should be indexed in a paper-safe way and retrievable for that paper.
Actual connection:
New chunks are embedded/upserted with document-scoped vector IDs. Read-only local audit found 15,846 unversioned legacy vectors and 229 chunk-locator IDs in `./storage/rag/`.
Files involved:
- `src/agents/indexer_agent.py`
- `src/services/identity.py`
Evidence:
`src/agents/indexer_agent.py:22`, `src/agents/indexer_agent.py:90`, `src/agents/indexer_agent.py:125`, `src/agents/indexer_agent.py:135`.
Impact:
New writes are paper-scoped; old local index contents can still corrupt retrieval until rebuilt.
Suggested fix:
Back up and rebuild legacy local Chroma contents from current artifacts.
Suggested test:
Index two papers with same page/chunk ordinals and assert separate vector IDs; run before/after audit around rebuild.

## Wiring item: Claimset/artifacts to Paper Notes structured state

Status: Partially connected
Expected connection:
Successful Deep Read promotes resolved claimset into note structured state.
Actual connection:
Promotion runs best-effort only if note path resolves and candidate is eligible.
Files involved:
- `backend/services/job_runner.py`
- `src/services/deepread_state_projection.py`
Evidence:
`backend/services/job_runner.py:1989`, `src/services/deepread_state_projection.py:183`, `src/services/deepread_state_projection.py:196`.
Impact:
Artifacts can exist without note structured state if note resolution fails.
Suggested fix:
Expose promotion-skipped reason as first-class job/artifact metadata.
Suggested test:
Run Deep Read for DB-only paper with no note and assert clear promotion status.

## Wiring item: Frontend/backend type contract for import response

Status: Partially connected
Expected connection:
Frontend type should match backend `PaperNoteImportResponse`.
Actual connection:
Backend response includes `doi`; frontend type omits it.
Files involved:
- `src/schemas/paper_notes.py`
- `frontend/src/app/lib/types.ts`
Evidence:
`src/schemas/paper_notes.py:414`, `frontend/src/app/lib/types.ts:133`.
Impact:
Current UI may not need DOI, but contract drift can hide future usage bugs.
Suggested fix:
Update TS type or generate frontend types from schema.
Suggested test:
Frontend/backend contract test for import response.

## Wiring item: Worker stale recovery

Status: Partially connected
Expected connection:
Worker restart should recover or unblock stale running jobs.
Actual connection:
Worker only claims queued jobs; stale recovery exists behind ops endpoints.
Files involved:
- `src/jobs/worker.py`
- `src/jobs/queue.py`
- `backend/main.py`
Evidence:
`src/jobs/worker.py:31`, `src/jobs/queue.py:213`, `src/jobs/queue.py:217`, `backend/main.py:5541`.
Impact:
Crash/restart can block future jobs for a paper until manual reclaim.
Suggested fix:
Add startup/periodic stale reconciliation or explicit operational runbook + alert.
Suggested test:
Seed stale running job, start worker loop/reclaim routine, assert queue unblocked.
