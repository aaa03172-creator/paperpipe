# Method Comparison v0 Implementation Plan (2026-03-18)

Status: Historical implementation plan  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`

Related docs:
- `docs/archive/Method_Comparison_Layer_RFC_2026-03-18.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/document_artifact_v2.md`
- `docs/MEETING_PACK.md`
- `docs/Lattice_v3_Master_Spec.md`

## Purpose

This document turns the `Method Comparison Layer RFC` into a concrete v0 execution plan.

The goal is not to build a broad project/method platform.

The goal is to add the smallest useful paper-centric comparison artifact that:
- reuses current claim/evidence lineage
- stays deterministic
- remains file-backed
- can be implemented in small PRs

## Current repo reality

Current repo already has:
- paper identity and note identity
- deepread run artifacts under `storage/artifacts/<paper_id>/<run_id>/`
- `claimset.resolved.json` with claim/evidence lineage
- document/table artifacts
- paper-note structured state keyed by `paper_slug`
- evidence locator contracts already reused across downstream surfaces

Current repo does not have:
- a first-class method extraction schema
- a comparison artifact family
- a dedicated method viewer
- any reason to introduce `/projects/{id}/methods` first

So v0 should start as:
- a bounded derived artifact
- generated from selected papers and selected field IDs
- read-first

## V0 fixed decisions

### 1. Request shape stays narrow

First request contract should stay close to:
- `comparison_id?`
- `title?`
- `paper_ids[]`
- `field_ids[]`

Do not start with:
- freeform project-wide memory context
- arbitrary note-body semantic search
- broad ontology editing

Identity rule:
- v0 request should stay `paper_id`-first because current backend/runtime surfaces are paper-id centric
- when the generator consumes note-backed `state.json` or emits downstream evidence refs, it should resolve `paper_slug` explicitly instead of assuming `paper_id == paper_slug`

### 2. Source priority stays deterministic

V0 source order:
1. `claimset.resolved.json`
2. `document_artifact.json` or `document_artifact_v2` direct payloads
3. paper-note `state.json` only when claim/evidence identity is preserved

Do not start with fuzzy note-body mining or ungrounded summary text.

Practical note:
- `claimset.resolved.json` is most realistic for fields that often survive into explicit claims or claim-linked evidence
- some method fields will more naturally come from document/table payloads than from claim cards

### 3. Field catalog starts from a conservative allowlist

V0 should not pretend to support every method dimension.

Start with a small allowlist such as:
- `intervention`
- `comparator`
- `duration_or_timepoint`
- `primary_readout`
- `sample_size`

Deferred until there is stronger deterministic extraction evidence:
- `model_system`
- `sample_or_population`

The exact labels may change, but the first slice should stay curated and explicit.

### 4. Comparison truth stays evidence-linked

- every non-missing cell should carry `evidence_refs[]`
- if support is weak, mark the cell `inferred` or `conflict`
- if no supported value exists, keep the cell `missing`
- do not silently promote note-only prose into `explicit`

### 5. Storage stays file-first

Suggested root:

```text
storage/method_comparisons/<comparison_id>/
  comparison.json
  comparison.csv
  comparison.md
