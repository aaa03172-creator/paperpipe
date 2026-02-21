# Operations Checklist - Downloads Watcher & Review Queue

Date: 2026-02-21
Scope: `downloads_watcher`, `review_queue`, QA counters

## 0) One-Time Guardrail (DB Index)
Ensure open review rows are unique per `(paper_id, decision)`.

```bash
sqlite3 storage/state.db "CREATE UNIQUE INDEX IF NOT EXISTS idx_review_queue_open_unique ON review_queue (paper_id, decision) WHERE resolved_at IS NULL;"
sqlite3 storage/state.db "SELECT type, name FROM sqlite_master WHERE tbl_name='review_queue' ORDER BY type, name;"
```

Expected:
- `idx_review_queue_open_unique` exists.

## 1) Pre-Run Safety Check (60 sec)
Verify there are no existing open duplicates before watcher operation.

```bash
sqlite3 storage/state.db "SELECT paper_id, decision, COUNT(*) AS cnt FROM review_queue WHERE resolved_at IS NULL GROUP BY paper_id, decision HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT 20;"
```

Expected:
- No rows returned.

## 2) Watcher Runtime Check
After placing test PDFs in Downloads folder, confirm watcher outcomes.

```bash
python3 -m src.cli watch-downloads
```

Expected:
- Matched files move to `storage/pdfs/`.
- Ambiguous or unmatched files move to `storage/pdfs/_unmatched/`.
- DB updates:
  - matched: `papers.pdf_status='downloaded'`, `papers.pdf_path` filled
  - unmatched/ambiguous: `review_queue` receives `NEEDS_PDF_MATCH` (no open duplicates for same paper/decision)

## 3) QA Counter Sanity
Run QA and validate counter meanings.

```bash
python3 scripts/qa_report.py
```

Counter contract:
- `manual_required`: active papers with `pdf_status='manual_required'`
- `downloaded_missing_path`: active papers with downloaded status but blank `pdf_path`
- `unmatched`: open review count (`review_queue`, `decision='NEEDS_PDF_MATCH'`, `resolved_at IS NULL`)
- `unmatched_files`: count of PDF files in `storage/pdfs/_unmatched`

## 4) Triage Workflow for Unmatched
1. Open review targets:
```bash
sqlite3 storage/state.db "SELECT id, paper_id, decision, reason, created_at FROM review_queue WHERE decision='NEEDS_PDF_MATCH' AND resolved_at IS NULL ORDER BY created_at ASC LIMIT 50;"
```
2. Confirm candidate paper metadata:
```bash
sqlite3 storage/state.db "SELECT paper_id, title, doi, pdf_status, pdf_path FROM papers WHERE paper_id='<PAPER_ID>';"
```
3. After manual resolution, mark queue row resolved:
```bash
sqlite3 storage/state.db "UPDATE review_queue SET resolved_at=CURRENT_TIMESTAMP, resolution='MANUAL_FIX', owner='OPS' WHERE id=<QUEUE_ID> AND resolved_at IS NULL;"
```

## 5) Incident Pattern & Action
- Symptom: `unmatched_files` increasing, `unmatched` flat.
  - Action: inspect `_unmatched` and confirm watcher process is running.
- Symptom: `unmatched` increasing rapidly.
  - Action: check DOI quality in downloaded filenames and update manual-required paper metadata quality.
- Symptom: integrity error on review insert.
  - Action: indicates duplicate open row race was blocked as designed; inspect queue row and continue.

## 6) Weekly Smoke (Recommended)
```bash
pytest -q tests/test_downloads_watcher.py tests/test_qa_report_institutional_counters.py tests/test_claimset_export_review_queue_qa.py
```

Expected:
- All pass.

