# First Shippable Product Bar

Status: Active decision note  
Date: 2026-03-24  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/WEB_VIEWER.md`
- `docs/Pending_PR_Queue.md`

## Purpose

Set the first externally presentable product bar for the current repo without silently redefining the product around a future workspace/platform shape.

This note answers:
- what the first showable/shippable product should be
- what must be true before we present it as a coherent product
- what should stay out of the first product promise even if some code already exists

This is not a new master spec.

## Current First-Product Statement

The first shippable product for the current repo is:

> a local-first, paper-centered, paper-first, artifact-first, single-operator-first biomedical evidence workspace that lets a researcher go from paper ingestion and deep read to evidence-linked structured state, reproducible search-design refinement, and at least one meeting-ready downstream artifact without losing provenance or uncertainty.

In current repo terms, that means:
- paper-first
- artifact-first
- job/run/artifact-first
- human-reviewable
- additive rather than fully autonomous
- local inspectability over hidden orchestration

It does **not** mean:
- a first-class `project` platform
- a broad workspace memory system
- a generalized protocol/experiment operating system
- a chatbot-first product

## Why This Is The Right First Bar

This bar matches the current repo better than a broader workspace story.

Repo-grounded reasons:
- `docs/Product_Positioning_Principles.md` says the current best-fit shape is `paper-first`, `local-first`, `reviewable by a human operator`, and `additive rather than fully autonomous`.
- `frontend/src/App.tsx` exposes `/papers`, `/meeting-packs`, `/method-comparisons`, `/chart-packs`, `/image-evidence`, `/protocol-cards`, and `/workbench/:paperId`, but not `/projects`.
- `docs/RESEARCH_DNA.md` and `docs/MEETING_PACK.md` both describe real implemented lanes with API/service/store surfaces and explicit bounded semantics.
- `docs/Pending_PR_Queue.md` keeps `Project Memory` behind a backend-only hold and does not approve it as a first-class runtime surface.
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md` explicitly says opening a project API now would backdoor a product-shape decision the repo has not approved.

Implication:
- the first product should be defined around the already-coherent biomedical core loop
- newer bounded artifact families may be included, but they should not redefine the launch story

## Release-Defining Core Loop

The first product should be considered real only if this operator loop works end to end:

1. ingest a biomedical paper and run the deep-read/job pipeline
2. persist reusable local paper state with evidence and uncertainty preserved
3. inspect the result in the paper-notes/workbench surface
4. create and refine a `Research DNA` search design through `DRAFT -> PILOT -> LOCKED`
5. generate a downstream artifact from saved state, with `Meeting Pack` as the required anchor artifact
6. reopen, validate, rerender, or regenerate artifacts without silent corruption

If this loop is weak, no amount of extra bounded viewers makes the product ready.

## Minimum Deep Read Success Bar

For this release bar, `deep read succeeded` should mean the current runtime produced inspectable, reusable paper state rather than only finishing a background job.

Minimum acceptable bar:
- a real biomedical paper can be enqueued and processed through the current deep-read/job path
- the run leaves inspectable paper-scoped saved state at the current sidecar path, not only transient logs
- the saved state preserves the current minimum structured shape needed by viewer and downstream artifact surfaces:
  - `runs`
  - `signals`
  - `claimset`
  - `entities`
  - `mesh`
  - `outcomes`
- if claims are promoted, they remain evidence-linked or explicitly uncertainty-marked under the current evidence rules rather than silently upgraded into certainty
- if support is weak, partial, or missing, the system surfaces readiness/warning/issue state instead of reporting a false clean success
- the resulting state is inspectable through current paper-notes/workbench routes against real backend data
- reruns or follow-up artifact generation may fail or stay partial, but they must not silently corrupt saved state or leave hidden partial bundles behind

Current repo anchors:
- `docs/WEB_VIEWER.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/Evidence_and_Uncertainty_Rules.md`
- `backend/main.py`
- `src/services/paper_ops_summary.py`

## What Is Launch-Defining For The First Product

These lanes are required for the first externally presentable product story.

### 1. Paper ingestion, jobs, and local structured state

Required outcome:
- a paper can move through the existing ingest/deep-read path into saved local state and artifacts
- the run remains inspectable through the current paper/job/artifact model

