# Project / Queue Runtime Contract Scoping (2026-04-03)

## Goal
- Define the smallest runtime-backed next step for stronger `Project` or `Queue` UI in PaperPipe.
- Avoid extending the current home/workspace IA beyond what the repo can truthfully support today.

## Current runtime truth
- The frontend still has no project route or project workspace route.
  - Current top-level routes are home, papers, paper detail, workbench, and artifact families in [App.tsx](/Users/jangseongjin/paperpipe/frontend/src/App.tsx).
- The home screen is currently assembled from three existing surfaces:
  - `/health`
  - `/papers`
  - `/paper-notes`
  - See [TriageDashboard.tsx](/Users/jangseongjin/paperpipe/frontend/src/app/pages/TriageDashboard.tsx).
- The strongest home-facing paper signal is still paper-centric:
  - `PaperSummaryResponse` exposes `issues`, `issues_state`, `updated_at`, `ops_summary`, and `access_summary`
  - see [papers.py](/Users/jangseongjin/paperpipe/src/schemas/papers.py)
- The strongest note-facing signal is still note-centric:
  - `PaperNoteIndexItem` exposes `slug`, `structured_state_present`, `updated_at`, and `ops_summary`
  - see [paper_notes.py](/Users/jangseongjin/paperpipe/src/schemas/paper_notes.py)
- `ops_summary` is already the most useful queue-like operational signal:
  - it distinguishes `healthy` vs `action_needed`
  - and recommends `none`, `repair_stats`, or `open_workbench`
  - see [paper_notes.py](/Users/jangseongjin/paperpipe/src/schemas/paper_notes.py) and [paper_ops_summary.py](/Users/jangseongjin/paperpipe/src/services/paper_ops_summary.py)

## Existing project-like signals that are **not** yet home/runtime contracts
- There is storage-level `project_memory` infrastructure:
  - [project_memory.py](/Users/jangseongjin/paperpipe/src/schemas/project_memory.py)
  - [store.py](/Users/jangseongjin/paperpipe/src/project_memory/store.py)
- There are `project_note` references in meeting-pack source selection and `project_progress_update` output modes.
- But there is still no frontend-facing route, router, or API payload that turns these into a real home/project surface.
- So today, `project` exists as an internal/storage-adjacent concept, not as a stable UI/runtime contract.

## Judgment
- `Queue` should remain a derived operational lens for now.
- `Project` should remain deferred as a lightweight future context container, not promoted into UI rows or tabs yet.
- The next runtime step should be a **small summary contract**, not a full project system.

## What should stay deferred
- Fake `Active projects` rows on home
- A top-level `Projects` route without a project payload
- A heavier `Queue` container/route that pretends to own data
- Project-owned tabs for claims, decisions, experiments, or artifacts
- Multi-project paper membership semantics

## Recommended minimum contract sequence

### 1. Keep `Queue lens` derived until server-side queue logic is truly needed
- Current queue-like behavior is already expressible from:
  - `PaperSummaryResponse`
  - `PaperNoteOpsSummary`
  - optional note slug join
- Do **not** introduce a dedicated queue endpoint yet just to mirror current frontend sorting/filtering.

### 2. If home needs a stronger stable payload, add one small home/workspace summary contract
- Preferred direction:
  - add a compact backend summary payload instead of stretching `/papers` or `/paper-notes` with more home-only fields
- Suggested shape:

```ts
interface HomeWorkspaceSummary {
  saved_notes: number;
  structured_notes: number;
  needs_review: number;
  blocked: number;
  latest_note_updated_at?: string | null;
  note_context_limited: boolean;
}
```

- This simply formalizes what home already computes today.
- It does **not** create a project system.

### 3. Only add project summary UI after a real project summary payload exists
- The first acceptable project payload should stay lightweight:

```ts
interface ProjectSummaryLite {
  project_id: string;
  title: string;
  objective?: string | null;
  status: "active" | "archived";
  linked_paper_count: number;
  needs_review_count: number;
  blocked_count: number;
  updated_at: string;
}
```

- This should be treated as a **paper context** wrapper, not an object owner.
- The UI should not imply project ownership of claims/artifacts until the backend truly models that.

### 4. Keep initial paper-to-project semantics strict
- If project membership is added later, prefer:
  - `0 or 1 active project per paper`
- Do not start with multi-project paper membership.
- Do not duplicate artifact ownership upward into project summaries.

## Why this is the smallest product-correct next step
- The current UX gains came from:
  - clearer continuity
  - task-first language
  - more honest state boundaries
- The next mistake would be adding attractive project/queue chrome before the runtime can back it.
- A small summary contract preserves momentum without creating conceptual debt.

## Recommended next implementation trigger
- Re-open this only if one of these becomes true:
  - home needs server-owned counts because the client-side join becomes too fragile or too expensive
  - a real project list is ready to be shown on home
  - queue behavior requires backend-owned ordering/filter semantics rather than a frontend lens

## Explicit recommendation
- Do **not** build `Active projects` UI next.
- Do **not** build a new queue route next.
- If the repo needs another step soon, prefer one of:
  - `HomeWorkspaceSummary` backend contract
  - a tiny `ProjectSummaryLite` API backed by real project-memory exposure
