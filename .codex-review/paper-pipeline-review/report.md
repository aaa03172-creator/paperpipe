# Paper Processing Pipeline Deep Review Report

## Remediation status after follow-up fixes

Implemented and verified:
- New Chroma vector writes are document-scoped; local chunk locators are preserved as metadata.
- Read-only Chroma vector audit now distinguishes unversioned legacy vectors from actual chunk-locator IDs.
- Chroma rebuild dry-run planning now collects latest artifact candidates without touching Chroma or creating backups.
- Guarded rebuild script added at `scripts/rebuild_vector_index.py`; it defaults to dry-run and refuses `--apply` unless `--confirm REBUILD_LOCAL_CHROMA` is provided.
- Local Chroma rebuild was applied after explicit proceed: 130 validated candidates, 13,171 indexed chunks, zero failures, and post-rebuild audit clean for legacy/unversioned IDs.
- Clean reindex now writes replacement vectors first and prunes stale vectors only after complete replacement; partial embedding replacement skips prune.
- New `save_paper_state` writes reuse an existing normalized DOI row; manual PDF import rejects a different existing DOI; existing duplicate DOI rows can now be reported read-only.
- Manual import rollback now removes a newly-created DB row after post-save failure.
- Default Fitz/pdfplumber parsing now detects obvious standalone academic headings such as Abstract/Methods/Results and falls back to page sections when none are detected.
- Import-to-Deep-Read wiring has a regression test proving the imported PDF path can be resolved and enqueued.
- Import-to-parser continuity has a regression test proving upload bytes are persisted, DB `pdf_path` resolves to the stored PDF, and `IngestAgent.process_v2` preserves sentinel text and v2 source refs from that same file.
- Frontend import response type now includes backend `doi`, and contract coverage includes `PaperNoteImportResponse`.

Still open:
- Existing local Chroma data initially needed rebuild/migration: read-only audit found 15,846 unversioned vectors and 229 chunk-locator vector IDs in `./storage/rag/`.
- Dry-run rebuild plan found 130 latest document-artifact candidates totaling 13,171 chunks. The approved apply rebuilt those 13,171 backed-by-artifact vectors and dropped stale/duplicate/no-longer-backed vectors from the local index.
- The generated plan now includes all 130 candidate entries plus a 25-item sample, with repo-relative paths in `.codex-review/paper-pipeline-review/chroma-rebuild-dry-run-plan.json`.
- Parser realism is still partial for multi-column papers, citations/references, tables/figures/captions, non-English/huge scanned PDFs, malformed PDFs, and large real fixtures.
- Stale running job recovery, cancellation inside long phases, cloud fallback payload enforcement, and lifecycle status semantics remain open findings.

## 1. Executive summary

Overall risk level: Medium-High after targeted fixes

- Does the paper processing pipeline appear to work end-to-end? More strongly yes for the manual import -> Deep Read enqueue path, when the worker is running and a user explicitly queues Deep Read after import. It is still not fully automatic from import to parsing.
- Where does a paper enter the system? Manual PDF import enters through `POST /paper-notes/import-pdf`; Zotero/download paths also populate `papers` and `pdf_path`.
- How is it parsed? Deep Read resolves a local PDF, selects `fitz_pdfplumber` or optional Docling, produces `DocumentArtifactV2`, indexes chunks, runs reader extraction, grounds claims, and writes artifacts.
- What is extracted? Metadata, page/block text, tables, chunks/embeddings, claimsets/evidence spans, figure-caption sidecars, visual/evidence bundles, optional clinical extraction, optional stats verification.
- Where is extracted data stored? SQLite stores canonical paper/job/run state; run directories store parsed/extracted artifacts; Chroma stores vectors; Obsidian `.pp/<slug>/state.json` stores promoted structured note state.
- Which downstream features use it? Paper Notes, Workbench, artifact APIs, paper synthesis, method comparison, meeting packs, visual evidence, and review/gate artifacts.
- Which parts are broken, partially wired, or need verification? New vector IDs, clean reindex, local Chroma rebuild, new DOI writes, import rollback, obvious section-heading parsing, and import-response typing have been hardened. Parser realism/provenance, stale job recovery, production/remote vector stores, and cancellation still need fixes or verification.
- Top 5 remaining risks: weak real-world PDF fixture coverage; parser provenance limits for tables/figures/references; stale running job recovery; lifecycle status semantics; production/remote Chroma stores not audited by this local rebuild.

