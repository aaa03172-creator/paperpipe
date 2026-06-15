# Paper Pipeline Fragment / Unused Work Review

Date: 2026-05-15

Scope:
- Paper ingestion, parsing, indexing, job recovery, extraction provenance, and downstream artifact usage.
- This is not a whole-repository dead-code audit.
- Production/source code was not modified for this review artifact.

## Summary

Conclusion:
No clearly confirmed "implemented but completely unused" production code was found in the recently reviewed paper-pipeline hardening work. The main pattern is different: several pieces are intentionally manual, opt-in, or stored for traceability but not yet surfaced strongly downstream.

Recommended treatment:
1. Keep manual/ops-only tools as explicit maintenance tools.
2. Do not delete cloud fallback or vector rebuild code; both have runtime or operational purpose.
3. Add follow-up wiring only where product/runtime value is clear: table provenance display/quality use, ops visibility for batch stale reclaim, and HTTP/frontend import-to-worker E2E coverage.

## Fragment: Vector rebuild and audit tooling

Status: Manual/ops-only, not dead code

Files:
- `scripts/rebuild_vector_index.py`
- `src/services/vector_index_rebuild.py`
- `src/agents/indexer_agent.py`
- `tests/test_rebuild_vector_index_script.py`
- `tests/test_vector_index_rebuild_plan.py`
- `tests/test_indexer_agent_chunk_ids.py`

What exists:
- `scripts/rebuild_vector_index.py` plans and optionally applies a guarded local Chroma rebuild. It refuses apply unless `--confirm REBUILD_LOCAL_CHROMA` is supplied.
- `src/services/vector_index_rebuild.py` discovers artifact candidates and validates candidate document artifacts.
- `IndexerAgent.audit_vector_index()` provides a read-only audit for legacy/unversioned/mismatched vector IDs.

Evidence:
- `scripts/rebuild_vector_index.py:141` builds the CLI entry point.
- `scripts/rebuild_vector_index.py:151` validates apply confirmation.
- `scripts/rebuild_vector_index.py:160` only applies when `--apply` is present.
- `scripts/rebuild_vector_index.py:103` calls `agent.audit_vector_index()` after rebuild.
- `src/services/vector_index_rebuild.py:86` defines candidate collection.
- `src/agents/indexer_agent.py:96` defines the vector audit helper.

Runtime/downstream wiring:
- The rebuild tool is not wired to FastAPI, scheduler, worker, or a frontend ops surface.
- The audit helper is used by the rebuild script and tests, not by normal Deep Read execution.

Assessment:
This looks intentional and safe as a one-off maintenance path. It should not be treated as stale code just because the main runtime does not call it.

Recommended action:
- Keep as manual tooling.
- Optionally add an ops command/documented runbook if rebuild/audit is expected during production support.
- Do not wire automatic rebuilds without a separate safety review.

## Fragment: Table provenance fields

Status: Connected to chart-pack source consumers after follow-up

Files:
- `src/schemas/agent_artifacts.py`
- `src/contracts/document_artifact_v2.py`
- `src/ingest/parser_backends.py`
- `src/ingest/cloud_table_fallback.py`
- `src/schemas/chart_pack.py`
- `src/chart_packs/source_loader.py`
- `src/chart_packs/service.py`
- `frontend/src/app/lib/types.ts`
- `frontend/src/app/pages/ChartPackPage.tsx`
- `tests/test_chart_pack_source_loader.py`
- `tests/test_chart_pack_service.py`

What exists:
- Table artifacts now carry optional provenance fields: `source_ref`, `extraction_method`, `confidence`, and `provenance_note`.
- Parser paths populate them for pdfplumber, Docling structured tables, Docling markdown fallback, and cloud fallback.

Evidence:
- `src/schemas/agent_artifacts.py:48` adds `TableData.source_ref`.
- `src/schemas/agent_artifacts.py:49` adds `TableData.extraction_method`.
- `src/schemas/agent_artifacts.py:50` adds `TableData.confidence`.
- `src/schemas/agent_artifacts.py:51` adds `TableData.provenance_note`.
- `src/contracts/document_artifact_v2.py:64` adds `TableV2.source_ref`.
- `src/contracts/document_artifact_v2.py:65` adds `TableV2.extraction_method`.
- `src/contracts/document_artifact_v2.py:66` adds `TableV2.confidence`.
- `src/contracts/document_artifact_v2.py:67` adds `TableV2.provenance_note`.
- `src/ingest/parser_backends.py:396` populates pdfplumber table `source_ref`.
- `src/ingest/parser_backends.py:397` marks `pdfplumber.extract_tables`.
- `src/ingest/parser_backends.py:889` populates Docling table `source_ref`.
- `src/ingest/parser_backends.py:890` marks `docling.structured_table`.
- `src/ingest/parser_backends.py:1205` populates markdown fallback `source_ref`.
- `src/ingest/cloud_table_fallback.py:131` populates cloud fallback `source_ref`.
- `src/ingest/cloud_table_fallback.py:132` marks cloud extraction method.

