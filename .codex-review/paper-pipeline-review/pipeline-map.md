## Pipeline area: Manual PDF import / Paper Notes entry

Purpose:
Accept a user PDF, store the raw file, create a Paper Notes markdown note, and create/update the canonical `papers` row.
Main files:
- `frontend/src/app/pages/PaperNotesListPage.tsx`
- `frontend/src/app/lib/api.ts`
- `backend/routers/paper_notes.py`
- `src/db_utils.py`
- `src/schemas/paper_notes.py`
Entry points:
- `PaperNotesListPage.handleImportSelection` at `frontend/src/app/pages/PaperNotesListPage.tsx:812`
- `importPaperPdf` at `frontend/src/app/lib/api.ts:995`
- `POST /paper-notes/import-pdf` at `backend/routers/paper_notes.py:2255`
- `import_pdf_payload` at `backend/routers/paper_notes.py:933`
Callers:
- Paper Notes list UI.
- CLI import commands call the same `import_pdf_payload` path in tests.
Downstream dependencies:
- Paper detail view via `/papers/{slug}` after import.
- Deep Read enqueue from Paper Note detail / Workbench.
Database/storage dependencies:
- PDF bytes under `config.paths.pdf_storage_dir`, named `userpdf-<sha1>.pdf`.
- Markdown note under `Inbox/PaperPipe`.
- `papers` row through `save_paper_state`.
External dependencies:
- `pypdf` for import title/DOI metadata/text sniffing.
Background jobs/queues:
- None automatically. Import does not enqueue parsing.
Tests found:
- `tests/test_paper_notes_api.py`
- `tests/test_cli_import_pdf.py`
Initial risk level: Medium
Notes:
- Import validates non-empty payload and `%PDF-` header, but does not deeply validate parseability before persisting.
- Import is idempotent by content hash, but post-DB failures can leave stale DB rows.

## Pipeline area: Deep Read job API and queue

Purpose:
Create a background job/run for parsing, indexing, claim extraction, optional verification, and artifact writing.
Main files:
- `backend/main.py`
- `src/jobs/queue.py`
- `src/jobs/worker.py`
- `src/jobs/schemas.py`
- `src/services/event_log.py`
Entry points:
- `POST /jobs/deepread` at `backend/main.py:5809`
- `JobQueue.enqueue` at `src/jobs/queue.py:67`
- `Worker.start` / `process_job` at `src/jobs/worker.py:29` and `src/jobs/worker.py:45`
Callers:
- Frontend `enqueueDeepReadJob` at `frontend/src/app/lib/api.ts:1565`
- Paper Note detail and Analysis Workbench UI.
Downstream dependencies:
- `backend/services/job_runner.py::run_deepread_job`.
- `/jobs`, `/jobs/{job_id}`, `/jobs/{job_id}/events`, run timeline/artifact APIs.
Database/storage dependencies:
- `jobs`, `execution_runs`, `job_events`.
- job logs under `logs/jobs`.
External dependencies:
- Worker process must be running separately.
Background jobs/queues:
- SQLite-backed polling queue.
Tests found:
- `tests/test_jobs_api_smoke.py`
- `tests/test_job_runner_ingest_backend.py`
- `tests/test_worker_job_runner_chain.py`
Initial risk level: Medium
Notes:
- Enqueue/claim is transaction guarded.
- Stale running jobs require manual ops recovery rather than worker startup recovery.

## Pipeline area: PDF parsing / document artifact generation

Purpose:
Turn a local PDF into `DocumentArtifactV2` with metadata, page/block text, page coordinates, and tables.
Main files:
- `src/agents/ingest_agent.py`
- `src/ingest/parser_backends.py`
- `src/ingest/ocr_fallback.py`
- `src/ingest/cloud_table_fallback.py`
- `src/contracts/document_artifact_v2.py`
- `src/schemas/agent_artifacts.py`
Entry points:
- `IngestAgent.process_v2` at `src/agents/ingest_agent.py:301`
- `create_parser_backend` at `src/ingest/parser_backends.py:1129`
Callers:
- `run_deepread_job` at `backend/services/job_runner.py:1256`
Downstream dependencies:
- Indexer, Reader, citation grounding, figure caption sidecar, visual evidence ledger, claimset coverage, clinical extraction.
Database/storage dependencies:
- Writes `document_artifact.json` under the artifact run directory.
External dependencies:
- PyMuPDF (`fitz`), pdfplumber, optional Docling, optional `ocrmypdf`, optional OpenAI-compatible table fallback.
Background jobs/queues:
- Runs inside Deep Read worker.
Tests found:
- `tests/test_ingest_parser_backend.py`
- `tests/test_ingest_bbox_clamp.py`
- `tests/test_ingest_creation_date.py`
- `tests/test_ocr_fallback.py`
Initial risk level: High
Notes:
- Default backend emits page-level sections, not semantic Abstract/Methods/Results sections.
- Metadata is mostly PDF metadata-dependent.

