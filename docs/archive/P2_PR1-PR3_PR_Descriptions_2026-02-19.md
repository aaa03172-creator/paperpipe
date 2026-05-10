# P2 PR#1~PR#3 Submission Drafts (2026-02-19)

Status: Historical PR prep  
Date: 2026-02-19  
Owner: Repository maintainers  
Canonical parent: `docs/Pending_PR_Queue.md`

## PR#1 - Eval Harness + Goldset Skeleton

### Scope
- Added goldset skeleton and manifest/query structures.
- Added snapshot runner and snapshot diff scripts.
- Added regression tests for determinism/integrity/diff sanity.

### AC Checklist
- [x] AC1. Goldset structure (queries + pdfs + manifest) is fixed and versioned.
- [x] AC2. Pipeline snapshot outputs are stored per run directory.
- [x] AC3. Snapshot diff report outputs JSON + readable summary.

### How To Run Tests
```bash
pytest -q tests/test_eval_harness.py
```

### Example Output Artifacts
- `goldset/queries.jsonl`
- `goldset/manifest.json`
- `scripts/eval/run_eval.py`
- `scripts/eval/diff_snapshots.py`
- `snapshots/<run_id>/summary.json`

---

## PR#2 - DocumentArtifact v2 Contract + Stable IDs + BBox Rules

### Scope
- Added DocumentArtifact v2 contract and validation rules.
- Added ingest v2 output mapping with stable IDs.
- Added bridge/views and agent compatibility updates.
- Added regression tests for schema validation and ID stability.

### AC Checklist
- [x] AC1. Stable IDs are assigned to page/block/line/span units.
- [x] AC2. BBox contract is defined and validated.
- [x] AC3. Ingest v2 output is consumable by Reader/Indexer/Stats.

### How To Run Tests
```bash
pytest -q tests/test_document_artifact_v2.py tests/test_artifact_bridge.py tests/test_stats_agent.py
```

### Example Output Artifacts
- `src/contracts/document_artifact_v2.py`
- `src/contracts/artifact_views.py`
- `src/contracts/artifact_bridge.py`
- `docs/document_artifact_v2.md`

---

## PR#3 - OCR Fallback (OCRmyPDF + Tesseract)

### Scope
- Added OCR fallback module with detection + execution metadata.
- Integrated optional OCR fallback into ingest pipeline (flag-based).
- Added fail-safe behavior when OCR fails.
- Added regression tests for OCR success and failure-safe path.

### AC Checklist
- [x] AC1. Scanned PDFs can be OCR-layered before ingest.
- [x] AC2. OCR applied/version/language metadata is recorded.
- [x] AC3. OCR failure does not crash pipeline and logs reason.

### How To Run Tests
```bash
pytest -q tests/test_ocr_fallback.py
```

### Example Output Artifacts
- `src/ingest/ocr_fallback.py`
- `docs/ocr_fallback.md`
- OCR cache output: `storage/ocr_cache/<hash>.pdf` (runtime)

---

## Worker -> JobRunner Chain Regression Guard

### Scope
- Added smoke test ensuring `worker.py` calls real `job_runner.py` chain.
- Verifies ingest/index/read/verify artifacts are generated and job completes.

### How To Run Tests
```bash
pytest -q tests/test_worker_job_runner_chain.py tests/test_jobs_api_smoke.py
```

### Example Output Artifacts
- `storage/artifacts/<paper_id>/<run_id>/document_artifact.json`
- `storage/artifacts/<paper_id>/<run_id>/index_artifact.json`
- `storage/artifacts/<paper_id>/<run_id>/claimset.json`
- `storage/artifacts/<paper_id>/<run_id>/stats_report.json`
