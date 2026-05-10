# State vs Artifact Drift Review

Status: Active review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: active bounded artifact docs vs current canonical-state/runtime storage boundaries

## Purpose

Check whether current active docs and runtime anchors still agree on this boundary:

- canonical structured state stays in paper-scoped saved state, run artifacts, runtime DB state, and `Research DNA`
- bounded artifact lanes stay derived bundles
- mirror, context, and bundle-local metadata do not silently upgrade into new truth stores

This note is not a new spec.

## Executive Call

Current repo is strongly aligned on state-vs-artifact boundaries.

Strong current center:
- `Meeting Pack`, `Chart Pack`, `Method Comparison`, `Image Evidence`, and `Protocol Knowledge` are all still documented and implemented as bounded derived bundles
- runtime store code writes each bounded lane into its own file-backed root with atomic save/rollback behavior
- current drift was wording, not implementation

The main risk was a few phrases that mixed:
- canonical inputs
- context-only inputs
- bundle-local primary files
- historical raw artifact path examples

## 1. What Is Aligned

### A. Bounded lanes are still derived bundles, not second truth stores

Repo anchors:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/MEETING_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/CHART_PACK.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/PROTOCOL_KNOWLEDGE.md`

Why this is aligned:
- active docs already say these lanes are file-backed, read-first, warning-visible, and derived from existing runtime truth
- no active spec currently promotes these bundles into global paper/run/search-state ownership

### B. Runtime storage layout keeps artifact bundles separate from canonical paper/run state

Repo anchors:
- `src/services/runtime_paths.py`
- `src/meeting_packs/store.py`
- `src/chart_packs/store.py`
- `src/method_comparisons/store.py`
- `src/image_evidence/store.py`
- `src/protocol_cards/store.py`

Why this is aligned:
- canonical run outputs stay under `storage/artifacts/<paper-segment>/<run_id>/`
- bounded lanes save into separate roots such as `storage/meeting_packs/`, `storage/chart_packs/`, `storage/method_comparisons/`, `storage/image_evidence/`, and `storage/protocol_cards/`
- store code uses atomic writes, tracked expected files, and rollback/cleanup paths instead of mutating canonical state in place

### C. Viewer/workbench docs still treat sidecar state as primary paper truth

Repo anchors:
- `docs/WEB_VIEWER.md`
- `backend/routers/paper_notes.py`

Why this is aligned:
- the viewer contract still centers `vault/.pp/<slug>/state.json` as canonical structured state for note-backed review surfaces
- notes and artifact-health summaries enrich operator review, but they do not replace saved run/claim/evidence state

## 2. Wording Drift Found

### A. `Meeting Pack` mixed canonical inputs and context-only inputs under one truth heading

Repo evidence:
- `docs/MEETING_PACK.md:207`
- `docs/MEETING_PACK.md:209`
- `docs/MEETING_PACK.md:223`

Issue:
- listing note body, screening rationale, and projected profiles under the same “input truth” heading made secondary context look co-equal with canonical paper state.

Action taken:
- split the section into:
  - canonical inputs: `state.json` and explicitly named run artifacts
  - context-only secondary inputs: notes, screening rationale, projected profiles
- added an explicit line that context does not become claim/evidence truth

### B. `Meeting Pack` checkpoint wording compressed the loading chain too much

Repo evidence:
- `docs/MEETING_PACK.md:119`
- `docs/MEETING_PACK.md:120`

Issue:
- the old wording made it look like notes/screening/profile selectors all flow into the same truth layer without preserving the canonical-vs-context distinction.

Action taken:
- changed the stable-lane wording to `selector metadata/context -> canonical paper state (+ explicit source artifacts when named) -> evidence ledger -> deterministic markdown`

### C. `WEB_VIEWER` still used an old raw artifact path example

Repo evidence:
- `docs/WEB_VIEWER.md:255`
- `src/services/runtime_paths.py`

Issue:
- the old `storage/artifacts/<paper_id>/<run_id>` example lagged behind the current path-helper contract and made artifact-health wording look more concrete than the runtime guarantee actually is.

Action taken:
- changed the wording to refer to the preferred run artifact directory under `storage/artifacts/<paper-segment>/<run_id>`

### D. `Image Evidence` used “canonical bundle metadata” without bundle-local qualification

Repo evidence:
- `docs/IMAGE_EVIDENCE.md:128`
- `src/image_evidence/store.py`

Issue:
- “canonical” there was intended to mean primary file inside the image-evidence bundle, but it could be misread as global runtime truth.

Action taken:
- changed the wording to `primary bundle-local metadata and provenance file`
- added that it does not replace canonical paper/run truth elsewhere in the runtime

## 3. Remaining Low-Risk Tension

### A. Historical raw-path examples still exist in reports and archives

Repo evidence:
- `docs/reports/Deep_Read_Structured_State_Gap_2026-03-24.md`
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/archive/...`

Current judgment:
- acceptable for now because the active specs now point to the current path-helper contract
- worth cleaning opportunistically if those reports are promoted into active guidance later

### B. Some bundle docs still use “canonical” for bundle-internal primacy

Repo evidence:
- active bounded docs in general

Current judgment:
- acceptable as long as “bundle-local” vs “global runtime truth” stays explicit
- future edits should prefer `primary bundle file`, `bundle-local metadata`, or `derived bundle contract` when possible

## 4. Current Boundary Map

### Canonical structured state

- `vault/.pp/<slug>/state.json`
- runtime DB state (`jobs`, `execution_runs`, `job_events`, `user_actions`)
- run artifacts under `storage/artifacts/<paper-segment>/<run_id>/`
- `Research DNA`

### Derived bundles

- `storage/meeting_packs/<pack_id>/`
- `storage/chart_packs/<chart_pack_id>/`
- `storage/method_comparisons/<comparison_id>/`
- `storage/image_evidence/<image_evidence_id>/`
- `storage/protocol_cards/<protocol_id>/`

### Mirror/context surfaces

- note body/frontmatter
- project/research note context
- screening rationale/context
- projected execution profiles
- viewer/debug traces

These may shape selection, framing, review, or observability, but they do not automatically upgrade into claim/evidence truth.

## 5. Recommended Guardrail Going Forward

When a bounded lane doc talks about “truth”, “canonical”, “source”, or “artifact”:

1. name the canonical paper/run/search-state owner first
2. say whether the lane writes a derived bundle or mutates canonical state
3. separate context-only inputs from structured truth inputs
4. if a file is “canonical”, say whether that only means bundle-local primacy
