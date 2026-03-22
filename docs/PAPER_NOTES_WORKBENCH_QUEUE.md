# Paper Notes / Workbench Queue

Status: Active scoped queue  
Date: 2026-03-13  
Owner: Lattice runtime maintainers  
Canonical parent: `docs/WEB_VIEWER.md`

## Purpose
- Track only paper-notes, triage, rail, and workbench follow-up items.
- Keep this queue narrower than the repo-wide `docs/Pending_PR_Queue.md`.
- Record reopen conditions so speculative UX work does not get promoted without evidence.
- Keep flow-local micro-backlog in the matching `docs/UX_REVIEW_REPORT_<flow>.md`; use this queue for shared cross-surface follow-up only.

## Active

### P1 - Promote `issues_state` to a producer-level field
- Status: Partially implemented
- Why:
  - `/papers` now returns `issues_state`, and the backend will honor a stored explicit value when one exists.
  - legacy batch producer (`src/processor.py`) and watcher local producer (`src/watcher.py`) now write explicit `issues_state` from producer-owned `processing_status` and analysis availability.
  - Zotero sync now inserts new rows with `issues_state="unavailable"`.
  - It still falls back to `issues` / `issues_label` and legacy `status` when other producers do not write `issues_state`, so this is not yet a first-class repo-wide producer contract.
- Current evidence:
  - `flagged | clear | unavailable` works across `/papers`, triage, workbench, and rail.
  - batch ingestion and watcher local ingestion persist `clear` / `flagged` / `unavailable` explicitly when they own the analysis outcome.
  - newly synced `NEW` rows no longer masquerade as `clear`.
  - API/build/e2e coverage is green.
- Reopen only if:
  - another stable producer or artifact field can emit content-review state directly, or
  - `issues_label` wording starts changing often enough to make backend heuristics brittle.

## Deferred

### P2 - Add structured `review_flags[]` or richer taxonomy
- Status: Deferred
- Why not now:
  - Current source-of-truth is `issues` + `issues_label` + `issues_state`.
  - Verification/gate `reason_codes` are not the same contract and should not be projected into viewer UX without an explicit mapping source.
- Reopen only if:
  - `/papers` or note/artifact payloads directly expose structured review flags.

### P2 - Add list density presets
- Status: Deferred
- Why not now:
  - Current note volume does not justify another density control.
  - The existing row-card hierarchy is readable at the current scale.
- Reopen only if:
  - actual note volume or user testing shows scan speed degradation.

### P2 - Unify timeline/stepper grammar with operational state
- Status: Deferred
- Why not now:
  - timeline events, pipeline progress, and operational state represent different semantics.
  - forced visual unification would likely blur meaning rather than reduce load.
- Reopen only if:
  - actual user confusion is observed between these systems.

## Completed in current workspace
- `Content Review` and operational artifact health are visually and semantically separated.
- `issues_label` is preserved across triage, workbench notice/body, and selected rail context.
- `Unavailable` no longer masquerades as `Clear`.
- `/papers` now returns `issues_state`, and frontend uses it as the primary content-review state signal.
- legacy batch producer and watcher local producer persist explicit `issues_state` when they own analysis/gating output.
