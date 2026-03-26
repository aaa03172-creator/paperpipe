# Canonical Objects, Scope Cut, and Supported Journey

Status: Active integration note  
Date: 2026-03-24  
Owner: Runtime/product maintainers  
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

## Purpose

Compress three already-reviewed questions into one repo-grounded note:

1. what the actual current canonical objects are
2. what belongs in `now`, `later`, and `not this product`
3. what a single biomedical researcher journey is that the current repo can honestly support

This note is not a new spec.
It is an integration layer across the current canonical stack.

## 1. Actual Current Canonical Objects

The current repo does not have one giant canonical graph.
It has a smaller paper/job/artifact-centered runtime with a few bounded canonical objects and several bounded derived lanes.

### 1.1 Core canonical structured state

| Object | Current owner | Current storage / contract | Status | Why it counts as current canonical truth |
| --- | --- | --- | --- | --- |
| `StructuredPaperState` | PaperPipe runtime | `vault/.pp/<slug>/state.json`; `src/schemas/skills.py`; `GET /paper-notes/{slug}` | `implemented, green on current rerun path but uneven legacy coverage` | This is the note-side canonical state used by paper-note detail and note-backed review surfaces when present. |
| job / run / event trail | PaperPipe runtime | `jobs`, `execution_runs`, `job_events`, `user_actions`; `src/db_utils.py` | `implemented` | This is the audit backbone for what ran, when it ran, and what happened. |
| `ResearchDNA` | PaperPipe runtime | `src/profiles/research_dna_schema.py`; `src/profiles/research_dna_service.py`; `docs/RESEARCH_DNA.md` | `implemented` | This is the bounded canonical search-design asset with `DRAFT -> PILOT -> LOCKED`. |

### 1.2 Current canonical runtime metadata surfaces

| Surface | Current owner | Current storage / contract | Status | Why it matters |
| --- | --- | --- | --- | --- |
| paper-note index metadata surface | PaperPipe runtime | `src/schemas/paper_notes.py`; `backend/routers/paper_notes.py`; `GET /paper-notes` | `implemented projection` | This is the current list/detail entry surface for note-backed paper review, including ops summary and saved-state presence, but it is a runtime projection over note and sidecar-backed state rather than a separate truth root. |

### 1.3 Current bounded derived objects

These are real and implemented, but they are not the primary source of truth.

| Object family | Current role | Current contract | Status | Why it is bounded rather than canonical root |
| --- | --- | --- | --- | --- |
| `MeetingPack` | downstream meeting draft | `src/schemas/meeting_pack.py`; `docs/MEETING_PACK.md` | `implemented` | It is a saved derived artifact with trace/readiness/regenerate rules, not the root truth store. |
| `Method Comparison` | evidence-linked comparison artifact | `src/schemas/method_comparison.py`; `docs/METHOD_COMPARISON.md` | `implemented` | It is a bounded comparison family derived from current paper-side evidence state. |
| `Chart Pack` | downstream numeric visualization artifact | `src/schemas/chart_pack.py`; `docs/CHART_PACK.md` | `implemented` | It is an artifact bundle, not a general data platform backbone. |
| `Image Evidence` | image-sidecar review artifact | `src/schemas/image_evidence.py`; `docs/IMAGE_EVIDENCE.md` | `implemented` | It remains a bounded metadata-first lane with warnings and handoff refs. |
| `Protocol Knowledge` / `ProtocolCard` | version-first protocol reference artifact | `src/schemas/protocol_card.py`; `docs/PROTOCOL_KNOWLEDGE.md` | `implemented` | It is a bounded protocol-reference lane, not a top-level project/protocol database. |

### 1.4 Current non-canonical but important source/mirror layers

| Layer | Current role | Why it is not the canonical owner |
| --- | --- | --- |
| Zotero / PDFs / raw note content | source data origin | They provide source metadata, files, and imported context, but PaperPipe owns runtime structured state. |
| Obsidian note body / frontmatter | note mirror and operator-facing file surface | It is a human-facing note/export surface, not the owner of run audit or all structured truth. |

