## Test gap: Import-to-Deep-Read end-to-end

Status: Partially covered
Production behavior:
Import stores PDF/row/note; separate Deep Read parses and writes artifacts.
Production files:
`backend/routers/paper_notes.py`, `backend/services/job_runner.py`, `src/jobs/worker.py`
Existing tests checked:
`tests/test_paper_notes_api.py`, `tests/test_cli_import_pdf.py`, `tests/test_job_runner_ingest_backend.py`
Missing scenario:
Import a PDF, persist DB/file/note state, resolve the stored DB `pdf_path`, enqueue Deep Read, and parse the resolved imported PDF with `IngestAgent.process_v2` are now covered. Full worker execution through artifact production still needs an E2E fixture.
Suggested test type: Integration
Suggested test location:
`tests/test_import_to_deepread_pipeline.py`
Suggested assertions:
DB `pdf_path` resolves; stored bytes match upload bytes; parser preserves sentinel text and v2 source refs; job completes with expected artifacts; parser backend recorded; structured state promotion status explicit.
Priority: P1
Reason:
Current tests now prove import-to-parser continuity, but not full worker artifact production and structured state promotion.

## Test gap: Vector ID collision across papers

Status: Covered for new writes
Production behavior:
Indexer writes all papers to one Chroma collection using local chunk IDs.
Production files:
`src/agents/indexer_agent.py`, `src/services/identity.py`
Existing tests checked:
`tests/test_indexer_agent_chunk_ids.py`
Missing scenario:
Legacy Chroma rebuild/migration for old unscoped vector IDs. Local audit initially found 15,846 unversioned vectors and 229 chunk-locator IDs.
Dry-run planning and local apply are now covered by script tests; local apply rebuilt 13,171 chunks and post-audit reported zero legacy/unversioned vectors.
Suggested test type: Regression
Suggested test location:
`tests/test_indexer_agent_chunk_ids.py`
Suggested assertions:
Collection upsert IDs are globally unique while local chunk locators remain stable.
Priority: P1
Reason:
Current tests lock in local deterministic IDs but not cross-paper uniqueness.

## Test gap: Duplicate DOI policy

Status: Partially covered
Production behavior:
New `save_paper_state` writes reuse an existing normalized DOI row and manual imports reject a different existing DOI; DOI index remains non-unique for compatibility.
Production files:
`scripts/init_db.py`, `src/db_utils.py`
Existing tests checked:
`tests/test_db_get_paper_by_id.py`, `tests/test_db_paper_write_ops.py`
Missing scenario:
Existing duplicate DOI rows in a live DB need read-only audit plus approved merge/backfill behavior.
Suggested test type: Contract
Suggested test location:
`tests/test_db_paper_write_ops.py`
Suggested assertions:
Either conflict/merge behavior occurs or explicit duplicate policy fields are set.
Priority: P1
Reason:
Duplicate canonical records break traceability and downstream joins.

## Test gap: Realistic/malformed/scanned/large PDF fixtures

Status: Partially covered
Production behavior:
Pipeline must handle real academic PDFs and malformed/scanned/large cases.
Production files:
`backend/routers/paper_notes.py`, `src/agents/ingest_agent.py`, `src/ingest/parser_backends.py`, `src/ingest/ocr_fallback.py`
Existing tests checked:
`tests/test_paper_notes_api.py`, `tests/test_ingest_parser_backend.py`, `tests/test_ocr_fallback.py`
Missing scenario:
Synthetic parser fixtures now cover born-digital multi-column-like academic layout, malformed/corrupted PDF, mocked scanned/OCR recovery, a generated image-only scanned PDF with real OCRmyPDF/Tesseract round trip when tools are installed, a 24-page large valid PDF through `IngestAgent.process_v2`, and an import-to-parser path through DB-resolved imported PDF storage. Remaining gap is full worker artifact production for scanned PDFs.
Suggested test type: Integration
Suggested test location:
`tests/fixtures/papers/` plus parser/import tests.
Suggested assertions:
Expected rejection or status; minimum page/text counts; OCR metadata; no stale DB/file drift. Large fixture now asserts all 24 pages, page sentinels, v2 source refs, and block count.
Priority: P1
Reason:
Current parser-level synthetic coverage is strong; full worker artifact production and non-English/huge scanned OCR remain weaker.

## Test gap: Semantic section extraction

