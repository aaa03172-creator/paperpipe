# Paper Notes / Workbench Midpoint Checkpoint

Status: Recorded checkpoint  
Date: 2026-03-13  
Reviewer: Codex  
Scope: `/papers`, `/papers/:slug`, triage, rail, workbench content-review and operational-state surfaces

## Why this checkpoint exists
- The viewer/workbench slice no longer has an immediate runtime blocker.
- The main remaining risks are scope control, contract ownership, and avoiding speculative UX work.
- This checkpoint records which forks were reviewed and which were intentionally not taken.

## Multi-perspective review

### Runtime perspective
- Current paper-notes/workbench flows are stable enough for continued use.
- Verified in the current workspace:
  - `pytest -q tests/test_papers_api.py tests/test_paper_notes_api.py`
  - `cd frontend && npm run build`
  - targeted backend Playwright coverage around content review and operational summaries

### UX perspective
- `Content Review` and `Operational State` are now distinct signals.
- `flagged`, `clear`, and `unavailable` behave consistently across triage, workbench, and selected rail context.
- `Unavailable` is explicit, so `Not analyzed` no longer reads as `Clear`.

### Architecture perspective
- `/papers` and `/papers/{paper_id}` now expose `issues_state`.
- This reduced frontend heuristic drift. Backend now prefers a stored explicit `issues_state` when present, and the legacy batch producer plus watcher local producer write it directly from producer-owned processing results. Other paths still fall back to `issues` / `issues_label` plus legacy `status`, and Zotero sync inserts fresh rows as `unavailable` so they do not masquerade as `clear`.
- Current state is acceptable, but not yet the final contract shape.

### QA perspective
- The paper-notes/workbench slice has green API/build/e2e coverage for the recent changes.
- The remaining QA risk is process-related: wide unrelated workspace churn makes future regression isolation harder.

### Operations perspective
- The repo-wide `docs/Pending_PR_Queue.md` has expanded beyond viewer/workbench concerns.
- A scoped queue is now necessary to keep paper-notes/workbench follow-up items reviewable.

## Decisions reviewed and locked

### Decision 1 - Keep `issues_state`, but do not over-extend it yet
- Decision: keep the new `issues_state` contract in place.
- Why:
  - It is already reducing frontend ambiguity.
  - It is small enough to maintain without inventing richer taxonomy.
- Not chosen:
  - immediate `review_flags[]` or taxonomy expansion
- Reopen when:
  - additional producer/artifact payloads emit structured content-review fields directly.

### Decision 2 - Do not add density presets now
- Decision: defer list density controls.
- Why:
  - current evidence does not show a scanning problem large enough to justify new controls.

### Decision 3 - Do not force timeline/stepper grammar unification now
- Decision: defer shared grammar work for timeline/stepper.
- Why:
  - these surfaces represent different meanings and currently benefit from staying separate.

### Decision 4 - Split scoped tracking from the repo-wide queue
- Decision: add `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`.
- Why:
  - shared viewer/workbench follow-up items should not compete with unrelated repo tracks in the same working queue.
  - flow-local trigger backlog can stay in the matching UX review report until it becomes a cross-surface concern.

## Current recommended next step
- Do not open new viewer/workbench UX work by default.
- Reopen only scoped items with explicit trigger evidence from `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`.
- Keep list/detail/actions-only trigger backlog in the matching UX review report until it crosses surfaces.
- If a new cross-surface change touches triage, rail, workbench, or shared `/papers` contracts, update both:
  - `docs/UX_REVIEW_REPORT_paper-notes-viewer.md`
  - `docs/PAPER_NOTES_WORKBENCH_QUEUE.md`