Runtime/downstream wiring:
- Chart pack loading selects a table by `table_id`, loads rows, and now enriches the chart `source_ref` with table provenance.
- Low-confidence table extraction now adds a chart warning so chart definitions, pack warnings, markdown, and spec JSON preserve the quality signal.
- Frontend chart-pack types now accept the enriched provenance fields returned by the backend.
- The chart frontend still displays source kind, paper id, run id, table id, and source label only; direct UI display of extraction method/confidence/provenance note remains a later UX task.

Evidence:
- `src/chart_packs/source_loader.py:220` reads tables from the saved document artifact.
- `src/chart_packs/source_loader.py:221` selects by `table_id`.
- `src/chart_packs/source_loader.py:226` enriches the chart source ref from the selected table.
- `src/chart_packs/source_loader.py:227` builds table provenance warnings.
- `src/chart_packs/source_loader.py:286` returns `_RawSnapshot` with the enriched source ref.
- `src/chart_packs/source_loader.py:290` defines `_enrich_document_table_source_ref`.
- `src/chart_packs/source_loader.py:313` defines `_table_provenance_warnings`.
- `src/chart_packs/service.py:85` persists `snapshot.source_ref` into the chart definition.
- `src/chart_packs/service.py:113` persists `snapshot.source_ref` into pack source items.
- `src/schemas/chart_pack.py:81` adds `source_page`.
- `src/schemas/chart_pack.py:82` adds `table_source_ref`.
- `src/schemas/chart_pack.py:83` adds `extraction_method`.
- `src/schemas/chart_pack.py:84` adds `extraction_confidence`.
- `src/schemas/chart_pack.py:85` adds `provenance_note`.
- `frontend/src/app/lib/types.ts:677` adds matching frontend fields.
- `tests/test_chart_pack_source_loader.py` includes `test_document_table_snapshot_preserves_table_provenance`.
- `tests/test_chart_pack_service.py` includes `test_generate_chart_pack_persists_document_table_provenance_in_chart_sources`.
- `frontend/src/app/pages/ChartPackPage.tsx:158` formats chart source refs from chart source metadata.
- `frontend/src/app/pages/ChartPackPage.tsx:1171` displays source kind.
- `frontend/src/app/pages/ChartPackPage.tsx:1172` displays table id when present.

Assessment:
Not dead code. The fields now improve artifact traceability and are carried into chart-pack source references, spec payloads, and warnings. Direct UI display remains intentionally deferred because it is a UX surface change.

Recommended action:
- Keep the new backend/source contract coverage.
- Consider a separate UX-sized follow-up to display extraction method/confidence/provenance note in the chart source panel.

## Fragment: Cloud table fallback

Status: Opt-in connected path, not dead code

Files:
- `src/ingest/cloud_table_fallback.py`
- `src/agents/ingest_agent.py`
- `backend/services/job_runner.py`
- `src/config.py`
- `config.example.yaml`
- `src/services/cli_workflows.py`
- `src/skills/runner.py`
- `tests/test_cloud_table_fallback.py`
- `tests/test_job_runner_ingest_backend.py`
- `tests/test_ingest_parser_backend.py`

What exists:
- A cloud/LLM table fallback path exists for papers with no tables after local extraction.
- The path is gated by explicit config and a page budget.
- The runner adds privacy preflight metadata before the external fallback can run.

Evidence:
- `src/config.py:304` defaults `enable_cloud_table_fallback` to `False`.
- `config.example.yaml:82` also defaults `enable_cloud_table_fallback` to `false`.
- `src/agents/ingest_agent.py:271` only enters pass3 when local tables are absent and cloud fallback is enabled.
- `backend/services/job_runner.py:476` resolves the setting from config.
- `backend/services/job_runner.py:492` builds the cloud fallback privacy preflight callback.
- `backend/services/job_runner.py:1307` wires that callback into the ingest agent when the fallback is enabled.
- `src/services/cli_workflows.py:195` passes the setting into CLI ingest workflows.
- `src/skills/runner.py:197` passes the setting into skill ingest fallback.

Runtime/downstream wiring:
- Connected in normal runner, CLI workflow, and skill runner.
- Disabled by default, by policy.
- Not surfaced as a default user flow.

