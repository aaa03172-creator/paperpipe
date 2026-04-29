# Presentation Review Schema

Status: Draft future seam
Date: 2026-04-20
Owner: Runtime/artifact maintainers
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/REVIEW_GATE_SCHEMA.md`
- `docs/TALK_PACK.md`
- `docs/TALK_PACK_EVALUATION_RUBRIC.md`

Related docs:
- `docs/TALK_PACK_STYLE_GUIDE.md`
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/ARTIFACT_BUNDLE_SPEC.md`
- `docs/EXPORT_PACK_SPEC.md`

## Purpose

Define the safest future minimum schema for `presentation_review.json` as an additive talk-pack review sidecar.

This schema exists to keep future presentation review:
- machine-readable
- additive
- bounded to one talk pack
- explicit about presenter-view and evaluator-view checks

without:
- creating a new truth owner
- collapsing all talk quality into one opaque score
- letting presentation review silently outrank evidence-linked upstream owners

## Current Judgment

At the current repo stage, `presentation_review.json` is only safe as:
- a future talk-pack-local review sidecar
- a lane-owned additive artifact
- a deterministic rebuild target from saved pack state plus selected exports

It is not yet safe as:
- a standalone runtime family
- a generalized seminar scoring engine
- a replacement for `talk_pack.json`, upstream owners, or lane manifests

Current status:
- no active `presentation_review.json` runtime artifact exists yet
- this doc is a bounded design target for a future talk-pack lane

## Current Scope

The safe current scope is:
- one `talk_pack_id`
- one selected output set
- one presenter-view summary
- one evaluator-view summary
- explicit missing dependency and warning state

## Non-Goals

This schema does not define:
- freeform prose review storage
- transcript or speech-performance analytics
- a visual design engine
- cross-pack leaderboard or scoring

## 1. Layer Rules

### 1.1 The review stays additive

`presentation_review.json` is a `review_gate_artifact`.

Current rule:
- it must remain non-canonical
- it must not replace `talk_pack.json` as the owner
- it must not establish biomedical truth by itself

### 1.2 Identity stays talk-pack-owned

Recommended primary ids:
- `talk_pack_id`
- `paper_slug`

Current rule:
- do not introduce a separate review-root identity that outranks the talk pack

### 1.3 Status vocabulary stays small

Recommended shared vocabulary:
- `overall_status`
  - `pass`
  - `warn`
  - `fail`
- per-check `status`
  - `pass`
  - `warn`
  - `fail`

Recommended severity vocabulary:
- `low`
- `medium`
- `high`

Current rule:
- keep status compact and machine-readable
- put nuance in `detail`, not in proliferating status enums

## 2. Minimum Shape

```json
{
  "schema_version": "draft",
  "workflow": "talk_pack_review",
  "talk_pack_id": "...",
  "paper_slug": "...",
  "generated_at": "2026-04-20T09:00:00Z",
  "overall_status": "warn",
  "reason_codes": [],
  "selected_outputs": [],
  "required_outputs": [],
  "missing_dependencies": [],
  "presenter_view": {
    "overall_status": "warn",
    "checks": []
  },
  "evaluator_view": {
    "overall_status": "warn",
    "checks": []
  },
  "warnings": []
}
```

Current notes:
- `selected_outputs[]` and `required_outputs[]` should match the talk-pack owner contract rather than inventing a second source of truth
- `generated_at` should reflect review refresh time, not pack creation time

## 3. Check Shape

Recommended minimum check shape:

```json
{
  "name": "time_fit",
  "perspective": "presenter_view",
  "status": "warn",
  "severity": "medium",
  "detail": "Script length exceeds the selected duration target.",
  "target_artifacts": ["speaker_script.md", "slide_manifest.json"],
  "fixable_by_ai": true
}
```

Recommended fields:
- `name`
- `perspective`
- `status`
- `severity`
- `detail`
- `target_artifacts`
- `fixable_by_ai`

Optional fields when truly needed:
- `reason_codes`
- `suggested_action`

Current rule:
- keep the check artifact-focused
- avoid free-floating advice detached from the affected member

## 4. Recommended Presenter-View Checks

Recommended `presenter_view.checks[]` names:
- `audience_fit`
- `time_fit`
- `narrative_flow`
- `slide_economy`
- `figure_explainability`
- `qa_readiness`

Current rule:
- these checks should reflect the selected talk mode and output set
- missing outputs should not produce fake pass states

## 5. Recommended Evaluator-View Checks

Recommended `evaluator_view.checks[]` names:
- `scientific_fidelity`
- `structure_and_clarity`
- `evidence_honesty`
- `slide_judgment`
- `discussion_quality`
- `seminar_readiness`

Current rule:
- evaluator-view should judge the presentation as an experienced academic reviewer would
- evaluator-view must not replace upstream evidence review

## 6. Recommended Hard-Fail And Warn Logic

Recommended hard-fail conditions:
- required output missing
- key numeric claim unverified
- slide-level claim cannot reopen trust
- conclusion materially overstates evidence

Recommended warn conditions:
- duration mismatch
- slide density high
- Q&A coverage shallow
- limitations underdeveloped
- evaluator-facing objections underprepared

Current rule:
- hard-fail should stay narrow
- warning logic should remain useful for regenerate-or-trim decisions

## 7. Relationship To Other Talk-Pack Docs

- `docs/TALK_PACK.md` owns the lane contract
- `docs/TALK_PACK_EVALUATION_RUBRIC.md` defines what to check
- this schema defines how to persist the additive review sidecar

Current rule:
- the schema should not drift beyond the rubric and owner contract

## 8. Conclusion

The safest future `presentation_review.json` is:
- additive
- non-canonical
- talk-pack-local
- explicit about presenter and evaluator views
- explicit about missing dependencies and warning-heavy readiness

That is enough structure to support regeneration and review without creating a second truth system.
