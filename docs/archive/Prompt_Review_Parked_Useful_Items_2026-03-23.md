# Prompt Review Parked Useful Items (2026-03-23)

Status: Historical
Date: 2026-03-23
Owner: Runtime/design maintainers
Related active doc: `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`

## Purpose

Preserve useful ideas from broader architecture-prompt review that were intentionally **not** adopted into the active execution guide because they would overreach the current PaperPipe runtime.

This note is not a runtime spec.

Use it as:
- a revisit list
- a future-RFC seed list
- a guard against forgetting valuable ideas that are not yet safe to promote

## Why These Items Were Parked

Current runtime still centers on:
- `papers`
- deep-read `jobs`
- run `artifacts`
- paper note structured state
- bounded `Research DNA`
- bounded downstream artifact families

That means useful ideas should stay parked when they would require:
- a first-class `project` root that does not yet exist in approved runtime contracts
- a generic workspace DB surface
- a broad experiment platform
- a new cross-product memory/chat lane

Current repo anchors:
- `docs/Product_Positioning_Principles.md`
- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

## 1. Project As A Future Canonical Owner Candidate

### Why it is useful

The product direction still points toward a biomedical research workspace where papers, meeting outputs, and project judgments can eventually be linked under a durable project context.

This remains strategically useful because it would reduce cross-paper context fragmentation.

### Why it stays parked now

Current approved runtime does not expose a first-class `project` root across DB, API, UI, and storage contracts.

Promoting `Project` into the active architecture guide now would make the docs lead the codebase instead of reflect it.

### Reopen when

- the master spec approves a bounded project/workspace concept
- runtime storage has a durable project identity that is not just a local experiment
- API/UI gain an intentional project-scoped surface

### Smallest safe starting point

Do not rename the product around `Project` first.

Start with a bounded file/store slice plus explicit owner boundaries, then decide whether a route or UI surface is justified.

### Current repo anchors

- `docs/Product_Positioning_Principles.md`
- `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`
- `docs/reports/Project_Memory_API_Gate_2026-03-23.md`

## 2. Project-Oriented Link Types And Cross-Object Relations

### Why it is useful

The broader prompt was right that some future link types will matter:
- `belongs_to_project`
- `triggered_by_decision`
- `linked_to_experiment`

These relations would become useful once project/decision/experiment objects become first-class and repeated enough to justify shared linkage rules.

### Why it stays parked now

Current runtime can already cover most real linkage needs with:
- `paper_id`
- `paper_slug`
- `run_id`
- `dna_id`
- `pack_id`
- `claim_id`
- `evidence_id`

Adding project/decision/experiment link types now would imply object families that do not yet have stable ownership.

### Reopen when

- project-scoped objects are approved
- decision or experiment objects exist outside generated markdown copy
- repeated manual joins cannot be explained with the current thin-link taxonomy

### Smallest safe starting point

Extend the thin-link taxonomy only after the new owner object exists.

Do not create relation types first and hope the owner model appears later.

### Current repo anchors

- `docs/ARCHITECTURE_REFOCUS_EXECUTION_GUIDE.md`
- `src/schemas/skills.py`
- `src/schemas/meeting_pack.py`

## 3. Decision / Next Action / Open Question / Blocked Reason As First-Class Objects

### Why it is useful

These objects are genuinely useful for a research workspace because they preserve operational context that papers alone do not capture.

They are especially relevant for:
- project-progress reviews
- handoff between reading and meeting preparation
- surfacing what changed versus what remains blocked

### Why it stays parked now

Current repo has partial signals, but not a stable cross-surface canonical object family:
- Meeting Pack already renders `next steps`, `questions`, and blocked framing
- historical RFCs discuss project-scoped questions and decisions
- some approval and review state exists in bounded lanes

That is not yet the same as a repo-wide canonical `decision` or `open_question` model.

### Reopen when

- operators repeatedly need cross-paper carryover of decisions/questions outside a single artifact
- the same decision/open-question data is being duplicated across packs, notes, and queue docs
- a bounded project-scoped storage lane is approved

### Smallest safe starting point

Prefer a tiny additive hook first:
- artifact-local structured fields
- append-only log entries
- a bounded future bundle under an approved project/workspace slice

Do not start with a generic task manager or broad workspace schema.

