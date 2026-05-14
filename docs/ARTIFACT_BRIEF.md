# Artifact Brief

Status: Active bounded contract  
Date: 2026-04-17  
Owner: Runtime/artifact maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

## Purpose

`Artifact Brief` is a small planning contract for downstream artifacts.

It exists to separate:
- source context
- communicative intent
- planned deliverable items
- pre-render review warnings

without:
- creating a second canonical truth store
- turning artifact planning into a new agent platform
- letting presentation logic silently override evidence rules

## Current Scope

The current active uses are:
- `Meeting Pack`
- `Chart Pack`

Current runtime behavior:
- canonical scientific truth still comes from existing structured paper state and evidence refs
- note/profile/screening inputs stay context-only
- chart-pack source truth stays with the named saved source artifact, snapshot, and spec bundle members
- the saved pack may include an additive `artifact_brief` and `artifact_brief_review`
- those snapshots are review metadata only; they do not become stronger owners than lane-owned bundle manifests plus upstream lineage

## Contract

### 1. `SourceContextManifest`
- records the source/context items that shaped the artifact
- records the allowlisted evidence refs available to the artifact
- records lightweight retrieval-trace summary metadata

### 2. `ArtifactCommunicativeIntent`
- states the artifact family, goal, audience, mode, and output-mode family
- lists must-include and must-not-infer rules
- keeps communication goals separate from scientific truth policy

### 3. `ArtifactPlan`
- records the planned deliverable items
- each item carries:
  - `kind`
  - `label`
  - `support_status`
  - `requires_evidence`
  - `evidence_refs`
  - `source_item_ids`

### 4. `ArtifactPlanReview`
- records additive warnings before or alongside rendering
- current status is intentionally small:
  - `pass`
  - `warn`
- current warnings focus on:
  - missing direct support for evidence-required items
  - presence of context-only inputs
  - absence of any allowed evidence refs where the lane is evidence-linked
  - saved chart warning states or missing source bindings where the lane is source-artifact-linked

## Guardrails

- `Artifact Brief` is not canonical scientific truth.
- `Artifact Brief` does not replace lane-owned renderers or validators.
- `Artifact Brief` must not upgrade context-only material into evidence-backed output.
- `Artifact Brief` should stay cheap to persist and cheap to ignore.
- if a lane does not use this contract, the lane remains valid.

## Current Judgment

This contract is worth keeping because it adds a missing planning seam between:
- canonical evidence state
- downstream communication artifacts

but it is only safe as an additive, lane-consuming contract.

It should not be turned into a generic orchestrator or a justification for importing large multi-agent runtime behavior.
