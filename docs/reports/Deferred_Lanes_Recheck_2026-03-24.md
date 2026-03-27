# Deferred Lanes Recheck (2026-03-24)

Status: Active
Date: 2026-03-24
Owner: Lattice runtime maintainers
Canonical: `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`

## Purpose

Recheck the remaining deferred lanes after the recent bounded-spec promotions and decide whether any of them should reopen as implementation work now.

This is a current-state decision note, not a new runtime spec.

## Lanes reviewed

- `future/project-memory-api-v0`
- `future/local-backup-restore-semantics`

## Decision

Do not reopen either lane yet.

Current recommendation:
- keep `Project Memory` at backend-only file-store v0
- keep `local-backup-restore` as a deferred operations RFC plus gate note

## Why nothing should reopen now

### 1. The current repo just finished freezing bounded artifact families

Recent work promoted:
- `Method Comparison`
- `Chart Pack`
- `Protocol Knowledge`
- `Image Evidence`

Those lanes now have active bounded specs and implemented read/review surfaces.

The next safe move is not to open a new platform-shaped lane by momentum alone.

### 2. `Project Memory` still lacks a justified runtime surface

Current state:
- file-backed schema/store are implemented
- no tracked `Project Memory API` gate note is currently promoted on `master`

What is still missing:
- an approved bounded project/workspace concept in the current master spec
- repeated real workflows proving that project-scoped read/write access is needed now

So the correct state remains:
- backend-only hold

### 3. `local-backup-restore` still lacks honest shared guarantees

Current state:
- local branch retention exists
- DB backup-before-apply scripts exist
- bounded stores already roll back partial writes
- some saved artifacts are rerenderable

What is still missing:
- a shared restore-readiness model in runtime code
- one truthful manifest/helper layer across DB, bundle, and rerenderable assets
- a justified app-wide backup API

So the correct state remains:
- deferred ops lane

### 4. Reopening now would widen scope faster than evidence justifies

If reopened now:
- `Project Memory` risks backdooring a project/workspace model
- `local-backup-restore` risks overpromising a unified restore system that does not exist yet

Both would create more product/runtime surface area than the current evidence supports.

## Recommended next move

Do not start a new implementation lane from these deferred items.

Preferred next move:
- keep hardening the current active bounded specs only when real issues appear
- reopen deferred lanes only when their existing gate notes are triggered by real usage or an explicit product decision

## References

- `docs/reports/Local_Backup_Restore_Gate_2026-03-24.md`
- `docs/reports/Current_Baseline_Recheck_2026-03-18.md`
- `docs/Pending_PR_Queue.md`

## Conclusion

The current repo no longer needs another immediate bounded implementation lane.

The right move is restraint:
- keep `Project Memory API` deferred
- keep `local-backup-restore` deferred
- let active bounded specs carry the next round of real usage before opening new surface area
