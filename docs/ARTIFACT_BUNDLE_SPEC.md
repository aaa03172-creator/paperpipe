# Artifact Bundle Spec

Status: Draft bounded spec  
Date: 2026-04-20  
Owner: Runtime/artifact maintainers  
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`

Related docs:
- `docs/ARTIFACT_BRIEF.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_SCHEMA.md`
- `docs/EXPORT_PACK_SPEC.md`
- `docs/MEETING_PACK.md`
- `docs/CHART_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/PROTOCOL_KNOWLEDGE.md`

## Purpose

Define the safest current shared contract for downstream PaperPipe/Lattice artifact bundles.

This spec exists to keep derived artifacts:
- file-backed
- lineage-visible
- reviewable
- bounded by current paper/job/artifact truth

without:
- introducing a second canonical truth store
- turning downstream bundles into a generic workspace platform
- letting review or presentation layers silently outrank evidence-linked canonical state

## Current Judgment

At the current repo stage, an `artifact bundle` is only safe when it is treated as:
- paper-scoped or run-scoped
- downstream and non-canonical by default
- explicit about lineage, readiness, freshness, and regeneration
- additive to current lane-owned schemas and stores

This spec is intentionally about the shared bundle seam across lanes.

It is not a proposal to replace:
- lane-owned bundle schemas
- current paper/job/artifact runtime truth
- lane-specific validators, renderers, or API surfaces

## Current Scope

This spec applies to bounded downstream families such as:
- `meeting_pack`
- `chart_pack`
- `method_comparison`
- `image_evidence`
- `protocol_knowledge`
- `paper_synthesis`

This spec may also guide future export-style bundles, but only when those bundles stay:
- paper-first
- derived
- clearly non-canonical

## Non-Goals

This spec does not define:
- a new runtime root object
- a generalized project/workspace platform
- a new approval engine
- a new provenance system separate from current evidence refs and lane lineage
- a mandatory folder rewrite for every current artifact lane

## 1. Bundle-Level Rules

### 1.1 Bundle ownership stays derived

An artifact bundle may summarize, frame, or export current research state.

It must not become the stronger owner than:
- current canonical structured paper state
- selected run artifacts
- named saved source artifacts in bounded downstream lanes

Current rule:
- bundle truth is always subordinate to upstream truth owners
- if the upstream owner is weak, partial, or warning-heavy, the bundle must stay weak, partial, or warning-heavy too

### 1.2 Bundle scope stays paper-first or run-first

The safest current bundle scope is:
- one paper
- one paper plus selected adjacent notes/context
- one saved run
- one bounded downstream family assembled from named paper/run sources

Current rule:
- avoid cross-project or broad workspace bundles as first-class current runtime families
- if multiple papers are combined, the bundle must still name the exact source set and keep the output reviewable

### 1.3 Bundle classification is explicit

Every bundle should classify itself with:
- `artifact_family`
- `template_kind`
- `layer`
- `canonical_status`

Current safe defaults for downstream bundles:
- `layer=user_facing_artifact` for handoff/export bundles
- `layer=compiled_knowledge` for synthesis-style bundles
- `canonical_status=non_canonical`

If a lane is actually a review/gate artifact, that should remain explicit rather than being hidden behind polished presentation.

### 1.4 Bundle review state is additive

Review artifacts such as:
- `acceptance_contract.json`
- `quality_gate.json`
- `artifact_brief_review`
- self-review or reporting outputs

may summarize readiness and risk.

They must not replace the bundle manifest as the bundle owner, and must not replace upstream evidence-linked state as scientific truth.

### 1.5 Regeneration is explicit

If a bundle can be regenerated safely, that capability must be visible.

If it cannot be regenerated safely, that limitation must also be visible.

Recommended shared vocabulary when a real lane or shared consumer needs it:
- `trace_available`
- `can_regenerate`
- lane-owned saved-request visibility, reusing current names such as `generation_request`, `has_generation_request`, or an equivalent presence flag
- lane-owned regenerate lineage, reusing current names such as `regenerated_from_pack_id` when parent-pack ancestry matters

Current rule:
- do not invent new synonyms such as `generation_request_saved` or `regenerated_from` when an active lane already has stronger names
- if regenerateability is not a real current concern for a lane, omit it rather than backfilling placeholder fields

### 1.6 Freshness and readiness stay visible

Bundles must not hide staleness or uncertain state behind polished output.

Recommended shared vocabulary:
- `freshness_state`
  - `current`
  - `stale`
  - `unknown`
- `readiness`
  - lane-owned, but should reuse a small explicit vocabulary where possible
- `warnings[]`
- `uncertainty_notes[]`

Current rule:
- not every lane must expose every trust-summary field immediately
- do not add dummy `freshness_state`, `trace_available`, or `can_regenerate` values just to make a bundle look uniform unless a real shared consumer needs them

### 1.7 Exports remain exports

Markdown, PPTX, PDF, CSV, and viewer-oriented files are bundle members.

They are not stronger owners than:
- the bundle manifest
- lane-owned structured bundle payloads
- upstream canonical state

## 2. Minimum Bundle Contract

The shared minimum contract for a derived artifact bundle is:

1. one manifest-like owner file
2. explicit member inventory
3. explicit upstream lineage
4. explicit warning/readiness/freshness summary
5. optional but explicit review/gate sidecars

### 2.1 Minimum manifest fields and optional trust summary fields

Each new bundle family should preserve or map to the following minimum fields:

```json
{
  "bundle_id": "...",
  "artifact_family": "...",
  "template_kind": "...",
  "layer": "compiled_knowledge",
  "canonical_status": "non_canonical",
  "title": "...",
  "created_at": "2026-04-20T00:00:00Z",
  "updated_at": "2026-04-20T00:00:00Z",
  "source_refs": [],
  "upstream_owners": [],
  "bundle_members": [],
  "warnings": [],
  "uncertainty_notes": [],
  "freshness_state": "unknown",
  "trace_available": false,
  "can_regenerate": "unknown"
}
```

Current notes:
- existing lane manifests do not need immediate migration if they already expose equivalent fields through lane-owned structures
- new lanes should prefer this shared vocabulary rather than inventing another naming set
- `freshness_state`, `trace_available`, and `can_regenerate` are optional trust-summary fields, not mandatory placeholders for every lane
- regenerate/request visibility should reuse current lane fields such as `generation_request`, `has_generation_request`, and `regenerated_from_pack_id` rather than introducing new shared synonyms

### 2.2 `upstream_owners`

`upstream_owners` should name the minimum upstream lineage needed to reopen trust.

Recommended owner kinds:
- `paper_state`
- `run_artifact`
- `source_artifact`
- `note_context`
- `review_gate_artifact`

Recommended fields:
- `owner_kind`
- `ref`
- `role`
  - `canonical`
  - `context_only`
  - `review_only`
- `note`

Current rule:
- `context_only` and `review_only` must never be confused with canonical scientific support

### 2.3 `bundle_members`

`bundle_members` should enumerate the saved files that make up the bundle.

Recommended fields:
- `path`
- `kind`
  - `manifest`
  - `render`
  - `data_snapshot`
  - `spec`
  - `view_state`
  - `review_gate`
  - `trace`
  - `export`
- `format`
- `role`
- `required`
- `note`

Current rule:
- the manifest-like owner file should be listed as a first-class member, not treated as invisible metadata

## 3. Recommended Bundle Layout

Current lanes already vary, so this is a recommended pattern rather than an immediate rewrite demand.

```text
storage/<artifact_family>/<bundle_id>/
  manifest.json
  artifact.md
  data/
  specs/
  review/
  exports/
  trace/
