# Parser Default Change RFC

Status: bounded RFC note, discussion opened explicitly, default unchanged
Date: 2026-04-24
Owner: ingest/runtime maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/reports/Ingest_Backend_Docling_Pilot_2026-03-23.md`

## Purpose

Record the current decision boundary for changing PaperPipe's runtime parser default from
`fitz_pdfplumber` to the optional `docling` backend.

This RFC does not approve a runtime default change. It exists to separate parser-quality evidence
from the architecture/product-policy decision that would be required before changing the default.

## Executive Call

Safest current direction:

1. keep `fitz_pdfplumber` as the runtime default
2. keep `docling` available only as a behind-flag optional hybrid pilot
3. treat the refreshed parser evidence as sufficient for a default-change review discussion, not as approval to switch
4. require an explicit architecture decision before any default parser change is implemented

## Current Evidence

Latest grounding artifacts:

- [parser readiness r7 summary](/Users/jangseongjin/paperpipe/snapshots/parser_baseline_readiness/parser_baseline_readiness_20260424_r7/summary.json)
- [parser blocker triage r6 summary](/Users/jangseongjin/paperpipe/snapshots/parser_readiness_blocker_triage/parser_readiness_blocker_triage_20260424_r6/summary.json)
- [expanded compare r28 metrics](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_20260424_r28/metrics.json)
- [broad compare r29 metrics](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_expanded_broad_20260424_r29/metrics.json)
- [refresh compare r24 metrics](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_refresh_20260423_r24/metrics.json)
- [section audit r25 summary](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_refresh_20260423_r25/summary.json)
- [table merge audit r27 summary](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_refresh_20260423_r27/summary.json)
- [parser eval artifact inventory r1](/Users/jangseongjin/paperpipe/snapshots/parser_eval_artifact_inventory/parser_eval_artifact_inventory_20260426_r1/summary.json)

Current readiness result:

- parser baseline ready: `true`
- baseline parser usable: `true`
- Docling optional pilot supported: `true`
- default parser change ready: `false`
- compare document count: `53`
- compare runs passed: `3 / 3`
- baseline success count: `53 / 53`
- candidate success count: `53 / 53`
- candidate DOI loss docs: `0`
- candidate low text-ratio docs: `0`
- candidate meaningful table loss docs: `0`
- candidate meaningful table gain docs: `19`
- candidate table fallback docs: `3`
- section missing-page docs: `0`
- section unclassified low-ratio docs: `0`
- section collapse docs: `0`
- same-page merge docs: `6`
- table merge content gaps: `0`

Default-change review evidence is now green enough to open this RFC:

- document-count floor: `53 / 50`
- freshness floor: `true`
- oldest compare artifact age at r7: about `0.03` days
- configured max artifact age for review: `30` days
- parser eval artifact inventory: `source_readiness_document_count=53`, `derived_stress_document_count=7`,
  and `default_change_review_document_count=53`

Derived OCR/repo stress evidence was also added after the RFC opened:

- [derived manifest](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_derived_ocr_and_repo_20260424.json)
- [derived compare r33 metrics](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/docling_pilot_manifest_derived_ocr_repo_20260426_r33/metrics.json)
- [derived section r33 summary](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/section_quality_audits/docling_section_quality_audit_derived_ocr_repo_20260426_r33/summary.json)
- [derived table-merge r33 summary](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/table_merge_audits/docling_same_page_merge_audit_derived_ocr_repo_20260426_r33/summary.json)
- [derived blocker triage r16](/Users/jangseongjin/paperpipe/snapshots/parser_readiness_blocker_triage/parser_readiness_blocker_triage_derived_ocr_repo_20260426_r16/summary.json)
- [same-page table rescue design](/Users/jangseongjin/paperpipe/docs/reports/Parser_Same_Page_Table_Rescue_Design_2026-04-24.md)
- [same-page rescue candidates r3](/Users/jangseongjin/paperpipe/snapshots/ingest_backend_eval/same_page_table_rescue_candidates/same_page_table_rescue_candidates_derived_ocr_repo_20260426_r3/summary.json)
- [same-page rescue readiness r2](/Users/jangseongjin/paperpipe/snapshots/same_page_table_rescue_readiness/same_page_table_rescue_readiness_20260426_r2/summary.json)

That derived lane still passes the top-level compare on `7 / 7` documents. The bounded same-page prefix-truncation
patch resolves the previous Dubois OCR-derived table content gap: r33 table-merge audit reports
`content_gap_count=0`, r16 blocker triage reports `table_runtime_patch_action=no_table_runtime_patch_needed`, and
r33 candidate taxonomy records `SAME_PAGE_TABLE_RESCUE_PATCHED_PREFIX_TRUNCATION=1`.
This removes the narrow derived OCR table blocker, but it does not approve a runtime default parser change.
The dedicated same-page rescue readiness check now preserves that conclusion as a one-command gate:
`passed=true`, `same_page_rescue_ready=true`, `post_patch_candidate_page_count=0`, and
`default_parser_change_ready=false`.
The parser eval artifact inventory records the same boundary explicitly: derived OCR/repo stress evidence is
`review_only` and excluded from default-change promotion evidence.

## Why This Is Not Adopted Yet

### 1. The candidate path is still a hybrid optional backend

The current `docling` lane uses bounded fallbacks for DOI, page-section, and meaningful table rescue cases.
That is a useful operator feature, but it is not evidence that pure Docling extraction should replace the
current parser default.

### 2. Eval artifacts are review evidence, not canonical runtime truth

The readiness and triage summaries are review/gate artifacts. They make the decision reproducible, but they
do not replace the current FastAPI/runtime parser contract or the existing paper/run/artifact model.

### 3. A default parser change is a product/runtime policy decision

Changing the default would affect every ingest path, including downstream paper notes, tables, generated
artifacts, and operator expectations. That needs explicit architecture approval even when the technical
evidence is healthy.

### 4. Derived OCR stress evidence is a stress lane, not default-change approval

The derived OCR/repo lane is not canonical source truth, but it is useful stress evidence for artifact-like PDFs.
The previous same-page table gap is now patched, but the lane remains review evidence rather than default-change
approval.

## Candidate Change If Later Adopted

If maintainers later approve a default parser change, the smallest safe implementation should be:

1. change only the configured default parser resolution, not the parser ownership model
2. keep the `enable_docling` gate or an equivalent explicit capability gate
3. keep fallback metadata visible in parser eval and runtime table metadata
4. keep `fitz_pdfplumber` available as a forced fallback/backend override
5. rerun parser readiness, blocker triage, backend smoke, and a real ingest smoke before release

Expected non-goals for that future patch:

- no new canonical document store
- no parser-output schema drift without a separate schema RFC
- no removal of existing fallback or override controls
- no broad rewrite of ingest, jobs, or paper-note generation

## What To Reject

Reject these shortcuts by default:

1. changing the default because the 53-document readiness set passed once
2. treating hybrid fallback success as proof that pure Docling is sufficient
3. hiding fallback frequency from runtime or eval artifacts
4. combining default-parser change with a broad ingest rewrite
5. weakening `fitz_pdfplumber` rollback/override paths before the new default has real operator history

## Current Decision

Current best judgment:

> keep `fitz_pdfplumber` as the runtime default, keep `docling` as a behind-flag optional hybrid pilot, and use
> the current green parser evidence only to support an explicit default-change review discussion.

## Reopen Trigger

Reopen this RFC for implementation only when all of the following are true:

1. runtime/product maintainers explicitly approve a default parser policy change
2. a fresh parser readiness run still passes across the combined saved evidence set
3. blocker triage still reports no candidate blockers
4. fallback usage and same-page merge behavior remain visible in artifacts
5. a rollback plan keeps `fitz_pdfplumber` selectable without a code revert
6. derived OCR table truncation is resolved, explicitly accepted, or excluded by policy before default adoption
7. any same-page table rescue follows the duplicate-safe design constraints and passes refreshed eval artifacts

Until then, this RFC should remain open for discussion with the default unchanged.
