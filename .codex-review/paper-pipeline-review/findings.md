## Remediation update

Applied after initial review:
- Finding 1 is fixed for new indexing writes: `make_vector_id()` scopes Chroma IDs by document while preserving local `chunk_id` metadata (`src/agents/indexer_agent.py:22`, `src/agents/indexer_agent.py:125`, `src/agents/indexer_agent.py:135`).
- Follow-up read-only vector audit is available at `src/agents/indexer_agent.py:90`. Local audit of `./storage/rag/` initially found 15,846 total vectors, 15,846 unversioned vectors, and 229 chunk-locator vector IDs matching `pNN_cNN`/`sNN_cNN`.
- Guarded apply rebuild completed for local `./storage/rag/`: 130 candidates, 13,171 indexed chunks, `failure_count=0`, and post-rebuild audit with `legacy_unscoped_count=0`, `unversioned_count=0`, and `vector_id_version_counts={"doc-scope-v1": 13171}`. Production/remote Chroma copies remain unverified.
- Finding 2 is partially fixed: the default Fitz/pdfplumber parser now splits obvious standalone academic section headings (`src/ingest/parser_backends.py:233`, `src/ingest/parser_backends.py:263`). This does not fully solve multi-column, references, captions, or malformed real-paper sectioning.
- Finding 3 is partially fixed for new writes/imports: `save_paper_state()` reuses an existing normalized DOI row (`src/db_utils.py:373`) and manual imports reject a different existing DOI with 409 (`backend/routers/paper_notes.py:1001`). Existing duplicate DOI rows still need dry-run/backfill review; `find_duplicate_doi_paper_rows()` now reports them read-only (`src/db_utils.py:467`).
- Finding 4 is fixed for newly-created import rows: import cleanup now deletes the just-created DB row after post-save failure (`backend/routers/paper_notes.py:993`, `backend/routers/paper_notes.py:1057`).
- Finding 7 is fixed for clean reindex replacement safety: Deep Read now upserts replacement vectors first and prunes stale vectors only after a complete replacement (`backend/services/job_runner.py:1492`, `backend/services/job_runner.py:1496`, `src/agents/indexer_agent.py:65`). Partial embedding replacement skips pruning.
- Finding 12 is fixed: frontend `PaperNoteImportResponse` now includes `doi?: string | null` and the contract test covers the import response (`frontend/src/app/lib/types.ts:139`, `tests/test_frontend_api_contracts.py:34`).

## Finding 1: Chroma vector IDs collide across papers

Severity: P1
Confidence: High
Status: Confirmed; fixed for new writes and rebuilt for local `./storage/rag/`; production/remote Chroma contents need verification
Category: Storage
File/line:
`src/agents/indexer_agent.py:25`, `src/agents/indexer_agent.py:82`, `src/agents/indexer_agent.py:95`, `src/agents/indexer_agent.py:124`
Related files/call sites:
`src/services/identity.py:77`, `backend/services/job_runner.py:1452`
Issue:
All papers are written into the same Chroma collection, but vector IDs are local chunk locators such as `p01_c01` and are not scoped by document/paper ID.
Evidence:
`IndexerAgent` defaults to collection `paperpipe_rag` at `src/agents/indexer_agent.py:25`, builds chunk IDs from page/chunk ordinals at `src/agents/indexer_agent.py:82`, appends those IDs to the Chroma ID list at `src/agents/indexer_agent.py:95`, and calls `collection.upsert(ids=ids, ...)` at `src/agents/indexer_agent.py:124`.
Why it matters:
A second paper with the same page/chunk ordinal can overwrite or alias the first paper’s vector. Retrieval, grounding, and downstream search/Q&A can return the wrong paper evidence.
Suggested fix:
Use a globally-scoped vector ID, e.g. stable document/paper prefix plus local chunk ID, while preserving local `chunk_id` as evidence locator metadata.
Suggested test:
Index two documents that both produce `p01_c01`; assert Chroma upsert IDs are distinct and metadata still contains the local chunk locator.

## Finding 2: Parser output does not preserve semantic paper sections

