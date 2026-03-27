# Local Backup Restore Gate (2026-03-24)

Status: Active
Date: 2026-03-24
Owner: Lattice runtime maintainers
Canonical parent: `docs/reports/Deferred_Lanes_Recheck_2026-03-24.md`

## Purpose

Record whether the `local-backup-restore` RFC should move from a future operations idea into immediate implementation work.

This is an implementation gate note, not a new runtime spec.

## Current repo state

Current repo already has real local safety patterns:
- local backup branch retention via `docs/Local_Backup_Branch_Retention_2026-02-24.md`
- DB backup-before-apply scripts such as `scripts/normalize_summaries.py` and `scripts/archive_legacy_failed_jobs.py`
- rollback-aware bounded bundle stores such as:
  - `src/meeting_packs/store.py`
  - `src/method_comparisons/store.py`
  - `src/chart_packs/store.py`
  - `src/protocol_cards/store.py`
  - `src/image_evidence/store.py`
  - `src/project_memory/store.py`

Current repo still does not have:
- a shared restore-readiness vocabulary wired into runtime code
- a unified backup manifest or helper layer
- an approved app-wide backup API
- honest restore guarantees for every bounded asset family

## Decision

Do not open `local-backup-restore` as an implementation lane yet.

Keep it at:
- historical RFC
- active gate note
- deferred queue item

for now.

## Why implementation should stay closed for now

### 1. Existing safety is real but heterogeneous

The repo already protects several risky operations.

But it does so through different mechanisms:
- git branch retention
- DB snapshot backup before mutation
- bundle-level write rollback
- rerenderable saved request state in selected bounded artifacts

These are all useful.

They are not yet one coherent restore system.

### 2. A unified backup layer would overstate current guarantees

Right now the repo can honestly say:
- some operations take a DB backup first
- some bounded bundles can roll back partial writes
- some saved artifacts are rerenderable

It cannot yet honestly say:
- every important asset has a direct restore path
- one manifest can describe restore safety across all bounded families
- a generic backup status means the same thing for DB state, file bundles, and rerenderable artifacts

### 3. The first safe abstraction is still documentation, not runtime

The RFC's `RestoreReadiness` vocabulary is useful.

But it is not yet attached to enough real code paths to justify:
- a `storage/backups/manifests/*.json` system
- shared backup helper utilities
- `POST /ops/backups/create`
- `POST /ops/backups/{backup_id}/restore-check`

Opening those too early would create an ops surface before the guarantees are real.

### 4. Current repo priorities are elsewhere

Recent work has gone into freezing bounded artifact families and preventing accidental platform drift.

`local-backup-restore` is important, but it is still an operations coherence problem, not the next product/runtime feature lane.

## What is safe to do now

Safe now:
- keep local branch retention policy as-is
- keep DB-mutation scripts on `dry-run` + `--apply` + backup-before-apply patterns
- keep rollback-aware bundle stores for bounded artifacts
- use this gate note to keep backup semantics honest

Not safe yet:
- introducing a generic backup manifest runtime
- opening an app-wide backup API
- claiming restore support where only rerenderability exists
- treating backup semantics as a reason to add `/projects` or workspace-wide ownership

## Reopen conditions

Revisit implementation only if at least one of these becomes true:

1. multiple bounded artifact families need a shared restore-readiness contract instead of subsystem-local rollback notes
2. operators need one explicit place to answer `direct_restore` vs `rerenderable` vs `manual_only` for real recovery workflows
3. a real incident shows that the current scattered safety docs/scripts are not enough to recover confidently

## Recommended next move

Do not implement `PR-OPS-BackupManifest-v0` yet.

Preferred next move:
- keep `future/local-backup-restore-semantics` as a deferred queue item
- if reopened later, start with a doc-only restore-readiness matrix before adding helpers or APIs

## Conclusion

The repo already has meaningful local safety discipline.

That is enough to justify the RFC and this gate note.

It is not yet enough to justify a unified backup/restore implementation lane.
