# Operational Backfill Outputs (2026-02-23)

## Scope
- Stabilize `scripts/qa_report.py` direct execution (`python3 scripts/qa_report.py`).
- Add one-shot operational helper for output backfill:
  - missing Obsidian markdown export
  - missing claimset queueing (DeepRead jobs)

## Changes
- `scripts/qa_report.py`
  - Added repo-root path bootstrap for direct script execution.
  - Improved output: `Missing/Invalid ClaimSet` now prints actual claimset-missing IDs.
  - Clarified summary ID line as `Missing Summary IDs`.
- `scripts/backfill_operational_outputs.py` (new)
  - Default dry-run.
  - `--apply --export-missing`: run exporter with `overwrite=False`.
  - `--apply --enqueue-claimset --limit N`: enqueue DeepRead jobs only for claimset-missing papers.
  - enqueue safety: default requires local pdf exists (`pdf_ready=True`).
- `backend/services/job_runner.py`
  - PDF locate path now checks DB `papers.pdf_path` first (paper_id/alias/doi fallback) before filename heuristic.
  - Purpose: canonical `paper_id` (`zotero:*`, `doi:*`) migration 이후에도 local PDF 탐색 실패 방지.
- `tests/test_backfill_operational_outputs.py` (new)
  - Candidate detection regression.
  - Open-job skip behavior regression.
- `tests/test_job_runner_pdf_lookup.py` (new)
  - DB `pdf_path` 우선 탐색 회귀.
  - DOI alias lookup 회귀.

## Execution
1. Pre-check:
```bash
python3 scripts/qa_report.py
python3 scripts/backfill_operational_outputs.py
```

2. Applied markdown backfill:
```bash
python3 scripts/backfill_operational_outputs.py --apply --export-missing
```

3. Applied claimset queue seed (small batch):
```bash
python3 scripts/backfill_operational_outputs.py --apply --enqueue-claimset --limit 10
```

## Results (current)
- QA:
  - `Missing Markdown Files: 0` (from 52)
  - `Missing/Invalid ClaimSet (Operational): 36` (from 52 after three follow-up batches)
  - `FAILED Papers: 0`
- Jobs:
  - Initial queue seed(10) was processed immediately and failed with `PDF not found` (pre-fix behavior).
  - Backfill script policy updated:
    - default enqueue requires `pdf_path` exists locally (`pdf_ready=True`)
    - `--allow-missing-pdf` must be explicit to bypass this guard
  - After `job_runner` hotfix, claimset backfill jobs proceed with DB path lookup and backlog reduction is observed.
  - Current job snapshot:
    - `completed: 21`
    - `failed: 12` (legacy pre-fix batch)
    - `queued: 0` (batch processed)
  - Backfill execution progress:
    - first post-fix drain: queued `4` processed (`50 -> 46`)
    - second batch: enqueue `5`, process all (`46 -> 41`)
    - third batch: enqueue `5`, process all (`41 -> 36`)
  - Runtime note:
    - one PDF emitted non-fatal MuPDF warnings (`cmsOpenProfileFromMem failed`) but ingest completed and job finished as `completed`.

## Next Ops Step
- Batch enqueue (`--enqueue-claimset --limit 5~10`) + worker run in controlled windows.
- Re-run `scripts/qa_report.py` after each batch and track `Missing/Invalid ClaimSet` delta.
- Optional housekeeping: if desired, archive/filter pre-fix `PDF not found` failed jobs from dashboard view.
