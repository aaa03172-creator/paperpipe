# Export Pack Spec

Status: Draft future seam
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_SCHEMA.md`
- `docs/REVIEW_GATE_SCHEMA.md`

Related docs:
- `docs/PAPER_SYNTHESIS.md`
- `docs/MEETING_PACK.md`
- `docs/CHART_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/TALK_PACK.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`
- `docs/TALK_PACK_STYLE_GUIDE.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`

## Purpose

Define the safest future shared seam for paper-scoped export packs.

An export pack is the bounded final handoff bundle that may collect:
- selected canonical references
- selected review summaries
- selected derived artifact exports
- operator-facing review notes

without:
- becoming a new truth owner
- turning PaperPipe into a project/file-management platform
- flattening current lane-specific provenance into one polished presentation blob

## Current Judgment

At the current repo stage, an export pack is only safe as:
- a future paper-scoped derived bundle
- a packaging seam above existing saved artifacts
- a reviewable handoff object for sharing, briefing, or downstream reuse

It is not yet safe as:
- an active runtime family with broad lifecycle rules
- a generalized workspace folder tree
- a replacement for lane manifests, review gates, or canonical paper state

Current status:
- no active `export_pack` runtime family exists yet
- this spec is a bounded design target for future implementation

## Current Scope

The safe current scope is:
- one paper
- one selected canonical state snapshot
- zero or more selected saved downstream artifacts for that same paper
- optional additive review and operator sidecars

Safe current examples of included members:
- `paper_synthesis.md`
- `meeting_pack.md`
- chart-pack bundle members needed for review or export
- protocol or image-evidence references when they are explicitly included as context

## Non-Goals

This spec does not define:
- multi-paper project packages
- generalized report builders
- a new review engine
- a cross-lane promotion framework
- a requirement to duplicate every saved artifact into one folder tree

## 1. Export-Pack Layer Rules

### 1.1 Export packs stay downstream and non-canonical

An export pack is a `user_facing_artifact`.

Current rule:
- it must carry `canonical_status=non_canonical`
- it must not silently outrank canonical structured state, selected run artifacts, or lane-owned manifests

### 1.2 Export packs stay paper-scoped

The safe default identity is one paper.

Current rule:
- use one paper as the trust boundary
- do not widen the pack into a cross-project workspace bundle
- if a pack later includes cross-paper context, that context must stay explicitly secondary

### 1.3 Export packs package saved artifacts; they do not replace them

Current rule:
- the pack should reference or include saved outputs from existing bounded lanes
- it should not redefine their semantics
- it should not downcast a richer lane-native manifest into an opaque attachment list

### 1.4 Export packs keep the trust-reopen path visible

An export pack may be presentation-friendly.

It must still preserve the minimum route back to:
- canonical paper state
- selected run artifacts when relevant
- selected derived manifest owners
- additive review-gate artifacts when they materially affect readiness

Current rule:
- if the pack includes a polished export, it must still name the stronger upstream owner

## 2. Minimum Export-Pack Contract

The shared minimum contract for a future export pack is:

1. one manifest-like owner file
2. one paper-scoped identity
3. explicit upstream owners
4. explicit exported members
5. explicit warnings/readiness summary
6. optional additive review and operator sidecars

### 2.1 Minimum manifest shape

```json
{
  "export_pack_id": "...",
  "paper_slug": "...",
  "title": "...",
  "created_at": "2026-04-20T00:00:00Z",
  "updated_at": "2026-04-20T00:00:00Z",
  "layer": "user_facing_artifact",
  "canonical_status": "non_canonical",
  "export_kind": "paper_briefing_pack",
  "upstream_owners": [],
  "exports": [],
  "warnings": [],
  "uncertainty_notes": []
}
```

Recommended notes:
- `export_kind` is safer than a generic `template_kind` when the pack is specifically about a final handoff package
- if a future implementation prefers `template_kind`, keep the meaning tight and explicit rather than using both fields loosely
- `updated_at` should reflect pack refresh time only when the pack is actually rewritten

### 2.2 `upstream_owners`

`upstream_owners[]` should identify the stronger artifacts or state behind the pack.

Recommended owner kinds:
- `paper_state`
- `run_artifact`
- `derived_manifest`
- `review_gate_artifact`
- `context_artifact`

Recommended fields:
- `owner_kind`
- `ref`
- `role`
  - `canonical`
  - `derived`
  - `review_only`
  - `context_only`
- `note`

Current rule:
- the pack must preserve the distinction between canonical, derived, review-only, and context-only inputs

### 2.3 `exports`

`exports[]` should enumerate the actual handoff members in the pack.

Recommended fields:
- `path`
- `kind`
  - `markdown_export`
  - `csv_export`
  - `pptx_export`
  - `json_manifest`
  - `review_sidecar`
  - `operator_sidecar`
  - `reference_index`
- `source_owner_kind`
- `source_owner_ref`
- `required`
- `note`

Current rule:
- exported members should be traceable back to a stronger saved owner
- if a member is regenerated from another saved artifact, the source owner should remain visible

## 3. Recommended Layout

This is a future recommended pattern, not an active rewrite demand.

```text
storage/export_packs/<export_pack_id>/
  export_pack.json
  canonical/
    state_ref.json
    claimset_ref.json
    run_meta_ref.json
  review/
    quality_gate_ref.json
    acceptance_contract_ref.json
  operator/
    review_feedback_refs.json
    generation_outcome_refs.json
  exports/
    paper_synthesis.md
    meeting_pack.md
    chart_pack/
  references/
    source_index.json
