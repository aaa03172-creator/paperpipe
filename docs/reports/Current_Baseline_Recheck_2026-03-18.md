# Current Baseline Recheck

Status: Active execution note
Date: 2026-03-18
Owner: Repository maintainers
Canonical parents:
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`
- `/Users/jangseongjin/paperpipe/docs/Repository_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/reports/Memory_Ready_Hardening_Baseline_2026-03-18.md`

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

Keep using the current tracked baseline-boundary notes as the include/exclude guardrail:

- `/Users/jangseongjin/paperpipe/docs/Repository_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/PR_M0_Meeting_Pack_Baseline_Adoption_2026-03-13.md`
- `/Users/jangseongjin/paperpipe/docs/Pending_PR_Queue.md`

Reason:

- together they preserve the narrow repository-baseline shape, the executed Meeting Pack baseline slice, and the current separate-lane guardrails
- they still separate baseline freeze from broader product expansion
- they are the tracked guardrail surface in a heavily dirty workspace

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
- broad external-reference adoption interpreted as a new architecture search rather than bounded fit-review work

Reason:

- these add complexity without improving the current biomedical core loop enough
- current repo value already comes from bounded `Research DNA`, `Meeting Pack`, and evidence-linked local state
- recent external references should stay in a bounded `sidecar / fallback / benchmark / dataset / reference` frame, not as inputs for a fresh architecture search

## 4. Immediate Execution Suggestion

### Verification recheck

The existing baseline manifests were re-run on 2026-03-18 and remained green without changing their scope:

- `PR-R0` verification command -> `32 passed`
- `PR-M0` verification command -> `97 passed`

Implication:

- the current manifests are still executable as written
- recent additive hardening should be treated as adjacent follow-up work, not as a trigger to reopen the baseline boundary

### Current execution baseline recheck

The runtime hardening lane was rechecked again on 2026-03-18 after the latest client-gesture logging and timeline visibility follow-up:

- `/Users/jangseongjin/paperpipe` -> `pytest -q` -> `645 passed, 1 skipped`
- `/Users/jangseongjin/paperpipe/frontend` -> `npm run build` -> success
- `/Users/jangseongjin/paperpipe/frontend` -> mock Playwright recheck -> `2 passed`
- `/Users/jangseongjin/paperpipe/frontend` -> backend Playwright `user_action` timeline recheck -> `1 passed`
- `python3 /Users/jangseongjin/paperpipe/scripts/lint_docs.py` -> `docs lint passed`

Implication:

- execution baseline is currently green across Python runtime, frontend build, mock UI coverage, backend timeline coverage, and docs hygiene
- the main remaining risk is repository-baseline breadth, not active runtime instability

### Do next

1. Treat repository baseline adoption for the Meeting Pack slice as already executed via `5c09619`, and keep the later backend/API commits as additive follow-up lanes rather than as reasons to reopen `PR-M0`.
2. Package the now-committed backend/API stack using `/Users/jangseongjin/paperpipe/docs/reports/Committed_Backend_API_Stack_Summary_2026-03-18.md`.
3. If code work resumes after packaging, leave `context_trace` API/debug-only and keep any additional `agent_artifacts` work bounded to schema/test hardening instead of widening the baseline bundle or reopening reader/runtime design.

### Memory-ready hardening status

The memory-ready hardening lane now includes:

- stable runtime identity/path helpers
- deterministic chunk ids
- additive event logging
- `user_actions` write/read/timeline integration
- grounding-preserving output bridge
- timeline UI visibility for `user_action`
- client-only navigation-intent logging
- evidence-review gesture logging for claim/stat jumps

Implication:

- this lane no longer has a required immediate follow-up
- the next step, if reopened, should target explicit reviewer-intent actions rather than more baseline hardening

### Explicitly skip

1. Do not widen baseline-freeze work with framework migration, memory-platform work, or plugin/hook systems.
2. Do not reopen Meeting Pack selector semantics during baseline adoption.
3. Do not prioritize frontend preview/polish work ahead of biomedical search/evidence reliability.

## 5. Reopen Conditions For Recent External References

Recent external references should remain closed unless new repository-grounded evidence justifies reopening them as bounded follow-up lanes.

- `GLM-OCR` / `Docling` / `GROBID` / parser-adjacent document tools
  - reopen only if a hard-document subset (`scanned`, `image-based`, `table-heavy`, `text-poor`) shows a repeatable quality gain over the current parser/OCR baseline
- `OpenAlex` / `Semantic Scholar` / source-enrichment references
  - reopen only if a bounded metadata, citation-graph, or enrichment gap appears that the current source stack and local artifacts cannot already cover cleanly
- `MedCPT` / retrieval-rerank baselines
  - reopen only if offline evaluation on existing `Research DNA` queries shows a meaningful gain in ranking usefulness (`include@k`, precision proxy, or bounded benchmark recall)
- `PubTator Central` / biomedical annotation sidecars
  - reopen only if entity/relation annotations measurably improve grounding, extraction review, or note-linking usefulness on real corpus slices
- `EBM-NLP` / extraction training-eval datasets
  - reopen only if extraction evaluation or supervision becomes the active bottleneck and the dataset still matches the target task closely enough to justify bounded offline use
- `Scientific Taste`-style judge layers
  - reopen only if local preference assets become strong enough to evaluate them without collapsing into citation-based shortcuts
- `Trialstreamer` / SR-RCT workflow references
  - reopen only if SR-RCT support becomes an active lane and the current pipeline needs a bounded benchmark or workflow reference there
- `PaperQA2` / agentic RAG references
  - reopen only if current answer assembly or evidence-citation behavior shows a specific, measurable gap that can be evaluated without recentering the system around a new RAG architecture
- `Ars Contexta`-style note or ops concepts
  - reopen only if they improve operator reliability or maintenance visibility without becoming a new system center

Implication:

- these are recheck triggers, not new roadmap items
- until those conditions are met, keep them in a bounded `sidecar / fallback / benchmark / dataset / reference` frame