### 1.5 Objects that are still not current canonical roots

These are either partial, gated, or future-only:

| Object | Current judgment | Why not current canonical root |
| --- | --- | --- |
| first-class `Project` | `future-only` | There is no approved project-first DB/API/UI/storage root in the current runtime. |
| repo-wide `Decision` object | `future-only` | Bounded decision-like signals exist, but not a stable cross-surface canonical object family. |
| repo-wide `Open Question` / `Blocked Reason` object | `future-only` | There are partial traces in bounded lanes, but not a stable current product object family. |
| generalized `Experiment` object | `future-only` | Current repo has adjacent artifact lanes, not a general experiment runtime model. |
| `Project Memory` as runtime product lane | `gated` | Backend/store exists, but active API/viewer adoption is explicitly blocked. |
| `/api/chat` as real product surface | `stub-only` | It remains a future hook, not current runtime truth. |

## 2. Scope Cut: Now / Later / Not This Product

### 2.1 Now

This is the current runtime and first-product truth.

| Area | Current standing | Current anchors |
| --- | --- | --- |
| paper-centered, paper-first, single-operator-first product shape | active now | `docs/Product_Positioning_Principles.md`; `docs/Lattice_v3_Master_Spec.md` |
| paper ingestion, jobs, runs, and artifact trail | active now | `backend/services/job_runner.py`; `src/db_utils.py` |
| note-backed paper review via `/papers` and `/papers/:slug` | active now | `backend/routers/paper_notes.py`; `frontend/src/app/pages/PaperNotesListPage.tsx`; `frontend/src/app/pages/PaperNoteDetailPage.tsx` |
| workbench-backed paper inspection | active now | `frontend/src/app/pages/AnalysisWorkbench.tsx`; `docs/WEB_VIEWER.md` |
| bounded `Research DNA` loop | active now | `docs/RESEARCH_DNA.md`; `src/profiles/research_dna_service.py` |
| `Meeting Pack` as the required downstream artifact anchor | active now | `docs/MEETING_PACK.md`; `backend/routers/meeting_packs.py` |
| provenance / uncertainty / visible system truth | active now | `docs/Evidence_and_Uncertainty_Rules.md`; `docs/Product_Positioning_Principles.md` |

### 2.2 Later

These are credible future candidates, but they are not current runtime commitments.

| Area | Current judgment | Why it is later |
| --- | --- | --- |
| first-class `Project` owner | later | Strategically useful, but current repo does not yet expose a project-first root. |
| project-oriented link types | later | Thin paper/run/claim/evidence ids cover current needs; project/decision/experiment link types would over-imply future object families. |
| repo-wide `Decision` / `Next Action` / `Open Question` / `Blocked Reason` | later | Useful research-workspace context, but still partial and fragmented across bounded lanes. |
| experiment data and negative-result capture | later | Important for the long-term product, but current repo only has adjacent bounded hooks. |
| unified why-changed / diff / sign-off layer | later | Valuable, but current pieces still live in bounded audit/review surfaces rather than one shared subsystem. |

Primary parking anchor:
- `docs/archive/Prompt_Review_Parked_Useful_Items_2026-03-23.md`

### 2.3 Not This Product

These should not define the current product or first shipped story.

| Area | Why it is out |
| --- | --- |
| generic `projects/documents` research platform | current positioning explicitly rejects this framing |
| broad workspace memory platform | would backdoor product-shape drift beyond the current paper-centered runtime |
| multi-user collaboration suite | not part of the current first-product assumption |
| chatbot-first or copilot-first product | the current runtime is not chat-first and `/api/chat` is stub-only |
| generalized protocol / experiment operating system | current bounded artifact lanes do not justify this product claim |
| system where output mode changes evidence truth | current trust policy explicitly forbids this |