Status: Partially covered
Production behavior:
Default parser detects obvious standalone academic headings and falls back to page sections while downstream reader prioritizes semantic section names.
Production files:
`src/ingest/parser_backends.py`, `src/agents/reader_agent.py`
Existing tests checked:
`tests/test_ingest_parser_backend.py`
Missing scenario:
Realistic external-paper fixture remains absent, but synthetic academic PDF coverage now exercises Abstract/Methods/Results headings in a two-column-like layout.
Suggested test type: Regression
Suggested test location:
`tests/test_ingest_parser_backend.py`
Suggested assertions:
Section names or section signal metadata include abstract/methods/results; reader priority count is nonzero.
Priority: P1
Reason:
Semantic extraction quality is central to reliable academic-paper processing.

## Test gap: Import rollback after DB write

Status: Covered for post-save failure
Production behavior:
Import commits `papers` row before final path/state operations.
Production files:
`backend/routers/paper_notes.py`, `src/db_utils.py`
Existing tests checked:
`tests/test_paper_notes_api.py`
Missing scenario:
Additional blob/filesystem storage failure variants around PDF/note writes.
Suggested test type: Regression
Suggested test location:
`tests/test_paper_notes_api.py`
Suggested assertions:
No orphan `papers` row, no stale `pdf_path`, consistent note/PDF cleanup.
Priority: P1
Reason:
Partial import corrupts paper storage/access state.

## Test gap: Parser/extraction retry after partial failure

Status: Likely gap
Production behavior:
Failed Deep Read can be re-enqueued after terminal status.
Production files:
`src/jobs/queue.py`, `src/jobs/worker.py`, `backend/services/job_runner.py`
Existing tests checked:
`tests/test_jobs_api_smoke.py`, `tests/test_worker_job_runner_chain.py`
Missing scenario:
Failed parse/index/read creates partial artifacts, then retry succeeds using same stored PDF and fresh run artifacts.
Suggested test type: Integration
Suggested test location:
`tests/test_job_runner_retry.py`
Suggested assertions:
First job failed; second job completed; artifacts are isolated by run ID; latest status/artifacts point to successful run.
Priority: P2
Reason:
Retry safety matters for real-world parsing failures.

## Test gap: Clean reindex failure safety

Status: Covered for replacement-before-prune and partial embedding skip
Production behavior:
Clean reindex upserts replacement vectors before pruning stale vectors and skips prune for partial embedding replacement.
Production files:
`src/agents/indexer_agent.py`, `backend/services/job_runner.py`
Existing tests checked:
`tests/test_indexer_agent_chunk_ids.py`
Missing scenario:
Legacy-vector migration/rebuild coverage for production/remote stores outside local `./storage/rag/`.
Suggested test type: Regression
Suggested test location:
`tests/test_indexer_agent_reindex.py`
Suggested assertions:
Before audit reports legacy IDs, rebuild runs from artifacts, after audit reports zero chunk-locator IDs and vectors carry `doc-scope-v1`.
The plan explicitly reports dropped stale/no-longer-backed vectors or preserves them by a chosen policy. Local script tests now cover apply refusal, preflight-before-backup, no-candidate refusal, and restore-from-backup after index failure.
Priority: P2
Reason:
Partial reindex can lose retrieval state.

## Test gap: Frontend/backend import response contract

Status: Covered for field presence
Production behavior:
Backend returns `doi`; frontend type now includes it.
Production files:
`src/schemas/paper_notes.py`, `frontend/src/app/lib/types.ts`, `frontend/src/app/lib/api.ts`
Existing tests checked:
`tests/test_paper_notes_api.py`, frontend contract coverage.
Missing scenario:
Deeper generated-schema/type compatibility beyond field presence.
Suggested test type: Contract
Suggested test location:
Frontend API contract tests or generated schema check.
Suggested assertions:
`paper_id`, `slug`, `title`, `note_path`, `pdf_url`, and `doi` are typed/handled; optional/null semantics remain compatible.
Priority: P2
Reason:
Contract drift hides data returned by backend.

## Test gap: Worker stale-running recovery

Status: Likely gap
Production behavior:
Manual ops endpoints reclaim stale jobs; worker does not auto-recover.
Production files:
`src/jobs/worker.py`, `src/jobs/queue.py`, `src/services/stale_jobs.py`
Existing tests checked:
Job queue/stale tests indirectly; no startup recovery found.
Missing scenario:
Worker restart with stale running job.
Suggested test type: Integration
Suggested test location:
`tests/test_worker_stale_recovery.py`
Suggested assertions:
Stale job is reclaimed/requeued or explicitly remains with ops alert.
Priority: P2
Reason:
Unattended worker crashes can block the pipeline.
