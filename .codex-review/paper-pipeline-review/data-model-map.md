## Data model: `papers` table

Files:
- `scripts/init_db.py`
- `src/db_utils.py`
- `src/schemas/papers.py`
- `frontend/src/app/lib/types.ts`
Purpose:
Canonical structured paper identity, metadata, lifecycle/status, access paths, and audit fields.
Fields:
`paper_id`, `doi`, `title`, `summary`, `year`, `venue`, `source`, `slot`, `status`, gate fields, `pdf_status`, `pdf_path`, `obsidian_path`, `feedback_json`, versions, timestamps.
Relations:
Referenced by jobs, notes, review queue, artifact paths, downstream features by `paper_id`.
Used by:
Import, paper listing/detail/PDF routes, Deep Read PDF lookup, downloader/watchers, downstream summaries.
Schema/type mismatches:
- Backend `PaperSummaryResponse.status` is `str | None`, while frontend `PaperSummary.status` is narrower.
Storage risks:
- DOI has a non-unique index for compatibility. New `save_paper_state` writes reuse an existing normalized DOI row, but existing duplicate rows can remain until audited.
- Import rollback now compensates for newly-created DB rows after post-save failure; residual storage-failure variants still need coverage.
Traceability/provenance support:
`pdf_path`, DOI, source, note path; no parser version/status fields on the row itself.
Versioning/reprocessing support:
Run/artifact metadata handles parser versioning; `papers` row does not track latest parser/extraction version.
Conclusion:
Mostly functional for identity/access, improved for new DOI writes/import rollback, still weak for existing duplicate remediation and parser lifecycle.
Evidence:
`scripts/init_db.py:28`, `scripts/init_db.py:75`, `src/db_utils.py:396`, `src/schemas/papers.py:20`.

## Data model: Jobs, runs, and events

Files:
- `src/db_utils.py`
- `src/jobs/schemas.py`
- `src/jobs/queue.py`
- `src/services/event_log.py`
- `backend/main.py`
Purpose:
Queue state, run provenance, event/audit timeline, and UI status.
Fields:
`jobs`: `job_id`, `run_id`, `paper_id`, persona fields, `run_verify`, `clean_reindex`, `status`, `progress`, `stage`, timestamps, artifact/log/error fields. `execution_runs`: run params and status. `job_events`: structured events.
Relations:
`job_events.job_id` references `jobs.job_id`; run IDs connect artifacts and event log.
Used by:
Worker, status APIs, SSE, Workbench.
Schema/type mismatches:
None confirmed in reviewed path.
Storage risks:
Stale `running` jobs can block queue until manual ops recovery.
Traceability/provenance support:
Strong: run params include parser backend; run metadata captures PDF SHA, config/profile snapshots, inference lanes.
Versioning/reprocessing support:
Run IDs provide immutable run separation; no automatic stale recovery.
Conclusion:
Probably working, with reliability risk.
Evidence:
`src/db_utils.py:67`, `src/db_utils.py:111`, `src/jobs/queue.py:140`, `backend/services/job_runner.py:1137`.

## Data model: `DocumentArtifact` / `DocumentArtifactV2`

Files:
- `src/schemas/agent_artifacts.py`
- `src/contracts/document_artifact_v2.py`
- `src/agents/ingest_agent.py`
- `src/ingest/parser_backends.py`
Purpose:
Parsed PDF text, metadata, page/block structure, and tables.
Fields:
V1: `doc_id`, source, metadata, sections, tables. V2: `document_id`, `meta`, `pages`, `tables`, `schema_version`. Tables now include additive `source_ref`, `extraction_method`, `confidence`, and `provenance_note`.
Relations:
Feeds indexing, reader, grounding, visual evidence, coverage, clinical extraction.
Used by:
Deep Read run artifacts and downstream sidecars.
Schema/type mismatches:
V1 `Section.name` is documented as standardized semantic section name. Default parser now emits obvious standalone semantic headings when detected, otherwise falls back to `page_N`.
Storage risks:
References/citations/footnotes are not modeled separately; figure extraction is sidecar-only and caption-only.
Traceability/provenance support:
V2 pages/block bboxes support page provenance; line/span bboxes are often unavailable. Table rows now preserve source page refs and method/confidence metadata, but not cell bboxes.
Versioning/reprocessing support:
Run artifacts include parser backend and run ID; artifact schema version exists.
Conclusion:
Good raw page traceability, partial semantic heading extraction, improved table provenance, weak structured references/figures.
Evidence:
`src/schemas/agent_artifacts.py:35`, `src/contracts/document_artifact_v2.py:66`, `src/ingest/parser_backends.py:228`.

