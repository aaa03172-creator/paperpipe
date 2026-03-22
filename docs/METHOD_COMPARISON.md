# Method Comparison

Status: Active spec
Date: 2026-03-23
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/document_artifact_v2.md`
- `docs/UX_REVIEW_REPORT_method-comparison-viewer.md`
- `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- `docs/archive/Method_Comparison_v0_Implementation_Plan_2026-03-18.md`

## Purpose

`Method Comparison` is a bounded, paper-centric comparison artifact.

It exists to let operators compare a small curated set of method-relevant fields across selected papers without introducing:
- a new spreadsheet platform
- a new project/workspace model
- a second truth store beside current paper/run/artifact state

The current lane is intentionally narrow:
- file-backed
- evidence-linked
- read-first
- derived from current runtime artifacts

## Current Implementation Status

Implemented in workspace:
- `src/schemas/method_comparison.py`
- `src/method_comparisons/store.py`
- `src/method_comparisons/source_loader.py`
- `src/method_comparisons/service.py`
- `src/method_comparisons/renderer.py`
- `src/services/runtime_paths.py::method_comparisons_root()`
- `backend/routers/method_comparisons.py`
- read-only frontend viewer:
  - `/method-comparisons`
  - `/method-comparisons/:comparisonId`
- fixture hardening, backend API tests, frontend mock smoke, frontend backend smoke

Currently deferred:
- document/table fallback beyond the current bounded extractor behavior
- operator edit flow
- spreadsheet-like workspace behavior
- project-scoped memory or workspace embedding

## Current Judgment

At the current repo stage, `Method Comparison` is the strongest candidate for an active bounded spec among the recent future lanes.

That judgment is based on:
- direct fit with the current paper-first runtime
- reuse of existing claim/evidence lineage
- bounded artifact storage that does not redefine the product surface
- enough implementation maturity to freeze the v0 boundary

## Current Boundary

### 1. Identity stays paper-first

The request/runtime stays `paper_id`-first.

Current rule:
- request inputs are centered on `paper_ids[]`
- downstream note/evidence lineage may carry a distinct `paper_slug`
- `paper_slug` must be resolved explicitly rather than inferred from `paper_id`

This keeps the lane aligned with current backend/runtime identity rules.

### 2. Source priority stays deterministic

Current v0 source priority:
1. `claimset.resolved.json`
2. `document_artifact` payloads
3. paper-note `state.json` only when claim/evidence identity is preserved

Current rule:
- do not mine freeform note prose as if it were structured evidence
- do not synthesize method cells through broad LLM rewriting
- if deterministic support is weak, preserve `inferred`, `conflict`, or `missing`

### 3. Field support stays curated

Current allowlist:
- `intervention`
- `comparator`
- `duration_or_timepoint`
- `primary_readout`
- `sample_size`

Current rule:
- `Method Comparison` does not claim to cover every method dimension
- expanding the field registry requires a new deterministic extractor case, not just a new label

### 4. Cell truth must stay evidence-linked

Current cell status family:
- `explicit`
- `inferred`
- `missing`
- `conflict`

Current rule:
- every non-missing cell must remain tied to explicit provenance
- current evidence refs reuse the existing `ChatEvidenceRef` / locator family
- no second evidence locator system may be introduced for this lane
- missing or conflicting support must stay visible in JSON/CSV/Markdown/viewer outputs

### 5. Storage stays file-backed

Current storage root:

```text
storage/method_comparisons/<comparison_id>/
  comparison.json
  comparison.csv
  comparison.md
```

Current rule:
- the saved bundle is a derived artifact, not a new canonical research-state store
- repeated generation with the same inputs should remain deterministic in row order, column order, and export ordering

### 6. API stays thin

Current API surface:
- `POST /method-comparisons/generate`
- `GET /method-comparisons`
- `GET /method-comparisons/{comparison_id}`
- `GET /method-comparisons/{comparison_id}/export.csv`

Current rule:
- the API is a thin wrapper over schema/service/store code
- CSV export remains an attachment-backed handoff surface, not a hidden editor contract

### 7. Viewer stays read-only

Current viewer surface:
- `/method-comparisons`
- `/method-comparisons/:comparisonId`

Current rule:
- viewer is for inspection, not editing
- conflict/missing cells must stay visually explicit
- evidence trace and warning visibility matter more than spreadsheet density
- row-level `Open note` handoff should only target canonical paper-note candidates

## Current Non-Goals

The current spec does not include:
- spreadsheet editing
- operator override UI
- project-level workspace ownership
- freeform note mining
- semantic search over arbitrary note bodies
- generalized method ontology management
- promotion of comparison output into claim truth

## Relationship To Other Bounded Lanes

- `Meeting Pack` may consume a saved Method Comparison later as a downstream artifact, but `Method Comparison` must not be embedded as a hidden side-format inside meeting-pack storage.
- `Chart Pack` may later consume structured values from Method Comparison, but Method Comparison itself is not a plotting or presentation layer.
- `Image Evidence` remains a separate metadata-first sidecar and should not be folded into Method Comparison semantics.

## Verification Expectations

Current verification lanes should remain:
- targeted pytest coverage for schema/store/source-loader/service/API
- backend Playwright smoke for generated comparison viewer/export flow
- mock Playwright coverage for the read-only viewer

When this spec changes:
- keep `comparison.json / comparison.csv / comparison.md` deterministic
- keep provenance and warning semantics stable
- avoid widening source semantics without updating both tests and the bounded spec

## Conclusion

`Method Comparison` is now an active bounded spec because the lane is implemented, evidence-linked, and well aligned with the current paper-first runtime.

The next changes in this area should harden or extend this bounded artifact family.

They should not reopen the broader question of whether Lattice should become a generalized comparison platform.