## 2. Scope reviewed

Reviewed:
Manual import, Paper Notes wiring, paper APIs, Deep Read queue/worker, parser backends, OCR/cloud table fallback, document/index/claim schemas, artifact storage, structured state promotion, selected downstream consumers, focused tests.

Partially reviewed:
Zotero/download ingestion, frontend Workbench details, paper synthesis/comparison/meeting-pack downstream usage.

Skipped:
General whole-repository review, unrelated artifact families, production deployment/worker supervision.

Needs verification:
Live worker behavior, production/remote Chroma contents beyond local `./storage/rag/`, production duplicate DOI rows beyond local `storage/state.db`, real-world Docling quality, external storage/vector DB behavior.

## 3. End-to-end flow summary

| flow | entry point | main files | status | risk level | main concern |
|---|---|---|---|---|---|
| Manual PDF import | `/paper-notes/import-pdf` | `paper_notes.py`, `api.ts` | Working for tested rollback/dedupe paths | Medium | Existing duplicate DOI rows need policy |
| Deep Read enqueue | `/jobs/deepread` | `main.py`, `queue.py`, `worker.py` | Working | Medium | Worker must run; stale jobs manual |
| PDF parse | `IngestAgent.process_v2` | `ingest_agent.py`, `parser_backends.py` | Partially working | Medium-High | Obvious headings split; weak metadata/provenance remains |
| Index/chunk | `IndexerAgent.process` | `indexer_agent.py` | Working locally after rebuild | Medium | Production/remote Chroma stores still need the same audit/rebuild |
| Claim extraction | `ReaderAgent.analyze` | `reader_agent.py`, `citation_grounding.py` | Probably working | Medium | Depends on parser and chunk correctness |
| Downstream state | `promote_deepread_structured_state_for_note` | `deepread_state_projection.py` | Probably working | Medium | Best-effort note promotion |

## 4. Data model and storage summary

Paper entities: `papers`, `jobs`, `execution_runs`, `job_events`, `DocumentArtifactV2`, `IndexArtifact`, `ClaimSet`, evidence extraction bundle, structured paper state.

Schema/type mismatches:
- Frontend import response now includes backend `doi`.
- Frontend paper status type is narrower than backend status strings.
- `Section.name` contract implies semantic names; default parser now detects obvious standalone headings but still falls back to page sections and lacks robust real-paper segmentation.

Storage risks:
- Existing local Chroma vector rebuild/migration: completed locally; initial audit found 15,846 unversioned vectors and 229 chunk-locator vector IDs, apply rebuilt 13,171 scoped vectors.
- Remaining table/figure/reference provenance gaps.

Idempotency/retry risks:
- Stale running jobs block retries until manual reclaim.

Provenance/versioning gaps:
- Good run-level SHA/config/parser provenance.
- Weak semantic section/reference/table-caption provenance.
- No clear paper-row parser version/latest extraction state.

## 5. Parsing and extraction summary

Parser/extractor components:
- Import metadata sniffing: title/DOI only, lightweight.
- Fitz/pdfplumber: metadata, page text/blocks, tables.
- Docling: optional text/table backend with fallbacks.
- OCR: optional `ocrmypdf` fallback.
- Cloud table fallback: optional external table extraction.
- Reader: LLM claim extraction, grounding, sidecars.
- Figure captions: caption-only, no image extraction.

