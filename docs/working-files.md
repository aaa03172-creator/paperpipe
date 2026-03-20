# Working Files Workflow

Status: Active
Date: 2026-03-17
Owner: Repository maintainers
Canonical: `docs/working-files.md`

Purpose: provide a lightweight file-based workflow for long multi-step work without creating a second spec, report, or queue system.

## When to use
- work expected to span many tool calls or multiple sessions
- work with several phases, forks, or reopen conditions
- work where findings, errors, and verification results need persistence between context shifts

Do not use this workflow for trivial one-shot edits.

## Non-goals
- not a new product/runtime SSOT
- not a replacement for `docs/Pending_PR_Queue.md`, scoped queues, `docs/reports/`, or `docs/archive/`
- not a Claude Code plugin or hook adoption path
- not a reason to copy external tool-specific command systems into this repo

## Task-local layout

Use one task-scoped folder per long-running item:

```text
.codex/work/<YYYY-MM-DD>_<slug>/
  plan.md
  findings.md
  progress.md
```

These files are task-local working memory and should stay untracked in git.

## File roles

### `plan.md`
- keep the goal, scope, non-goals, current phase, and next 1-3 actions
- record decision points, blockers, and reopen conditions
- re-read before major edits, architecture decisions, broad refactors, or after an interruption

Suggested shape:

```md
# Plan

Goal:
Scope:
Non-goals:
Current phase:

Next:
- ...
- ...

Open questions:
- ...
```

### `findings.md`
- store decision-relevant facts, not raw context dumps
- capture file paths, commands, constraints, contracts, and short source summaries
- note why each finding matters if that is not obvious

Suggested shape:

```md
# Findings

## Confirmed
- ...

## Constraints
- ...

## References
- ...
```

### `progress.md`
- append-only session log for changes, verification, failures, and next actions
- keep timestamps, commands, or exact artifact names when they help later recovery
- log errors explicitly so the same dead end is not retried blindly

Suggested shape:

```md
# Progress

## 2026-03-17 14:30
- Did:
- Verified:
- Errors:
- Next:
```

## Promotion rules

When information becomes durable, move or summarize it into the right long-lived home:

- canonical contract, policy, or workflow rule: existing canonical doc under `docs/`
- repo-wide follow-up item: `docs/Pending_PR_Queue.md`
- flow-specific follow-up item: matching scoped queue or UX review artifact
- dated validation, audit, or release evidence: `docs/reports/`
- historical checkpoint, fit review, or implementation plan: `docs/archive/`

Do not cite `.codex/work/...` files as SSOT.

## Operating loop
1. Create the task folder only when the work is large enough to justify it.
2. Write the first `plan.md` before deep implementation.
3. Add findings as they appear instead of keeping them only in chat context.
4. Append `progress.md` after meaningful verification, failure, or phase changes.
5. Re-read `plan.md` before major decisions and when resuming after context loss.
6. Promote durable outcomes into canonical docs, queues, reports, or archive before calling the work done.

## Relationship to existing workflows
- Use this alongside existing repo workflows, not instead of them.
- UI and flow work still follows `docs/ux-review.md` and the required `UX_REVIEW_*` artifacts.
- Runtime and feature work still belongs to the current FastAPI-first and Pydantic-first contracts.
- Queue, report, and archive documents remain the durable shared surfaces.
