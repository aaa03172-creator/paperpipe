## Storage behavior: Manual PDF import storage

Files:
- `backend/routers/paper_notes.py`
- `src/db_utils.py`
Write path:
Write PDF -> write note -> save `papers` row -> persist note path.
Read path:
Paper Notes index, `/papers/{paper_id}/pdf`, Deep Read PDF lookup.
Related models/tables:
`papers`, markdown note.
Expected behavior:
Create exactly one coherent paper, note, and PDF record per imported payload.
Observed behavior:
Content hash stabilizes paper ID; `save_paper_state` commits before later verification/note DOI updates; follow-up cleanup now deletes a newly-created DB row if post-save import work fails.
Idempotency:
Stable `userpdf-<sha1>` ID and note slug.
Transaction/consistency behavior:
File and DB writes are not one transaction. Exception cleanup removes note/PDF and now compensates for newly-created DB rows.
Delete/update behavior:
Compensating DB cleanup exists for rows created by the failed import attempt; pre-existing rows are preserved.
Retry behavior:
Re-import can reuse existing PDF/note if consistent.
Risks:
Residual file/DB drift risk remains around untested storage failures, but the confirmed post-save orphan-row path is covered.
Suggested fix:
Transactionalize DB write with final fallible work or add compensating delete/restore for newly-created import rows.
Suggested test:
Force `_persist_imported_note_path` or `_paper_state_persisted` failure after `save_paper_state`; assert no orphan `papers` row remains.
Evidence:
`backend/routers/paper_notes.py:995`, `backend/routers/paper_notes.py:1005`, `backend/routers/paper_notes.py:1011`, `src/db_utils.py:408`.

## Storage behavior: Paper identity and duplicate handling

Files:
- `scripts/init_db.py`
- `src/db_utils.py`
Write path:
`save_paper_state` insert/upsert.
Read path:
Paper APIs, Deep Read PDF lookup, downstream features.
Related models/tables:
`papers`.
Expected behavior:
Same DOI should not silently create multiple canonical papers unless explicitly allowed.
Observed behavior:
`paper_id` is primary key; DOI index is non-unique; new writes normalize DOI and reuse an existing row with the same normalized DOI when found.
Idempotency:
Idempotent only for the same `paper_id`.
Transaction/consistency behavior:
Single DB transaction for each `save_paper_state` call.
Delete/update behavior:
No duplicate DOI reconciliation in write path.
Retry behavior:
New writes/imports avoid creating a second row for the same normalized DOI; existing duplicates can still remain.
Risks:
Existing duplicate canonical records can fragment jobs, notes, artifacts, status, and downstream comparisons until audited/merged.
Suggested fix:
Run read-only duplicate DOI audit, then define approved normalized DOI uniqueness/backfill policy.
Suggested test:
Call `save_paper_state` twice with different paper IDs and same DOI; assert one canonical row. Seed existing duplicates and assert dry-run reporting.
Evidence:
`scripts/init_db.py:30`, `scripts/init_db.py:75`, `src/db_utils.py:396`.

## Storage behavior: Run artifact storage

Files:
- `backend/services/job_runner.py`
- `src/services/runtime_paths.py`
Write path:
`artifact_run_dir(paper_id, run_id)` receives run/bootstrap metadata and artifacts.
Read path:
Artifact APIs, structured state promotion, downstream synthesis/comparison.
Related models/tables:
`jobs.artifact_dir`, `execution_runs`, artifact files.
Expected behavior:
Each run writes isolated, traceable artifacts.
Observed behavior:
Run directory includes `run_meta.json`, `bootstrap_meta.json`, `document_artifact.json`, `index_artifact.json`, claimsets, sidecars, and handoff artifacts.
Idempotency:
Run IDs isolate retries.
Transaction/consistency behavior:
File writes are sequential; failures can leave partial artifacts with failure metadata.
Delete/update behavior:
No cleanup on failed runs; partial artifacts remain as evidence.
Retry behavior:
New run directory on retry.
Risks:
Failure-path handoff writing is not guarded and can fail while handling failure.
Suggested fix:
Wrap failure-path handoff artifact writes in best-effort guard.
Suggested test:
Mock `write_deepread_handoff_artifacts` to raise in exception path; assert runner returns failed result and worker records failure.
Evidence:
`backend/services/job_runner.py:1132`, `backend/services/job_runner.py:1280`, `backend/services/job_runner.py:1455`, `backend/services/job_runner.py:2023`, `backend/services/job_runner.py:2037`.

