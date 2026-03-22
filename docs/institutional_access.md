# Institutional Access Workflow (KNU libproxy)

Status: Active  
Date: 2026-03-09  
Owner: Downloader/export maintainers  
Canonical runbook: `docs/institutional_access.md`  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

PaperPipe keeps OA auto-download as-is.
When OA is unavailable, PaperPipe can route users to legal institutional access and continue intake semi-automatically.

## What is implemented (Feature A)
- Generate KNU libproxy links:
  - Prefix: `https://libproxy.knu.ac.kr/_Lib_Proxy_Url/`
  - DOI priority: `prefix + https://doi.org/{doi}`
  - Fallback: `prefix + publisher_url`
- For papers without local PDF but with resolvable proxy URL during export:
  - `pdf_status` is set to `manual_required`
  - `feedback_json.links.institutional_proxy_url` is stored
- Exported markdown includes:
  - `Download (Institutional)` block
  - institutional link + instruction text
- Bulk open script:
  - `python3 scripts/open_download_links.py --limit 20 --status manual_required`
  - prints all links and opens each with macOS `open`

## What is implemented (Feature B baseline)
- Downloads watcher matching flow:
  - watches `paths.downloads_watch_dir` (default `~/Downloads`)
  - moves matched PDFs to `paths.pdf_storage_dir` (default `storage/pdfs`)
  - updates `papers.pdf_status='downloaded'` and `papers.pdf_path`
- Matching strategy:
  - DOI-first exact match (filename DOI -> PDF content/metadata DOI -> papers.doi)
  - title similarity fallback (safe threshold)
  - ambiguous/unmatched files go to `storage/pdfs/_unmatched`
  - ambiguous/unmatched creates `review_queue` with `NEEDS_PDF_MATCH`
- Run command:
  - `python3 -m src.cli watch-downloads`

## Legal/Safety
- No paywall bypass.
- No credential scraping.
- No school ID/PW storage in code or files.
- Browser login remains user-controlled.

## Operational Notes
- DB path is unified to `storage/state.db`.
- Export now persists `papers.obsidian_path` after markdown write.

## QA / Operations (implemented)
- `scripts/qa_report.py` reports:
  - `manual_required`
  - `downloaded_missing_path`
  - `unmatched` (`storage/pdfs/_unmatched` PDF file count)
  - `unmatched_review_open` (`review_queue` open `NEEDS_PDF_MATCH`)
- Generate downloader ops dashboard:
  - `python3 scripts/downloader_ops_dashboard.py --hours 24`
  - output: `storage/reports/downloader_ops_dashboard.md`
- Retry telemetry is exposed in `download_attempts`:
  - `retry_no`
  - `will_retry`

## Optional Follow-ups (implemented)
- Provider HTTP policy:
  - provider-specific timeout/header defaults in `src/downloader/router.py`
  - override support via `DownloadRouter(..., provider_timeouts=..., provider_headers=...)`
- Candidate cache controls:
  - `candidate_cache_ttl_seconds` (default 600s)
  - `candidate_cache_max_entries` (default 1024)

## CI (opt-in integration)
- Workflow: `.github/workflows/phase3-integration-optin.yml`
- Runs `scripts/test_phase3_integration.py` only when opted in:
  - manual dispatch with `run_phase3_integration=true`, or
  - repo variable `RUN_PHASE3_INTEGRATION=1`
