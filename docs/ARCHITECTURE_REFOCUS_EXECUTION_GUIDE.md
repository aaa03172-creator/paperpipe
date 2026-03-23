# Architecture Refocus Execution Guide

Status: Active
Date: 2026-03-23
Owner: Runtime/design maintainers
Canonical: `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

Related docs:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/PERSONA_MODE_BOUNDARY.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/CHART_PACK.md`
- `docs/API_CHAT_CONTRACT.md`
- `docs/REFERENCE_REVIEW_ROUND2.md`
- `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`

## Purpose

Use this guide when PaperPipe needs a repo-grounded architecture/ownership/linkage/priority re-check without reopening product shape or importing a new platform model.

This guide exists to keep that work:
- audit-first
- additive
- repo-grounded
- small enough to turn into real PRs

It is not a replacement for the runtime spec.

## Use This Guide When

- current code/docs feel misaligned and need a bounded refocus pass
- ownership between source data, canonical structured state, and derived artifacts needs clarification
- linkage, provenance, lifecycle, or priority ordering needs cleanup
- a new external proposal/prompt risks pulling the repo into a broader redesign

## Do Not Use This Guide For

- creating a new master spec
- forcing a project-first runtime without code evidence
- opening a general memory/chat platform lane
- broad UI redesign or unrelated refactors
- reference-driven architecture resets

## Current Repo Baseline

Treat these as the active runtime centers unless the audit proves otherwise:

1. Paper-facing runtime
- `papers`
- deep-read `jobs`
- run `artifacts`
- Obsidian note state and mirror

2. Search-design lane
- `Research DNA`
- `ResearchDNA -> Profile` compatibility projections

3. Downstream bounded artifact lanes
- `Meeting Pack`
- `Chart Pack`
- `Image Evidence`
- `Method Comparison`
- `Protocol Card`

4. Product positioning
- product may serve small lab/project contexts
- current runtime shape is still paper/job/artifact-first, not generic `projects/documents`

## Hard Boundaries

### 1. Project is not assumed to be first-class

Do not begin with “Project is the top-level canonical owner.”

Instead:
- audit whether a first-class project entity actually exists in code, storage, API, and UI
- if not, document `Project` as a future RFC or positioning direction only
- do not force current paper/run/artifact state under a new project root by documentation alone

### 2. Memory stays future-facing unless explicitly reopened

For this workflow:
- memory may be discussed only as a bounded future integration point
- no new first-class memory schema/API/runtime should be proposed unless the task explicitly reopens that lane
- `/api/chat` stub-only status remains a hard boundary

### 3. Prefer existing canonicals over new top-level docs

Default output shape:
- one dated audit/refocus note
- minimal patches to existing canonical docs