```

Recommended member roles:
- `manifest.json`
  - primary bundle-local owner and inventory surface
- `artifact.md`
  - human-readable render or summary
- `data/`
  - normalized snapshots used for rendering or handoff
- `specs/`
  - deterministic render or assembly specs
- `review/`
  - additive quality or acceptance artifacts
- `exports/`
  - handoff members such as PDF, PPTX, CSV, DOCX
- `trace/`
  - optional deterministic trace or recovery metadata

Current rule:
- do not require every lane to use every folder
- do require that saved members remain discoverable and reviewable

## 4. Relationship To `Artifact Brief`

`Artifact Brief` is a planning seam.

This spec covers the saved bundle seam.

Current rule:
- `artifact_brief` and `artifact_brief_review` may be saved inside the bundle
- they remain additive planning/review metadata only
- they do not replace the manifest or lane-owned bundle payload

## 5. Relationship To Current Active Lanes

### 5.1 Meeting Pack

`Meeting Pack` already follows much of this spec:
- saved bundle owner
- markdown sibling
- readiness/warnings
- regenerate/rerender contract
- explicit retrieval trace

Expected alignment:
- keep `generation_request`, readiness, and regenerateability visible
- continue treating note/screening/profile inputs as `context_only`

### 5.2 Chart Pack

`Chart Pack` already follows the bundle pattern well:
- bundle-local manifest
- data snapshots
- spec files
- review gate files

Expected alignment:
- keep saved source artifact lineage explicit
- keep transform reviewability visible
- avoid turning charts into a stronger truth owner than the named source artifact

### 5.3 Method Comparison and Image Evidence

These lanes should remain:
- evidence-linked or metadata-first
- explicitly bounded
- non-canonical

Expected alignment:
- carry visible `canonical_status=non_canonical`
- keep their own bundle-local owner files and export members explicit

### 5.4 Protocol Knowledge

`Protocol Knowledge` remains version-first and file-backed.

Expected alignment:
- keep protocol identity and version content separated
- treat derived drafts and attachment-derived helpers as additive, not stronger truth owners

## 6. Shared Adoption Guidance For New Lanes

Before adding a new downstream artifact family, answer these in order:

1. What is the upstream truth owner?
2. Is the new lane `compiled_knowledge`, `review_gate_artifact`, or `user_facing_artifact`?
3. What is the single manifest-like owner file?
4. Which members are required to reopen trust?
5. Which inputs are canonical versus context-only?
6. Can the bundle be regenerated deterministically?
7. What warning, freshness, and readiness cues must remain visible?

If those answers are weak or ambiguous, the lane should stay draft-only or be deferred.

## 7. Future Paper-Scoped Export Pack

This section is a future-oriented appendix, not an active runtime family.

The safest future "final package" shape for PaperPipe is still paper-scoped and non-canonical:

```text
storage/export_packs/<pack_id>/
  manifest.json
  canonical/
    state_ref.json
    claimset_ref.json
    evidence_ref_index.json
  operator/
    highlights.json
    note_blocks.md
  review/
    review_report.json
    readiness.json
  exports/
    paper_note.md
    meeting_pack.md
    chart_pack/
    talk_pack/
```

Current rule:
- this is an export-pack wrapper around upstream truth, not a new truth owner
- `canonical/` members should point to or snapshot current canonical refs, not silently fork them
- `exports/` may be wide, but the pack still remains one paper-scoped derived bundle

## 8. Verification Expectations

When a lane adopts or extends this contract:
- keep bundle members deterministic where feasible
- keep warnings and caution notes visible in both saved files and viewers
- keep lineage explicit enough that an operator can reopen upstream truth without guessing
- prefer targeted verification per lane over a new heavyweight universal validator

## Conclusion

The safest current `artifact bundle` in PaperPipe/Lattice is:
- derived
- file-backed
- lineage-visible
- warning-visible
- non-canonical by default

That is the shared contract worth standardizing.

The standardization target is not a new workspace platform.

It is the seam between current evidence-linked truth and the growing set of reviewable downstream artifact lanes.