Assessment:
This is an intentionally dormant capability, not unused code. The local-first default matches project policy. It should remain opt-in unless a product/runtime decision changes inference policy.

Recommended action:
- Keep disabled by default.
- If enabled in any environment, add an operational check that confirms privacy preflight mode and API-key configuration before batch use.

## Fragment: Worker stale-running batch reclaim

Status: Connected to worker, partially surfaced in ops

Files:
- `src/services/stale_jobs.py`
- `src/jobs/worker.py`
- `backend/main.py`
- `tests/test_worker_heartbeat.py`
- `tests/test_stale_jobs_api.py`

What exists:
- Single-job stale reclaim and requeue are exposed through ops API.
- Batch reclaim helper exists and is now called by the worker before claiming queued work.

Evidence:
- `src/services/stale_jobs.py:981` defines `reclaim_stale_running_jobs`.
- `src/jobs/worker.py:80` defines `Worker.maybe_reclaim_stale_running_jobs`.
- `src/jobs/worker.py:87` calls the batch helper.
- `src/jobs/worker.py:102` runs a forced reclaim check on worker startup.
- `src/jobs/worker.py:105` runs periodic reclaim checks during polling.
- `backend/main.py:5526` exposes stale job diagnostics.
- `backend/main.py:5545` exposes single-job stale reclaim.
- `backend/main.py:5565` exposes requeue for reclaimed jobs.
- `tests/test_worker_heartbeat.py:265` verifies worker auto-reclaim before claiming queued work.

Runtime/downstream wiring:
- Worker path is connected.
- Ops API exposes diagnostics and single-job actions, but not batch reclaim as an explicit endpoint.

Assessment:
Not dead code. The batch helper is runtime-connected through the worker. The only gap is operational ergonomics if an operator wants a one-click/API batch reclaim without starting a worker.

Recommended action:
- Keep current worker wiring.
- Consider a guarded ops-only batch endpoint only if operations need manual intervention. Do not add it unless there is a concrete operator workflow.

## Fragment: Imported/scanned PDF worker E2E test

Status: Useful regression test, but not full HTTP/frontend E2E

Files:
- `tests/test_worker_job_runner_chain.py`
- `backend/routers/paper_notes.py`
- `src/jobs/worker.py`

What exists:
- A regression test covers import payload handling, scanned PDF OCR fallback, queue claim, worker processing, document artifact, index artifact, resolved claimset, handoff quality gate, paper status update, and Obsidian structured state promotion.

Evidence:
- `tests/test_worker_job_runner_chain.py:838` defines the imported scanned PDF worker artifact test.
- `tests/test_worker_job_runner_chain.py:872` calls `paper_notes_router.import_pdf_payload(...)`.
- `tests/test_worker_job_runner_chain.py:982` runs `worker.process_job(claimed)`.
- `tests/test_worker_job_runner_chain.py:993` reads `document_artifact.json`.
- `tests/test_worker_job_runner_chain.py:994` reads `index_artifact.json`.
- `tests/test_worker_job_runner_chain.py:995` reads `claimset.resolved.json`.
- `tests/test_worker_job_runner_chain.py:1023` checks the DB paper row.
- `tests/test_worker_job_runner_chain.py:1028` checks promoted structured state.

Runtime/downstream wiring:
- This is a test-only artifact, by design.
- It directly calls the import payload helper instead of exercising HTTP multipart upload or frontend behavior.

Assessment:
Not production dead code. It is a valuable integration regression. The remaining gap is route/client coverage, not unused implementation.

Recommended action:
- Keep the test.
- Add a separate contract/E2E test later if the upload route or frontend import flow changes.

## Possible cleanup / no-action list

No action recommended:
- Do not remove vector rebuild tooling. It is manual recovery tooling and was used for local Chroma rebuild validation.
- Do not remove cloud table fallback. It is intentionally opt-in and policy-gated.
- Do not remove table provenance fields. They are additive artifact traceability fields and useful for future chart/source trust UX.
- Do not add automatic vector rebuilds or enable cloud fallback by default without a separate privacy/reliability review.

Recommended next implementation:
1. Consider UI display of extraction method/confidence/provenance note in the chart source panel.
2. Add an ops runbook for vector rebuild/audit if this becomes a recurring production support task.
3. Add a guarded batch stale-reclaim ops endpoint only if operators need manual batch intervention.

Residual blind spots:
- No full static dead-code analyzer was run.
- External production deployment wiring for worker process supervision was not verified.
- Frontend upload route coverage was not re-run in this review.
- Production/remote Chroma instances remain outside this local review.