## Pipeline area: Chunking, embeddings, and vector indexing

Purpose:
Chunk parsed text, create embeddings, write vectors to ChromaDB, and emit `index_artifact.json`.
Main files:
- `src/agents/indexer_agent.py`
- `src/services/identity.py`
- `src/schemas/agent_artifacts.py`
Entry points:
- `IndexerAgent.process` at `src/agents/indexer_agent.py:57`
Callers:
- `run_deepread_job` at `backend/services/job_runner.py:1441`
Downstream dependencies:
- Reader evidence grounding and search/RAG usage.
Database/storage dependencies:
- Chroma persistent collection `paperpipe_rag`.
- `index_artifact.json`.
External dependencies:
- Ollama embedding adapter, ChromaDB.
Background jobs/queues:
- Runs inside Deep Read worker.
Tests found:
- `tests/test_indexer_agent_chunk_ids.py`
- `tests/test_openai_provider_embeddings.py`
Initial risk level: High
Notes:
- Vector IDs are local chunk IDs like `p01_c01`, not globally scoped by paper/document.

## Pipeline area: Claim extraction, grounding, and derived sidecars

Purpose:
Extract scientific claims/evidence, ground evidence to chunks/pages/bboxes, and generate review/export sidecars.
Main files:
- `src/agents/reader_agent.py`
- `src/services/citation_grounding.py`
- `src/services/figure_caption_sidecar.py`
- `src/services/visual_evidence_ledger.py`
- `src/services/claimset_coverage_sidecar.py`
- `src/services/evidence_extraction_sidecar.py`
- `backend/services/job_runner.py`
Entry points:
- `ReaderAgent.analyze` at `src/agents/reader_agent.py:138`
- `resolve_claimset_grounding` at `src/services/citation_grounding.py:30`
Callers:
- `run_deepread_job` reader stage.
Downstream dependencies:
- Paper Notes structured state promotion, method comparison, paper synthesis, meeting packs, visual evidence, API artifact views.
Database/storage dependencies:
- `claimset.json`, `claimset.resolved.json`, `reader_eval.json`, `visual_evidence_ledger.json`, `evidence_extraction_bundle.json`, coverage artifacts.
External dependencies:
- Configured LLM provider for reader and optional clinical extraction.
Background jobs/queues:
- Runs inside Deep Read worker.
Tests found:
- `tests/test_citation_grounding.py`
- `tests/test_evidence_extraction_sidecar.py`
- `tests/test_job_runner_clinical_extraction.py`
Initial risk level: Medium
Notes:
- Evidence traceability exists but depends on chunk IDs and text matching.

## Pipeline area: Downstream paper views and artifact usage

Purpose:
Display paper rows, PDF, Paper Notes, job status, artifacts, structured state, related papers, and synthesis/comparison features.
Main files:
- `backend/main.py`
- `backend/routers/paper_notes.py`
- `src/services/deepread_state_projection.py`
- `src/skills/storage.py`
- `frontend/src/app/pages/PaperNoteDetailPage.tsx`
- `frontend/src/app/pages/AnalysisWorkbench.tsx`
- `frontend/src/app/lib/api.ts`
Entry points:
- `/papers`, `/papers/{paper_id}`, `/papers/{paper_id}/pdf`
- `/paper-notes`, `/paper-notes/{slug}`, `/paper-notes/resolve-by-paper-id`
- `/artifacts/{paper_id}/latest`, `/artifacts/{paper_id}/{run_id}`
Callers:
- Paper Notes, Workbench, Method Comparison, Paper Synthesis, Meeting Packs.
Downstream dependencies:
- Artifact run directory layout and structured state files under `.pp/<slug>/state.json`.
Database/storage dependencies:
- SQLite `papers`, `jobs`, `execution_runs`.
- Obsidian markdown and structured state JSON.
External dependencies:
- None required for read paths.
Background jobs/queues:
- Reads job/run state produced by worker.
Tests found:
- `tests/test_papers_api.py`
- `tests/test_paper_notes_api.py`
- `tests/test_paper_synthesis_*`
Initial risk level: Medium
Notes:
- Deep Read status lives in job/run/artifacts; `papers.status` does not clearly transition after parsing.