```

## Phase 1: Schema + Field Registry + Runtime Path + Store

Purpose:
- fix the artifact contract before generation logic exists

Scope:
- `src/schemas/method_comparison.py`
- `src/services/runtime_paths.py`
  - `method_comparisons_root()`
- `src/method_comparisons/store.py`
- typed field-registry structure
- schema/store/path regression tests

Suggested schema pieces:
- `MethodComparisonRequest`
- `MethodComparison`
- `ComparisonColumn`
- `ComparisonRow`
- `ComparisonCell`
- `ComparisonSourceSummary`

Suggested cell-level fields:
- `value`
- `normalized_value?`
- `status`
  - `explicit`
  - `inferred`
  - `missing`
  - `conflict`
- `note?`
- `evidence_refs[]`

Suggested row-level identity fields:
- `paper_id`
- `paper_slug?`
- `citekey?`
- `title`
- `cells`

Evidence refs should reuse current locator conventions rather than inventing a new family.
That means the contract should stay compatible with the `paper_slug / claim_id / evidence_id / run_id / locator` shape already used in chat and meeting-pack surfaces.

Non-goals:
- generation logic
- API routes
- UI

Acceptance:
- a comparison artifact can be validated, saved, and loaded
- root path supports env override plus repo-relative fallback
- JSON/CSV/Markdown save helpers are deterministic
- no second evidence locator family is introduced

## Phase 2: Deterministic Source Loaders

Purpose:
- build a conservative paper-to-cell extraction lane

Scope:
- `src/method_comparisons/source_loader.py`
- `src/method_comparisons/evidence.py`
- deterministic field extractors for the curated v0 allowlist

Recommended first extractor subset:
- `intervention`
- `comparator`
- `primary_readout`
- `duration_or_timepoint`

Required source rules:
- prefer `claimset.resolved.json` when a field can be supported there
- use document/table payloads only when the value is directly extractable
- use note structured state only when evidence identity is preserved
- if multiple sources disagree, emit `conflict`
- if support exists but requires conservative interpretation, emit `inferred`

Non-goals:
- arbitrary LLM synthesis
- freeform note corpus search
- operator edit UI

Acceptance:
- row generation is deterministic for the same paper set and field set
- every non-missing cell either has `evidence_refs[]` or is explicitly marked unsupported in tests
- conflict and missing cases are preserved rather than normalized away
- note-backed rows resolve `paper_slug` explicitly instead of inferring it from `paper_id`

## Phase 3: Generation Service + Export Renderer

Purpose:
- turn loaded source facts into a reusable saved comparison artifact

Scope:
- `src/method_comparisons/service.py`
- `src/method_comparisons/renderer.py`
- generate `comparison.json`, `comparison.csv`, and `comparison.md`

Generation rules:
- row order should be deterministic
- column order should follow request `field_ids[]`
- evidence ordering should be deterministic
- markdown should remain read-first and evidence-aware, not polished into false certainty

Non-goals:
- spreadsheet editing
- interactive conflict resolution
- direct embedding into meeting-pack storage

Acceptance:
- one generated comparison can be rendered in JSON/CSV/Markdown from the same saved structure
- repeated generation with the same inputs produces stable ordering
- `inferred`, `conflict`, and `missing` remain visible in exported forms

## Phase 4: Thin FastAPI Surface

Purpose:
- expose the comparison artifact through the current API-first contract

Scope:
- `backend/routers/method_comparisons.py`
- `backend/main.py` router wiring
- endpoints:
  - `POST /method-comparisons/generate`
  - `GET /method-comparisons`
  - `GET /method-comparisons/{comparison_id}`
  - `GET /method-comparisons/{comparison_id}/export.csv`

Non-goals:
- full viewer route
- editing workflow
- project-scoped dependency

Acceptance:
- API layer is thin and delegates to service/store code
- response payload matches Pydantic contracts
- route regression tests pass

## Phase 5: Real-Fixture Hardening

Purpose:
- prove the lane on real or realistic paper inputs before any UI expansion

Scope:
- one or more recorded fixtures using current artifact roots
- regression coverage for:
  - explicit cells
  - missing cells
  - conflict cells
  - inferred cells
- one end-to-end saved comparison artifact example

Acceptance:
- generated artifact is inspectable and repeatable
- evidence refs survive into final outputs
- no fake support is introduced just to fill the table

## Cross-Cutting Guardrails

1. API-first
- core logic lives in schemas, service, store, and router layers
- no CLI-only comparison workflow as the primary path

2. Pydantic-first
- request/response/file contracts must live under `src/schemas/`

3. Evidence-first
- v0 comparison truth must follow `docs/Evidence_and_Uncertainty_Rules.md`
- output formatting must not loosen evidence policy

4. No alternate truth store
- method comparison is a derived artifact, not a replacement for papers, notes, or claimsets

5. No project-platform dependency
- v0 should not depend on a new `projects/documents` model

6. No hidden meeting-pack side format
- meeting packs may consume comparisons later
- comparisons should remain their own bounded artifact family

## Recommended PR Sequence

1. `PR-DOC-MethodComparison-v0-plan`
- record the execution plan and v0 allowlist

2. `PR-BE-MethodComparison-schema-store`
- add schema, field registry, runtime path, and store

3. `PR-BE-MethodComparison-source-loader`
- add deterministic evidence-aware extraction for curated fields

4. `PR-BE-MethodComparison-generation-api`
- add generation service, renderer, and thin API routes

5. `PR-QA-MethodComparison-fixture-hardening`
- add real-fixture coverage before UI work

6. `PR-FE-MethodComparison-viewer-v0`
- read-first viewer only after the artifact contract is stable

## Immediate start recommendation

The right first implementation slice is Phase 1 plus the narrowest part of Phase 2.

That means:
- schema
- field registry
- root/store
- deterministic load from current artifacts for a very small curated field set, with `claimset.resolved.json` first only where the target field is actually claim-linked

This keeps the first PR useful without opening ontology sprawl, fuzzy matching, or a new product model.
