# Research Data Visualization v0 Implementation Plan (2026-03-18)

Status: Historical implementation plan  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`

Related docs:
- `docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/document_artifact_v2.md`
- `docs/Stats_Verification_Agent_Spec.md`
- `docs/MEETING_PACK.md`
- `docs/archive/Method_Comparison_v0_Implementation_Plan_2026-03-18.md`
- `docs/Lattice_v3_Master_Spec.md`

## Purpose

This document turns the `Research Data Visualization Layer RFC` into a concrete v0 execution plan.

The goal is not to build a generic data app, dashboard shell, or dataset platform.

The goal is to add the smallest useful chart-artifact lane that:
- reuses current saved artifacts
- stays deterministic
- preserves provenance and uncertainty
- remains file-backed
- can later feed downstream prep surfaces such as `Meeting Pack`

## Current repo reality

Current repo already has:
- `document_artifact_v2` tables
- `stats_report.json`
- file-backed `method_comparison` artifacts
- `Meeting Pack` as a downstream derived artifact pattern
- evidence and uncertainty rules that already distinguish grounded output from unsupported synthesis

Current repo does not have:
- a general dataset registry
- a broad dataframe transformation workspace
- a chart-builder UI
- a dashboard/runtime shell that should become product architecture

Important current constraint:
- `method_comparison` exists, but the current v0 field set is mostly text-centric rather than numerically rich
- therefore the visualization lane should not force `method_comparison` to become the first numeric backbone

So v0 should start as:
- a bounded derived artifact family
- generated from explicit saved artifacts
- read-first

## V0 fixed decisions

### 1. Request shape stays artifact-first and template-first

First request contract should stay close to:
- `chart_pack_id?`
- `title?`
- `charts[]`

Each chart request should stay close to:
- `chart_id?`
- `source_kind`
  - `stats_report`
  - `document_table`
  - later `method_comparison`
- `source_ref`
- `template_id`
- `field_mappings`
- `filters[]?`
- `sort?`

Do not start with:
- uploaded arbitrary spreadsheets as a new runtime root
- raw Plotly spec passthrough
- freeform prompt-to-chart synthesis
- implicit source discovery from note prose

### 2. Source adapters stay deterministic and explicit

V0 should not guess where data came from.

The request should name the source artifact explicitly, and the runtime should load only that artifact family through typed adapters.

Recommended first adapter subset:
1. `stats_report`
2. `document_artifact.tables`

Deferred:
- `method_comparison` as a chartable numeric source until there is a stable numeric field subset worth plotting

Do not start with:
- note-body scraping
- claim text mining
- LLM-generated numeric tables

### 3. Template catalog starts from a conservative allowlist

V0 should not expose a generic chart grammar.

Start with a curated template set such as:
- `stats_check_status_counts`
- `reported_vs_computed_p_scatter`
- `table_numeric_bar`
- `table_numeric_line`

Deferred:
- multi-axis exploratory chart builders
- broad faceting systems
- notebook-like plotting freedom

The exact template labels may change, but the first slice should stay curated and explicit.

### 4. Data shaping stays reviewable

Every chart should persist:
- the normalized tabular snapshot it rendered from
- the transform ledger used to produce that snapshot
- caution notes for weak, sparse, missing, or non-numeric source data

Allowed v0 transforms should stay narrow, for example:
- column selection
- row filtering
- stable sorting
- explicit numeric coercion only when the source value is already numeric-like and the coercion rule is recorded

Do not allow:
- silent imputation
- silent unit conversion
- statistical inference or smoothing by default

### 5. Output truth stays source-bounded

- chart packs must not imply stronger truth than the source artifact they use
- warnings remain visible in `chart_pack.json` and `chart_pack.md`
- any render image is derived output, not canonical truth
- a chart built from low-confidence or sparse input stays caution-heavy rather than polished into certainty

### 6. Storage stays file-first

Suggested root:

```text
storage/chart_packs/<chart_pack_id>/
  chart_pack.json
  chart_pack.md
  data/
    <chart_id>.csv
  specs/
    <chart_id>.json
  renders/
    <chart_id>.png
