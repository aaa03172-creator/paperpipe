# OpenViking Reference Fit Review

Status: Reference-only architecture note  
Date: 2026-03-17  
Owner: Runtime/search maintainers  
Canonical parent: `docs/Lattice_v3_Master_Spec.md`

Reference source:
- [OpenViking GitHub README](https://github.com/volcengine/OpenViking)

Scope:
- reference only
- design inspiration only
- no direct adoption
- no current implementation mandate

## 0. Executive Summary

OpenViking is relevant as a reference because its README frames four ideas clearly:

1. filesystem-style hierarchical context organization
2. tiered context loading
3. observable retrieval trajectory
4. long-term memory and context consolidation

Those ideas are useful as architectural inspiration for PaperPipe.

They are not a current adoption target.

Current judgment:

- do not integrate OpenViking now
- do not replace PaperPipe architecture with an OpenViking-like system
- keep FastAPI-first, Pydantic-first, `state.json`-first, and `Research DNA`-first contracts
- prioritize core biomedical search, screening, extraction, and evidence grounding first

The right use of this reference is narrower:

- use it to sharpen future pathing and context-loading strategy
- use it to shape future retrieval observability
- do not let it expand current scope into a generic agent memory platform

## 1. What OpenViking Suggests

Based on the README, the most relevant signals are:

- a filesystem-like organization model for agent context
- on-demand loading across multiple context tiers
- retrieval that leaves an inspectable trajectory instead of a black-box chain
- session outputs that can be consolidated into longer-lived memory

These are useful abstractions.

They matter more as product architecture vocabulary than as immediate implementation details.

## 2. Current PaperPipe Reality

PaperPipe already has meaningful filesystem-scoped context organization.

Examples already in the repo:

- `research_dna/<dna_id>/...`
- `vault/.pp/<slug>/state.json`
- `vault/.pp/<slug>/runs/*.json`
- `storage/artifacts/<paper_id>/<run_id>/...`
- `storage/meeting_packs/<pack_id>/meeting_pack.json`

Current path helpers already formalize major roots:

- `research_dna_root()`
- `artifacts_root()`
- `meeting_packs_root()`
- `search_eval_root()`

So the repository is not missing hierarchical organization.

The bigger gap is not "we need a new context filesystem."

The bigger gaps are:

- stronger contract boundaries across existing roots
- more explicit retrieval/loading order
- better observability of why a given source was loaded
- bounded consolidation rules that do not blur canonical truth

## 3. Fit Assessment By Takeaway

### 3.1 Filesystem-style hierarchical context organization

Fit:

- strong conceptual fit
- low urgency for new implementation

Reason:

- `Research DNA` already uses a human-readable hierarchical asset tree with `profile.yaml`, `versions/`, `logs/`, and `benchmarks/`
- paper note structured state already uses a paper-scoped sidecar root under `.pp/<slug>/`
- Meeting Pack already uses its own artifact root instead of polluting paper-scoped canonical state

What to learn:

- keep context roots purpose-specific and inspectable
- prefer path helpers and deterministic directory structure over ad hoc scattered files
- keep canonical state and downstream drafts in different roots

What not to do:

- do not introduce a new generic "agent brain" root
- do not move existing `Research DNA`, `state.json`, or `meeting_pack` data into a new OpenViking-like hierarchy
- do not replace current FastAPI/runtime path helpers with a new virtual filesystem abstraction

PaperPipe-specific implication:

- continue deepening the current root taxonomy rather than adding a second context platform

### 3.2 Tiered context loading

Fit:

- strong conceptual fit
- medium future value
- not a current P0 task

PaperPipe already has natural context tiers even if they are not named that way.

A future PaperPipe-friendly tier model could look like:

- `Tier 0`: lightweight selectors and metadata
  - paper note index rows
  - `Research DNA` profile metadata
  - Meeting Pack source selectors
  - ops summaries
- `Tier 1`: canonical structured state
  - `.pp/<slug>/state.json`
  - `Research DNA` `profile.yaml`
  - screening and run logs
  - Meeting Pack JSON
- `Tier 2`: heavy evidence assets
  - claimset artifacts
  - stats artifacts
  - markdown bodies
  - PDF-derived evidence spans
  - rendered pack markdown

What to learn:

- load small, canonical, structured context first
- load heavier assets only when the user flow or operation truly needs them
- make the loading order explicit and deterministic

What not to do:

- do not build a generic RAG memory loader now
- do not delay biomedical search/screening/extraction work to invent a universal context tier system
- do not load translated or convenience summaries before canonical evidence state in decision-making paths

PaperPipe-specific implication:

- future context-loading work should be framed as "state-first, artifact-second, PDF-last"
- this especially fits `/papers/:slug`, Workbench evidence review, and Meeting Pack source resolution

### 3.3 Observable retrieval trajectory

Fit:

- very strong fit
- high future value

This is the most immediately useful OpenViking-inspired idea.

PaperPipe already has partial retrieval observability:

- `Research DNA` keeps append-only logs
- Meeting Pack source resolution is deterministic and selector-based
- Meeting Pack already exposes evidence refs and source item lineage
- runtime job execution is observable, but current event logging is still file/log centric

What is still missing:

- a normalized retrieval trace showing which sources were considered, selected, skipped, or rejected
- a stable explanation of load order across paper state, note body, screening context, profile projection, and artifacts
- a first-class trace object for user-visible context assembly

What to learn:

- retrieval should not be a black box
- future loading/resolution paths should emit an inspectable trajectory
- trajectory should be grounded in actual selectors, paths, ids, and rejection reasons

What not to do:

- do not build a generalized retrieval debugger UI now
- do not create a new observability subsystem before core search/screening/extraction reliability is higher

PaperPipe-specific implication:

- future retrieval observability should start with deterministic source traces, not semantic black-box traces
- the natural first targets are:
  - Meeting Pack source resolution
  - note detail context assembly
  - Workbench note-backed evidence loading
  - `Research DNA` projection-backed profile resolution

### 3.4 Long-term task memory and context consolidation

Fit:

- moderate conceptual fit
- high risk if over-expanded

PaperPipe already has bounded forms of long-term task memory:

- `Research DNA` append-only logs
- version snapshots
- paper-scoped `state.json` as a merged structured state
- per-run raw JSON under `.pp/<slug>/runs/`

This means PaperPipe does not need a broad "agent memory" project first.

What to learn:

- consolidation is useful when it compresses repeated operational context into explicit, inspectable state
- consolidation should produce bounded summaries on top of canonical logs, not replace them

What not to do:

- do not introduce a general conversational memory layer
- do not let downstream drafts become canonical memory
- do not overwrite append-only research logs with compact summaries

PaperPipe-specific implication:

- if future consolidation is added, it should likely be:
  - additive summaries on top of `Research DNA` logs
  - additive digests on top of paper `state.json`
  - additive retrieval traces on Meeting Pack and note-loading paths
- it should not become a free-form memory store that competes with canonical research state

## 4. Where This Reference Applies

This reference should only influence future design in these bounded places:

- `research_dna/`
- `.pp/<slug>/state.json`
- `storage/meeting_packs/<pack_id>/`
- claim/evidence asset loading under `storage/artifacts/`
- future context-loading strategy
- future retrieval observability

This reference should not currently influence:

- biomedical search quality policy
- screening decision policy
- claim/evidence truth policy
- inclusion/exclusion decisions
- current core extraction pipeline contracts

## 5. Priority and Non-Adoption Guardrails

Priority order remains:

1. biomedical search quality
2. screening reliability
3. extraction and evidence grounding
4. contract hardening
5. only then broader context-loading and retrieval observability work

Explicit non-adoption guardrails:

- do not vendor or integrate OpenViking now
- do not redesign PaperPipe around an OpenViking-like runtime
- do not create a new storage engine or virtual filesystem layer
- do not replace current `Research DNA`, `state.json`, or Meeting Pack storage contracts
- do not let this reference preempt core evidence/search/screening work

## 6. Recommended Future Direction

If this reference is used later, use it in this order:

1. formalize tiered load order on top of current roots
2. add retrieval trace objects to deterministic source resolution paths
3. add bounded consolidation summaries above append-only logs and canonical state
4. only revisit broader context architecture if the above proves insufficient

That sequence is intentionally conservative.

It lets PaperPipe learn from the reference without becoming a different system.

## 7. Current Decision

As of 2026-03-17:

- OpenViking is a useful reference, not an implementation dependency
- the strongest transferable idea is observable retrieval trajectory
- the second strongest is explicit tiered loading on top of current roots
- filesystem hierarchy is already largely aligned with PaperPipe's existing direction
- long-term memory should stay bounded and subordinate to canonical research state

No implementation work is implied by this note.

If future work is opened from this reference, it should be scoped as a small PaperPipe-native PR, not as an adoption effort.