Severity: P1
Confidence: High
Status: Confirmed; partially remediated for obvious standalone headings
Category: Parsing
File/line:
`src/ingest/parser_backends.py:228`, `src/schemas/agent_artifacts.py:35`, `src/agents/reader_agent.py:512`
Related files/call sites:
`src/agents/ingest_agent.py:181`, `backend/services/job_runner.py:1256`
Issue:
The default parser emits one section per page (`page_N`) while the schema describes standardized semantic section names and downstream reader logic looks for semantic priority sections.
Evidence:
Default backend creates `Section(name=f"page_{page_num + 1}")` at `src/ingest/parser_backends.py:228`. `Section.name` is documented as standardized names like abstract/methods/results at `src/schemas/agent_artifacts.py:35`. The reader later checks priority section names in `src/agents/reader_agent.py:512`.
Why it matters:
Abstract/methods/results-focused extraction degrades to page-level context. Real academic papers with multi-column layouts and section-specific claims are less reliably processed.
Suggested fix:
Add section-heading segmentation or explicitly mark artifacts as page-only and make reader priority selection inspect headings inside page text.
Suggested test:
Use a realistic paper fixture with Abstract/Methods/Results headings; assert semantic sections or reader priority context exists.

## Finding 3: Duplicate DOI records are allowed when paper IDs differ

Severity: P1
Confidence: High
Status: Confirmed; partially remediated for new writes/imports, existing duplicates need review
Category: Data model
File/line:
`scripts/init_db.py:30`, `scripts/init_db.py:75`, `src/db_utils.py:396`
Related files/call sites:
`backend/routers/paper_notes.py:995`, `src/db_utils.py:398`
Issue:
`papers.paper_id` is the primary key and DOI has a non-unique index. `save_paper_state` upserts on `paper_id` when present, so the same DOI under different paper IDs can create multiple canonical records.
Evidence:
Schema defines `paper_id TEXT PRIMARY KEY` at `scripts/init_db.py:30` and `idx_papers_doi` as a normal index at `scripts/init_db.py:75`. `save_paper_state` selects `paper_id` as conflict target at `src/db_utils.py:396`.
Why it matters:
Jobs, notes, artifacts, status, and downstream features can fragment across duplicate rows for the same paper, breaking traceability and idempotency.
Suggested fix:
Define and enforce normalized DOI duplicate policy, likely unique where non-null, with migration/backfill for existing duplicates.
Suggested test:
Save two different paper IDs with the same DOI and assert merge/conflict behavior.

## Finding 4: Import rollback can leave a stale DB paper row

Severity: P1
Confidence: High
Status: Confirmed; fixed for newly-created import rows
Category: Storage
File/line:
`backend/routers/paper_notes.py:995`, `backend/routers/paper_notes.py:1005`, `backend/routers/paper_notes.py:1011`, `src/db_utils.py:408`
Related files/call sites:
`backend/routers/paper_notes.py:933`
Issue:
`import_pdf_payload` commits the paper row, then performs additional fallible work. Its exception handler deletes only newly created note/PDF files, not the committed `papers` row.
Evidence:
`save_paper_state` is called at `backend/routers/paper_notes.py:995` and commits at `src/db_utils.py:408`. Later code checks persistence and updates note DOI/path at `backend/routers/paper_notes.py:1005`. Cleanup only unlinks note/PDF at `backend/routers/paper_notes.py:1011`.
Why it matters:
A failed import can leave a `NEW` paper row with `pdf_path` pointing to a deleted file, causing disconnected paper entries and failed downstream Deep Read.
Suggested fix:
Move the DB write after all fallible note/path work or add compensating DB cleanup for rows created by this import.
Suggested test:
Inject a failure after `save_paper_state`; assert no orphan row and no stale `pdf_path`.

## Finding 5: Metadata extraction relies on PDF metadata and weak fallback

Severity: P1
Confidence: High
Status: Confirmed
Category: Extraction
File/line:
`src/ingest/parser_backends.py:213`, `src/ingest/parser_backends.py:623`
Related files/call sites:
`src/agents/ingest_agent.py:181`, `backend/services/job_runner.py:1256`
Issue:
Title/authors/year/journal extraction mainly uses embedded PDF metadata. There is no bounded first-page title/author repair in the default path.
Evidence:
Default backend uses `doc.metadata` directly for title/authors/year/journal at `src/ingest/parser_backends.py:213`. Docling path also builds metadata around parser-provided metadata at `src/ingest/parser_backends.py:623`.
Why it matters:
Real academic PDFs often have missing or poor metadata. Downstream display, notes, IDs, and prompts can inherit file-stem titles or unsplit/empty authors.
Suggested fix:
Add metadata quality flags and bounded first-page/Docling text fallback for title/authors.
Suggested test:
Fixture with blank/bad PDF metadata but clear first-page title/authors; assert repaired metadata and quality signal.

