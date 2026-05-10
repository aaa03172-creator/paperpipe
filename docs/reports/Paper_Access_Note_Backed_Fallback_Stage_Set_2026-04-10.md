# Paper Access Note-Backed Fallback Stage Set

Date: 2026-04-10
Owner: Codex
Status: staged-slice-prep

## Intent

Isolate the `papers` API slice that:

- adds `access_summary` to paper list/detail responses
- derives local/open/institutional access labels from existing paper metadata
- falls back to note-backed local PDF paths when the DB row is absent or incomplete

## Included scope

- `src/schemas/papers.py`
  - add `PaperAccessSummary`
  - expose `access_summary` on `PaperSummaryResponse` and `PaperDetailResponse`
- `backend/main.py`
  - add paper access summary helpers
  - add note-backed local PDF resolution helpers
  - update `/papers` to emit derived access summaries
  - update `/papers/{paper_id}` to support note-backed fallback
  - update `/papers/{paper_id}/pdf` to serve note-backed local PDFs when available

## Explicitly excluded

- `/workspace-summary`
- browser security, beta gate, audit logging, or runtime-readiness changes
- fixture filtering and other listing-cleanup changes
- unrelated `backend/main.py` imports and helpers
- remaining `src/cli.py` tail changes

## Why this is a valid standalone lane

- The route behavior is covered by focused tests in `tests/test_papers_api.py`.
- The schema additions are self-contained and required for response validation.
- The lane preserves the existing FastAPI ownership and does not introduce a new storage layer.

## Verification plan

- `pytest -q tests/test_papers_api.py::test_papers_endpoints_include_derived_access_summary tests/test_papers_api.py::test_papers_detail_includes_pdf_exists_and_missing_status tests/test_papers_api.py::test_papers_detail_and_pdf_route_fall_back_to_note_backed_local_pdf`
- `python3 scripts/lint_docs.py`

## Verification results

- `pytest -q tests/test_papers_api.py::test_papers_endpoints_include_derived_access_summary tests/test_papers_api.py::test_papers_detail_includes_pdf_exists_and_missing_status tests/test_papers_api.py::test_papers_detail_and_pdf_route_fall_back_to_note_backed_local_pdf`
  - passed in the current worktree: `3 passed, 5 warnings`
- `python3 scripts/lint_docs.py`
  - passed: `docs lint passed`
- clean index-export verification is currently blocked by a pre-existing mixed-file dependency:
  - `backend/main.py` already imports `ResearchDNAScreeningGuidanceIndexEnvelope`
  - `HEAD:src/schemas/research_dna.py` does not yet define that symbol
  - this blocker is outside the paper-access lane staged here
