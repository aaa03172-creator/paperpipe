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
  - `Missing/Invalid ClaimSet (Operational): 0` (from 52 after full batch drain)
  - `FAILED Papers: 0`
- Jobs:
  - Initial queue seed(10) was processed immediately and failed with `PDF not found` (pre-fix behavior).
  - Backfill script policy updated:
    - default enqueue requires `pdf_path` exists locally (`pdf_ready=True`)
    - `--allow-missing-pdf` must be explicit to bypass this guard
  - After `job_runner` hotfix, claimset backfill jobs proceed with DB path lookup and backlog reduction is observed.
  - Current job snapshot:
    - `completed: 57`
    - `failed: 0` (legacy failures archived)
    - `queued: 0` (batch processed)
  - Backfill execution progress:
    - first post-fix drain: queued `4` processed (`50 -> 46`)
    - second batch: enqueue `5`, process all (`46 -> 41`)
    - third batch: enqueue `5`, process all (`41 -> 36`)
    - fourth/fifth drain: enqueue `10 + 10 + 6`, process all (`36 -> 0`)
  - Runtime note:
    - one PDF emitted non-fatal MuPDF warnings (`cmsOpenProfileFromMem failed`) but ingest completed and job finished as `completed`.
  - Legacy failed job hygiene:
    - archived `12` rows into `job_failures_archive` with backup snapshot
    - reasons:
      - `pdf_not_found_recovered`: 10
      - `test_fixture_failed_legacy`: 2

## Operational Policy Update
- `scripts/qa_report.py` now excludes fixture records (`local--`, `integration_test_*`, `/tests/` paths) from default operational counters.
- Current operational snapshot (default mode):
  - `Total Active Papers (APPROVED/INDEXED): 52`
  - `Missing Summary: 0`
  - `Bad Content (No Summary): 0`

## Next Ops Step
- Keep `scripts/backfill_operational_outputs.py` as recurring recovery path for new deltas.
- Keep `scripts/archive_legacy_failed_jobs.py` for one-shot cleanup when recovered failures accumulate.
