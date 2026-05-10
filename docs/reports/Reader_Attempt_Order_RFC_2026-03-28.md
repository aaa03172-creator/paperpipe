# Reader Attempt-Order RFC

Status: bounded RFC note, config-gated pilot path implemented and tiny acceptance run recorded, default unchanged
Date: 2026-03-28
Owner: runtime/product maintainers
Canonical parents:
- `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`
- `docs/reports/Reader_Attempt_Profile_2026-03-28.md`
- `docs/reports/TurboQuant_Fit_Review_2026-03-27.md`
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`

Related note:
- `docs/reports/Focused_First_Gated_Pilot_Acceptance_Checklist_2026-03-28.md`
- `docs/reports/Focused_First_Gated_Pilot_Acceptance_2026-03-28.md`

## Purpose

Record the smallest decision boundary for a possible reader attempt-order change.

This is not:

- a runtime adoption note
- a serving-infrastructure proposal
- a reason to reopen TurboQuant

It is a narrow RFC that answers:

> should the runtime eventually consider `focused -> primary -> sentence_focus` instead of `primary -> focused -> sentence_focus`?

## Executive Call

Safest current direction:

1. do **not** change the default runtime attempt order yet
2. treat `focused_first` as a benchmark-backed candidate, not an adopted runtime policy
3. only reopen implementation if a small additional validation bar is met
4. keep TurboQuant and other inference-infra work out of this lane

## Status update

As of `2026-03-28`, the smallest pilot path now exists behind config:

- `llm.reader_attempt_order: current` keeps the existing runtime default
- `llm.reader_attempt_order: focused_first` enables the candidate order for explicitly opted-in runs
- runtime metadata now records the configured attempt order

This does **not** mean the pilot is accepted or active by default. The opt-in gate exists, and a tiny acceptance run is now recorded, but the runtime default is still unchanged.

## Confirmed current evidence

From `docs/reports/Focused_First_Reader_Benchmark_2026-03-28.md`:

- sample A: `zotero:coricTargetingProdromalAlzheimer2015`
  - claim yield preserved: `4 -> 4`
  - prompt tokens reduced: `10004 -> 4553`
- sample B: `zotero:parkDiscoveryDualactionSmall2022`
  - claim yield preserved: `2 -> 2`
  - prompt tokens reduced: `8340 -> 3648`
  - current-order `primary` attempt timed out
- sample C: `zotero:grandeBloodbasedBiomarkersAlzheimers2025`
  - claim yield preserved: `3 -> 3`
  - prompt tokens reduced: `8535 -> 3757`
  - current-order `primary` attempt timed out
- sample D: `zotero:leeDeepLearningbasedBrain2022`
  - claim yield preserved: `3 -> 3`
  - prompt tokens reduced: `8456 -> 3608`
  - current-order `primary` attempt timed out

Repo-grounded inference:

- the strongest current bottleneck candidate is still reader prompt/context strategy
- the evidence is now stronger for `focused_first`
- but the evidence is still benchmark-only and live-model dependent

## Why this is not adopted yet

### 1. Benchmark evidence is not runtime evidence

The current benchmark:

- uses live local model calls
- is non-deterministic
- does not yet measure downstream effects on:
  - note-side state quality
  - resolved evidence quality
  - rerun consistency across a broader paper mix

### 2. Four papers are enough to justify a gated pilot discussion, not a silent default flip

Current evidence is strong enough to say:

- this is no longer a one-off hunch
- the outlier benchmark bar is now met

Current evidence is not strong enough to say:

- the runtime default should flip immediately
- downstream quality impact is already known

### 3. Three current-order failures came from `primary` timeout

That matters, but it changes the interpretation:

- the benchmark is showing policy fragility
- not just clean deterministic speedup

That means any runtime adoption must be treated as a trust and stability decision, not only a performance tweak.

## Candidate change if later adopted

Current order:

- `primary`
- `focused`
- `sentence_focus`

Candidate order:

- `focused`
- `primary`
- `sentence_focus`

Current expectation if adopted later:

- preserve the existing bounded multi-attempt structure
- do not remove `primary`
- do not introduce giant-context behavior
- do not pair this with provider/runtime changes in the same lane

## Adoption bar

The smallest safe adoption bar is:

1. no observed claim-yield regression across the benchmark set
2. one deliberately difficult outlier benchmark is included
3. no evidence that `focused_first` causes worse resolved evidence linkage or weaker downstream artifacts
4. runtime rollout begins as:
   - benchmark-only, or
   - config-gated / explicitly opt-in
5. no product-facing speed claims at rollout time

If any of these are not met, keep the current default order.

## Safest implementation shape

The currently implemented bounded slice is:

1. add a bounded config or experiment flag for attempt order
2. keep the existing current order as default until the gate is explicitly flipped
3. record the effective attempt order in `reader_analysis` or `run_meta`
4. validate on a tiny representative set before broader use

Current touch points:

- `src/agents/reader_agent.py`
- `backend/services/job_runner.py`
- `src/config.py`

## What to reject

Reject these by default:

1. silently changing the runtime default from benchmark evidence alone
2. combining attempt-order experimentation with TurboQuant or serving-runtime changes
3. product-facing messaging about faster local inference
4. broad prompt redesign in the same lane

## Current decision

Current best judgment:

> keep the runtime default unchanged, keep `focused_first` as an RFC-backed opt-in path, and only discuss broader adoption after downstream quality checks remain clean beyond the tiny recorded pilot.

## Reopen trigger

Reopen this RFC only when one of these is true:

- a config-gated pilot is explicitly requested
- current-order `primary` continues to cause real runtime pain in fresh representative runs
- downstream quality checks for a tiny representative set are ready

Until then, this lane should stay closed.