## Finding 6: Table provenance and captions are partial

Severity: P2
Confidence: High
Status: Confirmed
Category: Extraction
File/line:
`src/ingest/parser_backends.py:284`, `src/ingest/parser_backends.py:1064`
Related files/call sites:
`src/services/visual_evidence_ledger.py:95`, `src/agents/reader_agent.py:146`
Issue:
Default tables receive synthetic captions (`Table found on page N`), and Docling markdown-table fallback assigns all fallback tables to page 1.
Evidence:
Default caption is synthetic at `src/ingest/parser_backends.py:284`; Docling markdown fallback page assignment is reported at `src/ingest/parser_backends.py:1064`.
Why it matters:
Table-derived evidence can cite unreliable captions/pages, harming traceability and review confidence.
Suggested fix:
Carry true captions/provenance when available; otherwise mark caption/page provenance as unknown/low-confidence rather than precise.
Suggested test:
PDF with table caption on page >1 and markdown fallback path; assert correct page or explicit unknown provenance.

## Finding 7: Clean reindex is not atomic

Severity: P2
Confidence: High
Status: Confirmed; fixed for replacement-before-prune flow
Category: Retry/idempotency
File/line:
`src/agents/indexer_agent.py:46`, `src/agents/indexer_agent.py:50`, `backend/services/job_runner.py:1442`, `src/agents/indexer_agent.py:123`
Related files/call sites:
`backend/services/job_runner.py:1452`
Issue:
Clean reindex deletes existing vectors before the replacement index is successfully built/upserted.
Evidence:
`reset_doc_index` fetches and deletes existing vector IDs at `src/agents/indexer_agent.py:46` and `src/agents/indexer_agent.py:50`. Runner calls reset before `indexer_agent.process` at `backend/services/job_runner.py:1442`; upsert happens later at `src/agents/indexer_agent.py:123`.
Why it matters:
Embedding or Chroma failure after reset leaves the last successful searchable index removed.
Suggested fix:
Build replacement vectors with a new version/run marker, then swap/delete old vectors after successful upsert.
Suggested test:
Simulate upsert failure after reset; assert old vectors remain or index invalidation is explicit.

## Finding 8: Stale running jobs require manual recovery

Severity: P2
Confidence: High
Status: Confirmed
Category: Reliability
File/line:
`src/jobs/worker.py:31`, `src/jobs/queue.py:213`, `src/jobs/queue.py:217`, `backend/main.py:5541`
Related files/call sites:
`src/services/stale_jobs.py`
Issue:
Worker startup claims queued jobs but does not automatically reclaim stale running jobs. `claim_next_job` counts all running rows against concurrency.
Evidence:
Worker polls `claim_next_job` at `src/jobs/worker.py:31`. `claim_next_job` counts running jobs at `src/jobs/queue.py:213` and returns none if limit reached at `src/jobs/queue.py:217`. Reclaim exists only via ops endpoint at `backend/main.py:5541`.
Why it matters:
Worker crash/restart can leave a paper job stuck running, block re-enqueue, and block queue capacity until manual intervention.
Suggested fix:
Add startup/periodic stale reconciliation or explicit alert/runbook.
Suggested test:
Seed stale running job, start recovery/worker path, assert it is reclaimed or requeued.

## Finding 9: Cancellation is only checked between major phases

Severity: P2
Confidence: High
Status: Confirmed
Category: Reliability
File/line:
`backend/services/job_runner.py:1256`, `backend/services/job_runner.py:1452`, `backend/services/job_runner.py:1578`
Related files/call sites:
`src/jobs/worker.py:86`
Issue:
Cancellation checks occur before phases, but not inside/after long ingest/index/read calls and before related artifact writes.
Evidence:
Long calls occur at `backend/services/job_runner.py:1256`, `backend/services/job_runner.py:1452`, and inside timeout-wrapped reader at `backend/services/job_runner.py:1578`.
Why it matters:
Cancel/delete during long processing can continue expensive work and write artifacts before cancellation is observed.
Suggested fix:
Check cancellation immediately after long calls and before artifact writes; pass cancellation hooks into agents where practical.
Suggested test:
Cancel during mocked long index/read; assert no post-cancel artifact writes.

## Finding 10: Cloud table fallback can send page text externally when enabled

