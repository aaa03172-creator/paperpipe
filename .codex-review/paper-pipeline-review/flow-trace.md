## Flow: New manual PDF ingestion flow

Purpose:
Import a local user PDF into Paper Notes and the canonical paper row.
Entry point:
`POST /paper-notes/import-pdf` at `backend/routers/paper_notes.py:2255`.
Call path:
`PaperNotesListPage.handleImportSelection` (`frontend/src/app/pages/PaperNotesListPage.tsx:812`) -> `importPaperPdf` (`frontend/src/app/lib/api.ts:995`) -> `import_paper_pdf` (`backend/routers/paper_notes.py:2255`) -> `import_pdf_payload` (`backend/routers/paper_notes.py:933`) -> `save_paper_state` (`src/db_utils.py:408`).
Data path:
Upload bytes are size-limited at `backend/routers/paper_notes.py:233`, checked for `%PDF-` at `backend/routers/paper_notes.py:939`, hashed at `backend/routers/paper_notes.py:947`, written to `pdf_storage_dir` at `backend/routers/paper_notes.py:959`, and linked from a markdown note with `/papers/{paper_id}/pdf`.
Database writes:
`papers` row via `save_paper_state` at `backend/routers/paper_notes.py:995`.
Database reads:
`_paper_state_persisted` verifies row existence at `backend/routers/paper_notes.py:259`.
External services:
None.
Background jobs/queues:
None automatically.
Status transitions:
Creates/updates `papers.status = NEW` at `backend/routers/paper_notes.py:1002`.
Error handling:
Deletes newly-created note/PDF on exceptions at `backend/routers/paper_notes.py:1011`.
Retries/idempotency:
Content hash creates stable `userpdf-<sha1>` paper ID at `backend/routers/paper_notes.py:947`.
Tests found:
`tests/test_paper_notes_api.py`, `tests/test_cli_import_pdf.py`.
Missing or suspicious connections:
Import does not enqueue or run parsing.
Potential contract/schema mismatches:
Frontend import response type omits backend `doi`.
Conclusion: Probably working
Evidence:
Registered route and router include at `backend/routers/paper_notes.py:2255` and `backend/main.py:6088`; focused tests passed.

## Flow: Deep Read parsing and extraction flow

Purpose:
Process a stored PDF into parsed document, index, claimset, evidence sidecars, and structured state.
Entry point:
`POST /jobs/deepread` at `backend/main.py:5809`.
Call path:
`enqueueDeepReadJob` (`frontend/src/app/lib/api.ts:1565`) -> `enqueue_job` (`backend/main.py:5809`) -> `JobQueue.enqueue` (`src/jobs/queue.py:67`) -> `Worker.process_job` (`src/jobs/worker.py:45`) -> `run_deepread_job` (`backend/services/job_runner.py:989`) -> `IngestAgent.process_v2` (`src/agents/ingest_agent.py:301`) -> `IndexerAgent.process` (`src/agents/indexer_agent.py:57`) -> `ReaderAgent.analyze` (`src/agents/reader_agent.py:138`).
Data path:
PDF path is resolved from DB at `backend/services/job_runner.py:1105`, note frontmatter at `backend/services/job_runner.py:1110`, or library search at `backend/services/job_runner.py:1115`. Artifacts are written under `artifact_run_dir(paper_id, run_id)` at `backend/services/job_runner.py:1132`.
Database writes:
`jobs`, `execution_runs`, and `job_events` through queue/event log. No confirmed write back to `papers.status` after parsing.
Database reads:
`papers.pdf_path` in `_resolve_pdf_path_from_db` at `backend/services/job_runner.py:122`.
External services:
Embeddings through Ollama adapter; reader through configured LLM; optional cloud table fallback.
Background jobs/queues:
SQLite polling worker.
Status transitions:
`queued` -> `running` in `claim_next_job` at `src/jobs/queue.py:236`; terminal status written in worker at `src/jobs/worker.py:164` or `src/jobs/worker.py:181`.
Error handling:
Runner broad exception records failed run metadata at `backend/services/job_runner.py:2023`; worker marks failed at `src/jobs/worker.py:186`.
Retries/idempotency:
One open job per paper enforced at `src/jobs/queue.py:93`; terminal jobs can be re-enqueued. Clean reindex deletes old vectors before replacement.
Tests found:
`tests/test_job_runner_ingest_backend.py`, `tests/test_jobs_api_smoke.py`, `tests/test_job_runner_pdf_lookup.py`.
Missing or suspicious connections:
Deep Read completion does not clearly update `papers.status` from `NEW`.
Potential contract/schema mismatches:
Parser outputs page sections while reader priority logic expects semantic names.
Conclusion: Probably working, with P1/P2 risks
Evidence:
`backend/services/job_runner.py:1256`, `backend/services/job_runner.py:1280`, `backend/services/job_runner.py:1455`, `backend/services/job_runner.py:1630`.

