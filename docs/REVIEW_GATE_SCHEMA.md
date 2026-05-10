# Review Gate Schema

Status: Draft bounded spec
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`

Related docs:
- `docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md`
- `docs/MEETING_PACK.md`
- `docs/CHART_PACK.md`
- `docs/PAPER_SYNTHESIS.md`
- `docs/ARTIFACT_BRIEF.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/PRESENTATION_REVIEW_SCHEMA.md`
- `docs/STYLE_LINT_SCHEMA.md`

## Purpose

Define the safest current shared seam for additive review-gate artifacts such as:
- `acceptance_contract.json`
- `quality_gate.json`

This spec exists to keep review-gate artifacts:
- file-backed
- machine-readable
- bundle-local or run-local
- explicit about readiness and failure conditions

without:
- creating a new canonical truth owner
- forcing every lane into one approval engine
- letting review summaries silently outrank bundle manifests, evidence refs, or canonical structured state

## Current Judgment

At the current repo stage, review-gate artifacts are only safe when they are treated as:
- additive
- lane-owned
- deterministic to rebuild from saved bundle or run state
- subordinate to upstream truth owners

This spec is intentionally about the shared review-gate seam.

It is not a proposal to replace:
- lane-owned bundle manifests
- current paper/run/artifact runtime truth
- lane-specific validators, evals, or promotion policy

## Current Scope

This spec applies to current bounded review-gate artifacts for:
- `deep_read` saved runs
- `meeting_pack`
- `chart_pack`

It also applies when another lane reads those artifacts as optional additive inputs.

Current example:
- `paper_synthesis` may attach a selected run's `quality_gate.json` or `acceptance_contract.json` as source refs
- `paper_synthesis` does not become the new owner of those review-gate artifacts

## Non-Goals

This spec does not define:
- a generalized workflow approval engine
- cross-lane numeric scoring
- a mandatory shared boolean set for every lane
- a replacement for lane-specific warnings or validation payloads
- a new scientific truth contract

## 1. Review-Gate Layer Rules

### 1.1 Review-gate artifacts stay additive

`acceptance_contract.json` and `quality_gate.json` are sibling review artifacts.

They must not become stronger owners than:
- current canonical structured state
- the saved run or bundle manifest they describe
- named saved source artifacts

Current rule:
- review-gate artifacts summarize acceptance, completeness, and handoff posture
- review-gate artifacts do not establish biomedical truth by themselves

### 1.2 `acceptance_contract` and `quality_gate` stay distinct

`acceptance_contract.json` answers:
- what outputs and checks were expected for this bounded run or bundle
- what the operator-facing acceptance rule is

`quality_gate.json` answers:
- what the current gate status is
- which checks passed, warned, or failed
- whether lane-specific handoff or promotion conditions currently hold

Current rule:
- do not collapse these into one opaque file
- do not use `quality_gate.json` as a substitute for the saved manifest or selected upstream lineage

### 1.3 Identity stays lane-owned

Review-gate artifacts should keep the identity fields that match the owning lane.

Current examples:
- `Meeting Pack`: `pack_id`
- `Chart Pack`: `chart_pack_id`
- `Deep Read`: `paper_id` plus `run_id`

Current rule:
- do not force a generic `bundle_id` or `artifact_id` field when the active lane already has a stronger identifier contract

### 1.4 Status vocabulary stays small

Recommended shared gate vocabulary:
- `overall_status`
  - `pass`
  - `warn`
  - `fail`
- check `status`
  - `pass`
  - `warn`
  - `fail`

Allowed lane extension:
- `not_run`
  - use only when a lane has a real saved distinction between "failed" and "did not run"

Current rule:
- keep `overall_status` small and comparable
- allow richer per-check semantics only when current runtime behavior truly needs them

### 1.5 Reason codes stay machine-readable

If a lane emits compact gate reasons, prefer:
- `reason_codes[]`
- lane-specific hard-fail codes when needed

Current rule:
- reason codes should stay short, stable, and machine-readable
- long prose belongs in `detail`, notes, or the owning manifest, not in reason-code fields

### 1.6 Readiness booleans stay lane-owned

Current lanes already use different readiness booleans:
- `bundle_ready`
- `handoff_ready`
- `discussion_ready`
- `current_promotion_candidate`
- `review_ready`

Current rule:
- reuse an existing boolean name only when the semantics actually match
- do not invent synonyms for an already-adopted meaning
- do not force all lanes to expose all readiness booleans

### 1.7 Hard-fail semantics stay explicit when needed

Some lanes need explicit fatal-condition reporting.

Current example:
- `Deep Read` uses:
  - `hard_fail_conditions[]` in `acceptance_contract.json`
  - `hard_fail_codes[]` in `quality_gate.json`

Current rule:
- lanes without fatal-condition logic do not need these fields
- lanes with fatal-condition logic should keep that distinction machine-readable rather than burying it in prose

### 1.8 Writes stay deterministic and additive

Review-gate files should be rebuilt from saved lane state, not hand-edited narrative outputs.

Current rule:
- write them as sibling files beside the owning run or bundle
- rewrite safely on rerender or refresh
- do not append partial fragments or treat stale gate files as invisible

## 2. Acceptance Contract Minimum Shape

Each acceptance contract should preserve or map to:

```json
{
  "schema_version": "...",
  "workflow": "...",
  "<lane_primary_ids>": "...",
  "requested_scope": {},
  "expected_outputs": [],
  "acceptance_checks": [
    {
      "name": "...",
      "required": true,
      "source": "...",
      "description": "..."
    }
  ],
  "operator_contract": {}
}
```

Current notes:
- lane-owned primary identity fields stay lane-specific
- `Deep Read` currently uses `promotion_contract` instead of `operator_contract`
- lanes may extend this shape, but they should keep the acceptance-check list explicit and machine-readable

### 2.1 `acceptance_checks[]`

Recommended fields:
- `name`
- `required`
- `source`
- `description`

Current rule:
- the check name should be stable enough for regression and refresh code
- `source` should point to the saved file, path pattern, or manifest field that the check is about
- `required=false` is allowed for bounded observability or review helpers that are useful but not mandatory

## 3. Quality Gate Minimum Shape

Each quality gate should preserve or map to:

```json
{
  "schema_version": "...",
  "workflow": "...",
  "<lane_primary_ids>": "...",
  "overall_status": "warn",
  "reason_codes": [],
  "checks": [
    {
      "name": "...",
      "status": "pass",
      "detail": "..."
    }
  ]
}
```

Current notes:
- lane-owned readiness booleans may be added when they carry real operator meaning
- fatal-condition and recovery summaries remain lane-owned extensions, not mandatory shared fields

### 3.1 `checks[]`

Recommended fields:
- `name`
- `status`
- `detail`

Current rule:
- `name` should be stable enough to support refresh, compare, or viewer projection
- `detail` should stay compact and operator-readable
- a lane may attach richer summaries outside `checks[]`, but the compact check list should remain first-class

## 4. Relationship To Bundle Manifests And Canonical State

Review-gate artifacts are not standalone bundle owners.

Current rule:
- bundle-local manifests such as `meeting_pack.json` and `chart_pack.json` remain the primary owner files for their lanes
- run-local state and canonical paper state remain stronger than any review-gate summary
- when a downstream lane imports a review-gate artifact as context, it must stay explicitly review-only or additive

Current example:
- `Paper Synthesis` may warn when a selected run `quality_gate.json` is `warn` or `fail`
- `Paper Synthesis` still derives scientific content from structured state plus selected resolved evidence, not from the gate file itself

## 5. Relationship To `Artifact Brief`

`Artifact Brief` is a planning seam.

Review-gate artifacts are acceptance and status seams.

Current rule:
- `artifact_brief` and `artifact_brief_review` may influence gate checks or reason codes
- they do not replace the acceptance contract
- they do not replace the quality gate
- they do not become stronger truth owners than the manifest or upstream lineage

## 6. Current Lane Mapping

### 6.1 Deep Read

Current implementation:
- `src/schemas/deepread_handoff.py`
- `src/services/deepread_handoff_artifacts.py`

Current gate shape highlights:
- identity via `paper_id` and `run_id`
- `current_promotion_candidate`
- `review_ready`
- `hard_fail_codes[]`
- optional recovery and stability summaries

### 6.2 Meeting Pack

Current implementation:
- `src/schemas/meeting_pack_handoff.py`
- `src/meeting_packs/handoff_artifacts.py`

Current gate shape highlights:
- identity via `pack_id`
- `bundle_ready`
- `discussion_ready`
- checks for regenerate availability, trace persistence, markdown sync, readiness label, artifact-brief review, and content-risk scan

### 6.3 Chart Pack

Current implementation:
- `src/schemas/chart_pack_handoff.py`
- `src/chart_packs/handoff_artifacts.py`

Current gate shape highlights:
- identity via `chart_pack_id`
- `bundle_ready`
- `handoff_ready`
- checks for source-item persistence, snapshot/spec completeness, markdown sync, artifact-brief review, and chart warning state

## 7. Shared Adoption Guidance For New Lanes

Before adding review-gate artifacts to a new lane, answer these in order:

1. What saved run or bundle does the gate describe?
2. What remains the stronger truth owner?
3. Does the lane need both an `acceptance_contract.json` and a `quality_gate.json`, or only one of them?
4. Which checks are stable enough to become machine-readable names?
5. Which readiness booleans already exist in the repo with the same meaning?
6. Are there true hard-fail conditions that deserve explicit codes?
7. Can the gate files be rebuilt deterministically from saved lane state?

If those answers are weak or ambiguous, the lane should keep warnings inside the primary manifest first rather than minting a new gate artifact pair.

## 8. Future Direction

If PaperPipe later needs a stronger shared review layer, the safe next step is:
- tighten shared naming around existing gate files
- keep lane-owned primary identities
- keep review-gate artifacts additive

The safe next step is not:
- replacing current manifests with a generic review object
- centralizing all lane decisions into one universal approval schema
- using review-gate files as scientific truth owners