### Current repo anchors

- `src/schemas/meeting_pack.py`
- `src/meeting_packs/service.py`
- `docs/archive/Project_Memory_Layer_RFC_2026-03-18.md`

## 4. Experiment Data And Negative-Result Capture

### Why it is useful

For a biomedical workspace, structured experiment or result capture is valuable because downstream reasoning often depends on:
- assay context
- model system
- intervention/comparator framing
- negative or null findings

This would eventually make PaperPipe less paper-summary-centric and more research-workspace-capable.

### Why it stays parked now

Current repo has bounded adjacent layers, not a general experiment data model:
- `Method Comparison`
- `Chart Pack`
- `Protocol Knowledge`
- paper-level claim/evidence state

Those layers show where experiment-related structure could attach, but they do not yet justify a new top-level experiment subsystem.

### Reopen when

- chart/method/protocol work repeatedly needs the same experiment fields
- negative-result capture becomes a repeated workflow gap
- operators need stable structured experiment context beyond a single artifact family

### Smallest safe starting point

Start with bounded schema hooks in existing artifact lanes or paper-sidecar state.

Do not open a generic experiment platform, ontology, or new top-level DB surface first.

### Current repo anchors

- `src/schemas/method_comparison.py`
- `docs/CHART_PACK.md`
- `docs/PROTOCOL_KNOWLEDGE.md`

## 5. Unified Why-Changed / Diff / Sign-Off Layer

### Why it is useful

The broader prompt was right to emphasize:
- version diffs
- why-changed history
- sign-off points
- failed and negative outcomes

These make reproducibility and operator trust much stronger.

### Why it stays parked now

Current repo already has pieces of this, but they are distributed:
- `Research DNA` revision and approval audit
- `search_eval/.../diff.json`
- `accepted` flags in bounded review loops
- `issues_state`
- failed job/run statuses

That means the idea is valuable, but a new unified layer would currently be more naming than runtime.

### Reopen when

- operators repeatedly need one place to answer “what changed and why”
- cross-surface audits become difficult with current distributed logs
- multiple bounded features converge on similar sign-off semantics

### Smallest safe starting point

Prefer one shared audit-summary shape or artifact validation summary before inventing a new global change-management subsystem.

### Current repo anchors

- `docs/RESEARCH_DNA.md`
- `src/profiles/research_dna_schema.py`
- `storage/search_eval/`
- `src/db_utils.py`
- `src/schemas/papers.py`

## 6. Cross-Surface Citation Trace / Contradiction / Stale-Artifact Hardening

### Why it is useful

This is one of the most practically valuable parked themes.

PaperPipe already cares about:
- evidence lineage
- visible uncertainty
- not silently hiding conflict
- preferring canonical sidecar state over stale artifacts

A more unified cross-surface validation view would strengthen that direction without changing product shape.

### Why it stays parked now

The capability is partial and fragmented:
- Meeting Pack surfaces conflict and uncertainty
- Method Comparison preserves `conflict` and `missing`
- viewer/workbench already prefers canonical sidecar data over stale artifact fallback

What is missing is not a whole new platform, but a narrower shared validation surface.

### Reopen when

- the same trace/conflict/stale checks are reimplemented across multiple artifact families
- operators need a common “citation trace / contradiction / freshness” inspection path
- downstream artifacts become harder to trust without a shared validation contract

### Smallest safe starting point

Prefer:
- a shared artifact validation summary
- a shared trace panel contract
- additive freshness/staleness fields

Do not start with a new graph DB, contradiction engine, or generic provenance dashboard.

### Current repo anchors

- `docs/Evidence_and_Uncertainty_Rules.md`
- `docs/MEETING_PACK.md`
- `docs/METHOD_COMPARISON.md`
- `docs/WEB_VIEWER.md`

## What Not To Reopen From This Note

Still not recommended from this parked list:
- a general chat-memory platform
- a giant workspace framework
- a first move toward a broad experiment ontology
- project-first renaming of the active runtime
- relation types without first-class owner objects

## Revisit Rule

If one of these items is reopened later, do it by:

1. writing a dated bounded RFC or gate note
2. proving the current runtime pain with repo-grounded evidence
3. proposing the smallest additive schema/store change first
4. checking compatibility impact before any API or UI expansion
