# Current Baseline Recheck

Status: Active execution note
Date: 2026-03-18
Owner: Repository maintainers
Canonical parents:
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/PR_R0_Baseline_Adoption_Manifest_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`

## 0. Purpose

Translate the current-state reassessment into a narrow execution boundary:

- what is already real enough to treat as the current product baseline
- what should stay in the immediate repository-baseline lane
- what should remain a separate follow-up lane instead of widening the baseline freeze

This note is not a new master spec.

## 1. Current Product Reality

As of 2026-03-18, the repo already has three product-real surfaces that should not be treated as speculative reference work:

1. `Research DNA`
   - API/service/store/CLI lane exists.
   - The pilot -> screening -> refine -> lock loop is already documented and implemented.
   - Search-eval reporting now includes additive `refinement_report` and `decision_summary` surfaces.

2. `Meeting Pack`
   - Evidence-linked downstream artifact generation is already real.
   - Deterministic selector loading, evidence ledger, retrieval trace, validate/regenerate/rerender boundaries are already part of the active design.

3. `paper-notes` operational detail surface
   - Detail responses already expose `ops_summary`, `issues_state`, and additive `context_trace`.
   - `context_trace` is operational metadata only and is not a new scientific-truth layer.

Implication:

- the immediate need is not more framework adoption
- the immediate need is keeping the existing biomedical core lanes legible, bounded, and baseline-readable

## 2. Bind Into Baseline Now

These items should be treated as the "hold steady and adopt cleanly" slice.

### 2.1 Repository-freeze boundary

Keep using the existing baseline manifests as the actual include/exclude authority:

- `/Users/jangseongjin/paperpipe/docs/PR_R0_Baseline_Adoption_Manifest_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`

Reason:

- they already define the narrow repository-baseline shape
- they already separate baseline freeze from broader product expansion
- they are still the right guardrail in a heavily dirty workspace

### 2.2 Treat these as stable product lanes, not reopen points

The following recent work should be considered additive hardening on top of the current product surfaces:

- `Research DNA` search-eval reporting hardening
- paper-note detail `context_trace` contract
- shared "source trace is operational metadata only" rule between Meeting Pack and note detail

Reason:

- these changes improve explainability and reproducibility
- they do not justify reopening architecture boundaries
- they should not be used to smuggle broader runtime, memory, or UI scope into baseline-freeze work

### 2.3 Default posture for the next repository step

The next repository-level action should still read as:

- freeze the verified narrow baseline
- keep broader unstaged tails in separate lanes
- avoid turning a baseline PR into a speculative product expansion PR

## 3. Keep In Separate Lanes

The following are valid later ideas, but they should stay outside the immediate baseline bundle.

### 3.1 UI and operator-surface expansion

- surfacing `context_trace` in the reader UI
- adding a dedicated ops/debug panel for note-detail trace
- broader Meeting Pack inspector expansion

Reason:

- current API/debug metadata is sufficient
- biomedical core correctness beats extra viewer instrumentation

### 3.2 Semantic broadening

- broader synonym coverage in Meeting Pack focus-family logic
- looser cross-focus majority/outlier semantics
- deeper note/context-derived synthesis beyond the current framing layer

Reason:

- these are useful, but they are not baseline blockers
- they should land only after the current baseline is accepted cleanly

### 3.3 New platform layers or framework imports

- project memory layer
- protocol knowledge layer
- method comparison layer
- DeerFlow/LangGraph/Claude-style runtime adoption
- heavy frontend preview tooling as a product dependency

Reason:

- these add complexity without improving the current biomedical core loop enough
- current repo value already comes from bounded `Research DNA`, `Meeting Pack`, and evidence-linked local state

## 4. Immediate Execution Suggestion

### Verification recheck

The existing baseline manifests were re-run on 2026-03-18 and remained green without changing their scope:

- `PR-R0` verification command -> `32 passed`
- `PR-M0` verification command -> `97 passed`

Implication:

- the current manifests are still executable as written
- recent additive hardening should be treated as adjacent follow-up work, not as a trigger to reopen the baseline boundary

### Do next

1. Treat repository baseline adoption for the Meeting Pack slice as already executed via `5c09619`, and keep the later backend/API commits as additive follow-up lanes rather than as reasons to reopen `PR-M0`.
2. Package the now-committed backend/API stack using `/Users/jangseongjin/paperpipe/docs/reports/Committed_Backend_API_Stack_Summary_2026-03-18.md`.
3. If code work resumes, leave `context_trace` API/debug-only and start a separate `agent_artifacts` contract-hardening lane instead of widening the baseline bundle.

### Explicitly skip

1. Do not widen baseline-freeze work with framework migration, memory-platform work, or plugin/hook systems.
2. Do not reopen Meeting Pack selector semantics during baseline adoption.
3. Do not prioritize frontend preview/polish work ahead of biomedical search/evidence reliability.
