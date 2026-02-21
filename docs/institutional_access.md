# Institutional Access Workflow (KNU libproxy)

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
  - DOI-first exact match (filename DOI -> papers.doi/paper_id)
  - title similarity fallback (safe threshold)
  - ambiguous/unmatched files go to `storage/pdfs/_unmatched`
  - ambiguous/unmatched creates `review_queue` with `NEEDS_PDF_MATCH` (best-effort)
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

## Next Steps
- Feature C: QA counters for manual/downloaded/unmatched states (baseline implemented)
  - `scripts/qa_report.py` now reports:
    - `manual_required`
    - `downloaded_missing_path`
    - `unmatched` (`review_queue` open `NEEDS_PDF_MATCH`)
