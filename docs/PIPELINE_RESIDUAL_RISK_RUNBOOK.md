# Pipeline Residual Risk Runbook

Status: Active
Date: 2026-05-14
Owner: Runtime/ops maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose

Use this runbook to verify the remaining production risks around retrieval index state, worker restart recovery, and hard-scanned PDFs. These checks are operator verification steps, not a replacement truth store.

## Production Chroma Verification

Risk: production Chroma collections can drift from the runtime DB or be created with the wrong model/metric/version.

Verification path:

- Confirm the active DB path and paper count before indexing.
- Run a deterministic local index command:
  - `python -m src.indexer --db ./storage/state.db index`
- Run a smoke search against a known biomedical term:
  - `python -m src.indexer --db ./storage/state.db search "biomarker" --k 5`
- Confirm collection naming follows `paper_pipe_bio__{model_slug}__v{N}` and the collection metric remains cosine.
- If model or metric changes, create a new versioned collection instead of mutating the old collection in place.

Pass signal:

- index command exits successfully
- search returns expected local papers or an explicitly empty result for an empty DB
- no unversioned production collection is used

Escalate when:

- the collection metric differs from cosine
- search succeeds against stale papers after a clean reindex request
- the runtime DB and Chroma collection disagree after re-running the index command

## Worker Restart Verification

Risk: a worker restart can leave `running` jobs stale, block the same `paper_id`, or tempt direct DB mutation.

Verification path:

- Check queue readiness:
  - `GET /health/ready`
  - browser-safe path: `GET /api/health/ready`
- Identify stale candidates:
  - `GET /ops/stale-jobs?stale_after_seconds=900&limit=50`
- Capture bounded evidence before mutation:
  - `POST /ops/jobs/{job_id}/stale-incident-snapshot`
- Reclaim only after confirming no progress:
  - `POST /ops/jobs/{job_id}/reclaim-stale`
- Re-run explicitly:
  - `POST /ops/jobs/{job_id}/requeue-reclaimed`
  - or `POST /jobs/deepread`

Pass signal:

- stale candidates are warnings first, not automatic proof of worker death
- incident snapshot exists before reclaim
- reclaimed jobs move to terminal `failed` with `STALE_RUNNING_RECLAIMED`
- replacement jobs get a new `job_id` and `run_id`

Escalate when:

- multiple unrelated jobs become stale together
- replacement jobs never leave `queued`
- queue health remains degraded after reclaim/requeue

## Hard-Scanned PDF Verification

Risk: a hard-scanned or image-only PDF can produce little text, empty claim extraction, or misleading downstream artifacts.

Verification path:

- Confirm local OCR tooling is installed when OCR fallback is enabled:
  - `ocrmypdf --version`
  - `tesseract --version`
- Check `config.yaml` / runtime config for:
  - `enable_ocr_fallback`
  - `ocr_lang`
  - `ocr_min_text_chars`
- Run the paper through Deep Read with a known hard-scanned fixture or operator-selected scanned PDF.
- Inspect the run artifacts:
  - `run_meta.json`
  - `bootstrap_meta.json`
  - `document_artifact.json`
- Confirm OCR/cache behavior matches `docs/ocr_fallback.md`.

Pass signal:

- original PDF is never overwritten
- OCR output, when used, is cached under the configured OCR cache
- parser failure codes or low-text evidence are visible in `run_meta.json` / `bootstrap_meta.json`
- downstream artifacts preserve warnings instead of pretending full text extraction succeeded

Escalate when:

- OCR fallback is enabled but local OCR tools are unavailable
- `document_artifact.json` contains no meaningful text and no parser/OCR warning is visible
- repeated hard-scanned PDFs fail without a bounded fixture or eval record

## Verification Anchors

- `docs/indexer.md`
- `docs/STALE_RUNNING_RECOVERY.md`
- `docs/ocr_fallback.md`
- `tests/test_pipeline_residual_hardening_contract.py`
- `tests/test_indexer_agent_chunk_ids.py`
- `tests/test_runtime_readiness_external_roots.py`
- `tests/test_worker_job_runner_chain.py`