## Storage behavior: Vector indexing

Files:
- `src/agents/indexer_agent.py`
- `src/services/identity.py`
Write path:
Chunk text -> embedding -> Chroma `upsert`.
Read path:
Query/search and evidence grounding.
Related models/tables:
Chroma collection `paperpipe_rag`, `IndexArtifact`.
Expected behavior:
Vectors are unique per paper/chunk and reindex is recoverable.
Observed behavior:
New vector IDs are document-scoped while local chunk IDs are preserved as metadata. Clean reindex now upserts replacement vectors first, then prunes stale vectors only after a complete replacement.
Read-only local audit of `./storage/rag/` found 15,846 vectors without `vector_id_version`; 229 of those are actual chunk-locator IDs such as `p02_c06`, which can collide across papers.
Dry-run rebuild planning found 130 latest document-artifact candidates totaling 13,171 chunks and did not modify Chroma.
Guarded script `scripts/rebuild_vector_index.py` now defaults to dry-run and refuses apply without explicit confirmation.
Follow-up apply rebuilt local `./storage/rag/` from 130 validated candidates, indexing 13,171 chunks. Post-rebuild audit reported `total_vectors=13171`, `legacy_unscoped_count=0`, `unversioned_count=0`, `missing_doc_id_count=0`, and `vector_id_version_counts={"doc-scope-v1": 13171}`.
Idempotency:
Idempotent for same document shape and scoped across documents for new writes.
Transaction/consistency behavior:
No full vector-store transaction, but replacement-before-prune prevents deleting the last successful index when replacement is empty or partial.
Delete/update behavior:
`reset_doc_index` deletes by metadata `doc_id`.
Retry behavior:
Partial embedding replacement skips prune; old vectors remain.
Risks:
Local Chroma contents have been rebuilt successfully; production/remote Chroma contents outside `./storage/rag/` still need the same audit before assuming they are clean.
Suggested fix:
Keep the guarded rebuild flow and audit command as the repeatable migration path for any other Chroma store. Add restore documentation for backup rollback if apply fails after clearing the collection.
Suggested test:
Index two documents with page 1 chunks and assert Chroma receives distinct IDs; simulate partial embedding replacement and assert old vectors remain; run before/after Chroma audit around rebuild.
Evidence:
`src/agents/indexer_agent.py:25`, `src/agents/indexer_agent.py:46`, `src/agents/indexer_agent.py:50`, `src/agents/indexer_agent.py:82`, `src/agents/indexer_agent.py:124`.

## Storage behavior: Structured state promotion

Files:
- `src/services/deepread_state_projection.py`
- `src/skills/storage.py`
Write path:
Successful artifact bundle -> `StructuredPaperState` -> `.pp/<slug>/state.json` and frontmatter update.
Read path:
Paper Notes detail, related papers, synthesis/comparison.
Related models/tables:
Obsidian note files and structured-state JSON.
Expected behavior:
Promote only successful, traceable Deep Read output and preserve user-owned state.
Observed behavior:
Requires `run_meta.status == succeeded`, resolved claimset, and skips if existing state is owned elsewhere.
Idempotency:
Refreshes Deep Read-owned state and preserves reading assists.
Transaction/consistency behavior:
Structured state and note frontmatter are separate file writes.
Delete/update behavior:
No automatic cleanup of older states; run records preserve provenance.
Retry behavior:
New successful runs can refresh state.
Risks:
Promotion skipped if note path cannot resolve; downstream may see artifacts but no note state.
Suggested fix:
Surface skipped promotion reason prominently in job/UI.
Suggested test:
Successful run with no resolvable note path should still expose artifacts and a clear promotion-skipped status.
Evidence:
`src/services/deepread_state_projection.py:41`, `src/services/deepread_state_projection.py:45`, `src/services/deepread_state_projection.py:196`, `src/services/deepread_state_projection.py:220`.
