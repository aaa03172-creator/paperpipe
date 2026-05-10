# Provenance / Trust Language Consistency Audit

Status: Applied bounded audit
Date: 2026-03-27
Owner: Runtime/product maintainers
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

## Purpose

Tighten a small release-defining wording gap:

- source of truth
- saved state
- runtime-managed sidecar state
- downstream artifact trust language

This is not a runtime change.
This is not a product-shape change.
This is a bounded wording audit across the current release/demo docs.

## Current Judgment

The core provenance/trust story was already mostly aligned.

The remaining drift was narrower:

- some release/demo docs still said `note-side canonical state`
- that wording could blur the owner boundary between:
  - runtime-managed paper-scoped sidecar state
  - note body/frontmatter as operator-facing mirror

Recommended fix:

- keep the current product/runtime story
- make the owner boundary more explicit
- do not widen the audit into a broader wording rewrite

## Findings

### 1. Current source-of-truth wording was mostly consistent

Consistent anchors already existed:

- `docs/Product_Positioning_Principles.md`
  - schema-backed structured state is the source of truth
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
  - source of truth is runtime-owned structured state
- `docs/Evidence_and_Uncertainty_Rules.md`
  - evidence-linked truth and visible uncertainty remain mandatory
- `docs/MEETING_PACK.md`
  - `.pp/<slug>/state.json` is paper-scoped canonical state
  - `Meeting Pack` is a downstream draft artifact, not the truth store

### 2. Small owner-boundary drift remained in release/demo docs

The drift points were:

- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`
  - `promoted note-side canonical state`
- `docs/reports/First_Product_Demo_Runbook_2026-03-27.md`
  - `visible note-side .pp/<slug>/state.json`
  - `canonical note-side structured state`
- `docs/reports/First_Product_Demo_FAQ_2026-03-27.md`
  - `note-side StructuredPaperState`

These phrases were close, but less precise than the stronger current wording already used elsewhere:

- `paper-scoped canonical state`
- runtime-managed sidecar state
- note body/frontmatter as mirror, not owner

## Applied changes

The audit applied only the narrow wording fixes.

### Launch readiness

- changed the deep-read/job row note to say the representative rerun promoted a runtime-managed paper-scoped sidecar state under `.pp/<slug>/state.json`

### Demo runbook

- changed representative-paper wording from `note-side` to `paper-scoped ... sidecar`
- changed detail-page talk track from `canonical note-side structured state` to `runtime-managed paper-scoped structured state sidecar`
- kept the rest of the demo flow unchanged

### Demo FAQ

- changed `note-side StructuredPaperState` to `paper-scoped StructuredPaperState sidecar (.pp/<slug>/state.json)`
- kept the overall answer shape unchanged

## Non-changes

This audit did not:

- change any runtime contract
- change viewer behavior
- change the launch-defining status rows
- promote `Meeting Pack` or any downstream artifact into a truth store
- reopen broader provenance/citation-verification feature work

## Remaining judgment

The launch checklist `yellow` on provenance/uncertainty should stay `yellow`.

Reason:

- docs/demo wording is now tighter
- but the underlying runtime truth remains the same:
  - citation readiness is still presence-based in places
  - not every trust signal is as strong as the strongest current lanes

So the remaining gap is no longer wording drift.
It is implementation-strength unevenness.

## Conclusion

This bounded wording audit is enough.

Current recommendation:

- keep the patched wording
- do not expand this into a larger copy pass
- treat the remaining provenance/trust item as a runtime-strength question, not a docs-language question