## Data model: Chunks and vector index

Files:
- `src/agents/indexer_agent.py`
- `src/services/identity.py`
- `src/schemas/agent_artifacts.py`
Purpose:
Chunk document text and persist embeddings for retrieval/grounding.
Fields:
`chunk_id`, text, vector ID, section/page hints, ordinals, chunk ID version.
Relations:
Claim evidence spans reference chunk IDs; Chroma metadata carries `doc_id`.
Used by:
Reader grounding and search/RAG paths.
Schema/type mismatches:
`chunk_id` remains a local locator; new Chroma writes use document-scoped `vector_id`.
Storage risks:
Existing local Chroma contents are confirmed legacy/unversioned: 15,846 vectors lack `vector_id_version`, including 229 chunk-locator IDs. New writes avoid cross-paper ID collisions.
Traceability/provenance support:
Chunk page hints, section names, local `chunk_id`, and scoped `vector_id` support grounding for new writes.
Versioning/reprocessing support:
`chunk_id_version = det-v1`; `vector_id_version = doc-scope-v1`; clean reindex upserts first and prunes stale vectors only after complete replacement.
Conclusion:
Working for new multi-paper vector uniqueness; local legacy index contents need rebuild/migration.
Evidence:
`src/agents/indexer_agent.py:25`, `src/agents/indexer_agent.py:82`, `src/agents/indexer_agent.py:95`, `src/agents/indexer_agent.py:124`.

## Data model: ClaimSet and evidence extraction bundle

Files:
- `src/schemas/agent_artifacts.py`
- `src/services/citation_grounding.py`
- `src/schemas/evidence_extraction.py`
- `src/services/evidence_extraction_sidecar.py`
Purpose:
Structured claims, evidence spans, grounded locators, and extracted records for downstream review/export.
Fields:
Claims include `claim_id`, type, statement, evidence spans, limitations, confidence. Evidence spans include page, chunk, char offsets, raw text/quote, bbox/table/cell fields, grounding status.
Relations:
Grounded against `IndexArtifact` and `DocumentArtifactV2`; promoted into structured state.
Used by:
Paper Notes, synthesis, method comparison, meeting packs, evidence sidecars.
Schema/type mismatches:
No confirmed schema mismatch; evidence depends on chunk ID stability.
Storage risks:
Reader can return heuristic claims; coverage/readiness flags help but downstream users must respect them.
Traceability/provenance support:
Good when quote grounding succeeds; unresolved/ambiguous spans are marked.
Versioning/reprocessing support:
Run-scoped artifacts and structured-state run records preserve versions.
Conclusion:
Probably working, but depends on parser and vector correctness.
Evidence:
`src/schemas/agent_artifacts.py:101`, `src/services/citation_grounding.py:30`, `src/schemas/evidence_extraction.py:13`.

## Data model: Paper Notes structured state

Files:
- `src/schemas/skills.py`
- `src/services/deepread_state_projection.py`
- `src/skills/storage.py`
- `backend/routers/paper_notes.py`
Purpose:
User-facing note-linked structured state projected from Deep Read artifacts.
Fields:
Paper slug, runs, signals, claimset, entities, MeSH, outcomes, reading assists.
Relations:
Stored under Obsidian `.pp/<slug>/state.json` and linked from note frontmatter.
Used by:
Paper Notes detail, related papers, synthesis, comparison, meeting packs.
Schema/type mismatches:
None confirmed.
Storage risks:
Promotion only occurs if a note path is resolvable and artifact run succeeded.
Traceability/provenance support:
Run record includes artifact paths and source claimset paths.
Versioning/reprocessing support:
Deep Read promotion refreshes only if existing state is owned by Deep Read promotion.
Conclusion:
Probably working as downstream projection.
Evidence:
`src/services/deepread_state_projection.py:32`, `src/services/deepread_state_projection.py:183`, `src/skills/storage.py:368`.
