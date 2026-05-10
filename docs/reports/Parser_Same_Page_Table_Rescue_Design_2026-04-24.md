# Parser Same-Page Table Rescue Design

Status: bounded prefix-truncation rescue implemented behind optional Docling path, default unchanged
Date: 2026-04-24
Owner: ingest/runtime maintainers

## Purpose

Record the constraints and verification for same-page table rescue in the optional `docling` hybrid parser path.

This note does not approve a default parser change. It exists because the derived OCR/repo stress lane found one real
same-page table truncation gap, while runtime behavior must still avoid duplicate-prone same-page fallback insertion.

## Layer Classification

This document is a review/gate artifact for the bounded runtime patch.

It does not change canonical state, parser contracts, FastAPI API shape, or the runtime default parser. The current
runtime default remains `fitz_pdfplumber`, and `docling` remains a behind-flag optional hybrid pilot.

## Evidence

Current grounding artifacts:

- [derived compare r33 metrics](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_derived_ocr_repo_20260426_r33/metrics.json)
- [derived section r33 summary](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_derived_ocr_repo_20260426_r33/summary.json)
- [derived table-merge r33 summary](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_derived_ocr_repo_20260426_r33/summary.json)
- [derived blocker triage r16](/Users/jangseongjin/paperpipe/snapshots/parser_readiness_blocker_triage/parser_readiness_blocker_triage_derived_ocr_repo_20260426_r16/summary.json)
- [source readiness r8](/Users/jangseongjin/paperpipe/snapshots/parser_baseline_readiness/parser_baseline_readiness_20260424_r8/summary.json)
- [same-page rescue readiness r2](/Users/jangseongjin/paperpipe/snapshots/same_page_table_rescue_readiness/same_page_table_rescue_readiness_20260426_r2/summary.json)
- [parser eval artifact inventory r1](/Users/jangseongjin/paperpipe/snapshots/parser_eval_artifact_inventory/parser_eval_artifact_inventory_20260426_r1/summary.json)
- [parser default-change RFC](/Users/jangseongjin/paperpipe/docs/reports/Parser_Default_Change_RFC_2026-04-24.md)

Current facts:

- r33 compare still passes on `7 / 7` derived OCR/repo documents.
- r33 candidate taxonomy records `SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION=1`.
- r33 candidate taxonomy records `FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED=3` for unresolved non-patched skips.
- r33 compare metrics record `docs_with_same_page_table_rescue_count=1`,
  `same_page_table_rescue_page_event_count=1`, and `same_page_table_rescue_patched_cell_count=1`.
- r33 table-merge audit reports `content_gap_count=0`.
- r16 blocker triage reports `table_runtime_patch_action=no_table_runtime_patch_needed`.
- Source-PDF readiness r8 still passes on the combined `53` document evidence set with `table_merge_gaps=0`.
- Same-page rescue readiness r2 passes with `patched_prefix_truncation_count=1`,
  `post_patch_candidate_page_count=0`, and `default_parser_change_ready=false`.
- Parser eval artifact inventory r1 keeps this stress evidence classified as derived review-only evidence, not
  default-change promotion evidence.

## Current Runtime Boundary

The current runtime behavior is intentionally conservative:

1. Fitz fallback tables may be merged when Docling has no table on that page.
2. Fitz fallback tables are not appended when Docling already has a table on that page.
3. A same-page fallback table may patch an existing Docling cell only when it covers a candidate-prefix truncation on a
   high-overlap same-page table.
4. Skipped same-page meaningful fallback candidates remain visible through
   `FALLBACK_TABLE_SKIPPED_PRIMARY_PAGE_COVERED`.
5. Patched same-page cells are visible through `SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION` and
   `same_page_table_rescue_*` diagnostics.
6. `fallback_used` and `fallback_pages` mean actual fallback table insertion, not same-page cell patching.

Do not weaken this boundary without a duplicate-safe design and targeted tests.

## Safe Rescue Shape

A future same-page rescue must be a patch/replace operation, not a blind append operation.

Allowed direction:

1. identify a same-page candidate table and same-page fallback table pair
2. prove the fallback table contains missing baseline-like cells or suffixes not present in the candidate table
3. prove candidate and fallback are the same logical table, not two separate same-page tables
4. patch only the missing row/cell span or replace the candidate table with a deduplicated table
5. emit diagnostics showing what was patched, replaced, skipped, or rejected

