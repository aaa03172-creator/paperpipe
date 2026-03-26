# Docs, References, And Implementation Alignment Review

Status: Active review note  
Date: 2026-03-24  
Owner: Runtime/design maintainers  
Scope: active docs, key review notes, reference interpretations, and current runtime implementation

## Purpose

Check whether the current PaperPipe/Lattice story is internally coherent across:
- active canonical docs
- active release-bar and readiness notes
- recent reference reviews
- parked future ideas
- current runtime routes, storage, and DB/state layers

This note is not a new runtime spec.

## Executive Call

Current repo direction is more coherent than it looks at first glance.

The current center of gravity is consistent across most newer materials:
- paper-first
- paper/job/artifact-first
- local-first
- operator-reviewable
- bounded around `papers`, `jobs`, `artifacts`, paper-note structured state, `Research DNA`, and `Meeting Pack`

The main alignment risk is not reference sprawl anymore.

The main alignment risk is that the top-level master spec still contains older broader wording and older contract examples, while the newer active docs and runtime have already converged on a narrower and more defensible product shape.

## 1. What Is Currently Aligned

### A. Product shape

These sources now point in the same direction:
- `docs/Product_Positioning_Principles.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

Shared conclusion:
- current product shape is paper-first
- current runtime center is papers/jobs/artifacts plus bounded downstream artifact families
- `Project`, memory/chat, and broad workspace/platform ideas are not active runtime truth

Why this matters:
- this is now strong enough to guide roadmap and release-bar decisions without pulling in future workspace scope

### B. Runtime surface

Current implementation matches the narrower product story:
- `frontend/src/App.tsx` exposes `/papers`, `/meeting-packs`, `/method-comparisons`, `/chart-packs`, `/image-evidence`, `/protocol-cards`, and `/workbench/:paperId`
- `backend/main.py` exposes paper/job/artifact routes, `Research DNA`, bounded artifact routers, and a stub-only `/api/chat`
- `src/db_utils.py` centers on `jobs`, `execution_runs`, `job_events`, and `user_actions`

Shared conclusion:
- the live runtime is not project-first
- the live runtime is not memory-first
- the live runtime is not a generalized documents/workspace platform

### C. Reference interpretation

The current reference review layer is also internally consistent:
- `docs/REFERENCE_REVIEW_ROUND2.md`
- `docs/archive/External_Reference_Fit_Review_2026-03-18.md`
- `docs/reports/Product_Document_Final_v2_Review_2026-03-24.md`

Shared conclusion:
- external systems are useful as packaging references, sidecars, fallbacks, benchmarks, datasets, or vocabulary
- they are not migration targets
- they must not reopen product shape by momentum

### D. Future ideas are now better parked

Recent parked/future notes are also coherent with the active runtime boundary:
- `docs/archive/Prompt_Review_Parked_Useful_Items_2026-03-23.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`

Shared conclusion:
- `Project` remains a future owner candidate, not active runtime truth
- `Project Memory` remains backend-only
- decision/open-question/experiment object families remain useful but unapproved

## 2. Where Drift Still Exists

### A. The master spec still reads older and broader than the current repo story

`docs/Lattice_v3_Master_Spec.md` is still the top-level SSOT in `docs/README.md`, but parts of it reflect an older broader phase.

Most important drift points:
- the opening framing still reads like a broad “integrated research system”
- section `1.2` still uses a strong Zotero/Obsidian “unique storage” framing that underplays the current PaperPipe-owned canonical structured layer
- section `4.2` still describes raw `storage/artifacts/{paper_id}/{run_id}/` pathing, while `src/services/runtime_paths.py` now preserves backward compatibility but prefers canonical segmented artifact-paper paths
- the headline architecture still hardcodes older engine/tool assumptions such as `effGen`, `Ollama`, `ChromaDB`, and `PythonREPL` as if they were the main way to explain the product/runtime, while newer docs emphasize the bounded contract and runtime surfaces first
- sections `15.2` and related hardening language contain older acceptance/performance targets that are not the same as the newer release-bar language

Why this matters:
- because the master spec is still cited as top-level SSOT, old wording there can override newer, more accurate guardrails in practice

### B. Canonical ownership language is newer in reports than in the master spec

Newer docs now implicitly or explicitly treat the current canonical structured layer as including:
- paper-sidecar state
- run/event/user-action state
- `Research DNA`
- bounded derived artifacts

But the master spec still foregrounds:
- Zotero as SoT for source data
- Obsidian as knowledge destination

That older split is not fully wrong, but it is incomplete for the current repo.

Why this matters:
- it can make PaperPipe’s own structured layer look like an implementation detail instead of a first-class canonical layer

### C. Runtime path examples are newer in code than in top-level documentation

Current implementation:
- `src/services/runtime_paths.py`
- `src/services/paper_ops_summary.py`

Current reality:
- artifact roots are managed through runtime-path helpers
- artifact paper directories now preserve backward compatibility while preferring normalized identity segments

Older doc wording:
- raw `storage/artifacts/{paper_id}/{run_id}/`

Why this matters:
- pathing is part of provenance and recovery; stale path examples create avoidable confusion

### D. Release-bar logic is accurate but still report-local

The newer release story is well-shaped in:
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

But those are still reports, not canonical spec patches.

Why this matters:
- the repo now has the right launch story, but it still depends on people remembering to read the newer reports instead of only the master spec

## 3. Current Implementation-Intent Ledger

This is the cleanest current interpretation of “what the repo is trying to be.”

### Launch-defining core

Treat these as the actual first-product center:
- paper ingestion and deep-read/job pipeline
- paper-sidecar structured state and paper-notes/workbench review
- `Research DNA` search-design loop
- `Meeting Pack` as the required downstream anchor artifact
- provenance/uncertainty/non-destructive rerenderability as product identity

Anchors:
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

### Shippable bounded extensions

Treat these as real product-adjacent lanes, but not the launch-defining center:
- `Method Comparison`
- `Chart Pack`
- `Protocol Knowledge`
- `Image Evidence`

Anchors:
- `docs/METHOD_COMPARISON.md`
- `docs/CHART_PACK.md`
- `docs/PROTOCOL_KNOWLEDGE.md`
- `docs/IMAGE_EVIDENCE.md`

### Gated or internal-only

Treat these as implemented or partially implemented but intentionally not part of current product truth:
- `Project Memory`
- `/api/chat`

Anchors:
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `docs/API_CHAT_CONTRACT.md`

### Parked future ideas

Treat these as valuable but not currently promotable:
- first-class `Project` owner
- project/decision/experiment link families
- first-class decision / open-question / blocked-reason objects
- generalized experiment data and negative-result capture
- unified why-changed / diff / sign-off layer

Anchor:
- `docs/archive/Prompt_Review_Parked_Useful_Items_2026-03-23.md`

## 4. Reference Status Recheck

Current reference posture is healthy.

The repo now has a clear enough interpretation rule:
- `keep`: only when the idea clearly improves a bounded current lane
- `adapt`: only as a small local pattern
- `park`: when strategically useful but ahead of the runtime
- `reject`: when it implies framework/platform drift

Current best examples:
- `anthropics/skills` -> packaging pattern only
- `planning-with-files` -> working-file discipline only
- `deer-flow` -> vocabulary/reference only
- `taste-skill` -> UI guardrail only
- `UI-Friend-MCP` -> optional local tooling only
- parser/retrieval/note-memory references -> fallback/benchmark/reference slots only

This is a good state.
The repo no longer appears vulnerable to reference-driven overengineering by default.

## 5. Recommended Interpretation Going Forward

If someone asks “what is PaperPipe right now?”, the clean answer should be:

> PaperPipe/Lattice is currently a local-first, paper-first, artifact-first biomedical evidence workspace built around papers, jobs, structured paper state, reproducible search design, and evidence-linked downstream artifacts such as Meeting Pack.

If someone asks “what is not true yet?”, the clean answer should be:

- not project-first runtime
- not broad workspace memory platform
- not generalized protocol or experiment operating system
- not chat/copilot product

## 6. Recommended Doc Actions

### 1. Patch the master spec before creating any new big document

Highest-value doc action:
- tighten `docs/Lattice_v3_Master_Spec.md` so it stops sounding broader and older than the current runtime

Most important patch targets:
- opening product framing
- section `1.2` ownership language
- section `4.2` artifact path examples
- acceptance/release language that should now point to the newer product-bar/release-checklist interpretation

### 2. Keep current reports as guardrails, not replacement SSOTs

Do not promote every report into a new top-level doc.

The current report family is doing the right job:
- release-bar and readiness logic
- product-doc triage
- deferred-lane gate notes
- bounded-layer promotion notes

### 3. Keep future ideas parked until a runtime owner exists

Do not promote:
- `Project`
- decision/open-question objects
- experiment objects
- broad memory lanes

until code, storage, API, and UI all justify them together.

## 7. Conclusion

Current repo state is more aligned than fragmented.

The story that now holds across docs, references, and implementation is:
- preserve the paper/job/artifact center
- preserve local inspectability and evidence linkage
- grow through bounded artifact families
- keep future workspace/project/memory ideas parked until there is real owner evidence

The one place still most likely to confuse future work is the master spec.

If we fix that, the current PaperPipe/Lattice narrative becomes substantially cleaner without any architecture redesign.
