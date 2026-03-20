# Research Data Visualization Layer RFC

Status: Future RFC  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/Product_Positioning_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/MEETING_PACK.md`
- `docs/archive/Deep_Research_Reports_2_3_4_Fit_Review_2026-03-18.md`
- `docs/archive/Research_Data_Visualization_v0_Implementation_Plan_2026-03-18.md`

## Purpose

Define a bounded future lane for evidence-linked research-data visualization without turning current Lattice into a general experiment-data platform.

This RFC exists to preserve the strongest parts of the visualization proposals:
- deterministic chart generation from structured data
- provenance-first chart artifacts
- explicit anti-hallucination guardrails
- downstream reuse in meeting/prep surfaces

## Current judgment

This is a valid future bounded layer, but not a current runtime contract.

If adopted, it should begin as:
- a file-backed derived artifact family
- tightly scoped to structured inputs
- explicitly downstream from current source/evidence state

It should not begin as:
- a new top-level workspace product
- a generic dataset-management platform
- a dashboard suite with broad authoring semantics

## Problem statement

Today the repo can produce:
- papers
- claim/evidence state
- meeting packs
- method comparisons

But it does not yet provide a bounded visualization artifact for:
- lab-meeting-ready charts
- project-update figures
- QC-oriented structured plots
- paper-linked numeric figure summaries

That gap is real, but it should be solved as an artifact layer, not as a product rewrite.

## Design goals

- keep numeric visualization deterministic and reviewable
- preserve source/data lineage
- store visualization outputs as reusable artifacts, not ephemeral screenshots
- keep uncertainty and caution notes visible
- allow later handoff into `Meeting Pack` or other downstream surfaces

## Non-goals

- no broad experiment-data LIMS replacement
- no arbitrary AI-generated numeric arrays or chart traces
- no silent imputation, unit conversion, or statistical inference by default
- no immediate Streamlit/Dash product-shell commitment
- no current-user-facing multi-user dashboard platform

## Fit with current Lattice

Closest current analogs:
- `Meeting Pack` as a downstream presentation artifact
- `Method Comparison` as a bounded derived artifact

Therefore the likely shape is:
- `chart_pack` or `figure_pack` as a bounded artifact family
- stored separately from current ingest/read/verify artifacts
- consumable by downstream presentation surfaces

## Proposed v0 boundary

### Inputs

Prefer current repo-native structured inputs first:
- `document_artifact.tables`
- `stats_report`
- `method_comparison`
- future explicitly registered tabular sidecar datasets

Do not start with:
- unrestricted user-uploaded arbitrary spreadsheets as a new canonical runtime root

### Outputs

Store a bounded bundle such as:
- `storage/chart_packs/<chart_pack_id>/chart_pack.json`
- `storage/chart_packs/<chart_pack_id>/chart_pack.md`
- `storage/chart_packs/<chart_pack_id>/export.png` or `.svg` when explicitly rendered

### Core model

Minimum future contract should include:
- `chart_pack_id`
- `title`
- `chart_type`
- `source_items[]`
- `data_fields_used`
- `filters[]`
- `transforms[]`
- `figure_spec`
- `render_env`
- `caution_notes[]`

## Guardrails

- LLM may suggest mappings or flag problems, but may not generate numeric series as truth input.
- Chart rendering must come from deterministic code paths over structured data.
- Missing values stay missing unless an explicit operator-approved transform says otherwise.
- Unit conversion must not happen silently.
- Version metadata for the rendering stack must be persisted.
- Outputs must preserve enough provenance to rerender or audit the figure later.

## Storage and runtime bias

The external reports suggest SQLite + Parquet + optional DuckDB. That is reasonable as subsystem design input, but not yet a current runtime commitment.

Current recommendation:
- treat those as implementation options inside the future bounded layer
- do not elevate them into top-level product architecture yet

## UI / framework stance

The external reports discuss Streamlit and Dash. Current recommendation:
- keep framework choice out of the v0 concept boundary
- define the data contract and storage contract first
- choose a UI shell only when the actual first slice is approved

## Integration points

### With Meeting Pack

- `Meeting Pack` may consume chart packs later as presentation-oriented downstream artifacts.
- chart packs must not become a hidden second canonical truth store inside meeting-pack storage.

### With paper and evidence state

- chart packs should reference source paper/artifact identities explicitly.
- chart packs should not pretend a plotted value is stronger than the structured source it came from.

## Suggested first slice

If this lane is reopened, the smallest current-system-safe slice is:
- file-backed chart-pack schema
- deterministic renderer over current structured artifacts only
- no arbitrary upload flow
- no statistical auto-interpretation
- no framework lock-in

## Adoption gate

Promote this RFC only if all are true:
- there is repeated operator demand for reusable numeric figures
- the source tables are already structured enough to avoid ad hoc cleanup chaos
- the first slice can stay artifact-first rather than platform-first

## Bottom line

This should become:
- a bounded visualization artifact layer

It should not become:
- a new product root
- a generic data-app platform
