# Chart Pack Figure Lane Fit Review

Status: Review note
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/CHART_PACK.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_SCHEMA.md`

## Executive Summary

Current judgment:
- `Chart Pack` is a real generated artifact lane
- it now includes deterministic SVG render persistence for the current template allowlist
- it is still not a full figure lane
- it is best understood as a deterministic `chart-spec/data bundle lane`

Recommended direction:
- do not reposition `Chart Pack` as a generic figure system
- keep it chart-pack-first and source-artifact-driven
- if we extend it, do so only as a bounded `rendered chart artifact` slice over the current template allowlist

Reason:
- this keeps PaperPipe paper-first and evidence-linked
- it avoids manuscript-first feature drift
- it preserves the current artifact discipline instead of introducing a visualization workspace

## What Chart Pack Actually Is Today

Current runtime evidence shows:
- chart generation exists via `POST /chart-packs/generate`
- the service builds deterministic data snapshots and chart specs from named saved artifacts
- the saved bundle currently centers on:
  - `chart_pack.json`
  - `chart_pack.md`
  - `data/<chart_id>.csv`
  - `specs/<chart_id>.json`
  - `renders/<chart_id>.svg`
  - additive `acceptance_contract.json`
  - additive `quality_gate.json`

Current code evidence:
- request and chart-template boundaries: `src/schemas/chart_pack.py`
- generation path: `src/chart_packs/service.py`
- saved bundle members: `src/chart_packs/store.py`
- CSV/spec rendering: `src/chart_packs/renderer.py`
- API surface: `backend/routers/chart_packs.py`
- viewer behavior: `frontend/src/app/pages/ChartPackPage.tsx`

## Why It Is Still Not A Full Figure Lane

The current lane now includes rendered SVG output, but it still stops short of a broader figure system.

Confirmed gaps:
- the service now populates `render_refs` for deterministic SVG renders only
- the store now persists `renders/<chart_id>.svg` and supports save/load for SVG render files
- the API now exports `render.svg`, but not `render.png`
- the viewer shows spec summary, warning state, transforms, CSV preview, and downloads, but not an actual chart render

Important nuance:
- the schema had already allowed `render_refs[]`
- the runtime now activates a narrow SVG-first version of that contract
- rendered files remain subordinate to CSV/spec siblings and upstream source artifacts
- the lane still does not provide manuscript-style figure composition, figure QA manifests, or a rendering-first viewer

## Fit With PaperPipe Identity

This current shape fits PaperPipe better than a broad figure system would.

Why it fits:
- it starts from already-saved structured artifacts rather than freeform prompting
- it keeps the artifact bounded and reviewable
- it preserves upstream truth ownership in saved stats/table artifacts
- it exposes transforms and warnings instead of hiding them behind polished visuals

Why a broader figure lane would be risky right now:
- it could shift the product toward manuscript/presentation packaging
- it could encourage prompt-to-figure behavior instead of evidence-linked rendering
- it could create a second quasi-canonical interpretation surface if chart polish outruns source review

## Recommended Direction

### 1. Keep the identity narrow

Recommended positioning:
- `Chart Pack` remains a bounded chart artifact family
- not a general figure builder
- not a manuscript figure composer
- not a visual abstract or graphical abstract lane

### 2. If extended, extend only to rendered chart artifacts

The next safe slice is:
- current named source artifact
- current curated template
- current deterministic spec
- plus rendered chart files as additional bundle members

That means:
- no new source semantics
- no freeform figure grammar
- no multi-panel manuscript figure composition
- no chart authoring workspace

### 3. Prefer SVG-first renders

Recommended render priority:
1. `render_svg`
2. optional `render_png`

Reason:
- SVG is reviewable, diffable, and deterministic
- PNG can remain a convenience export
- SVG-first keeps the lane closer to artifact inspection than presentation polish

### 4. Keep renders subordinate to spec and source data

If render files are added, the ownership order should remain:
1. upstream saved source artifact
2. `chart_pack.json`
3. `data/*.csv`
4. `specs/*.json`
5. `renders/*`

Current rule to preserve:
- render files are derived outputs
- spec and normalized data remain the reopen-trust surface
- a render should never be the only thing a downstream consumer can inspect

## Smallest Safe Extension Slice

If we choose to add rendered outputs, the safest bounded contract is:

### Inputs
- unchanged `ChartPackRequest`
- unchanged template allowlist
- unchanged `source_ref`
- unchanged transform family

### New derived outputs
- `renders/<chart_id>.svg`
- optional `renders/<chart_id>.png`

### Manifest/schema behavior
- populate `charts[].render_refs[]` only when files are actually written
- keep `data_snapshot_ref` and `spec_ref` mandatory for render-capable charts
- do not add render refs without the underlying CSV/spec siblings

### API additions
- `GET /chart-packs/{chart_pack_id}/charts/{chart_id}/render.svg`
- optional `GET /chart-packs/{chart_pack_id}/charts/{chart_id}/render.png`

### Viewer additions
- render preview stays below warning/source/spec metadata
- CSV/spec export actions remain visible
- warning and caution surfaces remain visible even when the rendered chart looks clean

### Quality gate additions
- optional check such as `render_refs_complete`
- this should stay additive
- lack of a render file should not silently downgrade the trust surface of the bundle itself

## What Not To Do

Avoid these moves in the next slice:
- do not add prompt-to-chart generation
- do not add arbitrary spreadsheet upload support
- do not make the viewer a chart builder
- do not add manuscript-first figure numbering/captioning workflow
- do not add multi-panel figure composition yet
- do not market this lane as a full figure system before rendered files, export routes, and preview actually exist

## PR-Sized Next Actions

1. Add rendered preview to the viewer while keeping source lineage, warnings, CSV export, and spec export first-class.
2. Decide whether a bounded PNG convenience export is actually needed, rather than assuming it.
3. Add an additive render-completeness check only if downstream consumers start depending on `render_refs[]`.

## Bottom Line

`Chart Pack` is worth keeping and hardening.

It is already a useful downstream chart artifact lane.

It is not yet a true figure lane.

The right next move is not “build figures” in the broad sense.

The right next move is:
- `chart-spec/data bundle`
- plus a small deterministic render step
- without changing the lane into a generic visualization or manuscript workflow system