Known limitations:
Default parser now identifies obvious standalone Abstract/Methods/Results-style headings. References/citations are not structured; default table captions are synthetic; figures are not visually parsed. Synthetic parser fixtures now cover born-digital academic layout, malformed/corrupted PDFs, mocked scanned/OCR recovery, generated image-only scanned PDF real OCR round trip, a 24-page large PDF, and DB-resolved import-to-parser continuity. Non-English/huge scanned OCR remains weak.

## 6. Wiring and integration summary

Connected parts:
Import route, frontend import call, Deep Read enqueue, queue/worker, parser selection, artifact writes, job status APIs.

Partially connected parts:
Import to parsing is user-triggered, not automatic. Structured state promotion is best-effort. Paper row lifecycle status may not reflect parsed/completed state.

Disconnected/broken parts:
Existing local vector index was rebuilt from latest artifacts and now contains only `doc-scope-v1` vectors. Any production/remote index still needs audit before trusting old indexed content.

Frontend/backend mismatches:
Import `doi` type is fixed; status type mismatch remains.

Job/queue/worker mismatches:
Stale running recovery exists only through ops endpoints, not worker startup.

Downstream usage gaps:
Search/RAG correctness for new writes is protected by scoped vector IDs; existing local index contents were rebuilt successfully. Note state can be absent when artifacts exist.

## 7. Failure case summary

| failure case | expected behavior | observed behavior | risk | suggested fix/test |
|---|---|---|---|---|
| malformed PDF | reject or explicit unparseable state | `%PDF-` header can pass import | Medium | lightweight PDF open test |
| scanned PDF | OCR or clear low-text state | OCR optional; generated English image-only real OCR fixture covered | Medium | full worker scanned fixture |
| duplicate DOI | merge/conflict | new writes/imports guarded; existing duplicates possible | Medium | dry-run existing rows, then approved merge/backfill |
| vector failure | preserve previous index | replacement upserts before prune; partial replacement skips prune; local rebuild path is guarded and audited | Medium | restore-from-backup failure-path test |
| worker crash | auto recover or alert | manual reclaim only | Medium | stale recovery test |
| cancel during phase | stop before writes | cooperative between phases | Medium | cancellation artifact-write test |

## 8. Test gap summary

| missing test | behavior | priority | type | assertions |
|---|---|---|---|---|
| Import-to-Deep-Read | full feature continuity | Covered for enqueue/path resolution and import-to-parser continuity | Integration | still add full worker artifact production E2E |
| Vector collision | multi-paper indexing | Covered for new writes | Regression | still add legacy-vector migration/rebuild coverage |
| Duplicate DOI | canonical identity | Covered for new writes/imports | Contract | still add existing duplicate merge/backfill coverage |
| Real fixtures | realistic papers | Partially covered | Integration | synthetic multi-column-like/malformed/scanned OCR/large/import-parser covered; still add full worker artifact fixture |
| Semantic sections | parser quality | Covered for obvious headings | Regression | still add external-paper fixture when license-safe |
| Import rollback | partial failure | Covered for post-save failure | Regression | keep expanding around storage failures |

## 9. Detailed findings

See `.codex-review/paper-pipeline-review/findings.md`.

Highest priority findings:
1. Production/remote Chroma copies, if any, have not been audited or rebuilt.
2. Metadata extraction depends on weak PDF metadata.
3. Table/figure/reference provenance remains partial.
4. Stale running jobs require manual recovery.
5. Paper lifecycle status semantics remain unclear.

## 10. Commands and validation

