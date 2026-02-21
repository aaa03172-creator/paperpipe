# Institutional Access (KNU libproxy) Execution Plan

Date: 2026-02-21

## Scope Requested
- Feature A: institutional proxy link generation + manual_required queue + bulk opener script
- Feature B: Downloads watcher for semi-auto PDF intake after user browser download
- Feature C: QA counters (manual_required / downloaded-missing-path / unmatched + unmatched_files)

## Hard Rules (Applied)
- No paywall bypass, no credential scraping, no ID/PW storage.
- OA auto-download remains unchanged.
- Fail-safe behavior is mandatory.
- Prefer existing DB columns: `pdf_status`, `pdf_path`, `feedback_json`, `obsidian_path`.

## Blocker Check (Stop Condition)
### 1) DB Path Mismatch (BLOCKER)
- `/Users/jangseongjin/paperpipe/src/db.py:6`
  - `DB_PATH = "state.db"`
- `/Users/jangseongjin/paperpipe/src/db_utils.py:10`
  - `DB_PATH = Path("storage/state.db")`
- `/Users/jangseongjin/paperpipe/scripts/init_db.py:6`
  - `DB_PATH = Path("storage/state.db")`

Impact:
- Different modules read/write different SQLite files.
- New `manual_required` and watcher updates may silently land in the wrong DB.

Fix Suggestion:
- Canonicalize DB path to `storage/state.db` across runtime modules.
- Best minimal change: update `/Users/jangseongjin/paperpipe/src/db.py` to use `Path("storage/state.db")` and ensure parent dir creation before connect.
- Add 1 smoke test asserting `src.db` and `src.db_utils` resolve same DB path.

### 2) Exporter/Obsidian Path Persistence Mismatch (BLOCKER-2)
- Schema has `obsidian_path` in `/Users/jangseongjin/paperpipe/scripts/init_db.py:56`.
- Current write paths are file-system only:
  - `/Users/jangseongjin/paperpipe/src/exporter.py:460-501`
  - `/Users/jangseongjin/paperpipe/src/obsidian.py:417-481`
- Neither path updates `papers.obsidian_path` in DB.

Impact:
- "use existing obsidian_path column" requirement cannot be guaranteed end-to-end.

Fix Suggestion:
- On markdown write success, persist relative note path to `papers.obsidian_path`.
- Apply in one place (recommended: exporter flow) to avoid dual writers.

## Priority vs Existing Follow-ups (#31/#32/#33)
### Immediate Priority (before Feature A/B/C)
1. P0: Resolve DB path mismatch.
2. P0: Resolve obsidian_path persistence mismatch.

### Then Requested Work
3. P1: PR#1 (Feature A) libproxy link + manual_required + open_download_links.
4. P1: PR#2 (Feature B) Downloads watcher + DOI/title matching + unmatched + review_queue.
5. P2: PR#3 (Feature C) QA additions + docs polish.

### Existing Optional Follow-ups
- #31 provider timeout/header policy
- #32 cache TTL/size
- #33 retry metrics

Placement:
- Defer #31/#32/#33 until after A/B/C baseline is merged.
- Rationale: institutional workflow is current product requirement; downloader tuning can follow without blocking legal intake flow.

## PR Breakdown (Refined)
### PR#0 (new, blocker fix)
- Unify DB path modules.
- Persist `obsidian_path` on markdown export.
- Add tests for path consistency and path persistence.

### PR#1 (Feature A)
- Add `src/institutional_proxy.py` (or downloader helper) for KNU proxy URL generation.
- On OA miss, set `pdf_status='manual_required'` and write
  - `feedback_json.links.institutional_proxy_url`
- Exporter markdown block: Institutional Link + instruction.
- Add `scripts/open_download_links.py`.
- Tests: T1/T2/T3.

### PR#2 (Feature B)
- Add downloads watcher (configurable, default `~/Downloads`).
- DOI exact match, title fuzzy match, ambiguous -> safe fallback.
- On match: move to storage path + set `pdf_status='downloaded'`, `pdf_path`, `updated_at`.
- On fail/ambiguous: move to `_unmatched`, enqueue `review_queue` with `NEEDS_PDF_MATCH`.
- Tests: T4/T5.

### PR#3 (Feature C)
- Extend `scripts/qa_report.py` counters.
- Write docs: `/Users/jangseongjin/paperpipe/docs/institutional_access.md`.

## Config Additions (planned)
- `paths.downloads_watch_dir` (optional, default `~/Downloads`)
- `paths.pdf_storage_dir` (optional, default `storage/pdfs`)
- Fuzzy threshold constant (safe conservative default, e.g., 0.90)

## Notes
- Keep OA providers untouched except manual_required fallback path.
- No schema migration required for new feature payload storage in `feedback_json`.