Primary anchors:
- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`

## 3. Currently Supported Researcher Journey

The current repo can honestly support one bounded researcher journey.
It is narrower than a full project-memory or decision-workspace story, but it is real.

### 3.1 Supported journey: paper -> structured understanding -> reproducible search design -> meeting-ready artifact

| Step | What the researcher does | Source data in play | Canonical state touched | Derived output | Current judgment |
| --- | --- | --- | --- | --- | --- |
| 1. Start from a biomedical paper | open an indexed paper note or paper-backed route | note markdown, frontmatter, PDF/source metadata | paper-note index metadata surface; paper/job lookup surfaces | none yet | `implemented` |
| 2. Run or inspect deep-read output | inspect whether the paper has saved structured state and artifact/run backing | artifact bundle files, note-side sidecar if present | `StructuredPaperState`; run/job/event trail | claimset/stats/document artifacts | `implemented, green on the bounded current release slice; legacy bundles remain outside that slice unless later backfilled` |
| 3. Review evidence and uncertainty | inspect the result in `/papers/:slug` or `/workbench/:paperId` | note body, references, context trace, claim/evidence state | note detail structured state; ops summary; workbench notebook state | review surface only | `implemented` |
| 4. Turn search intent into a reproducible asset | create, pilot, refine, and lock `Research DNA` | operator query/search-design inputs; screening actions | `ResearchDNA`; screening and approval audit | projected compatibility `Profile` may exist behind it | `implemented` |
| 5. Generate a meeting-ready downstream artifact | create or reopen a `Meeting Pack` from saved state/selectors | selected sources, note selectors, saved structured state | meeting-pack saved request, trace, readiness metadata | `Meeting Pack` markdown/json bundle | `implemented` |
| 6. Optionally use bounded extensions | inspect method/protocol/chart/image artifacts after the core loop | existing paper-side evidence or source bundles | bounded artifact-local saved metadata | Method Comparison / Chart Pack / Protocol Knowledge / Image Evidence | `implemented, not launch-defining` |

### 3.2 What the current journey does not honestly support yet

The current repo does not yet support this broader chain as a first-class canonical workflow:

- project-wide memory carried across many papers as one active runtime lane
- meeting-note ingestion that promotes canonical `Decision` and `Task` objects
- repo-wide `Decision -> Next Action -> Blocked Reason` object flow
- generalized experiment workspace coordination
- chat/copilot-led orchestration as the main user interface

### 3.3 Current realism check

The journey is real, but not fully green in every slice.

Most important current gap:
- the deep-read/job path is no longer blocked on the current representative rerun path, and older sampled papers now sit outside the bounded launch slice unless later backfilled; the remaining product-level yellow is rehearsal/trust confirmation rather than current-runtime deep-read viability

Current anchor:
- `docs/reports/Deep_Read_Release_Acceptance_Spot_Check_2026-03-24.md`
- `docs/reports/Fresh_Real_Paper_Deep_Read_Rerun_2026-03-24.md`
- `docs/reports/Deep_Read_Legacy_Bundle_Release_Boundary_2026-03-25.md`

## 4. Practical Use

Use this note when you need one short answer to:
- what the current repo actually treats as canonical
- what belongs in the first-product boundary vs future parking
- what operator journey the repo can truthfully demonstrate today

Do not use this note as:
- a replacement for `docs/Lattice_v3_Master_Spec.md`
- a reason to reopen `Project`, memory/chat, or generalized workspace lanes
- a shortcut around bounded lane specs such as `docs/RESEARCH_DNA.md` or `docs/MEETING_PACK.md`

## Bottom Line

Current PaperPipe/Lattice is best understood as:

> a local-first, paper-centered, paper-first, single-operator-first biomedical research workspace with a real paper/job/artifact core, bounded canonical search-design state, and at least one credible downstream artifact lane.

That is already enough to justify focused hardening.
It is not yet the same thing as a first-class project platform, a memory-first assistant, or a generalized research operating system.
