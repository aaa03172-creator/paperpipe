Status: Active release-boundary decision note
Date: 2026-03-25
Owner: Runtime/product maintainers
Canonical parents:
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

# Deep Read Legacy Bundle Release Boundary

## Purpose

Make one narrow release decision explicit:

- should legacy/partial deep-read bundles count toward the first-product proof slice?

This is not:
- a storage redesign
- a mass backfill plan
- a reason to reopen artifact-first fallback

It is a release-boundary decision grounded in the current repo evidence.

## Decision

For the first shipped/demo-ready product bar:

- count only the current runtime deep-read path and modern eligible bundles toward the launch-defining proof slice
- do **not** count older legacy/partial deep-read bundles as required proof for deep-read readiness
- keep legacy/partial bundles available as inspectable historical surfaces, but treat them as outside the bounded launch proof unless they are explicitly backfilled later

In short:

> v1 deep-read proof is based on current-runtime fresh/modern canonical state, not on every historical partial artifact bundle ever produced locally.

## Why This Is The Safest Current Call

Current repo evidence now splits into two different truths:

1. older sampled real-paper bundles remain legacy/partial
2. the current rerun path is now capable of producing canonical note-side state on a representative fresh real paper

Repo-grounded anchors:
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`
- `docs/reports/Deep_Read_Structured_State_Gap_2026-03-24.md`
- `docs/reports/Deep_Read_Note_State_Promotion_Design_2026-03-24.md`
- `backend/services/job_runner.py`

The key fact is:
- the blocker is no longer “current runtime cannot finish a representative real paper”
- the blocker is only that older bundles were produced before the modern promotion path and still do not surface canonical `.pp/<slug>/state.json`

That makes legacy coverage a release-boundary question, not a current-runtime credibility question.

## Bounded Inclusion Rule

Count a paper toward the first-product deep-read proof slice only when all of these are true:

1. it was produced by the current runtime or refreshed through a current bounded rerun
2. the run leaves a modern bundle shape sufficient for current proof:
   - `run_meta.json`
   - `claimset.resolved.json`
3. canonical note-side state exists at `.pp/<slug>/state.json`
4. current backend note/detail surfaces read that state successfully

This is the smallest honest rule that matches the current product bar.

## Explicit Exclusion Rule

Do not require older legacy/partial bundles to pass the first-product deep-read proof if they have one or more of these traits:

- no `run_meta.json`
- no `claimset.resolved.json`
- no canonical `.pp/<slug>/state.json`
- only historical artifact-bundle evidence without the current note-side canonical projection

These bundles remain:
- useful for local inspection
- useful as backfill candidates
- useful as drift evidence

But they are not launch-defining proof by default.

## What This Decision Does Not Mean

This decision does **not** mean:
- legacy bundles are deleted
- legacy notes should be hidden
- artifact-first fallback becomes the reader contract
- backfill is forbidden forever

It means only:
- v1 release judgment should not be blocked by historical bundles that predate the current canonical promotion path

## Why Not Backfill Before V1

Pre-v1 mass backfill is the wrong default because it would:

- widen scope late
- blur the line between current-runtime proof and historical repair work
- increase the risk of silently writing canonical state from incomplete bundles

Backfill can still happen later as a bounded follow-up if it is worth the operational cost.

## Why Not Artifact-First Fallback

Artifact-first note-detail fallback remains the wrong default because it would:

- create two structured-state assembly paths
- weaken the `.pp/<slug>/state.json` canonical note-backed contract
- make release readiness look greener by reading around the current canonical path instead of proving it

So the current decision keeps:
- `.pp/<slug>/state.json` as the note-backed truth contract
- modern rerun proof as the launch slice
- legacy bundles as out-of-slice historical evidence

## Practical Product Consequence

With this boundary in place:

- the deep-read/job lane can be judged `green enough` for the first-product proof slice
- remaining `yellow` items should move to:
  - provenance/trust hardening
  - rehearsal-level `Must-Not-Ship` confirmation
  - optional later legacy backfill

## Follow-Up Order

1. reflect this boundary in the release-facing notes
2. keep legacy-bundle backfill as a later bounded option, not a pre-v1 requirement
3. use release rehearsal to validate the remaining `Must-Not-Ship` rows

## Bottom Line

The safest current release decision is:

- prove v1 on the current canonical rerun path
- do not let historical partial bundles redefine the launch bar
- keep legacy backfill optional and post-boundary unless it becomes necessary