Why required:
- this is the base truth-producing path for the rest of the product
- without it, everything downstream becomes mock-first or file-fragment-driven

Current anchors:
- `backend/services/job_runner.py`
- `src/jobs/queue.py`
- `src/db_utils.py`
- `docs/Current_Code_Baseline_Audit_2026-03-13.md`

### 2. Paper notes viewer/workbench

Required outcome:
- the operator can inspect paper detail, ops state, and workbench context through the existing viewer surfaces

Why required:
- the product promise is not just background processing
- the operator must be able to review what the system produced

Current anchors:
- `frontend/src/App.tsx`
- `docs/Lattice_Paper_Notes_Web_Viewer_Spec.md`
- `docs/WEB_VIEWER.md`

### 3. Research DNA

Required outcome:
- the operator can create a bounded search-design asset, run a pilot, record screening decisions, refine query versions, and lock the result
- the projected `Profile` compatibility surface may exist behind this flow, but it is not a separate launch-defining canonical product lane

Why required:
- this is the clearest current expression of reproducible biomedical search-design state
- it distinguishes the product from a plain paper reader

Current anchors:
- `docs/RESEARCH_DNA.md`
- `src/profiles/research_dna_schema.py`
- `src/profiles/research_dna_service.py`

### 4. Meeting Pack

Required outcome:
- the operator can generate an evidence-linked meeting draft from saved structured state and reopen/validate/rerender/regenerate it safely

Why required:
- this is the strongest current downstream artifact story in the repo
- it turns the structured evidence loop into something immediately useful for a researcher

Current anchors:
- `docs/MEETING_PACK.md`
- `src/schemas/meeting_pack.py`
- `src/meeting_packs/service.py`
- `backend/routers/meeting_packs.py`

### 5. Provenance, uncertainty, and non-destructive regeneration

Required outcome:
- claims, artifacts, and downstream outputs keep evidence lineage visible
- weak or conflicting support stays visible
- rerender/regenerate paths do not leave silently broken partial bundles behind

Why required:
- this is part of the product identity, not optional polish
- without it, the product becomes another summary generator

Current anchors:
- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/MEETING_PACK.md`
- `docs/Product_Positioning_Principles.md`

## Included But Not Launch-Defining

These lanes are real and worth shipping when green, but they should not be the first product promise.

### Shippable extensions

#### Method Comparison

Keep as:
- a strong bounded artifact family
- a useful demo extension after the core loop is credible

Do not use as:
- the main product identity

Anchor:
- `docs/METHOD_COMPARISON.md`

#### Chart Pack

Keep as:
- a downstream visualization artifact

Do not use as:
- evidence that the product is a generic data platform

Anchor:
- `docs/CHART_PACK.md`

#### Protocol Knowledge

Keep as:
- a bounded version-first reference lane

Do not use as:
- proof that the first product is a generalized project/protocol platform

Anchor:
- `docs/PROTOCOL_KNOWLEDGE.md`

#### Image Evidence

Keep as:
- a metadata-first sidecar

Do not use as:
- a new core truth layer or microscopy platform claim

Anchor:
- `docs/IMAGE_EVIDENCE.md`

### Gated, internal-only, or non-product surfaces

These may be implemented in part, useful internally, or worth showing as future direction, but they should not count toward first-product readiness.

#### Project Memory

Current state:
- backend file-store exists
- API/viewer surface is explicitly gated

Use as:
- bounded implementation reference only

Do not use as:
- evidence that the first product is already project-first

Anchors:
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`
- `src/schemas/project_memory.py`

#### `/api/chat`

Current state:
- future integration hook only
- still stub-only

Use as:
- future-facing integration seam only

Do not use as:
- evidence that the first product includes chat, memory, or copilot behavior

Anchors:
- `docs/API_CHAT_CONTRACT.md`
- `backend/main.py`

## Explicitly Out Of Scope For The First Product

Do not describe the first shipped product as including these:
- first-class `Project` runtime ownership
- `Project Memory` as an active API/viewer surface
- broad chat/memory/copilot product behavior
- generalized experiment workspace or decision workspace platform
- protocol authoring or lab execution runtime
- multi-user collaboration suite
- broad connector strategy as a launch requirement
- polished conversational cockpit as a prerequisite for usefulness