Rejected direction:

1. append a Fitz fallback table to a page already covered by a Docling table
2. treat high row count alone as evidence of semantic improvement
3. fuzzy-match away semantic suffix loss such as `tau unknown`
4. hide duplicate-risk decisions from runtime metadata or eval artifacts
5. use derived OCR stress evidence to change the runtime default parser

## Required Gates For The Bounded Implementation

The bounded prefix-truncation implementation must keep all of the following true:

1. a pairwise same-page rescue classifier with explicit outcomes: `patch`, `replace`, `skip_duplicate_risk`, `skip_low_confidence`
2. normalized cell coverage checks that prove the repaired table improves missing-cell coverage
3. duplicate checks that prove the repaired table does not duplicate candidate rows or cells beyond a fixed threshold
4. diagnostics that preserve skipped same-page fallback candidates separately from inserted fallback tables
5. targeted unit tests covering the Dubois truncation pattern
6. a negative test proving two legitimate same-page tables are not collapsed into one table
7. regenerated derived OCR/repo compare, section audit, table audit, and blocker triage artifacts
8. unchanged source-PDF parser readiness for the 53-document combined evidence set

Current progress:

- [audit_table_merge_semantics.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_table_merge_semantics.py)
  now includes an eval-only `classify_same_page_table_rescue_pair` helper.
- The helper currently distinguishes `patch`, `replace`, `skip_duplicate_risk`, `skip_low_confidence`, and
  `skip_no_missing_cells`.
- This is not runtime rescue wiring. It is only a testable pairwise classifier harness for future review.
- [audit_same_page_table_rescue_candidates.py](/Users/jangseongjin/paperpipe/scripts/eval/audit_same_page_table_rescue_candidates.py)
  applies that helper to saved table-merge audit details and writes review-only sidecar artifacts.
- [check_same_page_table_rescue_readiness.py](/Users/jangseongjin/paperpipe/scripts/eval/check_same_page_table_rescue_readiness.py)
  now checks the saved compare, table-merge, blocker-triage, rescue-candidate, and source-readiness artifacts together.
- The first derived OCR/repo sidecar is
  [same_page_table_rescue_candidates_derived_ocr_repo_20260424_r1](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/same_page_table_rescue_candidates/same_page_table_rescue_candidates_derived_ocr_repo_20260424_r1/summary.json):
  `candidate_page_count=1`, `action_counts={"patch": 1}`, and `runtime_change_approved=false`.
- After the bounded runtime patch, r33/r16/r8 verify that the derived blocker is resolved and source-PDF readiness
  remains green.
- The first readiness artifact is
  [same_page_table_rescue_readiness_20260426_r1](/Users/jangseongjin/paperpipe/snapshots/same_page_table_rescue_readiness/same_page_table_rescue_readiness_20260426_r1/summary.json):
  `passed=true`, `same_page_rescue_ready=true`, and `runtime_default_unchanged=true`.
- The refreshed readiness artifact
  [same_page_table_rescue_readiness_20260426_r2](/Users/jangseongjin/paperpipe/snapshots/same_page_table_rescue_readiness/same_page_table_rescue_readiness_20260426_r2/summary.json)
  points at r33/r16/r3 evidence and preserves the same decision.

## Suggested Diagnostics

Keep these as additive metadata only:

- `same_page_table_rescue_action`
- `same_page_table_rescue_pages`
- `same_page_table_rescue_patched_cells`
- `same_page_table_rescue_rejected_pages`
- `same_page_table_rescue_reject_reasons`

Do not overload `fallback_pages`; it should continue to mean pages where fallback table content was actually merged.

## Acceptance Bar

The bounded implementation is acceptable only while:

1. the Dubois derived OCR blocker no longer reports `amyloidunknowntauunknown` as missing
2. `table_same_page_duplicate_risk_page_count` does not increase on the derived OCR/repo lane
3. source-PDF readiness remains green
4. table diagnostics still expose skipped and repaired same-page cases
5. docs keep the default parser unchanged unless the separate default-change RFC is explicitly approved

## Current Decision

Keep the bounded prefix-truncation patch in the optional Docling hybrid path.

Do not expand same-page table rescue beyond this patch shape without another review. In particular, do not append
same-page fallback tables, do not implement broad table replacement yet, and do not use this patch as evidence for a
runtime default parser change.