```

Current rule:
- `canonical/`, `review/`, and `operator/` entries may be ref-style summaries rather than full copies
- do not duplicate large saved artifacts without a real transport or portability need
- copied exports are acceptable only when the pack is intentionally being materialized as a shareable handoff bundle

## 4. Relationship To Current Runtime Logs

Current runtime already has operator-sidecar logs such as:
- `ArtifactReviewFeedbackCase`
- `ArtifactGenerationOutcome`

Current rule:
- these are additive operator history signals
- they should not become the primary owner of an export pack
- if included, include them as references or small summaries, not as replacement truth

## 5. Relationship To Current Active Lanes

### 5.1 Paper Synthesis

`Paper Synthesis` is the strongest current export-pack candidate for a compiled summary member.

Current role in a future pack:
- summary-oriented compiled export
- provenance-visible synthesis member

### 5.2 Meeting Pack

`Meeting Pack` is the strongest current downstream artifact lane for a presentation-ready member.

Current role in a future pack:
- meeting-ready draft member
- optional discussion/review handoff member

### 5.3 Chart Pack

`Chart Pack` is a structured chart/export lane.

Current role in a future pack:
- figure/data appendix member
- reviewable chart sub-bundle when a briefing or submission handoff needs it

### 5.4 Method Comparison

`Method Comparison` is a bounded comparison appendix.

Current role in a future pack:
- comparison table appendix
- optional structured comparison export

### 5.5 Image Evidence and Protocol Knowledge

These lanes remain context-heavy bounded references.

Current role in a future pack:
- include only when explicitly needed
- keep them as referenced sidecars or bounded appendix members
- do not let them silently become the narrative center of the pack

## 6. Readiness And Warning Rules

An export pack should expose:
- `warnings[]`
- optional `uncertainty_notes[]`
- a compact pack-level readiness summary only when it can be derived from selected members without inventing new semantics

Current rule:
- pack readiness must remain downstream of selected member readiness
- if any included member is warning-heavy or review-only, the pack must stay warning-heavy or review-only too

## 7. Shared Adoption Guidance

Before introducing an export pack runtime, answer these in order:

1. What paper is the pack anchored to?
2. What are the stronger upstream owners?
3. Which members are copied exports versus reference-only summaries?
4. What warning or review-only state must remain visible at pack level?
5. Does the pack need operator-sidecar references?
6. Can the pack be regenerated deterministically from saved owners?
7. Is the pack helping a real handoff flow, or just creating a prettier duplicate folder?

If those answers are weak, do not introduce the pack yet.

## 8. Future Direction

The safe next step is:
- implement manifest-first export-pack packaging for one paper
- reuse existing saved artifacts and sidecars
- keep exported members explicitly traceable to stronger owners

The unsafe next step is:
- promoting export packs into a new workspace root
- using the pack manifest as a replacement for canonical paper state
- hiding review-only or warning-heavy inputs behind polished packaging