## Flow: Storage flow for parsed and extracted data

Purpose:
Persist raw paper identity, run/job state, parsed document artifacts, indexed chunks, extracted claims, and promoted structured state.
Entry point:
Import and Deep Read job runner.
Call path:
Import writes `papers`; runner writes artifact files; promotion writes `.pp/<slug>/state.json`.
Data path:
Raw PDF remains in PDF storage. Parsed/extracted data is artifact-run scoped. Promoted user-facing state is stored with the note.
Database writes:
`papers`, `jobs`, `execution_runs`, `job_events`, `user_actions`.
Database reads:
Paper listing/detail, PDF serving, job status APIs.
External services:
ChromaDB for vectors.
Background jobs/queues:
Deep Read worker.
Status transitions:
Job/run statuses are explicit; paper row status boundary is ambiguous.
Error handling:
Partial artifacts can remain for failed runs; run/bootstrap metadata record failure where possible.
Retries/idempotency:
Artifact run IDs are unique. Vector clean reindex is not atomic.
Tests found:
Storage-related coverage in `tests/test_jobs_api_smoke.py`, `tests/test_indexer_agent_chunk_ids.py`, `tests/test_paper_notes_api.py`.
Missing or suspicious connections:
Duplicate DOI rows are possible. Vector IDs collide across papers.
Potential contract/schema mismatches:
Frontend status type narrower than backend status strings.
Conclusion: Partially working
Evidence:
`scripts/init_db.py:28`, `src/db_utils.py:396`, `src/agents/indexer_agent.py:82`, `src/services/deepread_state_projection.py:183`.

## Flow: Downstream usage flow

Purpose:
Expose parsed/extracted data to Workbench, Paper Notes, artifact APIs, synthesis, comparison, and meeting-pack surfaces.
Entry point:
`/papers`, `/paper-notes`, `/jobs`, `/artifacts`.
Call path:
Frontend API functions call backend read routes; backend reads DB rows, artifact files, and note structured state.
Data path:
`claimset.resolved.json` and `run_meta.json` are promoted into `StructuredPaperState`; downstream tools also read artifact files directly.
Database writes:
No new parsing writes on read paths; operator state writes are separate raw-memory/user-facing state.
Database reads:
Paper rows, jobs/runs, user actions.
External services:
None for read paths.
Background jobs/queues:
Reads worker-produced outputs.
Status transitions:
Failed jobs are surfaced through `/jobs` and SSE. Paper note ops summaries inspect artifacts.
Error handling:
Missing artifacts often degrade to unavailable/limited state.
Retries/idempotency:
Structured-state promotion replaces/refreshed state only when owned by Deep Read promotion.
Tests found:
`tests/test_papers_api.py`, `tests/test_paper_notes_api.py`, `tests/test_paper_synthesis_*`.
Missing or suspicious connections:
Search/Q&A vector consumers were not exhaustively verified; vector collisions can corrupt downstream retrieval.
Potential contract/schema mismatches:
Frontend import response missing `doi`; frontend paper status type is too narrow.
Conclusion: Needs verification
Evidence:
`src/services/deepread_state_projection.py:32`, `src/paper_syntheses/service.py:125`, `src/method_comparisons/service.py:64`.