These may become later product decisions.
They are not required for the first credible release.

## First Product Quality Bar

The first product should be considered showable only if the following are true.

### A. Functional integrity

Must be true:
- the paper/job/artifact path works on real biomedical papers
- paper-notes and workbench surfaces open against real backend data
- `Research DNA` completes the bounded `DRAFT -> PILOT -> LOCKED` loop
- `Meeting Pack` generation works from real saved state and retains regenerate/rerender safety
- uncertainty, warnings, and conflicts remain visible instead of being flattened away

### B. Verification integrity

Must be true:
- current backend test suite is green, or the intentionally release-scoped backend verification set is green with no known P0 regressions
- `cd frontend && npm run build` is green
- the current viewer/artifact Playwright coverage for release-defining surfaces is green
- `./scripts/run_meeting_pack_verify.sh` is green
- `python3 scripts/lint_docs.py` is green

Release-defining surfaces for verification:
- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`
- `/meeting-packs`
- `/meeting-packs/:packId`
- `Research DNA` backend/API/service flow

### C. Performance and operational bar

The first product should promise:
- reliable local completion
- visible long-running work
- safe reruns and recovery

It should **not** promise:
- instant analysis
- chatbot-like response speed
- full automation without operator review

Practical performance bar for the current first product:
- representative real-paper batches complete with high success under the current adaptive timeout policy
- failures are surfaced as warnings, partial status, or failed runs rather than silent corruption
- saved artifacts remain readable and recoverable after rerender/regenerate paths

Current performance evidence:
- `docs/reports/Local_Batch_Validation_2026-03-09_30_full_timeout_adaptive_precise_v6.md` recorded `29 completed`, `1 partial`, `0 timeout`, `0 error` on a 30-paper validation slice
- current baseline recheck recorded green Python runtime, frontend build, Playwright slices, and docs lint in `docs/reports/Current_Baseline_Recheck_2026-03-18.md`

Interpretation:
- the first product bar should be framed as `operator-reliable within minutes`
- not as `real-time AI copilot`

### D. Trust bar

Must be true:
- evidence lineage is inspectable
- uncertainty is visible
- draft artifacts are clearly drafts
- there is no implied hidden truth store behind the UI
- the product can be explained using the current paper/job/artifact vocabulary without hand-waving

## Must-Not-Ship Conditions

Do not present the product as ready if any of these are true:
- the first demo requires explaining away missing provenance
- the first demo only works because an operator keeps narrating where the real truth actually lives, how to mentally reconstruct missing system state, or which hidden storage path to trust
- `Meeting Pack` works only through brittle fallback or mock data
- `Research DNA` cannot actually be piloted/refined/locked on a real example
- core viewer routes are only visually plausible but not real-backend-credible
- the product story depends on `Project`, memory, or chat surfaces that are still explicitly gated
- run failures or partial artifact writes can silently leave broken local state

## Suggested First Reveal Story

If we present the first version now, the story should be:

1. Start from a real biomedical paper.
2. Show that the system produces inspectable local paper state rather than a one-shot summary.
3. Show the operator reviewing evidence/uncertainty in the paper-notes or workbench surface.
4. Show `Research DNA` turning a search idea into a reproducible locked asset.
5. Show `Meeting Pack` turning saved state into a meeting-ready draft with visible evidence lineage.
6. Only then show bounded extras such as `Method Comparison` or `Chart Pack` as extensions, not as the core explanation.

## Product Line In One Sentence

The first externally presentable PaperPipe/Lattice product is:

> a local-first, paper-centered, paper-first, artifact-first biomedical evidence workspace built for a single-operator-first workflow, centered on papers, reproducible search design, and evidence-linked meeting preparation.

## Immediate Use

Use this note when:
- deciding whether a feature is launch-defining or a later bounded extension
- checking whether a roadmap item belongs in the first product bar
- pushing back on scope that would redefine the product around `projects`, memory, or chat before the current core loop is fully hardened

Do not use this note as:
- a route/schema contract
- a permission to widen the product shape beyond the current repo reality