Severity: P2
Confidence: Medium
Status: Confirmed
Category: Reliability
File/line:
`src/ingest/cloud_table_fallback.py:110`, `src/ingest/cloud_table_fallback.py:205`, `backend/services/job_runner.py:445`
Related files/call sites:
`src/agents/ingest_agent.py:335`
Issue:
The cloud table extractor sends selected page text to an OpenAI-compatible client. The runner attaches a privacy preflight callback, but direct use of the extractor can run without that callback.
Evidence:
Preflight is optional at `src/ingest/cloud_table_fallback.py:110`; external call occurs at `src/ingest/cloud_table_fallback.py:205`. Runner callback is built at `backend/services/job_runner.py:445`.
Why it matters:
Inference payload classification should be enforced consistently for paper text, especially full page excerpts.
Suggested fix:
Require explicit payload classification/preflight metadata before pass3 use, or make callback mandatory when cloud fallback is enabled.
Suggested test:
Enable cloud fallback without callback/API key and assert run metadata records payload class and blocked/unavailable status.

## Finding 11: Paper lifecycle row may not reflect completed parsing

Severity: P2
Confidence: Medium
Status: Needs verification
Category: Wiring
File/line:
`backend/routers/paper_notes.py:1002`, `src/jobs/worker.py:164`, `src/jobs/queue.py:317`
Related files/call sites:
`backend/services/job_runner.py`
Issue:
Manual import sets `papers.status = NEW`, while Deep Read completion updates job/run status and artifacts. No confirmed `papers.status` update occurs after successful parsing.
Evidence:
Import passes `status="NEW"` at `backend/routers/paper_notes.py:1002`; worker marks completed at `src/jobs/worker.py:164`; queue updates execution run status at `src/jobs/queue.py:317`. No `update_paper_status` call was found in `backend/services/job_runner.py` or `src/jobs/*`.
Why it matters:
If `papers.status` is intended as lifecycle status, parsed/imported papers can remain `NEW`, confusing downstream listings and UI.
Suggested fix:
Clarify boundary: either update `papers.status`/parse status on completion or expose parse status as separate latest-job field.
Suggested test:
Run Deep Read for imported paper; assert paper detail exposes correct parsing state.

## Finding 12: Frontend import response type omits backend `doi`

Severity: P2
Confidence: High
Status: Confirmed; fixed
Category: Contract mismatch
File/line:
`src/schemas/paper_notes.py:414`, `frontend/src/app/lib/types.ts:133`
Related files/call sites:
`frontend/src/app/lib/api.ts:995`, `tests/test_paper_notes_api.py:745`
Issue:
Backend `PaperNoteImportResponse` includes `doi`, but the frontend TypeScript type omits it.
Evidence:
Backend schema includes `doi` at `src/schemas/paper_notes.py:414`; frontend type starts at `frontend/src/app/lib/types.ts:133` and omits `doi`; backend tests assert `payload["doi"]` at `tests/test_paper_notes_api.py:745`.
Why it matters:
Contract drift can hide returned data and break future UI usage.
Suggested fix:
Add `doi?: string | null` to the frontend type or generate frontend types from backend schemas.
Suggested test:
Frontend/backend contract test for import response fields.

## Finding 13: Realistic PDF fixture coverage is insufficient

Severity: P2
Confidence: High
Status: Confirmed
Category: Test gap
File/line:
`tests/test_paper_notes_api.py:664`, `tests/test_paper_notes_api.py:740`, `tests/test_ocr_fallback.py:23`
Related files/call sites:
`src/agents/ingest_agent.py`, `src/ingest/parser_backends.py`
Issue:
Import/parser tests use a tiny sample PDF or minimal `%PDF-1.4` bytes; OCR tests synthesize/mock rather than proving real scanned paper behavior.
Evidence:
Import test uses `frontend/public/sample.pdf` at `tests/test_paper_notes_api.py:664`; minimal bytes are used at `tests/test_paper_notes_api.py:740`; OCR test builds a blank PDF at `tests/test_ocr_fallback.py:23`.
Why it matters:
The feature claims real-world paper handling, but tests do not cover realistic, malformed, large, or scanned academic PDFs end-to-end.
Suggested fix:
Add fixture suite: one real article, one malformed/truncated PDF, one scanned/image-only PDF, one large valid PDF.
Suggested test:
Run import/parser/Deep Read smoke against fixtures with expected success/failure metadata.