Create a new top-level active doc only if the content cannot fit cleanly into:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/RESEARCH_DNA.md`
- `docs/MEETING_PACK.md`
- `docs/CHART_PACK.md`
- `docs/README.md`

### 4. Reference review is delta-only

Do not reopen broad external reference review from scratch unless the audit shows the repo has changed enough to alter an earlier judgment.

Default reference baseline:
- `docs/REFERENCE_REVIEW_ROUND2.md`
- `docs/SKILLS_PACKAGING_GUIDE.md`
- `docs/archive/External_Reference_Fit_Review_2026-03-18.md`
- `docs/OpenViking_Reference_Fit_Review_2026-03-17.md`

## Phase A: Current-State Audit

Audit before proposing structure changes.

### Required checks

- directory roots and runtime path helpers
- active canonical docs and their current status
- API routes and actual runtime surfaces
- storage roots and file-backed state
- schema boundaries
- run/job/event provenance
- frontend routes and what is actually exposed

### Required surfaces to inspect

- `Research DNA` schema/store/service/API
- paper note structured state and its stable IDs
- claim/evidence artifact contracts
- job queue, execution runs, job events, user actions
- Meeting Pack source resolution and artifact contract
- Chart Pack / Image Evidence / Method Comparison bounded layers
- any existing `project` or `workspace` implementation evidence

### Audit output contract

Every implemented / partial / missing judgment must include:
- file path
- relevant symbol, route, or schema name when available
- 1-3 sentence explanation grounded in the repo

## Phase B: Bounded Clarification

Once the audit is done, clarify only what the current repo can actually support.

### Allowed clarification topics

- source data vs canonical structured state vs derived artifacts
- canonical owner and write authority
- sync/export/conflict rules
- thin link normalization
- lifecycle/state transitions
- priority reset
- biomedical hooks that fit current active schemas

### Disallowed moves

- renaming the entire architecture around `Project`
- inventing a new generic workspace DB surface
- moving existing paper/run/artifact truth into a new memory layer
- replacing existing bounded artifact roots with a new umbrella platform

## Canonical Owners To Start From

Use these as the default hypothesis.

### Source data layer

- Zotero metadata/export
- PDFs and attachments
- raw notes and imported files

### Canonical structured state layer

- paper-scoped note sidecar state: `.pp/<slug>/state.json`
- search-design state: `research_dna/<dna_id>/profile.yaml` plus logs/snapshots
- run/ops state: `jobs`, `execution_runs`, `job_events`, `user_actions`
- run artifacts under `storage/artifacts/<paper-segment>/<run_id>/`
- preserve legacy raw `paper_id` artifact directories when they already exist

### Derived artifact layer

- roots below may be absent until the first artifact of that type is materialized
- `storage/meeting_packs/<pack_id>/`
- `storage/chart_packs/<chart_pack_id>/`
- `storage/image_evidence/<image_evidence_id>/`
- `storage/method_comparisons/<comparison_id>/`
- `storage/protocol_cards/<protocol_id>/`
- Obsidian exports and rendered markdown

## Thin Link Guidance

Do not begin with a large knowledge graph.

Start by normalizing existing IDs and reuse paths that are already present:
- `paper_id`
- `paper_slug`
- `run_id`
- `dna_id`
- `pack_id`
- `claim_id`
- `evidence_id`

Recommended minimal link shape:

```json
{
  "source_object_type": "paper_state",
  "source_object_id": "wenzelShortchainFattyAcids2020",
  "relation_type": "derived_from",
  "target_object_type": "artifact_run",
  "target_object_id": "run_20260323T010203Z",
  "provenance_run_id": "run_20260323T010203Z",
  "created_at": "2026-03-23T01:02:03Z"
}
```

Recommended minimal `relation_type` taxonomy:
- `derived_from`
- `supports`
- `references`
- `selected_by`
- `generated_by`
- `linked_note`
- `projects_to`
- `uses_profile`

Only add a new taxonomy term when the existing set cannot express the relation clearly.

## Lifecycle Guidance

Prefer the smallest realistic state set already present in code.

### Research DNA

Keep the existing `DRAFT -> PILOT -> LOCKED` lane as primary unless code evidence justifies more.

### Screening

Keep decision-level `include | exclude | unclear` plus run linkage.

### Claim / evidence

Prefer additive state clarification around:
- extracted
- grounded / unresolved
- reviewed / accepted / rejected

Do not invent a much larger review state machine unless current code already uses it.

### Meeting Pack

Keep the existing draft/regenerate/rerender/readiness model rather than expanding into a general presentation workflow.

## Biomedical Hook Rule

Only propose biomedical hooks that fit current active lanes.

Good current candidates:
- `ResearchDNA.scope.population`
- `ResearchDNA.scope.intervention_or_exposure`
- `ResearchDNA.scope.comparison`
- `ResearchDNA.scope.outcomes`
- method-comparison fields such as `intervention`, `comparator`, `primary_readout`, `sample_size`
- active claim/evidence tags and outcomes already persisted in note state

If a hook only exists in legacy or isolated extraction code, mark it `partial` rather than promoting it into the active canonical layer automatically.

## Required Deliverables

Default deliverable set for this workflow:

1. Dated audit note
- recommended location: `docs/reports/Architecture_Refocus_Audit_<date>.md`

2. Minimal canonical doc updates
- update only the docs that truly need correction

3. Optional single bounded cross-cutting note
- only if the clarification cannot fit into existing canonicals cleanly

Avoid precommitting to a fixed set of new top-level docs before the audit is finished.

## Required Response Format

When executing this workflow, organize the output in this order:

1. Current state audit
- implemented
- partial
- missing
- duplicates or conflicts

2. Recommended architectural clarification
- data layers
- ownership
- write authority
- thin links
- lifecycle
- biomedical hooks

3. Priority reset
- `P0`
- `P1`
- `P2`
- each item tagged `doc-only`, `schema-only`, or `code-required`

4. Open decisions requiring human confirmation

5. PR-sized next steps
- 3-5 small follow-up PRs
- dependency order included

## Example Chains

### Example chain A: Search-design to downstream pack

`ResearchDNA profile`  
-> `pilot run`  
-> `screening log`  
-> projected profile  
-> paper `state.json`  
-> `meeting_pack.json`

### Example chain B: Deep-read to evidence-linked artifact reuse

`paper_id`  
-> `job_id` / `run_id`  
-> `claimset.resolved.json`  
-> stable claim/evidence IDs in `.pp/<slug>/state.json`  
-> `Chart Pack` or `Meeting Pack` evidence refs

## Adapted Execution Prompt

Use this prompt shape instead of a project-first or memory-first rewrite prompt.

```text
[TITLE]
PaperPipe architecture refocus: repo-grounded audit first, bounded clarification second

[ROLE]
You are a senior system reviewer working against the current PaperPipe repository.
You must read the current repo first and only make recommendations that fit the current runtime unless you explicitly mark something as a future RFC.

[WORKING MODE]
Phase A: Current-state audit
- inspect repo structure, active docs, storage roots, schemas, APIs, frontend routes, and runtime state
- classify implemented / partial / missing with path + symbol + short reason

Phase B: Bounded clarification
- clarify source data vs canonical structured state vs derived artifacts
- clarify owner, write authority, thin links, lifecycle, and priority
- prefer updates to existing canonical docs over creating new top-level docs

[HARD BOUNDARIES]
- do not assume Project is a first-class runtime owner unless code proves it
- treat project/workspace as future RFC if current runtime is still paper/job/artifact-first
- do not open a first-class memory/chat platform lane
- memory may appear only as a future integration appendix unless explicitly reopened
- reference review is delta-only; reuse existing fit reviews first
- no giant redesign, framework migration, or broad file moves

[CURRENT BASELINE TO RESPECT]
- paper note structured state under `.pp/<slug>/state.json`
- Research DNA under `research_dna/<dna_id>/...`
- run/ops state in `jobs`, `execution_runs`, `job_events`, `user_actions`
- run artifacts under `storage/artifacts/<paper-segment>/<run_id>/`, with legacy raw `paper_id` directories preserved when present
- bounded downstream artifact lanes such as Meeting Pack, Chart Pack, Image Evidence, Method Comparison, and Protocol Card

[OUTPUT]
1. Current state audit
2. Recommended architectural clarification
3. Priority reset with `doc-only` / `schema-only` / `code-required`
4. Open decisions requiring human confirmation
5. PR-sized next steps with dependency order

[SPECIAL RULES]
- normalize around existing IDs first: `paper_id`, `paper_slug`, `run_id`, `dna_id`, `pack_id`, `claim_id`, `evidence_id`
- if a concept exists only in a historical RFC or isolated legacy schema, mark it `future RFC` or `partial`
- if a recommendation would change product shape, say so explicitly and park it
```
