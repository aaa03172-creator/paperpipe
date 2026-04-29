# Derived Artifact Manifest Schema

Status: Draft bounded spec
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`

Related docs:
- `docs/PAPER_SYNTHESIS.md`
- `docs/DERIVED_ARTIFACT_MANIFEST_CONFORMANCE.md`
- `docs/METHOD_COMPARISON.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/ARTIFACT_BRIEF.md`
- `docs/REVIEW_GATE_SCHEMA.md`

## Purpose

Define the safest current shared seam for derived artifact manifests.

This spec exists to keep saved derived manifests:
- file-backed
- machine-readable
- explicit about layer and canonical status
- explicit about the minimum trust-reopen path when a lane really has one

without:
- forcing every bounded lane into one universal schema
- replacing lane-owned payloads with a generic manifest wrapper
- letting polished exports outrank the saved structured owner file

## Current Judgment

At the current repo stage, a shared manifest schema is only safe as:
- a mapping target
- a vocabulary guide for new derived lanes
- a hardening reference for lanes that already expose similar fields

It is not yet safe as:
- a mandatory migration target for every active lane
- a new root object above current lane-owned schemas
- a reason to erase useful lane-specific source or readiness semantics

The strongest current implementation of this seam is:
- `paper_synthesis`

Other lanes align partially and should stay lane-owned until a real shared consumer requires more convergence.

## Current Scope

This spec applies to saved owner files for derived lanes such as:
- `paper_synthesis`
- `meeting_pack`
- `chart_pack`
- `method_comparison`
- `image_evidence`
- `protocol_card`

This spec does not apply to:
- `raw_source` bundles such as attachment uploads
- standalone review-gate sidecars
- raw memory stores
- canonical structured state

## Non-Goals

This spec does not define:
- one required filename for every manifest
- one required id field for every lane
- a new provenance family separate from current evidence/source-ref contracts
- a generic project/workspace document model
- a requirement that every lane expose `source_refs[]` immediately

## 1. Manifest Layer Rules

### 1.1 The manifest stays the lane owner

The saved manifest-like file remains the primary structured owner for a derived lane.

Current examples:
- `paper_synthesis.json`
- `meeting_pack.json`
- `chart_pack.json`
- `comparison.json`
- `image_evidence.json`
- `protocol_card.json`

Current rule:
- exports such as Markdown, CSV, PPTX, or viewer renderings stay subordinate to the saved owner file
- review-gate sidecars stay additive

### 1.2 Manifest identity stays lane-owned

Each lane keeps its own primary identity field.

Current examples:
- `synthesis_id`
- `pack_id` or `id`
- `chart_pack_id`
- `comparison_id`
- `image_evidence_id`
- `protocol_id`

Current rule:
- do not force a universal `bundle_id` field into active lanes that already have stable identifiers

### 1.3 Layer and canonical status stay explicit

Derived manifests should keep their runtime layer visible.

Recommended shared vocabulary:
- `layer`
  - `compiled_knowledge`
  - `user_facing_artifact`
- `canonical_status`
  - `non_canonical`

Current rule:
- if a saved manifest could be mistaken for promoted truth, `canonical_status=non_canonical` should stay visible
- do not hide layer classification only in app state or route logic

### 1.4 Readiness, warnings, and freshness stay literal

When a lane has trust-summary fields, they should stay explicit in the saved manifest rather than being inferred only from UI copy.

Current examples:
- `readiness`
- `warnings[]`
- `uncertainty_notes[]`
- `freshness` or `freshness_state`

Current rule:
- keep current lane names when they already exist
- do not invent new shared synonyms unless a real shared consumer needs them

### 1.5 Provenance must reopen trust, not simulate it

If a derived manifest claims evidence-linked or source-linked support, it should preserve or map to the minimum upstream lineage needed to reopen trust.

Current safe vocabulary when the lane really has it:
- `source_refs`
- `source_ref_count`
- additive summaries such as `lineage_summary`

Current rule:
- summaries remain downstream of the underlying source refs
- provenance summaries must not replace direct upstream refs when the lane already saves them

## 2. Minimum Shared Manifest Shape

Each new derived manifest family should preserve or map to:

```json
{
  "<lane_primary_id>": "...",
  "title": "...",
  "created_at": "2026-04-20T00:00:00Z",
  "updated_at": "2026-04-20T00:00:00Z",
  "layer": "compiled_knowledge",
  "canonical_status": "non_canonical",
  "warnings": []
}
```

Current notes:
- `updated_at` may be absent in some current lanes; do not backfill fake timestamps
- `warnings[]` may be absent for clean lanes, but warning-capable lanes should prefer a first-class list over hiding caution state in prose
- readiness/freshness fields are recommended only when the lane already has real semantics for them

## 3. Stronger Manifest Vocabulary For Provenance-Visible Lanes

When a lane is explicitly compiled-knowledge or evidence-linked synthesis, prefer the fuller vocabulary already proven in `paper_synthesis`.

Recommended fields:
- `artifact_family`
- `template_kind`
- `layer`
- `canonical_status`
- `readiness`
- `freshness` or `freshness_state`
- `source_refs`
- `warnings[]`
- `uncertainty_notes[]`
- optional additive `lineage_summary`

Current rule:
- new compiled-knowledge lanes should prefer this vocabulary instead of inventing adjacent names
- older lanes do not need immediate migration if their current payload already keeps the trust-reopen path explicit through lane-owned structures

## 4. `source_refs` Guidance

### 4.1 When `source_refs` belong in the manifest

Use first-class `source_refs[]` when the lane directly synthesizes or summarizes upstream state across more than one saved input class.

Current strongest example:
- `paper_synthesis`
  - `structured_state`
  - `claimset_resolved`
  - `run_meta`
  - optional `quality_gate`
  - optional `acceptance_contract`

Current rule:
- `source_refs[]` are most useful when the manifest itself is making a compiled claim about what upstream state it used

### 4.2 When lane-owned source structures are enough

Some lanes already carry sufficient lineage in lane-specific fields.

Current examples:
- `meeting_pack.source_items[]`
- `meeting_pack.evidence_refs[]`
- `chart_pack.source_items[]`
- per-chart `source_ref`
- `protocol_version.source_refs[]`
- `image_evidence.source_ref`

Current rule:
- do not duplicate those into a second manifest-level `source_refs[]` field unless a real shared consumer needs it
- preserve the stronger lane-native structure instead of flattening it prematurely

### 4.3 `lineage_summary` remains additive

If a manifest exposes a compact provenance summary, it should stay explicitly secondary to the underlying source refs.

Current example:
- `paper_synthesis.lineage_summary`

Current rule:
- `lineage_summary` is an operator convenience
- it must not become the only provenance surface

## 5. Relationship To `Artifact Brief`

`Artifact Brief` is a planning seam that may feed a derived manifest.

Current rule:
- `artifact_brief` and `artifact_brief_review` may be embedded or referenced by a lane manifest
- they do not replace the lane manifest as the owner file
- they do not replace direct source refs or evidence refs

## 6. Relationship To Review-Gate Artifacts

Review-gate files stay sibling artifacts, not manifest replacements.

Current rule:
- `acceptance_contract.json` and `quality_gate.json` remain additive sidecars
- a manifest may reference their effects through warnings, readiness, or imported source refs
- the manifest must not delegate all trust signaling to review-gate files alone

Current example:
- `paper_synthesis` may import a selected run's `quality_gate.json` and `acceptance_contract.json` as additive `source_refs`
- the synthesis manifest still derives its main trust-reopen path from structured state plus resolved evidence

## 7. Current Lane Mapping

### 7.1 Paper Synthesis

Current implementation:
- `src/schemas/paper_synthesis.py`

Current alignment:
- strongest current shared-manifest match
- explicit `artifact_family`
- explicit `template_kind`
- explicit `layer`
- explicit `canonical_status`
- explicit `source_refs`
- explicit `warnings[]` and `uncertainty_notes[]`
- additive `lineage_summary`

### 7.2 Meeting Pack

Current implementation:
- `src/schemas/meeting_pack.py`

Current alignment:
- explicit `layer`
- explicit `canonical_status`
- explicit `readiness`
- lane-native lineage via `source_items[]`, `retrieval_trace[]`, and `evidence_refs[]`
- optional planning seam via `artifact_brief`

Current caution:
- do not flatten `source_items[]` and `retrieval_trace[]` into a weaker generic provenance list unless a real shared consumer needs it

### 7.3 Chart Pack

Current implementation:
- `src/schemas/chart_pack.py`

Current alignment:
- bundle-local owner file
- warning-visible manifest
- explicit source lineage through `source_items[]`, per-chart `source_ref`, snapshot refs, and spec refs
- optional planning seam via `artifact_brief`

Current caution:
- chart provenance is artifact-linked, not just summary-linked, so preserve per-chart source structures

### 7.4 Method Comparison

Current implementation:
- `src/schemas/method_comparison.py`

Current alignment:
- explicit `layer`
- explicit `canonical_status`
- explicit `readiness`
- explicit `freshness`
- explicit `warnings[]`
- evidence-linked cells and source summary

Current caution:
- this lane currently keeps provenance at cell/source-summary level rather than a manifest-level `source_refs[]` list

### 7.5 Image Evidence

Current implementation:
- `src/schemas/image_evidence.py`

Current alignment:
- primary bundle-local owner file
- explicit raw-vs-derived separation
- explicit `source_ref`
- explicit warning list
- explicit derived-output refs and handoff refs

Current caution:
- this lane is metadata-first, not compiled-knowledge-first
- do not force `artifact_family/template_kind/source_refs[]` onto it unless a real shared consumer appears

### 7.6 Protocol Knowledge

Current implementation:
- `src/schemas/protocol_card.py`

Current alignment:
- version-first owner file plus version members
- protocol versions keep `source_refs[]`
- card identity stays separate from version content

Current caution:
- the protocol card manifest is identity/version metadata, not a compiled synthesis manifest
- preserve version-level source refs instead of flattening them into card-level convenience fields too early

## 8. Shared Adoption Guidance For New Lanes

Before introducing a new derived manifest family, answer these in order:

1. What file is the true saved owner?
2. What is the lane's real runtime layer?
3. Does the lane need explicit `artifact_family` and `template_kind`, or is it a narrower metadata-first owner?
4. What is the minimum upstream trust-reopen path?
5. Should that path live in first-class `source_refs[]`, or is lane-native source structure stronger?
6. Which warnings, readiness, or freshness fields already have real semantics?
7. Are review-gate sidecars additive siblings, or is the lane trying to outsource its trust contract?

If those answers are weak, the lane should stay more specific and lane-owned rather than being normalized into a generic manifest vocabulary.

## 9. Future Direction

If PaperPipe later wants stronger cross-lane manifest convergence, the safe next step is:
- reuse `artifact_family`, `template_kind`, `layer`, `canonical_status`, and provenance vocabulary where a real compiled-knowledge lane needs them
- keep lane-native source structures when they are richer than a generic list
- add manifest-only inspection routes before widening export or viewer contracts

The unsafe next step is:
- flattening every lane into one manifest object
- treating `source_ref_count` or `lineage_summary` as substitutes for direct provenance
- migrating metadata-first lanes into compiled-synthesis vocabulary just for symmetry