```

Notes:
- `data/<chart_id>.csv` is the normalized tabular snapshot used for rendering
- `specs/<chart_id>.json` is the deterministic render spec
- `renders/<chart_id>.png` is optional derived output, not required for phase 1

## Phase 1: Schema + Template Registry + Runtime Path + Store

Purpose:
- fix the artifact contract before any renderer logic exists

Scope:
- `src/schemas/chart_pack.py`
- `src/services/runtime_paths.py`
  - `chart_packs_root()`
- `src/chart_packs/store.py`
- typed template-registry structure
- schema/store/path regression tests

Suggested schema pieces:
- `ChartPackRequest`
- `ChartPack`
- `ChartPackSummary`
- `ChartDefinition`
- `ChartSourceRef`
- `ChartFieldMapping`
- `ChartTransform`
- `ChartWarning`
- `ChartOutputRef`

Suggested chart-level fields:
- `chart_id`
- `title`
- `template_id`
- `source_ref`
- `field_mappings`
- `warnings[]`
- `data_snapshot_ref`
- `spec_ref`
- `render_refs[]`

Suggested pack-level fields:
- `chart_pack_id`
- `title`
- `charts[]`
- `source_items[]`
- `generation_request`
- `render_env`
- `caution_notes[]`

Acceptance:
- a chart-pack artifact can be validated, saved, and loaded
- root path supports env override plus repo-relative fallback
- save/load helpers are deterministic
- no current runtime truth store is replaced

## Phase 2: Deterministic Source Adapters

Purpose:
- build conservative artifact-to-tabular adapters

Scope:
- `src/chart_packs/source_loader.py`
- `src/chart_packs/adapters/stats_report.py`
- `src/chart_packs/adapters/document_table.py`
- deterministic normalization of source rows/columns into a chartable table snapshot

Recommended first adapter subset:
- `stats_report`
  - status counts
  - reported vs computed `p` pairs when directly present
- `document_table`
  - explicitly selected numeric columns from saved tables

Deferred:
- `method_comparison` adapter
- broad claim/evidence-to-chart synthesis

Required source rules:
- source artifacts must be named explicitly in the request
- adapters may normalize shape, but may not invent missing numbers
- non-numeric or sparse input must surface warnings instead of silent cleanup
- row and column ordering must be deterministic

Acceptance:
- the same source ref produces the same normalized snapshot
- warnings for sparse, missing, or mixed-type data remain explicit
- adapter output is stable enough to rerender later without rereading notes

## Phase 3: Deterministic Render Spec + Bundle Service

Purpose:
- turn normalized snapshot data into a reusable saved chart artifact bundle

Scope:
- `src/chart_packs/service.py`
- `src/chart_packs/renderer.py`
- template-specific spec builders
- bundle generation for:
  - `chart_pack.json`
  - `chart_pack.md`
  - `data/<chart_id>.csv`
  - `specs/<chart_id>.json`

Generation rules:
- chart ordering follows request order
- render spec ordering is deterministic
- markdown stays review-first and caution-aware
- image exports remain optional derived outputs

Non-goals:
- interactive chart editing
- dashboard assembly
- automatic narrative interpretation of figures

Acceptance:
- one saved pack can be reloaded and audited without touching the original note layer
- repeated generation with the same request produces stable specs and snapshots
- `chart_pack.md` shows source refs, transforms, and warnings clearly

## Phase 4: Thin FastAPI Surface

Purpose:
- expose the chart-pack artifact through the current API-first contract

Scope:
- `backend/routers/chart_packs.py`
- `backend/main.py` router wiring
- endpoints:
  - `POST /chart-packs/generate`
  - `GET /chart-packs`
  - `GET /chart-packs/{chart_pack_id}`
  - `GET /chart-packs/{chart_pack_id}/charts/{chart_id}/data.csv`
  - `GET /chart-packs/{chart_pack_id}/charts/{chart_id}/spec.json`

Non-goals:
- viewer page
- editing workflow
- project-scoped workspace root

Acceptance:
- API layer stays thin and delegates to service/store code
- response payload matches Pydantic contracts
- export endpoints return saved artifact outputs, not live recomputation

## Phase 5: Real-Fixture Hardening

Purpose:
- prove the lane on realistic saved artifacts before any UI expansion

Scope:
- recorded fixtures for:
  - one `stats_report` chart-pack case
  - one numeric `document_table` chart-pack case
- regression coverage for:
  - deterministic snapshot generation
  - warnings on sparse/non-numeric input
  - stable export paths

Non-goals:
- large-scale visual QA
- broad chart template coverage

Acceptance:
- saved packs reproduce deterministically from recorded fixtures
- warning-heavy cases do not collapse into falsely clean charts

## Phase 6: Optional Read Surface

Purpose:
- only after bundle and API contracts are stable, add a lightweight read surface

Scope:
- saved pack index
- detail page with:
  - chart metadata
  - source refs
  - warnings
  - snapshot/spec download

Non-goals:
- dashboard builder
- arbitrary drag-and-drop figure authoring

Acceptance:
- reader can inspect source lineage and warning state before trusting a figure

## Suggested PR sequence

### PR-DOC-BE-ChartPack-v0

Scope:
- implementation-plan doc
- schema contract
- runtime path
- store
- tests

### PR-BE-ChartPack-Adapters-v0

Scope:
- `stats_report` adapter
- `document_table` adapter
- normalization tests

### PR-BE-ChartPack-Generate-v0

Scope:
- service
- renderer/spec builder
- bundle save
- markdown rendering

### PR-BE-ChartPack-API-v0

Scope:
- thin FastAPI routes
- response models
- export endpoints

### PR-QA-ChartPack-Fixtures-v0

Scope:
- recorded fixtures
- deterministic regression coverage

## Explicitly out of scope

- dataset upload as a new top-level workflow
- user-managed dataframe workspace
- broad chart editor
- dashboard shell commitment
- automatic statistical storytelling
- silent smoothing, interpolation, or unit repair
- replacing `Meeting Pack` with a figure-first presentation system

## Bottom line

The safe first implementation is:
- `chart_pack` as a bounded, deterministic, file-backed artifact family over existing saved artifacts

The unsafe first implementation would be:
- a new general data workspace
- a chart builder with open-ended semantics
- a stealth architecture pivot into Streamlit, Dash, or another dashboard product shell
