# Chart Pack

Status: Active spec
Date: 2026-03-23
Owner: Paper notes/runtime maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Related docs:
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/Stats_Verification_Agent_Spec.md`
- `docs/document_artifact_v2.md`
- `docs/MEETING_PACK.md`
- `docs/UX_REVIEW_REPORT_chart-pack-viewer.md`
- `docs/archive/Research_Data_Visualization_Layer_RFC_2026-03-18.md`
- `docs/archive/Research_Data_Visualization_v0_Implementation_Plan_2026-03-18.md`

## Purpose

`Chart Pack` is a bounded, file-backed chart artifact family for deterministic visualization of already-saved structured research artifacts.

It exists to support fast review and downstream handoff without introducing:
- a generic dataset platform
- a dashboard/runtime shell
- a freeform chart builder
- a second truth store beside current paper/run/artifact state

The current lane is intentionally:
- artifact-first
- template-first
- deterministic
- file-backed
- read-first

## Current Implementation Status

Implemented in workspace:
- `src/schemas/chart_pack.py`
- `src/chart_packs/store.py`
- `src/chart_packs/source_loader.py`
- `src/chart_packs/service.py`
- `src/chart_packs/renderer.py`
- `src/services/runtime_paths.py::chart_packs_root()`
- `backend/routers/chart_packs.py`
- read-only frontend viewer:
  - `/chart-packs`
  - `/chart-packs/:chartPackId`
- mock and backend Playwright coverage

Currently deferred:
- generic chart-builder behavior
- arbitrary uploaded spreadsheet runtime
- inline editing
- broad render-engine expansion
- chart-driven product navigation or dataset workspace behavior

## Current Judgment

At the current repo stage, `Chart Pack` is mature enough to freeze as an active bounded spec.

That judgment is based on:
- implemented backend/API/viewer slices
- explicit source-bound lineage
- deterministic saved bundle structure
- clean fit as a downstream artifact rather than a new platform root

## Current Boundary

### 1. Request shape stays artifact-first and template-first

Current pack request is centered on:
- `chart_pack_id?`
- `title?`
- `charts[]`

Current chart request is centered on:
- `chart_id?`
- `template_id`
- `source_ref`
- `field_mappings`
- `filters[]?`
- `sort?`

Current rule:
- requests must name the source artifact explicitly
- the lane does not support freeform prompt-to-chart behavior
- raw chart grammar passthrough is not part of the current contract

### 2. Source adapters stay narrow and deterministic

Current supported source kinds:
- `stats_report`
- `document_table`

Current rule:
- chart generation loads only the named source artifact family through typed adapters
- note prose, claim text mining, and broad numeric synthesis are out of scope
- `method_comparison` is not yet a first-class chart source in the active contract

### 3. Template support stays curated

Current template allowlist:
- `stats_check_status_counts`
- `reported_vs_computed_p_scatter`
- `table_numeric_bar`
- `table_numeric_line`

Current rule:
- `Chart Pack` does not expose a generic chart grammar
- adding a new template requires a new deterministic source/field mapping path, not just a new UI control

### 4. Data shaping must remain reviewable

Current transform family:
- `field_mapping`
- `filter`
- `sort`
- `coerce_numeric`

Current rule:
- each chart persists the normalized tabular snapshot it rendered from
- transform steps remain explicit in saved artifacts and the viewer
- silent imputation, silent unit conversion, or hidden statistical inference are out of scope

### 5. Output truth stays source-bounded

Current rule:
- charts must not imply stronger truth than the source artifact they use
- warnings and caution notes remain first-class parts of the pack contract
- rendered output is derived output, not canonical truth
- a sparse or warning-heavy chart should stay caution-heavy rather than being polished into certainty

### 6. Storage stays file-backed

Current storage root:

```text
storage/chart_packs/<chart_pack_id>/
  chart_pack.json
  chart_pack.md
  data/
    <chart_id>.csv
  specs/
    <chart_id>.json
```

Current rule:
- `data/<chart_id>.csv` is the normalized tabular snapshot
- `specs/<chart_id>.json` is the deterministic render spec
- render files may exist later, but they are optional derived outputs rather than the primary bundle contract

### 7. API stays thin

Current API surface:
- `POST /chart-packs/generate`
- `GET /chart-packs`
- `GET /chart-packs/{chart_pack_id}`
- `GET /chart-packs/{chart_pack_id}/charts/{chart_id}/data.csv`
- `GET /chart-packs/{chart_pack_id}/charts/{chart_id}/spec.json`

Current rule:
- API remains a thin wrapper over schema/service/store code
- export routes remain attachment-backed handoff surfaces
- the API is not a live chart-editing contract

### 8. Viewer stays read-only

Current viewer surface:
- `/chart-packs`
- `/chart-packs/:chartPackId`

Current rule:
- viewer is for artifact QA, not chart authoring
- chart cards must keep warning state, source refs, transform steps, and export actions visible together
- the viewer should remain metadata-first rather than becoming a plotting tool

## Current Non-Goals

The current spec does not include:
- freeform chart authoring
- notebook-style plotting
- arbitrary dataframe workspace behavior
- direct plot editing in the browser
- promotion of rendered charts into scientific truth
- replacing `Meeting Pack` or `Stats Verification` with a generic visualization platform

## Relationship To Other Bounded Lanes

- `Chart Pack` may feed `Meeting Pack` later as a downstream presentation-oriented artifact, but it must not become a hidden second truth store inside meeting-pack storage.
- `Method Comparison` remains a separate evidence-linked comparison artifact; it should not be forced into numeric backbone duty unless a later bounded extension proves that need.
- `Image Evidence` remains a separate metadata-first sidecar and should not be folded into chart-pack render semantics.

## Verification Expectations

Current verification lanes should remain:
- targeted pytest coverage for schema/store/source-loader/service/API
- backend Playwright smoke for generated chart-pack viewer/export flow
- mock Playwright coverage for the read-only viewer

When this spec changes:
- keep `chart_pack.json`, markdown, CSV snapshots, and spec JSON deterministic
- keep warnings and caution notes visible in both saved artifacts and the viewer
- avoid widening source semantics without updating both tests and the bounded spec

## Conclusion

`Chart Pack` is now an active bounded spec because the lane is implemented, deterministic, and clearly bounded as a downstream artifact family.

The next changes in this area should harden or extend this artifact family.

They should not reopen the broader question of whether Lattice should become a generic visualization or dataset platform.