Commands run:
- `git status --short`: showed pre-existing unrelated dirty tree.
- `pytest -q tests/test_ingest_parser_backend.py tests/test_job_runner_ingest_backend.py tests/test_job_runner_pdf_lookup.py tests/test_indexer_agent_chunk_ids.py tests/test_paper_notes_api.py tests/test_jobs_api_smoke.py`
- `pytest -q tests/test_frontend_api_contracts.py tests/test_db_utils_download_attempts.py tests/test_paper_notes_api.py tests/test_indexer_agent_chunk_ids.py tests/test_ingest_parser_backend.py tests/test_worker_job_runner_chain.py`
- `pytest -q tests/test_indexer_agent_chunk_ids.py tests/test_worker_job_runner_chain.py tests/test_frontend_api_contracts.py tests/test_db_utils_download_attempts.py tests/test_paper_notes_api.py tests/test_ingest_parser_backend.py`
- `cd frontend && npm run build`
- `python3 - <<'PY' ... find_duplicate_doi_paper_rows() ... PY`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 - <<'PY' ... IndexerAgent().audit_vector_index() ... PY`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 - <<'PY' ... build_vector_rebuild_dry_run_plan() ... PY`
- `pytest -q tests/test_vector_index_rebuild_plan.py tests/test_rebuild_vector_index_script.py tests/test_indexer_agent_chunk_ids.py`
- `python3 scripts/rebuild_vector_index.py --json --output .codex-review/paper-pipeline-review/chroma-rebuild-dry-run-plan.json`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 scripts/rebuild_vector_index.py --apply --confirm REBUILD_LOCAL_CHROMA --json --output .codex-review/paper-pipeline-review/chroma-rebuild-apply-result.json`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 - <<'PY' ... IndexerAgent().audit_vector_index(sample_limit=5) ... PY`
- `pytest -q tests/test_vector_index_rebuild_plan.py tests/test_rebuild_vector_index_script.py tests/test_indexer_agent_chunk_ids.py tests/test_worker_job_runner_chain.py`
- `git diff --check -- src/agents/indexer_agent.py src/services/vector_index_rebuild.py scripts/rebuild_vector_index.py backend/services/job_runner.py src/db_utils.py backend/routers/paper_notes.py src/ingest/parser_backends.py frontend/src/app/lib/types.ts tests/test_vector_index_rebuild_plan.py tests/test_rebuild_vector_index_script.py tests/test_indexer_agent_chunk_ids.py tests/test_worker_job_runner_chain.py tests/test_frontend_api_contracts.py tests/test_db_utils_download_attempts.py tests/test_paper_notes_api.py tests/test_ingest_parser_backend.py .codex-review/paper-pipeline-review`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 - <<'PY' ... json.loads(...) for rebuild artifacts ... PY`
- `pytest -q tests/test_rebuild_vector_index_script.py tests/test_vector_index_rebuild_plan.py tests/test_indexer_agent_chunk_ids.py tests/test_worker_job_runner_chain.py`
- `git diff --check -- scripts/rebuild_vector_index.py tests/test_rebuild_vector_index_script.py .codex-review/paper-pipeline-review`
- `pytest -q tests/test_ingest_parser_backend.py`
- `pytest -q tests/test_ingest_parser_backend.py tests/test_rebuild_vector_index_script.py tests/test_vector_index_rebuild_plan.py tests/test_indexer_agent_chunk_ids.py tests/test_worker_job_runner_chain.py`

Results:
- 105 passed, 6 warnings.
- Follow-up focused suite: 103 passed, 6 warnings.
- Latest focused suite after vector-audit work: 106 passed, 6 warnings.
- Frontend build passed.
- Read-only local duplicate DOI audit reported `duplicate_group_count=0` for `storage/state.db`.
- Read-only local Chroma audit for `./storage/rag/` reported `total_vectors=15846`, `unversioned_count=15846`, `legacy_unscoped_count=229`, `missing_doc_id_count=0`, and `metadata_vector_id_mismatch_count=0`.
- Chroma rebuild dry-run plan written to `.codex-review/paper-pipeline-review/chroma-rebuild-dry-run-plan.json`; it reported `candidate_count=130`, `total_candidate_chunks=13171`, and `will_modify_chroma=False`.
- Rebuild script safety tests passed: 13 passed, 5 warnings.
- Script dry-run output includes `candidate_entries=130`; no backup directory was created and Chroma was not modified.
- Local Chroma apply result written to `.codex-review/paper-pipeline-review/chroma-rebuild-apply-result.json`; it reported `indexed_documents=130`, `indexed_chunks=13171`, `failure_count=0`, and backup directory `storage/backups/rag_before_rebuild_20260510T142940Z`.
- Post-rebuild audit reported `total_vectors=13171`, `legacy_unscoped_count=0`, `unversioned_count=0`, `missing_doc_id_count=0`, `metadata_vector_id_mismatch_count=0`, and `vector_id_version_counts={"doc-scope-v1": 13171}`.
- Latest focused vector/job suite: 32 passed, 5 warnings.
- `git diff --check` passed for touched code, tests, scripts, and review artifacts.
- Rebuild dry-run/apply JSON artifacts parsed successfully.
- Rebuild apply failure now restores `vector_root` from backup and exits non-zero; regression suite passed: 33 passed, 5 warnings.
- Follow-up direct Chroma audit remained clean after restore-path tests: `total_vectors=13171`, `legacy_unscoped_count=0`, `unversioned_count=0`, `missing_doc_id_count=0`, and `vector_id_version_counts={"doc-scope-v1": 13171}`.
- Added a 24-page large synthetic paper parser fixture that verifies all pages, page sentinels, v2 source refs, and block preservation.
- Parser/rebuild focused suite passed: 62 passed, 6 warnings.
- Added import-to-parser continuity coverage that imports a generated PDF, verifies persisted upload bytes and DB `pdf_path`, then parses the resolved file through `IngestAgent.process_v2`.
- Import/parser/rebuild focused suite passed: 65 passed, 6 warnings.
- Added a generated image-only scanned PDF fixture that runs real OCRmyPDF/Tesseract when installed, then verifies recovered text through `IngestAgent.process_v2`.
- OCR/import/parser/rebuild focused suite passed: 68 passed, 6 warnings.

Failures:
- Direct route listing via system `python3` failed because that interpreter lacked `fastapi`.
- `python - <<'PY' ...` failed because `python` is not installed on PATH; reran with `python3`.
- Chroma audit with default Homebrew `python3` failed because that interpreter lacked `chromadb`; reran with the same Python 3.13 environment used by `pytest`.
- During preflight hardening, an early test path exposed a real safety bug: `IndexerAgent()` ignored the script's `--vector-root` and touched the default local Chroma path. The code was corrected so apply uses `IndexerAgent(persist_path=...)`, preflight validation now runs before backup/delete, and the local Chroma index was rebuilt successfully from artifacts afterward.

Commands not run and why:
- Full test suite: broader than requested and likely slow/noisy for this review.
- Browser E2E: no visual or route behavior changed; touched frontend surface is a response type contract.

Sample fixtures inspected:
- `frontend/public/sample.pdf`: 1498 bytes.
- `Library/1411.2441.pdf`: 3,641,803 bytes, present but not treated as an intentional test fixture.
- `tmp/dubois2024_actual.pdf`: 15 bytes, not a meaningful valid fixture.

## 11. Remaining blind spots

- Production worker supervision and whether stale recovery is automated outside this repo.
- Existing local Chroma contents were audited and rebuilt; production/remote Chroma copies outside `./storage/rag/` remain unknown.
- Existing duplicate DOI state in `storage/state.db` was checked read-only and had zero duplicate groups; other production/remote DB copies remain unknown.
- Real-world Docling behavior on hard academic PDFs.
- External parser/cloud table fallback behavior with real credentials/config.
- End-to-end browser behavior for Workbench/Paper Notes under live worker.
- External callers outside repo.

## 12. Recommended next actions

1. Run the same audit/rebuild process for any production/remote Chroma store.
2. Improve metadata/table/figure/reference provenance or explicitly mark low-confidence extraction.
3. Harden stale job recovery and cancellation checks inside long phases.
4. Add full worker artifact-production E2E for imported and scanned PDFs.
5. Clarify remaining paper status lifecycle/type boundary.
