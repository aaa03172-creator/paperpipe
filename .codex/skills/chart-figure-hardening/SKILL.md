---
name: chart-figure-hardening
description: Developer-only workflow skill for reviewing chart and figure artifact lanes against current bundle contracts, provenance rules, and warning-visible derived-artifact boundaries.
---

# Chart Figure Hardening

## Overview

Use this skill when reviewing or hardening bounded chart and figure artifact lanes in the current PaperPipe runtime.

This skill is for developer workflow only.
It does not create a runtime-visible product capability.

The current primary targets are:
- `Chart Pack`
- `Image Evidence`
- `Method Comparison`

## Trigger conditions

Use this skill when:
- a chart or figure artifact looks too polished relative to its source truth
- a viewer or export path may be hiding warnings, conflicts, or sparse support
- a saved artifact family may be drifting toward a second truth store
- you need a bounded review path for chart/figure-related code changes

Do not use this skill to redesign plotting, image analysis, or generalized dataset workspace behavior.

## Inputs and expected context

Gather or infer:
- artifact family (`chart_pack`, `image_evidence`, `method_comparison`, or similar bounded lane)
- artifact id or saved bundle path
- whether the task is code review, runtime diagnosis, or viewer hardening

If there is no representative live bundle under `storage/`, use a fixture-backed or targeted-test-generated bundle path and label the review as fixture-backed rather than live-runtime-backed.

Primary references:
- `docs/CHART_PACK.md`
- `docs/IMAGE_EVIDENCE.md`
- `docs/METHOD_COMPARISON.md`
- `docs/Evidence_and_Uncertainty_Rules.md`

Likely owner paths:
- `src/chart_packs/`
- `src/image_evidence/`
- `src/method_comparisons/`
- matching `backend/routers/`
- matching viewer routes in `frontend/src/app/pages/`

## Output contract

Return:
1. `Artifact family status`
2. `Source/canonical/derived check`
3. `Warning and provenance visibility check`
4. `Mismatch or risk`
5. `Smallest hardening follow-up`

If useful, use the bundled template in `templates/artifact-review-note.md`.

## Workflow

1. Confirm the bounded contract first.
   Read the active spec for the artifact family before evaluating code or UI behavior.
2. Inspect saved bundle members.
   Identify the primary bundle-local manifest and any sibling derived files.
   If no live bundle exists, use the smallest targeted test or fixture path that produces the artifact family and keep that boundary explicit.
3. Verify truth ownership.
   Confirm the artifact remains derived from current canonical structured inputs rather than becoming a new truth root.
4. Verify warning and provenance visibility.
   Check whether warning-heavy, missing, sparse, or conflict states remain explicit in saved artifacts and user-visible viewers.
5. Propose a bounded hardening patch if needed.
   Prefer wording, trace, export, or viewer visibility fixes before schema expansion.

## Bundled resource map

- `references/provenance-checklist.md`
- `templates/artifact-review-note.md`

## Guardrails and non-goals

- Do not reopen generic chart builder or image analysis scope.
- Do not promote derived visual artifacts into canonical scientific truth.
- Do not hide sparse evidence or warnings in order to make outputs look cleaner.
- Do not widen into generalized dataset or spreadsheet workspace behavior.

## Verification or handoff expectations

When closing the task, separate:
- what was inspected directly
- what was inferred from current docs or code
- what remains unverified
- the smallest safe follow-up if a patch is needed
