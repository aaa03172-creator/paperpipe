# Institutional Access Status Semantics RFC

Status: proposed, no runtime change required
Date: 2026-03-28
Owner: Runtime/product maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/reports/Institutional_Access_Fit_Review_2026-03-28.md`

## Purpose

Freeze the current decision boundary for the new derived `access_summary.status_label` field so it is not misread as:
- a new canonical paper-source model
- a promise of publisher or institution login support
- a precise provenance statement about how a local PDF arrived

This is a semantics RFC, not a subsystem proposal.

## 1. Current runtime facts

### Repo-confirmed facts

- `access_summary` is additive API/UI shaping only:
  - `src/schemas/papers.py`
  - `backend/main.py`
  - `frontend/src/app/lib/types.ts`
  - `frontend/src/app/lib/api.ts`
- Current stored/runtime truth still lives in existing fields:
  - `papers.pdf_status`
  - `papers.pdf_path`
  - `papers.pdf_link`
  - `papers.link`
  - `papers.doi`
  - `feedback_json.links.institutional_proxy_url`
- Current UI exposure is intentionally minimal:
  - triage row badge + optional route link
  - no new access workflow
  - no new login flow
- Current institution assist remains:
  - KNU libproxy URL generation
  - no credential storage
  - no scraping

### Current derived label set

- `open`
- `institution_required`
- `user_imported_pdf`
- `unavailable`

## 2. Current meaning of each label

### `open`

Current meaning:
- an open-access PDF route is directly present in current paper state
- currently derived from `pdf_link`
- only used when no local PDF is currently present

What it does **not** mean:
- that every downstream viewer/export route is OA-complete
- that PaperPipe performed fresh live OA verification at render time

### `institution_required`

Current meaning:
- no local PDF is present
- an institution-assisted route is available
- currently derived from `feedback_json.links.institutional_proxy_url` or deterministic DOI/publisher URL fallback

What it does **not** mean:
- that the institution route is guaranteed to succeed
- that PaperPipe handles login, proxy session, or entitlement verification

### `user_imported_pdf`

Current meaning **today**:
- a local PDF is present and routable via `/papers/{paper_id}/pdf`

Important mismatch:
- the label reads as if the PDF definitely came from a manual user import
- current repo truth does **not** consistently preserve that provenance distinction
- a present local PDF may have arrived from:
  - prior OA auto-download
  - manual import / downloads watcher recovery
  - older local migration state

So current semantics are intentionally coarse:
- API label: `user_imported_pdf`
- operator-facing UI copy: `Local PDF`

### `unavailable`

Current meaning:
- no local PDF
- no OA PDF route currently present
- no institution-assisted route currently derivable

What it does **not** mean:
- that the paper can never be obtained
- that future downloader/provider improvements cannot recover a route later

## 3. Why we are keeping the current coarse mapping

Because it is the smallest safe additive layer that:
- does not change stored paper truth
- does not require DB migration
- does not invent provenance we do not currently store
- helps the operator decide what route is currently visible

This is acceptable because the main product goal here is:
- route visibility
- not acquisition provenance fidelity

## 4. Why we are not renaming the API field yet

Possible future names such as:
- `local_pdf_available`
- `local_pdf_present`
- `local_pdf_ready`

would be more semantically precise than `user_imported_pdf`.

We are **not** renaming now because:
- the new field just landed
- current UI already softens the meaning by displaying `Local PDF`
- a rename would create unnecessary contract churn before proving a real operator problem

## 5. Current decision

Keep the API label set as-is for now.

Current operational rule:
- API may keep `user_imported_pdf`
- UI should prefer neutral wording like `Local PDF`
- docs must clearly state that this label currently means local-PDF-present, not guaranteed manual-import provenance

## 6. Reopen conditions

Reopen this RFC only if one of the following becomes true:

1. local PDF provenance becomes product-visible or operationally important
   - for example: users need to distinguish OA auto-download from manual recovery

2. saved access state starts driving workflow branching
   - for example: different actions for OA-ready vs manual-imported vs mirrored PDFs

3. exporter/notes/workbench need a precise provenance label rather than a coarse route label

4. a broader access-status cleanup is explicitly requested

## 7. Explicit non-goals

This RFC does **not** authorize:
- publisher scraping
- credential handling
- session persistence
- a new institutional-access subsystem
- turning access labels into canonical stored enums
- turning the paper model into an access-first source model

## Conclusion

The current semantics are intentionally conservative:
- keep the additive route labels
- keep the current API field stable
- keep UI wording neutral where needed
- revisit only if local PDF provenance becomes materially important
