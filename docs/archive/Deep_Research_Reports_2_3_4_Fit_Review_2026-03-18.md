# Deep Research Reports 2/3/4 Fit Review

Status: Historical fit review  
Date: 2026-03-18  
Owner: Runtime/design maintainers  
Scope: external deep-research visualization and microscopy reports reviewed against the current PaperPipe/Lattice runtime

Reviewed external docs:
- `/Users/jangseongjin/Downloads/deep-research-report-2.md`
- `/Users/jangseongjin/Downloads/deep-research-report-3.md`
- `/Users/jangseongjin/Downloads/deep-research-report-4.md`

Reference baseline:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/MEETING_PACK.md`
- `docs/RESEARCH_DNA.md`
- `docs/archive/Agent_Proposal_Fit_Review_2026-03-18.md`
- `docs/archive/Proposal_to_Lattice_Mapping_2026-03-18.md`

Follow-on docs created from this review:
- `docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`
- `docs/archive/Research_Data_Visualization_v0_Implementation_Plan_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_Layer_RFC_2026-03-18.md`
- `docs/archive/Image_Evidence_Viewer_v0_Implementation_Plan_2026-03-18.md`

## Executive judgment

Do not adopt these reports as a current runtime roadmap or master-spec replacement.

Do use them as:
- a product-positioning reference for local-first, provenance-heavy research tooling
- a future bounded subsystem idea pack
- a source of guardrails for chart artifacts, raw-vs-derived separation, and image-evidence provenance

Do not use them as:
- a replacement for the current paper/job/artifact model
- a reason to introduce a general experiment-data platform into the current SSOT
- a reason to choose Streamlit, Dash, napari, or OMERO as immediate runtime commitments

## What the reports get right

- They correctly separate numeric research-data visualization from microscopy/image-viewing concerns.
- They strongly reinforce current PaperPipe values:
  - local-first operation
  - provenance and evidence traceability
  - raw/derived separation
  - non-destructive downstream artifacts
  - explicit uncertainty and caution notes
- The `chart_pack` idea is directionally good when interpreted as a bounded downstream artifact rather than a new platform root.
- The microscopy proposals correctly treat image display choices, overlays, representative images, and measurements as provenance-bearing scientific operations rather than mere UI decoration.

## Why they do not fit the current repo as-is

### 1. Product-shape mismatch

The reports assume a broader research-data workspace with:
- uploaded experiment datasets
- chart/figure packs as first-class authoring surfaces
- image registries and microscopy-viewer flows
- optional project-like or dashboard-like state

Current Lattice is still centered on:
- `papers`
- deep-read `jobs`
- saved run `artifacts`
- Obsidian note state
- bounded `Research DNA`
- bounded `Meeting Pack`
- bounded `Method Comparison`

These proposals are therefore future layers, not current runtime truth.

### 2. Runtime-contract mismatch

The reports discuss:
- Streamlit/Dash app shells
- uploaded CSV/XLSX ingestion and edit flows
- chart artifact stores
- image registries, ROI stores, and viewer launch paths
- OMERO integration and napari handoff

None of those are active backend/runtime contracts today. The current live contract remains FastAPI plus file-backed paper/run/artifact outputs.

### 3. Vocabulary mismatch

The external reports use useful concepts, but they are not yet expressed in current repo vocabulary. In current Lattice terms:
- `chart_pack` would have to become a bounded downstream artifact family
- uploaded dataset registry would have to be a future sidecar, not a new canonical top-level root
- image evidence would need to be modeled as a new evidence-linked layer, not a standalone microscopy platform
- representative image selection would need to fit inside current evidence/pack lineage rules

### 4. Tool-choice prematurity

The reports compare Streamlit, Dash, Plotly, napari, and OMERO well enough as external options, but they still operate at a pre-adoption stage.

Current repo decisions should not jump from:
- no active chart/image subsystem

to:
- immediate framework commitment
- immediate runtime embedding
- immediate server-platform adoption

without a bounded spec and a narrower first slice.

### 5. Source-attribution quality limitation

These reports use deep-research `turn...` style source markers rather than durable external URLs in repo-native form.

That means they are useful as synthesis inputs, but they should not be treated as final legal, procurement, or library-selection evidence.

## Fit classification by report

### `deep-research-report-2.md`

Fit: medium as future bounded subsystem input, low as current runtime plan

Reusable:
- raw-vs-derived image separation
- view-state provenance
- representative-image provenance
- napari as local handoff target
- OMERO as optional connector rather than built-in core

Not directly reusable:
- any implication that PaperPipe should become an image-management platform in v1
- immediate browser-native microscopy viewer commitment

Recommended placement:
- future `Image Evidence Viewer` RFC input

### `deep-research-report-3.md`

Fit: medium-high as future bounded subsystem input, low as current runtime plan

Reusable:
- `chart_pack` as a downstream artifact concept
- deterministic chart rendering from structured data only
- strong provenance and transform-log requirements
- explicit anti-hallucination rules for numeric visualization

Not directly reusable:
- immediate Streamlit/Dash adoption as product architecture
- arbitrary dataset upload as a new product root

Recommended placement:
- future `Research Data Visualization` RFC input

### `deep-research-report-4.md`

Fit: high as synthesis/reference note, low as present runtime contract

Reusable:
- explicit split between numeric visualization and image/microscopy tracks
- stronger architecture framing for guardrails and storage separation
- useful adoption sequencing

Not directly reusable:
- integrated v1/v1.5/v2 roadmap as if the current repo were already a data-visualization platform

Recommended placement:
- integrated direction note feeding two separate RFC lanes

## Recommended adaptation strategy

### Keep as canonical

- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- the current bounded spec family in `docs/README.md`

### Preserve as future bounded lanes

- `Research Data Visualization / Chart Artifact`
- `Image Evidence Viewer / Microscopy Evidence`

### Explicitly do not do now

- do not introduce uploaded research datasets as a new top-level canonical runtime root
- do not add Streamlit or Dash as a new product shell by stealth
- do not treat napari or OMERO as immediate runtime dependencies
- do not redefine current Lattice around a general experiment-data workspace

## Bottom line

These reports are not wrong. They are mostly ahead of the current repo.

The right interpretation is:
- keep them as `v4 direction hypotheses`
- preserve their strongest ideas as bounded RFC inputs
- import only the parts that can fit the current paper/job/artifact architecture without collapsing product boundaries
