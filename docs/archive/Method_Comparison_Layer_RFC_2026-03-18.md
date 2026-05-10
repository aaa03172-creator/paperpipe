# Method Comparison Layer RFC

Status: Historical proposal  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related:
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/archive/Method_Comparison_v0_Implementation_Plan_2026-03-18.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/document_artifact_v2.md`
- `docs/MEETING_PACK.md`

## Purpose

External proposal docs strongly emphasized a structured `MethodRecord` plus comparison-table workflow.

That need is real:
- users often compare assay/model/sample/treatment/readout choices across papers
- today the repo can surface paper artifacts, notes, and meeting packs, but it does not yet provide a bounded reusable comparison layer

This RFC defines the smallest method-comparison subsystem that fits the current paper-centric runtime.

## Current fit

Current repo already has:
- papers as the main evidence source
- derived run artifacts under `storage/artifacts/`
- paper notes and structured state as reader-facing knowledge surfaces
- meeting packs for presentation-oriented downstream synthesis

Current repo does not have:
- a first-class comparison-table asset
- a canonical method extraction contract separate from general claims
- a reason to import a full `projects/documents/methods` platform model

So the correct adaptation is:
- build method comparison as a bounded paper-derived artifact
- not as a new app-wide CRUD baseline

## Non-goals

- not a generic spreadsheet system
- not a full scientific ontology project
- not a replacement for claim/evidence storage
- not a reason to introduce `/projects/{id}/methods` as the new product center

## Boundary rules

### What this layer may do

- compare method-like facts across selected papers
- preserve cell-level provenance
- distinguish explicit values from inferred values
- export stable comparison views

### What this layer must not do

- become an alternate truth store for papers
- claim certainty without evidence
- hide conflicts between body, table, figure, or supplement
- depend on a new global project database before proving value

## Proposed phase-0 model

### `MethodComparisonRequest`

Suggested fields:
- `comparison_id`
- `title`
- `paper_ids[]`
- `fields[]`
- `notes?`
- `created_at`

### `MethodComparison`

Suggested fields:
- `comparison_id`
- `title`
- `paper_ids[]`
- `columns[]`
- `rows[]`
- `generated_at`
- `source_summary`
- `warnings[]`

### `ComparisonColumn`

Suggested fields:
- `field_id`
- `label`
- `value_kind`
  - `text`
  - `numeric`
  - `duration`
  - `categorical`

### `ComparisonRow`

Suggested fields:
- `paper_id`
- `paper_slug?`
- `citekey?`
- `title`
- `cells`

### `ComparisonCell`

Suggested fields:
- `value`
- `normalized_value?`
- `status`
  - `explicit`
  - `inferred`
  - `missing`
  - `conflict`
- `note?`
- `evidence_refs[]`

## Source priority

Phase 0 should stay deterministic and use a fixed source priority:

1. `claimset.resolved.json` when the target field is already grounded there
2. `document_artifact.json` / `document_artifact_v2` table or page payload when the value is directly extractable
3. paper-note structured state when it preserves claim/evidence identity
4. explicit operator edit or override, clearly marked as such

Do not start with freeform semantic matching across arbitrary notes.

Identity rule:
- request and artifact lookup may stay `paper_id`-first because that is the current backend/runtime identity
- when note-backed state or downstream evidence refs are used, the layer should resolve `paper_slug` explicitly instead of treating `paper_id` and `paper_slug` as interchangeable

## Storage proposal

Suggested layout:

```text
storage/method_comparisons/<comparison_id>/
  comparison.json
  comparison.csv
  comparison.md
```

Why this matches current repo better:
- the product already uses file-backed derived assets
- comparison tables are derived outputs, not source-of-truth entities
- CSV/Markdown exports become natural adjuncts without forcing a new DB model

## API proposal

Not approved for immediate implementation. If pursued, keep it bounded:

- `POST /method-comparisons/generate`
- `GET /method-comparisons`
- `GET /method-comparisons/{comparison_id}`
- `GET /method-comparisons/{comparison_id}/export.csv`

The request should be paper-centric first:
- selected `paper_ids[]`
- selected comparison fields

Do not require a global `/projects` layer as a prerequisite for phase 0.

## Integration rules

### Evidence

- every non-missing cell should carry `evidence_refs[]` unless explicitly marked operator-added
- `inferred` and `conflict` cells must stay visually distinct from `explicit`

### Meeting Pack

- meeting packs may consume method-comparison outputs later
- method comparison should not be embedded into meeting-pack storage as a hidden side format

### Personas and output modes

- reasoning persona may influence extraction lane upstream
- comparison artifacts themselves are not persona definitions
- presentation mode may change display emphasis, not cell truth

## Suggested PR sequence

1. `PR-DOC-MethodComparison-RFC`
- fix the boundary and storage model first

2. `PR-BE-MethodComparison-SchemaStore-v0`
- add file-backed comparison contract

3. `PR-BE-MethodComparison-Generate-v0`
- deterministic paper-centric generation path

4. `PR-FE-MethodComparison-Viewer-v0`
- read-first inspection surface

## Adoption gate

Do not treat the external `MethodRecord` proposal as automatically approved.

Implement only if:
- users still need repeated cross-paper method comparison
- we can keep comparison provenance explicit
- the layer stays additive to current papers/artifacts/notes rather than replacing them
