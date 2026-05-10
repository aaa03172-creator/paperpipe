# Institutional Access Fit Review

Status: completed
Date: 2026-03-28
Owner: Runtime/product maintainers
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
Follow-up:
- `docs/reports/Institutional_Access_Status_Semantics_RFC_2026-03-28.md`

## Purpose

Evaluate whether PaperPipe should refine its institutional-access behavior so operators can reach full text through university or institute subscriptions without turning the product into a publisher-login system.

This note is a bounded fit review, not a new subsystem spec.

## 1. Current repo access-layer summary

### Repo-confirmed facts

- PaperPipe already has an OA-first retrieval path:
  - `src/downloader/router.py`
  - `src/downloader/providers/unpaywall.py`
  - `src/downloader/providers/direct.py`
  - `src/downloader/providers/arxiv.py`
  - `src/downloader/providers/pmc.py`
- PaperPipe already has a lightweight institutional-access helper:
  - `src/institutional_access.py`
- That helper currently:
  - builds a KNU libproxy URL from DOI first, then publisher URL
  - stores it in `feedback_json.links.institutional_proxy_url`
  - never stores credentials
  - never performs publisher login
- Current operator-facing handling is already layered:
  - `pdf_status = manual_required`
  - `local_pdf_path`
  - `download_attempts`
  - `scripts/open_download_links.py`
  - `src/downloads_watcher.py` later reconciles manually obtained PDFs back into the local paper store
- Current note/export surfaces already expose the assist layer:
  - `src/obsidian.py`
  - `src/exporter.py`
- Current API does **not** yet expose a dedicated access-layer model:
  - `src/schemas/papers.py`
  - `backend/main.py`

### Current model shape

The current repo does **not** have a first-class institutional-access subsystem.

Instead it has:
- canonical paper metadata and download state
- OA-first downloader/provider logic
- a KNU-specific institutional proxy link helper
- manual download recovery via local PDF import/watch

That current shape is consistent with the product boundary.

## 2. What already fits

The following ideas already fit the repo and mostly exist in partial form:

- Open-access routes first
  - already true in the downloader/provider stack
- Institutional access second
  - already true in the current `manual_required + institutional_proxy_url` flow
- Never store university credentials directly
  - already true
- Separate canonical paper metadata from access routes
  - mostly true; the current proxy link lives in `feedback_json`, not in the main paper identity fields
- Treat institutional access as an optional access-assist layer
  - already the current behavior

So this is not a greenfield design problem.
It is mainly a cleanup, normalization, and clarity problem.

## 3. What would be overreach

These would be too large or off-shape right now:

- turning institutional access into a new canonical paper-source model
- publisher scraping
- direct credential handling
- session persistence for publisher or proxy login
- multi-institution account management
- a generalized “access platform” separate from current downloader/import flow
- first introducing new canonical DB enums without proving they map cleanly to current fields

These would push PaperPipe away from `paper-first biomedical workspace` and toward an access-infrastructure product.

## 4. Recommended bounded design

### Recommended decision

`docs/API cleanup only now`, with optional later additive API shaping.

That means:
- keep the current OA-first downloader flow
- keep the current local-PDF and watcher flow
- keep institutional access as optional assist only
- do **not** build a new subsystem

### Smallest safe refinement

If this is refined later, prefer:

1. leave current stored truth mostly as-is
   - `doi`
   - `link`
   - `pdf_link`
   - `local_pdf_path`
   - `download_attempts`
   - `pdf_status`
   - `feedback_json.links.institutional_proxy_url`

2. add a **derived** access summary for API/UI use
   - not a new canonical owner
   - not a replacement for downloader state

3. keep institutional assist generation deterministic
   - DOI first
   - publisher URL second
   - no scraping
   - no stored credentials

## 5. Suggested field/status model

### Canonical stored fields

Keep current stored fields as the main truth for now:

- `Paper.doi`
- `Paper.link`
- `Paper.pdf_link`
- `Paper.local_pdf_path`
- `Paper.download_attempts`
- `papers.pdf_status`
- `feedback_json.links.institutional_proxy_url`

### Recommended derived API field

If an additive cleanup is wanted later, introduce something like:

```json
{
  "access_summary": {
    "status_label": "open | institution_required | user_imported_pdf | unavailable",
    "open_access_url": "...",
    "institution_access_url": "...",
    "local_pdf_url": "/papers/<paper_id>/pdf"
  }
}
```

Important:
- `status_label` should start as a derived API/UI label
- not a new DB enum
- not a replacement for `pdf_status`

### Recommended mapping

- `user_imported_pdf`
  - when `local_pdf_path` exists
- `open`
  - when a known OA route is present or directly resolvable
  - likely from `pdf_link` or OA downloader/provider result
- `institution_required`
  - when no local PDF exists and an institutional proxy link is available
  - current `manual_required + institutional_proxy_url` is the closest existing shape
- `unavailable`
  - when neither local PDF, OA route, nor institutional assist route is available

### Why not make these canonical yet

Because the current repo already has:
- `pdf_status`
- `download_attempts`
- note/export feedback payloads

and those need a compatibility mapping first.

## 6. Recommended action

### Best next step

If anything is done, the next step should be a narrow additive API patch, not implementation-first subsystem work.

That RFC should answer:
- whether `manual_required` stays canonical
- whether `access_summary.status_label` should be added as an additive API field
- whether `institutional_proxy_url` should remain in `feedback_json` or move later into a better-bounded access summary object

### Recommendation today

- Do not start a new institutional-access subsystem
- Do not add scraping or credential handling
- Do not widen the product story
- If this area is touched, keep it to:
  - docs clarification
  - additive API response shaping
  - UI label cleanup

## 7. Applied outcome

Status: applied on 2026-03-28

The bounded additive path has now been implemented:
- `/papers` and `/papers/{paper_id}` expose derived `access_summary`
- no canonical stored paper fields were replaced
- no credential handling, scraping, or login persistence was introduced

Current derived response shape:
- `status_label`
- `open_access_url`
- `institution_access_url`
- `local_pdf_url`

Current label precedence:
- `user_imported_pdf` when a local PDF is present
- `open` when an OA PDF URL is present and no local PDF exists
- `institution_required` when no local PDF exists and an institutional proxy route is available
- `unavailable` otherwise

This keeps institutional access in the repo's intended role:
- optional access assist
- not canonical source truth
- not a login subsystem

Current semantics note:
- `user_imported_pdf` is intentionally treated as a coarse local-PDF-present label for now
- the current decision boundary is captured in `docs/reports/Institutional_Access_Status_Semantics_RFC_2026-03-28.md`

Current posture:
- treat this lane as applied and closed
- do not reopen it as a new institutional-access subsystem
- only revisit it if a concrete access-routing blocker appears on the current paper surfaces

## Conclusion

Institutional access is a good fit for PaperPipe only as a lightweight assist layer.

The repo already has the right primitive:
- OA first
- institutional proxy second
- local PDF import/watch as the real recovery path

So the right move is refinement, not reinvention.
